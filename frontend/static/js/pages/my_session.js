/**
 * pages/my_session.js
 * Nhiệm vụ Sprint 3:
 * - T-48 (SCRUM-179, Story S-22): Màn hình phiên đang sạc, live kWh tăng dần realtime (<2s), empty state cho tài xế.
 * - T-50 (SCRUM-173, Story S-23): Nút dừng từ xa, modal xác nhận, đồng hồ đếm ngược 2 phút (120s), xử lý 3 ca lỗi và 1 ca thành công.
 * - SCRUM-208 (FE, thuộc SCRUM-63): Hiển thị chi tiết cách tính tiền theo từng khung giờ trong modal phiên sạc.
 * - SCRUM-66 (FE): Màn hình hoá đơn E-Receipt có diễn giải từng đoạn giá cho tài xế.
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
  let _invoiceDetailRequest = 0;

  // Quản lý trạng thái dừng từ xa (T-50)
  let _pendingStopSessionId = null;
  let _stopCountdownTimer = null;
  let _stopRemainingSec = 0;
  let _activeStopButton = null;
  let _stoppingSessionId = null;

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

    const updateDuration = () => {
      if (!_activeStart) return;
      const seconds = Math.floor((Date.now() - _activeStart.getTime()) / 1000);
      durationEl.textContent = fmtDuration(seconds);
    };

    updateDuration();
    _activeTimer = setInterval(updateDuration, 1000);
  }

  // ── T-50: Luồng Dừng Phiên Sạc Từ Xa (Story S-23) ────────────────────────
  function showStopConfirmation(sessionId, buttonEl) {
    if (!_canRemoteStop || _stoppingSessionId !== null) return;
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
    _stoppingSessionId = sessionId;

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
        _stoppingSessionId = null;
        setStoppingUI(buttonEl, false, 0);
        showToast(
          'Đã quá 2 phút chưa nhận được xác nhận kết thúc phiên. Đang tải lại trạng thái từ máy chủ.',
          'warning'
        );
        loadSessions();
      }
    }, 1000);

    try {
      const result = await ApiClient.remoteStop(sessionId);
      if (_stoppingSessionId !== sessionId) return;
      // Khi server trả status Accepted
      showToast(
        result.message || 'Đã gửi lệnh dừng tới trụ; đang chờ trụ gửi StopTransaction xác nhận.',
        'info'
      );
    } catch (err) {
      if (_stoppingSessionId !== sessionId) return;
      // Hủy đồng hồ đếm ngược ngay khi có lỗi
      clearInterval(_stopCountdownTimer);
      _stopCountdownTimer = null;
      _stoppingSessionId = null;
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

  // ── SCRUM-208: Render bảng phân rã chi phí chi tiết theo khung giờ ──────────
  function renderInvoiceBreakdown(session) {
    const segments = Array.isArray(session.invoice_segments) ? session.invoice_segments : [];
    if (!segments.length) return '';

    const energySegs = segments.filter(s => s.kind !== 'occupancy_fee');
    const occupancySeg = segments.find(s => s.kind === 'occupancy_fee');
    const energyTotal = energySegs.reduce((sum, s) => sum + (s.amount_vnd || 0), 0);

    const segRows = energySegs.map((seg, idx) => {
      const fromTime = seg.from ? new Date(seg.from).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' }) : '—';
      const toTime = seg.to ? new Date(seg.to).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' }) : '—';
      const bandLabel = escHtml(seg.band || `Khung giá ${idx + 1}`);
      const tariffName = seg.tariff_name
        ? `<small class="invoice-tariff-name">${escHtml(seg.tariff_name)}</small>`
        : '';
      const serviceDate = seg.service_date
        ? `<small class="invoice-service-date">${escHtml(seg.service_date)}</small>`
        : '';
      const isLast = idx === energySegs.length - 1 && !occupancySeg;
      return `
        <tr class="invoice-seg-row">
          <td><span class="invoice-band-chip">${bandLabel}</span>${tariffName}</td>
          <td class="invoice-time-cell"><span class="invoice-time">${fromTime}</span><span class="invoice-time-sep">→</span><span class="invoice-time">${toTime}</span>${serviceDate}</td>
          <td class="invoice-num-cell">${escHtml(String(parseFloat(seg.energy_kwh || 0).toFixed(3)))} kWh</td>
          <td class="invoice-num-cell">${fmtVND(seg.price_vnd_per_kwh)}<span class="invoice-unit">/kWh</span></td>
          <td class="invoice-amount-cell">${fmtVND(seg.amount_vnd)}</td>
        </tr>`;
    }).join('');

    const occupancyRow = occupancySeg ? `
      <tr class="invoice-seg-row invoice-occupancy-row">
        <td><span class="invoice-band-chip invoice-band-chip--occupancy">Phí chiếm trụ</span></td>
        <td class="invoice-time-cell"><span class="invoice-hint">Sau ân hạn</span></td>
        <td class="invoice-num-cell">${escHtml(String(occupancySeg.duration_minutes || 0))} phút</td>
        <td class="invoice-num-cell">${fmtVND(occupancySeg.price_vnd_per_minute)}<span class="invoice-unit">/phút</span></td>
        <td class="invoice-amount-cell">${fmtVND(occupancySeg.amount_vnd)}</td>
      </tr>` : '';

    const totalRow = `
      <tr class="invoice-total-row">
        <td colspan="4">Tổng cộng</td>
        <td class="invoice-amount-cell invoice-grand-total">${fmtVND(session.cost_vnd)}</td>
      </tr>`;

    const roundingNote = session.invoice_rounding_rule
      ? `<p class="invoice-rounding-note">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          ${escHtml(session.invoice_rounding_rule)}
        </p>` : '';

    return `
      <section class="invoice-breakdown" aria-label="Phân rã chi phí theo khung giờ">
        <div class="invoice-breakdown__header">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="9" y1="7" x2="15" y2="7"/><line x1="9" y1="12" x2="15" y2="12"/><line x1="9" y1="17" x2="12" y2="17"/></svg>
          <h3>Phân rã chi phí theo khung giờ</h3>
        </div>
        <div class="invoice-table-wrap">
          <table class="invoice-table" aria-label="Chi tiết từng khung giờ sạc">
            <thead>
              <tr>
                <th>Khung giá</th>
                <th>Thời gian</th>
                <th>Sản lượng</th>
                <th>Đơn giá</th>
                <th>Thành tiền</th>
              </tr>
            </thead>
            <tbody>${segRows}${occupancyRow}</tbody>
            <tfoot>${totalRow}</tfoot>
          </table>
        </div>
        ${roundingNote}
        ${session.cost_vnd != null ? `<button class="btn btn--ghost btn--sm invoice-view-btn" type="button" id="btn-open-invoice" data-session-id="${session.id}">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          Xem hoá đơn đầy đủ
        </button>` : ''}
      </section>`;
  }

  function renderInvoiceDetail(invoice, session) {
    if (invoice?.status !== 'issued') {
      return `<section aria-label="Trạng thái hóa đơn" role="status" style="margin-top:var(--space-5);">
        <h3 style="font-size:var(--font-size-sm);margin-bottom:var(--space-2);">Hóa đơn</h3>
        <p class="form-hint">${escHtml(invoice?.message || 'Chưa tải được trạng thái hóa đơn.')}</p>
      </section>`;
    }

    const invoiceSession = {
      ...session,
      cost_vnd: invoice.total_vnd,
      invoice_segments: Array.isArray(invoice.segments) ? invoice.segments : [],
      invoice_rounding_rule: invoice.rounding_rule,
      invoice_subscription_id: invoice.subscription_id,
      invoice_package_name: invoice.package_name,
    };
    return renderInvoiceBreakdown(invoiceSession);
  }

  async function openDetail(session) {
    if (!session) return;
    const requestId = ++_invoiceDetailRequest;
    const titleEl = document.getElementById('session-detail-title');
    if (titleEl) titleEl.textContent = `Chi tiết phiên sạc #${session.id}`;

    const isCompleted = !!session.ended_at;
    const hasCost = session.cost_vnd != null;

    const bodyEl = document.getElementById('session-detail-body');
    if (bodyEl) {
      bodyEl.innerHTML = `
        <dl class="session-detail-dl">
          <div class="session-detail-field">
            <dt>Trạm sạc</dt>
            <dd>${escHtml(session.station_name || '—')}</dd>
          </div>
          <div class="session-detail-field">
            <dt>Mã trụ</dt>
            <dd><code class="mono-code">${escHtml(session.charge_point_code || '—')}</code></dd>
          </div>
          ${_isGlobal ? `<div class="session-detail-field"><dt>Tài xế</dt><dd>${escHtml(session.driver_name || '—')}</dd></div>` : ''}
          <div class="session-detail-field">
            <dt>Bắt đầu</dt>
            <dd>${fmtDatetime(session.started_at)}</dd>
          </div>
          <div class="session-detail-field">
            <dt>Kết thúc</dt>
            <dd>${isCompleted ? fmtDatetime(session.ended_at) : '<span class="status-charging">Đang sạc</span>'}</dd>
          </div>
          <div class="session-detail-field">
            <dt>Điện năng</dt>
            <dd class="field-highlight">${isCompleted ? (session.kwh != null ? session.kwh.toFixed(3) + ' kWh' : '—') : (session.live_kwh != null ? session.live_kwh.toFixed(3) + ' kWh' : 'Đang sạc')}</dd>
          </div>
          <div class="session-detail-field">
            <dt>Chi phí sạc</dt>
            <dd class="field-highlight field-cost">${hasCost ? fmtVND(session.cost_vnd) : '<span class="text-muted">Chưa có cấu hình biểu giá</span>'}</dd>
          </div>
          <div class="session-detail-field">
            <dt>Trạng thái</dt>
            <dd><span class="badge ${STATUS_CLASS[session.status] || 'badge--neutral'}">${STATUS_LABEL[session.status] || 'Không rõ'}</span></dd>
          </div>
          ${session.stop_reason ? `<div class="session-detail-field session-detail-field--full"><dt>Lý do kết thúc</dt><dd>${escHtml(session.stop_reason)}</dd></div>` : ''}
        </dl><div id="session-invoice-detail"><p class="form-hint" role="status">Đang tải hóa đơn...</p></div>`;
    }
    const modal = document.getElementById('session-detail-modal');
    if (modal) modal.classList.remove('is-hidden');

    try {
      const invoice = await ApiClient.getSessionInvoice(session.id);
      if (requestId !== _invoiceDetailRequest || modal?.classList.contains('is-hidden')) return;
      const invoiceEl = bodyEl?.querySelector('#session-invoice-detail');
      if (!invoiceEl) return;
      invoiceEl.innerHTML = renderInvoiceDetail(invoice, session);
      if (invoice.status === 'issued') {
        const invoiceSession = {
          ...session,
          cost_vnd: invoice.total_vnd,
          invoice_segments: Array.isArray(invoice.segments) ? invoice.segments : [],
          invoice_rounding_rule: invoice.rounding_rule,
          invoice_subscription_id: invoice.subscription_id,
          invoice_package_name: invoice.package_name,
        };
        const costEl = bodyEl.querySelector('.field-cost');
        if (costEl) costEl.textContent = fmtVND(invoice.total_vnd);
        const invoiceButton = invoiceEl.querySelector('#btn-open-invoice');
        invoiceButton?.addEventListener('click', event => {
          event.stopPropagation();
          openInvoice(invoiceSession);
        });
      }
    } catch (error) {
      if (requestId !== _invoiceDetailRequest || modal?.classList.contains('is-hidden')) return;
      const invoiceEl = bodyEl?.querySelector('#session-invoice-detail');
      if (invoiceEl) {
        invoiceEl.innerHTML = renderInvoiceDetail({
          status: 'unavailable',
          message: error.message || 'Không thể tải hóa đơn. Vui lòng thử lại.',
        }, session);
      }
    }
  }

  // ── SCRUM-66: Modal hoá đơn E-Receipt đầy đủ ─────────────────────────────
  function openInvoice(session) {
    if (!session) return;
    const modal = document.getElementById('invoice-modal');
    if (!modal) return;

    const segments = Array.isArray(session.invoice_segments) ? session.invoice_segments : [];
    const energySegs = segments.filter(s => s.kind !== 'occupancy_fee');
    const occupancySeg = segments.find(s => s.kind === 'occupancy_fee');
    const issuedAt = session.ended_at ? new Date(session.ended_at).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';
    const totalKwh = session.kwh != null ? session.kwh.toFixed(3) : '—';
    const durationSec = session.duration_seconds || 0;
    const durationStr = fmtDuration(durationSec);

    // Dòng chi tiết từng đoạn
    const segLines = energySegs.map(seg => {
      const fromTime = seg.from ? new Date(seg.from).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' }) : '—';
      const toTime = seg.to ? new Date(seg.to).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' }) : '—';
      const kwh = parseFloat(seg.energy_kwh || 0).toFixed(3);
      return `
        <div class="receipt-line-item">
          <div class="receipt-line-left">
            <span class="receipt-band">${escHtml(seg.band || 'Khung giá')}</span>
            ${seg.tariff_name ? `<span class="receipt-detail">${escHtml(seg.tariff_name)}</span>` : ''}
            ${seg.service_date ? `<span class="receipt-detail">Ngày ${escHtml(seg.service_date)}</span>` : ''}
            <span class="receipt-timerange">${fromTime} → ${toTime}</span>
            <span class="receipt-detail">${kwh} kWh × ${fmtVND(seg.price_vnd_per_kwh)}/kWh</span>
          </div>
          <div class="receipt-line-amount">${fmtVND(seg.amount_vnd)}</div>
        </div>`;
    }).join('');

    const occupancyLine = occupancySeg ? `
      <div class="receipt-line-item receipt-occupancy">
        <div class="receipt-line-left">
          <span class="receipt-band receipt-band--occupancy">Phí chiếm trụ</span>
          <span class="receipt-detail">${escHtml(String(occupancySeg.duration_minutes || 0))} phút × ${fmtVND(occupancySeg.price_vnd_per_minute)}/phút</span>
        </div>
        <div class="receipt-line-amount">${fmtVND(occupancySeg.amount_vnd)}</div>
      </div>` : '';

    const walletNote = session.invoice_subscription_id
      ? `<div class="receipt-wallet-note receipt-wallet-note--sub">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/></svg>
          Áp dụng gói thuê bao: <strong>${escHtml(session.invoice_package_name || 'Thuê bao tháng')}</strong>
        </div>`
      : `<div class="receipt-wallet-note">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/></svg>
          Thanh toán từ Ví điện tử CSMS
        </div>`;

    const bodyEl = document.getElementById('invoice-modal-body');
    if (!bodyEl) return;
    bodyEl.innerHTML = `
      <div class="receipt-card" id="receipt-printable">
        <!-- Header hoá đơn -->
        <div class="receipt-header">
          <div class="receipt-logo" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" width="24" height="24"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
          </div>
          <div class="receipt-brand">
            <div class="receipt-brand-name">CSMS</div>
            <div class="receipt-brand-sub">EV Charging Platform</div>
          </div>
          <div class="receipt-status-badge">Hoá đơn điện tử</div>
        </div>

        <!-- Mã phiên + thời gian phát hành -->
        <div class="receipt-meta-grid">
          <div class="receipt-meta-item">
            <span class="receipt-meta-label">Mã phiên sạc</span>
            <span class="receipt-meta-value receipt-session-id">#${escHtml(String(session.id))}</span>
          </div>
          <div class="receipt-meta-item">
            <span class="receipt-meta-label">Ngày phát hành</span>
            <span class="receipt-meta-value">${issuedAt}</span>
          </div>
          <div class="receipt-meta-item">
            <span class="receipt-meta-label">Trạm sạc</span>
            <span class="receipt-meta-value">${escHtml(session.station_name || '—')}</span>
          </div>
          <div class="receipt-meta-item">
            <span class="receipt-meta-label">Mã trụ</span>
            <span class="receipt-meta-value"><code class="mono-code">${escHtml(session.charge_point_code || '—')}</code></span>
          </div>
          <div class="receipt-meta-item">
            <span class="receipt-meta-label">Thời lượng sạc</span>
            <span class="receipt-meta-value">${durationStr}</span>
          </div>
          <div class="receipt-meta-item">
            <span class="receipt-meta-label">Tổng điện năng</span>
            <span class="receipt-meta-value receipt-kwh-val">${totalKwh} kWh</span>
          </div>
        </div>

        <!-- Divider -->
        <div class="receipt-divider"></div>

        <!-- Chi tiết từng đoạn giá -->
        <div class="receipt-section-title">Chi tiết tính phí</div>
        <div class="receipt-line-items">
          ${segLines || '<div class="receipt-no-segments">Không có dữ liệu phân đoạn giá.</div>'}
          ${occupancyLine}
        </div>

        <!-- Divider -->
        <div class="receipt-divider"></div>

        <!-- Tổng tiền -->
        <div class="receipt-total-row">
          <span class="receipt-total-label">Tổng thanh toán</span>
          <span class="receipt-total-amount">${fmtVND(session.cost_vnd)}</span>
        </div>

        <!-- Ghi chú phương thức thanh toán -->
        ${walletNote}

        <!-- Ghi chú làm tròn -->
        ${session.invoice_rounding_rule ? `<div class="receipt-rounding"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg> ${escHtml(session.invoice_rounding_rule)}</div>` : ''}

        <!-- Footer hoá đơn -->
        <div class="receipt-footer">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
          Cảm ơn bạn đã sử dụng dịch vụ sạc xe điện CSMS!
        </div>
      </div>`;

    modal.classList.remove('is-hidden');
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
      ++_invoiceDetailRequest;
      document.getElementById('session-detail-modal')?.classList.add('is-hidden');
    });

    document.getElementById('session-detail-modal')?.addEventListener('click', e => {
      if (e.target === e.currentTarget) {
        ++_invoiceDetailRequest;
        e.currentTarget.classList.add('is-hidden');
      }
    });

    // SCRUM-66: Đóng modal hoá đơn E-Receipt
    document.getElementById('invoice-modal-close')?.addEventListener('click', () => {
      document.getElementById('invoice-modal')?.classList.add('is-hidden');
    });

    document.getElementById('invoice-modal')?.addEventListener('click', e => {
      if (e.target === e.currentTarget) e.currentTarget.classList.add('is-hidden');
    });

    // Modal dừng từ xa (T-50)
    document.getElementById('remote-stop-modal-cancel')?.addEventListener('click', closeStopConfirmation);
    document.getElementById('remote-stop-modal-close')?.addEventListener('click', closeStopConfirmation);
    document.getElementById('remote-stop-modal-confirm')?.addEventListener('click', executeRemoteStop);
    document.getElementById('remote-stop-modal')?.addEventListener('click', e => {
      if (e.target === e.currentTarget) closeStopConfirmation();
    });

    // Kênh realtime SSE (T-48 & T-50)
    if (_pageRoot?.dataset.liveUpdates === 'true' && window.SseClient) {
      SseClient.on('_connected', () => {
        loadSessions();
      });
      SseClient.connect('/api/monitoring/sse');
      SseClient.on('session_update', payload => {

        if (payload?.session_id == _stoppingSessionId && payload.status === 'completed') {
          clearInterval(_stopCountdownTimer);
          _stopCountdownTimer = null;
          _stoppingSessionId = null;
          setStoppingUI(_activeStopButton, false, 0);
        }

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
