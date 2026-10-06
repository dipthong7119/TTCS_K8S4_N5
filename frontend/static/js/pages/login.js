/** S-02/T-05: đăng nhập qua API, xử lý lỗi và chuyển tới trang được phép. */
(function () {
  'use strict';
  const form = document.getElementById('login-form');
  if (!form) return;
  const password = document.getElementById('password');
  const toggle = document.getElementById('password-toggle');
  const alertBox = document.getElementById('login-alert');
  const alertText = document.getElementById('login-alert-text');
  const EYE_OPEN   = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
  const EYE_CLOSED = '<path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>';
  toggle.addEventListener('click', () => {
    const show = password.type === 'password';
    password.type = show ? 'text' : 'password';
    document.getElementById('eye-icon').innerHTML = show ? EYE_CLOSED : EYE_OPEN;
    toggle.setAttribute('aria-pressed', String(show));
    toggle.setAttribute('aria-label', show ? 'Ẩn mật khẩu' : 'Hiện mật khẩu');
  });
  ['email', 'password'].forEach(name => {
    document.getElementById(name).addEventListener('input', () => { alertBox.style.display = 'none'; });
  });
  function showError(error) {
    alertText.textContent = error.message || 'Có lỗi xảy ra. Vui lòng thử lại.';
    alertBox.style.display = 'flex';
  }
  FormGuard.protect(form, async data => {
    alertBox.style.display = 'none';
    data.email = (data.email || '').trim();
    const fields = {};
    const emailInput = document.getElementById('email');
    if (!data.email || !emailInput.validity.valid) fields.email = 'Vui lòng nhập email hợp lệ.';
    if (!data.password) fields.password = 'Vui lòng nhập mật khẩu.';
    if (Object.keys(fields).length) {
      Object.entries(fields).forEach(([name, message]) => {
        form.elements[name].classList.add('is-error');
        const error = document.getElementById(name + '-error');
        error.textContent = message;
        error.classList.add('is-visible');
      });
      form.elements[Object.keys(fields)[0]].focus();
      return false;
    }
    const result = await ApiClient.login(data.email, data.password);
    const roles = Array.isArray(result.roles) ? result.roles : [];
    const next = new URLSearchParams(window.location.search).get('next');
    const destination = AuthGuard.safeNext(next, roles) || AuthGuard.safeNext(result.redirect_to, roles);
    if (!destination) throw { status: 403, message: 'Tài khoản chưa có trang phù hợp. Vui lòng liên hệ quản trị viên.' };
    window.location.assign(destination);
  }, { loadingText: 'Đang đăng nhập...', keepDisabledOnSuccess: true, onError: showError });
})();
