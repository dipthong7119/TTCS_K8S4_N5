/**
 * route_guard.js — Bảo vệ route phía client (SCRUM-135 frontend)
 *
 * Cách dùng:
 *   RouteGuard.requireAuth()                  — yêu cầu đăng nhập, không cần role cụ thể
 *   RouteGuard.requireRole('admin', 'operator') — yêu cầu ít nhất 1 trong các role
 *
 * Cơ chế:
 *   - Gọi GET /api/auth/me để lấy thông tin người dùng hiện tại.
 *   - Nếu 401 → chuyển về /login?next=<trang hiện tại>.
 *   - Nếu không đủ quyền → ẩn toàn bộ nội dung trang và hiển thị thông báo 403.
 *   - Nếu hợp lệ → expose window.currentUser và resolve Promise với user object.
 *
 * Lưu ý:
 *   - Đây là lớp bảo vệ UX phía client, KHÔNG thay thế kiểm tra quyền ở server.
 *   - Mọi API đã có deny-by-default ở backend (deps.py).
 */

const RouteGuard = (() => {
  // Cache để không gọi /api/auth/me nhiều lần trong cùng một trang
  let _userPromise = null;

  /**
   * Lấy thông tin người dùng hiện tại từ session.
   * Kết quả được cache trong bộ nhớ cho đến khi tải lại trang.
   * @returns {Promise<object>} user object { id, email, full_name, roles, role_label }
   */
  function fetchCurrentUser() {
    if (_userPromise) return _userPromise;

    _userPromise = ApiClient.get('/auth/me').catch((err) => {
      _userPromise = null; // reset cache khi lỗi để cho phép retry
      throw err;
    });

    return _userPromise;
  }

  /**
   * Chuyển hướng về trang đăng nhập, giữ lại URL hiện tại trong ?next=
   */
  function redirectToLogin() {
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.replace('/login?next=' + next);
  }

  /**
   * Hiển thị trang lỗi 403 tại chỗ — không redirect để người dùng biết tại sao.
   * @param {string[]} requiredRoles - các role cần thiết (để hiển thị thông báo)
   */
  function show403(requiredRoles) {
    // Ẩn nội dung trang
    const main = document.getElementById('main-content');
    if (main) {
      main.innerHTML = `
        <div id="guard-403" style="
          display:flex; flex-direction:column; align-items:center; justify-content:center;
          min-height:60vh; gap:16px; text-align:center; padding:32px;
        ">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none"
               stroke="var(--color-danger, #ef4444)" stroke-width="1.5"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10"/>
            <line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>
          </svg>
          <h2 style="margin:0; font-size:1.4rem; color:var(--color-text-primary, #f1f5f9);">
            Không có quyền truy cập
          </h2>
          <p style="margin:0; color:var(--color-text-secondary, #94a3b8); max-width:360px; line-height:1.6;">
            Trang này yêu cầu vai trò:
            <strong>${requiredRoles.map(_roleLabel).join(', ')}</strong>.<br/>
            Tài khoản của bạn không có quyền này.
          </p>
          <a href="javascript:history.back()" class="btn btn--ghost" style="margin-top:8px;">
            ← Quay lại
          </a>
        </div>
      `;
    }
  }

  /** Ánh xạ role key sang nhãn tiếng Việt */
  function _roleLabel(role) {
    const MAP = {
      admin:         'Quản trị viên',
      operator:      'Vận hành viên',
      station_owner: 'Chủ trạm',
      accountant:    'Kế toán',
      driver:        'Tài xế',
    };
    return MAP[role] || role;
  }

  /**
   * Bảo vệ trang: chỉ cần đăng nhập, không cần role cụ thể.
   * @returns {Promise<object>} user object khi hợp lệ
   */
  async function requireAuth() {
    try {
      const user = await fetchCurrentUser();
      window.currentUser = user;
      return user;
    } catch (err) {
      // 401 → chưa đăng nhập
      redirectToLogin();
      // Dừng script của trang bằng cách throw để tránh render UI trước khi redirect
      throw new Error('Chưa đăng nhập — đang chuyển hướng...');
    }
  }

  /**
   * Bảo vệ trang: yêu cầu người dùng có ít nhất một trong các role được liệt kê.
   * @param {...string} roles - danh sách role được phép vào trang
   * @returns {Promise<object>} user object khi hợp lệ
   */
  async function requireRole(...roles) {
    let user;
    try {
      user = await fetchCurrentUser();
    } catch (err) {
      redirectToLogin();
      throw new Error('Chưa đăng nhập — đang chuyển hướng...');
    }

    window.currentUser = user;

    const userRoles = Array.isArray(user.roles) ? user.roles : [];
    const allowed = roles.some((r) => userRoles.includes(r));

    if (!allowed) {
      show403(roles);
      throw new Error(`Không đủ quyền. Cần: ${roles.join(', ')}`);
    }

    return user;
  }

  /**
   * Lấy thông tin người dùng hiện tại (không bảo vệ route, chỉ fetch).
   * Trả về null nếu chưa đăng nhập thay vì throw.
   * @returns {Promise<object|null>}
   */
  async function getUser() {
    try {
      const user = await fetchCurrentUser();
      window.currentUser = user;
      return user;
    } catch (_) {
      return null;
    }
  }

  return { requireAuth, requireRole, getUser };
})();

window.RouteGuard = RouteGuard;
