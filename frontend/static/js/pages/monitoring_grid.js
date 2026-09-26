/**
 * pages/monitoring_grid.js — Lưới giám sát realtime với SSE
 */
(function () {
  'use strict';

  let _data     = [];
  let _viewMode = 'grid';  // 'grid' | 'list'

  const STATUS_LABEL = {
    available: 'Sẵn sàng', charging: 'Đang sạc',
    offline: 'Ngoại tuyến', fault: 'Lỗi', finishing: 'Kết thúc',
  };
  const STATUS_CLASS = {
    available: 'badge--available', charging: 'badge--charging',
    offline: 'badge--offline', fault: 'badge--fault', finishing: 'badge--finishing',
  };

  function escHtml(s) {
    return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  async function loadData() {
    try {
      const data = await ApiClient.getMonitoringTree();
      _data = Array.isArray(data) ? data : (data.stations || []);
      renderGrid();
      updateStats();
      document.getElementById('mon-loading')?.remove();
    } catch (e) {
      showToast('Không tải được dữ liệu giám sát', 'error');
    }
  }

  function getFiltered() {
    const search = (document.getElementById('mon-search')?.value || '').toLowerCase();
    const status = document.getElementById('mon-status-filter')?.value || '';
    return _data.filter(station => {
      const nameMatch = !search || station.name.toLowerCase().includes(search) || (station.address||'').toLowerCase().includes(search);
      const statusMatch = !status || (station.charge_points||[]).some(cp => cp.status === status);
      return nameMatch && statusMatch;
    });
  }

  function renderGrid() {
    const grid = document.getElementById('monitoring-grid');
    const filtered = getFiltered();
    const loading = document.getElementById('mon-loading');

    // Remove all cards but keep loading if present
    Array.from(grid.children).forEach(c => { if (c !== loading) c.remove(); });

    if (!filtered.length) {
      const el = document.createElement('div');
      el.className = 'empty-state';
      el.style.gridColumn = '1/-1';
      el.innerHTML = '<div class="empty-state__icon">🔌</div><div class="empty-state__title">Không có kết quả</div><div class="empty-state__desc">Thử thay đổi bộ lọc</div>';
      grid.appendChild(el);
      return;
    }

    filtered.forEach(station => {
      const card = createStationCard(station);
      grid.appendChild(card);
    });
  }

  function createStationCard(station) {
    const div = document.createElement('div');
    div.className = 'station-card';
    div.setAttribute('tabindex', '0');
    div.setAttribute('role', 'button');
    div.setAttribute('aria-label', `Trạm ${station.name}`);
    div.dataset.stationId = station.id;

    const stStatus = (station.charge_points||[]).every(cp => cp.status === 'offline') ? 'offline'
                   : (station.charge_points||[]).some(cp => cp.status === 'fault') ? 'fault' : 'online';

    div.innerHTML = `
      <div class="station-card__header">
        <div>
          <div class="station-card__name">${escHtml(station.name)}</div>
          <div class="station-card__addr">${escHtml(station.address||'')}</div>
        </div>
        <span class="badge ${STATUS_CLASS[stStatus]||'badge--neutral'}">${STATUS_LABEL[stStatus]||'Không rõ'}</span>
      </div>
      <div class="station-card__body">
        <div class="cp-grid">
          ${(station.charge_points||[]).map(cp => `
            <div class="cp-tile">
              <div class="cp-tile__code">${escHtml(cp.code)}</div>
              <span class="badge ${STATUS_CLASS[cp.status]||'badge--neutral'}">${STATUS_LABEL[cp.status]||'Không rõ'}</span>
            </div>`).join('')}
          ${!(station.charge_points||[]).length ? '<div style="color:var(--color-text-muted);font-size:var(--font-size-xs)">Chưa có trụ</div>' : ''}
        </div>
      </div>`;

    div.addEventListener('click', () => openDetail(station));
    div.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openDetail(station); } });
    return div;
  }

  function updateStats() {
    const cps = _data.flatMap(s => s.charge_points || []);
    document.getElementById('mon-total').textContent    = cps.length;
    document.getElementById('mon-charging').textContent = cps.filter(c => c.status === 'charging').length;
    document.getElementById('mon-offline').textContent  = cps.filter(c => c.status === 'offline').length;
    document.getElementById('mon-fault').textContent    = cps.filter(c => c.status === 'fault').length;
  }

  // ── Detail drawer ──
  function openDetail(station) {
    const backdrop = document.getElementById('detail-backdrop');
    const body     = document.getElementById('detail-body');
    document.getElementById('detail-title').textContent = station.name;
    body.innerHTML = `
      <p style="color:var(--color-text-secondary);font-size:var(--font-size-sm);margin-bottom:var(--space-4);">${escHtml(station.address||'')}</p>
      <div style="display:flex;flex-direction:column;gap:var(--space-3);">
        ${(station.charge_points||[]).map(cp => `
          <div style="background:var(--color-surface-alt);border:1px solid var(--color-border);border-radius:var(--radius-md);padding:var(--space-4);">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:var(--space-2);">
              <strong style="font-family:monospace;">${escHtml(cp.code)}</strong>
              <span class="badge ${STATUS_CLASS[cp.status]||'badge--neutral'}">${STATUS_LABEL[cp.status]||'Không rõ'}</span>
            </div>
            <div style="font-size:var(--font-size-xs);color:var(--color-text-secondary);">
              ${cp.vendor ? `Nhà SX: ${escHtml(cp.vendor)}` : ''}
              ${cp.model  ? ` | Model: ${escHtml(cp.model)}` : ''}
              ${cp.last_seen_at ? ` | Lần cuối: ${new Date(cp.last_seen_at).toLocaleString('vi-VN')}` : ''}
            </div>
          </div>`).join('')}
      </div>`;
    backdrop.classList.remove('is-hidden');
  }

  // ── SSE integration ──
  function connectSSE() {
    SseClient.connect('/api/monitoring/sse');
    const indicator = document.getElementById('sse-indicator');
    const label     = document.getElementById('sse-label');

    SseClient.on('_connected', () => {
      indicator.className = 'sse-indicator connected';
      label.textContent = 'Đang kết nối';
    });
    SseClient.on('_error', () => {
      indicator.className = 'sse-indicator error';
      label.textContent = 'Mất kết nối';
    });
    SseClient.on('status_update', (payload) => {
      // Update local data and re-render
      if (payload.station_id) {
        const s = _data.find(x => x.id === payload.station_id);
        if (s && payload.charge_points) s.charge_points = payload.charge_points;
        renderGrid();
        updateStats();
      }
    });
  }

  // ── Init ──
  document.addEventListener('DOMContentLoaded', () => {
    loadData();
    connectSSE();

    let deb;
    document.getElementById('mon-search')?.addEventListener('input', () => { clearTimeout(deb); deb = setTimeout(renderGrid, 250); });
    document.getElementById('mon-status-filter')?.addEventListener('change', renderGrid);
    document.getElementById('btn-refresh-monitoring')?.addEventListener('click', loadData);

    document.getElementById('view-grid')?.addEventListener('click', () => {
      _viewMode = 'grid';
      document.getElementById('monitoring-grid').classList.remove('list-view');
      document.getElementById('view-grid').classList.add('is-active');
      document.getElementById('view-grid').setAttribute('aria-pressed', 'true');
      document.getElementById('view-list').classList.remove('is-active');
      document.getElementById('view-list').setAttribute('aria-pressed', 'false');
    });
    document.getElementById('view-list')?.addEventListener('click', () => {
      _viewMode = 'list';
      document.getElementById('monitoring-grid').classList.add('list-view');
      document.getElementById('view-list').classList.add('is-active');
      document.getElementById('view-list').setAttribute('aria-pressed', 'true');
      document.getElementById('view-grid').classList.remove('is-active');
      document.getElementById('view-grid').setAttribute('aria-pressed', 'false');
    });

    document.getElementById('detail-close')?.addEventListener('click', () => document.getElementById('detail-backdrop').classList.add('is-hidden'));
    document.getElementById('detail-backdrop')?.addEventListener('click', e => { if (e.target === e.currentTarget) e.currentTarget.classList.add('is-hidden'); });
  });
})();
