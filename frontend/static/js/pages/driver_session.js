/**
 * driver_session.js — SCRUM-98: Theo dõi phiên sạc đang chạy + nhận thông báo SSE
 * Author: Vy Hoàng Tú — Sprint 678
 *
 * API sử dụng:
 *   GET /api/sessions/current → phiên đang chạy hoặc 404
 *   GET /api/sessions/mine?page=1&page_size=5 → lịch sử gần đây
 *   SSE /api/sse → event: session_update { session_id }
 *   GET /api/sessions/{id} → chi tiết phiên
 */

'use strict';

const DriverSession = (() => {
  // ── State ────────────────────────────────────────────────────────────
  let _currentSession = null;   // phiên đang chạy
  let _durationTimer = null;    // interval đếm thời gian
  let _sessionEndedId = null;   // ID phiên vừa kết thúc (để hiện overlay)

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
    // Hỗ trợ cả chuỗi có Z và không có Z (server trả naive UTC)
    const suffix = iso.endsWith('Z') ? '' : 'Z';
    return new Date(iso + suffix).toLocaleString('vi-VN', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  }

  function _elapsed(startIso) {
    if (!startIso) return '—';
    const suffix = startIso.endsWith('Z') ? '' : 'Z';
    const ms = Date.now() - new Date(startIso + suffix).getTime();
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
    if (!session) { _showNoSession(); return; }
    _currentSession = session;
    _showSession();

    // Station name
    const stationName = session.station_name || session.charge_point_code || 'Trạm sạc';
    $('ds-station-name').textContent = stationName;

    // Connector
    $('ds-connector').textContent = session.connector_id != null
      ? `Đầu nối #${session.connector_id}`
      : '—';

    // Energy
    const kwh = session.live_kwh ?? session.total_kwh;
    $('ds-kwh').textContent = _fmtKwh(kwh);

    // Cost estimate
    const cost = session.live_cost_vnd ?? session.cost_vnd;
    $('ds-cost').textContent = _fmtVnd(cost);

    // Duration (live counter)
    _stopDurationTimer();
    if (!session.ended_at) {
      _durationTimer = setInterval(() => {
        $('ds-duration').textContent = _elapsed(session.started_at);
      }, 1000);
    }
    $('ds-duration').textContent = _elapsed(session.started_at);

    // Progress (estimate based on time — max 3h assumed)
    const maxMs = 3 * 3600 * 1000;
    const suffix = (session.started_at || '').endsWith('Z') ? '' : 'Z';
    const elapsedMs = Date.now() - new Date((session.started_at || '') + suffix).getTime();
    const pct = Math.min(100, Math.round((elapsedMs / maxMs) * 100));
    $('ds-progress-fill').style.width = `${pct}%`;
    $('ds-progress-pct').textContent = `${pct}%`;
    const pb = $('ds-progress-fill').closest('[role="progressbar"]');
    if (pb) pb.setAttribute('aria-valuenow', pct);

    // Start time
    $('ds-start-time').textContent = `Bắt đầu: ${_fmtDate(session.started_at)}`;

    // Session info
    $('ds-cp-code').textContent = session.charge_point_code || '—';
    $('ds-session-id').textContent = `#${session.id}`;

    // Status badge
    const statusBadge = $('ds-session-status-badge');
    const isCharging = !session.ended_at;
    statusBadge.innerHTML = isCharging
      ? '<span class="badge badge--charging"><span class="badge-text">Đang sạc</span></span>'
      : '<span class="badge badge--offline"><span class="badge-text">Đã kết thúc</span></span>';

    // Status text in header
    $('ds-status-text').textContent = isCharging ? 'Đang sạc' : 'Phiên đã kết thúc';

    // Live badge visibility
    const liveBadge = $('ds-live-badge');
    if (liveBadge) {
      liveBadge.style.display = isCharging ? '' : 'none';
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
      _renderSession(session);
      _loadRecentHistory();
    } catch (err) {
      if (err.status === 404) {
        _showNoSession();
        _loadRecentHistory();
      } else {
        $('ds-loading').style.display = '';
        $('ds-loading').innerHTML = `
          <p style="color:var(--color-fault);">Không thể tải phiên sạc. ${_esc(err.message || '')}</p>
          <button class="btn btn--secondary btn--sm" onclick="DriverSession.reload()" style="margin-top:var(--space-3);">Thử lại</button>
        `;
      }
    }
  }

  // ── Load recent history ───────────────────────────────────────────────
  async function _loadRecentHistory() {
    const list = $('ds-history-list');
    const section = $('ds-history-section');
    if (!list) return;

    try {
      const data = await ApiClient.listMySessions({ page: 1, page_size: 5 });
      const items = data.items || data;
      if (!items || items.length === 0) {
        section.style.display = 'none';
        return;
      }
      list.innerHTML = items.map(s => `
        <div class="ds-history-item">
          <div class="ds-history-item__left">
            <span class="ds-history-item__station">${_esc(s.station_name || s.charge_point_code || '—')}</span>
            <span class="ds-history-item__date">${_fmtDate(s.started_at)}</span>
          </div>
          <div class="ds-history-item__right">
            <span class="ds-history-item__kwh">${_fmtKwh(s.total_kwh)}</span>
            <span class="ds-history-item__cost">${_fmtVnd(s.cost_vnd)}</span>
          </div>
        </div>
      `).join('');
      section.style.display = '';
    } catch {
      section.style.display = 'none';
    }
  }

  // ── Notification banner ───────────────────────────────────────────────
  function _showBanner(text, type = 'info', icon = '⚡') {
    const banner = $('ds-notif-banner');
    if (!banner) return;
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
    const banner = $('ds-notif-banner');
    if (banner) banner.classList.add('is-hidden');
  }

  // ── Session ended overlay (SCRUM-97 / SCRUM-98) ───────────────────────
  async function _showEndedOverlay(sessionId, stopped = false) {
    _stopDurationTimer();
    _sessionEndedId = sessionId;

    const overlay = $('ds-ended-overlay');
    const icon = $('ds-ended-icon');
    const title = $('ds-ended-title');
    const sub = $('ds-ended-sub');
    const summary = $('ds-ended-summary');

    if (!overlay) return;

    // Stopped vs natural end
    if (stopped) {
      icon.className = 'ds-ended-card__icon ds-ended-card__icon--stopped';
      icon.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/></svg>`;
      title.textContent = 'Phiên sạc đã bị dừng';
      sub.textContent = 'Phiên sạc của bạn đã bị dừng bởi hệ thống.';
    } else {
      icon.className = 'ds-ended-card__icon ds-ended-card__icon--done';
      icon.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`;
      title.textContent = 'Phiên sạc đã kết thúc';
      sub.textContent = 'Cảm ơn bạn đã sử dụng dịch vụ!';
    }

    // Load session details for summary
    summary.innerHTML = '<div style="text-align:center;padding:var(--space-3);color:var(--color-text-secondary);font-size:var(--font-size-sm);">Đang tải thông tin phiên...</div>';
    overlay.classList.remove('is-hidden');

    try {
      const s = await ApiClient.getSession(sessionId);
      const suffix1 = (s.started_at || '').endsWith('Z') ? '' : 'Z';
      const suffix2 = (s.ended_at || '').endsWith('Z') ? '' : 'Z';
      const elMs = s.started_at && s.ended_at
        ? new Date(s.ended_at + suffix2) - new Date(s.started_at + suffix1) : 0;
      const elStr = elMs > 0 ? (() => {
        const h = Math.floor(elMs / 3600000);
        const m = Math.floor((elMs % 3600000) / 60000);
        return h > 0 ? `${h}h ${m}m` : `${m} phút`;
      })() : '—';

      summary.innerHTML = `
        <div class="ds-ended-row">
          <span class="ds-ended-row__label">Điện năng nạp</span>
          <span class="ds-ended-row__value">${_fmtKwh(s.total_kwh)}</span>
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

      // Wire invoice button — chuyển thẳng sang trang lịch sử phiên
      const invoiceBtn = $('ds-ended-view-invoice');
      if (invoiceBtn) {
        invoiceBtn.onclick = () => {
          overlay.classList.add('is-hidden');
          window.location.href = '/sessions/mine';
        };
      }
    } catch {
      summary.innerHTML = '<div style="font-size:var(--font-size-sm);color:var(--color-text-secondary);text-align:center;">Không thể tải thông tin phiên.</div>';
    }

    // Push browser notification (if permitted) — SCRUM-97
    _pushBrowserNotification(
      stopped ? '⚡ Phiên sạc bị dừng' : '✅ Phiên sạc hoàn tất',
      stopped ? 'Phiên sạc của bạn đã bị dừng bởi hệ thống.' : 'Pin đã được nạp. Cảm ơn bạn!'
    );

    // Reload history after ending
    setTimeout(_loadRecentHistory, 1000);
  }

  // ── Browser push notification (SCRUM-97) ─────────────────────────────
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

  // ── SSE (SCRUM-98) ────────────────────────────────────────────────────
  function _initSSE() {
    if (!window.SseClient) return;
    SseClient.connect('/api/sse');

    SseClient.on('_connected', () => {
      const ind = $('ds-sse-indicator');
      if (ind) {
        ind.className = 'sse-indicator connected';
        const lbl = $('ds-sse-label');
        if (lbl) lbl.textContent = 'Nhận thông báo';
      }
    });

    SseClient.on('_error', () => {
      const ind = $('ds-sse-indicator');
      if (ind) {
        ind.className = 'sse-indicator error';
        const lbl = $('ds-sse-label');
        if (lbl) lbl.textContent = 'Mất kết nối';
      }
    });

    SseClient.on('session_update', async (payload) => {
      const { session_id } = payload;
      try {
        const session = await ApiClient.getSession(session_id);

        if (session.ended_at) {
          // Phiên kết thúc — chỉ hiện overlay nếu đây là phiên của tài xế này
          if (_currentSession && _currentSession.id === session_id) {
            const wasStopped = session.stop_reason === 'Remote' || session.stop_reason === 'Local';
            await _showEndedOverlay(session_id, wasStopped);
            _showBanner(
              wasStopped ? 'Phiên sạc của bạn vừa bị dừng.' : 'Phiên sạc đã hoàn tất!',
              wasStopped ? 'warning' : 'success',
              wasStopped ? '⛔' : '✅'
            );
            _currentSession = null;
            _showNoSession();
            _stopDurationTimer();
          }
        } else {
          // Cập nhật live kWh / cost
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
    const notifClose = $('ds-notif-close');
    if (notifClose) notifClose.addEventListener('click', _hideBanner);

    // Overlay dismiss (click outside card)
    const endedOverlay = $('ds-ended-overlay');
    if (endedOverlay) {
      endedOverlay.addEventListener('click', (e) => {
        if (e.target === endedOverlay) {
          endedOverlay.classList.add('is-hidden');
          _loadCurrentSession();
        }
      });
    }

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
