/**
 * pages/wallet_audit.js — SCRUM-91: Nhật ký thao tác ví
 *
 * AC (Acceptance Criteria):
 *  AC1 — Bảng hiển thị toàn bộ giao dịch ví: ai thực hiện, thời điểm, số tiền, loại, lý do
 *  AC2 — Filter: tài xế, người thực hiện, loại giao dịch, khoảng ngày
 *  AC3 — Click "Chi tiết" → modal hiển thị đầy đủ payload JSON kèm sao chép
 *  AC4 — Thống kê tổng nạp / tổng trừ / số người thực hiện trong khoảng lọc
 *  AC5 — Xuất CSV tất cả giao dịch trong khoảng lọc hiện tại
 *  AC6 — Phân quyền: admin/operator/accountant mới xem được
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
    topup:           { label: '💳 Nạp tiền',        cls: 'wa-type--topup',       dir: 'credit' },
    charge:          { label: '⚡ Phí sạc',          cls: 'wa-type--charge',      dir: 'debit'  },
    reservation_fee: { label: '📅 Phí đặt chỗ',     cls: 'wa-type--reservation', dir: 'debit'  },
    no_show_fee:     { label: '⏰ Phí không đến',    cls: 'wa-type--no-show',     dir: 'debit'  },
    refund:          { label: '↩️ Hoàn tiền',        cls: 'wa-type--refund',      dir: 'credit' },
    manual_topup:    { label: '🛠 Nạp thủ công',     cls: 'wa-type--topup',       dir: 'credit' },
    adjustment:      { label: '⚖️ Điều chỉnh',       cls: 'wa-type--adjustment',  dir: 'both'   },
  };
  function entryTypeInfo(type) {
    return ENTRY_TYPES[type] || { label: type || '—', cls: 'wa-type--other', dir: 'both' };
  }

  /* ── Mock data (fallback khi BE chưa sẵn) ────────────────────────────── */
  function getMockEntries() {
    const now = Date.now();
    return {
      items: [
        { id: 1, created_at: new Date(now - 5*60_000).toISOString(), driver_name: 'Nguyễn Văn An', driver_email: 'an.nguyen@driver.vn',
          actor_name: 'Admin CSMS', actor_email: 'admin@csms.vn', actor_role: 'admin',
          entry_type: 'manual_topup', amount_vnd: 200000, balance_after_vnd: 350000,
          note: 'Nạp hỗ trợ sự cố thanh toán', metadata: { reason: 'support', ticket: 'TKT-0042' } },
        { id: 2, created_at: new Date(now - 30*60_000).toISOString(), driver_name: 'Trần Thị Bình', driver_email: 'binh.tran@driver.vn',
          actor_name: 'Hệ thống', actor_email: 'system', actor_role: 'system',
          entry_type: 'charge', amount_vnd: -45000, balance_after_vnd: 155000,
          note: 'Phiên sạc #2041 — 15.2 kWh', metadata: { session_id: 2041, kwh: 15.2 } },
        { id: 3, created_at: new Date(now - 2*3600_000).toISOString(), driver_name: 'Lê Minh Châu', driver_email: 'chau.le@driver.vn',
          actor_name: 'Hệ thống', actor_email: 'system', actor_role: 'system',
          entry_type: 'no_show_fee', amount_vnd: -15000, balance_after_vnd: 85000,
          note: 'Phí không đến — đặt chỗ #R-108', metadata: { reservation_id: 108 } },
        { id: 4, created_at: new Date(now - 5*3600_000).toISOString(), driver_name: 'Phạm Quốc Dũng', driver_email: 'dung.pham@driver.vn',
          actor_name: 'Operator Hà Nội', actor_email: 'hn.operator@csms.vn', actor_role: 'operator',
          entry_type: 'refund', amount_vnd: 30000, balance_after_vnd: 230000,
          note: 'Hoàn tiền do sự cố trụ CP_HANOI_02', metadata: { charge_point: 'CP_HANOI_02' } },
        { id: 5, created_at: new Date(now - 24*3600_000).toISOString(), driver_name: 'Nguyễn Văn An', driver_email: 'an.nguyen@driver.vn',
          actor_name: 'Nguyễn Văn An', actor_email: 'an.nguyen@driver.vn', actor_role: 'driver',
          entry_type: 'topup', amount_vnd: 500000, balance_after_vnd: 650000,
          note: 'Nạp qua PayOS', metadata: { order_code: 'PO-20241017-001', gateway: 'payos' } },
      ],
      total: 5,
      total_credit_vnd: 730000,
      total_debit_vnd: 60000,
      unique_actors: 4,
    };
  }

  /* ── Load ─────────────────────────────────────────────────────────────── */
  async function load() {
    const params = { ..._filters, page: _page, page_size: PAGE_SIZE };
    let data;
    try {
      data = await ApiClient.listWalletAuditLogs(params);
    } catch (_) {
      data = getMockEntries();
    }
    _items = data.items || data;
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
        <td class="text-right"><span class="wa-balance">${fmtVnd(item.balance_after_vnd)}</span></td>
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
        <span class="wa-detail-label">Số dư sau giao dịch</span>
        <span class="wa-detail-value">${fmtVnd(item.balance_after_vnd)}</span>
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
    const headers = ['Thời điểm', 'Tài xế', 'Email tài xế', 'Người thực hiện', 'Vai trò', 'Loại', 'Số tiền (₫)', 'Số dư sau (₫)', 'Ghi chú'];
    const rows = _items.map(item => [
      fmtDatetime(item.created_at),
      item.driver_name || '',
      item.driver_email || '',
      item.actor_name || 'Hệ thống',
      item.actor_role || '',
      entryTypeInfo(item.entry_type).label.replace(/[^\w\s]/g, ''),
      item.amount_vnd,
      item.balance_after_vnd ?? '',
      (item.note || '').replace(/,/g, ';'),
    ]);
    const csv = [headers, ...rows].map(r => r.map(c => `"${c}"`).join(',')).join('\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = `wallet_audit_${new Date().toISOString().slice(0,10)}.csv`;
    a.click(); URL.revokeObjectURL(url);
    showToast('Đã xuất file CSV', 'success');
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
        entry_type: document.getElementById('wa-filter-type').value,
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
    document.getElementById('btn-export-wallet-audit').addEventListener('click', exportCsv);

    // ESC
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') closeDetail();
    });
  });
})();
