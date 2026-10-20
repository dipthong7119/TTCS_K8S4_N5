/** S-02/T-05: đăng nhập qua API, xử lý lỗi và chuyển tới trang được phép. */
(function () {
  'use strict';
  const form = document.getElementById('login-form');
  if (!form) return;
  const password = document.getElementById('password');
  const toggle = document.getElementById('password-toggle');
  const alertBox = document.getElementById('login-alert');
  const alertText = document.getElementById('login-alert-text');
  const registerForm = document.getElementById('register-form');
  const showRegister = document.getElementById('show-register');
  const showLogin = document.getElementById('show-login');
  const registerAlert = document.getElementById('register-alert');
  const registerSuccess = document.getElementById('register-success');
  const title = document.getElementById('login-view-title');
  const subtitle = document.getElementById('login-view-subtitle');
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

  function clearRegisterAlerts() {
    if (registerAlert) registerAlert.hidden = true;
    if (registerSuccess) registerSuccess.hidden = true;
  }

  function setRegisterView(isRegistering) {
    clearRegisterAlerts();
    if (alertBox) alertBox.style.display = 'none';
    form.hidden = isRegistering;
    if (registerForm) registerForm.hidden = !isRegistering;
    if (showRegister) showRegister.hidden = isRegistering;
    if (showLogin) showLogin.hidden = !isRegistering;
    if (title) title.textContent = isRegistering ? 'Tạo tài khoản tài xế' : 'Đăng nhập';
    if (subtitle) subtitle.textContent = isRegistering
      ? 'Đăng ký tài khoản để sử dụng các dịch vụ trạm sạc'
      : 'Vui lòng nhập thông tin tài khoản của bạn';
    if (isRegistering) document.getElementById('register-full-name')?.focus();
    else document.getElementById('email')?.focus();
  }

  showRegister?.addEventListener('click', () => setRegisterView(true));
  showLogin?.addEventListener('click', () => setRegisterView(false));

  if (registerForm && typeof ApiClient.registerDriver === 'function') {
    registerForm.querySelectorAll('input').forEach(input => {
      input.addEventListener('input', clearRegisterAlerts);
    });

    FormGuard.protect(registerForm, async data => {
      clearRegisterAlerts();
      data.full_name = (data.full_name || '').trim();
      data.email = (data.email || '').trim();
      const emailInput = document.getElementById('register-email');
      const fields = {};
      if (data.full_name.length < 2) fields.full_name = 'Vui lòng nhập họ tên có ít nhất 2 ký tự.';
      if (!data.email || !emailInput.validity.valid) fields.email = 'Vui lòng nhập email hợp lệ.';
      if ((data.password || '').length < 8) fields.password = 'Mật khẩu cần có ít nhất 8 ký tự.';
      else if (data.password.length > 128) fields.password = 'Mật khẩu không được vượt quá 128 ký tự.';
      if (data.password !== data.password_confirm) fields.password_confirm = 'Mật khẩu nhập lại chưa khớp.';

      if (Object.keys(fields).length) {
        Object.entries(fields).forEach(([name, message]) => {
          const input = registerForm.elements.namedItem(name);
          if (input) input.classList.add('is-error');
          const errorId = {
            full_name: 'register-full-name-error',
            email: 'register-email-error',
            password: 'register-password-error',
            password_confirm: 'register-password-confirm-error',
          }[name];
          const error = document.getElementById(errorId);
          if (error) {
            error.textContent = message;
            error.classList.add('is-visible');
          }
        });
        registerForm.elements.namedItem(Object.keys(fields)[0])?.focus();
        return false;
      }

      await ApiClient.registerDriver({
        full_name: data.full_name,
        email: data.email,
        password: data.password,
      });
      const email = document.getElementById('email');
      const loginPassword = document.getElementById('password');
      if (email) email.value = data.email;
      if (loginPassword) loginPassword.value = '';
      const message = 'Tạo tài khoản tài xế thành công. Vui lòng đăng nhập.';
      if (registerSuccess) {
        registerSuccess.textContent = message;
        registerSuccess.hidden = false;
      }
      registerForm.reset();
      setRegisterView(false);
      if (registerSuccess) {
        registerSuccess.textContent = message;
        registerSuccess.hidden = false;
      }
      document.getElementById('password')?.focus();
    }, {
      loadingText: 'Đang tạo tài khoản...',
      onError: error => {
        if (!registerAlert) return;
        registerAlert.textContent = error.message || 'Không thể tạo tài khoản. Vui lòng thử lại.';
        registerAlert.hidden = false;
      },
    });
  }
})();
