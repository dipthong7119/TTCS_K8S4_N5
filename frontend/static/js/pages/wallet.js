/**
 * pages/wallet.js — Trang ví điện tử (S-40)
 */
(function () {
  'use strict';

  const PAGE_SIZE = 20;
  let _page = 1;

  function fmtVND(amountInt) {
    if (amountInt == null) return '—';
    return new Intl.NumberFormat('vi-VN', { style:'currency', currency:'VND' }).format(amountInt);
  }
  function fmtDatetime(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('vi-VN', { day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit' });
  }
  function escHtml(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

  async function loadWallet() {
    try {
      const w = await ApiClient.getWallet();
      document.getElementById('wallet-amount').textContent = fmtVND(w.balance_vnd);
      document.getElementById('wallet-sub').textContent = w.account_id ? `Tài khoản: ${w.account_id}` : '';
      document.getElementById('total-topup').textContent = fmtVND(w.total_topup_vnd);
      document.getElementById('total-spent').textContent  = fmtVND(w.total_spent_vnd);
      if (w.balance_vnd < 0) {
        document.getElementById('wallet-amount').style.color = 'var(--color-fault)';
      }
    } catch (err) {
      document.getElementById('wallet-amount').textContent = 'Lỗi tải';
      showToast(err.message || 'Không tải được số dư', 'error');
    }
  }

  async function loadLedger() {
    const period = document.getElementById('ledger-period').value;
    try {
      const data = await ApiClient.listLedger({ days: period, page: _page, page_size: PAGE_SIZE });
      const items = data.items || data;
      renderLedger(items);
      renderPagination(data.total || items.length);
    } catch (err) {
      showToast(err.message || 'Không tải được lịch sử', 'error');
    }
  }

  function renderLedger(items) {
    const tbody = document.getElementById('ledger-tbody');
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="5"><div class="empty-state"><div class="empty-state__icon">📒</div><div class="empty-state__title">Chưa có giao dịch</div></div></td></tr>';
      return;
    }
    tbody.innerHTML = items.map(e => {
      const isCredit = e.type === 'topup' || e.amount_vnd > 0;
      return `<tr>
        <td style="white-space:nowrap;font-size:var(--font-size-xs);">${fmtDatetime(e.created_at)}</td>
        <td><span class="badge ${isCredit ? 'badge--available' : 'badge--fault'}">${isCredit ? 'Nạp tiền' : 'Thanh toán'}</span></td>
        <td style="font-size:var(--font-size-sm);color:var(--color-text-secondary);">${escHtml(e.description||'—')}</td>
        <td class="text-right ${isCredit ? 'ledger-credit' : 'ledger-debit'}">${isCredit ? '+' : ''}${fmtVND(e.amount_vnd)}</td>
        <td class="text-right" style="color:var(--color-text-secondary);">${fmtVND(e.balance_after_vnd)}</td>
      </tr>`;
    }).join('');
  }

  function renderPagination(total) {
    const pages = Math.ceil(total / PAGE_SIZE);
    const pg = document.getElementById('ledger-pagination');
    pg.innerHTML = '';
    if (pages <= 1) return;
    for (let i = 1; i <= pages; i++) {
      const b = document.createElement('button');
      b.className = 'pagination__btn' + (i === _page ? ' is-active' : '');
      b.textContent = i; b.setAttribute('aria-label', `Trang ${i}`);
      if (i === _page) b.setAttribute('aria-current', 'page');
      b.addEventListener('click', () => { _page = i; loadLedger(); });
      pg.appendChild(b);
    }
  }

  // ── Top-up modal ──
  const topupModal = document.getElementById('topup-modal');

  function openTopup() { topupModal.classList.remove('is-hidden'); }
  function closeTopup() { topupModal.classList.add('is-hidden'); }

  document.addEventListener('DOMContentLoaded', () => {
    loadWallet();
    loadLedger();

    document.getElementById('btn-topup')?.addEventListener('click', openTopup);
    document.getElementById('btn-refresh-wallet')?.addEventListener('click', () => { loadWallet(); loadLedger(); });
    document.getElementById('topup-modal-close')?.addEventListener('click', closeTopup);
    document.getElementById('topup-cancel')?.addEventListener('click', closeTopup);
    topupModal?.addEventListener('click', e => { if (e.target === topupModal) closeTopup(); });

    document.getElementById('ledger-period')?.addEventListener('change', () => { _page = 1; loadLedger(); });

    // Quick amount buttons
    document.querySelectorAll('.quick-amount-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.quick-amount-btn').forEach(b => b.classList.remove('is-selected'));
        btn.classList.add('is-selected');
        document.getElementById('topup-amount').value = btn.dataset.amount;
      });
    });

    // Top-up submit
    const topupForm = document.getElementById('topup-form');
    FormGuard.protect(topupForm, async (data) => {
      const amount = parseInt(data.amount, 10);
      if (isNaN(amount) || amount < 10000) throw { message: 'Số tiền tối thiểu là 10.000 ₫' };
      if (amount > 10000000) throw { message: 'Số tiền tối đa là 10.000.000 ₫' };
      const result = await ApiClient.topUp(amount);
      // Redirect to payment gateway
      if (result.payment_url) {
        window.location.href = result.payment_url;
      } else {
        showToast('Nạp tiền thành công', 'success');
        closeTopup();
        loadWallet();
        loadLedger();
      }
    }, { loadingText: 'Đang xử lý...' });
  });
})();
