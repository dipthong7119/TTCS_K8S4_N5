/**
 * realtime_status.js — Hook nhận sự kiện trạng thái realtime (SCRUM-134 / SCRUM-123)
 *
 * Module dùng chung cho mọi trang cần theo dõi trạng thái đầu nối thời gian thực.
 * Giai đoạn mock: phát sự kiện giả lập để frontend phát triển độc lập.
 * Khi backend SCRUM-123 sẵn sàng: bỏ mock, dùng SseClient thật.
 *
 * Sử dụng:
 *   RealtimeStatus.subscribe('status_change', (payload) => { ... });
 *   RealtimeStatus.unsubscribe('status_change', handler);
 *   RealtimeStatus.connect();        // khởi động kết nối SSE
 *   RealtimeStatus.disconnect();     // ngắt kết nối
 *   RealtimeStatus.isConnected();    // trả true/false
 */

const RealtimeStatus = (() => {
  'use strict';

  let _connected = false;
  let _mockTimer = null;
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
   *   - '_connected'     : kết nối SSE thành công
   *   - '_disconnected'  : mất kết nối SSE
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

  // ── Mock data generator (xóa khi ghép SCRUM-123) ─────────────────────
  function _startMock() {
    // Phát sự kiện giả lập mỗi 5–15 giây
    function scheduleNext() {
      const delay = 5000 + Math.random() * 10000;
      _mockTimer = setTimeout(() => {
        const mockPayload = {
          charge_point_code: 'CP-MOCK-' + String(Math.floor(Math.random() * 5) + 1).padStart(3, '0'),
          connector_id: Math.floor(Math.random() * 2) + 1,
          status: MOCK_STATUSES[Math.floor(Math.random() * MOCK_STATUSES.length)],
          timestamp: new Date().toISOString(),
        };
        _emit('status_change', mockPayload);

        // Ngẫu nhiên phát sự kiện online/offline
        if (Math.random() < 0.15) {
          const offlinePayload = {
            charge_point_code: mockPayload.charge_point_code,
            timestamp: mockPayload.timestamp,
          };
          _emit(Math.random() < 0.5 ? 'cp_offline' : 'cp_online', offlinePayload);
        }

        scheduleNext();
      }, delay);
    }
    scheduleNext();
  }

  function _stopMock() {
    if (_mockTimer) {
      clearTimeout(_mockTimer);
      _mockTimer = null;
    }
  }

  // ── Kết nối SSE ──────────────────────────────────────────────────────
  function connect() {
    if (_connected) return;

    // Khi SCRUM-123 sẵn sàng, thay khối mock bằng:
    //   SseClient.on('status_update', (payload) => _emit('status_change', payload));
    //   SseClient.on('_connected', () => { _connected = true; _emit('_connected'); });
    //   SseClient.on('_error', () => { _connected = false; _emit('_disconnected'); });
    //   SseClient.connect('/api/monitoring/sse');

    // --- Mock mode ---
    _connected = true;
    _emit('_connected', null);
    _startMock();

    // Nối vào SseClient nếu đang chạy (để nhận sự kiện thật khi có)
    if (typeof SseClient !== 'undefined') {
      SseClient.on('status_update', (payload) => {
        _emit('status_change', payload);
      });
    }
  }

  function disconnect() {
    _stopMock();
    _connected = false;
    _emit('_disconnected', null);
  }

  function isConnected() {
    return _connected;
  }

  return { subscribe, unsubscribe, connect, disconnect, isConnected };
})();

window.RealtimeStatus = RealtimeStatus;
