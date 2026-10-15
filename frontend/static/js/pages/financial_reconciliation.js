// SCRUM-231 / SCRUM-85 — Hiển thị báo cáo đối soát.
document.addEventListener('DOMContentLoaded', () => {
  'use strict';
  const get = name => document.getElementById(`financial-${name}`);
  const form = get('filter-form');
  const from = get('from');
  const to = get('to');
  const status = get('status');
  const button = get('apply');
  const message = get('message');
  const tbody = get('table-body');
  const reviewList = get('review-list');
  const source = window.FinancialReconciliationData;
  const money = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 0 });
  const energy = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 3 });
  const labels = {
    missing_invoice: 'Có kWh nhưng thiếu hóa đơn',
    missing_ledger: 'Có hóa đơn nhưng thiếu dòng sổ cái',
    amount_mismatch: 'Hóa đơn lệch với tính lại từ biểu giá',
  };
  const fields = {
    'total-kwh': ['total_kwh', energy],
    'total-invoiced': ['total_invoiced_vnd', money],
    'total-collected': ['total_collected_vnd', money],
    'total-difference': ['total_difference_vnd', money],
  };
  let revision = 0;
  const format = (value, formatter) =>
    Number.isFinite(value) ? formatter.format(value) : '—';
  const describe = row => row.issues.map(code => labels[code] || 'Cần xem xét').join('; ');

  function notice(text, type = 'info') {
    message.className = `alert alert--${type}`;
    message.textContent = text;
  }
  function tableMessage(text) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 8;
    cell.textContent = text;
    row.append(cell);
    tbody.replaceChildren(row);
  }
  function clear(text) {
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
  function render(report) {
    const { rows, summary } = report;
    for (const [id, [field, formatter]] of Object.entries(fields)) {
      get(id).textContent = format(summary[field], formatter);
    }
    get('review-count').textContent = format(summary.review_count, money);
    reviewList.replaceChildren();
    const reviewRows = rows.filter(row => row.issues.length > 0);
    const items = reviewRows.length ? reviewRows.map(row =>
      `${row.session_id}: ${describe(row)}`
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
        row.session_id, row.charge_point_code,
        format(row.energy_kwh, energy), format(row.expected_vnd, money),
        format(row.invoiced_vnd, money), format(row.collected_vnd, money),
        format(row.difference_vnd, money),
      ];
      values.forEach((value, index) => {
        const cell = document.createElement('td');
        cell.textContent = value ?? '—';
        if (index >= 2) cell.className = 'text-right';
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
    notice('DỮ LIỆU MẪU — 5 phiên minh họa từ 02–06/10/2026. '
      + 'Các chỉ số theo bộ lọc hiện tại, chỉ cộng khoản đã có dữ liệu. '
      + 'Dấu — là dữ liệu thiếu; tổng lệch mẫu là tổng trị tuyệt đối. '
      + 'Chưa dùng để chốt sổ.', 'warning');
  }
  async function load() {
    const current = ++revision;
    clear('Đang chuẩn bị báo cáo mẫu…');
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
    notice('Đang tải dữ liệu mẫu…');
    try {
      const report = await source.getReport({
        fromDate: from.value, toDate: to.value, status: status.value,
      });
      if (current !== revision) return;
      if (!report.is_sample || !Array.isArray(report.rows) || !report.summary) {
        throw new Error('Dữ liệu mẫu không hợp lệ.');
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
  if (!source) {
    notice('Chưa tải được dữ liệu mẫu. Hãy tải lại trang để thử lại.', 'danger');
    return;
  }
  from.value = source.defaultPeriod.fromDate;
  to.value = source.defaultPeriod.toDate;
  button.disabled = false;
  form.addEventListener('submit', event => {
    event.preventDefault();
    load();
  });
  form.addEventListener('input', () => {
    ++revision;
    from.setCustomValidity('');
    busy(false);
    clear('Bộ lọc đã thay đổi. Bấm Xem báo cáo để cập nhật.');
    notice('Dữ liệu mẫu — chọn Xem báo cáo để áp dụng bộ lọc mới.');
  });
  load();
});
