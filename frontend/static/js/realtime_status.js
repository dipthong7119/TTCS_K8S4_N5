/**
 * realtime_status.js — Sự kiện và Reset cho trụ mẫu (T-24 / T-25 / T-35)
 *
 * Nhận danh sách trụ đang hiển thị để mô phỏng đúng mã trụ và đầu nối.
 * Dữ liệu máy chủ đi qua SseClient; module này chỉ xử lý dữ liệu mẫu.
 *
 * Sử dụng:
 *   RealtimeStatus.subscribe('status_change', (payload) => { ... });
 *   RealtimeStatus.unsubscribe('status_change', handler);
 *   RealtimeStatus.connect(points);  // khởi động mô phỏng trên các trụ mẫu
 *   RealtimeStatus.resetChargePoint(code, 'Soft');
 *   RealtimeStatus.disconnect();     // dừng mô phỏng và các Reset đang chạy
 *   RealtimeStatus.isConnected();    // trả true/false
 */

const RealtimeStatus = (() => {
  'use strict';

  let _connected = false;
  let _mockTimer = null;
  const _points = new Map();
  const _resetTimers = new Map();
  const _handlers = {};

  // ── Trạng thái OCPP mẫu để mock ──────────────────────────────────────
  const MOCK_STATUSES = [
    'Available', 'Preparing', 'Charging', 'SuspendedEV',
    'SuspendedEVSE', 'Finishing', 'Reserved', 'Unavailable', 'Faulted',
  ];

  // ── Event bus nội bộ ──────────────────────────────────────────────────
  function _emit(event, data) {
    (_handlers[event] || []).forEach(fn => {
      try { fn(data); } catch (e) { console.error('[RealtimeStatus] handler error:', e); }
    });
  }

  /**
   * Đăng ký lắng nghe sự kiện.
   * Các sự kiện hỗ trợ:
   *   - 'status_change'  : đầu nối đổi trạng thái  { charge_point_code, connector_id, status, timestamp }
   *   - 'cp_online'      : trụ lên tuyến            { charge_point_code, timestamp }
   *   - 'cp_offline'     : trụ mất kết nối          { charge_point_code, timestamp }
   *   - '_connected'     : mô phỏng đã bật
   *   - '_disconnected'  : mô phỏng đã dừng
   */
  function subscribe(event, handler) {
    if (!_handlers[event]) _handlers[event] = [];
    _handlers[event].push(handler);
    // Trả về hàm hủy đăng ký
    return () => unsubscribe(event, handler);
  }

  function unsubscribe(event, handler) {
    if (_handlers[event]) {
      _handlers[event] = _handlers[event].filter(fn => fn !== handler);
    }
  }

  function _statusChange(point, connector, status, timestamp) {
    _emit('status_change', {
      charge_point_code: point.code,
      connector_id: connector.connector_id,
      status,
      timestamp,
    });
  }

  function _offline(point, timestamp) {
    point.status = 'offline';
    _emit('cp_offline', { charge_point_code: point.code, timestamp });
  }

  function _online(point, timestamp) {
    point.status = 'online';
    _emit('cp_online', { charge_point_code: point.code, timestamp });
    point.connectors.forEach(connector => _statusChange(point, connector, 'Available', timestamp));
  }

  // ── Sự kiện giả lập trên danh sách trụ đang hiển thị ─────────────────
  function _startMock() {
    // Phát sự kiện giả lập mỗi 5–15 giây
    function scheduleNext() {
      if (!_connected) return;
      const delay = 5000 + Math.random() * 10000;
      _mockTimer = setTimeout(() => {
        if (!_connected) return;
        const points = [..._points.values()].filter(point => !_resetTimers.has(point.code));
        if (points.length) {
          const point = points[Math.floor(Math.random() * points.length)];
          const timestamp = new Date().toISOString();
          if (point.status === 'offline') {
            _online(point, timestamp);
          } else if (point.connectors.length) {
            const connector = point.connectors[Math.floor(Math.random() * point.connectors.length)];
            const status = MOCK_STATUSES[Math.floor(Math.random() * MOCK_STATUSES.length)];
            _statusChange(point, connector, status, timestamp);
            if (Math.random() < 0.15) _offline(point, timestamp);
          }
        }

        scheduleNext();
      }, delay);
    }
    scheduleNext();
  }

  function _stopMock() {
    if (_mockTimer !== null) {
      clearTimeout(_mockTimer);
      _mockTimer = null;
    }
  }

  function connect(points = []) {
    disconnect();
    points.forEach(point => {
      _points.set(point.code, {
        code: point.code,
        status: point.status,
        connectors: (point.connectors || []).map(connector => ({ connector_id: connector.connector_id })),
      });
    });
    _connected = true;
    _emit('_connected', null);
    _startMock();
  }

  async function resetChargePoint(code, type = 'Soft') {
    const point = _points.get(code);
    if (!_connected || !point) throw new Error('Trụ không thuộc dữ liệu mẫu đang hiển thị.');
    if (!['Soft', 'Hard'].includes(type)) throw new Error('Kiểu khởi động lại không hợp lệ.');
    if (_resetTimers.has(code)) throw new Error(`Trụ mẫu "${code}" đang khởi động lại.`);
    if (point.status === 'offline') throw new Error(`Trụ mẫu "${code}" đang ngoại tuyến.`);

    // Không gửi API: chỉ đổi trạng thái bộ mẫu và phát lại trạng thái đầu nối.
    const timer = setTimeout(() => {
      if (_resetTimers.get(code) !== timer) return;
      _resetTimers.delete(code);
      if (_connected && _points.get(code) === point) _online(point, new Date().toISOString());
    }, 2000);
    _resetTimers.set(code, timer);
    _offline(point, new Date().toISOString());
    return { status: 'Accepted', message: `Trụ mẫu "${code}" đã chấp nhận Reset ${type}.` };
  }

  function disconnect() {
    _stopMock();
    _resetTimers.forEach(timer => clearTimeout(timer));
    _resetTimers.clear();
    _points.clear();
    _connected = false;
    _emit('_disconnected', null);
  }

  function isConnected() {
    return _connected;
  }

  return { subscribe, unsubscribe, connect, disconnect, isConnected, resetChargePoint };
})();

window.RealtimeStatus = RealtimeStatus;
