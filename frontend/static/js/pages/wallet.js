/**
 * pages/wallet.js — Quản lý ví, Nạp tiền Sandbox (SCRUM-195), Theo dõi đơn nạp (SCRUM-200) & Xem lịch sử giao dịch (SCRUM-74)
 */
(function () {
  'use strict';

  const LEDGER_PAGE_SIZE = 20;
  const TOPUP_PAGE_SIZE = 10;
  let _pageLedger = 1;
  let _pageTopups = 1;
  let _currentCreatedOrder = null;
  let _currentWalletTotals = null;

  // Cache for SCRUM-74 filtering
  let _rawLedgerItems = [];
  let _filteredLedgerItems = [];
  let _ledgerTypeFilter = 'all';
  let _ledgerSearchQuery = '';

  function fmtVND(amountInt) {
    if (amountInt == null) return '—';
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amountInt);
  }

  function fmtDatetime(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('vi-VN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function escHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // --- Load Wallet Totals & Balance Check (SCRUM-74 & SCRUM-199/72) ---
  async function loadWallet() {
    try {
      const w = await ApiClient.getWallet();
      _currentWalletTotals = w;

      const amountEl = document.getElementById('wallet-amount');
      if (amountEl) {
        amountEl.textContent = fmtVND(w.balance_vnd);
        if (w.balance_vnd < 0) {
          amountEl.style.color = 'var(--color-fault)';
        } else {
          amountEl.style.color = 'white';
        }
      }

      document.getElementById('wallet-sub').textContent = w.account_id ? `Mã tài khoản: ${w.account_id}` : '';
      document.getElementById('total-topup').textContent = fmtVND(w.total_topup_vnd);
      document.getElementById('total-spent').textContent = fmtVND(w.total_spent_vnd);

      await checkMinimumBalance(w.balance_vnd);
    } catch (err) {
      const amountEl = document.getElementById('wallet-amount');
      if (amountEl) amountEl.textContent = 'Lỗi tải';
      if (typeof showToast === 'function') {
        showToast(err.message || 'Không tải được số dư ví', 'error');
      }
    }
  }

  async function checkMinimumBalance(knownBalance) {
    const statusWrap = document.getElementById('wallet-min-balance-status');
    const indicator = document.getElementById('wallet-balance-indicator');
    if (!statusWrap || !indicator) return;

    try {
      const check = await ApiClient.checkWalletBalance(50000);
      statusWrap.style.display = 'block';
      if (check.has_minimum_balance) {
        indicator.className = 'badge badge--available';
        indicator.textContent = '✓ Đủ điều kiện bắt đầu sạc (≥ 50.000 ₫)';
      } else {
        indicator.className = 'badge badge--warning';
        indicator.textContent = '⚠ Cần nạp thêm: Số dư < 50.000 ₫ tối thiểu để kích hoạt sạc';
      }
    } catch {
      if (knownBalance != null) {
        statusWrap.style.display = 'block';
        if (knownBalance >= 50000) {
          indicator.className = 'badge badge--available';
          indicator.textContent = '✓ Số dư khả dụng (≥ 50.000 ₫)';
        } else {
          indicator.className = 'badge badge--warning';
          indicator.textContent = '⚠ Số dư dưới mức tối thiểu 50.000 ₫';
        }
      }
    }
  }

  // =========================================================================
  // SCRUM-74: Sổ cái giao dịch & Chi tiết lịch sử ví của Tài xế
  // =========================================================================
  async function loadLedger() {
    const period = document.getElementById('ledger-period')?.value || '30';
    const tbody = document.getElementById('ledger-tbody');
    try {
      // Load ledger items (max 50 per page request from backend)
      const data = await ApiClient.listLedger({ days: period, page: 1, page_size: 50 });
      _rawLedgerItems = data.items || data || [];

      // Update badge count
      const badgeEl = document.getElementById('badge-ledger-count');
      if (badgeEl) badgeEl.textContent = data.total || _rawLedgerItems.length;

      applyLedgerFilters();
    } catch (err) {
      if (tbody) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--color-fault);">Lỗi tải sổ cái: ${escHtml(err.message || 'Lỗi kết nối')}</td></tr>`;
      }
      if (typeof showToast === 'function') {
        showToast(err.message || 'Không tải được lịch sử sổ cái', 'error');
      }
    }
  }

  function applyLedgerFilters() {
    _ledgerTypeFilter = document.getElementById('ledger-type-filter')?.value || 'all';
    _ledgerSearchQuery = (document.getElementById('ledger-search-input')?.value || '').trim().toLowerCase();

    _filteredLedgerItems = _rawLedgerItems.filter((item) => {
      // Filter by type
      const isCredit = item.amount_vnd > 0;
      const entryType = item.entry_type || item.type;

      if (_ledgerTypeFilter === 'credit' && !isCredit) return false;
      if (_ledgerTypeFilter === 'debit' && isCredit) return false;
      if (_ledgerTypeFilter === 'session_charge' && entryType !== 'session_charge') return false;
      if (_ledgerTypeFilter === 'sandbox_topup' && entryType !== 'sandbox_topup') return false;
      if (_ledgerTypeFilter === 'manual_topup' && entryType !== 'manual_topup') return false;

      // Filter by search text
      if (_ledgerSearchQuery) {
        const desc = (item.description || '').toLowerCase();
        const ref = String(item.session_id || item.reference_code || item.reference_id || '').toLowerCase();
        const typeStr = String(entryType).toLowerCase();
        if (!desc.includes(_ledgerSearchQuery) && !ref.includes(_ledgerSearchQuery) && !typeStr.includes(_ledgerSearchQuery)) {
          return false;
        }
      }
      return true;
    });

    // Update summary note
    updateLedgerSummaryNote(_filteredLedgerItems);

    // Reset pagination to page 1
    _pageLedger = 1;
    renderLedgerSlice();
  }

  function updateLedgerSummaryNote(items) {
    const noteEl = document.getElementById('ledger-summary-note');
    if (!noteEl) return;

    let totalIn = 0;
    let totalOut = 0;
    items.forEach((it) => {
      if (it.amount_vnd > 0) totalIn += it.amount_vnd;
      else totalOut += Math.abs(it.amount_vnd);
    });

    noteEl.innerHTML = `Hiển thị <strong>${items.length}</strong> giao dịch | Tiền vào: <span class="ledger-credit">+${fmtVND(totalIn)}</span> | Tiền ra: <span class="ledger-debit">-${fmtVND(totalOut)}</span>`;
  }

  function renderLedgerSlice() {
    const tbody = document.getElementById('ledger-tbody');
    if (!tbody) return;

    if (!_filteredLedgerItems.length) {
      tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state" style="padding:32px 16px;text-align:center;"><div style="font-size:32px;margin-bottom:8px;">📒</div><div style="font-weight:600;">Không tìm thấy giao dịch phù hợp</div><div style="font-size:var(--font-size-xs);color:var(--color-text-muted);">Thử điều chỉnh bộ lọc hoặc từ khóa tìm kiếm.</div></div></td></tr>`;
      renderPagination(0, LEDGER_PAGE_SIZE, _pageLedger, 'ledger-pagination', () => {});
      return;
    }

    const start = (_pageLedger - 1) * LEDGER_PAGE_SIZE;
    const pageItems = _filteredLedgerItems.slice(start, start + LEDGER_PAGE_SIZE);

    tbody.innerHTML = pageItems.map((e, index) => {
      const isCredit = e.amount_vnd > 0;
      const entryType = e.entry_type || e.type;
      let typeLabel = 'Điều chỉnh';
      if (entryType === 'sandbox_topup') typeLabel = 'Nạp Sandbox';
      else if (entryType === 'payment_refund') typeLabel = 'Hoàn nạp Sandbox';
      else if (entryType === 'manual_topup') typeLabel = 'Nạp thủ công';
      else if (entryType === 'demo_topup') typeLabel = 'Nạp demo';
      else if (entryType === 'session_charge') typeLabel = 'Phiên sạc';
      else if (entryType === 'subscription_charge') typeLabel = 'Phí gói tháng';
      else if (entryType === 'refund') typeLabel = 'Hoàn tiền';

      let refLink = '';
      if (e.session_id) {
        refLink = `<div style="font-size:11px;margin-top:2px;"><a href="/sessions/mine" class="link-session-detail" title="Xem danh sách phiên sạc">⚡ Phiên #${escHtml(e.session_id)}</a></div>`;
      } else if (e.reference_code) {
        refLink = `<div style="font-size:11px;color:var(--color-text-muted);margin-top:2px;">Mã: ${escHtml(e.reference_code)}</div>`;
      }

      return `<tr class="clickable-row" data-index="${start + index}">
        <td style="white-space:nowrap;font-size:var(--font-size-xs);">${fmtDatetime(e.created_at)}</td>
        <td><span class="badge ${isCredit ? 'badge--available' : 'badge--fault'}">${typeLabel}</span></td>
        <td style="font-size:var(--font-size-sm);color:var(--color-text-secondary);">
          <div>${escHtml(e.description || '—')}</div>
          ${refLink}
        </td>
        <td class="text-right ${isCredit ? 'ledger-credit' : 'ledger-debit'}" style="font-weight:700;">
          ${isCredit ? '+' : ''}${fmtVND(e.amount_vnd)}
        </td>
        <td class="text-right" style="color:var(--color-text-secondary);font-weight:600;">
          ${fmtVND(e.balance_after_vnd)}
        </td>
        <td class="text-center">
          <button type="button" class="btn-ledger-detail" data-index="${start + index}" aria-label="Xem chi tiết bút toán">
            Chi tiết
          </button>
        </td>
      </tr>`;
    }).join('');

    // Attach row click events
    tbody.querySelectorAll('.clickable-row, .btn-ledger-detail').forEach((el) => {
      el.addEventListener('click', (ev) => {
        // Do not intercept if clicked directly on an anchor link
        if (ev.target.tagName === 'A') return;
        const idx = parseInt(el.getAttribute('data-index'), 10);
        if (!isNaN(idx) && _filteredLedgerItems[idx]) {
          openLedgerDetailModal(_filteredLedgerItems[idx]);
        }
      });
    });

    renderPagination(_filteredLedgerItems.length, LEDGER_PAGE_SIZE, _pageLedger, 'ledger-pagination', (p) => {
      _pageLedger = p;
      renderLedgerSlice();
    });
  }

  // --- Modal Chi tiết Giao dịch Sổ cái (SCRUM-74) ---
  const modalLedgerDetail = document.getElementById('ledger-detail-modal');

  function openLedgerDetailModal(item) {
    if (!modalLedgerDetail) return;

    const isCredit = item.amount_vnd > 0;
    const amountEl = document.getElementById('detail-amount');
    if (amountEl) {
      amountEl.textContent = (isCredit ? '+' : '') + fmtVND(item.amount_vnd);
      amountEl.style.color = isCredit ? 'var(--color-online)' : 'var(--color-fault)';
    }

    const typeBadgeEl = document.getElementById('detail-type-badge');
    const entryType = item.entry_type || item.type;
    let typeName = 'Bút toán điều chỉnh';
    if (entryType === 'sandbox_topup') typeName = 'Nạp tiền qua Cổng Sandbox';
    else if (entryType === 'payment_refund') typeName = 'Hoàn giao dịch nạp Sandbox';
    else if (entryType === 'manual_topup') typeName = 'Nạp tiền thủ công qua quản trị';
    else if (entryType === 'demo_topup') typeName = 'Nạp tiền thử nghiệm demo';
    else if (entryType === 'session_charge') typeName = 'Trừ chi phí phiên sạc';
    else if (entryType === 'subscription_charge') typeName = 'Trừ phí gói thuê bao tháng';
    else if (entryType === 'refund') typeName = 'Hoàn trả tiền';

    if (typeBadgeEl) {
      typeBadgeEl.innerHTML = `<span class="badge ${isCredit ? 'badge--available' : 'badge--fault'}">${typeName}</span>`;
    }

    document.getElementById('detail-entry-id').textContent = item.entry_id ? `#LEDGER-${item.entry_id}` : '—';
    document.getElementById('detail-created-at').textContent = fmtDatetime(item.created_at);
    document.getElementById('detail-balance-after').textContent = fmtVND(item.balance_after_vnd);

    let refText = 'Không có';
    if (item.session_id) {
      refText = `Phiên sạc #${item.session_id} (${item.reference_type || 'charging_session'})`;
    } else if (item.reference_code) {
      refText = `Mã đối soát / Phiếu: ${item.reference_code}`;
    } else if (item.reference_id) {
      refText = `${item.reference_type || 'tham_chieu'}: #${item.reference_id}`;
    }
    document.getElementById('detail-reference').textContent = refText;
    document.getElementById('detail-description').textContent = item.description || 'Không có mô tả bổ sung.';

    modalLedgerDetail.classList.add('is-open');
    modalLedgerDetail.setAttribute('aria-hidden', 'false');
  }

  function closeLedgerDetailModal() {
    if (!modalLedgerDetail) return;
    modalLedgerDetail.classList.remove('is-open');
    modalLedgerDetail.setAttribute('aria-hidden', 'true');
  }

  // --- Xuất Sao kê Giao dịch CSV (SCRUM-74) ---
  function exportLedgerCsv() {
    if (!_filteredLedgerItems.length) {
      if (typeof showToast === 'function') {
        showToast('Không có giao dịch nào để xuất sao kê', 'error');
      }
      return;
    }

    const headers = [
      'Mã bút toán',
      'Thời gian',
      'Loại giao dịch',
      'Mô tả',
      'Số tiền (VND)',
      'Số dư sau (VND)',
      'Mã phiên sạc',
      'Mã phiếu thu/đối soát',
    ];

    const rows = _filteredLedgerItems.map((e) => {
      const entryType = e.entry_type || e.type || '';
      return [
        `LEDGER-${e.entry_id || ''}`,
        `"${fmtDatetime(e.created_at)}"`,
        `"${entryType}"`,
        `"${(e.description || '').replace(/"/g, '""')}"`,
        e.amount_vnd || 0,
        e.balance_after_vnd || 0,
        e.session_id || '',
        `"${(e.reference_code || '').replace(/"/g, '""')}"`,
      ].join(',');
    });

    // UTF-8 BOM \uFEFF to preserve Vietnamese characters in Excel
    const csvContent = '\uFEFF' + headers.join(',') + '\n' + rows.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const dateStr = new Date().toISOString().slice(0, 10);
    const accountStr = _currentWalletTotals?.account_id || 'driver';
    a.href = url;
    a.download = `sao_ke_vi_${accountStr}_${dateStr}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    if (typeof showToast === 'function') {
      showToast('Đã xuất thành công file sao kê CSV!', 'success');
    }
  }

  // =========================================================================
  // SCRUM-200: Lịch sử đơn nạp tiền Sandbox (Payment Transactions)
  // =========================================================================
  async function loadTopupHistory() {
    const tbody = document.getElementById('topups-tbody');
    try {
      const res = await ApiClient.listTopupHistory({ page: _pageTopups, page_size: TOPUP_PAGE_SIZE });
      const items = res.items || [];
      const total = res.total || items.length;

      document.getElementById('badge-topup-count').textContent = total;
      document.getElementById('total-topup-count').textContent = total;

      renderTopupHistory(items);
      renderPagination(total, TOPUP_PAGE_SIZE, _pageTopups, 'topups-pagination', (p) => {
        _pageTopups = p;
        loadTopupHistory();
      });
    } catch (err) {
      if (tbody) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--color-fault);">Lỗi khi tải lịch sử đơn nạp: ${escHtml(err.message || 'Lỗi kết nối')}</td></tr>`;
      }
    }
  }

  function renderTopupHistory(items) {
    const tbody = document.getElementById('topups-tbody');
    if (!tbody) return;

    if (!items.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6">
            <div class="empty-state" style="padding:32px 16px;text-align:center;">
              <div style="font-size:32px;margin-bottom:8px;">💳</div>
              <div style="font-weight:600;margin-bottom:4px;">Chưa có đơn nạp tiền Sandbox</div>
              <div style="font-size:var(--font-size-xs);color:var(--color-text-muted);">
                Bấm "Nạp tiền vào ví" để thực hiện giao dịch thử nghiệm đầu tiên.
              </div>
            </div>
          </td>
        </tr>`;
      return;
    }

    tbody.innerHTML = items.map((tx) => {
      let statusBadge = '';
      if (tx.status === 'success') {
        statusBadge = '<span class="status-badge status-badge--success">● Thành công</span>';
      } else if (tx.status === 'pending') {
        statusBadge = '<span class="status-badge status-badge--pending">⏳ Chờ thanh toán</span>';
      } else if (tx.status === 'refunded') {
        statusBadge = '<span class="status-badge status-badge--failed">↩ Đã hoàn tiền</span>';
      } else if (tx.status === 'cancelled') {
        statusBadge = '<span class="status-badge status-badge--failed">✕ Đã hủy</span>';
      } else {
        statusBadge = '<span class="status-badge status-badge--failed">✕ ' + escHtml(tx.status || 'Thất bại') + '</span>';
      }
      const statusReason = tx.refund_reason || tx.failure_reason;
      const reasonHtml = statusReason
        ? `<div class="form-hint" title="${escHtml(statusReason)}">${escHtml(statusReason)}</div>`
        : '';

      let actionHtml = '';
      if (tx.status === 'pending') {
        actionHtml = `
          <div style="display:inline-flex;gap:4px;">
            <button type="button" class="btn btn--xs btn--primary btn-pay-now" data-order="${escHtml(tx.order_code)}" title="Xác nhận thanh toán mô phỏng">
              Thanh toán ngay
            </button>
            <a href="/wallet/sandbox-checkout?order_code=${encodeURIComponent(tx.order_code)}" class="btn btn--xs btn--secondary" title="Mở cổng Sandbox">
              Cổng
            </a>
          </div>`;
      } else if (tx.status === 'success') {
        actionHtml = `<button type="button" class="btn btn--xs btn--secondary btn-refund-topup" data-order="${escHtml(tx.order_code)}" title="Mô phỏng cổng hoàn lại khoản nạp">
          Mô phỏng hoàn tiền
        </button>`;
      } else if (tx.status === 'refunded') {
        actionHtml = '<span style="font-size:var(--font-size-xs);color:var(--color-text-muted);">Đã hoàn tiền</span>';
      } else {
        actionHtml = '<span style="font-size:var(--font-size-xs);color:var(--color-text-muted);">Không ghi có vào ví</span>';
      }

      const amountColor = tx.status === 'success'
        ? 'hsl(142,76%,36%)'
        : 'var(--color-text-secondary)';
      return `<tr>
        <td style="white-space:nowrap;font-size:var(--font-size-xs);">${fmtDatetime(tx.created_at)}</td>
        <td style="font-family:monospace;font-weight:600;font-size:var(--font-size-xs);color:var(--color-text);">${escHtml(tx.order_code)}</td>
        <td><span class="badge badge--neutral">${escHtml(tx.provider || 'sandbox')}</span></td>
        <td class="text-right" style="font-weight:700;color:${amountColor};">${fmtVND(tx.amount_vnd)}</td>
        <td>${statusBadge}${reasonHtml}</td>
        <td class="text-center">${actionHtml}</td>
      </tr>`;
    }).join('');

    // Attach click events for quick pay button inside table
    tbody.querySelectorAll('.btn-pay-now').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const orderCode = btn.getAttribute('data-order');
        if (!orderCode) return;
        btn.disabled = true;
        btn.textContent = 'Đang xử lý...';
        try {
          const res = await ApiClient.simulateSandboxPay(orderCode, 'success');
          if (typeof showToast === 'function') {
            showToast(`Nạp thành công ${fmtVND(res.amount_vnd)} vào ví!`, 'success');
          }
          await loadWallet();
          await loadTopupHistory();
          await loadLedger();
        } catch (err) {
          if (typeof showToast === 'function') {
            showToast(err.message || 'Thanh toán thất bại', 'error');
          }
          btn.disabled = false;
          btn.textContent = 'Thanh toán ngay';
        }
      });
    });

    tbody.querySelectorAll('.btn-refund-topup').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const orderCode = btn.getAttribute('data-order');
        if (!orderCode) return;
        btn.disabled = true;
        btn.textContent = 'Đang hoàn...';
        try {
          const result = await ApiClient.simulateSandboxPay(orderCode, 'refunded');
          if (typeof showToast === 'function') {
            showToast(
              result.status === 'refunded'
                ? `Đã ghi nhận hoàn ${fmtVND(result.amount_vnd)} từ ví.`
                : 'Không thể hoàn giao dịch ở trạng thái hiện tại.',
              result.status === 'refunded' ? 'success' : 'error',
            );
          }
          await loadWallet();
          await loadTopupHistory();
          await loadLedger();
        } catch (err) {
          if (typeof showToast === 'function') {
            showToast(err.message || 'Không thể hoàn giao dịch nạp tiền', 'error');
          }
          btn.disabled = false;
          btn.textContent = 'Mô phỏng hoàn tiền';
        }
      });
    });
  }

  // --- Phân trang dùng chung ---
  function renderPagination(total, pageSize, currentPage, targetElId, onPageClick) {
    const pages = Math.ceil(total / pageSize);
    const pg = document.getElementById(targetElId);
    if (!pg) return;
    pg.innerHTML = '';
    if (pages <= 1) return;

    for (let i = 1; i <= pages; i++) {
      const b = document.createElement('button');
      b.className = 'pagination__btn' + (i === currentPage ? ' is-active' : '');
      b.textContent = i;
      b.setAttribute('aria-label', `Trang ${i}`);
      if (i === currentPage) b.setAttribute('aria-current', 'page');
      b.addEventListener('click', () => onPageClick(i));
      pg.appendChild(b);
    }
  }

  // =========================================================================
  // SCRUM-195: Modal Nạp Tiền Sandbox
  // =========================================================================
  const modalTopup = document.getElementById('topup-modal');
  const amountInput = document.getElementById('topup-amount-input');
  const previewText = document.getElementById('topup-formatted-preview');
  const topupError = document.getElementById('topup-error');
  const btnSubmit = document.getElementById('btn-submit-topup');
  const spinner = document.getElementById('topup-spinner');

  function openTopupModal() {
    if (!modalTopup) return;
    resetTopupForm();
    modalTopup.classList.add('is-open');
    modalTopup.setAttribute('aria-hidden', 'false');
    if (amountInput) amountInput.focus();
  }

  function closeTopupModal() {
    if (!modalTopup) return;
    modalTopup.classList.remove('is-open');
    modalTopup.setAttribute('aria-hidden', 'true');
  }

  function resetTopupForm() {
    document.getElementById('topup-step-1').style.display = 'block';
    document.getElementById('topup-step-2').style.display = 'none';
    document.getElementById('step-1-actions').style.display = 'flex';
    document.getElementById('step-2-actions').style.display = 'none';
    if (topupError) topupError.style.display = 'none';
    const resBox = document.getElementById('step2-result');
    if (resBox) resBox.style.display = 'none';
    if (btnSubmit) btnSubmit.disabled = false;
    if (spinner) spinner.style.display = 'none';

    // Default to 100,000 VND
    if (amountInput) {
      amountInput.value = '100000';
      updateAmountPreview(100000);
    }
    document.querySelectorAll('.topup-preset-btn').forEach((btn) => {
      btn.classList.toggle('is-active', btn.getAttribute('data-amount') === '100000');
    });
  }

  function updateAmountPreview(val) {
    if (!previewText) return;
    const num = parseInt(val, 10);
    if (isNaN(num) || num < 10000) {
      previewText.textContent = 'Số tiền tối thiểu: 10.000 ₫';
      previewText.style.color = 'var(--color-fault)';
    } else if (num > 10000000) {
      previewText.textContent = 'Số tiền tối đa: 10.000.000 ₫';
      previewText.style.color = 'var(--color-fault)';
    } else {
      previewText.textContent = `Bằng số: ${fmtVND(num)}`;
      previewText.style.color = 'var(--color-primary-light)';
    }
  }

  async function handleCreateTopup() {
    const val = parseInt(amountInput.value, 10);
    if (isNaN(val) || val < 10000 || val > 10000000) {
      showTopupError('Số tiền nạp phải từ 10.000 ₫ đến 10.000.000 ₫.');
      return;
    }

    btnSubmit.disabled = true;
    spinner.style.display = 'inline-block';
    if (topupError) topupError.style.display = 'none';

    try {
      const order = await ApiClient.createSandboxTopup(val);
      _currentCreatedOrder = order;

      // Switch to Step 2
      document.getElementById('topup-step-1').style.display = 'none';
      document.getElementById('topup-step-2').style.display = 'block';
      document.getElementById('step-1-actions').style.display = 'none';
      document.getElementById('step-2-actions').style.display = 'flex';

      document.getElementById('step2-order-code').textContent = order.order_code;
      document.getElementById('step2-amount').textContent = fmtVND(order.amount_vnd);

      const goCheckoutBtn = document.getElementById('btn-step2-go-checkout');
      if (goCheckoutBtn) {
        goCheckoutBtn.href = order.payment_url || `/wallet/sandbox-checkout?order_code=${encodeURIComponent(order.order_code)}`;
      }

      // Refresh background history table
      loadTopupHistory();
    } catch (err) {
      showTopupError(err.message || 'Không thể tạo đơn nạp tiền sandbox.');
    } finally {
      btnSubmit.disabled = false;
      spinner.style.display = 'none';
    }
  }

  function showTopupError(msg) {
    if (!topupError) return;
    topupError.style.display = 'block';
    topupError.textContent = msg;
  }

  async function handleStep2QuickPay() {
    if (!_currentCreatedOrder) return;
    const btnQuickPay = document.getElementById('btn-step2-quick-pay');
    const resBox = document.getElementById('step2-result');

    btnQuickPay.disabled = true;
    resBox.style.display = 'block';
    resBox.className = 'alert alert--info';
    resBox.textContent = 'Đang mô phỏng giao dịch thành công qua cổng Sandbox...';

    try {
      const res = await ApiClient.simulateSandboxPay(_currentCreatedOrder.order_code, 'success');
      resBox.className = 'alert alert--success';
      resBox.innerHTML = `<strong>Thanh toán thành công!</strong> Đã nạp <strong>${fmtVND(res.amount_vnd)}</strong> vào ví.<br>Số dư mới: <strong>${fmtVND(res.balance_vnd)}</strong>.`;

      document.getElementById('step2-status').className = 'badge badge--available';
      document.getElementById('step2-status').textContent = 'Thành công (Success)';

      if (typeof showToast === 'function') {
        showToast(`Nạp ví thành công ${fmtVND(res.amount_vnd)}!`, 'success');
      }

      await loadWallet();
      await loadTopupHistory();
      await loadLedger();

      setTimeout(() => {
        closeTopupModal();
      }, 1500);
    } catch (err) {
      resBox.className = 'alert alert--danger';
      resBox.textContent = err.message || 'Lỗi khi mô phỏng thanh toán';
      btnQuickPay.disabled = false;
    }
  }

  // --- Tabs Navigation ---
  function setupTabs() {
    const btnTabTopups = document.getElementById('tab-btn-topups');
    const btnTabLedger = document.getElementById('tab-btn-ledger');
    const paneTopups = document.getElementById('tab-pane-topups');
    const paneLedger = document.getElementById('tab-pane-ledger');
    const ledgerFilter = document.getElementById('ledger-filter-wrap');
    const topupsActions = document.getElementById('topups-actions-wrap');

    btnTabTopups?.addEventListener('click', () => {
      btnTabTopups.classList.add('is-active');
      btnTabTopups.setAttribute('aria-selected', 'true');
      btnTabLedger.classList.remove('is-active');
      btnTabLedger.setAttribute('aria-selected', 'false');

      paneTopups.style.display = 'block';
      paneLedger.style.display = 'none';
      if (ledgerFilter) ledgerFilter.style.display = 'none';
      if (topupsActions) topupsActions.style.display = 'block';
    });

    btnTabLedger?.addEventListener('click', () => {
      btnTabLedger.classList.add('is-active');
      btnTabLedger.setAttribute('aria-selected', 'true');
      btnTabTopups.classList.remove('is-active');
      btnTabTopups.setAttribute('aria-selected', 'false');

      paneLedger.style.display = 'block';
      paneTopups.style.display = 'none';
      if (ledgerFilter) ledgerFilter.style.display = 'flex';
      if (topupsActions) topupsActions.style.display = 'none';
    });
  }

  // --- Initializer ---
  document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    loadWallet();
    loadLedger();
    loadTopupHistory();

    // Check URL params for topup_success
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('topup_success') === '1') {
      if (typeof showToast === 'function') {
        showToast('Nạp tiền vào ví thành công qua Cổng Sandbox!', 'success');
      }
      const cleanUrl = window.location.pathname;
      window.history.replaceState({}, document.title, cleanUrl);
    }

    // Refresh buttons
    document.getElementById('btn-refresh-wallet')?.addEventListener('click', () => {
      loadWallet();
      loadTopupHistory();
      loadLedger();
    });
    document.getElementById('btn-refresh-topups')?.addEventListener('click', () => {
      loadTopupHistory();
    });

    // Ledger toolbar filters (SCRUM-74)
    document.getElementById('ledger-period')?.addEventListener('change', () => {
      loadLedger();
    });
    document.getElementById('ledger-type-filter')?.addEventListener('change', () => {
      applyLedgerFilters();
    });
    document.getElementById('ledger-search-input')?.addEventListener('input', () => {
      applyLedgerFilters();
    });
    document.getElementById('btn-export-ledger-csv')?.addEventListener('click', exportLedgerCsv);

    // Ledger detail modal events
    document.getElementById('btn-close-ledger-detail')?.addEventListener('click', closeLedgerDetailModal);
    document.getElementById('btn-done-ledger-detail')?.addEventListener('click', closeLedgerDetailModal);
    modalLedgerDetail?.addEventListener('click', (e) => {
      if (e.target === modalLedgerDetail) closeLedgerDetailModal();
    });

    // Topup modal triggers
    document.getElementById('btn-open-topup')?.addEventListener('click', openTopupModal);
    document.getElementById('btn-open-topup-header')?.addEventListener('click', openTopupModal);
    document.getElementById('btn-close-topup-modal')?.addEventListener('click', closeTopupModal);
    document.getElementById('btn-cancel-topup')?.addEventListener('click', closeTopupModal);
    document.getElementById('btn-done-topup')?.addEventListener('click', closeTopupModal);

    modalTopup?.addEventListener('click', (e) => {
      if (e.target === modalTopup) closeTopupModal();
    });

    // Preset pills click
    document.querySelectorAll('.topup-preset-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.topup-preset-btn').forEach((b) => b.classList.remove('is-active'));
        btn.classList.add('is-active');
        const amt = btn.getAttribute('data-amount');
        if (amountInput) {
          amountInput.value = amt;
          updateAmountPreview(amt);
        }
      });
    });

    // Amount input change
    amountInput?.addEventListener('input', (e) => {
      const v = e.target.value;
      updateAmountPreview(v);
      document.querySelectorAll('.topup-preset-btn').forEach((btn) => {
        btn.classList.toggle('is-active', btn.getAttribute('data-amount') === v);
      });
    });

    // Submit topup
    btnSubmit?.addEventListener('click', handleCreateTopup);

    // Step 2 quick simulation
    document.getElementById('btn-step2-quick-pay')?.addEventListener('click', handleStep2QuickPay);
  });
})();
