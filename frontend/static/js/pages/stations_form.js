/**
 * pages/stations_form.js — JS trang tạo/sửa trạm (T-09, SCRUM-105)
 * Giới hạn: ~100 dòng — logic dùng lại (FormGuard, ApiClient) ở shared files.
 * Mọi gọi API đi qua ApiClient — không rải fetch trực tiếp.
 */
(function () {
  'use strict';

  const isEdit     = !!document.querySelector('[name="station_id"]');
  const stationId  = document.querySelector('[name="station_id"]')?.value || null;

  const tariffCard = document.getElementById('station-tariff-card');
  if (tariffCard) {
    const tariffForm = document.getElementById('station-tariff-form');
    const history = document.getElementById('station-tariff-history');
    const message = document.getElementById('station-tariff-message');
    const submit = document.getElementById('tariff-submit');
    const path = `/stations/${tariffCard.dataset.stationId}/tariffs`;
    const money = amount => new Intl.NumberFormat('vi-VN').format(amount) + ' đ';

    // ── Quản lý chế độ biểu giá (Cố định vs Nhiều khung giờ) ──
    let currentTariffMode = 'flat'; // 'flat' | 'time_bands'
    const typeFlatRadio = document.getElementById('tariff-type-flat');
    const typeBandsRadio = document.getElementById('tariff-type-bands');
    const labelFlat = document.getElementById('label-type-flat');
    const labelBands = document.getElementById('label-type-bands');
    const flatSection = document.getElementById('tariff-flat-section');
    const bandsSection = document.getElementById('tariff-bands-section');
    const tariffPriceInput = document.getElementById('tariff-price');

    // Mẫu 3 khung giờ chuẩn 24h hệ thống CSMS (Thấp điểm, Tiêu chuẩn, Cao điểm)
    const STANDARD_PRESET_BANDS = [
      { label: 'Thấp điểm', startTime: '00:00', endTime: '06:00', price: 3000 },
      { label: 'Tiêu chuẩn', startTime: '06:00', endTime: '17:00', price: 4000 },
      { label: 'Cao điểm',  startTime: '17:00', endTime: '22:00', price: 5000 },
      { label: 'Thấp điểm', startTime: '22:00', endTime: '24:00', price: 3000 },
    ];

    let timeBands = JSON.parse(JSON.stringify(STANDARD_PRESET_BANDS));

    // ── Helper thời gian và phút ──
    function timeToMinute(str) {
      if (!str) return null;
      const s = String(str).trim();
      if (s === '24:00') return 1440;
      const parts = s.split(':');
      if (parts.length < 2) return null;
      const h = parseInt(parts[0], 10);
      const m = parseInt(parts[1], 10);
      if (isNaN(h) || isNaN(m)) return null;
      if (h === 24 && m === 0) return 1440;
      if (h < 0 || h >= 24 || m < 0 || m >= 60) return null;
      return h * 60 + m;
    }

    function minuteToTime(minute) {
      if (minute == null) return '—';
      if (minute >= 1440) return '24:00';
      const h = Math.floor(minute / 60);
      const m = minute % 60;
      return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
    }

    // Chuyển đổi giữa 2 chế độ
    function setTariffMode(mode) {
      currentTariffMode = mode;
      if (mode === 'flat') {
        typeFlatRadio.checked = true;
        labelFlat?.classList.add('is-active');
        labelBands?.classList.remove('is-active');
        flatSection?.classList.remove('is-hidden');
        bandsSection?.classList.add('is-hidden');
        if (tariffPriceInput) tariffPriceInput.required = true;
      } else {
        typeBandsRadio.checked = true;
        labelBands?.classList.add('is-active');
        labelFlat?.classList.remove('is-active');
        flatSection?.classList.add('is-hidden');
        bandsSection?.classList.remove('is-hidden');
        if (tariffPriceInput) tariffPriceInput.required = false;
        renderBandsTable();
        validateAndUpdateView();
      }
    }

    typeFlatRadio?.addEventListener('change', () => setTariffMode('flat'));
    typeBandsRadio?.addEventListener('change', () => setTariffMode('time_bands'));
    labelFlat?.addEventListener('click', () => setTariffMode('flat'));
    labelBands?.addEventListener('click', () => setTariffMode('time_bands'));

    // ── Thuật toán kiểm tra tính toàn vẹn 24h & không chồng lấn (SCRUM-62) ──
    function validateDailyBands(bandsList) {
      const errors = [];
      if (!bandsList || bandsList.length === 0) {
        return { valid: false, errors: ['Biểu giá phải có ít nhất một khung giờ'] };
      }

      // 1. Kiểm tra từng hàng riêng lẻ
      const parsed = [];
      for (let i = 0; i < bandsList.length; i++) {
        const b = bandsList[i];
        const rowNum = i + 1;
        const label = String(b.label || '').trim();
        const start = timeToMinute(b.startTime);
        const end = timeToMinute(b.endTime);
        const price = Number(b.price);

        if (!label) {
          errors.push(`Khung giờ #${rowNum}: Tên khung giờ không được để trống`);
        }
        if (start === null) {
          errors.push(`Khung giờ #${rowNum} ("${label || 'Chưa đặt tên'}"): Giờ bắt đầu không hợp lệ`);
        }
        if (end === null) {
          errors.push(`Khung giờ #${rowNum} ("${label || 'Chưa đặt tên'}"): Giờ kết thúc không hợp lệ`);
        }
        if (!Number.isSafeInteger(price) || price < 0) {
          errors.push(`Khung giờ #${rowNum} ("${label || 'Chưa đặt tên'}"): Đơn giá phải là số nguyên không âm`);
        }
        if (start !== null && end !== null && start === end) {
          errors.push(`Khung giờ #${rowNum} ("${label}"): Giờ bắt đầu và kết thúc không được trùng nhau (${minuteToTime(start)})`);
        }

        if (start !== null && end !== null && start !== end) {
          if (end < start) {
            // Khung giờ qua đêm: tách thành 2 đoạn như chuẩn backend
            parsed.push({ label, start_minute: start, end_minute: 1440, price, originalIndex: i });
            parsed.push({ label, start_minute: 0, end_minute: end, price, originalIndex: i });
          } else {
            parsed.push({ label, start_minute: start, end_minute: end, price, originalIndex: i });
          }
        }
      }

      if (errors.length > 0) {
        return { valid: false, errors, parsed };
      }

      // 2. Kiểm tra tính liên tục, không chồng lấn và phủ kín 24h
      const ordered = [...parsed].sort((a, b) => a.start_minute - b.start_minute);
      let cursor = 0;

      for (const seg of ordered) {
        if (seg.start_minute > cursor) {
          errors.push(`Biểu giá bị hở từ ${minuteToTime(cursor)} đến ${minuteToTime(seg.start_minute)}`);
        }
        if (seg.start_minute < cursor) {
          const overlapEnd = Math.min(cursor, seg.end_minute);
          errors.push(`Biểu giá bị chồng lấn từ ${minuteToTime(seg.start_minute)} đến ${minuteToTime(overlapEnd)}`);
        }
        cursor = Math.max(cursor, seg.end_minute);
      }

      if (cursor < 1440) {
        errors.push(`Biểu giá bị hở từ ${minuteToTime(cursor)} đến 24:00`);
      }

      return {
        valid: errors.length === 0,
        errors,
        ordered,
      };
    }

    // ── Render bảng nhập các khung giờ ──
    const tbody = document.getElementById('tariff-bands-tbody');
    const bandsCountHint = document.getElementById('bands-count-hint');

    function renderBandsTable() {
      if (!tbody) return;
      tbody.innerHTML = '';
      timeBands.forEach((band, idx) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>
            <input class="form-input band-label-input" type="text" value="${escapeHtml(band.label)}"
                   placeholder="VD: Cao điểm" data-index="${idx}" required maxlength="80">
          </td>
          <td>
            <input class="form-input band-start-input" type="time" value="${band.startTime}"
                   data-index="${idx}" required step="60">
          </td>
          <td>
            <select class="form-select band-end-select" data-index="${idx}">
              ${generateEndTimeOptions(band.endTime)}
            </select>
          </td>
          <td>
            <div class="input-with-suffix">
              <input class="form-input band-price-input" type="number" value="${band.price}"
                     min="0" max="1000000000" step="100" placeholder="VD: 4000" data-index="${idx}" required>
              <span class="input-suffix">đ/kWh</span>
            </div>
          </td>
          <td style="text-align: center;">
            <button type="button" class="btn-remove-band" data-remove-index="${idx}" title="Xóa khung giờ này"
                    ${timeBands.length <= 1 ? 'disabled style="opacity:0.4;cursor:not-allowed;"' : ''}>
              ✕
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      });

      if (bandsCountHint) {
        bandsCountHint.textContent = `Đang có ${timeBands.length} khung giờ`;
      }

      // Gắn sự kiện sửa dữ liệu
      tbody.querySelectorAll('.band-label-input').forEach(input => {
        input.addEventListener('input', e => {
          const idx = Number(e.target.dataset.index);
          timeBands[idx].label = e.target.value;
          validateAndUpdateView();
        });
      });
      tbody.querySelectorAll('.band-start-input').forEach(input => {
        input.addEventListener('change', e => {
          const idx = Number(e.target.dataset.index);
          timeBands[idx].startTime = e.target.value;
          validateAndUpdateView();
        });
      });
      tbody.querySelectorAll('.band-end-select').forEach(select => {
        select.addEventListener('change', e => {
          const idx = Number(e.target.dataset.index);
          timeBands[idx].endTime = e.target.value;
          validateAndUpdateView();
        });
      });
      tbody.querySelectorAll('.band-price-input').forEach(input => {
        input.addEventListener('input', e => {
          const idx = Number(e.target.dataset.index);
          timeBands[idx].price = Number(e.target.value) || 0;
          validateAndUpdateView();
        });
      });
      tbody.querySelectorAll('[data-remove-index]').forEach(btn => {
        btn.addEventListener('click', e => {
          const idx = Number(btn.dataset.removeIndex);
          if (timeBands.length > 1) {
            timeBands.splice(idx, 1);
            renderBandsTable();
            validateAndUpdateView();
          }
        });
      });
    }

    function generateEndTimeOptions(selected) {
      const times = [];
      for (let h = 0; h < 24; h++) {
        for (let m = 0; m < 60; m += 30) {
          const t = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
          times.push(t);
        }
      }
      times.push('24:00'); // Mốc kết thúc ngày 24:00

      // Nếu giá trị hiện tại không nằm trong bước 30 phút, vẫn thêm vào
      if (selected && !times.includes(selected)) {
        times.push(selected);
        times.sort();
      }

      return times.map(t => {
        const isSel = t === selected ? 'selected' : '';
        const label = t === '24:00' ? '24:00 (Hết ngày)' : t;
        return `<option value="${t}" ${isSel}>${label}</option>`;
      }).join('');
    }

    function escapeHtml(str) {
      return String(str || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
    }

    // Nút thêm khung giờ
    document.getElementById('btn-add-time-band')?.addEventListener('click', () => {
      // Tìm mốc giờ bắt đầu hợp lý tiếp theo
      let nextStart = '00:00';
      if (timeBands.length > 0) {
        const last = timeBands[timeBands.length - 1];
        nextStart = last.endTime && last.endTime !== '24:00' ? last.endTime : '18:00';
      }
      timeBands.push({
        label: `Khung ${timeBands.length + 1}`,
        startTime: nextStart,
        endTime: '24:00',
        price: 3500,
      });
      renderBandsTable();
      validateAndUpdateView();
    });

    // Nút áp dụng mẫu 24h chuẩn
    document.getElementById('btn-apply-preset-bands')?.addEventListener('click', () => {
      timeBands = JSON.parse(JSON.stringify(STANDARD_PRESET_BANDS));
      renderBandsTable();
      validateAndUpdateView();
      showToast('Đã áp dụng mẫu biểu giá 24 giờ tiêu chuẩn (3 khung)', 'success');
    });

    // ── Cập nhật Timeline 24h và Hộp cảnh báo ──
    const alertBox = document.getElementById('tariff-bands-validation-alert');
    const track = document.getElementById('timeline-24h-track');
    const legend = document.getElementById('timeline-24h-legend');

    function validateAndUpdateView() {
      if (currentTariffMode !== 'time_bands') return;
      const result = validateDailyBands(timeBands);

      // Cập nhật hộp cảnh báo
      if (alertBox) {
        if (result.valid) {
          alertBox.className = 'tariff-validation-alert tariff-validation-alert--valid';
          alertBox.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
              <polyline points="22 4 12 14.01 9 11.01"></polyline>
            </svg>
            <div>
              <strong>Cấu hình 24 giờ hợp lệ!</strong>
              <div style="font-size:var(--font-size-xs);opacity:0.9;">Đã phủ kín toàn bộ 24:00 trong ngày, không phát hiện khoảng hở hoặc chồng lấn.</div>
            </div>
          `;
          submit.disabled = false;
        } else {
          alertBox.className = 'tariff-validation-alert tariff-validation-alert--error';
          alertBox.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <div>
              <strong>Cấu hình chưa hợp lệ (${result.errors.length} cảnh báo):</strong>
              <ul style="margin:4px 0 0 var(--space-4);padding:0;">
                ${result.errors.map(err => `<li>${escapeHtml(err)}</li>`).join('')}
              </ul>
            </div>
          `;
        }
      }

      // Cập nhật thanh timeline 24 giờ trực quan
      if (track) {
        track.innerHTML = '';
        const parsed = [];
        timeBands.forEach((b, i) => {
          const s = timeToMinute(b.startTime);
          const e = timeToMinute(b.endTime);
          if (s !== null && e !== null && s !== e) {
            if (e < s) {
              parsed.push({ label: b.label, start: s, end: 1440, price: b.price });
              parsed.push({ label: b.label, start: 0, end: e, price: b.price });
            } else {
              parsed.push({ label: b.label, start: s, end: e, price: b.price });
            }
          }
        });

        parsed.sort((a, b) => a.start - b.end);

        // Vẽ các đoạn từ 0 đến 1440 phút
        let cur = 0;
        const sorted = [...parsed].sort((a, b) => a.start - b.start);
        sorted.forEach(seg => {
          if (seg.start > cur) {
            // Khoảng hở
            const gapWidth = ((seg.start - cur) / 1440) * 100;
            const gapEl = document.createElement('div');
            gapEl.className = 'timeline-24h__segment timeline-24h__segment--gap';
            gapEl.style.width = `${gapWidth}%`;
            gapEl.textContent = 'Hở';
            gapEl.title = `Chưa có giá: ${minuteToTime(cur)} – ${minuteToTime(seg.start)}`;
            track.appendChild(gapEl);
          }
          const width = ((Math.min(seg.end, 1440) - seg.start) / 1440) * 100;
          const segEl = document.createElement('div');
          let colorType = 'timeline-24h__segment--standard';
          const lbl = seg.label.toLowerCase();
          if (lbl.includes('thấp') || lbl.includes('đêm')) colorType = 'timeline-24h__segment--low';
          else if (lbl.includes('cao')) colorType = 'timeline-24h__segment--peak';

          segEl.className = `timeline-24h__segment ${colorType}`;
          segEl.style.width = `${width}%`;
          segEl.textContent = `${seg.label} (${money(seg.price)})`;
          segEl.title = `${seg.label}: ${minuteToTime(seg.start)} – ${minuteToTime(seg.end)} (${money(seg.price)}/kWh)`;
          track.appendChild(segEl);
          cur = Math.max(cur, seg.end);
        });

        if (cur < 1440) {
          const gapWidth = ((1440 - cur) / 1440) * 100;
          const gapEl = document.createElement('div');
          gapEl.className = 'timeline-24h__segment timeline-24h__segment--gap';
          gapEl.style.width = `${gapWidth}%`;
          gapEl.textContent = 'Hở';
          gapEl.title = `Chưa có giá: ${minuteToTime(cur)} – 24:00`;
          track.appendChild(gapEl);
        }
      }

      // Legend
      if (legend) {
        legend.innerHTML = `
          <span class="timeline-24h__legend-item"><span class="timeline-24h__legend-dot" style="background:hsl(150,70%,38%);"></span> Thấp điểm</span>
          <span class="timeline-24h__legend-item"><span class="timeline-24h__legend-dot" style="background:hsl(210,85%,50%);"></span> Tiêu chuẩn</span>
          <span class="timeline-24h__legend-item"><span class="timeline-24h__legend-dot" style="background:hsl(28,92%,52%);"></span> Cao điểm</span>
          <span class="timeline-24h__legend-item"><span class="timeline-24h__legend-dot" style="background:hsl(0,0%,82%);"></span> Khoảng trống (hở giờ)</span>
        `;
      }
    }

    // ── Tải lịch sử biểu giá của trạm ──
    async function loadTariffs() {
      try {
        const tariffs = await ApiClient.get(path);
        history.replaceChildren();
        if (!tariffs.length) {
          const emptyNotice = document.createElement('p');
          emptyNotice.className = 'form-hint';
          emptyNotice.textContent = 'Trạm chưa có biểu giá tùy chỉnh (đang áp dụng giá mặc định).';
          history.append(emptyNotice);
          return;
        }

        const heading = document.createElement('h3');
        heading.className = 'card__title';
        heading.style.marginBottom = 'var(--space-3)';
        heading.textContent = 'Lịch sử biểu giá trạm';
        history.append(heading);

        const listContainer = document.createElement('div');
        listContainer.className = 'station-tariff-history';

        tariffs.forEach((tariff, index) => {
          const item = document.createElement('div');
          item.className = 'tariff-history-item';

          const effectiveDate = new Date(tariff.effective_from);
          const isCurrent = index === 0 && effectiveDate <= new Date();
          const effectiveAt = new Intl.DateTimeFormat('vi-VN', {
            dateStyle: 'short', timeStyle: 'short', timeZone: tariff.timezone_name,
          }).format(effectiveDate);

          const hasBands = Array.isArray(tariff.bands) && tariff.bands.length > 0;

          item.innerHTML = `
            <div class="tariff-history-item__header">
              <span class="tariff-history-item__title">
                ${escapeHtml(tariff.name)}
                ${isCurrent ? '<span class="badge badge--online" style="font-size:11px;">Hiện hành</span>' : ''}
                ${tariff.is_demo ? '<span class="badge badge--neutral" style="font-size:11px;">Demo</span>' : ''}
              </span>
              <span class="badge ${hasBands && tariff.price_vnd_per_kwh == null ? 'badge--charging' : 'badge--neutral'}">
                ${hasBands && tariff.price_vnd_per_kwh == null ? 'Nhiều khung giờ' : 'Cố định cả ngày'}
              </span>
            </div>
            <div class="tariff-history-item__meta">
              ${tariff.price_vnd_per_kwh != null ? `<strong>Đơn giá:</strong> ${money(tariff.price_vnd_per_kwh)}/kWh · ` : ''}
              <strong>Phí chiếm trụ:</strong> ${money(tariff.occupancy_fee_vnd_per_minute)}/phút ·
              <strong>Ân hạn:</strong> ${tariff.grace_period_minutes} phút
              <br>
              <span style="color:var(--color-text-muted);">Hiệu lực: ${effectiveAt} (${tariff.timezone_name})</span>
            </div>
            ${hasBands && tariff.price_vnd_per_kwh == null ? `
              <div class="tariff-history-bands-list">
                ${tariff.bands.map(b => `
                  <span class="tariff-history-band-tag">
                    <strong>${escapeHtml(b.label)}:</strong> ${minuteToTime(b.start_minute)}–${minuteToTime(b.end_minute)} (${money(b.price_vnd_per_kwh)}/kWh)
                  </span>
                `).join('')}
              </div>
            ` : ''}
          `;
          listContainer.append(item);
        });

        history.append(listContainer);
      } catch (error) {
        message.textContent = error.message || 'Không tải được lịch sử biểu giá.';
        message.className = 'form-error';
      }
    }

    // Khởi tạo
    loadTariffs();
    renderBandsTable();
    validateAndUpdateView();

    // ── Xử lý lưu biểu giá (SCRUM-61 & SCRUM-62) ──
    tariffForm.addEventListener('submit', async event => {
      event.preventDefault();
      message.textContent = '';
      const data = new FormData(tariffForm);
      const name = String(data.get('name') || '').trim();

      if (!name) {
        message.textContent = 'Vui lòng nhập tên biểu giá.';
        message.className = 'form-error';
        return;
      }

      const feeRaw = data.get('occupancy_fee_vnd_per_minute');
      const graceRaw = data.get('grace_period_minutes');
      const fee = Number(feeRaw);
      const grace = Number(graceRaw);

      if (!Number.isSafeInteger(fee) || fee < 0 || !Number.isSafeInteger(grace) || grace < 0) {
        message.textContent = 'Phí chiếm trụ và thời gian ân hạn phải là số nguyên không âm.';
        message.className = 'form-error';
        return;
      }

      const payload = {
        name,
        occupancy_fee_vnd_per_minute: fee,
        grace_period_minutes: grace,
        timezone_name: 'Asia/Ho_Chi_Minh',
      };

      const effective = data.get('effective_from');
      if (effective) payload.effective_from = effective;

      if (currentTariffMode === 'flat') {
        // Chế độ 1 giá cố định
        const priceRaw = data.get('price_vnd_per_kwh');
        const price = Number(priceRaw);
        if (!Number.isSafeInteger(price) || price < 0) {
          message.textContent = 'Đơn giá điện cố định phải là số nguyên không âm.';
          message.className = 'form-error';
          return;
        }
        payload.price_vnd_per_kwh = price;
      } else {
        // Chế độ nhiều khung giờ
        const validation = validateDailyBands(timeBands);
        if (!validation.valid) {
          message.textContent = 'Cấu hình khung giờ chưa hợp lệ: ' + validation.errors[0];
          message.className = 'form-error';
          alertBox?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          return;
        }

        payload.bands = timeBands.map(b => ({
          label: b.label.trim(),
          start_minute: timeToMinute(b.startTime),
          end_minute: timeToMinute(b.endTime),
          price_vnd_per_kwh: Number(b.price),
        }));
      }

      submit.disabled = true;
      submit.textContent = 'Đang lưu...';
      try {
        await ApiClient.post(path, payload);
        message.textContent = '✓ Đã lưu biểu giá mới thành công cho trạm!';
        message.className = 'tariff-validation-alert tariff-validation-alert--valid';
        showToast('Đã lưu biểu giá mới cho trạm', 'success');

        // Reset về giá trị cơ bản
        document.getElementById('tariff-name').value = 'Biểu giá trạm';
        document.getElementById('tariff-effective').value = '';
        await loadTariffs();
      } catch (error) {
        message.textContent = error.message || 'Không lưu được biểu giá.';
        message.className = 'form-error';
        showToast(error.message || 'Lỗi lưu biểu giá', 'error');
      } finally {
        submit.disabled = false;
        submit.textContent = 'Lưu biểu giá';
      }
    });
  }

  // ── Helpers hiện lỗi tại ô nhập (không dùng alert chung chung) ──
  function showFieldError(fieldName, message) {
    const el = document.querySelector(`[data-error="${fieldName}"]`);
    if (el) {
      el.textContent = message;
      const input = document.getElementById(
        fieldName === 'name'      ? 'station-name'    :
        fieldName === 'address'   ? 'station-address' :
        fieldName === 'latitude'  ? 'station-lat'     :
        fieldName === 'longitude' ? 'station-lng'     : ''
      );
      if (input) input.classList.add('is-error');
    }
  }

  function clearFieldErrors() {
    document.querySelectorAll('.form-error[data-error]').forEach(el => el.textContent = '');
    document.querySelectorAll('.form-input.is-error, .form-textarea.is-error')
      .forEach(el => el.classList.remove('is-error'));
  }

  // ── Xử lý lỗi validation từ server (Pydantic → FastAPI 422) ──
  function handleServerErrors(err) {
    if (err.message === 'validation') return;
    if (err.status === 422 && Array.isArray(err.detail)) {
      err.detail.forEach(e => {
        const field = e.loc?.[e.loc.length - 1];
        if (field) showFieldError(field, e.msg);
      });
    } else {
      showToast(err.message || 'Có lỗi xảy ra, vui lòng thử lại', 'error');
    }
  }

  // ── Bảo vệ form chính (FormGuard chặn submit 2 lần) ──
  const stationForm = document.getElementById('station-form');
  if (stationForm) {
    FormGuard.protect(stationForm, async (formData) => {
      clearFieldErrors();

      // Chuẩn bị payload — ép kiểu số thực cho toạ độ
      const payload = {
        name:      (formData.name || '').trim(),
        address:   (formData.address || '').trim(),
        latitude:  formData.latitude  ? parseFloat(formData.latitude)  : null,
        longitude: formData.longitude ? parseFloat(formData.longitude) : null,
        no_show_fee_vnd: formData.no_show_fee_vnd === '' ? 0 : parseInt(formData.no_show_fee_vnd, 10),
      };
      if (isEdit && formData.status) payload.status = formData.status;

      // Validate cơ bản phía client (server vẫn là nơi quyết định cuối — T-11 NFR)
      if (!payload.name) {
        showFieldError('name', 'Tên trạm không được để trống');
        throw new Error('validation');
      }
      if (!payload.address) {
        showFieldError('address', 'Địa chỉ không được để trống');
        throw new Error('validation');
      }

      if (isEdit) {
        await ApiClient.updateStation(stationId, payload);
        showToast('Đã cập nhật trạm thành công', 'success');
        // Chuyển về trang danh sách trạm sau khi lưu thông tin trạm (kể cả cập nhật trạng thái)
        setTimeout(() => {
          window.location.href = '/stations';
        }, 300);
      } else {
        const created = await ApiClient.createStation(payload);
        showToast('Đã tạo trạm mới thành công!', 'success');
        // Chuyển về trang danh sách trạm
        setTimeout(() => {
          window.location.href = `/stations`;
        }, 300);
      }
    }, {
      loadingText: isEdit ? 'Đang lưu...' : 'Đang tạo...',
      onError: handleServerErrors,
      keepDisabledOnSuccess: true,
    });
  }

  // ── Kiểm tra trùng mã trụ real-time khi rời ô nhập (T-11) ──
  const cpCodeInput = document.getElementById('cp-code');
  const cpCodeCheck = document.getElementById('cp-code-check');
  if (cpCodeInput && cpCodeCheck) {
    let _checkTimer;
    cpCodeInput.addEventListener('blur', () => {
      const code = cpCodeInput.value.trim();
      if (!code) return;
      clearTimeout(_checkTimer);
      _checkTimer = setTimeout(async () => {
        cpCodeCheck.textContent = '⏳ Đang kiểm tra mã...';
        cpCodeCheck.style.color = 'var(--color-text-muted)';
        try {
          // Gọi API kiểm tra mã — server trả 200 nếu có thể dùng, 409 nếu trùng
          await ApiClient.checkChargePointCode(code);
          cpCodeCheck.textContent = '✓ Mã trụ hợp lệ';
          cpCodeCheck.style.color = 'var(--color-online)';
          cpCodeInput.classList.remove('is-error');
        } catch (err) {
          if (err.status === 409) {
            cpCodeCheck.textContent = '✗ Mã trụ này đã tồn tại trong hệ thống';
            cpCodeCheck.style.color = 'var(--color-fault)';
            cpCodeInput.classList.add('is-error');
          } else {
            cpCodeCheck.textContent = '';
          }
        }
      }, 400);
    });
    cpCodeInput.addEventListener('input', () => {
      cpCodeCheck.textContent = '';
      cpCodeInput.classList.remove('is-error');
    });
  }

  // ── Modal thêm trụ sạc ──
  const cpModal   = document.getElementById('cp-modal');
  const addCpBtn  = document.getElementById('btn-add-cp');

  if (cpModal && addCpBtn) {
    function openCpModal() {
      document.getElementById('cp-form').reset();
      if (cpCodeCheck) cpCodeCheck.textContent = '';
      document.querySelector('#cp-form .form-error[data-error="code"]')
        && (document.querySelector('#cp-form .form-error[data-error="code"]').textContent = '');
      cpModal.classList.remove('is-hidden');
      document.getElementById('cp-code').focus();
    }

    function closeCpModal() {
      cpModal.classList.add('is-hidden');
      addCpBtn.focus();
    }

    addCpBtn.addEventListener('click', openCpModal);
    document.getElementById('cp-modal-close').addEventListener('click',  closeCpModal);
    document.getElementById('cp-modal-cancel').addEventListener('click', closeCpModal);
    cpModal.addEventListener('click', e => { if (e.target === cpModal) closeCpModal(); });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && !cpModal.classList.contains('is-hidden')) closeCpModal();
    });

    document.getElementById('cp-modal-submit').addEventListener('click', async () => {
      const form      = document.getElementById('cp-form');
      const formData  = Object.fromEntries(new FormData(form).entries());
      const code      = (formData.code || '').trim();
      const codeError = document.getElementById('cp-code-error');

      // Validate phía client
      if (!code) {
        codeError.textContent = 'Vui lòng nhập mã trụ';
        document.getElementById('cp-code').focus();
        return;
      }

      const submitBtn = document.getElementById('cp-modal-submit');
      submitBtn.disabled   = true;
      submitBtn.textContent = 'Đang thêm...';

      try {
        await ApiClient.createChargePoint({
          code,
          vendor:          (formData.vendor || '').trim() || null,
          model:           (formData.model  || '').trim() || null,
          connector_count: parseInt(formData.connector_count, 10) || 2,
          station_id:      stationId,
        });
        showToast('Đã thêm trụ sạc thành công', 'success');
        closeCpModal();
        // Reload để cập nhật bảng danh sách trụ trong trạm
        window.location.reload();
      } catch (err) {
        if (err.status === 409) {
          codeError.textContent = 'Mã trụ đã tồn tại trong hệ thống';
          document.getElementById('cp-code').focus();
        } else if (err.status === 422 && Array.isArray(err.detail)) {
          err.detail.forEach(e => {
            const field = e.loc?.[e.loc.length - 1];
            if (field === 'code') codeError.textContent = e.msg;
          });
        } else {
          showToast(err.message || 'Thêm trụ thất bại', 'error');
        }
      } finally {
        submitBtn.disabled   = false;
        submitBtn.textContent = 'Thêm trụ';
      }
    });
  }

  // ── Xóa trụ theo yêu cầu S-05; máy chủ vẫn kiểm tra quyền sở hữu ──
  document.querySelectorAll('[data-cp-delete-id]').forEach(button => {
    button.addEventListener('click', async () => {
      const cpId = button.dataset.cpDeleteId;
      const row = button.closest('tr');
      const code = row?.querySelector('.code-tag')?.textContent?.trim() || 'trụ này';
      if (!window.confirm(`Bạn có chắc muốn xóa ${code}?`)) return;

      button.disabled = true;
      try {
        await ApiClient.deleteChargePoint(cpId);
        showToast('Đã xóa trụ sạc', 'success');
        row?.remove();
        if (!document.querySelector('#cp-tbody tr')) window.location.reload();
      } catch (error) {
        showToast(error.message || 'Không xóa được trụ sạc', 'error');
        button.disabled = false;
      }
    });
  });

  // ── SCRUM-80: Quản lý hạn mức công suất trạm & đầu nối ──
  const powerCard = document.getElementById('station-power-card');
  if (powerCard && isEdit && stationId) {
    const powerLoading = document.getElementById('power-capacity-loading');
    const powerContent = document.getElementById('power-capacity-content');
    const powerLimitInput = document.getElementById('station-power-limit');
    const powerTbody = document.getElementById('power-connectors-tbody');
    const countEl = document.getElementById('power-connectors-count');
    const metricLimit = document.getElementById('power-metric-limit');
    const metricNominal = document.getElementById('power-metric-nominal');
    const metricStatus = document.getElementById('power-metric-status');
    const metricStatusHint = document.getElementById('power-metric-status-hint');
    const oversubBanner = document.getElementById('power-oversubscribed-banner');
    const powerForm = document.getElementById('station-power-form');
    const powerMessage = document.getElementById('station-power-message');
    const saveBtn = document.getElementById('btn-save-power-capacity');

    function _escHtml(str) {
      return String(str || '').replace(/[&<>"']/g, c =>
        ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    function renderStatus(nominal, limit) {
      if (!limit || limit <= 0) {
        metricStatus.innerHTML = '<span class="badge badge--neutral"><span class="badge-text">Chưa đặt hạn mức</span></span>';
        metricStatusHint.textContent = 'Cần nhập hạn mức công suất trạm';
        oversubBanner.classList.add('is-hidden');
        return;
      }

      if (nominal > limit) {
        metricStatus.innerHTML = '<span class="badge badge--warning"><span class="badge-text">Vượt hạn mức (Over-subscribed)</span></span>';
        metricStatusHint.textContent = `Vượt ${((nominal - limit) / limit * 100).toFixed(0)}% so với hạn mức nguồn cấp`;
        oversubBanner.classList.remove('is-hidden');
      } else {
        metricStatus.innerHTML = '<span class="badge badge--success"><span class="badge-text">An toàn (Trong hạn mức)</span></span>';
        metricStatusHint.textContent = `Tải danh định đạt ${((nominal / limit) * 100).toFixed(0)}% hạn mức`;
        oversubBanner.classList.add('is-hidden');
      }
    }

    function recalculateMetrics() {
      const limit = parseFloat(powerLimitInput.value) || 0;
      let nominal = 0;
      const rows = powerTbody.querySelectorAll('tr[data-cp-code]');
      rows.forEach(row => {
        const input = row.querySelector('.connector-power-input');
        const val = parseFloat(input?.value) || 0;
        nominal += val;
      });

      metricLimit.textContent = limit > 0 ? `${limit.toFixed(1)} kW` : '—';
      metricNominal.textContent = `${nominal.toFixed(1)} kW`;
      renderStatus(nominal, limit);
    }

    async function loadPowerCapacity() {
      try {
        const currentCapacity = await ApiClient.getStationPowerCapacity(stationId);
        powerLoading.classList.add('is-hidden');
        powerContent.classList.remove('is-hidden');

        // Điền hạn mức trạm
        if (currentCapacity.power_limit_kw != null) {
          powerLimitInput.value = currentCapacity.power_limit_kw;
        }

        // Render bảng đầu nối
        const connectors = currentCapacity.connectors || [];
        countEl.textContent = `${connectors.length} đầu nối`;

        if (connectors.length === 0) {
          powerTbody.innerHTML = `
            <tr>
              <td colspan="4" style="text-align:center;padding:var(--space-6);color:var(--color-text-muted);">
                Trạm chưa có trụ sạc hoặc đầu nối nào. Vui lòng thêm trụ sạc ở mục phía trên trước.
              </td>
            </tr>
          `;
          saveBtn.disabled = true;
          return;
        }

        powerTbody.innerHTML = connectors.map(c => `
          <tr data-cp-code="${_escHtml(c.charge_point_code)}" data-conn-id="${c.connector_id}">
            <td><code class="code-tag">${_escHtml(c.charge_point_code)}</code></td>
            <td><strong>Cổng #${c.connector_id}</strong></td>
            <td>
              <div class="input-with-suffix" style="max-width:180px;">
                <input type="number" step="0.1" min="0.1" max="500" class="form-input connector-power-input"
                  value="${c.rated_power_kw != null ? c.rated_power_kw : ''}"
                  placeholder="VD: 60" required />
                <span class="input-suffix">kW</span>
              </div>
            </td>
            <td>
              <div class="power-preset-group">
                <button type="button" class="power-preset-btn" data-preset="7.4">7.4 kW</button>
                <button type="button" class="power-preset-btn" data-preset="11">11 kW</button>
                <button type="button" class="power-preset-btn" data-preset="22">22 kW</button>
                <button type="button" class="power-preset-btn" data-preset="60">60 kW</button>
                <button type="button" class="power-preset-btn" data-preset="120">120 kW</button>
              </div>
            </td>
          </tr>
        `).join('');

        // Wire events for inputs
        powerTbody.querySelectorAll('.connector-power-input').forEach(input => {
          input.addEventListener('input', recalculateMetrics);
        });

        // Wire preset buttons
        powerTbody.querySelectorAll('.power-preset-btn').forEach(btn => {
          btn.addEventListener('click', () => {
            const row = btn.closest('tr');
            const input = row.querySelector('.connector-power-input');
            if (input) {
              input.value = btn.dataset.preset;
              recalculateMetrics();
            }
          });
        });

        powerLimitInput.addEventListener('input', recalculateMetrics);
        recalculateMetrics();
      } catch (err) {
        powerLoading.innerHTML = `
          <p style="color:var(--color-fault);">Không thể tải thông tin công suất: ${err.message || 'Lỗi kết nối'}</p>
          <button class="btn btn--secondary btn--sm" type="button" id="btn-retry-power" style="margin-top:var(--space-2);">Thử lại</button>
        `;
        document.getElementById('btn-retry-power')?.addEventListener('click', loadPowerCapacity);
      }
    }

    // Submit handler
    powerForm?.addEventListener('submit', async (e) => {
      e.preventDefault();
      powerMessage.innerHTML = '';

      const limit = parseFloat(powerLimitInput.value);
      if (!limit || limit <= 0) {
        powerMessage.innerHTML = '<div class="alert alert--error">Vui lòng nhập hạn mức công suất toàn trạm hợp lệ (&gt; 0 kW).</div>';
        powerLimitInput.focus();
        return;
      }

      const connectorsPayload = [];
      let hasError = false;
      const rows = powerTbody.querySelectorAll('tr[data-cp-code]');
      rows.forEach(row => {
        const code = row.dataset.cpCode;
        const connId = parseInt(row.dataset.connId, 10);
        const input = row.querySelector('.connector-power-input');
        const ratedKw = parseFloat(input?.value);
        if (isNaN(ratedKw) || ratedKw <= 0) {
          hasError = true;
          input?.classList.add('form-input--error');
        } else {
          input?.classList.remove('form-input--error');
          connectorsPayload.push({
            charge_point_code: code,
            connector_id: connId,
            rated_power_kw: ratedKw
          });
        }
      });

      if (hasError) {
        powerMessage.innerHTML = '<div class="alert alert--error">Vui lòng nhập công suất định danh hợp lệ cho tất cả các đầu nối.</div>';
        return;
      }

      saveBtn.disabled = true;
      saveBtn.innerHTML = '<span class="spinner spinner--sm" aria-hidden="true"></span> Đang lưu...';

      try {
        await ApiClient.updateStationPowerCapacity(stationId, {
          power_limit_kw: limit,
          connectors: connectorsPayload
        });
        powerMessage.innerHTML = '<div class="alert alert--success">Đã lưu cấu hình hạn mức công suất trạm thành công! Thuật toán phân bổ động đã được kích hoạt.</div>';
        showToast('Đã lưu cấu hình công suất trạm', 'success');
        recalculateMetrics();
      } catch (err) {
        powerMessage.innerHTML = `<div class="alert alert--error">Lỗi khi lưu cấu hình: ${_escHtml(err.message || 'Không thể lưu')}</div>`;
      } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          Lưu cấu hình công suất
        `;
      }
    });

    loadPowerCapacity();
  }

  // ── SCRUM-83: CRUD khung giờ hạn mức công suất ──
  const powerBandsCard = document.getElementById('station-power-bands-card');
  if (powerBandsCard && isEdit && stationId) {
    const form = document.getElementById('power-band-form');
    const startInput = document.getElementById('power-band-start');
    const endInput = document.getElementById('power-band-end');
    const limitInput = document.getElementById('power-band-limit');
    const saveButton = document.getElementById('power-band-save');
    const cancelButton = document.getElementById('power-band-cancel');
    const message = document.getElementById('power-bands-message');
    const warning = document.getElementById('power-band-overlap-warning');
    const tbody = document.getElementById('power-bands-tbody');
    let bands = [];
    let editingId = null;

    const minute = value => {
      const [hour, min] = value.split(':').map(Number);
      return hour * 60 + min;
    };
    const clock = value => `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;
    const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);

    function setMessage(text, type = 'info') {
      message.className = `alert alert--${type}`;
      message.textContent = text;
      message.hidden = !text;
    }

    function render() {
      if (!bands.length) {
        tbody.innerHTML = '<tr><td colspan="4">Chưa có khung giờ. Hạn mức mặc định của trạm đang được áp dụng.</td></tr>';
        return;
      }
      tbody.innerHTML = bands.map(band => `<tr>
        <td>${clock(band.start_minute)}</td><td>${clock(band.end_minute)}</td>
        <td class="text-right">${Number(band.power_limit_kw).toLocaleString('vi-VN', { maximumFractionDigits: 3 })} kW</td>
        <td><button class="btn btn--secondary btn--sm" type="button" data-band-edit="${band.id}">Sửa</button>
          <button class="btn btn--secondary btn--sm" type="button" data-band-delete="${band.id}">Xoá</button></td>
      </tr>`).join('');
    }

    function overlapping(start, end, excludedId = null) {
      return bands.find(band => band.id !== excludedId
        && Math.max(start, band.start_minute) < Math.min(end, band.end_minute));
    }

    function checkBand() {
      warning.textContent = '';
      if (!startInput.value || !endInput.value) return false;
      const start = minute(startInput.value);
      const end = minute(endInput.value);
      if (start >= end) {
        warning.textContent = 'Giờ bắt đầu phải sớm hơn giờ kết thúc.';
        return false;
      }
      const conflict = overlapping(start, end, editingId);
      if (conflict) {
        warning.textContent = `Cảnh báo: khung giờ này chồng lấn với ${clock(conflict.start_minute)}–${clock(conflict.end_minute)}.`;
        return false;
      }
      return true;
    }

    async function loadBands() {
      tbody.innerHTML = '<tr><td colspan="4">Đang tải khung giờ...</td></tr>';
      setMessage('Đang tải khung giờ...');
      try {
        bands = await ApiClient.listStationPowerCapacityBands(stationId);
        bands.sort((a, b) => a.start_minute - b.start_minute);
        render();
        setMessage(bands.length ? `Đã tải ${bands.length} khung giờ (${bands[0].timezone_name || 'giờ địa phương của trạm'}).` : 'Chưa có khung giờ.');
      } catch (error) {
        tbody.innerHTML = '<tr><td colspan="4">Không tải được khung giờ.</td></tr>';
        setMessage(error.message || 'Không tải được khung giờ công suất.', 'error');
      }
    }

    function resetForm() {
      form.reset();
      editingId = null;
      saveButton.textContent = 'Thêm khung giờ';
      cancelButton.classList.add('is-hidden');
      warning.textContent = '';
    }

    [startInput, endInput, limitInput].forEach(input => input.addEventListener('input', checkBand));
    cancelButton.addEventListener('click', resetForm);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const limit = Number(limitInput.value);
      if (!startInput.value || !endInput.value || !Number.isFinite(limit) || limit <= 0 || !checkBand()) {
        if (limitInput.value && limit <= 0) warning.textContent = 'Hạn mức công suất phải lớn hơn 0 kW.';
        return;
      }
      const body = { start_minute: minute(startInput.value), end_minute: minute(endInput.value), power_limit_kw: limit };
      saveButton.disabled = true;
      try {
        if (editingId === null) await ApiClient.createStationPowerCapacityBand(stationId, body);
        else await ApiClient.updateStationPowerCapacityBand(stationId, editingId, body);
        setMessage('Đã lưu khung giờ công suất.', 'success');
        resetForm();
        await loadBands();
      } catch (error) {
        setMessage(error.message || 'Không lưu được khung giờ.', 'error');
      } finally {
        saveButton.disabled = false;
      }
    });
    tbody.addEventListener('click', async event => {
      const editButton = event.target.closest('[data-band-edit]');
      const deleteButton = event.target.closest('[data-band-delete]');
      if (editButton) {
        const band = bands.find(item => item.id === Number(editButton.dataset.bandEdit));
        if (!band) return;
        editingId = band.id;
        startInput.value = clock(band.start_minute);
        endInput.value = clock(band.end_minute);
        limitInput.value = band.power_limit_kw;
        saveButton.textContent = 'Cập nhật khung giờ';
        cancelButton.classList.remove('is-hidden');
        checkBand();
      } else if (deleteButton) {
        const id = Number(deleteButton.dataset.bandDelete);
        if (!window.confirm('Bạn có chắc muốn xoá khung giờ công suất này?')) return;
        deleteButton.disabled = true;
        try {
          await ApiClient.deleteStationPowerCapacityBand(stationId, id);
          if (editingId === id) resetForm();
          setMessage('Đã xoá khung giờ công suất.', 'success');
          await loadBands();
        } catch (error) {
          setMessage(error.message || 'Không xoá được khung giờ.', 'error');
          deleteButton.disabled = false;
        }
      }
    });
    loadBands();
  }
})();
