/**
 * pages/stations_form.js — JS trang tạo/sửa trạm (T-09, SCRUM-105)
 * Giới hạn: ~100 dòng — logic dùng lại (FormGuard, ApiClient) ở shared files.
 * Mọi gọi API đi qua ApiClient — không rải fetch trực tiếp.
 */
(function () {
  'use strict';

  const isEdit     = !!document.querySelector('[name="station_id"]');
  const stationId  = document.querySelector('[name="station_id"]')?.value || null;

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
      } else {
        const created = await ApiClient.createStation(payload);
        showToast('Đã tạo trạm mới thành công!', 'success');
        // Chuyển sang trang edit để thêm trụ
        setTimeout(() => {
          window.location.href = `/stations/${created.id}/edit`;
        }, 800);
      }
    }, {
      loadingText: isEdit ? 'Đang lưu...' : 'Đang tạo...',
      onError: handleServerErrors,
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
          await ApiClient.get(`/charge-points/check-code?code=${encodeURIComponent(code)}`);
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
        // Reload để cập nhật bảng trụ
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
})();
