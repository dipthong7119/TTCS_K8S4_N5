/** Realtime station, charge point, and connector monitoring (T-24, T-25, T-35, SCRUM-134). */
(function () {
  'use strict';

  const startRequests = new Map();
  let stations = [];
  let isSseConnected = false;
  let loadRequestId = 0;
  let loadError = '';
  let activeDetailStationId = null;
  const canReset = document.getElementById('monitoring-grid')?.dataset.canReset === 'true';

  const STATUS = {
    online: ['Trực tuyến', 'badge--online'],
    offline: ['Ngoại tuyến', 'badge--offline'],
    'rảnh': ['Sẵn sàng', 'badge--available'],
    'bận': ['Đang bận', 'badge--charging'],
    'đặt chỗ': ['Đã đặt chỗ', 'badge--warning'],
    'lỗi': ['Báo lỗi', 'badge--fault'],
    unavailable: ['Tạm ngừng', 'badge--offline'],
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
    Unavailable: ['Tạm ngừng', 'badge--offline'],
    Faulted: ['Báo lỗi', 'badge--fault'],
  };
  const OCPP_STATUS = {
    Available: 'rảnh', Preparing: 'bận', Charging: 'bận', SuspendedEV: 'bận',
    SuspendedEVSE: 'bận', Finishing: 'bận', Reserved: 'đặt chỗ',
    Unavailable: 'unavailable', Faulted: 'lỗi',
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

  function formatLastSeen(timestamp) {
    // Timestamps without an offset from the DB represent UTC.
    const value = /(?:Z|[+-]\d{2}:\d{2})$/i.test(timestamp) ? timestamp : `${timestamp}Z`;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 'Không rõ' : date.toLocaleString('vi-VN');
  }

  function operationalStatus(item) {
    // The API groups Unavailable and Faulted under "lỗi". Keep them distinct
    // on the monitoring page using the original OCPP status.
    if (item.ocpp_status) return OCPP_STATUS[item.ocpp_status] || 'unknown';
    return STATUS[item.status] ? item.status : 'unknown';
  }

  function hasFault(item) {
    return operationalStatus(item) === 'lỗi' ||
      Boolean(item.error_code && item.error_code !== 'NoError');
  }

  function pointHasFault(point) {
    return hasFault(point) || (point.connectors || []).some(hasFault);
  }

  function pointDisplayStatus(point) {
    if (point.status === 'offline') return 'offline';
    if (pointHasFault(point)) return 'Faulted';
    return point.ocpp_status || point.status;
  }

  function updateRealtimeIndicator() {
    const indicator = document.getElementById('sse-indicator');
    const label = document.getElementById('sse-label');
    if (indicator) indicator.className = `sse-indicator ${isSseConnected ? 'connected' : 'error'}`;
    if (label) label.textContent = isSseConnected ? 'Đang theo dõi' : 'Đang kết nối lại';
  }

  async function loadData() {
    const requestId = ++loadRequestId;
    try {
      const result = await ApiClient.getMonitoringTree();
      if (requestId !== loadRequestId) return;
      stations = Array.isArray(result) ? result : (result?.stations || []);
      loadError = '';
      render();
      document.getElementById('mon-loading')?.remove();
    } catch (error) {
      if (requestId !== loadRequestId) return;
      loadError = 'Không tải được trạng thái từ máy chủ. Bấm Làm mới để thử lại.';
      render();
      document.getElementById('mon-loading')?.remove();
      if (typeof showToast === 'function') {
        showToast(stations.length ? 'Mất kết nối máy chủ. Đang giữ dữ liệu đã tải trước đó.' : loadError, 'warning');
      }
    }
  }

  function matchesStatus(point, wanted) {
    if (!wanted) return true;
    if (wanted === 'online' || wanted === 'offline') return point.status === wanted;
    if (wanted === 'lỗi') return pointHasFault(point);
    // An offline point's last known connector state does not make it ready.
    if (point.status === 'offline') return false;
    return operationalStatus(point) === wanted ||
      (point.connectors || []).some(connector => operationalStatus(connector) === wanted);
  }

  function filteredStations() {
    const search = (document.getElementById('mon-search')?.value || '').trim().toLocaleLowerCase('vi');
    const status = document.getElementById('mon-status-filter')?.value || '';
    return stations.flatMap(station => {
      const stationMatches = [station.name, station.address].filter(Boolean)
        .join(' ').toLocaleLowerCase('vi').includes(search);
      const points = (station.charge_points || []).filter(point =>
        (!search || stationMatches || String(point.code || '').toLocaleLowerCase('vi').includes(search)) &&
        matchesStatus(point, status)
      );
      // Copies preserve the complete API tree for counters and later filters.
      if (points.length || (!status && stationMatches && !(station.charge_points || []).length)) {
        return [{ ...station, charge_points: points }];
      }
      return [];
    });
  }

  function connectorMarkup(connector, offline = false) {
    const displayedStatus = offline ? 'unknown' :
      (hasFault(connector) ? 'Faulted' : (connector.ocpp_status || connector.status));
    return `<div class="connector-status" aria-label="Đầu nối ${escapeHtml(connector.connector_id)}: ${escapeHtml(STATUS[displayedStatus]?.[0] || STATUS.unknown[0])}">
      <span class="connector-status__number">Đầu ${escapeHtml(connector.connector_id)}</span>
      ${statusBadge(displayedStatus)}
    </div>`;
  }

  function chargePointMarkup(point) {
    const connectorMarkupList = (point.connectors || []).map(connector => connectorMarkup(connector, point.status === 'offline')).join('');
    const lastSeen = point.status === 'offline' && point.last_seen_at
      ? `<p class="cp-tile__last-seen">Liên lạc lần cuối: ${escapeHtml(formatLastSeen(point.last_seen_at))}</p>`
      : '';
    return `<section class="cp-tile" aria-label="Trụ ${escapeHtml(point.code)}" data-cp-code="${escapeHtml(point.code)}">
      <div class="cp-tile__header">
        <strong class="cp-tile__code">${escapeHtml(point.code)}</strong>${statusBadge(pointDisplayStatus(point))}
      </div>
      ${lastSeen}
      <div class="connector-list">${connectorMarkupList || '<span class="muted-text">Chưa khai báo đầu nối</span>'}</div>
    </section>`;
  }

  function stationStatus(station) {
    if (['maintenance', 'inactive', 'locked'].includes(station.status)) return station.status;
    const points = station.charge_points || [];
    if (!points.length) return station.status || 'unknown';
    return points.every(point => point.status === 'offline') ? 'offline' : 'online';
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
      empty.innerHTML = `<div class="empty-state__title">${loadError ? 'Không tải được dữ liệu' : 'Không có kết quả'}</div><div class="empty-state__desc">${escapeHtml(loadError || 'Chưa có trụ sạc hoặc không có trụ phù hợp bộ lọc')}</div>`;
      grid.appendChild(empty);
    } else {
      result.forEach(station => {
        const card = document.createElement('article');
        card.className = 'station-card';
        card.dataset.stationId = station.id;
        const original = stations.find(item => item.id === station.id);
        card.innerHTML = `<button class="station-card__open" type="button" aria-label="Xem chi tiết trạm ${escapeHtml(station.name)}">
          <span class="station-card__heading"><span><strong class="station-card__name">${escapeHtml(station.name)}</strong>
          <span class="station-card__addr">${escapeHtml(station.address || '')}</span></span>${statusBadge(stationStatus(original))}</span>
        </button><div class="station-card__body"><div class="cp-grid">
          ${(station.charge_points || []).map(chargePointMarkup).join('') || '<p class="muted-text">Trạm chưa có trụ sạc.</p>'}
        </div></div>`;
        card.querySelector('.station-card__open').addEventListener('click', () => openDetail(station));
        card.querySelectorAll('.cp-tile').forEach(tile => {
          tile.style.cursor = 'pointer';
          tile.addEventListener('click', event => {
            event.stopPropagation();
            openDetail(station);
          });
        });
        grid.appendChild(card);
      });
    }
    updateStats();
    if (activeDetailStationId !== null) {
      const detail = result.find(station => station.id === activeDetailStationId);
      if (detail) renderDetailBody(detail);
      else closeDetail();
    }
  }

  function updateStats() {
    const points = stations.flatMap(station => station.charge_points || []);
    const connectors = points.filter(point => point.status !== 'offline').flatMap(point => point.connectors || []);
    const totalEl = document.getElementById('mon-total');
    const chargingEl = document.getElementById('mon-charging');
    const offlineEl = document.getElementById('mon-offline');
    const faultEl = document.getElementById('mon-fault');
    if (totalEl) totalEl.textContent = points.length;
    if (chargingEl) chargingEl.textContent = connectors.filter(connector => operationalStatus(connector) === 'bận').length;
    if (offlineEl) offlineEl.textContent = points.filter(point => point.status === 'offline').length;
    if (faultEl) faultEl.textContent = points.filter(pointHasFault).length;
  }

  // SCRUM-190: chọn đầu nối và nút bắt đầu sạc.
  function startChargingMarkup(point) {
    const connectors = point.connectors || [];

    const options = connectors.map(connector => {
      const available = point.status === 'online' &&
        (connector.ocpp_status
          ? connector.ocpp_status === 'Available'
          : connector.status === 'rảnh');

      return `
        <option value="${escapeHtml(connector.connector_id)}"
                ${available ? '' : 'disabled'}>
          Đầu nối ${escapeHtml(connector.connector_id)}
          — ${available ? 'Sẵn sàng' : 'Không khả dụng'}
        </option>`;
    }).join('');

    return `
      <div class="start-charging-controls">
        <label>
          Chọn đầu nối
          <select class="form-select" data-start-connector>
            <option value="">-- Chọn đầu nối --</option>
            ${options}
          </select>
        </label>

        <label>Mã thẻ RFID <input class="form-input" data-start-tag maxlength="20" autocomplete="off" placeholder="Nhập mã thẻ được cấp" /></label>
        <button class="btn btn--primary"
                type="button"
                data-start-charging
                data-cp-code="${escapeHtml(point.code)}"
                disabled>
          Bắt đầu sạc
        </button>

        <p data-start-message role="status" aria-live="polite"></p>
      </div>`;
  }
  function renderDetailBody(station, body = document.getElementById('detail-body')) {
    if (!body) return;
    body.innerHTML = `<p class="detail-address">${escapeHtml(station.address || '')}</p>
      <div class="detail-points">${(station.charge_points || []).map(point => {
      const lastSeen = point.last_seen_at
        ? `<p class="cp-tile__last-seen">Liên lạc lần cuối: ${escapeHtml(formatLastSeen(point.last_seen_at))}</p>` : '';
      const restartMarkup = canReset ? RestartButton.createMarkup(point) : '';
      return `<section class="detail-point"><div class="detail-point__heading"><strong>${escapeHtml(point.code)}</strong>${statusBadge(pointDisplayStatus(point))}</div>
          <p class="detail-point__meta">${point.vendor ? `Nhà sản xuất: ${escapeHtml(point.vendor)}` : ''}${point.model ? ` · Model: ${escapeHtml(point.model)}` : ''}</p>
          ${lastSeen}<div class="connector-list">${(point.connectors || []).map(connector => connectorMarkup(connector, point.status === 'offline')).join('') || '<span class="muted-text">Chưa khai báo đầu nối</span>'}</div>${startChargingMarkup(point)}${restartMarkup}</section>`;
    }).join('') || '<p class="muted-text">Trạm chưa có trụ sạc.</p>'}</div>`;
    RestartButton.bindEvents(body);
    body.querySelectorAll('.start-charging-controls').forEach(bindStartControls);
  }

  function startState(code) {
    if (!startRequests.has(code)) startRequests.set(code, { pending: false, message: '', selected: '', tag: '' });
    return startRequests.get(code);
  }

  function bindStartControls(controls) {
    const select = controls.querySelector('[data-start-connector]');
    const button = controls.querySelector('[data-start-charging]');
    const tag = controls.querySelector('[data-start-tag]');
    const message = controls.querySelector('[data-start-message]');
    const state = startState(button.dataset.cpCode);
    const usable = () => {
      const point = stations.flatMap(station => station.charge_points || []).find(point => point.code === button.dataset.cpCode);
      const connector = point?.connectors?.find(item => String(item.connector_id) === select.value);
      return point?.status === 'online' && connector &&
        (connector.ocpp_status ? connector.ocpp_status === 'Available' : connector.status === 'rảnh');
    };
    const update = () => {
      select.disabled = tag.disabled = state.pending;
      button.disabled = state.pending || !usable() || !tag.value.trim() || tag.value.trim().length > 20;
      button.textContent = state.pending ? 'Đang chờ bắt đầu sạc…' : 'Bắt đầu sạc';
      message.textContent = state.message;
    };
    if (state.selected) select.value = state.selected;
    if (state.tag !== undefined) tag.value = state.tag;
    state.update = update;
    select.addEventListener('change', () => { if (!state.pending) { state.selected = select.value; state.message = ''; } update(); });
    tag.addEventListener('input', () => { if (!state.pending) state.tag = tag.value; update(); });
    button.addEventListener('click', async () => {
      if (state.pending || !usable() || !tag.value.trim() || tag.value.trim().length > 20) return;
      state.selected = select.value;
      state.tag = tag.value.trim();
      state.pending = true;
      state.message = 'Đang gửi yêu cầu bắt đầu sạc. Chờ tối đa 60 giây…';
      const started = Date.now();
      const controller = new AbortController();
      state.controller = controller;
      const active = () => state.pending && state.controller === controller;
      const finish = text => {
        if (!active()) return;
        state.pending = false; state.message = text;
        clearTimeout(state.deadline); clearTimeout(state.poll);
        controller.abort(); state.update();
      };
      const expire = () => finish('Hết thời gian chờ 60 giây, chưa xác nhận được phiên sạc. Kiểm tra trạng thái trước khi thử lại.');
      const withinDeadline = () => {
        if (!active()) return false;
        if (Date.now() - started >= 60000) { expire(); return false; }
        return true;
      };
      state.deadline = setTimeout(expire, 60000);
      update();
      const poll = async () => {
        if (!withinDeadline()) return;
        try {
          let user = {};
          try { user = JSON.parse(document.getElementById('auth-context')?.textContent || '{}'); } catch (_) { }
          const driver = user.roles?.includes('driver');
          const response = driver
            ? await ApiClient.getCurrentSession({ signal: controller.signal })
            : await ApiClient.listAllSessions({ status: 'active', page_size: 100 }, { signal: controller.signal });
          if (!withinDeadline()) return;
          const sessions = driver ? [response] : (response?.items || []);
          const session = sessions.find(item => item && item.charge_point_code === button.dataset.cpCode &&
            Number(item.connector_number) === Number(state.selected) && !item.ended_at &&
            Date.parse(item.started_at) >= started - 1000);
          if (session) {
            finish('Phiên sạc đã bắt đầu.');
            if (driver) window.location.assign('/sessions/mine');
            else if (user.roles?.some(role => ['admin', 'operator'].includes(role))) window.location.assign('/audit');
            return;
          }
        } catch (error) {
          if (!withinDeadline()) return;
          if ([401, 403].includes(error.status)) { finish(error.message || 'Không có quyền kiểm tra phiên sạc.'); return; }
        }
        if (active()) state.poll = setTimeout(poll, 2000);
      };
      try {
        const result = await ApiClient.remoteStartChargePoint(button.dataset.cpCode, Number(state.selected), tag.value.trim(), { signal: controller.signal });
        if (!withinDeadline()) return;
        if (result?.status !== 'Accepted') { finish('Trụ từ chối bắt đầu sạc. Vui lòng kiểm tra súng sạc đã cắm và mã thẻ.'); return; }
        state.message = 'Trụ đã nhận lệnh. Đang chờ phiên sạc bắt đầu (tối đa 60 giây)…';
        state.update();
        await poll();
      } catch (error) {
        if (!withinDeadline()) return;
        if (error.status === 409) finish(/ngoại tuyến|ngắt kết nối/i.test(error.message || '') ? error.message : 'Trụ hoặc đầu nối đang bận. Vui lòng chọn đầu nối khác.');
        else if (error.status === 504 || error.name === 'AbortError') finish('Hết thời gian chờ, trụ chưa phản hồi. Kiểm tra trạng thái trước khi thử lại.');
        else if (error.status === 502) finish('Trụ từ chối bắt đầu sạc. Vui lòng kiểm tra súng sạc đã cắm và mã thẻ.');
        else finish(error.message || 'Không thể gửi yêu cầu bắt đầu sạc. Vui lòng thử lại.');
      }
    });
    update();
  }

  function openDetail(station) {
    activeDetailStationId = station.id;
    document.getElementById('detail-title').textContent = station.name;
    renderDetailBody(station);
    document.getElementById('detail-backdrop').classList.remove('is-hidden');
    document.getElementById('detail-close').focus();
  }

  function connectSSE() {
    SseClient.on('_connected', () => {
      isSseConnected = true;
      updateRealtimeIndicator();
      loadData(); // Restore the complete tree after initial connection or reconnect.
    });
    SseClient.on('_error', () => {
      isSseConnected = false;
      updateRealtimeIndicator();
    });
    SseClient.on('status_update', payload => {
      const station = stations.find(item => item.id === payload.station_id);
      if (station && Array.isArray(payload.charge_points)) {
        ++loadRequestId; // An older HTTP snapshot must not replace this newer event.
        station.charge_points = payload.charge_points;
        render();
      } else {
        loadData();
      }
    });
    SseClient.connect('/api/monitoring/sse');
  }

  document.addEventListener('DOMContentLoaded', () => {
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
    // Controls must work even if the realtime transport cannot start.
    loadData();
    try {
      connectSSE();
    } catch (error) {
      isSseConnected = false;
      updateRealtimeIndicator();
      if (typeof showToast === 'function') {
        showToast('Chưa kết nối được cập nhật trực tiếp. Bấm Làm mới để tải trạng thái.', 'warning');
      }
    }
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
    activeDetailStationId = null;
    document.getElementById('detail-backdrop')?.classList.add('is-hidden');
  }
  if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
    window.addEventListener('pagehide', () => {
      startRequests.forEach(state => {
        clearTimeout(state.deadline);
        clearTimeout(state.poll);
        if (state.pending) {
          state.pending = false;
          state.message = 'Đã dừng theo dõi yêu cầu khi rời trang. Kiểm tra trạng thái trước khi thử lại.';
          state.update?.();
        }
        state.controller?.abort();
      });
    });
  }
})();
