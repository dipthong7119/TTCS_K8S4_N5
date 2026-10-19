(function () {
  'use strict';
  const stationSel = document.getElementById('rev-station'),
    startInput = document.getElementById('rev-start'),
    endInput = document.getElementById('rev-end'),
    errBox = document.getElementById('rev-err'),
    loadBox = document.getElementById('rev-load'),
    emptyBox = document.getElementById('rev-empty'),
    reportBox = document.getElementById('rev-report'),
    tableBody = document.getElementById('rev-tbody'),
    tableFoot = document.getElementById('rev-tfoot'),
    exportButton = document.getElementById('btn-export-csv'),
    exportMessage = document.getElementById('rev-export-message');

  let _reqId = 0, _ac = null;
  const esc = s => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const fmtVnd = n => new Intl.NumberFormat('vi-VN').format(Math.round(n || 0)) + ' đ';
  const fmtKwh = n => new Intl.NumberFormat('vi-VN', { minimumFractionDigits: 1, maximumFractionDigits: 3 }).format(n || 0) + ' kWh';
  const fmtNum = n => new Intl.NumberFormat('vi-VN').format(n || 0);
  const toIso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

  function clearViews() {
    _reqId++;
    if (_ac) { _ac.abort(); _ac = null; }
    if (reportBox) reportBox.hidden = true;
    if (exportButton) exportButton.disabled = true;
    if (exportMessage) {
      exportMessage.textContent = '';
      exportMessage.className = 'alert alert--info';
      exportMessage.hidden = true;
    }
    if (loadBox) loadBox.hidden = true;
    if (emptyBox) emptyBox.hidden = true;
    if (errBox) { errBox.textContent = ''; errBox.classList.remove('is-visible'); }
  }

  function showErr(msg) {
    clearViews();
    errBox.textContent = msg;
    errBox.classList.add('is-visible');
  }

  function setDates(start, end) {
    startInput.value = toIso(start);
    endInput.value = toIso(end);
    loadRevenue();
  }

  function setQuickFilter(type) {
    const now = new Date();
    if (type === 'today') setDates(now, now);
    else if (type === 'week') {
      const day = now.getDay();
      const mon = new Date(now.getFullYear(), now.getMonth(), now.getDate() + (day === 0 ? -6 : 1 - day));
      setDates(mon, new Date(mon.getFullYear(), mon.getMonth(), mon.getDate() + 6));
    } else if (type === 'month') {
      setDates(new Date(now.getFullYear(), now.getMonth(), 1), new Date(now.getFullYear(), now.getMonth() + 1, 0));
    }
  }

  async function loadRevenue() {
    const stId = stationSel?.value;
    const start = startInput?.value, end = endInput?.value;
    clearViews();
    if (!stId) { if (emptyBox) emptyBox.hidden = false; return; }
    if (!start || !end) return showErr('Vui lòng chọn đầy đủ ngày bắt đầu và kết thúc.');
    if (start > end) return showErr('Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.');

    loadBox.hidden = false;
    _ac = new AbortController();
    const curId = _reqId;
    try {
      const data = await ApiClient.getStationRevenue(stId, { start_date: start, end_date: end }, { signal: _ac.signal });
      if (curId !== _reqId) return;
      loadBox.hidden = true;
      if (!data || (!data.session_count && (!data.charge_points || !data.charge_points.length))) {
        emptyBox.hidden = false;
        return;
      }
      render(data);
    } catch (err) {
      if (err.name === 'AbortError' || curId !== _reqId) return;
      loadBox.hidden = true;
      showErr(err.detail || err.message || 'Lỗi khi tải báo cáo doanh thu.');
    }
  }

  function render(d) {
    document.getElementById('stat-rev').textContent = fmtVnd(d.revenue_vnd);
    document.getElementById('stat-kwh').textContent = fmtKwh(d.total_kwh);
    document.getElementById('stat-sessions').textContent = fmtNum(d.session_count);
    document.getElementById('stat-occ').textContent = fmtVnd(d.occupancy_fee_vnd);
    document.getElementById('rev-period-badge').textContent = `${d.start_date} → ${d.end_date} (${d.timezone || 'Asia/Ho_Chi_Minh'})`;
    const cps = d.charge_points || [];
    tableBody.innerHTML = cps.length ? cps.map(cp => `<tr>
      <td><strong>${esc(cp.charge_point_code)}</strong></td><td class="text-right">${fmtNum(cp.session_count)}</td>
      <td class="text-right">${fmtKwh(cp.total_kwh)}</td><td class="text-right">${fmtVnd(cp.occupancy_fee_vnd)}</td>
      <td class="text-right"><strong>${fmtVnd(cp.revenue_vnd)}</strong></td></tr>`).join('') :
      '<tr><td colspan="5" class="text-center py-4">Không có dữ liệu trụ sạc trong kỳ này</td></tr>';
    tableFoot.innerHTML = `<tr><th>Tổng cộng</th><th class="text-right">${fmtNum(d.session_count)}</th>
      <th class="text-right">${fmtKwh(d.total_kwh)}</th><th class="text-right">${fmtVnd(d.occupancy_fee_vnd)}</th>
      <th class="text-right">${fmtVnd(d.revenue_vnd)}</th></tr>`;
    reportBox.hidden = false;
    if (exportButton) exportButton.disabled = false;
  }

  exportButton?.addEventListener('click', async () => {
    const stationId = stationSel?.value;
    const start = startInput?.value, end = endInput?.value;
    if (!stationId || !start || !end || start > end) return;
    exportButton.disabled = true;
    exportButton.textContent = 'Đang xuất…';
    exportMessage.hidden = false;
    exportMessage.textContent = '';
    exportMessage.className = 'alert alert--info';
    try {
      await ApiClient.exportStationRevenueCsv(stationId, { start_date: start, end_date: end });
      exportMessage.textContent = 'Đã tải báo cáo CSV.';
    } catch (error) {
      exportMessage.textContent = error?.message || 'Không tải được tệp CSV.';
      exportMessage.className = 'alert alert--danger';
    } finally {
      exportButton.disabled = !reportBox || reportBox.hidden;
      exportButton.textContent = 'Tải CSV';
    }
  });

  ['btn-quick-today:today', 'btn-quick-week:week', 'btn-quick-month:month'].forEach(item => {
    const [id, type] = item.split(':');
    document.getElementById(id)?.addEventListener('click', () => setQuickFilter(type));
  });
  document.getElementById('btn-apply-filter')?.addEventListener('click', loadRevenue);
  stationSel?.addEventListener('change', () => { clearViews(); loadRevenue(); });
  startInput?.addEventListener('input', clearViews);
  endInput?.addEventListener('input', clearViews);
  if (stationSel?.value) setQuickFilter('month');
  else if (emptyBox) emptyBox.hidden = false;
})();
