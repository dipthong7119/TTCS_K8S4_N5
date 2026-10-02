/**
 * pages/login.js — Logic trang đăng nhập (SCRUM-135, T-05)
 *
 * Phụ thuộc (nạp trước trong login.html):
 *   - /static/js/api_client.js  (ApiClient)
 *   - /static/js/form_guard.js  (FormGuard)
 *
 * Xử lý:
 *   - Toggle hiện/ẩn mật khẩu
 *   - Submit form → ApiClient.login() → redirect theo vai trò
 *   - Hiển thị lỗi sai mật khẩu (HTTP 401 — chung chung, không tiết lộ email)
 *   - Hiển thị lỗi khóa tạm (HTTP 401 với detail chứa "tạm khoá")
 *   - Xóa alert khi người dùng bắt đầu nhập lại
 */
(function () {
  // ── Hiện/ẩn mật khẩu ────────────────────────────────────────────────────
  const pwdInput  = document.getElementById('password');
  const pwdToggle = document.getElementById('password-toggle');
  const eyeIcon   = document.getElementById('eye-icon');

  const EYE_OPEN   = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
  const EYE_CLOSED = '<path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>';

  pwdToggle.addEventListener('click', () => {
    const isPassword = pwdInput.type === 'password';
    pwdInput.type = isPassword ? 'text' : 'password';
    pwdToggle.setAttribute('aria-pressed', isPassword ? 'true' : 'false');
    eyeIcon.innerHTML = isPassword ? EYE_CLOSED : EYE_OPEN;
    pwdToggle.setAttribute('aria-label', isPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu');
  });

  // ── Alert box helper ─────────────────────────────────────────────────────
  const alertBox  = document.getElementById('login-alert');
  const alertText = document.getElementById('login-alert-text');

  function showAlert(msg, type = 'danger') {
    alertBox.className = `alert alert--${type}`;
    alertText.textContent = msg;
    alertBox.style.display = 'flex';
    alertBox.focus();
  }

  function hideAlert() {
    alertBox.style.display = 'none';
  }

  // Xóa alert khi người dùng bắt đầu nhập lại
  ['email', 'password'].forEach((fieldName) => {
    const el = document.getElementById(fieldName);
    if (el) el.addEventListener('input', hideAlert, { once: false });
  });

  // ── Xác định thông báo lỗi từ response backend ───────────────────────────
  /**
   * Backend luôn trả về HTTP 401 dù lỗi là "sai mật khẩu" hay "khóa tạm".
   * Phân biệt bằng chuỗi trong `detail`:
   *   - "tạm khoá" / "tam khoa" / "locked"  → thông báo khóa tạm với icon đồng hồ
   *   - còn lại                              → thông báo sai thông tin chung
   *
   * (T-05 AC: không tiết lộ email có tồn tại hay không)
   */
  function parseLoginError(err) {
    const detail = (err.message || '').toLowerCase();
    const isLocked =
      detail.includes('tạm khoá') ||
      detail.includes('tam khoa') ||
      detail.includes('locked') ||
      detail.includes('khoá');

    if (isLocked) {
      return {
        msg: 'Tài khoản tạm khoá 15 phút do nhập sai nhiều lần. Vui lòng thử lại sau.',
        type: 'warning',
      };
    }
    // Thông báo chung, không tiết lộ email có tồn tại hay không (S-02 AC)
    return {
      msg: 'Email hoặc mật khẩu không đúng.',
      type: 'danger',
    };
  }

  // ── Form submit ──────────────────────────────────────────────────────────
  FormGuard.protect(
    document.getElementById('login-form'),
    async (data) => {
      hideAlert();

      // Validate cơ bản phía client để tránh round-trip không cần thiết
      if (!data.email || !data.email.includes('@')) {
        showAlert('Vui lòng nhập địa chỉ email hợp lệ.');
        document.getElementById('email').focus();
        throw new Error('client-validation');
      }
      if (!data.password) {
        showAlert('Vui lòng nhập mật khẩu.');
        document.getElementById('password').focus();
        throw new Error('client-validation');
      }

      const loginResp = await ApiClient.login(data.email, data.password);

      // Xác định trang đích an toàn
      const params = new URLSearchParams(window.location.search);
      const requestedNext = params.get('next');
      let safeNext = null;

      if (requestedNext && requestedNext.startsWith('/') && !requestedNext.startsWith('//')) {
        try {
          const parsed = new URL(requestedNext, window.location.origin);
          if (parsed.origin === window.location.origin) {
            safeNext = `${parsed.pathname}${parsed.search}${parsed.hash}`;
          }
        } catch (_) {
          safeNext = null;
        }
      }

      window.location.assign(safeNext || loginResp.redirect_to || '/monitoring');
    },
    {
      loadingText: 'Đang đăng nhập...',
      onError: (err) => {
        // Bỏ qua lỗi validation phía client (đã hiển thị rồi)
        if (err.message === 'client-validation') return;

        const { msg, type } = parseLoginError(err);
        showAlert(msg, type);
      },
    }
  );
})();
