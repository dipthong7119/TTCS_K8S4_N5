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
        throw {
          status: res.status,
          message,
          detail: data?.detail,
          code: data?.code,
          minimum_required_vnd: data?.minimum_required_vnd,
          top_up_url: data?.top_up_url,
        };
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
    getBookingOptions: (stationId) => _request('GET', `/stations/${stationId}/booking-options`),
    createStation: (body) => _request('POST', '/stations', body),
    updateStation: (id, body) => _request('PUT', `/stations/${id}`, body),
    deleteStation: (id) => _request('DELETE', `/stations/${id}`),
    getStationRevenue: (stationId, params = {}, opts = {}) => {
      const q = new URLSearchParams(params).toString();
      return _request('GET', `/stations/${encodeURIComponent(stationId)}/revenue` + (q ? '?' + q : ''), null, opts);
    },

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
    // --- Bắt đầu sạc theo tài khoản tài xế (SCRUM-95) ---
    createDriverRemoteStart: (connectorId, opts) =>
      _request('POST', `/connectors/${encodeURIComponent(connectorId)}/remote-start`, null, opts),

    getDriverRemoteStart: (requestId, opts) =>
      _request('GET', `/remote-starts/${encodeURIComponent(requestId)}`, null, opts),
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
    // SCRUM-96: Tài xế tìm trạm gần (dùng monitoring/tree với role driver)
    findDriverStations: (params = {}) => _request('GET', '/stations?' + new URLSearchParams(params)),
    listAllSessions: (params = {}, opts) => _request('GET', '/sessions?' + new URLSearchParams(params), null, opts),
    getSession: (id) => _request('GET', `/sessions/${id}`),
    getSessionInvoice: (id) => _request('GET', `/sessions/${id}/invoice`),
    remoteStop: (id) => _request('POST', `/sessions/${id}/remote-stop`),
    listAnomalies: (params = {}) => _request('GET', '/sessions/anomalies?' + new URLSearchParams(params)),


    // --- Operational Alerts (SCRUM-90) ---
    listOperationalAlerts: (params = {}) => {
      const q = new URLSearchParams(params).toString();
      return _request('GET', '/alerts' + (q ? '?' + q : ''));
    },
    acknowledgeAlert: (id, note = 'Đã xác nhận xử lý') =>
      _request('POST', `/alerts/${encodeURIComponent(id)}/resolve`, { note }),


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
    createSandboxTopup: (amountVnd) => _request('POST', '/wallet/topups/sandbox', { amount_vnd: amountVnd }),
    simulateSandboxPay: (orderCode, status = 'success') => _request('POST', '/wallet/topups/sandbox/simulate-pay', { order_code: orderCode, status }),
    listTopupHistory: (params = {}) => _request('GET', '/wallet/topups?' + new URLSearchParams(params)),
    checkWalletBalance: (minAmountVnd = 50000) => _request('GET', `/wallet/check-balance?min_amount_vnd=${encodeURIComponent(minAmountVnd)}`),

    // --- Subscriptions (SCRUM-68) ---
    listSubscriptionPlans: () => _request('GET', '/subscriptions/plans'),
    getMySubscriptions: () => _request('GET', '/subscriptions/mine'),
    subscribePlan: (planId) => _request('POST', '/subscriptions', { plan_id: planId }),
    getRevenueShareReport: (params = {}) => {
      const query = new URLSearchParams(
        Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '')
      ).toString();
      return _request('GET', '/subscriptions/revenue-share' + (query ? '?' + query : ''));
    },
    listRevenueShareContracts: (params = {}) => {
      const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '')).toString();
      return _request('GET', '/subscriptions/revenue-share/contracts' + (query ? '?' + query : ''));
    },
    createRevenueShareContract: (body) => _request('POST', '/subscriptions/revenue-share/contracts', body),

    // --- Tariffs (SCRUM-61, SCRUM-62 FE) ---
    listStationTariffs: (stationId) => _request('GET', `/stations/${stationId}/tariffs`),
    createStationTariff: (stationId, body) => _request('POST', `/stations/${stationId}/tariffs`, body),

    // --- Reservations (SCRUM-76 / S-48) ---
    listReservations: (params = {}, opts = {}) => {
      const query = new URLSearchParams({
        active_only: String(params.active_only === true),
      }).toString();
      return _request('GET', `/reservations/me?${query}`, null, opts);
    },
    createReservation: (body, opts = {}) =>
      _request('POST', '/reservations', body, opts),
    cancelReservation: (id, body = null, opts = {}) =>
      _request('POST', `/reservations/${encodeURIComponent(id)}/cancel`, body, opts),
    getReservation: (id, opts = {}) =>
      _request('GET', `/reservations/${encodeURIComponent(id)}`, null, opts),

    // --- Wallet Audit Logs (SCRUM-91) ---
    listWalletAuditLogs: (params = {}) => {
      const q = new URLSearchParams(params).toString();
      return _request('GET', '/audit' + (q ? '?' + q : ''));
    },

    // --- Privacy & Data Deletion (SCRUM-92 / S-57 / Nghị định 13/2023/NĐ-CP) ---
    getPrivacyProfile: () => _request('GET', '/privacy/profile'),
    requestDataDeletion: (body) => _request('POST', '/privacy/deletion-requests', body),
    cancelDataDeletionRequest: (id) => _request('POST', `/privacy/deletion-requests/${encodeURIComponent(id)}/cancel`),
    listDataDeletionRequests: (params = {}) => {
      const q = new URLSearchParams(params).toString();
      return _request('GET', '/privacy/admin/deletion-requests' + (q ? '?' + q : ''));
    },
    approveDataDeletionRequest: (id, body = {}) =>
      _request('POST', `/privacy/admin/deletion-requests/${encodeURIComponent(id)}/approve`, body),
    rejectDataDeletionRequest: (id, body = {}) =>
      _request('POST', `/privacy/admin/deletion-requests/${encodeURIComponent(id)}/reject`, body),

    // --- Power capacity (SCRUM-80) ---
    getStationPowerCapacity: (stationId) => _request('GET', `/stations/${stationId}/power-capacity`),
    updateStationPowerCapacity: (stationId, body) => _request('PUT', `/stations/${stationId}/power-capacity`, body),
    listStationPowerCapacityBands: (stationId) => _request('GET', `/stations/${stationId}/power-capacity-bands`),
    createStationPowerCapacityBand: (stationId, body) => _request('POST', `/stations/${stationId}/power-capacity-bands`, body),
    updateStationPowerCapacityBand: (stationId, bandId, body) => _request('PUT', `/stations/${stationId}/power-capacity-bands/${bandId}`, body),
    deleteStationPowerCapacityBand: (stationId, bandId) => _request('DELETE', `/stations/${stationId}/power-capacity-bands/${bandId}`),

    // --- Nearby stations (SCRUM-96 / S-47) ---
    getNearbyStations: (params = {}) => _request('GET', '/stations/nearby?' + new URLSearchParams(params)),
  };
})();

// Expose globally
window.ApiClient = ApiClient;
