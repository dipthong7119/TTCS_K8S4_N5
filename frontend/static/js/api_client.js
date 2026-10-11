/**
 * api_client.js — MỌI lời gọi API đi qua đây
 * Không rải fetch(...) khắp nơi — tuân theo quy ước codebase map
 */

const ApiClient = (() => {
  const BASE_URL = '/api';   // same-origin; thay bằng URL thật khi deploy tách riêng

  /**
   * Gọi fetch nội bộ, tự xử lý redirect 401 về trang login
   */
  async function _request(method, path, body = null, opts = {}) {
    const headers = { 'Content-Type': 'application/json', ...opts.headers };
    const config = { method, headers, credentials: 'include', signal: opts.signal };
    if (body !== null) config.body = JSON.stringify(body);
    try {
      const res = await fetch(BASE_URL + path, config);
      const ct = res.headers.get('Content-Type') || '';
      const data = res.status === 204 ? null :
        (ct.includes('application/json') ? await res.json() : await res.text());
      if (!res.ok) {
        let message = data?.detail || data || 'Có lỗi xảy ra';
        if (Array.isArray(message)) message = message.map(item => item.msg).join(', ');
        if (message && typeof message === 'object') message = message.message || 'Có lỗi xảy ra';
        if (typeof message !== 'string') message = 'Có lỗi xảy ra';
        if (res.status === 401 && path !== '/auth/login' && window.location.pathname !== '/login') {
          const next = window.location.pathname + window.location.search;
          window.location.replace('/login?next=' + encodeURIComponent(next));
        }
        throw { status: res.status, message, detail: data?.detail };
      }
      return data;
    } catch (err) {
      if (err.status) throw err;
      if (err.name === 'AbortError') throw err;
      throw { status: 0, message: 'Không thể kết nối đến máy chủ. Vui lòng thử lại.' };
    }
  }

  return {
    get: (path, opts) => _request('GET', path, null, opts),
    post: (path, body, opts) => _request('POST', path, body, opts),
    put: (path, body, opts) => _request('PUT', path, body, opts),
    patch: (path, body, opts) => _request('PATCH', path, body, opts),
    delete: (path, opts) => _request('DELETE', path, null, opts),

    // --- Auth ---
    login: (email, password) => _request('POST', '/auth/login', { email, password }),
    logout: () => _request('POST', '/auth/logout'),

    // --- Stations ---
    listStations: (params = {}) => _request('GET', '/stations?' + new URLSearchParams(params)),
    getStation: (id) => _request('GET', `/stations/${id}`),
    createStation: (body) => _request('POST', '/stations', body),
    updateStation: (id, body) => _request('PUT', `/stations/${id}`, body),
    deleteStation: (id) => _request('DELETE', `/stations/${id}`),

    // --- Charge Points ---
    listChargePoints: (stationId) => _request('GET', `/charge-points?station_id=${encodeURIComponent(stationId)}`),
    createChargePoint: (body) => _request('POST', '/charge-points', body),
    updateChargePoint: (id, body) => _request('PATCH', `/charge-points/${id}`, body),
    deleteChargePoint: (id) => _request('DELETE', `/charge-points/${id}`),
    // Kiểm tra mã trụ có trùng không (T-11) — server trả 200 nếu OK, 409 nếu đã tồn tại
    checkChargePointCode: (code) => _request('GET', `/charge-points/check-code?code=${encodeURIComponent(code)}`),

    // --- Monitoring ---
    getMonitoringTree: () => _request('GET', '/monitoring/tree'),
    resetChargePoint: (code, type = 'Soft') => _request('POST', `/charge_points/${encodeURIComponent(code)}/reset`, { type }),

    remoteStartChargePoint: (code, connectorId, idTag, opts) => _request('POST', `/charge_points/${encodeURIComponent(code)}/remote-start`, { connector_id: connectorId, id_tag: idTag }, opts),
    // --- Cấu hình trụ (SCRUM-60) ---
    getChargePointConfiguration: (code) =>
      _request('GET', `/charge-points/${encodeURIComponent(code)}/configuration`),

    changeChargePointConfiguration: (code, key, value) =>
      _request(
        'PUT',
        `/charge-points/${encodeURIComponent(code)}/configuration/${encodeURIComponent(key)}`,
        { value }
      ),

    // --- Sessions ---
    listMySessions: (params = {}) => _request('GET', '/sessions/mine?' + new URLSearchParams(params)),
    getCurrentSession: (opts) => _request('GET', '/sessions/current', null, opts),
    listAllSessions: (params = {}, opts) => _request('GET', '/sessions?' + new URLSearchParams(params), null, opts),
    getSession: (id) => _request('GET', `/sessions/${id}`),
    remoteStop: (id) => _request('POST', `/sessions/${id}/remote-stop`),
    listAnomalies: (params = {}) => _request('GET', '/sessions/anomalies?' + new URLSearchParams(params)),

    // --- Audit trail ---
    listAuditLogs: (params = {}) => _request('GET', '/audit?' + new URLSearchParams(params)),

    // --- Reconciliation (SCRUM-183 / SCRUM-184) ---
    getKwhReconciliation: (params = {}, opts = {}) => {
      const q = new URLSearchParams(params).toString();
      return _request('GET', '/reconciliation/kwh' + (q ? '?' + q : ''), null, opts);
    },

    // --- Wallet ---
    getWallet: () => _request('GET', '/wallet'),
    listLedger: (params = {}) => _request('GET', '/wallet/ledger?' + new URLSearchParams(params)),
    listDriverWallets: (params = {}) => _request('GET', '/wallet/drivers?' + new URLSearchParams(params)),
    manualTopUp: (driverId, body) => _request('POST', `/wallet/drivers/${driverId}/topups`, body),
  };
})();

// Expose globally
window.ApiClient = ApiClient;
