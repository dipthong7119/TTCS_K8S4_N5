/**
 * pages/subscriptions.js — SCRUM-68: Giao diện đăng ký gói thuê bao hàng tháng cho tài xế
 */
(function () {
  'use strict';

  let plans = [];
  let activeSub = null;
  let history = [];
  let walletBalance = 0;
  let selectedPlan = null;

  function money(value) {
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(value || 0);
  }

  function moneyRate(value) {
    return (value || 0).toLocaleString('vi-VN') + ' ₫/kWh';
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[char]);
  }

  function formatDate(isoStr) {
    if (!isoStr) return '—';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString('vi-VN', { year: 'numeric', month: '2-digit', day: '2-digit' });
    } catch (_) {
      return isoStr;
    }
  }

  function formatDateTime(isoStr) {
    if (!isoStr) return '—';
    try {
      const d = new Date(isoStr);
      return d.toLocaleString('vi-VN', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit'
      });
    } catch (_) {
      return isoStr;
    }
  }

  function calculateDaysRemaining(expiresAtStr) {
    if (!expiresAtStr) return '';
    const exp = new Date(expiresAtStr).getTime();
    const now = Date.now();
    const diff = exp - now;
    if (diff <= 0) return 'Đã hết hạn';
    const days = Math.ceil(diff / (1000 * 60 * 60 * 24));
    return `Còn lại ${days} ngày`;
  }

  async function loadData() {
    try {
      const [plansData, mySubsData, walletData] = await Promise.all([
        ApiClient.listSubscriptionPlans(),
        ApiClient.getMySubscriptions(),
        ApiClient.getWallet().catch(() => ({ balance_vnd: 0 })),
      ]);

      plans = Array.isArray(plansData) ? plansData : [];
      activeSub = mySubsData.active_subscription || null;
      history = mySubsData.subscriptions || [];
      walletBalance = walletData.balance_vnd || 0;

      renderActiveSubscription();
      renderPlans();
      renderHistory();
    } catch (err) {
      if (typeof showToast === 'function') {
        showToast(err.message || 'Không thể tải thông tin gói thuê bao', 'error');
      }
    }
  }

  function renderActiveSubscription() {
    const cardEl = document.getElementById('active-sub-card');
    const noCardEl = document.getElementById('no-active-sub-card');

    if (activeSub && activeSub.is_active) {
      noCardEl.style.display = 'none';
      cardEl.style.display = 'block';

      document.getElementById('active-plan-name').textContent = activeSub.plan_name || 'Gói thuê bao tháng';
      document.getElementById('active-time-remaining').textContent = calculateDaysRemaining(activeSub.expires_at);
      document.getElementById('active-rate').textContent = moneyRate(activeSub.price_vnd_per_kwh);
      document.getElementById('active-fee').textContent = money(activeSub.monthly_fee_vnd);
      document.getElementById('active-starts').textContent = formatDate(activeSub.starts_at);
      document.getElementById('active-expires').textContent = formatDate(activeSub.expires_at);
    } else {
      cardEl.style.display = 'none';
      noCardEl.style.display = 'block';
    }
  }

  function renderPlans() {
    const grid = document.getElementById('plans-grid');
    if (!plans.length) {
      grid.innerHTML = '<div class="text-center" style="grid-column: 1 / -1; padding: 32px; color: var(--color-text-secondary);">Hiện tại chưa có gói thuê bao nào được mở đăng ký.</div>';
      return;
    }

    grid.innerHTML = plans.map(plan => {
      const isCurrentPlan = activeSub && activeSub.is_active && activeSub.plan_id === plan.id;
      const hasOtherActive = activeSub && activeSub.is_active && activeSub.plan_id !== plan.id;

      let actionBtn = '';
      if (isCurrentPlan) {
        actionBtn = '<button class="btn btn--secondary" type="button" disabled>Đang sử dụng</button>';
      } else if (hasOtherActive) {
        actionBtn = '<button class="btn btn--secondary" type="button" disabled title="Bạn đang có gói hiệu lực. Chỉ đăng ký gói mới khi gói cũ hết hạn.">Đã có gói hiệu lực</button>';
      } else {
        actionBtn = `<button class="btn btn--primary" type="button" data-plan-id="${plan.id}">Đăng ký ngay</button>`;
      }

      return `
        <article class="plan-card ${plan.name.toLowerCase().includes('tiết kiệm') || plan.name.toLowerCase().includes('pro') ? 'plan-card--featured' : ''}">
          <div>
            ${plan.name.toLowerCase().includes('tiết kiệm') || plan.name.toLowerCase().includes('pro') ? '<span class="plan-card__badge-top">Phổ biến</span>' : ''}
            <h3 class="plan-card__title">${escapeHtml(plan.name)}</h3>
            ${plan.description ? `<p class="plan-card__description">${escapeHtml(plan.description)}</p>` : ''}
            <div class="plan-card__pricing">
              <div class="plan-card__fee">${escapeHtml(money(plan.monthly_fee_vnd))} <span class="plan-card__fee-unit">/ tháng</span></div>
              <div class="plan-card__rate">⚡ Giá sạc ưu đãi: ${escapeHtml(moneyRate(plan.price_vnd_per_kwh))}</div>
            </div>
            <ul class="plan-card__features">
              <li>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                Áp dụng mọi trạm sạc trên toàn quốc
              </li>
              <li>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                Hiệu lực trọn vẹn 1 tháng dương lịch
              </li>
              <li>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                Trừ phí tự động từ số dư ví tài xế
              </li>
            </ul>
          </div>
          <div class="plan-card__action">
            ${actionBtn}
          </div>
        </article>
      `;
    }).join('');

    grid.querySelectorAll('[data-plan-id]').forEach(btn => {
      btn.addEventListener('click', () => {
        const pId = Number(btn.dataset.planId);
        const targetPlan = plans.find(p => p.id === pId);
        if (targetPlan) {
          openSubscribeModal(targetPlan);
        }
      });
    });
  }

  function renderHistory() {
    const tbody = document.getElementById('history-tbody');
    const countEl = document.getElementById('history-count');
    countEl.textContent = `${history.length} chu kỳ`;

    if (!history.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center" style="padding: 32px 16px; color: var(--color-text-secondary);">Chưa có lịch sử đăng ký gói thuê bao.</td></tr>';
      return;
    }

    tbody.innerHTML = history.map(item => {
      const badgeHtml = item.is_active
        ? '<span class="badge badge--available">Đang hiệu lực</span>'
        : '<span class="badge badge--fault" style="opacity: 0.85;">Đã kết thúc</span>';

      return `
        <tr>
          <td><strong>${escapeHtml(item.plan_name || 'Gói tháng')}</strong></td>
          <td class="text-right">${escapeHtml(money(item.monthly_fee_vnd))}</td>
          <td class="text-right"><span style="color: var(--color-success, #16a34a); font-weight: 600;">${escapeHtml(moneyRate(item.price_vnd_per_kwh))}</span></td>
          <td>${escapeHtml(formatDateTime(item.starts_at))}</td>
          <td>${escapeHtml(formatDateTime(item.expires_at))}</td>
          <td>${badgeHtml}</td>
        </tr>
      `;
    }).join('');
  }

  function openSubscribeModal(plan) {
    selectedPlan = plan;
    const dialog = document.getElementById('subscribe-dialog');
    if (!dialog) return;

    document.getElementById('modal-plan-name').textContent = plan.name;
    document.getElementById('modal-plan-rate').textContent = moneyRate(plan.price_vnd_per_kwh);
    document.getElementById('modal-wallet-balance').textContent = money(walletBalance);
    document.getElementById('modal-plan-fee').textContent = money(plan.monthly_fee_vnd);

    const balanceAfter = walletBalance - plan.monthly_fee_vnd;
    const isInsufficient = balanceAfter < 0;

    const afterRow = document.getElementById('modal-balance-after-row');
    const afterEl = document.getElementById('modal-balance-after');
    const warningEl = document.getElementById('modal-insufficient-warning');
    const goTopupBtn = document.getElementById('btn-go-topup');
    const confirmBtn = document.getElementById('btn-confirm-subscribe');

    if (isInsufficient) {
      afterRow.style.display = 'none';
      warningEl.style.display = 'flex';
      goTopupBtn.style.display = 'inline-flex';
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Số dư không đủ';
    } else {
      afterRow.style.display = 'flex';
      afterEl.textContent = money(balanceAfter);
      warningEl.style.display = 'none';
      goTopupBtn.style.display = 'none';
      confirmBtn.disabled = false;
      confirmBtn.textContent = 'Xác nhận thanh toán';
    }

    dialog.showModal();
  }

  async function handleConfirmSubscribe() {
    if (!selectedPlan) return;
    const confirmBtn = document.getElementById('btn-confirm-subscribe');
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Đang xử lý trừ ví...';

    try {
      const result = await ApiClient.subscribePlan(selectedPlan.id);
      document.getElementById('subscribe-dialog').close();
      if (typeof showToast === 'function') {
        showToast(`Đăng ký thành công gói ${result.plan_name || selectedPlan.name}! Biểu giá ưu đãi ${moneyRate(result.price_vnd_per_kwh)} đã được kích hoạt.`, 'success');
      }
      selectedPlan = null;
      await loadData();
    } catch (err) {
      let msg = err.message || 'Đăng ký gói thuê bao thất bại';
      if (msg.includes('402') || msg.toLowerCase().includes('số dư')) {
        msg = 'Số dư ví không đủ để thanh toán gói thuê bao này. Vui lòng nạp thêm tiền vào ví.';
      } else if (msg.includes('409') || msg.toLowerCase().includes('hiệu lực')) {
        msg = 'Tài khoản đang có một gói thuê bao còn hiệu lực. Bạn chỉ có thể gia hạn khi gói cũ kết thúc.';
      }
      if (typeof showToast === 'function') {
        showToast(msg, 'error');
      }
    } finally {
      confirmBtn.disabled = false;
      confirmBtn.textContent = 'Xác nhận thanh toán';
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    loadData();

    const dialog = document.getElementById('subscribe-dialog');
    const closeDialog = () => dialog?.close();

    document.getElementById('btn-dialog-close')?.addEventListener('click', closeDialog);
    document.getElementById('btn-dialog-cancel')?.addEventListener('click', closeDialog);
    dialog?.addEventListener('click', event => {
      if (event.target === dialog) closeDialog();
    });

    document.getElementById('btn-confirm-subscribe')?.addEventListener('click', handleConfirmSubscribe);
  });
})();
