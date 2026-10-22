/**
 * reservations.js — Logic quản lý đặt chỗ trụ sạc cho tài xế (SCRUM-76 / S-48)
 * Tác giả: Phạm Văn Tuấn (Frontend Developer)
 * Hỗ trợ: Tạo đặt chỗ, Đếm ngược thời gian thực, Lọc/Tìm kiếm, Tải dữ liệu đặt chỗ từ máy chủ
 */
(function () {
  'use strict';

  // Keep page state inside this IIFE. Assigning these values without declarations
  // throws in strict mode and prevents the DOM event handlers from being bound.
  let stationsTree = [];
  let reservations = [];
  let activeReservation = null;
  let reservationLoadError = null;
  let countdownTimerId = null;
  let expiryRefreshTimerId = null;

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[char]);
  }

  function formatDate(isoStr) {
    if (!isoStr) return '—';
    const d = new Date(isoStr);
    return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('vi-VN');
  }

  function formatTimeOnly(isoStr) {
    if (!isoStr) return '—';
    const d = new Date(isoStr);
    return Number.isNaN(d.getTime()) ? '—' : d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
  }

  // --- 1. Tải dữ liệu ---
  async function loadStations() {
    try {
      const result = await ApiClient.getMonitoringTree();
      stationsTree = Array.isArray(result) ? result : (result?.stations || []);
      populateStationSelect();
    } catch (err) {
      console.error('[Reservations] Không tải được danh sách trạm:', err);
      stationsTree = [];
      populateStationSelect();
      const hint = document.getElementById('station-address-hint');
      if (hint) hint.textContent = 'Không tải được danh sách trạm. Hãy làm mới trang và thử lại.';
    }
  }

  function populateStationSelect() {
    const sel = document.getElementById('select-station');
    if (!sel) return;
    sel.innerHTML = '<option value="">-- Chọn trạm sạc --</option>' +
      stationsTree.map(st => `<option value="${st.id}">${escapeHtml(st.name)} (${escapeHtml(st.address || '')})</option>`).join('');
  }

  function normalizeReservation(item) {
    const point = stationsTree.flatMap(station =>
      (station.charge_points || []).map(chargePoint => ({ station, chargePoint }))
    ).find(({ chargePoint }) => chargePoint.code === item.charge_point_code);
    const statusMap = {
      accepted: 'Active', active: 'Active', pending: 'Pending',
      completed: 'Completed', fulfilled: 'Completed', cancelled: 'Cancelled',
      expired: 'Expired', rejected: 'Rejected',
    };
    const status = String(item.status || '').toLowerCase();

    return {
      ...item,
      reservation_code: `RES-${String(item.id).padStart(6, '0')}`,
      station_id: point?.station.id ?? null,
      station_name: point?.station.name || `Trạm ${item.charge_point_id}`,
      station_address: point?.station.address || '',
      connector_type: point?.chargePoint.connectors?.find(connector =>
        Number(connector.connector_id) === Number(item.connector_id)
      )?.type || '',
      expiry_at: item.expiry_date || item.expiry_at,
      status: statusMap[status] || item.status || 'Unknown',
      no_show_fee_vnd: Number(item.no_show_fee_vnd || 0),
    };
  }

  // --- 1.1 Banner thông báo quá hạn giữ chỗ & phí no-show từ backend (SCRUM-78) ---
  function renderExpiredNotice(res) {
    const container = document.getElementById('expired-notice-container');
    if (!container) return;
    if (!res) {
      container.innerHTML = '';
      return;
    }

    const fee = Number(res.no_show_fee_vnd || 0);
    const feeLabel = `${fee.toLocaleString('vi-VN')} ₫`;

    container.innerHTML = `
      <div class="expired-alert-banner" role="alert">
        <div class="expired-alert-banner__content">
          <div class="expired-alert-banner__icon" aria-hidden="true">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
          </div>
          <div>
            <h3 class="expired-alert-banner__title">ĐẶT CHỖ QUÁ HẠN — ĐÃ MỞ LẠI TRỤ CHO TÀI XẾ KHÁC</h3>
            <p class="expired-alert-banner__desc">
              Lượt đặt chỗ <strong>${escapeHtml(res.reservation_code)}</strong> tại <strong>${escapeHtml(res.station_name)}</strong> đã quá thời gian giữ chỗ lúc <strong>${formatTimeOnly(res.expiry_at)}</strong>.
              Trạng thái và phí không đến thực tế: <strong>${feeLabel}</strong>${fee > 0 ? ' đã được ghi nhận vào ví.' : ' (được miễn hoặc không phát sinh).'}
            </p>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:var(--space-2);flex-shrink:0;">
          ${fee > 0 ? `<a href="/wallet" class="btn btn--secondary btn--sm" style="display:inline-flex;align-items:center;gap:4px;font-weight:600;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/>
            </svg>
            Biến động ví (-${feeLabel})
          </a>` : ''}
          <button type="button" class="btn btn--secondary btn--sm" id="btn-dismiss-expired-notice" title="Đóng thông báo" style="padding:4px 8px;">
            ✕
          </button>
        </div>
      </div>
    `;

    document.getElementById('btn-dismiss-expired-notice')?.addEventListener('click', () => {
      container.innerHTML = '';
    });
  }

  async function loadReservations() {
    try {
      const res = await ApiClient.listReservations();
      reservationLoadError = null;
      reservations = (Array.isArray(res) ? res : (res?.items || [])).map(normalizeReservation);
    } catch (err) {
      reservationLoadError = err?.message || 'Không thể tải danh sách đặt chỗ từ máy chủ.';
      reservations = [];
      console.error('[Reservations] Không tải được đặt chỗ từ máy chủ:', err);
    }

    const latestExpired = reservations.find(r => r.status === 'Expired');
    renderExpiredNotice(latestExpired || null);

    // Tìm đặt chỗ đang hoạt động
    activeReservation = reservations.find(r => r.status === 'Active') || null;

    renderActiveReservation();
    renderStats();
    renderTable();
  }

  // --- 2. Render Giao diện ---
  function renderActiveReservation() {
    const container = document.getElementById('active-res-container');
    if (!container) return;

    if (!activeReservation) {
      container.innerHTML = `
        <div class="empty-res-card">
          <div class="empty-res-card__icon" aria-hidden="true">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
              <line x1="16" y1="2" x2="16" y2="6"/>
              <line x1="8" y1="2" x2="8" y2="6"/>
              <line x1="3" y1="10" x2="21" y2="10"/>
            </svg>
          </div>
          <h3 class="empty-res-card__title">Bạn chưa có lượt đặt chỗ nào đang giữ</h3>
          <p class="empty-res-card__desc">
            Đặt trước vị trí sạc để xe của bạn luôn có cổng sạc sẵn sàng khi đến trạm mà không cần phải chờ đợi.
          </p>
          <button class="btn btn--primary" id="btn-empty-create" type="button">
            Đặt chỗ ngay bây giờ
          </button>
        </div>
      `;
      document.getElementById('btn-empty-create')?.addEventListener('click', openReserveModal);
      stopCountdown();
      return;
    }

    // Có đặt chỗ đang Active -> Render Hero Card
    container.innerHTML = `
      <section class="active-res-card" aria-label="Lượt đặt chỗ đang hiệu lực">
        <div class="active-res-card__header">
          <div class="active-res-card__badge-wrap">
            <span class="res-pulse-dot" aria-hidden="true"></span>
            <strong style="color:var(--color-primary);font-size:var(--font-size-base);">LƯỢT ĐẶT CHỖ HIỆU LỰC</strong>
            <span class="badge badge--res-active">Mã: ${escapeHtml(activeReservation.reservation_code)}</span>
          </div>
          <span style="font-size:var(--font-size-xs);color:var(--color-text-secondary);">
            Tạo lúc: ${formatDate(activeReservation.created_at)}
          </span>
        </div>

        <div class="active-res-card__grid">
          <div class="active-res-details">
            <h2 class="active-res-station">${escapeHtml(activeReservation.station_name)}</h2>
            <div class="active-res-address">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
              </svg>
              <span>${escapeHtml(activeReservation.station_address || 'Địa chỉ đang cập nhật')}</span>
            </div>

            <div class="active-res-meta">
              <span class="meta-chip">
                <strong>Trụ sạc:</strong> ${escapeHtml(activeReservation.charge_point_code)}
              </span>
              <span class="meta-chip">
                <strong>Đầu nối:</strong> Cổng #${escapeHtml(activeReservation.connector_id)}
              </span>
              <span class="meta-chip" style="color:var(--color-primary);font-weight:600;">
                <span class="badge badge--warning" style="padding:2px 8px;font-size:11px;">Reserved</span> Trụ đã khóa cho bạn
              </span>
            </div>
          </div>

          <div class="countdown-box">
            <div class="countdown-box__label">Thời gian giữ chỗ còn lại</div>
            <div class="countdown-box__time" id="active-res-countdown">--:--</div>
            <div class="countdown-box__hint">
              Hạn đến: <strong>${formatTimeOnly(activeReservation.expiry_at)}</strong> hôm nay
            </div>
          </div>
        </div>

        <div class="active-res-actions">
          <a href="/monitoring" class="btn btn--primary">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
            </svg>
            Xem trạm & Bắt đầu sạc
          </a>
          <button class="btn btn--secondary" type="button" id="btn-cancel-active-res" data-id="${activeReservation.id}" style="color:var(--color-danger, #ef4444);">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
            </svg>
            Hủy đặt chỗ này
          </button>
        </div>
      </section>
    `;

    document.getElementById('btn-cancel-active-res')?.addEventListener('click', () => {
      openCancelModal(activeReservation.id);
    });

    startCountdown();
  }

  function startCountdown() {
    stopCountdown();
    updateCountdownDisplay();
    countdownTimerId = setInterval(updateCountdownDisplay, 1000);
  }

  function stopCountdown() {
    if (countdownTimerId) {
      clearInterval(countdownTimerId);
      countdownTimerId = null;
    }
  }

  function updateCountdownDisplay() {
    const el = document.getElementById('active-res-countdown');
    if (!el || !activeReservation) return;

    const remainingMs = new Date(activeReservation.expiry_at).getTime() - Date.now();
    if (remainingMs <= 0) {
      el.textContent = 'Đang cập nhật';
      el.style.color = '#ef4444';
      stopCountdown();
      if (!expiryRefreshTimerId) {
        expiryRefreshTimerId = setTimeout(async () => {
          expiryRefreshTimerId = null;
          await loadReservations();
        }, 3000);
      }
      return;
    }

    const totalSeconds = Math.floor(remainingMs / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    el.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  }

  function renderStats() {
    const active = reservations.filter(r => r.status === 'Active').length;
    const completed = reservations.filter(r => r.status === 'Completed').length;
    const cancelled = reservations.filter(r => r.status === 'Cancelled').length;
    const expired = reservations.filter(r => r.status === 'Expired').length;

    const elAct = document.getElementById('stat-active');
    const elComp = document.getElementById('stat-completed');
    const elCanc = document.getElementById('stat-cancelled');
    const elExp = document.getElementById('stat-expired');

    if (elAct) elAct.textContent = active;
    if (elComp) elComp.textContent = completed;
    if (elCanc) elCanc.textContent = cancelled;
    if (elExp) elExp.textContent = expired;
  }

  function renderTable() {
    const tbody = document.getElementById('res-table-body');
    if (!tbody) return;

    const query = document.getElementById('search-res')?.value.trim().toLowerCase() || '';
    const statusFilter = document.getElementById('filter-res-status')?.value || '';

    if (reservationLoadError) {
      tbody.innerHTML = `<tr><td colspan="7" class="table__empty" role="alert" style="text-align:center;padding:var(--space-6);color:var(--color-danger);">Không tải được dữ liệu đặt chỗ: ${escapeHtml(reservationLoadError)}</td></tr>`;
      return;
    }

    const filtered = reservations.filter(r => {
      if (statusFilter && r.status !== statusFilter) return false;
      if (query) {
        const text = `${r.reservation_code} ${r.station_name} ${r.charge_point_code}`.toLowerCase();
        return text.includes(query);
      }
      return true;
    });

    if (filtered.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="table__empty" style="text-align:center;padding:var(--space-6);">
            <p style="color:var(--color-text-secondary);margin:0;">Không tìm thấy lượt đặt chỗ nào phù hợp.</p>
          </td>
        </tr>
      `;
      return;
    }

    const badgeMap = {
      Active: ['Đang giữ chỗ', 'badge--res-active'],
      Completed: ['Đã sử dụng', 'badge--res-completed'],
      Cancelled: ['Đã hủy', 'badge--res-cancelled'],
      Expired: ['Quá hạn', 'badge--res-expired']
    };

    tbody.innerHTML = filtered.map(r => {
      const [statusLabel, badgeClass] = badgeMap[r.status] || [r.status, 'badge--neutral'];
      const isAct = r.status === 'Active';

      return `
        <tr>
          <td><strong style="color:var(--color-primary);">${escapeHtml(r.reservation_code)}</strong></td>
          <td>
            <div><strong>${escapeHtml(r.station_name)}</strong></div>
            <div style="font-size:var(--font-size-xs);color:var(--color-text-secondary);">${escapeHtml(r.station_address || '')}</div>
          </td>
          <td>
            <span class="badge badge--neutral">${escapeHtml(r.charge_point_code)}</span>
            <span style="font-size:var(--font-size-xs);margin-left:4px;">Cổng #${escapeHtml(r.connector_id)}</span>
          </td>
          <td>${formatDate(r.created_at)}</td>
          <td>
            <strong style="color:${isAct ? 'var(--color-primary)' : 'inherit'};">
              ${formatTimeOnly(r.expiry_at)}
            </strong>
            ${r.status === 'Expired' && r.no_show_fee_vnd > 0 ? `
              <div style="margin-top:2px;">
                <span class="no-show-badge" title="Phí phạt giữ chỗ không đến: -${Number(r.no_show_fee_vnd).toLocaleString('vi-VN')} ₫">-${Number(r.no_show_fee_vnd).toLocaleString('vi-VN')} ₫</span>
              </div>
            ` : ''}
          </td>
          <td><span class="badge ${badgeClass}">${statusLabel}</span></td>
          <td style="text-align:right;">
            <div style="display:inline-flex;gap:var(--space-2);align-items:center;">
              <button class="btn btn--secondary btn--sm btn-view-detail" type="button" data-id="${r.id}" title="Xem chi tiết">
                Chi tiết
              </button>
              ${isAct ? `
                <button class="btn btn--secondary btn--sm btn-cancel-row" type="button" data-id="${r.id}" style="color:#ef4444;" title="Hủy đặt chỗ">
                  Hủy
                </button>
              ` : ''}
              ${r.status === 'Expired' && r.no_show_fee_vnd > 0 ? `
                <a href="/wallet" class="btn btn--secondary btn--sm" style="font-size:11px;padding:3px 8px;color:var(--color-primary);" title="Xem trừ phí phạt trong ví">
                  Ví
                </a>
              ` : ''}
            </div>
          </td>
        </tr>
      `;
    }).join('');

    tbody.querySelectorAll('.btn-view-detail').forEach(btn => {
      btn.addEventListener('click', () => openDetailModal(Number(btn.dataset.id)));
    });

    tbody.querySelectorAll('.btn-cancel-row').forEach(btn => {
      btn.addEventListener('click', () => openCancelModal(Number(btn.dataset.id)));
    });
  }

  // --- 3. Modal Đặt chỗ mới ---
  function openReserveModal() {
    const modal = document.getElementById('modal-reserve-new');
    if (!modal) return;

    // Reset form
    document.getElementById('form-reserve-new')?.reset();
    document.getElementById('select-charge-point').innerHTML = '<option value="">-- Vui lòng chọn trạm trước --</option>';
    document.getElementById('select-charge-point').disabled = true;
    document.getElementById('reserve-feedback').innerHTML = '';
    document.getElementById('station-address-hint').textContent = 'Chọn trạm xe điện bạn muốn đến sạc';

    // Đặt mặc định 30 phút
    selectMinutes(30);

    modal.classList.remove('is-hidden');
  }

  function closeReserveModal() {
    document.getElementById('modal-reserve-new')?.classList.add('is-hidden');
  }

  function selectMinutes(mins) {
    document.getElementById('input-arrival-minutes').value = mins;
    document.querySelectorAll('.time-chip-btn').forEach(btn => {
      btn.classList.toggle('is-selected', Number(btn.dataset.minutes) === Number(mins));
    });

    // Cập nhật giờ mục tiêu
    const target = new Date(Date.now() + mins * 60 * 1000);
    const timeStr = target.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
    document.getElementById('display-expiry-target').textContent = `${timeStr} (sau ${mins} phút)`;
  }

  function onStationChanged() {
    const stationId = Number(document.getElementById('select-station').value);
    const cpSelect = document.getElementById('select-charge-point');
    const addrHint = document.getElementById('station-address-hint');

    if (!stationId) {
      cpSelect.innerHTML = '<option value="">-- Vui lòng chọn trạm trước --</option>';
      cpSelect.disabled = true;
      addrHint.textContent = 'Chọn trạm xe điện bạn muốn đến sạc';
      return;
    }

    const station = stationsTree.find(s => s.id === stationId);
    if (!station) return;

    addrHint.textContent = station.address || 'Địa chỉ trạm';

    // Tìm các đầu nối khả dụng (Available / rảnh)
    const options = [];
    (station.charge_points || []).forEach(cp => {
      if (cp.status === 'offline') return;
      (cp.connectors || []).forEach(conn => {
        const isAvail = (conn.ocpp_status ? conn.ocpp_status === 'Available' : conn.status === 'rảnh');
        if (isAvail) {
          options.push(`
            <option value="${escapeHtml(cp.code)}|${escapeHtml(conn.connector_id)}">
              Trụ ${escapeHtml(cp.code)} — Cổng #${escapeHtml(conn.connector_id)} (${escapeHtml(conn.type || 'Sạc nhanh')})
            </option>
          `);
        }
      });
    });

    if (options.length === 0) {
      cpSelect.innerHTML = '<option value="">-- Trạm này hiện không còn đầu nối rảnh --</option>';
      cpSelect.disabled = true;
    } else {
      cpSelect.innerHTML = '<option value="">-- Chọn đầu nối khả dụng --</option>' + options.join('');
      cpSelect.disabled = false;
    }
  }

  // --- SCRUM-77 (S-49): Xử lý tranh chấp đặt chỗ đồng thời & Gợi ý trụ khác ---
  function findAlternativeConnectors(currentStationId, excludeCpCode, excludeConnId) {
    const suggestions = [];
    const currentStation = stationsTree.find(s => s.id === currentStationId);

    // 1. Tìm các đầu nối khác trong cùng trạm trước
    if (currentStation) {
      (currentStation.charge_points || []).forEach(cp => {
        if (cp.status === 'offline') return;
        (cp.connectors || []).forEach(conn => {
          if (cp.code === excludeCpCode && Number(conn.connector_id) === Number(excludeConnId)) {
            return; // Bỏ qua đầu nối đang bị xung đột
          }
          const isAvail = (conn.ocpp_status ? conn.ocpp_status === 'Available' : conn.status === 'rảnh');
          if (isAvail) {
            suggestions.push({
              station_id: currentStation.id,
              station_name: currentStation.name,
              charge_point_code: cp.code,
              connector_id: conn.connector_id,
              type: conn.type || 'CCS2 (60kW)',
              is_same_station: true
            });
          }
        });
      });
    }

    // 2. Nếu cùng trạm ít lựa chọn, quét thêm các trạm lân cận trong hệ thống
    if (suggestions.length < 3) {
      stationsTree.forEach(st => {
        if (st.id === currentStationId) return;
        (st.charge_points || []).forEach(cp => {
          if (cp.status === 'offline') return;
          (cp.connectors || []).forEach(conn => {
            const isAvail = (conn.ocpp_status ? conn.ocpp_status === 'Available' : conn.status === 'rảnh');
            if (isAvail && suggestions.length < 4) {
              suggestions.push({
                station_id: st.id,
                station_name: st.name,
                charge_point_code: cp.code,
                connector_id: conn.connector_id,
                type: conn.type || 'CCS2 (60kW)',
                is_same_station: false
              });
            }
          });
        });
      });
    }

    return suggestions;
  }

  function renderConflictAlert(errorMessage, stationId, cpCode, connId) {
    const feedback = document.getElementById('reserve-feedback');
    if (!feedback) return;

    const alternatives = findAlternativeConnectors(stationId, cpCode, connId);

    let suggestionsHtml = '';
    if (alternatives.length > 0) {
      suggestionsHtml = `
        <div class="suggestion-section">
          <div class="suggestion-section__title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 14 14"/>
            </svg>
            Gợi ý các vị trí sạc khả dụng thay thế
          </div>
          <div class="suggestion-list">
            ${alternatives.map(alt => `
              <div class="suggestion-item">
                <div class="suggestion-item__info">
                  <span class="badge badge--available" style="font-size:10px;padding:1px 6px;">Rảnh</span>
                  <div>
                    <span class="suggestion-item__cp">${escapeHtml(alt.charge_point_code)} - Cổng #${escapeHtml(alt.connector_id)}</span>
                    <span class="suggestion-item__type">(${escapeHtml(alt.type)}${alt.is_same_station ? '' : ` • ${escapeHtml(alt.station_name)}`})</span>
                  </div>
                </div>
                <button type="button" class="btn btn--primary btn-select-suggested"
                        data-station-id="${alt.station_id}"
                        data-cp-code="${escapeHtml(alt.charge_point_code)}"
                        data-connector-id="${alt.connector_id}">
                  Đặt vị trí này
                </button>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    } else {
      suggestionsHtml = `
        <div class="suggestion-section" style="color:var(--color-text-secondary);font-size:var(--font-size-xs);">
          Hiện tại tất cả các trụ sạc khác tại trạm cũng đang bận hoặc ngoại tuyến. Vui lòng chọn trạm khác trong danh sách.
        </div>
      `;
    }

    feedback.innerHTML = `
      <div class="conflict-alert" role="alert">
        <div class="conflict-alert__header">
          <div class="conflict-alert__icon" aria-hidden="true">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
          </div>
          <div>
            <h4 class="conflict-alert__title">Trùng lịch đặt chỗ! Vị trí vừa có người đặt</h4>
            <p class="conflict-alert__desc">${escapeHtml(errorMessage || 'Đầu nối này vừa được một tài xế khác hoàn tất đặt chỗ trước bạn vài phần trăm giây. Để không làm gián đoạn chuyến đi, bạn có thể chọn ngay một trong các vị trí sạc còn trống bên dưới.')}</p>
          </div>
        </div>
        ${suggestionsHtml}
      </div>
    `;

    // Gắn sự kiện cho các nút "Đặt vị trí này" để chuyển nhanh đầu nối
    feedback.querySelectorAll('.btn-select-suggested').forEach(btn => {
      btn.addEventListener('click', () => {
        const targetStId = Number(btn.dataset.stationId);
        const targetCpCode = btn.dataset.cpCode;
        const targetConnId = Number(btn.dataset.connectorId);

        if (Number(document.getElementById('select-station').value) !== targetStId) {
          document.getElementById('select-station').value = targetStId;
          onStationChanged();
        }

        setTimeout(() => {
          const cpSelect = document.getElementById('select-charge-point');
          cpSelect.value = `${targetCpCode}|${targetConnId}`;
          feedback.innerHTML = `
            <div class="alert alert--info" style="animation:resFadeIn 0.2s ease;">
              ✓ Đã tự động chuyển lựa chọn sang <strong>Trụ ${escapeHtml(targetCpCode)} — Cổng #${targetConnId}</strong>. Bấm nút <strong>"Xác nhận đặt chỗ"</strong> bên dưới để hoàn tất!
            </div>
          `;
          // Tắt toggle mô phỏng để lần bấm kế tiếp thành công
          const simToggle = document.getElementById('simulate-conflict-toggle');
          if (simToggle) simToggle.checked = false;
        }, 150);
      });
    });
  }

  async function handleReserveSubmit(e) {
    e.preventDefault();
    const feedback = document.getElementById('reserve-feedback');
    const submitBtn = document.getElementById('btn-submit-reserve');
    const stationId = Number(document.getElementById('select-station').value);
    const cpConnVal = document.getElementById('select-charge-point').value;
    const mins = Number(document.getElementById('input-arrival-minutes').value) || 30;
    const simulateConflict = document.getElementById('simulate-conflict-toggle')?.checked === true;

    if (!stationId || !cpConnVal) {
      feedback.innerHTML = '<div class="alert alert--danger">Vui lòng chọn trạm và đầu nối còn trống.</div>';
      return;
    }

    const [cpCode, connIdStr] = cpConnVal.split('|');
    const connectorId = Number(connIdStr);

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<div class="spinner spinner--sm"></div> Đang kiểm tra & gửi ReserveNow...';
    feedback.innerHTML = '<div class="alert alert--info">Hệ thống đang kiểm tra tính khả dụng và gửi bản tin ReserveNow tới trụ sạc...</div>';

    const payload = {
      charge_point_code: cpCode,
      connector_id: connectorId,
      expiry_minutes: mins,
      start_time: new Date().toISOString(),
    };

    try {
      // 1. Kiểm tra kịch bản giả lập tranh chấp (Conflict Simulation - SCRUM-77)
      if (simulateConflict) {
        await new Promise(r => setTimeout(r, 600)); // Delay nhẹ như mạng thật
        throw {
          status: 409,
          code: 'reservation_conflict',
          message: 'Vị trí này vừa được một tài xế khác hoàn tất đặt trước bạn 0.2 giây (Giả lập tranh chấp đồng thời).'
        };
      }

      const response = await ApiClient.createReservation(payload);
      if (response.status !== 'Accepted' || !response.reservation) {
        throw { status: 409, message: response.message || 'Trụ sạc chưa chấp nhận đặt chỗ.' };
      }
      const result = normalizeReservation(response.reservation);
      result.message = response.message;

      // Lưu vào danh sách
      reservations.unshift(result);

      feedback.innerHTML = `<div class="alert alert--success">${escapeHtml(result.message || 'Đặt chỗ thành công! Trụ đã chuyển sang trạng thái Reserved.')}</div>`;

      setTimeout(() => {
        closeReserveModal();
        loadReservations();
        if (typeof showToast === 'function') {
          showToast(`Đặt chỗ thành công mã ${result.reservation_code}.`, 'success');
        }
      }, 700);

    } catch (err) {
      if (err.status === 409) {
        renderConflictAlert(err.message, stationId, cpCode, connectorId);
        if (typeof showToast === 'function') {
          showToast('Trùng vị trí: Đã có người đặt trước bạn!', 'warning');
        }
      } else {
        const msg = err.message || 'Không thể tạo đặt chỗ. Vui lòng thử lại.';
        feedback.innerHTML = `<div class="alert alert--danger"><strong>Lỗi:</strong> ${escapeHtml(msg)}</div>`;
      }
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
        Xác nhận đặt chỗ
      `;
    }
  }

  // --- 4. Hủy đặt chỗ (SCRUM-79 / S-51) ---
  function openCancelModal(id) {
    const res = reservations.find(r => r.id === id);
    if (!res) return;

    if (res.status === 'Expired') {
      alert('Không thể hủy lượt đặt chỗ đã quá hạn vì hệ thống đã tự động mở lại trụ và tính phí không đến.');
      return;
    }
    if (res.status === 'Cancelled' || res.status === 'Completed') {
      return;
    }

    const modal = document.getElementById('modal-cancel-confirm');
    if (!modal) return;

    document.getElementById('cancel-reservation-id').value = res.id;
    document.getElementById('cancel-code-display').textContent = res.reservation_code;
    document.getElementById('cancel-station-display').textContent = res.station_name;
    document.getElementById('cancel-cp-display').textContent = `Trụ ${res.charge_point_code} — Cổng #${res.connector_id} (${res.connector_type || 'CCS2'})`;
    document.getElementById('cancel-feedback').innerHTML = '';
    const confirmBtn = document.getElementById('btn-confirm-cancel-submit');
    if (confirmBtn) {
      confirmBtn.disabled = false;
      confirmBtn.innerHTML = 'Xác nhận hủy đặt chỗ';
    }

    modal.classList.remove('is-hidden');
  }

  function closeCancelModal() {
    document.getElementById('modal-cancel-confirm')?.classList.add('is-hidden');
  }

  async function handleCancelSubmit(e) {
    e.preventDefault();
    const id = Number(document.getElementById('cancel-reservation-id').value);
    const reason = document.getElementById('select-cancel-reason')?.value || 'Thay đổi kế hoạch di chuyển';
    const feedback = document.getElementById('cancel-feedback');
    const submitBtn = document.getElementById('btn-confirm-cancel-submit');

    const res = reservations.find(r => r.id === id);
    if (!res) return;

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<div class="spinner spinner--sm"></div> Đang gửi lệnh OCPP CancelReservation...';
    feedback.innerHTML = '<div class="alert alert--info">Đang gửi bản tin CancelReservation tới trạm sạc để giải phóng đầu nối...</div>';

    try {
      const result = await ApiClient.cancelReservation(id, { reason });
      const pending = result.cancel_status === 'pending';
      feedback.innerHTML = pending
        ? '<div class="alert alert--warning">Đã ghi nhận yêu cầu hủy. Đang chờ trụ xác nhận giải phóng đầu nối.</div>'
        : '<div class="alert alert--success">Đã hủy đặt chỗ thành công. Trạng thái được đồng bộ từ máy chủ.</div>';

      setTimeout(() => {
        closeCancelModal();
        loadReservations();
        if (typeof showToast === 'function') {
          showToast(`Đã gửi yêu cầu hủy ${res.reservation_code}.`, pending ? 'warning' : 'success');
        }
      }, 600);
    } catch (err) {
      feedback.innerHTML = `<div class="alert alert--danger">Lỗi khi hủy đặt chỗ: ${escapeHtml(err.message || 'Có lỗi xảy ra')}</div>`;
      submitBtn.disabled = false;
      submitBtn.textContent = 'Xác nhận hủy đặt chỗ';
    }
  }

  // --- 5. Modal Chi tiết (Tích hợp SCRUM-78 & SCRUM-79) ---
  function openDetailModal(id) {
    const res = reservations.find(r => r.id === id);
    if (!res) return;

    const body = document.getElementById('detail-modal-body');
    if (!body) return;

    const isExpired = res.status === 'Expired';
    const isCancelled = res.status === 'Cancelled';
    const isActive = res.status === 'Active';

    let extraBannerHtml = '';
    if (isExpired) {
      const fee = Number(res.no_show_fee_vnd || 0);
      const feeLabel = `${fee.toLocaleString('vi-VN')} ₫`;
      extraBannerHtml = `
        <div class="alert alert--danger" style="margin-top:var(--space-3);border-radius:var(--radius-md);display:flex;align-items:flex-start;gap:var(--space-2);">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;color:#dc2626;">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <div>
            <strong>Đặt chỗ đã quá hạn:</strong> Lượt đặt chỗ hết hạn lúc ${formatDate(res.expiry_at)}. Phí không đến ghi nhận thực tế: <strong>${feeLabel}</strong>${fee > 0 ? ' (đã trừ vào ví).' : ' (được miễn hoặc không phát sinh).'}
          </div>
        </div>
        ${fee > 0 ? `<div style="margin-top:var(--space-2);text-align:right;">
          <a href="/wallet" class="btn btn--secondary btn--sm" style="display:inline-flex;align-items:center;gap:6px;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>
            Xem lịch sử trừ ví (-${feeLabel})
          </a>
        </div>` : ''}
      `;
    } else if (isCancelled) {
      const cancelStatusLabel = {
        done: 'Trụ đã xác nhận hủy',
        pending: 'Đang chờ trụ xác nhận hủy',
        gone: 'Trụ không còn reservation này',
        abandoned: 'Đã dừng gửi lại lệnh hủy',
      }[res.cancel_status] || 'Đã ghi nhận hủy trên hệ thống';
      extraBannerHtml = `
        <div class="alert alert--info" style="margin-top:var(--space-3);border-radius:var(--radius-md);display:flex;align-items:flex-start;gap:var(--space-2);">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;color:#0284c7;">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
          </svg>
          <div>
            <strong>Đã hủy chủ động trước hạn:</strong> Lượt đặt chỗ đã hủy lúc ${formatDate(res.cancelled_at || res.expiry_at)}. ${escapeHtml(cancelStatusLabel)}. Phí hủy: <strong>0 ₫</strong>.
          </div>
        </div>
      `;
    }

    body.innerHTML = `
      <div class="reservation-detail-grid">
        <div class="reservation-detail-item reservation-detail-item--code">
          <span class="reservation-detail-item__label">Mã đặt chỗ</span>
          <strong>${escapeHtml(res.reservation_code)}</strong>
        </div>
        <div class="reservation-detail-item">
          <span class="reservation-detail-item__label">Trạng thái</span>
          <span class="badge badge--res-${res.status.toLowerCase()}">${escapeHtml(res.status)}</span>
        </div>
        <div class="reservation-detail-item">
          <span class="reservation-detail-item__label">Phản hồi OCPP</span>
          <strong>${escapeHtml(res.ocpp_status || 'Accepted')}</strong>
        </div>
        <div class="reservation-detail-item reservation-detail-item--wide">
          <span class="reservation-detail-item__label">Trạm sạc</span>
          <strong>${escapeHtml(res.station_name)}</strong>
          <div style="font-size:var(--font-size-sm);color:var(--color-text-secondary);">${escapeHtml(res.station_address || '')}</div>
        </div>
        <div class="reservation-detail-item">
          <span class="reservation-detail-item__label">Trụ sạc</span>
          <strong>${escapeHtml(res.charge_point_code)}</strong>
        </div>
        <div class="reservation-detail-item">
          <span class="reservation-detail-item__label">Cổng sạc</span>
          <strong>Cổng #${escapeHtml(res.connector_id)}</strong> (${escapeHtml(res.connector_type || 'CCS2')})
        </div>
        <div class="reservation-detail-item">
          <span class="reservation-detail-item__label">Thời điểm đặt</span>
          <span>${formatDate(res.created_at)}</span>
        </div>
        <div class="reservation-detail-item">
          <span class="reservation-detail-item__label">Hạn giữ chỗ</span>
          <strong style="color:var(--color-primary);">${formatDate(res.expiry_at)}</strong>
        </div>
        ${extraBannerHtml ? `<div class="reservation-detail-wide">${extraBannerHtml}</div>` : ''}
        ${isActive ? `
          <div class="reservation-detail-wide reservation-detail-actions">
            <button class="btn btn--danger btn--sm" id="btn-cancel-from-detail" type="button" style="background-color:#ef4444;color:white;border-color:#ef4444;">
              Hủy đặt chỗ này
            </button>
          </div>
        ` : ''}
      </div>
    `;

    document.getElementById('btn-cancel-from-detail')?.addEventListener('click', () => {
      closeDetailModal();
      openCancelModal(res.id);
    });

    document.getElementById('modal-res-detail')?.classList.remove('is-hidden');
  }

  function closeDetailModal() {
    document.getElementById('modal-res-detail')?.classList.add('is-hidden');
  }

  // --- Khởi tạo sự kiện ---
  document.addEventListener('DOMContentLoaded', async () => {
    // Nút mở modal đặt chỗ
    document.getElementById('btn-open-reserve-modal')?.addEventListener('click', openReserveModal);
    document.getElementById('btn-close-reserve-modal')?.addEventListener('click', closeReserveModal);
    document.getElementById('modal-reserve-backdrop')?.addEventListener('click', closeReserveModal);
    document.getElementById('btn-cancel-reserve-dialog')?.addEventListener('click', closeReserveModal);

    // Modal chi tiết
    document.getElementById('btn-close-detail-modal')?.addEventListener('click', closeDetailModal);
    document.getElementById('modal-detail-backdrop')?.addEventListener('click', closeDetailModal);
    document.getElementById('btn-detail-close')?.addEventListener('click', closeDetailModal);

    // Modal hủy đặt chỗ (SCRUM-79)
    document.getElementById('btn-close-cancel-modal')?.addEventListener('click', closeCancelModal);
    document.getElementById('modal-cancel-backdrop')?.addEventListener('click', closeCancelModal);
    document.getElementById('btn-cancel-dialog-dismiss')?.addEventListener('click', closeCancelModal);
    document.getElementById('form-cancel-reservation')?.addEventListener('submit', handleCancelSubmit);

    // Chọn trạm trong form
    document.getElementById('select-station')?.addEventListener('change', onStationChanged);

    // Chọn chip thời gian
    document.querySelectorAll('.time-chip-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        selectMinutes(Number(btn.dataset.minutes));
      });
    });

    // Submit form đặt chỗ
    document.getElementById('form-reserve-new')?.addEventListener('submit', handleReserveSubmit);

    // Tìm kiếm và lọc
    document.getElementById('search-res')?.addEventListener('input', renderTable);
    document.getElementById('filter-res-status')?.addEventListener('change', renderTable);
    document.getElementById('btn-refresh-res')?.addEventListener('click', loadReservations);

    // Gắn sự kiện trước khi gọi API để trang vẫn phản hồi nếu máy chủ chậm.
    await loadStations();
    await loadReservations();

    // Xử lý query param nếu điều hướng từ monitoring (ví dụ: ?action=reserve&station_id=1&cp_code=CP_VINCOM_01)
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('action') === 'reserve') {
      openReserveModal();
      const stId = urlParams.get('station_id');
      if (stId) {
        document.getElementById('select-station').value = stId;
        onStationChanged();
        const cpCode = urlParams.get('cp_code');
        const connId = urlParams.get('connector_id') || '1';
        if (cpCode) {
          setTimeout(() => {
            document.getElementById('select-charge-point').value = `${cpCode}|${connId}`;
          }, 100);
        }
      }
    }
  });

})();
