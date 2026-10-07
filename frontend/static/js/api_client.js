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
    listChargePoints:    (stationId)   => _request('GET', `/charge-points?station_id=${encodeURIComponent(stationId)}`),
    createChargePoint:   (body)        => _request('POST', '/charge-points', body),
    updateChargePoint:   (id, body)    => _request('PATCH', `/charge-points/${id}`, body),
    deleteChargePoint:   (id)          => _request('DELETE', `/charge-points/${id}`),
    // Kiểm tra mã trụ có trùng không (T-11) — server trả 200 nếu OK, 409 nếu đã tồn tại
    checkChargePointCode: (code)       => _request('GET', `/charge-points/check-code?code=${encodeURIComponent(code)}`),

    // --- Monitoring ---
    getMonitoringTree: () => _request('GET', '/monitoring/tree'),
    resetChargePoint: (code, type = 'Soft') => _request('POST', `/charge_points/${encodeURIComponent(code)}/reset`, { type }),

    // --- Sessions ---
    listMySessions:   (params = {}) => _request('GET', '/sessions/mine?' + new URLSearchParams(params)),
    getCurrentSession: ()           => _request('GET', '/sessions/current'),
    listAllSessions:  (params = {}) => _request('GET', '/sessions?' + new URLSearchParams(params)),
    getSession:       (id)          => _request('GET', `/sessions/${id}`),
    remoteStop:       (id)          => _request('POST', `/sessions/${id}/remote-stop`),
    listAnomalies:    async (params = {}) => {
      // T-54: Mock API for Anomaly List
      console.warn("Using Mock API for listAnomalies");
      return {
        total: 3,
        offline_count: 1,
        negative_kwh_count: 1,
        items: [
          { id: 101, station_name: 'Trạm Vincom', charge_point_code: 'CP_VIN_01', driver_name: 'Nguyễn Văn A', started_at: '2026-10-04T10:00:00Z', anomaly_reason: 'offline', kwh: 12.5, status: 'active', charge_point_status: 'offline' },
          { id: 102, station_name: 'Trạm Lotte', charge_point_code: 'CP_LOT_02', driver_name: 'Trần Thị B', started_at: '2026-10-04T11:00:00Z', anomaly_reason: 'no_stop', kwh: 45.2, status: 'active', charge_point_status: 'online' },
          { id: 103, station_name: 'Trạm Lotte', charge_point_code: 'CP_LOT_03', driver_name: 'Lê Văn C', started_at: '2026-10-05T07:15:00Z', anomaly_reason: 'negative_kwh', kwh: -5.0, status: 'finished', charge_point_status: 'online' }
        ]
      };
      // return _request('GET', '/sessions/anomalies?' + new URLSearchParams(params));
    },

    // --- Audit trail ---
    listAuditLogs:    async (params = {}) => {
      // T-58: Mock API for Audit Logs
      console.warn("Using Mock API for listAuditLogs");
      return {
        total: 2,
        items: [
          { id: 1, created_at: '2026-10-05T08:00:00Z', actor_name: 'Admin', actor_email: 'admin@admin.com', action: 'charge_point.reset.accepted', object_type: 'ChargePoint', object_id: 'CP_VIN_01', charge_point_code: 'CP_VIN_01', details: { type: 'Soft' } },
          { id: 2, created_at: '2026-10-05T09:30:00Z', actor_name: 'Vận hành viên', actor_email: 'op@admin.com', action: 'remote_stop.accepted', object_type: 'Session', object_id: 102, charge_point_code: 'CP_LOT_02', details: { reason: 'Anomaly' } }
        ]
      };
      // return _request('GET', '/audit?' + new URLSearchParams(params));
    },

    // --- Wallet ---
    getWallet:        ()            => _request('GET', '/wallet'),
    listLedger:       (params = {}) => _request('GET', '/wallet/ledger?' + new URLSearchParams(params)),
    listDriverWallets:(params = {}) => _request('GET', '/wallet/drivers?' + new URLSearchParams(params)),
    manualTopUp:      (driverId, body) => _request('POST', `/wallet/drivers/${driverId}/topups`, body),
  };
})();

// Expose globally
window.ApiClient = ApiClient;
