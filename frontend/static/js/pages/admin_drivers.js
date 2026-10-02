/** Driver account balances and auditable manual wallet top-ups. */
(function () {
  'use strict';

  const PAGE_SIZE = 20;
  let page = 1;
  let query = '';
  let searchTimer;
  let selectedDriver = null;

  const money = value => new Intl.NumberFormat('vi-VN', {
    style: 'currency', currency: 'VND', maximumFractionDigits: 0,
  }).format(value || 0);
  const dateTime = value => value
    ? new Date(value).toLocaleString('vi-VN', { dateStyle: 'medium', timeStyle: 'short' })
    : 'Chưa có phiên sạc';
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);

  async function loadDrivers() {
    const tbody = document.getElementById('driver-wallet-tbody');
    tbody.innerHTML = '<tr><td colspan="6" class="driver-table-message">Đang tải danh sách tài xế...</td></tr>';
    try {
      const result = await ApiClient.listDriverWallets({ q: query, page, page_size: PAGE_SIZE });
      renderRows(result.items || []);
      renderPagination(result.total || 0);
      document.getElementById('driver-count').textContent = `${result.total || 0} tài khoản tài xế`;
    } catch (error) {
      tbody.innerHTML = '<tr><td colspan="6" class="driver-table-message">Không tải được danh sách tài xế.</td></tr>';
      showToast(error.message || 'Không tải được ví tài xế', 'error');
    }
  }

  function renderRows(drivers) {
    const tbody = document.getElementById('driver-wallet-tbody');
    if (!drivers.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="driver-table-message">Không tìm thấy tài khoản tài xế.</td></tr>';
      return;
    }
    tbody.innerHTML = drivers.map(driver => `<tr>
      <td><div class="driver-cell__name">${escapeHtml(driver.full_name)}</div><div class="driver-cell__email">${escapeHtml(driver.email)}</div></td>
      <td><span class="badge ${driver.is_active ? 'badge--available' : 'badge--fault'}">${driver.is_active ? 'Đang hoạt động' : 'Đã khóa'}</span></td>
      <td class="text-right driver-money">${money(driver.balance_vnd)}</td>
      <td class="text-right">${money(driver.total_spent_vnd)}</td>
      <td class="driver-last-charge">${dateTime(driver.last_charge_at)}</td>
      <td class="text-right">${window.WalletAdmin.canTopUp && driver.is_active
        ? `<button class="btn btn--primary btn--sm" type="button" data-topup-driver="${driver.id}" data-driver-name="${escapeHtml(driver.full_name)}">Nạp tiền</button>`
        : '<span class="driver-readonly">Chỉ xem</span>'}</td>
    </tr>`).join('');
    tbody.querySelectorAll('[data-topup-driver]').forEach(button => {
      button.addEventListener('click', () => openTopUp(button.dataset.topupDriver, button.dataset.driverName));
    });
  }

  function renderPagination(total) {
    const pages = Math.ceil(total / PAGE_SIZE);
    const container = document.getElementById('driver-pagination');
    container.innerHTML = '';
    if (pages <= 1) return;
    const addButton = (label, target, disabled, ariaLabel) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'pagination__btn';
      button.textContent = label;
      button.setAttribute('aria-label', ariaLabel);
      button.disabled = disabled;
      button.addEventListener('click', () => { page = target; loadDrivers(); });
      container.appendChild(button);
    };
    addButton('‹', page - 1, page === 1, 'Trang trước');
    const current = document.createElement('span');
    current.className = 'driver-page-label';
    current.textContent = `Trang ${page} / ${pages}`;
    container.appendChild(current);
    addButton('›', page + 1, page === pages, 'Trang sau');
  }

  function openTopUp(driverId, driverName) {
    selectedDriver = driverId;
    document.getElementById('topup-driver-name').textContent = driverName;
    document.getElementById('topup-form').reset();
    document.getElementById('topup-dialog').showModal();
    document.getElementById('topup-amount').focus();
  }

  async function submitTopUp(event) {
    event.preventDefault();
    if (!selectedDriver) return;
    const form = event.currentTarget;
    if (!form.reportValidity()) return;
    const submit = document.getElementById('topup-submit');
    submit.disabled = true;
    try {
      const amount = Number(document.getElementById('topup-amount').value);
      const receipt = document.getElementById('topup-receipt').value.trim();
      const result = await ApiClient.manualTopUp(selectedDriver, {
        amount_vnd: amount, receipt_code: receipt,
      });
      document.getElementById('topup-dialog').close();
      showToast(`Đã nạp ${money(result.amount_vnd)}. Số dư mới: ${money(result.balance_vnd)}.`, 'success');
      await loadDrivers();
    } catch (error) {
      showToast(error.message || 'Không ghi nhận được khoản nạp', 'error');
    } finally {
      submit.disabled = false;
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    loadDrivers();
    document.getElementById('btn-refresh-drivers').addEventListener('click', loadDrivers);
    document.getElementById('driver-search').addEventListener('input', event => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => { query = event.target.value.trim(); page = 1; loadDrivers(); }, 250);
    });
    document.getElementById('topup-form')?.addEventListener('submit', submitTopUp);
    document.getElementById('topup-close')?.addEventListener('click', () => document.getElementById('topup-dialog').close());
    document.getElementById('topup-cancel')?.addEventListener('click', () => document.getElementById('topup-dialog').close());
    document.getElementById('topup-dialog')?.addEventListener('click', event => {
      if (event.target === event.currentTarget) event.currentTarget.close();
    });
  });
})();
