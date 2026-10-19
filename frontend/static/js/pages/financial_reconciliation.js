// SCRUM-85 — Đối soát tài chính từ phiên sạc, hóa đơn và sổ cái.
document.addEventListener('DOMContentLoaded', () => {
  'use strict';
  const get = name => document.getElementById(`financial-${name}`);
  const form = get('filter-form');
  const from = get('from');
  const to = get('to');
  const status = get('status');
  const station = get('station');
  const chargePoint = get('charge-point');
  const button = get('apply');
  const lockButton = get('lock');
  const exportButton = get('export');
  const exportMessage = get('export-message');
  const reopenButton = get('reopen');
  const reopenModal = get('reopen-modal');
  const reopenReason = get('reopen-reason');
  const reopenConfirm = get('reopen-confirm');
  const reopenCancel = get('reopen-cancel');
  const reopenClose = get('reopen-close');
  const message = get('message');
  const periodState = get('period-state');
  const tbody = get('table-body');
  const reviewList = get('review-list');
  const money = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 0 });
  const energy = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 3 });
  const labels = {
    missing_invoice: 'Có kWh nhưng thiếu hóa đơn',
    missing_ledger: 'Có hóa đơn nhưng thiếu dòng sổ cái',
    amount_mismatch: 'Hóa đơn lệch với tính lại theo biểu giá',
    collection_mismatch: 'Tiền thu lệch hóa đơn',
    missing_pricing: 'Thiếu dữ liệu biểu giá để tính lại',
  };
  const fields = {
    'total-kwh': ['total_kwh', energy],
    'total-expected': ['total_expected_vnd', money],
    'total-invoiced': ['total_invoiced_vnd', money],
    'total-collected': ['total_collected_vnd', money],
    'total-difference': ['total_difference_vnd', money],
    'total-invoice-difference': ['total_invoice_difference_vnd', money],
  };
  let revision = 0;
  let lastReport = null;
  let filterOptions = { stations: [], charge_points: [] };
  const format = (value, formatter) =>
    Number.isFinite(Number(value)) && value !== null ? formatter.format(Number(value)) : '—';
  const describe = row => (row.issues || []).map(code => labels[code] || 'Cần xem xét').join('; ');

  function notice(text, type = 'info') {
    message.className = `alert alert--${type}`;
    message.textContent = text;
  }
  function tableMessage(text) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 11;
    cell.textContent = text;
    row.append(cell);
    tbody.replaceChildren(row);
  }
  function clear(text) {
    lastReport = null;
    exportButton.disabled = true;
    exportMessage.hidden = true;
    lockButton.disabled = true;
    lockButton.textContent = 'Chốt kỳ';
    if (reopenButton) {
      reopenButton.hidden = true;
      reopenButton.disabled = true;
    }
    periodState.textContent = 'Trạng thái kỳ chưa được tải.';
    Object.keys(fields).forEach(id => { get(id).textContent = '—'; });
    get('review-count').textContent = '—';
    const item = document.createElement('li');
    item.textContent = text;
    reviewList.replaceChildren(item);
    get('row-count').textContent = 'Chưa có báo cáo';
    tableMessage(text);
  }
  function busy(value) {
    button.disabled = value;
    button.textContent = value ? 'Đang tải…' : 'Xem báo cáo';
    tbody.setAttribute('aria-busy', String(value));
  }
  function fillOptions(select, values, valueOf, labelOf, placeholder) {
    const selected = select.value;
    select.replaceChildren();
    const all = document.createElement('option');
    all.value = '';
    all.textContent = placeholder;
    select.append(all);
    values.forEach(item => {
      const option = document.createElement('option');
      option.value = valueOf(item);
      option.textContent = labelOf(item);
      select.append(option);
    });
    select.value = values.some(item => String(valueOf(item)) === selected) ? selected : '';
  }
  function updateFilters(options) {
    filterOptions = options || filterOptions;
    fillOptions(
      station,
      filterOptions.stations || [],
      item => item.id,
      item => item.name,
      'Tất cả trạm',
    );
    const points = (filterOptions.charge_points || []).filter(item =>
      !station.value || String(item.station_id) === station.value
    );
    fillOptions(chargePoint, points, item => item.code, item => item.code, 'Tất cả trụ');
  }
  function render(report) {
    const { rows, summary } = report;
    lastReport = report;
    exportButton.disabled = false;
    updateFilters(report.filters);
    for (const [id, [field, formatter]] of Object.entries(fields)) {
      get(id).textContent = format(summary[field], formatter);
    }
    get('review-count').textContent = format(summary.review_count, money);
    reviewList.replaceChildren();
    const reviewRows = rows.filter(row => row.issues.length > 0);
    const items = reviewRows.length ? reviewRows.map(row =>
      `Phiên ${row.session_id} — ${row.station_name}: ${describe(row)}`
    ) : ['Không có phiên cần xem xét trong bộ lọc hiện tại.'];
    items.forEach(text => {
      const item = document.createElement('li');
      item.textContent = text;
      reviewList.append(item);
    });
    tbody.replaceChildren();
    rows.forEach(row => {
      const tr = document.createElement('tr');
      const values = [
        row.session_id, row.date, row.station_name, row.charge_point_code,
        format(row.energy_kwh, energy), format(row.expected_vnd, money),
        format(row.invoiced_vnd, money), format(row.collected_vnd, money),
        format(row.difference_vnd, money), format(row.invoice_difference_vnd, money),
      ];
      values.forEach((value, index) => {
        const cell = document.createElement('td');
        cell.textContent = value ?? '—';
        if (index >= 4) cell.className = 'text-right';
        tr.append(cell);
      });
      const cell = document.createElement('td');
      const badge = document.createElement('span');
      badge.className = `badge badge--${row.issues.length ? 'warning' : 'online'}`;
      badge.textContent = describe(row) || 'Khớp';
      cell.append(badge);
      tr.append(cell);
      tbody.append(tr);
    });
    if (!rows.length) tableMessage('Không có phiên trong bộ lọc đã chọn.');
    get('row-count').textContent = `${rows.length} phiên theo bộ lọc hiện tại`;
    updatePeriodControls(report);
    notice('Số liệu được tổng hợp từ phiên sạc, hóa đơn đã chốt và sổ cái ví.');
  }
  function updatePeriodControls(report) {
    if (report.period_state === 'locked') {
      const lockedAt = report.locked_at
        ? new Date(report.locked_at).toLocaleString('vi-VN') : '';
      periodState.textContent = `Đã khóa${lockedAt ? ` lúc ${lockedAt}` : ''}. Báo cáo đang dùng ảnh chụp đã chốt.`;
      lockButton.textContent = 'Kỳ đã khóa';
      lockButton.disabled = true;
      if (reopenButton) {
        reopenButton.hidden = false;
        reopenButton.disabled = false;
      }
      return;
    }
    if (reopenButton) {
      reopenButton.hidden = true;
      reopenButton.disabled = true;
    }
    periodState.textContent = 'Kỳ đang mở.';
    const endedPeriod = report.period?.to_date < todayInStationZone();
    const canLock = Boolean(station.value)
      && status.value === 'all'
      && endedPeriod
      && report.summary.review_count === 0;
    lockButton.disabled = !canLock;
    lockButton.textContent = 'Chốt kỳ';
    if (!canLock) {
      const reason = report.summary.review_count
        ? ' Hãy xử lý các phiên cần xem xét.'
        : !station.value ? ' Hãy chọn một trạm.'
          : status.value !== 'all' ? ' Chọn Tất cả phiên để chốt.'
            : !endedPeriod ? ' Chỉ chốt kỳ đã kết thúc.' : '';
      periodState.textContent += reason;
    }
  }
  async function load() {
    const current = ++revision;
    clear('Đang tải dữ liệu đối soát…');
    from.setCustomValidity('');
    if (!form.reportValidity()) return;
    if (from.value > to.value) {
      from.setCustomValidity('Từ ngày phải nhỏ hơn hoặc bằng Đến ngày.');
      notice('Khoảng ngày không hợp lệ. Hãy kiểm tra lại.', 'danger');
      clear('Khoảng ngày không hợp lệ.');
      from.reportValidity();
      return;
    }
    busy(true);
    notice('Đang tải số liệu thật từ máy chủ…');
    try {
      const report = await window.ApiClient.getFinancialReconciliation({
        from_date: from.value,
        to_date: to.value,
        station_id: station.value,
        charge_point_code: chargePoint.value,
        status: status.value,
      });
      if (current !== revision) return;
      if (!Array.isArray(report.rows) || !report.summary || !report.filters) {
        throw new Error('Dữ liệu đối soát không đúng định dạng.');
      }
      render(report);
    } catch (error) {
      if (current !== revision) return;
      clear('Không tải được báo cáo.');
      notice(error.message || 'Không tải được dữ liệu. Hãy thử lại.', 'danger');
      get('row-count').textContent = 'Bấm Xem báo cáo để thử lại';
    } finally {
      if (current === revision) busy(false);
    }
  }
  function todayInStationZone() {
    const parts = new Intl.DateTimeFormat('en', {
      timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit',
    }).formatToParts(new Date());
    const part = type => parts.find(item => item.type === type).value;
    return `${part('year')}-${part('month')}-${part('day')}`;
  }

  const today = todayInStationZone();
  from.value = `${today.slice(0, 7)}-01`;
  to.value = today;
  form.addEventListener('submit', event => {
    event.preventDefault();
    load();
  });
  exportButton.addEventListener('click', async () => {
    if (!lastReport || exportButton.disabled) return;
    exportButton.disabled = true;
    exportButton.textContent = 'Đang xuất…';
    exportMessage.hidden = false;
    exportMessage.textContent = 'Đang tạo tệp CSV…';
    exportMessage.className = 'alert alert--info';
    try {
      await window.ApiClient.exportFinancialReconciliationCsv({
        from_date: from.value,
        to_date: to.value,
        station_id: station.value,
        charge_point_code: chargePoint.value,
        status: status.value,
      });
      exportMessage.textContent = 'Đã tải báo cáo CSV.';
    } catch (error) {
      exportMessage.textContent = error.message || 'Không tải được tệp CSV.';
      exportMessage.className = 'alert alert--danger';
    } finally {
      exportButton.disabled = !lastReport;
      exportButton.textContent = 'Tải CSV';
    }
  });
  lockButton.addEventListener('click', async () => {
    if (!lastReport || lockButton.disabled || !station.value) return;
    if (status.value !== 'all') {
      notice('Chọn Tất cả phiên trước khi chốt kỳ.', 'danger');
      return;
    }
    if (!window.confirm('Chốt kỳ này? Sau khi chốt, báo cáo trở thành ảnh chụp chỉ đọc.')) return;
    lockButton.disabled = true;
    lockButton.textContent = 'Đang chốt…';
    try {
      const report = await window.ApiClient.lockFinancialReconciliationPeriod({
        station_id: Number(station.value),
        from_date: from.value,
        to_date: to.value,
      });
      render(report);
      notice('Kỳ đối soát đã được chốt.', 'info');
    } catch (error) {
      notice(error.message || 'Không chốt được kỳ đối soát.', 'danger');
      if (lastReport) updatePeriodControls(lastReport);
    }
  });
  function closeReopenModal() {
    reopenModal?.classList.add('is-hidden');
  }
  function reopenErrorMessage(error) {
    if (error.status === 403) return 'Chỉ quản trị viên mới được mở lại kỳ đối soát.';
    if (error.status === 400) return error.message || 'Kỳ này chưa chốt hoặc đã được mở lại.';
    if (error.status === 404) return 'Không tìm thấy kỳ đối soát đã chốt.';
    if (!error.status) return 'Không kết nối được máy chủ. Hãy thử lại.';
    return error.message || 'Không mở lại được kỳ đối soát.';
  }
  reopenButton?.addEventListener('click', () => {
    if (!lastReport || lastReport.period_state !== 'locked' || reopenButton.disabled) return;
    if (reopenReason) reopenReason.value = '';
    reopenModal?.classList.remove('is-hidden');
    reopenReason?.focus();
  });
  reopenCancel?.addEventListener('click', closeReopenModal);
  reopenClose?.addEventListener('click', closeReopenModal);
  reopenModal?.addEventListener('click', event => {
    if (event.target === event.currentTarget) closeReopenModal();
  });
  reopenConfirm?.addEventListener('click', async () => {
    if (!lastReport || lastReport.period_state !== 'locked' || !station.value) return;
    const payload = {
      station_id: Number(station.value),
      from_date: from.value,
      to_date: to.value,
      status: status.value,
    };
    if (chargePoint.value) payload.charge_point_code = chargePoint.value;
    const reason = reopenReason?.value.trim();
    if (reason) payload.reason = reason;
    reopenConfirm.disabled = true;
    reopenConfirm.textContent = 'Đang mở lại…';
    reopenCancel.disabled = true;
    if (reopenClose) reopenClose.disabled = true;
    if (reopenButton) reopenButton.disabled = true;
    try {
      const report = await window.ApiClient.reopenFinancialReconciliationPeriod(payload);
      closeReopenModal();
      render(report);
      notice('Kỳ đối soát đã được mở lại. Báo cáo đang dùng dữ liệu hiện tại.', 'info');
    } catch (error) {
      notice(reopenErrorMessage(error), 'danger');
      if (lastReport) updatePeriodControls(lastReport);
    } finally {
      reopenConfirm.disabled = false;
      reopenConfirm.textContent = 'Xác nhận mở lại';
      reopenCancel.disabled = false;
      if (reopenClose) reopenClose.disabled = false;
    }
  });
  station.addEventListener('change', () => updateFilters(filterOptions));
  form.addEventListener('input', () => {
    ++revision;
    from.setCustomValidity('');
    busy(false);
    clear('Bộ lọc đã thay đổi. Bấm Xem báo cáo để cập nhật.');
    notice('Chọn Xem báo cáo để áp dụng bộ lọc mới.');
  });
  load();
});
