(function () {
  'use strict';

  const fromInput = document.getElementById('rev-share-from');
  const toInput = document.getElementById('rev-share-to');
  const partnerInput = document.getElementById('rev-share-partner');
  const errBox = document.getElementById('rev-share-error');
  const loadBox = document.getElementById('rev-share-loading');
  const notReadyBox = document.getElementById('rev-share-not-ready');
  const tbody = document.getElementById('rev-share-tbody');
  const tfoot = document.getElementById('rev-share-tfoot');
  const btnApply = document.getElementById('btn-apply-filter');
  let requestVersion = 0;
  const money = value => `${Number(value || 0).toLocaleString('vi-VN')} ₫`;
  const energy = value => `${Number(value || 0).toLocaleString('vi-VN', { maximumFractionDigits: 3 })} kWh`;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

  function isoDate(value) {
    return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
  }

  function showError(message) {
    errBox.textContent = message;
    errBox.hidden = false;
    notReadyBox.hidden = true;
  }

  function onDateChange() {
    requestVersion += 1;
    errBox.hidden = true;
    setLoading(false);
    notReadyBox.hidden = false;
    tfoot.hidden = true;
    document.getElementById('stat-base-revenue').textContent = '—';
    document.getElementById('stat-shared-amount').textContent = '—';
    tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">Áp dụng bộ lọc để tải lại bảng kê.</td></tr>';
  }

  function setLoading(loading) {
    loadBox.hidden = !loading;
    if (loading) {
      errBox.hidden = true;
      notReadyBox.hidden = true;
      tfoot.hidden = true;
      tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">Đang tải bảng kê...</td></tr>';
      document.getElementById('stat-base-revenue').textContent = '—';
      document.getElementById('stat-shared-amount').textContent = '—';
      btnApply.disabled = true;
    } else {
      btnApply.disabled = false;
    }
  }

  function renderPartners(partners) {
    const selected = partnerInput.value;
    partnerInput.replaceChildren(new Option('Tất cả đối tác', ''));
    partners.forEach(partner => {
      partnerInput.add(new Option(`${partner.name} (${partner.email})`, String(partner.id)));
    });
    if ([...partnerInput.options].some(option => option.value === selected)) {
      partnerInput.value = selected;
    }
  }

  function renderReport(report) {
    renderPartners(report.partners || []);
    const items = report.items || [];
    document.getElementById('stat-base-revenue').textContent = money(report.totals?.base_revenue_vnd);
    document.getElementById('stat-shared-amount').textContent = money(report.totals?.shared_amount_vnd);

    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">Không có lượt sử dụng gói thuê bao trong kỳ đã chọn.</td></tr>';
      tfoot.hidden = true;
      notReadyBox.hidden = true;
      return;
    }

    tbody.innerHTML = items.map(item => `<tr>
      <td><strong>${esc(item.partner_name)}</strong><br><small>${esc(item.partner_email)}</small></td>
      <td>${esc(item.policy_label)}</td>
      <td class="text-right">${Number(item.share_percent)}%</td>
      <td class="text-right">${money(item.base_revenue_vnd)}</td>
      <td class="text-right"><strong>${money(item.shared_amount_vnd)}</strong><br><small>${energy(item.energy_kwh)}</small></td>
    </tr>`).join('');
    document.getElementById('tfoot-base-revenue').textContent = money(report.totals?.base_revenue_vnd);
    document.getElementById('tfoot-shared-amount').textContent = money(report.totals?.shared_amount_vnd);
    tfoot.hidden = false;
    notReadyBox.hidden = true;
  }

  async function applyFilter() {
    const version = ++requestVersion;
    const from = fromInput.value;
    const to = toInput.value;
    if (!from || !to) {
      setLoading(false);
      showError('Vui lòng chọn đầy đủ ngày bắt đầu và kết thúc.');
      return;
    }
    if (from > to) {
      setLoading(false);
      showError('Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.');
      return;
    }

    setLoading(true);
    try {
      const report = await ApiClient.getRevenueShareReport({
        date_from: from,
        date_to: to,
        station_owner_id: partnerInput.value || undefined,
      });
      if (version !== requestVersion) return;
      renderReport(report);
    } catch (error) {
      if (version !== requestVersion) return;
      showError(error?.message || 'Không tải được bảng kê chia doanh thu.');
      tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">Không tải được dữ liệu.</td></tr>';
      tfoot.hidden = true;
    } finally {
      if (version === requestVersion) setLoading(false);
    }
  }

  function setDates(from, to) {
    fromInput.value = isoDate(from);
    toInput.value = isoDate(to);
    applyFilter();
  }

  function setQuickFilter(type) {
    const now = new Date();
    if (type === 'today') return setDates(now, now);
    if (type === 'week') {
      const day = now.getDay();
      const monday = new Date(now.getFullYear(), now.getMonth(), now.getDate() + (day === 0 ? -6 : 1 - day));
      return setDates(monday, new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + 6));
    }
    setDates(new Date(now.getFullYear(), now.getMonth(), 1), new Date(now.getFullYear(), now.getMonth() + 1, 0));
  }

  document.getElementById('btn-quick-today')?.addEventListener('click', () => setQuickFilter('today'));
  document.getElementById('btn-quick-week')?.addEventListener('click', () => setQuickFilter('week'));
  document.getElementById('btn-quick-month')?.addEventListener('click', () => setQuickFilter('month'));
  btnApply?.addEventListener('click', applyFilter);
  partnerInput?.addEventListener('change', applyFilter);
  fromInput?.addEventListener('input', onDateChange);
  toInput?.addEventListener('input', onDateChange);
  fromInput?.addEventListener('change', onDateChange);
  toInput?.addEventListener('change', onDateChange);

  setQuickFilter('month');
})();
