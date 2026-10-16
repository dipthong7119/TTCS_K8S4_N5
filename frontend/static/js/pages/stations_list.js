/**
 * pages/stations_list.js — JS đặc thù trang danh sách trạm (T-09, SCRUM-105)
 * Giới hạn: ~100 dòng — logic tái sử dụng (API, pagination) ở shared files.
 * Mọi gọi API đi qua ApiClient (api_client.js) — không rải fetch trực tiếp.
 */
(function () {
  'use strict';

  let _stations = [];
  let _page = 1;
  const PAGE_SIZE = 10;
  const canManageStations = document.getElementById('stations-page')?.dataset.canManageStations === 'true';
  const isDriverView = document.getElementById('stations-page')?.dataset.isDriverView === 'true';
  let _bookingOptions = [];
  let _bookingStationId = null;

  // ── Labels & classes trạng thái ──
  const STATUS_LABELS = {
    active:      'Hoạt động',
    inactive:    'Tạm dừng',
    maintenance: 'Bảo trì',
    locked:      'Bị quản trị khóa',
  };
  const STATUS_CLASS = {
    active:      'badge--online',
    inactive:    'badge--offline',
    maintenance: 'badge--warning',
    locked:      'badge--offline',
  };

  // ── Tải danh sách trạm từ API ──
  async function loadStations() {
    const search = document.getElementById('station-search').value.trim();
    const status = document.getElementById('status-filter').value;
    const tbody  = document.getElementById('station-tbody');

    // Hiện loading
    tbody.innerHTML = `
      <tr><td colspan="6" style="text-align:center;padding:40px;color:var(--color-text-muted);">
        <div style="display:flex;align-items:center;justify-content:center;gap:10px;">
          <div class="spinner" aria-hidden="true"></div><span>Đang tải...</span>
        </div>
      </td></tr>`;

    try {
      const params = { page: _page, page_size: PAGE_SIZE };
      if (search) params.search = search;
      if (status) params.status = status;

      const data  = await ApiClient.listStations(params);
      _stations   = data.items || data;
      const total = data.total ?? _stations.length;

      renderTable(_stations);
      renderStats(_stations);
      updateCount(total);
      renderPagination(total);
    } catch (err) {
      tbody.innerHTML = `
        <tr><td colspan="6" style="text-align:center;padding:40px;">
          <div class="empty-state">
            <div class="empty-state__icon">⚠️</div>
            <div class="empty-state__title">Không tải được dữ liệu</div>
            <div class="empty-state__desc">${escHtml(err.message || 'Lỗi kết nối máy chủ')}</div>
          </div>
        </td></tr>`;
      showToast(err.message || 'Không tải được danh sách trạm', 'error');
    }
  }

  // ── Cập nhật thẻ thống kê ──
  function renderStats(stations) {
    const counts = { active: 0, inactive: 0, maintenance: 0 };
    stations.forEach(s => { if (counts[s.status] !== undefined) counts[s.status]++; });
    const values = {
      'stat-total': stations.length,
      'stat-active': counts.active,
      'stat-maintenance': counts.maintenance,
      'stat-inactive': counts.inactive,
    };
    Object.entries(values).forEach(([id, value]) => {
      const element = document.getElementById(id);
      if (element) element.textContent = value;
    });
  }

  // ── Render bảng danh sách ──
  function renderTable(stations) {
    const tbody = document.getElementById('station-tbody');
    if (!stations.length) {
      tbody.innerHTML = `
        <tr><td colspan="6">
          <div class="empty-state">
            <div class="empty-state__icon">🏗️</div>
            <div class="empty-state__title">Chưa có trạm nào</div>
            <div class="empty-state__desc">Bấm <strong>Thêm trạm mới</strong> để bắt đầu</div>
          </div>
        </td></tr>`;
      return;
    }

    tbody.innerHTML = stations.map(s => {
      const statusLabel = STATUS_LABELS[s.status] || 'Không rõ';
      const statusClass = STATUS_CLASS[s.status]  || 'badge--neutral';
      return `
        <tr>
          <td><strong>${escHtml(s.name)}</strong></td>
          <td class="td-address" title="${escHtml(s.address || '')}">${escHtml(s.address || '—')}</td>
          <td>
            <span class="cp-count">
              ${s.charge_point_count ?? '—'}
              <span class="cp-count__sub"> trụ</span>
            </span>
          </td>
          <td>
            <span class="badge ${statusClass}" aria-label="Trạng thái: ${statusLabel}">
              ${statusLabel}
            </span>
          </td>
          <td class="td-date">${fmtDate(s.created_at)}</td>
          <td class="text-right">
            <div class="station-row-actions">
              ${canManageStations ? `
              <a href="/stations/${s.id}/edit"
                 class="btn btn--ghost btn--icon-sm"
                 aria-label="Sửa trạm ${escHtml(s.name)}">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                     stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
              </a>
              <button class="btn btn--ghost btn--icon-sm"
                      data-delete-id="${s.id}"
                      data-delete-name="${escHtml(s.name)}"
                      type="button"
                      aria-label="Xoá trạm ${escHtml(s.name)}">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                     stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <polyline points="3 6 5 6 21 6"/>
                  <path d="M19 6l-1 14H6L5 6"/>
                  <path d="M10 11v6"/><path d="M14 11v6"/>
                  <path d="M9 6V4h6v2"/>
                </svg>
              </button>
              ` : (isDriverView ? `
              <button class="btn btn--primary btn--sm" type="button"
                      data-book-station-id="${s.id}"
                      data-book-station-name="${escHtml(s.name)}">
                Đặt chỗ
              </button>
              ` : '<span aria-label="Chỉ xem">Chỉ xem</span>')}
            </div>
          </td>
        </tr>`;
    }).join('');

    // Gắn event xoá
    tbody.querySelectorAll('[data-delete-id]').forEach(btn => {
      btn.addEventListener('click', () =>
        openDeleteModal(btn.dataset.deleteId, btn.dataset.deleteName));
    });
    tbody.querySelectorAll('[data-book-station-id]').forEach(btn => {
      btn.addEventListener('click', () =>
        openBookingModal(btn.dataset.bookStationId, btn.dataset.bookStationName));
    });
  }

  async function loadMyReservations() {
    const tbody = document.getElementById('reservation-tbody');
    if (!tbody || !isDriverView) return;

    tbody.innerHTML = '<tr><td colspan="5" class="reservation-empty">Đang tải...</td></tr>';
    try {
      const reservations = await ApiClient.listMyReservations();
      if (!reservations.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="reservation-empty">Bạn chưa có lượt đặt chỗ nào.</td></tr>';
        return;
      }

      tbody.innerHTML = reservations.map(item => {
        const state = reservationStatus(item.status);
        const cancelButton = item.status === 'accepted'
          ? `<button class="btn btn--ghost btn--sm" type="button" data-cancel-reservation="${item.id}">Hủy chỗ</button>`
          : '—';
        return `
          <tr>
            <td><strong>${escHtml(item.charge_point_code)}</strong></td>
            <td>${escHtml(item.connector_id)}</td>
            <td>${fmtDateTime(item.expiry_date)}</td>
            <td><span class="badge ${state.className}">${state.label}</span></td>
            <td class="text-right">${cancelButton}</td>
          </tr>`;
      }).join('');

      tbody.querySelectorAll('[data-cancel-reservation]').forEach(btn => {
        btn.addEventListener('click', () => cancelMyReservation(btn));
      });
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="5" class="reservation-empty">${escHtml(err.message || 'Không tải được đặt chỗ')}</td></tr>`;
    }
  }

  function reservationStatus(value) {
    const labels = {
      pending: ['Đang gửi đến trụ', 'badge--warning'],
      accepted: ['Đã xác nhận', 'badge--online'],
      rejected: ['Bị từ chối', 'badge--offline'],
      completed: ['Đã sử dụng', 'badge--neutral'],
      expired: ['Hết hạn', 'badge--offline'],
      cancelled: ['Đã hủy', 'badge--neutral'],
    };
    const [label, className] = labels[value] || ['Không rõ', 'badge--neutral'];
    return { label, className };
  }

  async function cancelMyReservation(button) {
    const reservationId = button.dataset.cancelReservation;
    button.disabled = true;
    button.textContent = 'Đang gửi lệnh hủy...';
    try {
      const result = await ApiClient.cancelReservation(reservationId);
      if (result.cancel_status === 'pending') {
        showToast('Đã hủy đặt chỗ trên hệ thống; đang chờ trụ xác nhận giải phóng đầu nối.', 'warning', 7000);
      } else {
        showToast('Đã hủy đặt chỗ thành công.', 'success');
      }
      await Promise.all([loadMyReservations(), loadStations()]);
    } catch (err) {
      showToast(err.message || 'Không thể hủy đặt chỗ', 'error', 6000);
      button.disabled = false;
      button.textContent = 'Hủy chỗ';
    }
  }

  async function openBookingModal(stationId, stationName) {
    _bookingStationId = stationId;
    const modal = document.getElementById('booking-modal');
    if (!modal) return;
    document.getElementById('booking-station-name').textContent = stationName;
    document.getElementById('booking-error').hidden = true;
    document.getElementById('booking-modal').classList.remove('is-hidden');
    document.getElementById('booking-modal-close').focus();
    await loadBookingOptions();
  }

  async function loadBookingOptions() {
    const pointSelect = document.getElementById('booking-charge-point');
    const connectorSelect = document.getElementById('booking-connector');
    const submit = document.getElementById('booking-submit');
    const help = document.getElementById('booking-options-help');
    pointSelect.disabled = true;
    connectorSelect.disabled = true;
    submit.disabled = true;
    pointSelect.innerHTML = '<option value="">Đang tải trụ...</option>';
    connectorSelect.innerHTML = '<option value="">Chọn trụ trước</option>';
    help.textContent = 'Đang kiểm tra đầu nối đang rảnh...';

    try {
      const result = await ApiClient.getBookingOptions(_bookingStationId);
      _bookingOptions = result.items || [];
      if (!_bookingOptions.length) {
        pointSelect.innerHTML = '<option value="">Không có trụ đang kết nối với đầu nối rảnh</option>';
        connectorSelect.innerHTML = '<option value="">Chưa có đầu nối khả dụng</option>';
        help.textContent = 'Thử làm mới sau khi trụ kết nối và báo trạng thái khả dụng.';
        return;
      }

      pointSelect.innerHTML = _bookingOptions.map((point, index) =>
        `<option value="${index}">${escHtml(point.charge_point_code)}</option>`
      ).join('');
      pointSelect.disabled = false;
      help.textContent = `${_bookingOptions.reduce((sum, point) => sum + point.connectors.length, 0)} đầu nối đang khả dụng.`;
      renderBookingConnectors();
    } catch (err) {
      _bookingOptions = [];
      pointSelect.innerHTML = '<option value="">Không tải được danh sách trụ</option>';
      connectorSelect.innerHTML = '<option value="">Thử lại sau</option>';
      help.textContent = err.message || 'Không thể tải đầu nối của trạm.';
    }
  }

  function renderBookingConnectors() {
    const pointSelect = document.getElementById('booking-charge-point');
    const connectorSelect = document.getElementById('booking-connector');
    const submit = document.getElementById('booking-submit');
    const point = _bookingOptions[Number(pointSelect.value)];
    const connectors = point?.connectors || [];
    connectorSelect.innerHTML = connectors.map(connector => {
      const type = connector.connector_type ? ` · ${escHtml(connector.connector_type)}` : '';
      const power = connector.rated_power_kw ? ` · ${escHtml(connector.rated_power_kw)} kW` : '';
      return `<option value="${connector.connector_id}">Đầu nối ${connector.connector_id}${type}${power}</option>`;
    }).join('') || '<option value="">Không có đầu nối khả dụng</option>';
    connectorSelect.disabled = connectors.length === 0;
    submit.disabled = connectors.length === 0;
  }

  function closeBookingModal() {
    document.getElementById('booking-modal')?.classList.add('is-hidden');
    _bookingStationId = null;
  }

  async function submitBooking(event) {
    event.preventDefault();
    const point = _bookingOptions[Number(document.getElementById('booking-charge-point').value)];
    if (!point) return;

    const submit = document.getElementById('booking-submit');
    const error = document.getElementById('booking-error');
    submit.disabled = true;
    submit.textContent = 'Đang gửi đặt chỗ...';
    error.hidden = true;
    try {
      const result = await ApiClient.createReservation({
        charge_point_code: point.charge_point_code,
        connector_id: Number(document.getElementById('booking-connector').value),
        expiry_minutes: Number(document.getElementById('booking-expiry').value),
      });
      showToast(result.message || 'Đặt chỗ đã được gửi đến trụ.', 'success', 6000);
      closeBookingModal();
      await Promise.all([loadMyReservations(), loadStations()]);
    } catch (err) {
      error.textContent = err.message || 'Không thể đặt chỗ.';
      error.hidden = false;
      showToast(err.message || 'Không thể đặt chỗ.', 'error', 6000);
      await loadBookingOptions();
    } finally {
      submit.textContent = 'Đặt chỗ';
      if (!document.getElementById('booking-modal').classList.contains('is-hidden')) {
        submit.disabled = document.getElementById('booking-connector').disabled;
      }
    }
  }

  // ── Hiện số lượng kết quả ──
  function updateCount(total) {
    document.getElementById('result-count').textContent = `${total} trạm`;
  }

  // ── Phân trang ──
  function renderPagination(total) {
    const pages = Math.ceil(total / PAGE_SIZE);
    const pg    = document.getElementById('pagination');
    pg.innerHTML = '';
    if (pages <= 1) return;

    const prev = makePageBtn('‹', _page === 1, () => { _page--; loadStations(); }, 'Trang trước');
    pg.appendChild(prev);

    const maxShow = 5;
    let start = Math.max(1, _page - Math.floor(maxShow / 2));
    let end   = Math.min(pages, start + maxShow - 1);
    if (end - start + 1 < maxShow) start = Math.max(1, end - maxShow + 1);

    if (start > 1) pg.appendChild(makeEllipsis());
    for (let i = start; i <= end; i++) {
      pg.appendChild(makePageBtn(String(i), false, () => { _page = i; loadStations(); }, `Trang ${i}`, i === _page));
    }
    if (end < pages) pg.appendChild(makeEllipsis());

    const next = makePageBtn('›', _page === pages, () => { _page++; loadStations(); }, 'Trang sau');
    pg.appendChild(next);
  }

  function makePageBtn(text, disabled, onClick, label, active = false) {
    const b = document.createElement('button');
    b.className = 'pagination__btn' + (active ? ' is-active' : '');
    b.textContent = text;
    b.disabled = disabled;
    b.setAttribute('aria-label', label);
    if (active) b.setAttribute('aria-current', 'page');
    b.addEventListener('click', onClick);
    return b;
  }

  function makeEllipsis() {
    const span = document.createElement('span');
    span.className = 'pagination__ellipsis';
    span.textContent = '…';
    span.setAttribute('aria-hidden', 'true');
    return span;
  }

  // ── Modal xoá ──
  let _deleteId = null;

  function openDeleteModal(id, name) {
    _deleteId = id;
    document.getElementById('delete-station-name').textContent = name;
    document.getElementById('delete-modal').classList.remove('is-hidden');
    document.getElementById('delete-confirm').focus();
  }

  function closeDeleteModal() {
    document.getElementById('delete-modal').classList.add('is-hidden');
    _deleteId = null;
  }

  // ── Tiện ích ──
  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleDateString('vi-VN',
        { day: '2-digit', month: '2-digit', year: 'numeric' });
    } catch { return '—'; }
  }

  function fmtDateTime(iso) {
    if (!iso) return '—';
    const date = new Date(iso);
    return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('vi-VN');
  }

  // ── Khởi động ──
  document.addEventListener('DOMContentLoaded', () => {
    loadStations();
    if (isDriverView) loadMyReservations();

    // Tìm kiếm có debounce
    let _debounce;
    document.getElementById('station-search').addEventListener('input', () => {
      clearTimeout(_debounce);
      _debounce = setTimeout(() => { _page = 1; loadStations(); }, 350);
    });

    // Lọc trạng thái
    document.getElementById('status-filter').addEventListener('change', () => {
      _page = 1;
      loadStations();
    });

    // Nút làm mới
    document.getElementById('btn-refresh').addEventListener('click', () => {
      _page = 1;
      loadStations();
    });

    document.getElementById('btn-refresh-reservations')?.addEventListener('click', loadMyReservations);
    document.getElementById('booking-charge-point')?.addEventListener('change', renderBookingConnectors);
    document.getElementById('booking-form')?.addEventListener('submit', submitBooking);
    document.getElementById('booking-modal-close')?.addEventListener('click', closeBookingModal);
    document.getElementById('booking-cancel')?.addEventListener('click', closeBookingModal);
    document.getElementById('booking-modal')?.addEventListener('click', event => {
      if (event.target === event.currentTarget) closeBookingModal();
    });

    // Modal xoá — mở/đóng
    document.getElementById('delete-modal-close').addEventListener('click', closeDeleteModal);
    document.getElementById('delete-cancel').addEventListener('click', closeDeleteModal);
    document.getElementById('delete-modal').addEventListener('click', e => {
      if (e.target === e.currentTarget) closeDeleteModal();
    });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') {
        closeDeleteModal();
        closeBookingModal();
      }
    });

    // Modal xoá — xác nhận
    document.getElementById('delete-confirm').addEventListener('click', async () => {
      if (!_deleteId) return;
      const btn = document.getElementById('delete-confirm');
      btn.disabled = true;
      btn.textContent = 'Đang xoá...';
      try {
        await ApiClient.deleteStation(_deleteId);
        showToast('Đã xoá trạm thành công', 'success');
        closeDeleteModal();
        _page = 1;
        loadStations();
      } catch (err) {
        showToast(err.message || 'Xoá thất bại', 'error');
      } finally {
        btn.disabled = false;
        btn.textContent = 'Xoá trạm';
      }
    });
  });
})();
