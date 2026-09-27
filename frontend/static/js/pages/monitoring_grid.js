/** Realtime station, charge point, and connector monitoring (T-24, T-25, T-35). */
(function () {
  'use strict';

  let stations = [];
  const canReset = document.getElementById('monitoring-grid')?.dataset.canReset === 'true';
  const STATUS = {
    online: ['Trực tuyến', 'badge--online'],
    offline: ['Ngoại tuyến', 'badge--offline'],
    'rảnh': ['Sẵn sàng', 'badge--available'],
    'bận': ['Đang bận', 'badge--charging'],
    'đặt chỗ': ['Đã đặt chỗ', 'badge--warning'],
    'lỗi': ['Lỗi', 'badge--fault'],
    unavailable: ['Không khả dụng', 'badge--offline'],
    unknown: ['Chưa rõ', 'badge--neutral'],
    active: ['Đang hoạt động', 'badge--online'],
    inactive: ['Tạm ngừng', 'badge--offline'],
    locked: ['Bị khóa', 'badge--offline'],
    maintenance: ['Bảo trì', 'badge--warning'],
    Available: ['Sẵn sàng', 'badge--available'],
    Preparing: ['Đang chuẩn bị', 'badge--charging'],
    Charging: ['Đang sạc', 'badge--charging'],
    SuspendedEV: ['Tạm dừng', 'badge--warning'],
    SuspendedEVSE: ['Trụ tạm dừng', 'badge--warning'],
    Finishing: ['Đang kết thúc', 'badge--finishing'],
    Reserved: ['Đã đặt chỗ', 'badge--warning'],
    Unavailable: ['Không khả dụng', 'badge--fault'],
    Faulted: ['Báo lỗi', 'badge--fault'],
  };

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[char]);
  }

  function statusBadge(status) {
    const [label, style] = STATUS[status] || STATUS.unknown;
    return `<span class="badge ${style}">${label}</span>`;
  }

  function internalStatus(ocppStatus) {
    if (ocppStatus === 'Available') return 'rảnh';
    if (['Preparing', 'Charging', 'SuspendedEV', 'SuspendedEVSE', 'Finishing'].includes(ocppStatus)) return 'bận';
    if (ocppStatus === 'Reserved') return 'đặt chỗ';
    if (['Unavailable', 'Faulted'].includes(ocppStatus)) return 'lỗi';
    return 'unknown';
  }

  async function loadData() {
    try {
      const result = await ApiClient.getMonitoringTree();
      stations = Array.isArray(result) ? result : (result.stations || []);
      render();
      document.getElementById('mon-loading')?.remove();
    } catch (error) {
      showToast(error.message || 'Không tải được dữ liệu giám sát', 'error');
    }
  }

  function matchesStatus(station, wanted) {
    if (!wanted) return true;
    return (station.charge_points || []).some(point =>
      point.status === wanted || internalStatus(point.ocpp_status) === wanted ||
      (point.connectors || []).some(connector => connector.status === wanted)
    );
  }

  function filteredStations() {
    const search = (document.getElementById('mon-search')?.value || '').trim().toLocaleLowerCase('vi');
    const status = document.getElementById('mon-status-filter')?.value || '';
    return stations.filter(station => {
      const searchText = [station.name, station.address, ...(station.charge_points || []).map(point => point.code)]
        .filter(Boolean).join(' ').toLocaleLowerCase('vi');
      return (!search || searchText.includes(search)) && matchesStatus(station, status);
    });
  }

  function connectorMarkup(connector) {
    return `<div class="connector-status" aria-label="Đầu nối ${escapeHtml(connector.connector_id)}: ${escapeHtml(STATUS[connector.status]?.[0] || STATUS.unknown[0])}">
      <span class="connector-status__number">Đầu ${escapeHtml(connector.connector_id)}</span>
      ${statusBadge(connector.status)}
    </div>`;
  }

  function chargePointMarkup(point) {
    const displayedStatus = point.status === 'offline' ? 'offline' : (point.ocpp_status || point.status);
    const connectorMarkupList = (point.connectors || []).map(connectorMarkup).join('');
    const lastSeen = point.status === 'offline' && point.last_seen_at
      ? `<p class="cp-tile__last-seen">Liên lạc lần cuối: ${escapeHtml(new Date(point.last_seen_at).toLocaleString('vi-VN'))}</p>`
      : '';
    return `<section class="cp-tile" aria-label="Trụ ${escapeHtml(point.code)}">
      <div class="cp-tile__header">
        <strong class="cp-tile__code">${escapeHtml(point.code)}</strong>${statusBadge(displayedStatus)}
      </div>
      ${lastSeen}
      <div class="connector-list">${connectorMarkupList || '<span class="muted-text">Chưa khai báo đầu nối</span>'}</div>
    </section>`;
  }

  function stationStatus(station) {
    const points = station.charge_points || [];
    if (!points.length) return station.status || 'unknown';
    if (points.every(point => point.status === 'offline')) return 'offline';
    if (points.some(point => internalStatus(point.ocpp_status) === 'lỗi' || (point.connectors || []).some(connector => connector.status === 'lỗi'))) return 'lỗi';
    return 'online';
  }

  function render() {
    const grid = document.getElementById('monitoring-grid');
    if (!grid) return;
    const loading = document.getElementById('mon-loading');
    Array.from(grid.children).forEach(child => { if (child !== loading) child.remove(); });
    const result = filteredStations();
    if (!result.length) {
      const empty = document.createElement('div');
      empty.className = 'empty-state monitoring-empty';
      empty.innerHTML = '<div class="empty-state__title">Không có kết quả</div><div class="empty-state__desc">Thử thay đổi bộ lọc</div>';
      grid.appendChild(empty);
    } else {
      result.forEach(station => {
        const card = document.createElement('article');
        card.className = 'station-card';
        card.dataset.stationId = station.id;
        card.innerHTML = `<button class="station-card__open" type="button" aria-label="Xem chi tiết trạm ${escapeHtml(station.name)}">
          <span class="station-card__heading"><span><strong class="station-card__name">${escapeHtml(station.name)}</strong>
          <span class="station-card__addr">${escapeHtml(station.address || '')}</span></span>${statusBadge(stationStatus(station))}</span>
        </button><div class="station-card__body"><div class="cp-grid">
          ${(station.charge_points || []).map(chargePointMarkup).join('') || '<p class="muted-text">Trạm chưa có trụ sạc.</p>'}
        </div></div>`;
        card.querySelector('.station-card__open').addEventListener('click', () => openDetail(station));
        grid.appendChild(card);
      });
    }
    updateStats();
  }

  function updateStats() {
    const points = stations.flatMap(station => station.charge_points || []);
    const connectors = points.flatMap(point => point.connectors || []);
    document.getElementById('mon-total').textContent = points.length;
    document.getElementById('mon-charging').textContent = connectors.filter(connector => connector.status === 'bận').length;
    document.getElementById('mon-offline').textContent = points.filter(point => point.status === 'offline').length;
    document.getElementById('mon-fault').textContent =
      connectors.filter(connector => connector.status === 'lỗi').length +
      points.filter(point => internalStatus(point.ocpp_status) === 'lỗi').length;
  }

  function openDetail(station) {
    const backdrop = document.getElementById('detail-backdrop');
    const body = document.getElementById('detail-body');
    document.getElementById('detail-title').textContent = station.name;
    body.innerHTML = `<p class="detail-address">${escapeHtml(station.address || '')}</p>
      <div class="detail-points">${(station.charge_points || []).map(point => {
        const offline = point.status === 'offline';
        const lastSeen = point.last_seen_at
          ? `<p class="cp-tile__last-seen">Liên lạc lần cuối: ${escapeHtml(new Date(point.last_seen_at).toLocaleString('vi-VN'))}</p>` : '';
        const reset = canReset ? `<div class="reset-controls">
          <label for="reset-type-${point.id}">Kiểu khởi động lại</label>
          <select id="reset-type-${point.id}" class="form-select" aria-label="Kiểu khởi động lại trụ ${escapeHtml(point.code)}">
            <option value="Soft">Mềm</option><option value="Hard">Cứng</option>
          </select>
          <button class="btn btn--secondary btn--sm" type="button" data-reset-code="${escapeHtml(point.code)}" ${offline ? 'disabled' : ''}>
            Khởi động lại
          </button></div>` : '';
        return `<section class="detail-point"><div class="detail-point__heading"><strong>${escapeHtml(point.code)}</strong>${statusBadge(point.status)}</div>
          <p class="detail-point__meta">${point.vendor ? `Nhà sản xuất: ${escapeHtml(point.vendor)}` : ''}${point.model ? ` · Model: ${escapeHtml(point.model)}` : ''}</p>
          ${lastSeen}<div class="connector-list">${(point.connectors || []).map(connectorMarkup).join('') || '<span class="muted-text">Chưa khai báo đầu nối</span>'}</div>${reset}</section>`;
      }).join('') || '<p class="muted-text">Trạm chưa có trụ sạc.</p>'}</div>`;
    body.querySelectorAll('[data-reset-code]').forEach(button => {
      button.addEventListener('click', () => resetPoint(button, station));
    });
    backdrop.classList.remove('is-hidden');
    document.getElementById('detail-close').focus();
  }

  async function resetPoint(button, station) {
    const code = button.dataset.resetCode;
    const point = (station.charge_points || []).find(item => item.code === code);
    const select = document.getElementById(`reset-type-${point?.id}`);
    button.disabled = true;
    button.textContent = 'Đang gửi lệnh…';
    try {
      const result = await ApiClient.resetChargePoint(code, select.value);
      showToast(result.message || 'Trụ đã chấp nhận lệnh Reset', 'success');
      window.setTimeout(loadData, 1000);
    } catch (error) {
      showToast(error.message || 'Không gửi được lệnh Reset', 'error');
      button.disabled = false;
      button.textContent = 'Khởi động lại';
    }
  }

  function connectSSE() {
    const indicator = document.getElementById('sse-indicator');
    const label = document.getElementById('sse-label');
    SseClient.on('_connected', () => {
      indicator.className = 'sse-indicator connected';
      label.textContent = 'Đang theo dõi';
      loadData(); // Refresh authoritative state after the initial connection or reconnect.
    });
    SseClient.on('_error', () => {
      indicator.className = 'sse-indicator error';
      label.textContent = 'Đang kết nối lại';
    });
    SseClient.on('status_update', payload => {
      const station = stations.find(item => item.id === payload.station_id);
      if (station && payload.charge_points) station.charge_points = payload.charge_points;
      render();
    });
    SseClient.connect('/api/monitoring/sse');
  }

  document.addEventListener('DOMContentLoaded', () => {
    loadData();
    connectSSE();
    let debounce;
    document.getElementById('mon-search')?.addEventListener('input', () => {
      clearTimeout(debounce);
      debounce = setTimeout(render, 200);
    });
    document.getElementById('mon-status-filter')?.addEventListener('change', render);
    document.getElementById('btn-refresh-monitoring')?.addEventListener('click', loadData);
    document.getElementById('view-grid')?.addEventListener('click', () => setView('grid'));
    document.getElementById('view-list')?.addEventListener('click', () => setView('list'));
    document.getElementById('detail-close')?.addEventListener('click', closeDetail);
    document.getElementById('detail-backdrop')?.addEventListener('click', event => {
      if (event.target === event.currentTarget) closeDetail();
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') closeDetail();
    });
  });

  function setView(mode) {
    const grid = document.getElementById('monitoring-grid');
    grid.classList.toggle('list-view', mode === 'list');
    ['grid', 'list'].forEach(view => {
      const button = document.getElementById(`view-${view}`);
      button.classList.toggle('is-active', view === mode);
      button.setAttribute('aria-pressed', String(view === mode));
    });
  }

  function closeDetail() {
    const backdrop = document.getElementById('detail-backdrop');
    if (backdrop && !backdrop.classList.contains('is-hidden')) {
      backdrop.classList.add('is-hidden');
    }
  }
})();
