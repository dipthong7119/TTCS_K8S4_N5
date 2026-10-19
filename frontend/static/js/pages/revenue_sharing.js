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
  const exportButton = document.getElementById('btn-export-csv');
  const exportMessage = document.getElementById('rev-share-export-message');
  const contractForm = document.getElementById('revenue-contract-form');
  const contractPartner = document.getElementById('contract-partner');
  const contractPartnerPercent = document.getElementById('contract-partner-percent');
  const contractPlatformPercent = document.getElementById('contract-platform-percent');
  const contractEffectiveFrom = document.getElementById('contract-effective-from');
  const contractMessage = document.getElementById('contract-message');
  const contractHistory = document.getElementById('contract-history-body');
  const contractSave = document.getElementById('contract-save');
  let requestVersion = 0;
  let reportLoaded = false;
  const money = value => `${Number(value || 0).toLocaleString('vi-VN')} ₫`;
  const energy = value => `${Number(value || 0).toLocaleString('vi-VN', { maximumFractionDigits: 3 })} kWh`;
  const percent = value => Number.isFinite(value) && value >= 0 && value <= 100
    ? `${value.toLocaleString('vi-VN', { maximumFractionDigits: 20 })}%` : '—';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const localDateTime = value => {
    if (!value) return '—';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('vi-VN');
  };

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
    reportLoaded = false;
    exportMessage.hidden = true;
    exportButton.disabled = true;
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
    if (loading) exportButton.disabled = true;
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

  function renderContracts(data) {
    const partners = data.partners || [];
    const selected = contractPartner.value;
    contractPartner.innerHTML = '<option value="">Chọn đối tác</option>' + partners.map(partner =>
      `<option value="${Number(partner.id)}">${esc(partner.name)} (${esc(partner.email)})</option>`
    ).join('');
    if (partners.some(partner => String(partner.id) === selected)) contractPartner.value = selected;
    const items = data.items || [];
    contractHistory.innerHTML = items.length ? items.map(item => `<tr>
      <td>${esc(item.partner_name)}<br><small>${esc(item.partner_email)}</small></td>
      <td class="text-right">${Number(item.partner_share_percent)}%</td>
      <td class="text-right">${Number(item.platform_share_percent)}%</td>
      <td>${localDateTime(item.effective_from)}</td>
      <td>${localDateTime(item.effective_to)}</td>
    </tr>`).join('') : '<tr><td colspan="5">Chưa có hợp đồng. Tạo hợp đồng để bắt đầu chia doanh thu.</td></tr>';
  }

  async function loadContracts() {
    contractHistory.innerHTML = '<tr><td colspan="5">Đang tải hợp đồng...</td></tr>';
    try {
      renderContracts(await ApiClient.listRevenueShareContracts());
    } catch (error) {
      contractHistory.innerHTML = '<tr><td colspan="5">Không tải được danh sách hợp đồng.</td></tr>';
      contractMessage.textContent = error?.message || 'Không tải được danh sách hợp đồng.';
      contractMessage.className = 'alert alert--danger';
      contractMessage.hidden = false;
    }
  }

  function setPlatformPercent() {
    const partnerPercent = Number(contractPartnerPercent.value);
    contractPlatformPercent.value = Number.isFinite(partnerPercent) && partnerPercent >= 0 && partnerPercent <= 100
      ? (100 - partnerPercent).toFixed(2).replace(/\.00$/, '') : '';
  }

  function renderReport(report) {
    renderPartners(report.partners || []);
    const items = report.items || [];
    document.getElementById('stat-base-revenue').textContent = money(report.totals?.base_revenue_vnd);
    document.getElementById('stat-shared-amount').textContent = money(report.totals?.shared_amount_vnd);

    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">Không có dữ liệu chia doanh thu trong kỳ đã chọn.</td></tr>';
      tfoot.hidden = true;
      notReadyBox.hidden = true;
      return;
    }

    tbody.innerHTML = items.map(item => `<tr>
      <td><strong>${esc(item.partner_name)}</strong><br><small>${esc(item.partner_email)}</small></td>
      <td>${esc(item.policy_label)}</td>
      <td class="text-right">${percent(item.share_percent)}</td>
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
    reportLoaded = false;
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
    exportMessage.hidden = true;
    try {
      const report = await ApiClient.getRevenueShareReport({
        date_from: from,
        date_to: to,
        station_owner_id: partnerInput.value || undefined,
      });
      if (version !== requestVersion) return;
      renderReport(report);
      reportLoaded = true;
      exportButton.disabled = false;
    } catch (error) {
      if (version !== requestVersion) return;
      showError(error?.message || 'Không tải được bảng kê chia doanh thu.');
      reportLoaded = false;
      exportButton.disabled = true;
      tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">Không tải được dữ liệu.</td></tr>';
      tfoot.hidden = true;
    } finally {
      if (version === requestVersion) setLoading(false);
    }
  }

  exportButton?.addEventListener('click', async () => {
    const from = fromInput.value, to = toInput.value;
    if (!from || !to || from > to) return;
    exportButton.disabled = true;
    exportButton.textContent = 'Đang xuất…';
    exportMessage.hidden = false;
    exportMessage.className = 'alert alert--info';
    exportMessage.textContent = 'Đang tạo tệp CSV…';
    try {
      await ApiClient.exportRevenueShareCsv({
        date_from: from,
        date_to: to,
        station_owner_id: partnerInput.value || undefined,
      });
      exportMessage.textContent = 'Đã tải bảng kê CSV.';
    } catch (error) {
      exportMessage.className = 'alert alert--danger';
      exportMessage.textContent = error?.message || 'Không tải được tệp CSV.';
    } finally {
      exportButton.disabled = !reportLoaded;
      exportButton.textContent = 'Tải CSV';
    }
  });

  contractPartnerPercent.addEventListener('input', setPlatformPercent);
  contractForm.addEventListener('submit', async event => {
    event.preventDefault();
    const partnerPercent = Number(contractPartnerPercent.value);
    const platformPercent = Number(contractPlatformPercent.value);
    if (!contractPartner.value || !contractEffectiveFrom.value
      || !Number.isFinite(partnerPercent) || !Number.isFinite(platformPercent)
      || partnerPercent < 0 || platformPercent < 0
      || Math.abs(partnerPercent + platformPercent - 100) > 0.000001) {
      contractMessage.textContent = 'Chọn đối tác, ngày hiệu lực và bảo đảm tổng hai tỉ lệ bằng 100%.';
      contractMessage.className = 'alert alert--danger';
      contractMessage.hidden = false;
      return;
    }
    contractSave.disabled = true;
    contractMessage.hidden = true;
    try {
      await ApiClient.createRevenueShareContract({
        station_owner_id: Number(contractPartner.value),
        partner_share_percent: partnerPercent,
        platform_share_percent: platformPercent,
        effective_from: new Date(contractEffectiveFrom.value).toISOString(),
      });
      contractMessage.textContent = 'Đã tạo phiên bản hợp đồng. Các khoản đã phát sinh vẫn giữ tỉ lệ cũ.';
      contractMessage.className = 'alert alert--success';
      contractMessage.hidden = false;
      await loadContracts();
      await applyFilter();
    } catch (error) {
      contractMessage.textContent = error?.message || 'Không lưu được hợp đồng.';
      contractMessage.className = 'alert alert--danger';
      contractMessage.hidden = false;
    } finally {
      contractSave.disabled = false;
    }
  });

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

  const initialContractTime = new Date();
  initialContractTime.setMinutes(initialContractTime.getMinutes() + 1, 0, 0);
  contractEffectiveFrom.value = `${isoDate(initialContractTime)}T${String(initialContractTime.getHours()).padStart(2, '0')}:${String(initialContractTime.getMinutes()).padStart(2, '0')}`;
  loadContracts();

  setQuickFilter('month');
})();
