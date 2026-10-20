/**
 * pages/alerts.js — SCRUM-90: Cảnh báo trụ ngoại tuyến / báo lỗi liên tục
 *
 * Acceptance criteria:
 *  AC1 — Danh sách trụ đang offline > ngưỡng (30p mặc định) với badge mức độ
 *  AC2 — Danh sách trụ đang Faulted liên tục với mã lỗi OCPP
 *  AC3 — Thời gian kéo dài tính real-time (cập nhật mỗi giây khi tab active)
 *  AC4 — SSE: khi trụ phục hồi cảnh báo tự động biến mất; trụ mới lỗi có banner
 *  AC5 — Filter: loại (offline/faulted), mức độ (critical/warning/info), search
 *  AC6 — Bấm "Xác nhận đã biết" ghi audit log (POST /api/alerts/{id}/acknowledge)
 *  AC7 — Tự động poll mỗi 30 giây; stop poll khi tab ẩn
 */
(function () {
  'use strict';

  /* ── Cấu hình ─────────────────────────────────────────────────────────── */
  const POLL_INTERVAL_MS   = 30_000;  // 30 giây
  const OFFLINE_WARN_MIN   = 30;      // phút — ngưỡng cảnh báo offline
  const OFFLINE_CRIT_MIN   = 120;     // phút — ngưỡng nghiêm trọng
  const PAGE_SIZE          = 20;

  /* ── State ───────────────────────────────────────────────────────────────*/
  let _allAlerts    = [];   // toàn bộ sau filter/sort
  let _page         = 1;
  let _pollTimer    = null;
  let _pendingAckId = null;
  let _pendingAckCode = null;
  let _tickTimer    = null;   // cập nhật duration mỗi giây
  let _prevCount    = null;   // phát hiện cảnh báo mới qua SSE/poll

  /* ── Helpers ──────────────────────────────────────────────────────────── */
  function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  }

  function fmtDatetime(iso) {
    if (!iso) return '—';
    const d = new Date((/Z|[+-]\d{2}:\d{2}$/i).test(iso) ? iso : iso + 'Z');
    return isNaN(d) ? '—' : d.toLocaleString('vi-VN', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  }

  /** Tính số phút từ ISO string đến bây giờ */
  function minutesSince(iso) {
    if (!iso) return 0;
    const d = new Date((/Z|[+-]\d{2}:\d{2}$/i).test(iso) ? iso : iso + 'Z');
    return isNaN(d) ? 0 : Math.floor((Date.now() - d.getTime()) / 60_000);
  }

  /** Format số phút thành chuỗi dễ đọc */
  function fmtDuration(mins) {
    if (mins < 1)   return '< 1 phút';
    if (mins < 60)  return `${mins} phút`;
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return m ? `${h}h ${m}p` : `${h}h`;
  }

  /** Tính mức độ dựa trên loại và thời gian */
  function getSeverity(alert) {
    if (alert.severity === 'critical' || alert.severity === 'warning') return alert.severity;
    if (alert.alert_type === 'faulted') {
      const mins = minutesSince(alert.started_at);
      return mins >= OFFLINE_CRIT_MIN ? 'critical' : mins >= OFFLINE_WARN_MIN ? 'warning' : 'info';
    }
    // offline
    const mins = minutesSince(alert.started_at);
    if (mins >= OFFLINE_CRIT_MIN) return 'critical';
    if (mins >= OFFLINE_WARN_MIN) return 'warning';
    return 'info';
  }

  const SEV_LABEL = { critical: 'Nghiêm trọng', warning: 'Cảnh báo', info: 'Thông tin' };
  const SEV_CLASS = { critical: 'severity-badge--critical severity-badge--pulse', warning: 'severity-badge--warning', info: 'severity-badge--info' };
  const SEV_ICON  = {
    critical: `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"
      stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
      <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
    warning: `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
      stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/>
      <line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
    info: `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
      stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/>
      <line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
  };

  /* ── API calls ─────────────────────────────────────────────────────────── */
  async function fetchAlerts() {
    try {
      const first = await ApiClient.listOperationalAlerts({ skip: 0, limit: 100 });
      const items = [...(first.items || [])];
      for (let skip = items.length; skip < first.total; skip += 100) {
        const page = await ApiClient.listOperationalAlerts({ skip, limit: 100 });
        items.push(...(page.items || []));
      }
      return items.map(item => ({
        ...item,
        alert_type: item.alert_type === 'connector_error' ? 'faulted' : item.alert_type,
        started_at: item.triggered_at,
        station_name: item.station_name || item.charge_point_code,
        error_code: item.error_code || (item.error_count ? `${item.error_count} lỗi liên tiếp` : null),
        info: item.message,
        acknowledged_by: item.status === 'resolved'
          ? (item.resolved_by_id ? `Tài khoản #${item.resolved_by_id}` : 'Đã xử lý tự động')
          : null,
      }));
    } catch (error) {
      showToast(error?.message || 'Không tải được cảnh báo vận hành.', 'error');
      return null;
    }
  }

  async function acknowledgeAlert(id) {
    return ApiClient.acknowledgeAlert(id, 'Đã xác nhận xử lý từ trang cảnh báo vận hành');
  }

  /* ── Load & render ─────────────────────────────────────────────────────── */
  async function load() {
    const raw = await fetchAlerts();
    if (raw === null) {
      document.getElementById('alerts-tbody').innerHTML = '<tr><td colspan="7"><div class="empty-state"><div class="empty-state__title">Không tải được cảnh báo</div><div class="empty-state__desc">Kiểm tra kết nối rồi bấm Làm mới.</div></div></td></tr>';
      document.getElementById('stat-total').textContent = '—';
      document.getElementById('alerts-result-count').textContent = 'Không có dữ liệu';
      return;
    }
    const prevCount = _prevCount;
    const activeAlerts = raw.filter(alert => alert.status === 'active');

    // apply filters
    const typeF   = document.getElementById('alert-type-filter').value;
    const sevF    = document.getElementById('alert-severity-filter').value;
    const sortF   = document.getElementById('alert-sort-filter').value;
    const search  = (document.getElementById('alert-search').value || '').toLowerCase().trim();

    let list = activeAlerts.map(a => ({ ...a, _sev: getSeverity(a), _mins: minutesSince(a.started_at) }));

    if (typeF)   list = list.filter(a => a.alert_type === typeF);
    if (sevF)    list = list.filter(a => a._sev === sevF);
    if (search)  list = list.filter(a =>
      (a.charge_point_code || '').toLowerCase().includes(search) ||
      (a.station_name || '').toLowerCase().includes(search));

    // sort
    if (sortF === 'duration_desc') list.sort((a, b) => b._mins - a._mins);
    else if (sortF === 'duration_asc') list.sort((a, b) => a._mins - b._mins);
    else list.sort((a, b) => (a.station_name || '').localeCompare(b.station_name || '', 'vi'));

    _allAlerts = list;
    _prevCount = activeAlerts.length;

    // detect new alerts via SSE
    if (prevCount !== null && activeAlerts.length > prevCount) {
      showNewBanner(activeAlerts.length - prevCount);
    }

    updateStats(raw);
    renderTable();
    renderPagination();
    updateRefreshTime();
    startTickTimer();
  }

  function updateStats(raw) {
    const active = raw.filter(a => a.status === 'active');
    const offline  = active.filter(a => a.alert_type === 'offline').length;
    const faulted  = active.filter(a => a.alert_type === 'faulted').length;
    const today = new Date().toISOString().slice(0, 10);
    const resolved = raw.filter(a => a.status === 'resolved' && a.resolved_at?.slice(0, 10) === today).length;
    document.getElementById('stat-total').textContent   = active.length;
    document.getElementById('stat-offline').textContent = offline;
    document.getElementById('stat-faulted').textContent = faulted;
    document.getElementById('stat-resolved').textContent = resolved;
  }

  function renderTable() {
    const tbody = document.getElementById('alerts-tbody');
    const start = (_page - 1) * PAGE_SIZE;
    const slice = _allAlerts.slice(start, start + PAGE_SIZE);
    document.getElementById('alerts-result-count').textContent = `${_allAlerts.length} cảnh báo`;

    if (!slice.length) {
      tbody.innerHTML = `<tr><td colspan="7">
        <div class="empty-state">
          <div class="empty-state__icon">✅</div>
          <div class="empty-state__title">Không có cảnh báo nào</div>
          <div class="empty-state__desc">Tất cả trụ đang hoạt động bình thường</div>
        </div></td></tr>`;
      return;
    }

    tbody.innerHTML = slice.map(a => {
      const sev   = a._sev;
      const mins  = a._mins;
      const barPct = Math.min(100, Math.round((mins / (OFFLINE_CRIT_MIN * 2)) * 100));
      const durClass = sev === 'critical' ? 'duration-value--critical' : sev === 'warning' ? 'duration-value--warning' : '';
      const barCls   = `duration-bar--${sev}`;

      const typeLabel = a.alert_type === 'offline' ? 'Ngoại tuyến' : 'Báo lỗi';
      const typeCls   = a.alert_type === 'offline' ? 'alert-type-badge--offline' : 'alert-type-badge--faulted';
      const typeIcon  = a.alert_type === 'offline'
        ? `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <line x1="1" y1="1" x2="23" y2="23"/><path d="M16.72 11.06A10.94 10.94 0 0119 12.55"/>
            <path d="M5 12.55a10.94 10.94 0 015.17-2.39"/><path d="M10.71 5.05A16 16 0 0122.56 9"/>
            <path d="M1.42 9a15.91 15.91 0 014.7-2.88"/><path d="M8.53 16.11a6 6 0 016.95 0"/>
            <line x1="12" y1="20" x2="12.01" y2="20"/></svg>`
        : `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`;

      const errCode = a.error_code && a.error_code !== 'NoError'
        ? `<code class="error-code-chip">${esc(a.error_code)}</code>`
        : `<span class="error-code-chip error-code-chip--no-error">—</span>`;

      const ackBtn = a.acknowledged_by
        ? `<span style="font-size:var(--font-size-xs);color:var(--color-text-secondary);">✓ Đã biết</span>`
        : `<button class="btn btn--ghost btn--sm" data-ack-id="${esc(a.id)}" data-ack-code="${esc(a.charge_point_code)}" type="button">Đã biết</button>`;

      return `<tr class="${sev === 'critical' ? 'is-critical' : ''}" data-alert-id="${esc(a.id)}">
        <td><span class="severity-badge ${SEV_CLASS[sev]}">${SEV_ICON[sev]}${SEV_LABEL[sev]}</span></td>
        <td><span class="alert-type-badge ${typeCls}">${typeIcon} ${typeLabel}</span></td>
        <td>
          <div style="font-weight:700;font-size:var(--font-size-sm);">${esc(a.station_name || '—')}</div>
          <code style="font-size:11px;color:var(--color-text-secondary);">${esc(a.charge_point_code || '—')}</code>
        </td>
        <td style="white-space:nowrap;font-size:var(--font-size-xs);">${fmtDatetime(a.started_at)}</td>
        <td>
          <div class="duration-cell">
            <span class="duration-value ${durClass}" data-since="${esc(a.started_at)}">${fmtDuration(mins)}</span>
            <div class="duration-bar-wrap">
              <div class="duration-bar ${barCls}" style="width:${barPct}%"></div>
            </div>
          </div>
        </td>
        <td>${errCode}</td>
        <td class="text-right">
          <div style="display:flex;gap:var(--space-2);justify-content:flex-end;align-items:center;">
            <button class="btn btn--secondary btn--sm btn-detail" data-alert-id="${esc(a.id)}" type="button">Chi tiết</button>
            ${ackBtn}
          </div>
        </td>
      </tr>`;
    }).join('');

    // bind detail buttons
    tbody.querySelectorAll('.btn-detail').forEach(btn => {
      btn.addEventListener('click', () => openDetailModal(btn.dataset.alertId));
    });

    // bind ack buttons
    tbody.querySelectorAll('[data-ack-id]').forEach(btn => {
      btn.addEventListener('click', () => openAckModal(btn.dataset.ackId, btn.dataset.ackCode));
    });
  }

  function renderPagination() {
    const total = _allAlerts.length;
    const pages = Math.ceil(total / PAGE_SIZE);
    const prevBtn = document.getElementById('alerts-prev');
    const nextBtn = document.getElementById('alerts-next');
    const pagesEl = document.getElementById('alerts-pages');
    const labelEl = document.getElementById('alerts-page-label');

    prevBtn.disabled = _page <= 1;
    nextBtn.disabled = _page >= pages;
    labelEl.textContent = pages > 1 ? `Trang ${_page} / ${pages}` : `${total} cảnh báo`;

    pagesEl.innerHTML = '';
    if (pages <= 1) return;
    const start = Math.max(1, _page - 2);
    const end   = Math.min(pages, _page + 2);
    for (let i = start; i <= end; i++) {
      const b = document.createElement('button');
      b.className = 'pagination__btn' + (i === _page ? ' is-active' : '');
      b.textContent = i;
      b.setAttribute('aria-label', `Trang ${i}`);
      if (i === _page) b.setAttribute('aria-current', 'page');
      b.addEventListener('click', () => { _page = i; renderTable(); renderPagination(); });
      pagesEl.appendChild(b);
    }
  }

  /* ── Live duration tick ─────────────────────────────────────────────────── */
  function startTickTimer() {
    clearInterval(_tickTimer);
    _tickTimer = setInterval(() => {
      document.querySelectorAll('[data-since]').forEach(el => {
        const mins = minutesSince(el.dataset.since);
        el.textContent = fmtDuration(mins);
        el.className = 'duration-value' +
          (mins >= OFFLINE_CRIT_MIN ? ' duration-value--critical'
           : mins >= OFFLINE_WARN_MIN ? ' duration-value--warning' : '');
      });
    }, 10_000);  // cập nhật mỗi 10 giây
  }

  /* ── New-alert banner ───────────────────────────────────────────────────── */
  function showNewBanner(count) {
    const banner = document.getElementById('alert-new-banner');
    document.getElementById('alert-new-text').textContent =
      `Có ${count} cảnh báo mới xuất hiện!`;
    banner.classList.remove('is-hidden');
  }

  function hideNewBanner() {
    document.getElementById('alert-new-banner').classList.add('is-hidden');
  }

  /* ── Last refresh timestamp ─────────────────────────────────────────────── */
  function updateRefreshTime() {
    const el = document.getElementById('alerts-last-refresh');
    const now = new Date();
    el.textContent = 'Làm mới lúc ' + now.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  /* ── Detail modal ─────────────────────────────────────────────────────── */
  function openDetailModal(id) {
    const a = _allAlerts.find(x => String(x.id) === String(id));
    if (!a) return;

    const sev = getSeverity(a);
    const body = document.getElementById('alert-detail-body');
    body.innerHTML = `
      <div class="alert-detail-item">
        <span class="alert-detail-label">Loại cảnh báo</span>
        <span class="alert-detail-value">
          <span class="alert-type-badge ${a.alert_type === 'offline' ? 'alert-type-badge--offline' : 'alert-type-badge--faulted'}">
            ${a.alert_type === 'offline' ? 'Ngoại tuyến' : 'Báo lỗi'}
          </span>
        </span>
      </div>
      <div class="alert-detail-item">
        <span class="alert-detail-label">Mức độ</span>
        <span class="alert-detail-value">
          <span class="severity-badge ${SEV_CLASS[sev]}">${SEV_LABEL[sev]}</span>
        </span>
      </div>
      <div class="alert-detail-item">
        <span class="alert-detail-label">Trạm sạc</span>
        <span class="alert-detail-value">${esc(a.station_name || '—')}</span>
      </div>
      <div class="alert-detail-item">
        <span class="alert-detail-label">Mã trụ</span>
        <span class="alert-detail-value"><code>${esc(a.charge_point_code || '—')}</code></span>
      </div>
      <div class="alert-detail-item">
        <span class="alert-detail-label">Thời điểm phát hiện</span>
        <span class="alert-detail-value">${fmtDatetime(a.started_at)}</span>
      </div>
      <div class="alert-detail-item">
        <span class="alert-detail-label">Thời gian kéo dài</span>
        <span class="alert-detail-value" style="font-weight:700;">${fmtDuration(a._mins)}</span>
      </div>
      ${a.error_code && a.error_code !== 'NoError' ? `
      <div class="alert-detail-item">
        <span class="alert-detail-label">Mã lỗi OCPP</span>
        <span class="alert-detail-value"><code class="error-code-chip">${esc(a.error_code)}</code></span>
      </div>
      <div class="alert-detail-item">
        <span class="alert-detail-label">Mã lỗi nhà sản xuất</span>
        <span class="alert-detail-value">${esc(a.vendor_error_code || '—')}</span>
      </div>` : ''}
      ${a.info ? `
      <div class="alert-detail-item alert-detail-item--full">
        <span class="alert-detail-label">Thông tin bổ sung</span>
        <span class="alert-detail-value" style="white-space:pre-wrap;">${esc(a.info)}</span>
      </div>` : ''}
      ${a.acknowledged_by ? `
      <div class="alert-detail-item alert-detail-item--full">
        <span class="alert-detail-label">Đã xác nhận bởi</span>
        <span class="alert-detail-value" style="color:var(--color-online);">✓ ${esc(a.acknowledged_by)}</span>
      </div>` : ''}
      <div class="alert-detail-timeline">
        <div class="alert-detail-timeline__title">Dòng thời gian</div>
        <div class="timeline-event">
          <span class="timeline-dot timeline-dot--bad"></span>
          <div>
            <div style="font-weight:600;">${a.alert_type === 'offline' ? 'Trụ mất kết nối' : 'Trụ báo lỗi'}</div>
            <div style="color:var(--color-text-secondary);">${fmtDatetime(a.started_at)}</div>
          </div>
        </div>
        <div class="timeline-event">
          <span class="timeline-dot timeline-dot--warn"></span>
          <div>
            <div style="font-weight:600;">Kéo dài ${fmtDuration(a._mins)}</div>
            <div style="color:var(--color-text-secondary);">Chưa khôi phục</div>
          </div>
        </div>
      </div>`;

    const modal = document.getElementById('alert-detail-modal');
    modal.classList.remove('is-hidden');
    modal.setAttribute('aria-hidden', 'false');
  }

  function closeDetailModal() {
    const modal = document.getElementById('alert-detail-modal');
    modal.classList.add('is-hidden');
    modal.setAttribute('aria-hidden', 'true');
  }

  /* ── Acknowledge modal ────────────────────────────────────────────────── */
  function openAckModal(id, code) {
    _pendingAckId   = id;
    _pendingAckCode = code;
    document.getElementById('ack-cp-code').textContent = code;
    const modal = document.getElementById('modal-ack-dialog');
    modal.classList.remove('is-hidden');
    modal.setAttribute('aria-hidden', 'false');
  }

  function closeAckModal() {
    const modal = document.getElementById('modal-ack-dialog');
    modal.classList.add('is-hidden');
    modal.setAttribute('aria-hidden', 'true');
    _pendingAckId = _pendingAckCode = null;
  }

  /* ── SSE integration ──────────────────────────────────────────────────── */
  function setupSse() {
    const ind   = document.getElementById('alerts-sse-indicator');
    const label = document.getElementById('alerts-sse-label');

    function setConnected() {
      ind.className = 'sse-indicator connected';
      label.textContent = 'Trực tiếp';
    }
    function setDisconnected() {
      ind.className = 'sse-indicator error';
      label.textContent = 'Mất kết nối';
    }
    function setConnecting() {
      ind.className = 'sse-indicator';
      label.textContent = 'Đang kết nối...';
    }

    if (typeof SseClient !== 'undefined') {
      SseClient.connect('/api/monitoring/sse');
      SseClient.on('status_update', () => load());
      SseClient.on('_connected', setConnected);
      SseClient.on('_error', setDisconnected);
      setConnected();
    } else {
      setDisconnected();
    }

    // listen for SSE open/close via custom events if SseClient dispatches them
    document.addEventListener('sse:open',  setConnected);
    document.addEventListener('sse:error', setDisconnected);
    document.addEventListener('sse:close', setConnecting);
  }

  /* ── Auto-poll ────────────────────────────────────────────────────────── */
  function startPoll() {
    clearInterval(_pollTimer);
    _pollTimer = setInterval(() => {
      if (!document.hidden) load();
    }, POLL_INTERVAL_MS);
  }

  /* ── DOMContentLoaded ────────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', () => {
    // Initial load
    load();
    setupSse();
    startPoll();

    // Stop tick timer when hidden
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        clearInterval(_tickTimer);
        clearInterval(_pollTimer);
      } else {
        load();
        startPoll();
      }
    });

    // Filters
    document.getElementById('alert-type-filter').addEventListener('change',     () => { _page = 1; load(); });
    document.getElementById('alert-severity-filter').addEventListener('change', () => { _page = 1; load(); });
    document.getElementById('alert-sort-filter').addEventListener('change',     () => { _page = 1; load(); });
    document.getElementById('alert-search').addEventListener('input', () => { _page = 1; renderTable(); renderPagination(); });

    // Refresh btn
    document.getElementById('btn-refresh-alerts').addEventListener('click', load);

    // New-alert banner
    document.getElementById('btn-reload-banner').addEventListener('click',  () => { hideNewBanner(); load(); });
    document.getElementById('btn-close-banner').addEventListener('click',   hideNewBanner);

    // Pagination
    document.getElementById('alerts-prev').addEventListener('click', () => { if (_page > 1) { _page--; renderTable(); renderPagination(); } });
    document.getElementById('alerts-next').addEventListener('click', () => {
      const pages = Math.ceil(_allAlerts.length / PAGE_SIZE);
      if (_page < pages) { _page++; renderTable(); renderPagination(); }
    });

    // Detail modal
    document.getElementById('alert-detail-close').addEventListener('click',   closeDetailModal);
    document.getElementById('alert-detail-ok').addEventListener('click',      closeDetailModal);
    document.getElementById('alert-detail-backdrop').addEventListener('click', closeDetailModal);

    // Ack modal
    document.getElementById('modal-ack-close').addEventListener('click',   closeAckModal);
    document.getElementById('modal-ack-cancel').addEventListener('click',  closeAckModal);
    document.getElementById('modal-ack-backdrop').addEventListener('click', closeAckModal);
    document.getElementById('modal-ack-confirm').addEventListener('click', async () => {
      if (!_pendingAckId) return;
      const btn = document.getElementById('modal-ack-confirm');
      btn.disabled = true;
      try {
        await acknowledgeAlert(_pendingAckId);
        showToast(`Đã ghi nhận xác nhận cho trụ ${_pendingAckCode}`, 'success');
        closeAckModal();
        await load();
      } catch (err) {
        showToast(err?.message || 'Lỗi xác nhận', 'error');
        btn.disabled = false;
      }
    });

    // Test chips
    // ESC to close modals
    document.addEventListener('keydown', e => {
      if (e.key !== 'Escape') return;
      if (!document.getElementById('alert-detail-modal').classList.contains('is-hidden')) closeDetailModal();
      if (!document.getElementById('modal-ack-dialog').classList.contains('is-hidden')) closeAckModal();
    });
  });
})();
