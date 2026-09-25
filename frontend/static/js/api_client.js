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
    const config = { method, headers, credentials: 'include' };
    if (body !== null) config.body = JSON.stringify(body);

    try {
      const res = await fetch(BASE_URL + path, config);

      // Phiên hết hạn → chuyển về login
      if (res.status === 401) {
        if (window.location.pathname !== '/login') {
          window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname);
          throw { status: 401, message: 'Phiên đã hết hạn, vui lòng đăng nhập lại.' };
        }
      }

      let data;
      const ct = res.headers.get('Content-Type') || '';
      if (ct.includes('application/json')) {
        data = await res.json();
      } else {
        data = await res.text();
      }

      if (!res.ok) {
        let errMsg = data?.detail || data || 'Có lỗi xảy ra';
        if (Array.isArray(errMsg)) {
          errMsg = errMsg.map(e => `${e.loc ? e.loc.join('.') : ''}: ${e.msg}`).join(', ');
        }
        throw { status: res.status, message: errMsg };
      }
      return data;
    } catch (err) {
      if (err.status) throw err;
      throw { status: 0, message: 'Không thể kết nối đến máy chủ' };
    }
  }

  return {
    get:    (path, opts)       => _request('GET',    path, null, opts),
    post:   (path, body, opts) => _request('POST',   path, body, opts),
    put:    (path, body, opts) => _request('PUT',    path, body, opts),
    patch:  (path, body, opts) => _request('PATCH',  path, body, opts),
    delete: (path, opts)       => _request('DELETE', path, null, opts),

    // --- Auth ---
    login:  (email, password) => _request('POST', '/auth/login', { email, password }),
    logout: ()                => _request('POST', '/auth/logout'),

    // --- Stations ---
    listStations:  (params = {}) => _request('GET', '/stations?' + new URLSearchParams(params)),
    getStation:    (id)          => _request('GET', `/stations/${id}`),
    createStation: (body)        => _request('POST',   '/stations', body),
    updateStation: (id, body)    => _request('PUT',    `/stations/${id}`, body),
    deleteStation: (id)          => _request('DELETE', `/stations/${id}`),

    // --- Charge Points ---
    listChargePoints:    (stationId)   => _request('GET', `/stations/${stationId}/charge-points`),
    createChargePoint:   (body)        => _request('POST', '/charge-points', body),
    updateChargePoint:   (id, body)    => _request('PUT',  `/charge-points/${id}`, body),
    deleteChargePoint:   (id)          => _request('DELETE', `/charge-points/${id}`),
    // Kiểm tra mã trụ có trùng không (T-11) — server trả 200 nếu OK, 409 nếu đã tồn tại
    checkChargePointCode: (code)       => _request('GET', `/charge-points/check-code?code=${encodeURIComponent(code)}`),

    // --- Monitoring ---
    getMonitoringTree: () => _request('GET', '/monitoring/tree'),

    // --- Sessions ---
    listMySessions:   (params = {}) => _request('GET', '/sessions/mine?' + new URLSearchParams(params)),
    listAllSessions:  (params = {}) => _request('GET', '/sessions?' + new URLSearchParams(params)),
    getSession:       (id)          => _request('GET', `/sessions/${id}`),
    remoteStop:       (id)          => _request('POST', `/sessions/${id}/remote-stop`),
    listAnomalies:    (params = {}) => _request('GET', '/sessions/anomalies?' + new URLSearchParams(params)),

    // --- Wallet ---
    getWallet:        ()            => _request('GET', '/wallet'),
    listLedger:       (params = {}) => _request('GET', '/wallet/ledger?' + new URLSearchParams(params)),
    topUp:            (amount)      => _request('POST', '/wallet/topup', { amount }),
  };
})();

// Expose globally
window.ApiClient = ApiClient;
