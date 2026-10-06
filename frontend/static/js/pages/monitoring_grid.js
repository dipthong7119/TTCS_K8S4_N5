/** Realtime station, charge point, and connector monitoring (T-24, T-25, T-35, SCRUM-134). */
(function () {
  'use strict';

  let stations = [];
  let isMockMode = false;
  let mockModeSelected = false;
  let dataSourceVersion = 0;
  let isSseConnected = false;
  let loadRequestId = 0;
  let loadError = '';
  const canReset = document.getElementById('monitoring-grid')?.dataset.canReset === 'true';

  // Bộ dữ liệu mẫu 20 trụ sạc đáp ứng tiêu chí nghiệm thu SCRUM-124 / T-24 (Story S-11)
  const MOCK_STATIONS_20_POINTS = [
    {
      id: 1,
      name: "Trạm Sạc TT01 — Hoàn Kiếm",
      address: "12 Tràng Tiền, Hoàn Kiếm, Hà Nội",
      status: "active",
      charge_points: [
        {
          id: 101, code: "CP-HN-01", station_id: 1, status: "online", ocpp_status: "Available",
          vendor: "ABB", model: "Terra 54", firmware_version: "v1.4.2", last_seen_at: new Date().toISOString(),
          connectors: [
            { id: 1001, connector_id: 1, status: "rảnh", ocpp_status: "Available" },
            { id: 1002, connector_id: 2, status: "rảnh", ocpp_status: "Available" }
          ]
        },
        {
          id: 102, code: "CP-HN-02", station_id: 1, status: "online", ocpp_status: "Charging",
          vendor: "ABB", model: "Terra 54", firmware_version: "v1.4.2", last_seen_at: new Date().toISOString(),
          connectors: [
            { id: 1003, connector_id: 1, status: "bận", ocpp_status: "Charging" },
            { id: 1004, connector_id: 2, status: "rảnh", ocpp_status: "Available" }
          ]
        },
        {
          id: 103, code: "CP-HN-03", station_id: 1, status: "online", ocpp_status: "Reserved",
          vendor: "Schneider", model: "EVlink Pro", firmware_version: "v2.1.0", last_seen_at: new Date().toISOString(),
          connectors: [
            { id: 1005, connector_id: 1, status: "đặt chỗ", ocpp_status: "Reserved" }
          ]
        },
        {
          id: 104, code: "CP-HN-04", station_id: 1, status: "offline", ocpp_status: "offline",
          vendor: "Schneider", model: "EVlink Pro", firmware_version: "v2.1.0",
          last_seen_at: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
          connectors: [
            { id: 1006, connector_id: 1, status: "unknown", ocpp_status: "Unavailable" },
            { id: 1007, connector_id: 2, status: "unknown", ocpp_status: "Unavailable" }
          ]
        },
        {
          id: 105, code: "CP-HN-05", station_id: 1, status: "online", ocpp_status: "Faulted",
          vendor: "ABB", model: "Terra 124", firmware_version: "v1.6.0", last_seen_at: new Date().toISOString(),
          connectors: [
            { id: 1008, connector_id: 1, status: "lỗi", ocpp_status: "Faulted" },
            { id: 1009, connector_id: 2, status: "rảnh", ocpp_status: "Available" }
          ]
        }
      ]
    },
    {
      id: 2,
      name: "Trạm Sạc TT02 — Cầu Giấy",
      address: "88 Duy Tân, Cầu Giấy, Hà Nội",
      status: "active",
      charge_points: [
        {
          id: 201, code: "CP-HN-06", station_id: 2, status: "online", ocpp_status: "Available",
          vendor: "StarCharge", model: "Titan 180kW", firmware_version: "v3.0.1", last_seen_at: new Date().toISOString(),
          connectors: [
            { id: 2001, connector_id: 1, status: "rảnh", ocpp_status: "Available" },
            { id: 2002, connector_id: 2, status: "rảnh", ocpp_status: "Available" }
          ]
        },
        {
          id: 202, code: "CP-HN-07", station_id: 2, status: "online", ocpp_status: "Charging",
          vendor: "StarCharge", model: "Titan 180kW", firmware_version: "v3.0.1", last_seen_at: new Date().toISOString(),
          connectors: [
            { id: 2003, connector_id: 1, status: "bận", ocpp_status: "Charging" },
            { id: 2004, connector_id: 2, status: "bận", ocpp_status: "Charging" }
          ]
        },
        {
          id: 203, code: "CP-HN-08", station_id: 2, status: "online", ocpp_status: "Available",
          vendor: "StarCharge", model: "Nova 60kW", firmware_version: "v2.4.5", last_seen_at: new Date().toISOString(),
          connectors: [
            { id: 2005, connector_id: 1, status: "rảnh", ocpp_status: "Available" }
          ]
        },
        {
          id: 204, code: "CP-HN-09", station_id: 2, status: "offline", ocpp_status: "offline",
          vendor: "Delta", model: "Ultra Fast 150kW", firmware_version: "v1.2.9",
          last_seen_at: new Date(Date.now() - 120 * 60 * 1000).toISOString(),
          connectors: [
            { id: 2006, connector_id: 1, status: "unknown", ocpp_status: "Unavailable" },
            { id: 2007, connector_id: 2, status: "unknown", ocpp_status: "Unavailable" }
          ]
        },
        {
          id: 205, code: "CP-HN-10", station_id: 2, status: "online", ocpp_status: "Available",
          vendor: "Delta", model: "City Charger 50kW", firmware_version: "v1.1.4", last_seen_at: new Date().toISOString(),
          connectors: [
            { id: 2008, connector_id: 1, status: "rảnh", ocpp_status: "Available" },
            { id: 2009, connector_id: 2, status: "rảnh", ocpp_status: "Available" }
          ]
        }
      ]
    },
    {
      id: 3,
      name: "Trạm Sạc TT03 — Nam Từ Liêm (Mỹ Đình)",
      address: "1 Lê Đức Thọ, Nam Từ Liêm, Hà Nội",
      status: "active",
      charge_points: [
        {
          id: 301, code: "CP-HN-11", station_id: 3, status: "online", ocpp_status: "Charging",
          vendor: "ABB", model: "Terra 184", firmware_version: "v1.8.2", last_seen_at: new Date().toISOString(),
          connectors: [
            { id: 3001, connector_id: 1, status: "bận", ocpp_status: "Charging" },
            { id: 3002, connector_id: 2, status: "rảnh", ocpp_status: "Available" }
          ]
        },
        {
          id: 302, code: "CP-HN-12", station_id: 3, status: "online", ocpp_status: "Available",
          vendor: "ABB", model: "Terra 184", firmware_version: "v1.8.2", last_seen_at: new Date().toISOString(),
          connectors: [
            { id: 3003, connector_id: 1, status: "rảnh", ocpp_status: "Available" },
            { id: 3004, connector_id: 2, status: "rảnh", ocpp_status: "Available" }
          ]
        },
        {
          id: 303, code: "CP-HN-13", station_id: 3, status: "online", ocpp_status: "Faulted",
          vendor: "Schneider", model: "EVlink 22kW", firmware_version: "v2.0.3", last_seen_at: new Date().toISOString(),
          connectors: [
            { id: 3005, connector_id: 1, status: "lỗi", ocpp_status: "Faulted" }
          ]
        },
        {
          id: 304, code: "CP-HN-14", station_id: 3, status: "online", ocpp_status: "Available",
          vendor: "Schneider", model: "EVlink 22kW", firmware_version: "v2.0.3", last_seen_at: new Date().toISOString(),
          connectors: [
            { id: 3006, connector_id: 1, status: "rảnh", ocpp_status: "Available" },
            { id: 3007, connector_id: 2, status: "rảnh", ocpp_status: "Available" }
          ]
        },
        {
          id: 305, code: "CP-HN-15", station_id: 3, status: "offline", ocpp_status: "offline",
          vendor: "ABB", model: "Terra 54", firmware_version: "v1.4.2",
          last_seen_at: new Date(Date.now() - 3 * 3600 * 1000).toISOString(),
          connectors: [
            { id: 3008, connector_id: 1, status: "unknown", ocpp_status: "Unavailable" },
            { id: 3009, connector_id: 2, status: "unknown", ocpp_status: "Unavailable" }
          ]
        }
      ]
    },
    {
      id: 4,
      name: "Trạm Sạc TT04 — Long Biên (Aeon)",
      address: "27 Cổ Linh, Long Biên, Hà Nội",
      status: "active",
      charge_points: [
        {
          id: 401, code: "CP-HN-16", station_id: 4, status: "online", ocpp_status: "Available",
          vendor: "StarCharge", model: "Titan 120kW", firmware_version: "v2.8.0", last_seen_at: new Date().toISOString(),
          connectors: [
            { id: 4001, connector_id: 1, status: "rảnh", ocpp_status: "Available" },
            { id: 4002, connector_id: 2, status: "rảnh", ocpp_status: "Available" }
          ]
        },
        {
          id: 402, code: "CP-HN-17", station_id: 4, status: "online", ocpp_status: "Charging",
          vendor: "StarCharge", model: "Titan 120kW", firmware_version: "v2.8.0", last_seen_at: new Date().toISOString(),
          connectors: [
            { id: 4003, connector_id: 1, status: "bận", ocpp_status: "Charging" },
            { id: 4004, connector_id: 2, status: "rảnh", ocpp_status: "Available" }
          ]
        },
        {
          id: 403, code: "CP-HN-18", station_id: 4, status: "online", ocpp_status: "Reserved",
          vendor: "StarCharge", model: "Nova 30kW", firmware_version: "v2.2.1", last_seen_at: new Date().toISOString(),
          connectors: [
            { id: 4005, connector_id: 1, status: "đặt chỗ", ocpp_status: "Reserved" },
            { id: 4006, connector_id: 2, status: "rảnh", ocpp_status: "Available" }
          ]
        },
        {
          id: 404, code: "CP-HN-19", station_id: 4, status: "online", ocpp_status: "Available",
          vendor: "Delta", model: "City Charger 50kW", firmware_version: "v1.1.4", last_seen_at: new Date().toISOString(),
          connectors: [
            { id: 4007, connector_id: 1, status: "rảnh", ocpp_status: "Available" },
            { id: 4008, connector_id: 2, status: "rảnh", ocpp_status: "Available" }
          ]
        },
        {
          id: 405, code: "CP-HN-20", station_id: 4, status: "online", ocpp_status: "Available",
          vendor: "Delta", model: "City Charger 50kW", firmware_version: "v1.1.4", last_seen_at: new Date().toISOString(),
          connectors: [
            { id: 4009, connector_id: 1, status: "rảnh", ocpp_status: "Available" },
            { id: 4010, connector_id: 2, status: "rảnh", ocpp_status: "Available" }
          ]
        }
      ]
    }
  ];

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

  function formatLastSeen(timestamp) {
    // DB timestamps without an offset are UTC. Date otherwise interprets
    // them in the browser's local zone and shifts the displayed instant.
    const value = /(?:Z|[+-]\d{2}:\d{2})$/i.test(timestamp) ? timestamp : `${timestamp}Z`;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 'Không rõ' : date.toLocaleString('vi-VN');
  }

  function internalStatus(ocppStatus) {
    if (ocppStatus === 'Available') return 'rảnh';
    if (['Preparing', 'Charging', 'SuspendedEV', 'SuspendedEVSE', 'Finishing'].includes(ocppStatus)) return 'bận';
    if (ocppStatus === 'Reserved') return 'đặt chỗ';
    if (['Unavailable', 'Faulted'].includes(ocppStatus)) return 'lỗi';
    return 'unknown';
  }

  let activeDetailStationId = null;
  // SCRUM-191: lưu trạng thái chờ theo mã trụ.
  const startRequests = new Map();

  function connectorAvailable(point, connector) {
    return point?.status === 'online' && Boolean(connector) &&
      (connector.ocpp_status ? connector.ocpp_status === 'Available' : connector.status === 'rảnh');
  }

  function findStartPoint(code) {
    return stations.flatMap(station => station.charge_points || []).find(point => point.code === code);
  }

  function updateStartWaitingUI() {
    for (const [code, request] of startRequests) {
      if (!['sending', 'waiting'].includes(request.phase)) continue;
      const point = isMockMode ? null : findStartPoint(code);
      const connector = point?.connectors?.find(item => String(item.connector_id) === request.connectorId);
      if (connector?.ocpp_status === 'Charging') {
        request.phase = 'success';
        request.message = 'Đầu nối đã chuyển sang trạng thái đang sạc.';
        request.controller.abort();
      } else if (point?.status === 'offline') {
        request.phase = 'error';
        request.message = 'Trụ đã mất kết nối. Hãy kiểm tra trạng thái trước khi thử lại.';
        request.controller.abort();
      } else if (Date.now() >= request.deadline) {
        request.phase = 'error';
        request.message = 'Hết thời gian chờ 60 giây. Chưa xác nhận được phiên sạc; hãy kiểm tra trạng thái trước khi thử lại.';
        request.controller.abort();
      }
    }
    document.querySelectorAll('.start-charging-controls').forEach(controls => {
      const select = controls.querySelector('[data-start-connector]');
      const tag = controls.querySelector('[data-start-id-tag]');
      const button = controls.querySelector('[data-start-charging]');
      const message = controls.querySelector('[data-start-message]');
      const request = startRequests.get(button.dataset.cpCode);
      const pending = request && ['sending', 'waiting'].includes(request.phase);
      if (request) {
        select.value = request.connectorId;
        tag.value = request.idTag;
        const seconds = Math.max(0, Math.ceil((request.deadline - Date.now()) / 1000));
        message.textContent = pending
          ? `${request.phase === 'sending' ? 'Đang gửi yêu cầu' : 'Trụ đã chấp nhận lệnh, đang chờ bắt đầu sạc'}… còn ${seconds} giây.`
          : request.message;
      }
      const point = findStartPoint(button.dataset.cpCode);
      const connector = point?.connectors?.find(item => String(item.connector_id) === select.value);
      select.disabled = Boolean(pending);
      tag.disabled = Boolean(pending);
      button.disabled = Boolean(pending) || isMockMode || !connectorAvailable(point, connector) ||
        !tag.value.trim() || tag.value.trim().length > 20;
      button.textContent = pending ? 'Đang chờ...' : 'Bắt đầu sạc';
      if (isMockMode && !request) message.textContent = 'Đang xem dữ liệu mẫu. Chuyển sang dữ liệu máy chủ để gửi lệnh sạc.';
    });
  }

  async function submitRemoteStart(code, connectorId, idTag) {
    const previous = startRequests.get(code);
    if (previous && ['sending', 'waiting'].includes(previous.phase)) return;
    const point = findStartPoint(code);
    const connector = point?.connectors?.find(item => String(item.connector_id) === connectorId);
    if (isMockMode || !connectorAvailable(point, connector) || !idTag || idTag.length > 20) return;
    const request = {
      connectorId, idTag, phase: 'sending', deadline: Date.now() + 60000,
      controller: new AbortController(), message: ''
    };
    startRequests.set(code, request);
    updateStartWaitingUI();
    try {
      const result = await ApiClient.remoteStartChargePoint(code, Number(connectorId), idTag,
        { signal: request.controller.signal });
      if (request.phase !== 'sending') return;
      if (result?.status === 'Accepted') {
        request.phase = 'waiting';
      } else {
        request.phase = 'error';
        request.message = result?.status === 'Rejected'
          ? (result.message || 'Trụ từ chối lệnh bắt đầu sạc.')
          : 'Phản hồi không hợp lệ từ máy chủ. Hãy kiểm tra trạng thái trụ.';
      }
    } catch (error) {
      if (request.phase !== 'sending') return;
      request.phase = 'error';
      request.message = error.message || 'Không thể gửi lệnh bắt đầu sạc. Vui lòng thử lại.';
    } finally {
      updateStartWaitingUI();
    }
  }

  const startWaitingTimer = window.setInterval(updateStartWaitingUI, 1000);
  window.addEventListener('pagehide', () => {
    window.clearInterval(startWaitingTimer);
    for (const request of startRequests.values()) request.controller.abort();
  });

  function updateMockBtnUI() {
    const btn = document.getElementById('btn-toggle-mock');
    const label = document.getElementById('mock-btn-label');
    if (!btn || !label) return;
    if (isMockMode) {
      loadError = '';
      btn.classList.add('is-active');
      label.textContent = 'Dữ liệu máy chủ (API)';
      btn.title = 'Đang xem dữ liệu mẫu 20 trụ. Bấm để chuyển sang dữ liệu máy chủ';
    } else {
      btn.classList.remove('is-active');
      label.textContent = 'Dữ liệu mẫu (20 trụ)';
      btn.title = 'Bấm để nạp bộ dữ liệu mẫu 20 trụ kiểm thử giao diện';
    }
    updateRealtimeIndicator();
  }

  function updateRealtimeIndicator() {
    const indicator = document.getElementById('sse-indicator');
    const label = document.getElementById('sse-label');
    if (indicator) indicator.className = `sse-indicator ${isMockMode || isSseConnected ? 'connected' : 'error'}`;
    if (label) label.textContent = isMockMode ? 'Đang mô phỏng' : (isSseConnected ? 'Đang theo dõi' : 'Đang kết nối lại');
  }

  function toggleMockMode() {
    isMockMode = !isMockMode;
    mockModeSelected = isMockMode;
    dataSourceVersion += 1;
    closeDetail();
    loadRequestId += 1; // Ignore an in-flight API response after the user changes sources.
    if (isMockMode) {
      stations = JSON.parse(JSON.stringify(MOCK_STATIONS_20_POINTS));
      render();
      document.getElementById('mon-loading')?.remove();
      updateMockBtnUI();
      if (typeof RealtimeStatus !== 'undefined' && typeof RealtimeStatus.connect === 'function') {
        RealtimeStatus.connect(stations.flatMap(station => station.charge_points || []));
      }
      if (typeof showToast === 'function') {
        showToast('Đang hiển thị bộ dữ liệu mẫu 20 trụ kiểm thử giao diện (SCRUM-124 / T-24)', 'info');
      }
    } else {
      if (typeof RealtimeStatus !== 'undefined' && typeof RealtimeStatus.disconnect === 'function') {
        RealtimeStatus.disconnect();
      }
      updateMockBtnUI();
      loadData(true);
    }
  }

  async function loadData(forceServer = false) {
    const requestId = ++loadRequestId;
    if (forceServer) {
      isMockMode = false;
      mockModeSelected = false;
      updateMockBtnUI();
    }
    if (isMockMode && mockModeSelected) {
      render();
      document.getElementById('mon-loading')?.remove();
      updateMockBtnUI();
      return;
    }

    try {
      const result = await ApiClient.getMonitoringTree();
      if (requestId !== loadRequestId) return;
      const serverStations = Array.isArray(result) ? result : (result?.stations || []);
      stations = serverStations;
      isMockMode = false;
      loadError = '';
      render();
      if (activeDetailStationId) {
        const curStation = stations.find(s => s.id === activeDetailStationId);
        if (curStation) renderDetailBody(curStation);
      }
      document.getElementById('mon-loading')?.remove();
      updateMockBtnUI();
    } catch (error) {
      if (requestId !== loadRequestId) return;
      loadError = 'Không tải được trạng thái từ máy chủ. Bấm Làm mới để thử lại.';
      render();
      document.getElementById('mon-loading')?.remove();
      updateMockBtnUI();
      if (typeof showToast === 'function') {
        showToast(stations.length ? 'Mất kết nối máy chủ. Đang giữ dữ liệu đã tải trước đó.' : loadError, 'warning');
      }
    }
  }

  function matchesStatus(station, wanted) {
    if (!wanted) return true;
    return (station.charge_points || []).some(point =>
      point.status === wanted || internalStatus(point.ocpp_status) === wanted ||
      (point.connectors || []).some(connector => connector.status === wanted || internalStatus(connector.ocpp_status) === wanted)
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
      ? `<p class="cp-tile__last-seen">Liên lạc lần cuối: ${escapeHtml(formatLastSeen(point.last_seen_at))}</p>`
      : '';
    return `<section class="cp-tile" aria-label="Trụ ${escapeHtml(point.code)}" data-cp-code="${escapeHtml(point.code)}">
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
    if (points.some(point => point.status === 'lỗi' || internalStatus(point.ocpp_status) === 'lỗi' || (point.connectors || []).some(connector => connector.status === 'lỗi' || internalStatus(connector.ocpp_status) === 'lỗi'))) return 'lỗi';
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
      empty.innerHTML = `<div class="empty-state__title">${loadError ? 'Không tải được dữ liệu' : 'Không có kết quả'}</div><div class="empty-state__desc">${escapeHtml(loadError || 'Chưa có trụ sạc hoặc không có trụ phù hợp bộ lọc')}</div>`;
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
        card.querySelectorAll('.cp-tile').forEach(tile => {
          tile.style.cursor = 'pointer';
          tile.addEventListener('click', (e) => {
            e.stopPropagation();
            openDetail(station);
          });
        });
        grid.appendChild(card);
      });
    }
    updateStats();
  }

  function updateStats() {
    const points = stations.flatMap(station => station.charge_points || []);
    const connectors = points.flatMap(point => point.connectors || []);
    const totalEl = document.getElementById('mon-total');
    const chargingEl = document.getElementById('mon-charging');
    const offlineEl = document.getElementById('mon-offline');
    const faultEl = document.getElementById('mon-fault');
    if (totalEl) totalEl.textContent = points.length;
    if (chargingEl) chargingEl.textContent = connectors.filter(connector => connector.status === 'bận' || connector.ocpp_status === 'Charging').length;
    if (offlineEl) offlineEl.textContent = points.filter(point => point.status === 'offline').length;
    if (faultEl) faultEl.textContent =
      connectors.filter(connector => connector.status === 'lỗi' || connector.ocpp_status === 'Faulted').length +
      points.filter(point => internalStatus(point.ocpp_status) === 'lỗi' || point.status === 'lỗi').length;
  }
  // SCRUM-190: chọn đầu nối và nút bắt đầu sạc.
  function startChargingMarkup(point) {
    const connectors = point.connectors || [];

    const options = connectors.map(connector => {
      const available = connectorAvailable(point, connector);

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

        <label>
          Mã thẻ / mã tài xế
          <input class="form-input" type="text" data-start-id-tag
                 maxlength="20" required autocomplete="off" placeholder="Nhập mã từ 1 đến 20 ký tự">
        </label>
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
  function renderDetailBody(station, body) {
    if (!body) body = document.getElementById('detail-body');
    if (!body) return;
    body.innerHTML = `<p class="detail-address">${escapeHtml(station.address || '')}</p>
      <div class="detail-points">${(station.charge_points || []).map(point => {
      const lastSeen = point.last_seen_at
        ? `<p class="cp-tile__last-seen">Liên lạc lần cuối: ${escapeHtml(formatLastSeen(point.last_seen_at))}</p>` : '';
      const restartMarkup = canReset ? RestartButton.createMarkup(point) : '';
      return `<section class="detail-point"><div class="detail-point__heading"><strong>${escapeHtml(point.code)}</strong>${statusBadge(point.status)}</div>
          <p class="detail-point__meta">${point.vendor ? `Nhà sản xuất: ${escapeHtml(point.vendor)}` : ''}${point.model ? ` · Model: ${escapeHtml(point.model)}` : ''}</p>
          ${lastSeen}<div class="connector-list">${(point.connectors || []).map(connectorMarkup).join('') || '<span class="muted-text">Chưa khai báo đầu nối</span>'}</div>${startChargingMarkup(point)}${restartMarkup}</section>`;
    }).join('') || '<p class="muted-text">Trạm chưa có trụ sạc.</p>'}</div>`;
    const sourceVersion = dataSourceVersion;
    const resetChargePoint = isMockMode
      ? (code, type) => RealtimeStatus.resetChargePoint(code, type)
      : (code, type) => ApiClient.resetChargePoint(code, type);
    RestartButton.bindEvents(body, {
      resetChargePoint,
      isCurrentSource: () => sourceVersion === dataSourceVersion,
    });
    body.querySelectorAll('.start-charging-controls').forEach(controls => {
      const select = controls.querySelector('[data-start-connector]');
      const tag = controls.querySelector('[data-start-id-tag]');
      const button = controls.querySelector('[data-start-charging]');
      const clearResult = () => {
        const request = startRequests.get(button.dataset.cpCode);
        if (request && ['sending', 'waiting'].includes(request.phase)) return;
        startRequests.delete(button.dataset.cpCode);
        controls.querySelector('[data-start-message]').textContent = '';
        updateStartWaitingUI();
      };
      select.addEventListener('change', clearResult);
      tag.addEventListener('input', clearResult);
      button.addEventListener('click', () => {
        submitRemoteStart(button.dataset.cpCode, select.value, tag.value.trim());
      });
    });
    updateStartWaitingUI();
  }


  function openDetail(station) {
    activeDetailStationId = station.id;
    const backdrop = document.getElementById('detail-backdrop');
    const body = document.getElementById('detail-body');
    document.getElementById('detail-title').textContent = station.name;
    renderDetailBody(station, body);
    backdrop.classList.remove('is-hidden');
    document.getElementById('detail-close').focus();
  }

  function connectSSE() {
    SseClient.on('_connected', () => {
      isSseConnected = true;
      updateRealtimeIndicator();
      if (!mockModeSelected) {
        loadData(true); // Reload the complete server tree after initial connection or reconnect.
      }
    });
    SseClient.on('_error', () => {
      isSseConnected = false;
      updateRealtimeIndicator();
    });
    SseClient.on('status_update', payload => {
      if (mockModeSelected) return; // Giữ nguyên dữ liệu mẫu khi người dùng chủ động bật mock.
      const station = stations.find(item => item.id === payload.station_id);
      if (station && payload.charge_points) {
        station.charge_points = payload.charge_points;
        render();
        // Cập nhật tức thời Drawer chi tiết trạm nếu đang mở (realtime detail sync)
        if (activeDetailStationId === station.id) {
          renderDetailBody(station);
        }
      } else {
        // Trạm mới hoặc cây chưa có trạm này -> tải lại cây authoritative
        loadData(false);
      }
    });
    SseClient.connect('/api/monitoring/sse');
  }

  // ── Hook RealtimeStatus (Dành cho kiểm thử giao diện & mock) ───────────
  function connectRealtimeHook() {
    RealtimeStatus.subscribe('status_change', (payload) => {
      if (!isMockMode) return;
      for (const station of stations) {
        for (const point of (station.charge_points || [])) {
          if (point.code === payload.charge_point_code) {
            for (const conn of (point.connectors || [])) {
              if (conn.connector_id === payload.connector_id) {
                conn.ocpp_status = payload.status;
                conn.status = internalStatus(payload.status);
                conn.ocpp_status = payload.status;
              }
            }
            point.status = 'online';
            point.ocpp_status = payload.status;
            point.last_seen_at = payload.timestamp;
          }
        }
      }
      render();
      if (activeDetailStationId) {
        const cur = stations.find(s => s.id === activeDetailStationId);
        if (cur) renderDetailBody(cur);
      }
    });

    RealtimeStatus.subscribe('cp_offline', (payload) => {
      if (!isMockMode) return;
      for (const station of stations) {
        for (const point of (station.charge_points || [])) {
          if (point.code === payload.charge_point_code) {
            point.status = 'offline';
            point.ocpp_status = 'offline';
            (point.connectors || []).forEach(connector => {
              connector.status = 'unknown';
              connector.ocpp_status = 'unknown';
            });
          }
        }
      }
      render();
      if (activeDetailStationId) {
        const cur = stations.find(s => s.id === activeDetailStationId);
        if (cur) renderDetailBody(cur);
      }
      showToast(`Trụ ${payload.charge_point_code} đã mất kết nối`, 'warning');
    });

    RealtimeStatus.subscribe('cp_online', (payload) => {
      if (!isMockMode) return;
      for (const station of stations) {
        for (const point of (station.charge_points || [])) {
          if (point.code === payload.charge_point_code) {
            point.status = 'online';
            point.ocpp_status = 'unknown';
            point.last_seen_at = payload.timestamp;
          }
        }
      }
      render();
      if (activeDetailStationId) {
        const cur = stations.find(s => s.id === activeDetailStationId);
        if (cur) renderDetailBody(cur);
      }
      showToast(`Trụ ${payload.charge_point_code} đã trực tuyến trở lại`, 'success');
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    loadData();
    connectSSE();
    connectRealtimeHook();
    let debounce;
    document.getElementById('mon-search')?.addEventListener('input', () => {
      clearTimeout(debounce);
      debounce = setTimeout(render, 200);
    });
    document.getElementById('mon-status-filter')?.addEventListener('change', render);
    document.getElementById('btn-refresh-monitoring')?.addEventListener('click', () => loadData(false));
    document.getElementById('btn-toggle-mock')?.addEventListener('click', toggleMockMode);
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
    activeDetailStationId = null;
    const backdrop = document.getElementById('detail-backdrop');
    if (backdrop && !backdrop.classList.contains('is-hidden')) {
      backdrop.classList.add('is-hidden');
    }
  }
})();
