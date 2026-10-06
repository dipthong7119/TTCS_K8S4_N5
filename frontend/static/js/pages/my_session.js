/**
 * pages/my_session.js
 * Nhiệm vụ Sprint 3:
 * - T-48 (SCRUM-179, Story S-22): Màn hình phiên đang sạc, live kWh tăng dần realtime (<2s), empty state cho tài xế.
 * - T-50 (SCRUM-173, Story S-23): Nút dừng từ xa, modal xác nhận, đồng hồ đếm ngược 2 phút (120s), xử lý 3 ca lỗi và 1 ca thành công.
 */
(function () {
  'use strict';

  const PAGE_SIZE = 15;
  const REMOTE_STOP_TIMEOUT_SEC = 120; // 2 phút theo đặc tả S-23 & T-50

  let _page = 1;
  let _activeTimer = null;
  let _activeStart = null;
  let _activeSession = null;
  let _currentLiveKwh = 0;

  // Quản lý trạng thái dừng từ xa (T-50)
  let _pendingStopSessionId = null;
  let _stopCountdownTimer = null;
  let _stopRemainingSec = 0;
  let _activeStopButton = null;

  // Chế độ mô phỏng dữ liệu mẫu (Mock Mode) theo quy định Sprint 3
  let _isMockMode = false;
  let _mockMeterInterval = null;

  const _pageRoot = document.getElementById('sessions-page');
  const _isGlobal = _pageRoot?.dataset.scope === 'all';
  const _columnCount = Number(_pageRoot?.dataset.columnCount || 8);
  const _canRemoteStop = _pageRoot?.dataset.canRemoteStop === 'true';

  function escHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function fmtDatetime(iso) {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleString('vi-VN', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return iso;
    }
  }

  function fmtVND(amountInt) {
    if (amountInt == null) return 'Chưa tính';
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amountInt);
  }

  function fmtDuration(seconds) {
    const s = Math.max(0, Math.floor(seconds || 0));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = Math.floor(s % 60);
    return [h, m, sec].map(x => String(x).padStart(2, '0')).join(':');
  }

  // ── T-48: Hiển thị và Cập nhật Phiên đang sạc ──────────────────────────────
  async function loadCurrentActiveSession() {
    if (_isMockMode) return;
    try {
      // Ưu tiên gọi API phiên hiện tại cho driver (T-47)
      if (!_isGlobal && ApiClient.getCurrentSession) {
        const current = await ApiClient.getCurrentSession();
        if (current && typeof current === 'object' && current.id) {
          renderActiveBanner(current);
          return current;
        }
      }
    } catch {
      // Nếu API trả 403 hoặc lỗi tạm thời, fallback sang tìm trong danh sách
    }
    return null;
  }

  function renderActiveBanner(session) {
    _activeSession = session;
    const banner = document.getElementById('active-session-banner');
    const noSessionCard = document.getElementById('no-active-session-card');

    if (!session || (session.status !== 'active' && session.status !== 'charging')) {
      if (banner) banner.style.display = 'none';
      clearInterval(_activeTimer);
      _activeTimer = null;
      _activeSession = null;

      // Tài xế khi không có phiên sạc thì hiển thị card rỗng kèm nút tìm trạm (S-22 AC3)
      if (!_isGlobal && noSessionCard) {
        noSessionCard.style.display = 'flex';
      }
      return;
    }

    if (noSessionCard) noSessionCard.style.display = 'none';
    if (!banner) return;

    banner.style.display = 'block';

    const idEl = document.getElementById('active-session-id');
    if (idEl) idEl.textContent = `#${session.id}`;

    const metaEl = document.getElementById('active-session-meta');
    if (metaEl) {
      metaEl.textContent = `${session.station_name || 'Trạm sạc'} / ${session.charge_point_code || '—'}`;
    }

    const startEl = document.getElementById('active-start-time');
    if (startEl) startEl.textContent = fmtDatetime(session.started_at);

    const connEl = document.getElementById('active-connector-num');
    if (connEl) connEl.textContent = `#${session.connector_number || 1}`;

    const driverEl = document.getElementById('active-driver-name');
    if (driverEl) driverEl.textContent = session.driver_name || '—';

    // Cập nhật live kWh
    updateLiveKwhDisplay(session.live_kwh != null ? session.live_kwh : (session.kwh || 0), false);

    // Bắt đầu timer đếm thời gian sạc
    _activeStart = session.started_at ? new Date(session.started_at) : new Date();
    startDurationTimer();

    // Gắn handler cho nút Dừng từ xa trên banner (T-50)
    const stopBtn = document.getElementById('active-stop-btn');
    if (stopBtn && _canRemoteStop) {
      stopBtn.setAttribute('data-stop-session', session.id);
      stopBtn.onclick = () => showStopConfirmation(session.id, stopBtn);
      if (session.remote_stop_requested_at) {
        setStoppingUI(stopBtn, true, REMOTE_STOP_TIMEOUT_SEC);
      }
    }
  }

  function updateLiveKwhDisplay(newKwh, triggerPulse = true) {
    const kwhEl = document.getElementById('active-kwh');
    if (!kwhEl) return;

    const val = Number(newKwh || 0);
    _currentLiveKwh = val;
    kwhEl.innerHTML = `${val.toFixed(3)} <span class="active-unit">kWh</span>`;

    if (triggerPulse) {
      kwhEl.classList.remove('kwh-pulse');
      void kwhEl.offsetWidth; // Force DOM reflow để kích hoạt lại animation
      kwhEl.classList.add('kwh-pulse');
    }
  }

  function startDurationTimer() {
    clearInterval(_activeTimer);
    const durationEl = document.getElementById('active-duration');
    if (!durationEl) return;

    _activeTimer = setInterval(() => {
      if (!_activeStart) return;
      const seconds = Math.floor((Date.now() - _activeStart.getTime()) / 1000);
      durationEl.textContent = fmtDuration(seconds);
    }, 1000);
  }

  // ── T-50: Luồng Dừng Phiên Sạc Từ Xa (Story S-23) ────────────────────────
  function showStopConfirmation(sessionId, buttonEl) {
    _pendingStopSessionId = sessionId;
    _activeStopButton = buttonEl;

    const modal = document.getElementById('remote-stop-modal');
    const desc = document.getElementById('remote-stop-modal-desc');
    if (desc) {
      desc.textContent = `Bạn có chắc chắn muốn gửi lệnh dừng từ xa cho phiên sạc #${sessionId} tới trụ sạc không?`;
    }
    if (modal) modal.classList.remove('is-hidden');
  }

  function closeStopConfirmation() {
    const modal = document.getElementById('remote-stop-modal');
    if (modal) modal.classList.add('is-hidden');
    _pendingStopSessionId = null;
  }

  function setStoppingUI(buttonEl, isStopping, remainingSec) {
    if (!buttonEl) return;
    const bannerTimer = document.getElementById('active-stop-timer');

    if (isStopping) {
      buttonEl.disabled = true;
      buttonEl.classList.add('btn--stopping');
      const textSpan = buttonEl.querySelector('.stop-btn-text');
      if (textSpan) textSpan.textContent = `Đang dừng (${remainingSec}s)`;
      else buttonEl.textContent = `Đang dừng (${remainingSec}s)`;

      if (bannerTimer) {
        bannerTimer.style.display = 'inline-block';
        bannerTimer.textContent = `${remainingSec}s`;
      }
    } else {
      buttonEl.disabled = false;
      buttonEl.classList.remove('btn--stopping');
      const textSpan = buttonEl.querySelector('.stop-btn-text');
      if (textSpan) textSpan.textContent = 'Dừng từ xa';
      else buttonEl.textContent = 'Dừng từ xa';

      if (bannerTimer) {
        bannerTimer.style.display = 'none';
      }
    }
  }

  async function executeRemoteStop() {
    const sessionId = _pendingStopSessionId;
    const buttonEl = _activeStopButton;
    closeStopConfirmation();

    if (!sessionId) return;

    // Khởi động đồng hồ đếm ngược 120s (2 phút theo S-23 AC4)
    _stopRemainingSec = REMOTE_STOP_TIMEOUT_SEC;
    setStoppingUI(buttonEl, true, _stopRemainingSec);

    clearInterval(_stopCountdownTimer);
    _stopCountdownTimer = setInterval(() => {
      _stopRemainingSec--;
      if (_stopRemainingSec > 0) {
        setStoppingUI(buttonEl, true, _stopRemainingSec);
      } else {
        // Hết thời gian chờ 2 phút (Ca 3: S-23 AC4 & T-50)
        clearInterval(_stopCountdownTimer);
        _stopCountdownTimer = null;
        setStoppingUI(buttonEl, false, 0);
        showToast(
          'Đã quá 2 phút trụ không gửi xác nhận kết thúc phiên. Phiên sạc đã được đánh dấu cần xem xét.',
          'warning'
        );
        loadSessions();
      }
    }, 1000);

    // Kịch bản Mock Mode
    if (_isMockMode) {
      setTimeout(() => {
        clearInterval(_stopCountdownTimer);
        _stopCountdownTimer = null;
        setStoppingUI(buttonEl, false, 0);
        // Mô phỏng thành công
        showToast(`Phiên #${sessionId} đã kết thúc thành công từ xa.`, 'success');
        if (_activeSession && _activeSession.id == sessionId) {
          _activeSession.status = 'completed';
          _activeSession.ended_at = new Date().toISOString();
          renderActiveBanner(null);
        }
        loadSessions();
      }, 3000);
      return;
    }

    try {
      const result = await ApiClient.remoteStop(sessionId);
      // Khi server trả status Accepted
      showToast(
        result.message || 'Đã gửi lệnh dừng tới trụ; đang chờ trụ gửi StopTransaction xác nhận.',
        'info'
      );
    } catch (err) {
      // Hủy đồng hồ đếm ngược ngay khi có lỗi
      clearInterval(_stopCountdownTimer);
      _stopCountdownTimer = null;
      setStoppingUI(buttonEl, false, 0);

      const status = err.status || 0;
      const msg = String(err.message || err.detail || '');

      // Ca 2: Trụ ngoại tuyến (S-23 AC3)
      if (status === 409 || msg.includes('ngoại tuyến') || msg.includes('không còn sẵn sàng')) {
        showToast('Trụ sạc đang ngoại tuyến, không thể gửi lệnh dừng từ xa vào lúc này.', 'error');
        return;
      }

      // Ca 1: Trụ từ chối (S-23 AC2)
      if (status === 502 || msg.includes('từ chối') || msg.includes('không chấp nhận')) {
        showToast('Trụ sạc đã từ chối lệnh dừng từ xa (Rejected). Phiên sạc vẫn đang tiếp tục hoạt động.', 'error');
        return;
      }

      // Ca timeout kết nối máy chủ tới trụ (504)
      if (status === 504 || msg.includes('hết thời gian') || msg.includes('không phản hồi')) {
        showToast('Trụ sạc không phản hồi lệnh dừng từ xa trong thời gian quy định.', 'error');
        return;
      }

      // Lỗi chung
      showToast(msg || 'Gửi lệnh dừng từ xa thất bại.', 'error');
    }
  }

  // ── Tải danh sách phiên và kết xuất bảng ──────────────────────────────────
  async function loadSessions() {
    const period = document.getElementById('session-period')?.value || '30';
    const status = document.getElementById('session-status-filter')?.value || '';

    if (_isMockMode) {
      renderMockData();
      return;
    }

    try {
      const listFn = _isGlobal ? ApiClient.listAllSessions : ApiClient.listMySessions;
      const data = await listFn({ days: period, status, page: _page, page_size: PAGE_SIZE });
      const items = data.items || data || [];

      renderTable(items);
      renderStats(data);
      renderPagination(data.total || items.length);

      const countEl = document.getElementById('session-count');
      if (countEl) countEl.textContent = `${data.total || items.length} phiên`;

      // Kiểm tra phiên hoạt động
      const activeInList = items.find(s => s.status === 'active' || s.status === 'charging');
      if (activeInList) {
        renderActiveBanner(activeInList);
      } else {
        const current = await loadCurrentActiveSession();
        if (!current) {
          renderActiveBanner(null);
        }
      }
    } catch (err) {
      const tbody = document.getElementById('sessions-tbody');
      if (tbody) {
        tbody.innerHTML = `<tr><td colspan="${_columnCount}" class="text-center">${escHtml(err.message || 'Không tải được danh sách phiên')}</td></tr>`;
      }
      const countEl = document.getElementById('session-count');
      if (countEl) countEl.textContent = 'Lỗi kết nối';
      showToast(err.message || 'Không tải được phiên sạc', 'error');
    }
  }

  const STATUS_LABEL = {
    completed: 'Hoàn thành',
    active: 'Đang sạc',
    charging: 'Đang sạc',
    anomaly: 'Bất thường',
    needs_review: 'Cần xem xét',
  };

  const STATUS_CLASS = {
    completed: 'badge--available',
    active: 'badge--charging',
    charging: 'badge--charging',
    anomaly: 'badge--anomaly',
    needs_review: 'badge--anomaly',
  };

  function renderTable(sessions) {
    const tbody = document.getElementById('sessions-tbody');
    if (!tbody) return;

    if (!sessions.length) {
      tbody.innerHTML = `<tr><td colspan="${_columnCount}"><div class="empty-state"><div class="empty-state__icon">⚡</div><div class="empty-state__title">Chưa có phiên sạc nào</div><div class="empty-state__desc">Dữ liệu các phiên sạc sẽ xuất hiện tại đây khi có giao dịch.</div></div></td></tr>`;
      return;
    }

    tbody.innerHTML = sessions.map(s => {
      const durSec = s.duration_seconds;
      const dur = durSec != null ? fmtDuration(durSec) : '—';
      const isActive = s.status === 'active' || s.status === 'charging';

      return `<tr style="cursor:pointer;" data-session-id="${s.id}">
        <td><code style="font-family:monospace;font-size:var(--font-size-xs);background:var(--color-surface-alt);padding:2px 6px;border-radius:4px;">#${s.id}</code>${s.is_demo ? '<small class="audit-subtext">Dữ liệu mẫu</small>' : ''}</td>
        <td>${escHtml(s.station_name || '—')} / <span style="font-family:monospace;">${escHtml(s.charge_point_code || '—')}</span></td>
        ${_isGlobal ? `<td>${escHtml(s.driver_name || '—')}</td>` : ''}
        <td style="white-space:nowrap;font-size:var(--font-size-xs);">${fmtDatetime(s.started_at)}</td>
        <td style="white-space:nowrap;font-size:var(--font-size-xs);">${s.ended_at ? fmtDatetime(s.ended_at) : '<span style="color:var(--color-charging);font-weight:600;">Đang sạc</span>'}</td>
        <td style="font-size:var(--font-size-xs);font-family:monospace;">${dur}</td>
        <td style="font-weight:600;">${s.ended_at ? (s.kwh != null ? s.kwh.toFixed(3) : '—') : (s.live_kwh != null ? s.live_kwh.toFixed(3) : '—')}</td>
        <td>${fmtVND(s.cost_vnd)}</td>
        <td><span class="badge ${STATUS_CLASS[s.status] || 'badge--neutral'}">${STATUS_LABEL[s.status] || 'Không rõ'}</span></td>
        ${_canRemoteStop ? `<td>${isActive ? (s.remote_stop_requested_at ? '<button class="btn btn--secondary btn--sm" type="button" disabled>Đang chờ trụ</button>' : `<button class="btn btn--danger btn--sm" type="button" data-stop-session="${s.id}">Dừng từ xa</button>`) : '—'}</td>` : ''}
      </tr>`;
    }).join('');

    // Sự kiện mở modal xem chi tiết
    tbody.querySelectorAll('[data-session-id]').forEach(row => {
      row.addEventListener('click', () => {
        const item = sessions.find(s => s.id == row.dataset.sessionId);
        if (item) openDetail(item);
      });
    });

    // Sự kiện bấm nút Dừng từ xa trên bảng (T-50)
    tbody.querySelectorAll('[data-stop-session]').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        showStopConfirmation(btn.dataset.stopSession, btn);
      });
    });
  }

  function renderStats(data) {
    const totalEl = document.getElementById('s-total');
    if (totalEl) totalEl.textContent = data.total || '0';

    const kwhEl = document.getElementById('s-kwh');
    if (kwhEl) kwhEl.textContent = data.total_kwh != null ? data.total_kwh.toFixed(2) : '—';

    const costEl = document.getElementById('s-cost');
    if (costEl) {
      costEl.textContent = data.total_cost_vnd != null
        ? new Intl.NumberFormat('vi-VN').format(data.total_cost_vnd) + ' ₫'
        : 'Chưa tính';
    }
  }

  function renderPagination(total) {
    const pages = Math.ceil(total / PAGE_SIZE);
    const pg = document.getElementById('sessions-pagination');
    if (!pg) return;
    pg.innerHTML = '';
    if (pages <= 1) return;

    for (let i = 1; i <= pages; i++) {
      const b = document.createElement('button');
      b.className = 'pagination__btn' + (i === _page ? ' is-active' : '');
      b.textContent = i;
      b.setAttribute('aria-label', `Trang ${i}`);
      if (i === _page) b.setAttribute('aria-current', 'page');
      b.addEventListener('click', () => {
        _page = i;
        loadSessions();
      });
      pg.appendChild(b);
    }
  }

  function openDetail(session) {
    if (!session) return;
    const titleEl = document.getElementById('session-detail-title');
    if (titleEl) titleEl.textContent = `Chi tiết phiên sạc #${session.id}`;

    const bodyEl = document.getElementById('session-detail-body');
    if (bodyEl) {
      bodyEl.innerHTML = `
        <dl style="display:grid;grid-template-columns:1fr 1fr;gap:var(--space-3) var(--space-6);">
          <div><dt style="font-size:var(--font-size-xs);color:var(--color-text-secondary);font-weight:600;margin-bottom:2px;">Trạm sạc</dt><dd>${escHtml(session.station_name || '—')}</dd></div>
          <div><dt style="font-size:var(--font-size-xs);color:var(--color-text-secondary);font-weight:600;margin-bottom:2px;">Mã trụ</dt><dd><code style="font-family:monospace;">${escHtml(session.charge_point_code || '—')}</code></dd></div>
          ${_isGlobal ? `<div><dt style="font-size:var(--font-size-xs);color:var(--color-text-secondary);font-weight:600;margin-bottom:2px;">Tài xế</dt><dd>${escHtml(session.driver_name || '—')}</dd></div>` : ''}
          <div><dt style="font-size:var(--font-size-xs);color:var(--color-text-secondary);font-weight:600;margin-bottom:2px;">Thời điểm bắt đầu</dt><dd>${fmtDatetime(session.started_at)}</dd></div>
          <div><dt style="font-size:var(--font-size-xs);color:var(--color-text-secondary);font-weight:600;margin-bottom:2px;">Thời điểm kết thúc</dt><dd>${session.ended_at ? fmtDatetime(session.ended_at) : '<span style="color:var(--color-charging);font-weight:600;">Đang sạc</span>'}</dd></div>
          <div><dt style="font-size:var(--font-size-xs);color:var(--color-text-secondary);font-weight:600;margin-bottom:2px;">Điện năng tiêu thụ</dt><dd style="font-weight:700;">${session.ended_at ? (session.kwh != null ? session.kwh.toFixed(3) + ' kWh' : '—') : (session.live_kwh != null ? session.live_kwh.toFixed(3) + ' kWh' : 'Đang sạc')}</dd></div>
          <div><dt style="font-size:var(--font-size-xs);color:var(--color-text-secondary);font-weight:600;margin-bottom:2px;">Chi phí sạc</dt><dd style="font-weight:700;">${session.cost_vnd != null ? new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(session.cost_vnd) : 'Chưa có cấu hình biểu giá'}</dd></div>
          <div><dt style="font-size:var(--font-size-xs);color:var(--color-text-secondary);font-weight:600;margin-bottom:2px;">Trạng thái</dt><dd><span class="badge ${STATUS_CLASS[session.status] || 'badge--neutral'}">${STATUS_LABEL[session.status] || 'Không rõ'}</span></dd></div>
          <div><dt style="font-size:var(--font-size-xs);color:var(--color-text-secondary);font-weight:600;margin-bottom:2px;">Lý do kết thúc</dt><dd>${escHtml(session.stop_reason || '—')}</dd></div>
        </dl>`;
    }
    const modal = document.getElementById('session-detail-modal');
    if (modal) modal.classList.remove('is-hidden');
  }

  // ── Chế độ Mô phỏng / Dữ liệu mẫu (Mock Mode) ───────────────────────────
  function toggleMockMode() {
    _isMockMode = !_isMockMode;
    const indicator = document.getElementById('mock-mode-indicator');
    const text = document.getElementById('mock-mode-text');

    if (_isMockMode) {
      if (indicator) indicator.classList.add('is-active');
      if (text) text.textContent = 'Đang mô phỏng sạc';
      showToast('Đã bật chế độ mô phỏng kiểm thử giao diện T-48 / T-50.', 'info');
      startMockSimulation();
    } else {
      if (indicator) indicator.classList.remove('is-active');
      if (text) text.textContent = 'Mô phỏng sạc mẫu';
      stopMockSimulation();
      showToast('Đã tắt chế độ mô phỏng; quay về dữ liệu hệ thống.', 'default');
      loadSessions();
    }
  }

  function startMockSimulation() {
    const mockSession = {
      id: 8888,
      station_name: 'Trạm EcoCharge Cầu Giấy',
      charge_point_code: 'CP-CG-01',
      connector_number: 1,
      driver_name: 'Nguyễn Văn Tuấn',
      started_at: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
      live_kwh: 12.450,
      status: 'active',
      is_demo: true,
    };

    renderActiveBanner(mockSession);
    renderMockData();

    // Giả lập nhận MeterValues mỗi 3 giây (kiểm chứng T-48 AC2: cập nhật số kWh dưới 2s)
    clearInterval(_mockMeterInterval);
    _mockMeterInterval = setInterval(() => {
      if (!_isMockMode || !_activeSession) return;
      _currentLiveKwh += 0.052;
      _activeSession.live_kwh = _currentLiveKwh;
      updateLiveKwhDisplay(_currentLiveKwh, true);
    }, 3000);
  }

  function stopMockSimulation() {
    clearInterval(_mockMeterInterval);
    _mockMeterInterval = null;
  }

  function renderMockData() {
    const mockItems = [
      {
        id: 8888,
        station_name: 'Trạm EcoCharge Cầu Giấy',
        charge_point_code: 'CP-CG-01',
        driver_name: 'Nguyễn Văn Tuấn',
        started_at: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
        ended_at: null,
        duration_seconds: 900,
        live_kwh: _currentLiveKwh || 12.450,
        cost_vnd: null,
        status: 'active',
        is_demo: true,
      },
      {
        id: 8887,
        station_name: 'Trạm EcoCharge Ba Đình',
        charge_point_code: 'CP-BD-02',
        driver_name: 'Nguyễn Văn Tuấn',
        started_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
        ended_at: new Date(Date.now() - 1.2 * 3600 * 1000).toISOString(),
        duration_seconds: 2880,
        kwh: 35.820,
        cost_vnd: 135000,
        status: 'completed',
        stop_reason: 'EVDisconnected',
        is_demo: true,
      },
      {
        id: 8885,
        station_name: 'Trạm EcoCharge Mỹ Đình',
        charge_point_code: 'CP-MD-01',
        driver_name: 'Trần Thị Mai',
        started_at: new Date(Date.now() - 24 * 3600 * 1000).toISOString(),
        ended_at: new Date(Date.now() - 23 * 3600 * 1000).toISOString(),
        duration_seconds: 3600,
        kwh: 42.100,
        cost_vnd: 160000,
        status: 'completed',
        stop_reason: 'Local',
        is_demo: true,
      },
    ];

    renderTable(mockItems);
    renderStats({
      total: 3,
      total_kwh: 90.37,
      total_cost_vnd: 295000,
    });
    const countEl = document.getElementById('session-count');
    if (countEl) countEl.textContent = '3 phiên (mô phỏng)';
  }

  // ── Khởi tạo trang ────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    loadSessions();

    document.getElementById('session-period')?.addEventListener('change', () => {
      _page = 1;
      loadSessions();
    });

    document.getElementById('session-status-filter')?.addEventListener('change', () => {
      _page = 1;
      loadSessions();
    });

    document.getElementById('session-modal-close')?.addEventListener('click', () => {
      document.getElementById('session-detail-modal')?.classList.add('is-hidden');
    });

    document.getElementById('session-detail-modal')?.addEventListener('click', e => {
      if (e.target === e.currentTarget) e.currentTarget.classList.add('is-hidden');
    });

    // Modal dừng từ xa (T-50)
    document.getElementById('remote-stop-modal-cancel')?.addEventListener('click', closeStopConfirmation);
    document.getElementById('remote-stop-modal-close')?.addEventListener('click', closeStopConfirmation);
    document.getElementById('remote-stop-modal-confirm')?.addEventListener('click', executeRemoteStop);
    document.getElementById('remote-stop-modal')?.addEventListener('click', e => {
      if (e.target === e.currentTarget) closeStopConfirmation();
    });

    // Nút chuyển đổi Mock Mode
    document.getElementById('btn-toggle-session-mock')?.addEventListener('click', toggleMockMode);

    // Kênh realtime SSE (T-48 & T-50)
    if (_pageRoot?.dataset.liveUpdates === 'true' && window.SseClient) {
      SseClient.connect('/api/monitoring/sse');
      SseClient.on('session_update', payload => {
        if (_isMockMode) return;

        // Cập nhật live kWh tức thì (< 2s) nếu phiên đang hiển thị nhận được số đo mới
        if (_activeSession && payload?.session_id == _activeSession.id) {
          if (payload.live_kwh != null) {
            updateLiveKwhDisplay(payload.live_kwh, true);
          }
          if (payload.status === 'completed') {
            showToast(`Phiên sạc #${payload.session_id} đã kết thúc.`, 'success');
            renderActiveBanner(null);
          }
        }
        loadSessions();
      });
    }
  });
})();

