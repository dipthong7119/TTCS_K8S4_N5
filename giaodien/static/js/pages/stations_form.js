/**
 * pages/stations_form.js — JS trang thêm/sửa trạm
 */
(function () {
  'use strict';

  const isEdit = !!document.querySelector('[name="station_id"]');

  // ── Station form ──
  const stationForm = document.getElementById('station-form');
  if (stationForm) {
    FormGuard.protect(stationForm, async (data) => {
      if (isEdit) {
        const id = data.station_id;
        delete data.station_id;
        await ApiClient.updateStation(id, data);
        showToast('Đã cập nhật trạm thành công', 'success');
      } else {
        await ApiClient.createStation(data);
        showToast('Đã tạo trạm mới', 'success');
        setTimeout(() => { window.location.href = '/stations'; }, 800);
      }
    }, { loadingText: isEdit ? 'Đang lưu...' : 'Đang tạo...' });
  }

  // ── Charge point modal ──
  const cpModal   = document.getElementById('cp-modal');
  const addCpBtn  = document.getElementById('btn-add-cp');
  if (cpModal && addCpBtn) {
    addCpBtn.addEventListener('click', () => cpModal.classList.remove('is-hidden'));
    document.getElementById('cp-modal-close').addEventListener('click',  () => cpModal.classList.add('is-hidden'));
    document.getElementById('cp-modal-cancel').addEventListener('click', () => cpModal.classList.add('is-hidden'));
    cpModal.addEventListener('click', e => { if (e.target === cpModal) cpModal.classList.add('is-hidden'); });

    document.getElementById('cp-modal-submit').addEventListener('click', async () => {
      const form = document.getElementById('cp-form');
      const data = Object.fromEntries(new FormData(form).entries());
      const stationId = document.querySelector('[name="station_id"]')?.value;
      if (!data.code.trim()) {
        showToast('Vui lòng nhập mã trụ', 'error');
        return;
      }
      try {
        await ApiClient.createChargePoint({ ...data, station_id: stationId });
        showToast('Đã thêm trụ sạc', 'success');
        cpModal.classList.add('is-hidden');
        window.location.reload();
      } catch (err) {
        showToast(err.message || 'Thêm trụ thất bại', 'error');
      }
    });
  }
})();
