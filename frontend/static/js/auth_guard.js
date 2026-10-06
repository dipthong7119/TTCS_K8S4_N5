/** SCRUM-135: quyền giao diện lấy từ context server; server bảo vệ dữ liệu. */
window.AuthGuard = (() => {
  'use strict';
  const rules = [
    [/^\/monitoring\/?$/, ['admin', 'operator', 'station_owner']],
    [/^\/stations(?:\/new|\/\d+\/edit)\/?$/, ['admin', 'station_owner']],
    [/^\/stations\/?$/, ['admin', 'operator', 'station_owner']],
    [/^\/sessions\/mine\/?$/, ['driver']],
    [/^\/sessions\/anomalies\/?$/, ['admin', 'operator']],
    [/^\/sessions\/?$/, ['admin', 'operator', 'accountant', 'station_owner']],
    [/^\/audit\/?$/, ['admin', 'operator']],
    [/^\/wallet\/?$/, ['admin', 'accountant', 'driver']],
  ];
  function canVisit(path, roles = []) {
    const rule = rules.find(([pattern]) => pattern.test(path));
    return !!rule && Array.isArray(roles) && rule[1].some(role => roles.includes(role));
  }
  function safeNext(value, roles = []) {
    if (!value || !value.startsWith('/') || value.startsWith('//')) return null;
    try {
      const url = new URL(value, window.location.origin);
      if (url.origin !== window.location.origin || !canVisit(url.pathname, roles)) return null;
      return url.pathname + url.search + url.hash;
    } catch (_) { return null; }
  }
  function requireRoles(allowed, user) {
    return !!user && Array.isArray(user.roles) && allowed.some(role => user.roles.includes(role));
  }
  function apply() {
    const context = document.getElementById('auth-context');
    if (!context) return; // Trang login độc lập không có context.
    let user;
    try { user = JSON.parse(context.textContent); } catch (_) { user = null; }
    if (!user?.id || !Array.isArray(user.roles)) {
      window.location.replace('/login?next=' + encodeURIComponent(window.location.pathname + window.location.search));
      return;
    }
    document.querySelectorAll('[data-roles]').forEach(element => {
      element.hidden = !requireRoles(element.dataset.roles.split(',').map(role => role.trim()), user);
    });
  }
  apply();
  return { canVisit, safeNext, requireRoles, apply };
})();
