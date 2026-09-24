/**
 * sse_client.js — Kết nối SSE dùng chung (T-25)
 * Mọi trang cần realtime import file này
 */

const SseClient = (() => {
  let _source = null;
  let _listeners = {};
  let _reconnectTimer = null;
  let _reconnectDelay = 2000;
  const MAX_DELAY = 30000;

  function connect(url) {
    if (_source && _source.readyState !== EventSource.CLOSED) {
      _source.close();
    }
    _source = new EventSource(url, { withCredentials: true });

    _source.onopen = () => {
      _reconnectDelay = 2000;
      _emit('_connected', null);
    };

    _source.onerror = (e) => {
      _emit('_error', e);
      // Auto-reconnect with exponential back-off
      clearTimeout(_reconnectTimer);
      _reconnectTimer = setTimeout(() => {
        _reconnectDelay = Math.min(_reconnectDelay * 1.5, MAX_DELAY);
        connect(url);
      }, _reconnectDelay);
    };

    _source.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data);
        _emit(payload.event || 'message', payload);
      } catch {
        _emit('message', e.data);
      }
    };

    // Convenience: named events from server (e.g. event: status_update)
    ['status_update', 'session_update', 'heartbeat', 'anomaly'].forEach(name => {
      _source.addEventListener(name, (e) => {
        try { _emit(name, JSON.parse(e.data)); } catch { _emit(name, e.data); }
      });
    });
  }

  function disconnect() {
    clearTimeout(_reconnectTimer);
    if (_source) { _source.close(); _source = null; }
    _emit('_disconnected', null);
  }

  function on(event, handler) {
    if (!_listeners[event]) _listeners[event] = [];
    _listeners[event].push(handler);
    return () => off(event, handler);  // returns unsubscribe fn
  }

  function off(event, handler) {
    if (_listeners[event]) {
      _listeners[event] = _listeners[event].filter(h => h !== handler);
    }
  }

  function _emit(event, data) {
    (_listeners[event] || []).forEach(h => h(data));
  }

  return { connect, disconnect, on, off };
})();

window.SseClient = SseClient;
