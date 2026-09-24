/**
 * form_guard.js — Chặn bấm lưu 2 lần liên tiếp
 * Yêu cầu lặp lại ở T-09, T-11, S-04
 *
 * Cách dùng:
 *   FormGuard.protect(formElement, submitHandler)
 *   FormGuard.protect(formElement, submitHandler, { loadingText: 'Đang lưu...' })
 */

const FormGuard = (() => {
  /**
   * @param {HTMLFormElement} form
   * @param {function} onSubmit — async function(formData, formElement)
   * @param {object} opts — { loadingText, submitSelector }
   */
  function protect(form, onSubmit, opts = {}) {
    const { loadingText = 'Đang xử lý...', submitSelector = '[type="submit"]' } = opts;

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = form.querySelector(submitSelector);
      if (!btn || btn.dataset.loading === 'true') return;  // chặn click thứ 2

      // Ghi nhớ text gốc
      const origText = btn.textContent.trim();
      _setLoading(btn, true, loadingText);

      // Xoá lỗi cũ
      form.querySelectorAll('.form-error.is-visible').forEach(el => el.classList.remove('is-visible'));
      form.querySelectorAll('.form-input.is-error, .form-select.is-error, .form-textarea.is-error')
          .forEach(el => el.classList.remove('is-error'));

      try {
        const data = Object.fromEntries(new FormData(form).entries());
        await onSubmit(data, form);
      } catch (err) {
        // Hiển thị lỗi tại ô nhập hoặc alert chung
        _showError(form, err);
      } finally {
        _setLoading(btn, false, origText);
      }
    });
  }

  function _setLoading(btn, isLoading, text) {
    btn.dataset.loading = isLoading ? 'true' : 'false';
    btn.disabled = isLoading;
    btn.textContent = text;
    if (isLoading) btn.classList.add('btn--loading');
    else btn.classList.remove('btn--loading');
  }

  /**
   * Hiển thị lỗi tại đúng ô nhập (nếu server trả field-level error)
   * err.fields = { email: 'Email không hợp lệ', ... }
   */
  function _showError(form, err) {
    const msg = err.message || 'Có lỗi xảy ra, vui lòng thử lại.';
    if (err.fields && typeof err.fields === 'object') {
      let shown = false;
      Object.entries(err.fields).forEach(([field, fieldMsg]) => {
        const input = form.querySelector(`[name="${field}"]`);
        const errorEl = form.querySelector(`[data-error="${field}"]`);
        if (input) input.classList.add('is-error');
        if (errorEl) { errorEl.textContent = fieldMsg; errorEl.classList.add('is-visible'); shown = true; }
      });
      if (!shown) _showGeneralError(form, msg);
    } else {
      _showGeneralError(form, msg);
    }
  }

  function _showGeneralError(form, msg) {
    let general = form.querySelector('.form-error--general');
    if (!general) {
      general = document.createElement('p');
      general.className = 'form-error form-error--general is-visible';
      form.prepend(general);
    }
    general.textContent = msg;
    general.classList.add('is-visible');
  }

  return { protect };
})();

window.FormGuard = FormGuard;
