/**
 * driver_session.js — SCRUM-98: Theo dõi phiên sạc đang chạy + nhận thông báo SSE
 * Author: Vy Hoàng Tú — Sprint 678
 *
 * API sử dụng:
 *   GET /api/sessions/current → phiên đang chạy hoặc 404
 *   SSE /api/monitoring/sse → event: session_update { session_id }
 *   GET /api/sessions/{id} → chi tiết phiên
 */

'use strict';

const DriverSession = (() => {
  const REMOTE_STOP_CONFIRM_TIMEOUT_MS = 120000;
  // ── State ────────────────────────────────────────────────────────────
  let _currentSession = null;   // phiên đang chạy
  let _durationTimer  = null;   // interval đếm thời gian
  let _sessionEndedId = null;   // ID phiên vừa kết thúc (để hiện overlay)
  let _remoteStopPending = false;
  let _remoteStopTimer = null;
  let _hasConnectedBefore = false;

  // ── DOM refs ─────────────────────────────────────────────────────────
  const $ = (id) => document.getElementById(id);

  // ── Utility ──────────────────────────────────────────────────────────
  function _esc(s) {
    return (s || '').replace(/[&<>"']/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function _fmtVnd(n) {
    if (n == null) return '—';
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(n);
  }

  function _fmtKwh(v) {
    if (v == null) return '—';
    return `${parseFloat(v).toFixed(2)} kWh`;
  }

  function _fmtDate(iso) {
    if (!iso) return '—';
    const date = _parseDate(iso);
    if (!date) return '—';
    return date.toLocaleString('vi-VN', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  }

  function _parseDate(value) {
    if (!value) return null;
    const normalized = typeof value === 'string' && !/(?:Z|[+-]\d{2}:?\d{2})$/i.test(value)
      ? `${value}Z`
      : value;
    const date = new Date(normalized);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function _elapsed(startIso) {
    if (!startIso) return '—';
    const start = _parseDate(startIso);
    if (!start) return '—';
    const ms = Date.now() - start.getTime();
    if (ms < 0) return '—';
    const h = Math.floor(ms / 3600000);
    const m = Math.floor((ms % 3600000) / 60000);
    const s = Math.floor((ms % 60000) / 1000);
    if (h > 0) return `${h}h ${String(m).padStart(2, '0')}m`;
    return `${String(m).padStart(2, '0')}m ${String(s).padStart(2, '0')}s`;
  }

  // ── Show/hide states ─────────────────────────────────────────────────
  function _showLoading() {
    $('ds-loading').style.display = '';
    $('ds-no-session').classList.add('is-hidden');
    $('ds-session-wrap').classList.add('is-hidden');
  }
  function _showNoSession() {
    $('ds-loading').style.display = 'none';
    $('ds-no-session').classList.remove('is-hidden');
    $('ds-session-wrap').classList.add('is-hidden');
  }
  function _showSession() {
    $('ds-loading').style.display = 'none';
    $('ds-no-session').classList.add('is-hidden');
    $('ds-session-wrap').classList.remove('is-hidden');
  }

  // ── Render live session card ─────────────────────────────────────────
  function _renderSession(session) {
    const previousSessionId = _currentSession?.id;
    _currentSession = session;
    _showSession();

    // Station name from charge_point.station.name (if available in response)
    const stationName = session.station_name || session.charge_point_code || 'Trạm sạc';
    $('ds-station-name').textContent = stationName;

    // Connector
    const connectorNumber = session.connector_number ?? session.connector_id;
    $('ds-connector').textContent = connectorNumber != null
      ? `Đầu nối #${connectorNumber}`
      : '—';

    // Energy
    const kwh = session.live_kwh ?? session.total_kwh ?? session.kwh;
    $('ds-kwh').textContent = _fmtKwh(kwh);

    // Cost estimate
    const cost = session.live_cost_vnd ?? session.cost_vnd;
    $('ds-cost').textContent = _fmtVnd(cost);

    // Duration (live counter)
    _stopDurationTimer();
    _durationTimer = setInterval(() => {
      $('ds-duration').textContent = _elapsed(session.started_at);
    }, 1000);
    $('ds-duration').textContent = _elapsed(session.started_at);

    // Progress (estimate based on time — max 3h assumed)
    const maxMs = 3 * 3600 * 1000;
    const start = _parseDate(session.started_at);
    const elapsedMs = start ? Math.max(0, Date.now() - start.getTime()) : 0;
    const pct = start ? Math.min(100, Math.round((elapsedMs / maxMs) * 100)) : 0;
    $('ds-progress-fill').style.width = `${pct}%`;
    $('ds-progress-pct').textContent = `${pct}%`;
    const pb = $('ds-progress-fill').closest('[role="progressbar"]');
    if (pb) pb.setAttribute('aria-valuenow', pct);

    // Start time
    $('ds-start-time').textContent = `Bắt đầu: ${_fmtDate(session.started_at)}`;

    // Session info
    $('ds-cp-code').textContent = session.charge_point_code || '—';
    $('ds-session-id').textContent = `#${session.id}`;

    if (previousSessionId !== session.id) {
      clearTimeout(_remoteStopTimer);
      _remoteStopTimer = null;
    }
    const stopRequestedAt = _parseDate(session.remote_stop_requested_at);
    const stopWaitElapsed = stopRequestedAt
      ? Math.max(0, Date.now() - stopRequestedAt.getTime())
      : 0;
    const stopRequestExpired = Boolean(stopRequestedAt)
      && stopWaitElapsed >= REMOTE_STOP_CONFIRM_TIMEOUT_MS;
    const needsReview = ['needs_review', 'anomaly'].includes(session.status);
    _remoteStopPending = Boolean(stopRequestedAt)
      && !stopRequestExpired
      && !needsReview;
    _setStopButtonPending(_remoteStopPending);
    if (_remoteStopPending && !_remoteStopTimer) {
      _startRemoteStopTimeout(
        session.id,
        Math.max(0, REMOTE_STOP_CONFIRM_TIMEOUT_MS - stopWaitElapsed),
      );
    } else if (!_remoteStopPending && _remoteStopTimer) {
      clearTimeout(_remoteStopTimer);
      _remoteStopTimer = null;
    }

    // Status badge
    const statusBadge = $('ds-session-status-badge');
    const hasEnded = Boolean(session.ended_at);
    let statusLabel = 'Đang sạc';
    let statusClass = 'badge--charging';
    if (hasEnded) {
      statusLabel = 'Đã kết thúc';
      statusClass = 'badge--offline';
    } else if (needsReview) {
      statusLabel = 'Cần xem xét';
      statusClass = 'badge--anomaly';
    } else if (stopRequestedAt) {
      statusLabel = stopRequestExpired
        ? 'Chưa nhận xác nhận dừng'
        : 'Đang chờ trụ xác nhận dừng';
      statusClass = 'badge--warning';
    }
    statusBadge.innerHTML = `<span class="badge ${statusClass}"><span class="badge-text">${statusLabel}</span></span>`;

    // Status text in header
    $('ds-status-text').textContent = hasEnded ? 'Phiên đã kết thúc' : statusLabel;
    $('ds-live-badge').style.display = !hasEnded && !needsReview && !stopRequestedAt ? '' : 'none';
  }

  function _setStopButtonPending(pending) {
    const button = $('ds-stop-btn');
    const label = $('ds-stop-btn-label');
    if (!button || !label) return;
    button.disabled = pending;
    label.textContent = pending ? 'Đang chờ trụ xác nhận…' : 'Dừng sạc';
  }

  function _startRemoteStopTimeout(sessionId, timeoutMs = REMOTE_STOP_CONFIRM_TIMEOUT_MS) {
    clearTimeout(_remoteStopTimer);
    _remoteStopTimer = setTimeout(() => {
      if (_currentSession?.id !== sessionId) return;
      _remoteStopPending = false;
      _remoteStopTimer = null;
      _setStopButtonPending(false);
      const warning = 'Chưa nhận xác nhận dừng';
      const statusBadge = $('ds-session-status-badge');
      if (statusBadge) {
        statusBadge.innerHTML = `<span class="badge badge--warning"><span class="badge-text">${warning}</span></span>`;
      }
      $('ds-status-text').textContent = warning;
      $('ds-live-badge').style.display = 'none';
      _showBanner('Chưa nhận được xác nhận từ trụ. Bạn có thể thử gửi lại lệnh dừng.', 'warning', '⚠️');
    }, timeoutMs);
  }

  function _openStopModal() {
    if (!_currentSession || _remoteStopPending) return;
    $('ds-stop-modal-error').textContent = '';
    $('ds-stop-modal').classList.remove('is-hidden');
  }

  function _closeStopModal() {
    $('ds-stop-modal').classList.add('is-hidden');
    $('ds-stop-modal-error').textContent = '';
  }

  async function _confirmRemoteStop() {
    if (!_currentSession || _remoteStopPending) return;
    const sessionId = _currentSession.id;
    const confirmButton = $('ds-stop-modal-confirm');
    const error = $('ds-stop-modal-error');
    confirmButton.disabled = true;
    confirmButton.textContent = 'Đang gửi lệnh…';
    error.textContent = '';

    try {
      const result = await ApiClient.remoteStop(sessionId);
      if (!_currentSession || _currentSession.id !== sessionId) return;
      _remoteStopPending = true;
      _setStopButtonPending(true);
      const waitingLabel = 'Đang chờ trụ xác nhận dừng';
      $('ds-status-text').textContent = waitingLabel;
      $('ds-session-status-badge').innerHTML = `<span class="badge badge--warning"><span class="badge-text">${waitingLabel}</span></span>`;
      $('ds-live-badge').style.display = 'none';
      _closeStopModal();
      _showBanner(result.message || 'Đã gửi lệnh dừng; đang chờ trụ xác nhận.', 'info', '⏳');

      _startRemoteStopTimeout(sessionId);
    } catch (err) {
      error.textContent = err.message || 'Không gửi được lệnh dừng. Vui lòng thử lại.';
    } finally {
      confirmButton.disabled = false;
      confirmButton.textContent = 'Xác nhận dừng';
    }
  }

  // ── Duration timer ───────────────────────────────────────────────────
  function _stopDurationTimer() {
    if (_durationTimer) { clearInterval(_durationTimer); _durationTimer = null; }
  }

  // ── Load current session ─────────────────────────────────────────────
  async function _loadCurrentSession() {
    _showLoading();
    try {
      const session = await ApiClient.getCurrentSession();
      if (!session) {
        _currentSession = null;
        _stopDurationTimer();
        clearTimeout(_remoteStopTimer);
        _remoteStopPending = false;
        _showNoSession();
        return;
      }
      _renderSession(session);
    } catch (err) {
      if (err.status === 404) {
        _showNoSession();
      } else {
        _showLoading();
        $('ds-loading').innerHTML = `
          <p style="color:var(--color-fault);">Không thể tải phiên sạc. ${_esc(err.message || '')}</p>
          <button class="btn btn--secondary btn--sm" onclick="DriverSession.reload()" style="margin-top:var(--space-3);">Thử lại</button>
        `;
      }
    }
  }

  // ── Notification banner ───────────────────────────────────────────────
  function _showBanner(text, type = 'info', icon = '⚡') {
    const banner = $('ds-notif-banner');
    const bannerText = $('ds-notif-text');
    const bannerIcon = $('ds-notif-icon');
    banner.className = `ds-notif-banner ds-notif-banner--${type}`;
    bannerIcon.textContent = icon;
    bannerText.textContent = text;
    banner.classList.remove('is-hidden');
    // Auto-hide after 8s
    setTimeout(() => banner.classList.add('is-hidden'), 8000);
  }

  function _hideBanner() {
    $('ds-notif-banner').classList.add('is-hidden');
  }

  // ── Session ended overlay (SCRUM-97 / SCRUM-98) ───────────────────────
  async function _showEndedOverlay(sessionId, stopped = false) {
    _stopDurationTimer();
    _sessionEndedId = sessionId;

    const overlay = $('ds-ended-overlay');
    const icon    = $('ds-ended-icon');
    const title   = $('ds-ended-title');
    const sub     = $('ds-ended-sub');
    const summary = $('ds-ended-summary');

    // Stopped vs natural end
    if (stopped) {
      icon.className = 'ds-ended-card__icon ds-ended-card__icon--stopped';
      icon.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/></svg>`;
      title.textContent = 'Phiên sạc đã bị dừng';
      sub.textContent   = 'Phiên sạc của bạn đã bị dừng bởi hệ thống.';
    } else {
      icon.className = 'ds-ended-card__icon ds-ended-card__icon--done';
      icon.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`;
      title.textContent = 'Phiên sạc đã kết thúc';
      sub.textContent   = 'Cảm ơn bạn đã sử dụng dịch vụ!';
    }

    // Load session details for summary
    summary.innerHTML = '<div style="text-align:center;padding:var(--space-3);color:var(--color-text-secondary);font-size:var(--font-size-sm);">Đang tải thông tin phiên...</div>';
    overlay.classList.remove('is-hidden');

    try {
      const s = await ApiClient.getSession(sessionId);
      const startedAt = _parseDate(s.started_at);
      const endedAt = _parseDate(s.ended_at);
      const elMs = startedAt && endedAt ? endedAt - startedAt : 0;
      const elStr = elMs > 0 ? (() => {
        const h = Math.floor(elMs / 3600000);
        const m = Math.floor((elMs % 3600000) / 60000);
        return h > 0 ? `${h}h ${m}m` : `${m} phút`;
      })() : '—';

      summary.innerHTML = `
        <div class="ds-ended-row">
          <span class="ds-ended-row__label">Điện năng nạp</span>
          <span class="ds-ended-row__value">${_fmtKwh(s.total_kwh ?? s.kwh)}</span>
        </div>
        <div class="ds-ended-row">
          <span class="ds-ended-row__label">Thời gian sạc</span>
          <span class="ds-ended-row__value">${elStr}</span>
        </div>
        <div class="ds-ended-row">
          <span class="ds-ended-row__label">Trạm sạc</span>
          <span class="ds-ended-row__value">${_esc(s.station_name || s.charge_point_code || '—')}</span>
        </div>
        <div class="ds-ended-row ds-ended-row--total">
          <span class="ds-ended-row__label">Tổng tiền</span>
          <span class="ds-ended-row__value">${_fmtVnd(s.cost_vnd)}</span>
        </div>
      `;

      // Wire invoice button
      const invoiceBtn = $('ds-ended-view-invoice');
      if (invoiceBtn) {
        invoiceBtn.onclick = () => {
          overlay.classList.add('is-hidden');
          window.location.href = `/sessions/mine`;
        };
      }
    } catch {
      summary.innerHTML = '<div style="font-size:var(--font-size-sm);color:var(--color-text-secondary);text-align:center;">Không thể tải thông tin phiên.</div>';
    }

    // Push browser notification (if permitted)
    _pushBrowserNotification(
      stopped ? '⚡ Phiên sạc bị dừng' : '✅ Phiên sạc hoàn tất',
      stopped ? 'Phiên sạc của bạn đã bị dừng bởi hệ thống.' : 'Pin đã được nạp. Cảm ơn bạn!'
    );

  }

  // ── Browser push notification ─────────────────────────────────────────
  async function _pushBrowserNotification(title, body) {
    if (!('Notification' in window)) return;
    if (Notification.permission === 'default') {
      await Notification.requestPermission();
    }
    if (Notification.permission === 'granted') {
      new Notification(title, { body, icon: '/static/img/favicon.svg' });
    }
  }

  // ── Request notification permission early ─────────────────────────────
  async function _requestNotifPermission() {
    if ('Notification' in window && Notification.permission === 'default') {
      await Notification.requestPermission();
    }
  }

  // ── SSE ───────────────────────────────────────────────────────────────
  function _initSSE() {
    SseClient.connect('/api/monitoring/sse');

    SseClient.on('_connected', () => {
      const ind = $('ds-sse-indicator');
      if (ind) { ind.className = 'sse-indicator connected'; $('ds-sse-label').textContent = 'Nhận thông báo'; }
      if (_hasConnectedBefore) _loadCurrentSession();
      _hasConnectedBefore = true;
    });
    SseClient.on('_error', () => {
      const ind = $('ds-sse-indicator');
      if (ind) { ind.className = 'sse-indicator error'; $('ds-sse-label').textContent = 'Mất kết nối'; }
    });

    SseClient.on('session_update', async (payload) => {
      // payload: { session_id }
      const { session_id } = payload;
      try {
        const session = await ApiClient.getSession(session_id);

        if (session.ended_at) {
          // Session ended
          const wasStopped = session.stop_reason === 'Remote' || session.stop_reason === 'Local';
          _showEndedOverlay(session_id, wasStopped);
          _showBanner(
            wasStopped ? 'Phiên sạc của bạn vừa bị dừng.' : 'Phiên sạc đã hoàn tất!',
            wasStopped ? 'warning' : 'success',
            wasStopped ? '⛔' : '✅'
          );
          _currentSession = null;
          _remoteStopPending = false;
          clearTimeout(_remoteStopTimer);
          _showNoSession();
          _stopDurationTimer();
        } else {
          // Session updated (kwh, cost...)
          if (_currentSession && _currentSession.id === session_id) {
            _renderSession(session);
          }
        }
      } catch { /* ignore */ }
    });
  }

  // ── Init ──────────────────────────────────────────────────────────────
  function init() {
    // Banner close
    $('ds-notif-close').addEventListener('click', _hideBanner);
    $('ds-stop-btn').addEventListener('click', _openStopModal);
    $('ds-stop-modal-close').addEventListener('click', _closeStopModal);
    $('ds-stop-modal-cancel').addEventListener('click', _closeStopModal);
    $('ds-stop-modal-confirm').addEventListener('click', _confirmRemoteStop);
    $('ds-stop-modal').addEventListener('click', (e) => {
      if (e.target === $('ds-stop-modal')) _closeStopModal();
    });

    // Overlay dismiss (click outside card)
    $('ds-ended-overlay').addEventListener('click', (e) => {
      if (e.target === $('ds-ended-overlay')) {
        $('ds-ended-overlay').classList.add('is-hidden');
        _loadCurrentSession();
      }
    });

    _requestNotifPermission();
    _initSSE();
    _loadCurrentSession();
  }

  return {
    init,
    reload: _loadCurrentSession,
  };
})();

document.addEventListener('DOMContentLoaded', () => DriverSession.init());
window.DriverSession = DriverSession;
