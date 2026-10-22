/**
 * pages/wallet_audit.js — SCRUM-91: Nhật ký thao tác ví
 *
 * AC (Acceptance Criteria):
 *  AC1 — Bảng hiển thị toàn bộ giao dịch ví: ai thực hiện, thời điểm, số tiền, loại, lý do
 *  AC2 — Filter: tài xế, người thực hiện, loại giao dịch, khoảng ngày
 *  AC3 — Click "Chi tiết" → modal hiển thị đầy đủ payload JSON kèm sao chép
 *  AC4 — Thống kê tổng nạp / tổng trừ / số người thực hiện trong khoảng lọc
 *  AC5 — Xuất CSV tất cả giao dịch trong khoảng lọc hiện tại
 *  AC6 — Phân quyền: admin/accountant mới xem được
 */
(function () {
  'use strict';

  const PAGE_SIZE = 50;
  let _page   = 1;
  let _items  = [];
  let _total  = 0;
  let _currentDetail = null;
  let _filters = {};

  /* ── Helpers ──────────────────────────────────────────────────────────── */
  function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  }
  function fmtVnd(n) {
    if (n == null) return '—';
    return Number(n).toLocaleString('vi-VN') + ' ₫';
  }
  function fmtDatetime(iso) {
    if (!iso) return '—';
    const d = new Date((/Z|[+-]\d{2}:\d{2}$/i).test(iso) ? iso : iso + 'Z');
    return isNaN(d) ? '—' : d.toLocaleString('vi-VN', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  }
  function getInitials(name) {
    if (!name) return '?';
    const parts = name.trim().split(/\s+/);
    return parts.length === 1 ? parts[0].slice(0, 2).toUpperCase()
      : (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  /* ── Entry type config ────────────────────────────────────────────────── */
  const ENTRY_TYPES = {
    'wallet.manual_topup': { label: '🛠 Nạp thủ công', cls: 'wa-type--topup',      dir: 'credit' },
    'wallet.adjust':       { label: '⚖️ Điều chỉnh',   cls: 'wa-type--adjustment', dir: 'both'   },
    'wallet.lock':         { label: '🔒 Khóa ví',      cls: 'wa-type--other',      dir: 'both'   },
    'wallet.unlock':       { label: '🔓 Mở khóa ví',   cls: 'wa-type--other',      dir: 'both'   },
    'wallet.sandbox_topup_created': { label: '🧾 Nạp sandbox · chờ thanh toán', cls: 'wa-type--other', dir: 'both' },
    'wallet.sandbox_topup_success': { label: '💳 Nạp sandbox · thành công', cls: 'wa-type--topup', dir: 'credit' },
    'wallet.sandbox_simulated_pay': { label: '💳 Nạp sandbox · mô phỏng', cls: 'wa-type--topup', dir: 'credit' },
    'wallet.sandbox_topup_refunded': { label: '↩️ Hoàn nạp sandbox', cls: 'wa-type--adjustment', dir: 'debit' },
    'wallet.sandbox_simulated_refund': { label: '↩️ Hoàn nạp sandbox', cls: 'wa-type--adjustment', dir: 'debit' },
  };
  function entryTypeInfo(type) {
    return ENTRY_TYPES[type] || { label: type || '—', cls: 'wa-type--other', dir: 'both' };
  }

  function normalizeAuditEntry(entry) {
    const details = entry.details || {};
    let amountVnd = Number(details.amount_vnd || 0);
    const action = entry.action || '';
    if (action === 'wallet.sandbox_topup_refunded' || action === 'wallet.sandbox_simulated_refund') {
      amountVnd = -Math.abs(amountVnd);
    } else if (action.startsWith('wallet.sandbox_') && ![
      'wallet.sandbox_topup_success',
      'wallet.sandbox_simulated_pay',
    ].includes(action)) {
      amountVnd = 0;
    }
    return {
      ...entry,
      entry_type: entry.action,
      amount_vnd: amountVnd,
      note: details.reason || details.receipt_code || details.reference_code || entry.action,
      metadata: details,
      actor_name: entry.actor_name || 'Hệ thống',
      actor_role: entry.actor_role || 'system',
    };
  }

  /* ── Load ─────────────────────────────────────────────────────────────── */
  async function load() {
    const params = { ..._filters, page: _page, page_size: PAGE_SIZE };
    const tbody = document.getElementById('wa-tbody');
    const filterButton = document.getElementById('btn-wa-filter');
    filterButton.disabled = true;
    tbody.setAttribute('aria-busy', 'true');
    tbody.innerHTML = `<tr><td colspan="8"><div class="loading-state" style="padding:var(--space-8);">
      <div class="spinner" aria-hidden="true"></div><p>Đang tải nhật ký...</p></div></td></tr>`;
    document.getElementById('wa-count').textContent = 'Đang tải...';
    let data;
    try {
      data = await ApiClient.listWalletAuditLogs(params);
    } catch (error) {
      _items = [];
      _total = 0;
      updateStats({ total: 0, total_credit_vnd: 0, total_debit_vnd: 0, unique_actors: 0 });
      renderTable();
      renderPagination();
      document.getElementById('wa-count').textContent = 'Không tải được dữ liệu';
      showToast(error?.message || 'Không tải được nhật ký ví.', 'error');
      return;
    } finally {
      filterButton.disabled = false;
      tbody.setAttribute('aria-busy', 'false');
    }
    _items = (data.items || []).map(normalizeAuditEntry);
    _total = data.total || _items.length;
    updateStats(data);
    renderTable();
    renderPagination();
    document.getElementById('wa-count').textContent = `${_total} bản ghi`;
  }

  function updateStats(data) {
    document.getElementById('wa-stat-total').textContent  = (data.total || _items.length).toLocaleString('vi-VN');
    document.getElementById('wa-stat-credit').textContent = fmtVnd(data.total_credit_vnd);
    document.getElementById('wa-stat-debit').textContent  = fmtVnd(Math.abs(data.total_debit_vnd || 0));
    document.getElementById('wa-stat-actors').textContent = data.unique_actors ?? '—';
  }

  /* ── Render table ─────────────────────────────────────────────────────── */
  function renderTable() {
    const tbody = document.getElementById('wa-tbody');
    if (!_items.length) {
      tbody.innerHTML = `<tr><td colspan="8">
        <div class="empty-state">
          <div class="empty-state__icon">📒</div>
          <div class="empty-state__title">Không có giao dịch nào</div>
          <div class="empty-state__desc">Thử thay đổi bộ lọc hoặc khoảng thời gian</div>
        </div></td></tr>`;
      return;
    }
    tbody.innerHTML = _items.map(item => {
      const info    = entryTypeInfo(item.entry_type);
      const isDebit = item.amount_vnd < 0;
      const amtCls  = isDebit ? 'wa-amount--debit' : 'wa-amount--credit';
      const amtPrefix = isDebit ? '' : '+';
      const isSystem = item.actor_role === 'system' || item.actor_email === 'system';
      const avatarCls = isSystem ? 'wa-actor-avatar wa-actor-avatar--system' : 'wa-actor-avatar';

      return `<tr data-id="${item.id}">
        <td style="white-space:nowrap;font-size:var(--font-size-xs);">${fmtDatetime(item.created_at)}</td>
        <td>
          <div style="font-weight:600;font-size:var(--font-size-sm);">${esc(item.driver_name || '—')}</div>
          <div style="font-size:11px;color:var(--color-text-secondary);">${esc(item.driver_email || '')}</div>
        </td>
        <td>
          <div class="wa-actor">
            <div class="${avatarCls}">${isSystem ? '⚙' : esc(getInitials(item.actor_name))}</div>
            <div>
              <div class="wa-actor-name" title="${esc(item.actor_name)}">${esc(item.actor_name || 'Hệ thống')}</div>
              <div class="wa-actor-role">${esc(item.actor_role || '')}</div>
            </div>
          </div>
        </td>
        <td><span class="wa-type-badge ${info.cls}">${info.label}</span></td>
        <td class="text-right"><span class="wa-amount ${amtCls}">${amtPrefix}${fmtVnd(item.amount_vnd)}</span></td>
        <td><span class="wa-note">${esc(item.object_type || '—')}${item.object_id ? ` #${esc(item.object_id)}` : ''}</span></td>
        <td><span class="wa-note" title="${esc(item.note)}">${esc(item.note || '—')}</span></td>
        <td class="text-right">
          <button class="btn btn--ghost btn--sm btn-wa-detail" data-id="${item.id}" type="button">Chi tiết</button>
        </td>
      </tr>`;
    }).join('');

    tbody.querySelectorAll('.btn-wa-detail').forEach(btn => {
      btn.addEventListener('click', () => openDetail(btn.dataset.id));
    });
  }

  /* ── Pagination ───────────────────────────────────────────────────────── */
  function renderPagination() {
    const pages   = Math.ceil(_total / PAGE_SIZE);
    const prevBtn = document.getElementById('wa-prev');
    const nextBtn = document.getElementById('wa-next');
    const pagesEl = document.getElementById('wa-pages');
    const label   = document.getElementById('wa-page-label');

    prevBtn.disabled = _page <= 1;
    nextBtn.disabled = _page >= pages;
    label.textContent = pages > 1 ? `Trang ${_page} / ${pages}` : `${_total} bản ghi`;

    pagesEl.innerHTML = '';
    if (pages <= 1) return;
    const start = Math.max(1, _page - 2);
    const end   = Math.min(pages, _page + 2);
    for (let i = start; i <= end; i++) {
      const b = document.createElement('button');
      b.className = 'pagination__btn' + (i === _page ? ' is-active' : '');
      b.textContent = i;
      b.setAttribute('aria-label', `Trang ${i}`);
      if (i === _page) b.setAttribute('aria-current', 'page');
      b.addEventListener('click', () => { _page = i; load(); });
      pagesEl.appendChild(b);
    }
  }

  /* ── Detail modal ─────────────────────────────────────────────────────── */
  function openDetail(id) {
    const item = _items.find(x => String(x.id) === String(id));
    if (!item) return;
    _currentDetail = item;
    const info = entryTypeInfo(item.entry_type);
    const isDebit = item.amount_vnd < 0;

    document.getElementById('wa-detail-body').innerHTML = `
      <div class="wa-detail-item">
        <span class="wa-detail-label">Thời điểm</span>
        <span class="wa-detail-value">${fmtDatetime(item.created_at)}</span>
      </div>
      <div class="wa-detail-item">
        <span class="wa-detail-label">Loại giao dịch</span>
        <span class="wa-detail-value"><span class="wa-type-badge ${info.cls}">${info.label}</span></span>
      </div>
      <div class="wa-detail-item">
        <span class="wa-detail-label">Tài xế</span>
        <span class="wa-detail-value">${esc(item.driver_name || '—')} <span style="color:var(--color-text-secondary);font-size:11px;">${esc(item.driver_email || '')}</span></span>
      </div>
      <div class="wa-detail-item">
        <span class="wa-detail-label">Người thực hiện</span>
        <span class="wa-detail-value">${esc(item.actor_name || 'Hệ thống')} <span style="color:var(--color-text-secondary);font-size:11px;">[${esc(item.actor_role || '')}]</span></span>
      </div>
      <div class="wa-detail-item">
        <span class="wa-detail-label">Số tiền</span>
        <span class="wa-detail-value" style="font-weight:700;font-size:var(--font-size-base);color:${isDebit ? 'hsl(0,65%,45%)' : 'hsl(130,55%,38%)'};">
          ${isDebit ? '' : '+'}${fmtVnd(item.amount_vnd)}
        </span>
      </div>
      <div class="wa-detail-item">
        <span class="wa-detail-label">Giao dịch liên quan</span>
        <span class="wa-detail-value">${esc(item.object_type || '—')}${item.object_id ? ` #${esc(item.object_id)}` : ''}</span>
      </div>
      <div class="wa-detail-item wa-detail-item--full">
        <span class="wa-detail-label">Ghi chú / Lý do</span>
        <span class="wa-detail-value">${esc(item.note || '—')}</span>
      </div>
      <div class="wa-detail-item wa-detail-item--full">
        <span class="wa-detail-label">Metadata (JSON)</span>
        <pre class="wa-json-box"><code>${esc(JSON.stringify(item.metadata || {}, null, 2))}</code></pre>
      </div>`;

    document.getElementById('wa-detail-modal').classList.remove('is-hidden');
  }

  function closeDetail() {
    document.getElementById('wa-detail-modal').classList.add('is-hidden');
    _currentDetail = null;
  }

  /* ── CSV Export ───────────────────────────────────────────────────────── */
  function exportCsv() {
    const headers = ['Thời điểm', 'Tài xế', 'Email tài xế', 'Người thực hiện', 'Vai trò', 'Loại', 'Số tiền (₫)', 'Loại giao dịch', 'Mã giao dịch', 'Ghi chú'];
    const rows = _items.map(item => [
      fmtDatetime(item.created_at),
      item.driver_name || '',
      item.driver_email || '',
      item.actor_name || 'Hệ thống',
      item.actor_role || '',
      entryTypeInfo(item.entry_type).label.replace(/[^\w\s]/g, ''),
      item.amount_vnd,
      item.object_type || '',
      item.object_id || '',
      item.note || '',
    ]);
    const csv = [headers, ...rows].map(r => r.map(c => `"${String(c ?? '').replace(/"/g, '""')}"`).join(',')).join('\r\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = `wallet_audit_${new Date().toISOString().slice(0,10)}.csv`;
    a.click(); URL.revokeObjectURL(url);
    showToast('Đã xuất file CSV', 'success');
  }

  async function exportAllCsv() {
    try {
      const items = [];
      let page = 1;
      let total = 0;
      do {
        const data = await ApiClient.listWalletAuditLogs({ ..._filters, page, page_size: PAGE_SIZE });
        items.push(...(data.items || []).map(normalizeAuditEntry));
        total = data.total || 0;
        page++;
      } while (items.length < total);
      const original = _items;
      _items = items;
      exportCsv();
      _items = original;
    } catch (error) {
      showToast(error?.message || 'Không xuất được báo cáo CSV.', 'error');
    }
  }

  /* ── DOMContentLoaded ────────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', () => {
    load();

    // Filters
    document.getElementById('wa-filters').addEventListener('submit', e => {
      e.preventDefault();
      _filters = {
        driver:     document.getElementById('wa-filter-driver').value.trim(),
        actor:      document.getElementById('wa-filter-actor').value.trim(),
        action:     document.getElementById('wa-filter-type').value,
        date_from:  document.getElementById('wa-filter-from').value,
        date_to:    document.getElementById('wa-filter-to').value,
      };
      _page = 1; load();
    });
    document.getElementById('btn-wa-reset').addEventListener('click', () => {
      document.getElementById('wa-filters').reset();
      _filters = {}; _page = 1; load();
    });

    // Pagination
    document.getElementById('wa-prev').addEventListener('click', () => { if (_page > 1) { _page--; load(); } });
    document.getElementById('wa-next').addEventListener('click', () => { _page++; load(); });

    // Detail modal
    document.getElementById('wa-detail-close').addEventListener('click',    closeDetail);
    document.getElementById('wa-detail-ok').addEventListener('click',       closeDetail);
    document.getElementById('wa-detail-backdrop').addEventListener('click', closeDetail);
    document.getElementById('wa-detail-copy').addEventListener('click', () => {
      if (!_currentDetail) return;
      navigator.clipboard.writeText(JSON.stringify(_currentDetail, null, 2))
        .then(() => showToast('Đã sao chép JSON', 'success'))
        .catch(() => showToast('Không thể sao chép', 'error'));
    });

    // Export
    document.getElementById('btn-export-wallet-audit').addEventListener('click', exportAllCsv);

    // ESC
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') closeDetail();
    });
  });
})();
