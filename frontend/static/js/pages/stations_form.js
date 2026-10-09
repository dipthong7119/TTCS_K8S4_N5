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

    async function loadTariffs() {
      try {
        const tariffs = await ApiClient.get(path);
        history.replaceChildren();
        if (!tariffs.length) {
          history.textContent = 'Trạm chưa có biểu giá tùy chỉnh.';
          return;
        }
        const heading = document.createElement('h3');
        heading.className = 'card__title';
        heading.textContent = 'Lịch sử biểu giá';
        history.append(heading);
        const list = document.createElement('ul');
        list.style.paddingLeft = 'var(--space-5)';
        tariffs.forEach(tariff => {
          const item = document.createElement('li');
          const rate = tariff.price_vnd_per_kwh == null
            ? 'biểu giá nhiều khung giờ' : `${money(tariff.price_vnd_per_kwh)}/kWh`;
          item.textContent = `${tariff.name}: ${rate} · ${money(tariff.occupancy_fee_vnd_per_minute)}/phút · ân hạn ${tariff.grace_period_minutes} phút · hiệu lực ${new Date(tariff.effective_from).toLocaleString('vi-VN')}${tariff.is_demo ? ' (demo)' : ''}`;
          list.append(item);
        });
        history.append(list);
      } catch (error) {
        message.textContent = error.message || 'Không tải được biểu giá.';
        message.className = 'form-error';
      }
    }

    loadTariffs();
    tariffForm.addEventListener('submit', async event => {
      event.preventDefault();
      message.textContent = '';
      const data = new FormData(tariffForm);
      const name = String(data.get('name') || '').trim();
      const values = ['price_vnd_per_kwh', 'occupancy_fee_vnd_per_minute', 'grace_period_minutes'];
      if (!name || values.some(field => String(data.get(field) ?? '') === '')) {
        message.textContent = 'Vui lòng nhập tên biểu giá và đầy đủ các mức giá, thời gian.';
        message.className = 'form-error';
        return;
      }
      const [price, fee, grace] = values.map(field => Number(data.get(field)));
      if (![price, fee, grace].every(Number.isSafeInteger) || [price, fee, grace].some(value => value < 0)) {
        message.textContent = 'Đơn giá, phí chiếm trụ và thời gian ân hạn phải là số nguyên không âm.';
        message.className = 'form-error';
        return;
      }
      const payload = {
        name,
        price_vnd_per_kwh: price,
        occupancy_fee_vnd_per_minute: fee,
        grace_period_minutes: grace,
        timezone_name: 'Asia/Ho_Chi_Minh',
      };
      const effective = data.get('effective_from');
      if (effective) payload.effective_from = new Date(effective).toISOString();
      submit.disabled = true;
      submit.textContent = 'Đang lưu...';
      try {
        await ApiClient.post(path, payload);
        message.textContent = 'Đã lưu biểu giá mới cho trạm.';
        message.className = 'form-hint';
        tariffForm.reset();
        document.getElementById('tariff-name').value = 'Biểu giá trạm';
        document.getElementById('tariff-occupancy').value = '0';
        document.getElementById('tariff-grace').value = '0';
        await loadTariffs();
      } catch (error) {
        message.textContent = error.message || 'Không lưu được biểu giá.';
        message.className = 'form-error';
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
})();
