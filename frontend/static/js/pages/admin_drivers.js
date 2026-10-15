/** Driver account balances and auditable manual wallet top-ups. */
(function () {
  'use strict';

  const PAGE_SIZE = 20;
  let page = 1;
  let query = '';
  let searchTimer;
  let selectedDriver = null; // { id, name, balance }

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

  function checkCanTopUp() {
    if (window.WalletAdmin && typeof window.WalletAdmin.canTopUp === 'boolean') {
      return window.WalletAdmin.canTopUp;
    }
    if (document.getElementById('topup-dialog')) {
      return true;
    }
    try {
      const auth = JSON.parse(document.getElementById('auth-context')?.textContent || '{}');
      return Array.isArray(auth.roles) && auth.roles.includes('admin');
    } catch (_) {
      return false;
    }
  }

  function renderRows(drivers) {
    const tbody = document.getElementById('driver-wallet-tbody');
    if (!drivers.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="driver-table-message">Không tìm thấy tài khoản tài xế.</td></tr>';
      return;
    }
    const hasTopUpPermission = checkCanTopUp();
    tbody.innerHTML = drivers.map(driver => {
      const isNegative = (driver.balance_vnd || 0) < 0;
      const balanceClass = `text-right driver-money${isNegative ? ' driver-money--negative' : ''}`;
      const negativeTag = isNegative ? ' <span class="badge badge--fault badge--xs" title="Tài xế đang nợ - số dư âm">Nợ</span>' : '';
      return `<tr>
        <td><div class="driver-cell__name">${escapeHtml(driver.full_name)}</div><div class="driver-cell__email">${escapeHtml(driver.email)}</div></td>
        <td><span class="badge ${driver.is_active ? 'badge--available' : 'badge--fault'}">${driver.is_active ? 'Đang hoạt động' : 'Đã khóa'}</span></td>
        <td class="${balanceClass}">${money(driver.balance_vnd)}${negativeTag}</td>
        <td class="text-right">${money(driver.total_spent_vnd)}</td>
        <td class="driver-last-charge">${dateTime(driver.last_charge_at)}</td>
        <td class="text-right">${hasTopUpPermission && driver.is_active
          ? `<button class="btn btn--primary btn--sm" type="button" data-topup-driver="${driver.id}" data-driver-name="${escapeHtml(driver.full_name)}" data-driver-balance="${driver.balance_vnd || 0}">Nạp tiền</button>`
          : '<span class="driver-readonly">Chỉ xem</span>'}</td>
      </tr>`;
    }).join('');
    tbody.querySelectorAll('[data-topup-driver]').forEach(button => {
      button.addEventListener('click', () => openTopUp(
        button.dataset.topupDriver,
        button.dataset.driverName,
        Number(button.dataset.driverBalance),
      ));
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

  function openTopUp(driverId, driverName, balance) {
    selectedDriver = { id: driverId, name: driverName, balance };
    document.getElementById('topup-driver-name').textContent = driverName;
    const balanceEl = document.getElementById('topup-driver-balance');
    const isNeg = balance < 0;
    balanceEl.textContent = `Số dư hiện tại: ${money(balance)}${isNeg ? ' (đang nợ)' : ''}`;
    balanceEl.className = `topup-driver-balance${isNeg ? ' topup-driver-balance--negative' : ''}`;
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
    submit.textContent = 'Đang ghi nhận...';
    try {
      const amount = Number(document.getElementById('topup-amount').value);
      const receipt = document.getElementById('topup-receipt').value.trim();
      const note = (document.getElementById('topup-note')?.value || '').trim();
      const result = await ApiClient.manualTopUp(selectedDriver.id, {
        amount_vnd: amount,
        receipt_code: receipt,
        ...(note ? { note } : {}),
      });
      document.getElementById('topup-dialog').close();
      showToast(
        `Đã nạp ${money(result.amount_vnd || result.amount)} cho ${escapeHtml(selectedDriver.name)}. Số dư mới: ${money(result.balance_vnd || result.balance_after)}.`,
        'success',
      );
      selectedDriver = null;
      await loadDrivers();
    } catch (error) {
      // Phân biệt lỗi trùng mã phiếu (409) với lỗi khác
      const isConflict = error.message?.includes('409') || error.message?.toLowerCase().includes('phiếu');
      showToast(
        isConflict
          ? 'Mã phiếu thu này đã được sử dụng. Vui lòng kiểm tra lại mã phiếu.'
          : (error.message || 'Không ghi nhận được khoản nạp'),
        'error',
      );
    } finally {
      submit.disabled = false;
      submit.textContent = 'Ghi nhận nạp tiền';
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
