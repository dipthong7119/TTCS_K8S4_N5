(function () {
  // Password show/hide
  const pwdInput  = document.getElementById('password');
  const pwdToggle = document.getElementById('password-toggle');
  const eyeIcon   = document.getElementById('eye-icon');
  pwdToggle.addEventListener('click', () => {
    const show = pwdInput.type === 'password';
    pwdInput.type = show ? 'text' : 'password';
    pwdToggle.setAttribute('aria-pressed', show ? 'true' : 'false');
    eyeIcon.innerHTML = show
      ? '<path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>'
      : '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
  });

  const alertBox  = document.getElementById('login-alert');
  const alertText = document.getElementById('login-alert-text');

  FormGuard.protect(
    document.getElementById('login-form'),
    async (data) => {
      alertBox.style.display = 'none';
      const login = await ApiClient.login(data.email, data.password);
      const params = new URLSearchParams(window.location.search);
      const requestedNext = params.get('next');
      let safeNext = null;
      if (requestedNext && requestedNext.startsWith('/') && !requestedNext.startsWith('//')) {
        try {
          const parsedNext = new URL(requestedNext, window.location.origin);
          if (parsedNext.origin === window.location.origin) {
            safeNext = `${parsedNext.pathname}${parsedNext.search}${parsedNext.hash}`;
          }
        } catch (_) {
          safeNext = null;
        }
      }
      window.location.assign(safeNext || login.redirect_to || '/monitoring');
    },
    { loadingText: 'Đang đăng nhập...' }
  );

  // Lắng nghe lỗi submit để hiển thị alert chung
  document.getElementById('login-form').addEventListener('submit', () => {
    alertBox.style.display = 'none';
  });
})();
