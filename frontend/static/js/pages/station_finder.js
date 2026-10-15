/**
 * station_finder.js — SCRUM-96 FE: Tài xế tìm trạm gần & thấy đầu nối rảnh
 * Subtasks SCRUM-241 (đếm đầu nối rảnh), SCRUM-242 (hiển thị bản đồ)
 * Author: Vy Hoàng Tú — Sprint 678
 *
 * API sử dụng:
 *   GET /api/monitoring/tree  → [{id, name, address, lat, lng, charge_points:[{code, status, connectors:[{connector_id, status}]}]}]
 *   GET /api/sse              → SSE stream cho status_update
 */

'use strict';

const StationFinder = (() => {
  // ── State ──────────────────────────────────────────────────────────────
  let _stations = [];       // raw data from API
  let _filtered = [];       // after filter/sort
  let _userLat = null;
  let _userLng = null;
  let _leafletMap = null;
  let _mapMarkers = {};     // { stationId: L.marker }
  let _viewMode = 'cards';  // 'cards' | 'map'
  let _activeStationId = null;

  // ── DOM refs ───────────────────────────────────────────────────────────
  const $grid        = () => document.getElementById('finder-grid');
  const $loading     = () => document.getElementById('finder-loading');
  const $empty       = () => document.getElementById('finder-empty');
  const $search      = () => document.getElementById('finder-search');
  const $statusFlt   = () => document.getElementById('finder-status-filter');
  const $sort        = () => document.getElementById('finder-sort');
  const $backdrop    = () => document.getElementById('finder-detail-backdrop');
  const $drawerTitle = () => document.getElementById('finder-detail-title');
  const $drawerAddr  = () => document.getElementById('finder-detail-addr');
  const $drawerBody  = () => document.getElementById('finder-detail-body');
  const $sseInd      = () => document.getElementById('finder-sse-indicator');
  const $sseLabel    = () => document.getElementById('finder-sse-label');
  const $cardsView   = () => document.getElementById('finder-cards-view');
  const $mapView     = () => document.getElementById('finder-map-view');

  // ── Connector status helpers ───────────────────────────────────────────
  const STATUS_LABEL = {
    available:   'Rảnh',
    charging:    'Đang sạc',
    occupied:    'Đang bận',
    reserved:    'Đã đặt',
    unavailable: 'Tạm ngừng',
    faulted:     'Lỗi',
    offline:     'Offline',
    unknown:     'Chưa rõ',
  };

  function _connectorClass(status) {
    const s = (status || 'unknown').toLowerCase();
    if (s === 'available') return 'chip--available';
    if (s === 'charging')  return 'chip--charging';
    if (s === 'occupied')  return 'chip--occupied';
    if (s === 'reserved')  return 'chip--reserved';
    if (s === 'faulted')   return 'chip--faulted';
    if (s === 'unavailable') return 'chip--unavailable';
    if (s === 'offline')   return 'chip--offline';
    return 'chip--unknown';
  }

  function _countAvailable(station) {
    let n = 0;
    (station.charge_points || []).forEach(cp => {
      (cp.connectors || []).forEach(c => {
        if ((c.status || '').toLowerCase() === 'available') n++;
      });
    });
    return n;
  }

  function _countTotal(station) {
    let n = 0;
    (station.charge_points || []).forEach(cp => {
      n += (cp.connectors || []).length;
    });
    return n;
  }

  function _stationCardClass(avail, total) {
    if (total === 0) return 'finder-card--offline';
    if (avail === 0) return 'finder-card--busy';
    if (avail === total) return 'finder-card--all-available';
    return 'finder-card--partial';
  }

  // ── Haversine distance (km) ────────────────────────────────────────────
  function _dist(lat1, lng1, lat2, lng2) {
    if (lat1 == null || lat2 == null) return Infinity;
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) ** 2 +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLng / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  function _fmtDist(km) {
    if (km === Infinity) return null;
    return km < 1 ? `${Math.round(km * 1000)} m` : `${km.toFixed(1)} km`;
  }

  // ── Statistics bar (SCRUM-241) ─────────────────────────────────────────
  function _renderStats(stations) {
    let avail = 0, charging = 0, stationCt = 0, offline = 0;
    stations.forEach(s => {
      const hasOnline = (s.charge_points || []).some(cp => cp.status !== 'offline');
      if (!hasOnline && (s.charge_points || []).length > 0) { offline++; return; }
      stationCt++;
      (s.charge_points || []).forEach(cp => {
        (cp.connectors || []).forEach(c => {
          const st = (c.status || '').toLowerCase();
          if (st === 'available') avail++;
          else if (st === 'charging') charging++;
        });
      });
    });
    document.getElementById('stat-available').textContent = avail;
    document.getElementById('stat-charging').textContent  = charging;
    document.getElementById('stat-stations').textContent  = stationCt;
    document.getElementById('stat-offline').textContent   = offline;
  }

  // ── Render connector chips ─────────────────────────────────────────────
  function _renderConnectorChips(station) {
    const chips = [];
    (station.charge_points || []).forEach(cp => {
      (cp.connectors || []).forEach(c => {
        const cls = _connectorClass(c.status);
        const label = STATUS_LABEL[(c.status || 'unknown').toLowerCase()] || c.status || 'Chưa rõ';
        chips.push(`
          <span class="finder-connector-chip ${cls}" title="Trụ ${cp.code} — Đầu nối #${c.connector_id}">
            <span class="connector-dot" aria-hidden="true"></span>
            #${c.connector_id} ${label}
          </span>
        `);
      });
    });
    if (!chips.length) {
      return '<span style="font-size:var(--font-size-xs);color:var(--color-text-muted);">Chưa có đầu nối</span>';
    }
    return chips.join('');
  }

  // ── Render one station card ────────────────────────────────────────────
  function _renderCard(station) {
    const avail = _countAvailable(station);
    const total = _countTotal(station);
    const cardCls = _stationCardClass(avail, total);
    const availBadgeCls = avail > 0 ? 'finder-card__avail-badge--yes' : 'finder-card__avail-badge--no';
    const availText = avail > 0 ? `${avail} rảnh` : 'Hết chỗ';
    const distKm = _dist(_userLat, _userLng, station.latitude, station.longitude);
    const distText = _fmtDist(distKm);
    const cpCount = (station.charge_points || []).length;

    const card = document.createElement('article');
    card.className = `finder-card ${cardCls}`;
    card.dataset.stationId = station.id;
    card.setAttribute('role', 'button');
    card.setAttribute('tabindex', '0');
    card.setAttribute('aria-label', `Trạm ${station.name} — ${avail} đầu nối rảnh`);

    card.innerHTML = `
      <div class="finder-card__header">
        <div class="finder-card__top">
          <h2 class="finder-card__name">${_esc(station.name)}</h2>
          <span class="finder-card__avail-badge ${availBadgeCls}">
            ${avail > 0 ? '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>' : ''}
            ${availText}
          </span>
        </div>
        ${station.address ? `
          <div class="finder-card__addr">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
            ${_esc(station.address)}
          </div>` : ''}
        ${distText ? `<div class="finder-card__dist">📍 ${distText} từ bạn</div>` : ''}
      </div>

      <div class="finder-card__body">
        <div class="finder-card__cp-label">${cpCount} trụ — ${total} đầu nối</div>
        <div class="finder-connector-list">
          ${_renderConnectorChips(station)}
        </div>
      </div>

      <div class="finder-card__footer">
        <span class="finder-card__meta">
          ${total > 0
            ? `<b style="color:var(--color-online)">${avail}</b>/${total} đầu nối rảnh`
            : 'Chưa có dữ liệu'}
        </span>
        <button class="btn btn--primary btn--sm finder-detail-btn"
          data-station-id="${station.id}" aria-label="Xem chi tiết trạm ${_esc(station.name)}">
          Chi tiết
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </button>
      </div>
    `;

    // Click whole card → open drawer
    card.addEventListener('click', (e) => {
      if (e.target.closest('.finder-detail-btn')) return; // handled separately
      _openDetail(station.id);
    });
    card.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); _openDetail(station.id); }
    });

    // Detail button
    card.querySelector('.finder-detail-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      _openDetail(station.id);
    });

    return card;
  }

  // ── Render grid ───────────────────────────────────────────────────────
  function _renderGrid(stations) {
    const grid = $grid();
    grid.innerHTML = '';
    if (!stations.length) {
      $empty().classList.remove('is-hidden');
      return;
    }
    $empty().classList.add('is-hidden');
    const frag = document.createDocumentFragment();
    stations.forEach(s => frag.appendChild(_renderCard(s)));
    grid.appendChild(frag);
  }

  // ── Filter & sort ─────────────────────────────────────────────────────
  function _applyFilter() {
    const q = ($search().value || '').toLowerCase().trim();
    const statusFlt = $statusFlt().value;
    const sortKey = $sort().value;

    _filtered = _stations.filter(s => {
      // Text search
      if (q) {
        const hay = `${s.name} ${s.address || ''}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      // Status filter
      if (statusFlt === 'available' && _countAvailable(s) === 0) return false;
      if (statusFlt === 'charging') {
        const hasCharging = (s.charge_points || []).some(cp =>
          (cp.connectors || []).some(c => c.status === 'charging'));
        if (!hasCharging) return false;
      }
      return true;
    });

    // Sort
    _filtered.sort((a, b) => {
      if (sortKey === 'name_asc') return a.name.localeCompare(b.name, 'vi');
      if (sortKey === 'available_desc') return _countAvailable(b) - _countAvailable(a);
      if (sortKey === 'distance_asc') {
        const da = _dist(_userLat, _userLng, a.latitude, a.longitude);
        const db = _dist(_userLat, _userLng, b.latitude, b.longitude);
        return da - db;
      }
      return 0;
    });

    _renderGrid(_filtered);
    if (_viewMode === 'map') _updateMapMarkers(_filtered);
  }

  // ── Detail drawer ─────────────────────────────────────────────────────
  function _openDetail(stationId) {
    const s = _stations.find(x => x.id === stationId);
    if (!s) return;
    _activeStationId = stationId;

    $drawerTitle().textContent = s.name;
    $drawerAddr().textContent = s.address || '';
    $backdrop().classList.remove('is-hidden');
    document.body.style.overflow = 'hidden';
    _renderDrawerBody(s);
  }

  function _closeDetail() {
    $backdrop().classList.add('is-hidden');
    document.body.style.overflow = '';
    _activeStationId = null;
  }

  function _renderDrawerBody(station) {
    const avail = _countAvailable(station);
    const total = _countTotal(station);
    const distKm = _dist(_userLat, _userLng, station.latitude, station.longitude);
    const distText = _fmtDist(distKm);

    let cpHtml = '';
    (station.charge_points || []).forEach(cp => {
      const connHtml = (cp.connectors || []).map(c => {
        const cls = _connectorClass(c.status);
        const label = STATUS_LABEL[(c.status || 'unknown').toLowerCase()] || c.status;
        return `
          <div class="finder-detail-connector">
            <span class="finder-detail-connector__name">Đầu nối #${c.connector_id}</span>
            <span class="finder-connector-chip ${cls}">
              <span class="connector-dot" aria-hidden="true"></span> ${label}
            </span>
          </div>`;
      }).join('');

      cpHtml += `
        <div class="finder-detail-cp">
          <div class="finder-detail-cp__header">
            <span class="finder-detail-cp__code">${_esc(cp.code)}</span>
            <span class="badge ${cp.status === 'online' ? 'badge--available' : 'badge--offline'}">
              ${cp.status === 'online' ? 'Online' : 'Offline'}
            </span>
          </div>
          ${connHtml || '<div style="padding:var(--space-3) var(--space-4);font-size:var(--font-size-xs);color:var(--color-text-muted);">Chưa có đầu nối</div>'}
        </div>`;
    });

    if (!cpHtml) {
      cpHtml = '<p style="font-size:var(--font-size-sm);color:var(--color-text-secondary);">Trạm chưa có trụ sạc nào.</p>';
    }

    $drawerBody().innerHTML = `
      <!-- Summary -->
      <div style="display:flex;gap:var(--space-3);margin-bottom:var(--space-5);flex-wrap:wrap;">
        <div class="finder-stat finder-stat--available" style="flex:1;min-width:120px;padding:var(--space-3);">
          <div>
            <div class="finder-stat__value">${avail}</div>
            <div class="finder-stat__label">Đầu nối rảnh</div>
          </div>
        </div>
        <div class="finder-stat finder-stat--station" style="flex:1;min-width:120px;padding:var(--space-3);">
          <div>
            <div class="finder-stat__value">${total}</div>
            <div class="finder-stat__label">Tổng đầu nối</div>
          </div>
        </div>
        ${distText ? `
        <div class="finder-stat finder-stat--charging" style="flex:1;min-width:120px;padding:var(--space-3);">
          <div>
            <div class="finder-stat__value">${distText}</div>
            <div class="finder-stat__label">Khoảng cách</div>
          </div>
        </div>` : ''}
      </div>

      <!-- Charge points -->
      <div class="finder-detail-section">
        <div class="finder-detail-section-title">Trụ sạc & đầu nối</div>
        ${cpHtml}
      </div>

      <!-- Map mini if has coordinates -->
      ${station.latitude && station.longitude ? `
      <div class="finder-detail-section">
        <div class="finder-detail-section-title">Vị trí trạm</div>
        <div id="detail-mini-map" style="height:180px;border-radius:var(--radius-md);overflow:hidden;border:1px solid var(--color-border);">
        </div>
        <a href="https://maps.google.com/?q=${station.latitude},${station.longitude}"
          target="_blank" rel="noopener noreferrer"
          class="btn btn--secondary btn--sm" style="margin-top:var(--space-3);">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
          </svg>
          Mở Google Maps
        </a>
      </div>` : ''}

      <!-- Start charging CTA (chỉ khi có đầu nối rảnh) -->
      ${avail > 0 ? `
      <div class="finder-detail-section">
        <a href="/monitoring" class="btn btn--primary finder-start-btn" id="finder-go-charge">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
          </svg>
          Bắt đầu sạc tại đây
        </a>
      </div>` : `
      <div class="finder-detail-section">
        <p class="form-hint" style="text-align:center;padding:var(--space-3);background:var(--color-surface-alt);border-radius:var(--radius-md);">
          ⏳ Trạm hiện không có đầu nối rảnh. Vui lòng thử lại sau hoặc chọn trạm khác.
        </p>
      </div>`}
    `;

    // Init mini-map in drawer
    if (station.latitude && station.longitude && window.L) {
      setTimeout(() => {
        const miniMap = L.map('detail-mini-map', { zoomControl: false, attributionControl: false })
          .setView([station.latitude, station.longitude], 15);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(miniMap);
        L.marker([station.latitude, station.longitude])
          .addTo(miniMap)
          .bindPopup(`<b>${_esc(station.name)}</b>`)
          .openPopup();
      }, 100);
    }
  }

  // ── Map view (SCRUM-242) ───────────────────────────────────────────────
  function _initMap() {
    if (_leafletMap || !window.L) return;
    const center = _userLat ? [_userLat, _userLng] : [16.047, 108.206]; // Đà Nẵng default
    _leafletMap = L.map('finder-map').setView(center, 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap'
    }).addTo(_leafletMap);
  }

  function _markerColor(station) {
    const avail = _countAvailable(station);
    const total = _countTotal(station);
    if (total === 0) return '#8b8b8b';
    if (avail === 0) return '#3b82f6';
    return '#22c55e';
  }

  function _updateMapMarkers(stations) {
    if (!_leafletMap) return;
    // Remove old
    Object.values(_mapMarkers).forEach(m => m.remove());
    _mapMarkers = {};

    stations.forEach(s => {
      if (!s.latitude || !s.longitude) return;
      const avail = _countAvailable(s);
      const total = _countTotal(s);
      const color = _markerColor(s);
      const icon = L.divIcon({
        html: `<div style="width:28px;height:28px;border-radius:50%;background:${color};border:3px solid white;box-shadow:0 2px 8px rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;color:white;">${avail}</div>`,
        className: '',
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      });
      const m = L.marker([s.latitude, s.longitude], { icon })
        .addTo(_leafletMap)
        .bindPopup(`
          <div class="finder-map-popup">
            <div class="finder-map-popup__name">${_esc(s.name)}</div>
            <div class="finder-map-popup__addr">${_esc(s.address || '')}</div>
            <div style="font-size:12px;font-weight:700;color:${color};">${avail}/${total} đầu nối rảnh</div>
            <button onclick="StationFinder.openDetail(${s.id})" style="margin-top:8px;padding:4px 10px;background:${color};color:white;border:none;border-radius:6px;cursor:pointer;font-size:12px;">Xem chi tiết</button>
          </div>`, { maxWidth: 220 });
      _mapMarkers[s.id] = m;
    });
  }

  // ── SSE realtime updates ───────────────────────────────────────────────
  function _initSSE() {
    SseClient.connect('/api/sse');

    SseClient.on('_connected', () => {
      const ind = $sseInd();
      if (ind) { ind.className = 'sse-indicator connected'; $sseLabel().textContent = 'Thời gian thực'; }
    });
    SseClient.on('_error', () => {
      const ind = $sseInd();
      if (ind) { ind.className = 'sse-indicator error'; $sseLabel().textContent = 'Mất kết nối'; }
    });

    SseClient.on('status_update', (payload) => {
      // payload: { station_id, charge_points: [{code, status, connectors:[{connector_id, status}]}] }
      const { station_id, charge_points } = payload;
      const idx = _stations.findIndex(s => s.id === station_id);
      if (idx === -1) return;

      // Merge connector statuses
      _stations[idx].charge_points = charge_points;

      // Re-render the matching card in grid
      const card = $grid().querySelector(`[data-station-id="${station_id}"]`);
      if (card) {
        const newCard = _renderCard(_stations[idx]);
        card.replaceWith(newCard);
      }

      // Update map marker
      if (_leafletMap && _mapMarkers[station_id]) {
        _mapMarkers[station_id].remove();
        delete _mapMarkers[station_id];
        _updateMapMarkers([_stations[idx]]);
      }

      // Update stats
      _renderStats(_stations);

      // Update open drawer
      if (_activeStationId === station_id) {
        _renderDrawerBody(_stations[idx]);
      }
    });
  }

  // ── Load data ─────────────────────────────────────────────────────────
  async function _load() {
    try {
      const data = await ApiClient.getMonitoringTree();
      _stations = data;
      $loading().style.display = 'none';
      _renderStats(data);
      _applyFilter();
    } catch (err) {
      $loading().innerHTML = `
        <p style="color:var(--color-fault);">Không tải được dữ liệu trạm. ${err.message || ''}</p>
        <button class="btn btn--secondary btn--sm" onclick="StationFinder.reload()" style="margin-top:var(--space-3);">Thử lại</button>
      `;
    }
  }

  // ── Geolocation ───────────────────────────────────────────────────────
  function _requestLocation() {
    if (!navigator.geolocation) {
      _showToast('Trình duyệt không hỗ trợ định vị GPS', 'warning');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        _userLat = pos.coords.latitude;
        _userLng = pos.coords.longitude;
        const distOpt = document.getElementById('sort-distance-opt');
        if (distOpt) distOpt.disabled = false;
        $sort().value = 'distance_asc';
        _applyFilter();
        if (_leafletMap) _leafletMap.setView([_userLat, _userLng], 13);
        _showToast('Đã bật định vị. Đang sắp xếp theo khoảng cách.', 'success');
      },
      () => _showToast('Không thể lấy vị trí của bạn. Vui lòng cho phép trong trình duyệt.', 'warning')
    );
  }

  // ── Toast helper ──────────────────────────────────────────────────────
  function _showToast(msg, type = 'info') {
    const tc = document.getElementById('toast-container');
    if (!tc) return;
    const t = document.createElement('div');
    t.className = `toast toast--${type}`;
    t.setAttribute('role', 'alert');
    t.textContent = msg;
    tc.appendChild(t);
    setTimeout(() => t.remove(), 4000);
  }

  // ── Utility ───────────────────────────────────────────────────────────
  function _esc(str) {
    return (str || '').replace(/[&<>"']/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  // ── View toggle ───────────────────────────────────────────────────────
  function _setView(mode) {
    _viewMode = mode;
    const cardsBtn = document.getElementById('view-cards');
    const mapBtn   = document.getElementById('view-map-btn');
    if (mode === 'map') {
      $cardsView().style.display = 'none';
      $mapView().classList.remove('is-hidden');
      cardsBtn.classList.remove('is-active'); cardsBtn.setAttribute('aria-pressed', 'false');
      mapBtn.classList.add('is-active');      mapBtn.setAttribute('aria-pressed', 'true');
      // Load Leaflet dynamically
      if (!window.L) {
        _loadLeaflet().then(() => { _initMap(); _updateMapMarkers(_filtered); });
      } else {
        _initMap();
        _updateMapMarkers(_filtered);
      }
    } else {
      $cardsView().style.display = '';
      $mapView().classList.add('is-hidden');
      mapBtn.classList.remove('is-active');  mapBtn.setAttribute('aria-pressed', 'false');
      cardsBtn.classList.add('is-active');   cardsBtn.setAttribute('aria-pressed', 'true');
    }
  }

  function _loadLeaflet() {
    return new Promise((resolve) => {
      if (window.L) { resolve(); return; }
      const css = document.createElement('link');
      css.rel = 'stylesheet';
      css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      document.head.appendChild(css);
      const js = document.createElement('script');
      js.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
      js.onload = resolve;
      document.head.appendChild(js);
    });
  }

  // ── Init ──────────────────────────────────────────────────────────────
  function init() {
    // Filter/sort listeners
    $search().addEventListener('input', () => _applyFilter());
    $statusFlt().addEventListener('change', () => _applyFilter());
    $sort().addEventListener('change', () => _applyFilter());

    // Location button
    document.getElementById('btn-use-location').addEventListener('click', _requestLocation);

    // View toggle
    document.getElementById('view-cards').addEventListener('click', () => _setView('cards'));
    document.getElementById('view-map-btn').addEventListener('click', () => _setView('map'));

    // Drawer close
    document.getElementById('finder-detail-close').addEventListener('click', _closeDetail);
    $backdrop().addEventListener('click', (e) => {
      if (e.target === $backdrop()) _closeDetail();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') _closeDetail();
    });

    // Clear filter
    document.getElementById('btn-clear-filter').addEventListener('click', () => {
      $search().value = '';
      $statusFlt().value = '';
      $sort().value = 'available_desc';
      _applyFilter();
    });

    _initSSE();
    _load();
  }

  return {
    init,
    reload: _load,
    openDetail: _openDetail,
  };
})();

document.addEventListener('DOMContentLoaded', () => StationFinder.init());
window.StationFinder = StationFinder;
