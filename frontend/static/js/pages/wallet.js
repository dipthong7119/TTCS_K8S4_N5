/**
 * pages/wallet.js — Quản lý ví, Nạp tiền Sandbox (SCRUM-195) & Trạng thái giao dịch (SCRUM-200)
 */
(function () {
  'use strict';

  const LEDGER_PAGE_SIZE = 50;
  const TOPUP_PAGE_SIZE = 10;
  let _pageLedger = 1;
  let _pageTopups = 1;
  let _currentCreatedOrder = null;

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

  // --- Load Wallet Totals & Balance Check ---
  async function loadWallet() {
    try {
      const w = await ApiClient.getWallet();
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

  // --- SCRUM-200: Lịch sử đơn nạp tiền Sandbox (Payment Transactions) ---
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
      } else {
        statusBadge = '<span class="status-badge status-badge--failed">✕ ' + escHtml(tx.status || 'Thất bại') + '</span>';
      }

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
        actionHtml = '<span style="font-size:var(--font-size-xs);color:var(--color-text-muted);">Đã hoàn tất</span>';
      } else {
        actionHtml = '<span style="font-size:var(--font-size-xs);color:var(--color-text-muted);">Đã hủy</span>';
      }

      return `<tr>
        <td style="white-space:nowrap;font-size:var(--font-size-xs);">${fmtDatetime(tx.created_at)}</td>
        <td style="font-family:monospace;font-weight:600;font-size:var(--font-size-xs);color:var(--color-text);">${escHtml(tx.order_code)}</td>
        <td><span class="badge badge--neutral">${escHtml(tx.provider || 'sandbox')}</span></td>
        <td class="text-right" style="font-weight:700;color:hsl(142,76%,36%);">${fmtVND(tx.amount_vnd)}</td>
        <td>${statusBadge}</td>
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
  }

  // --- Sổ cái giao dịch (Ledger) ---
  async function loadLedger() {
    const period = document.getElementById('ledger-period')?.value || '30';
    try {
      const data = await ApiClient.listLedger({ days: period, page: _pageLedger, page_size: LEDGER_PAGE_SIZE });
      const items = data.items || data || [];
      renderLedger(items);
      renderPagination(data.total || items.length, LEDGER_PAGE_SIZE, _pageLedger, 'ledger-pagination', (p) => {
        _pageLedger = p;
        loadLedger();
      });
    } catch (err) {
      if (typeof showToast === 'function') {
        showToast(err.message || 'Không tải được lịch sử sổ cái', 'error');
      }
    }
  }

  function renderLedger(items) {
    const tbody = document.getElementById('ledger-tbody');
    if (!tbody) return;

    if (!items.length) {
      tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state" style="padding:32px 16px;text-align:center;"><div style="font-size:32px;margin-bottom:8px;">📒</div><div style="font-weight:600;">Chưa có giao dịch sổ cái</div></div></td></tr>`;
      return;
    }

    tbody.innerHTML = items.map((e) => {
      const isCredit = e.amount_vnd > 0;
      const entryType = e.entry_type || e.type;
      let typeLabel = 'Điều chỉnh';
      if (entryType === 'sandbox_topup') typeLabel = 'Nạp Sandbox';
      else if (entryType === 'manual_topup') typeLabel = 'Nạp thủ công';
      else if (entryType === 'demo_topup') typeLabel = 'Nạp demo';
      else if (entryType === 'session_charge') typeLabel = 'Phiên sạc';
      else if (entryType === 'subscription_charge') typeLabel = 'Phí gói tháng';
      else if (entryType === 'refund') typeLabel = 'Hoàn tiền';

      return `<tr>
        <td style="white-space:nowrap;font-size:var(--font-size-xs);">${fmtDatetime(e.created_at)}</td>
        <td><span class="badge ${isCredit ? 'badge--available' : 'badge--fault'}">${typeLabel}</span></td>
        <td style="font-size:var(--font-size-sm);color:var(--color-text-secondary);">${escHtml(e.description || '—')}</td>
        <td class="text-right ${isCredit ? 'ledger-credit' : 'ledger-debit'}">${isCredit ? '+' : ''}${fmtVND(e.amount_vnd)}</td>
        <td class="text-right" style="color:var(--color-text-secondary);">${fmtVND(e.balance_after_vnd)}</td>
      </tr>`;
    }).join('');
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

  // --- SCRUM-195: Modal Nạp Tiền Sandbox ---
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
      if (ledgerFilter) ledgerFilter.style.display = 'block';
      if (topupsActions) topupsActions.style.display = 'none';
    });
  }

  // --- Initializer ---
  document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    loadWallet();
    loadTopupHistory();
    loadLedger();

    // Check URL params for topup_success
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('topup_success') === '1') {
      if (typeof showToast === 'function') {
        showToast('Nạp tiền vào ví thành công qua Cổng Sandbox!', 'success');
      }
      // Remove params from URL cleanly
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
    document.getElementById('ledger-period')?.addEventListener('change', () => {
      _pageLedger = 1;
      loadLedger();
    });

    // Modal triggers
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
