/** T-09/T-24/T-25: execute the shipped JS with DOM/EventSource doubles.
 * These tests check behavior, not browser layout or rendering performance.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, 'frontend/static/js', file), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));

function element() {
  const classes = new Set();
  const selectors = new Map();
  return {
    children: [], dataset: {}, textContent: '', innerHTML: '', value: '', disabled: false,
    handlers: {},
    classList: {
      add: name => classes.add(name), remove: name => classes.delete(name),
      contains: name => classes.has(name),
      toggle: (name, active) => active ? classes.add(name) : classes.delete(name),
    },
    addEventListener(name, fn) { this.handlers[name] = fn; },
    appendChild(child) { child.parent = this; this.children.push(child); },
    remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); },
    querySelector(selector) { if (!selectors.has(selector)) selectors.set(selector, element()); return selectors.get(selector); },
    querySelectorAll() { return []; },
    setAttribute() {}, focus() {}, prepend() {},
  };
}

function mockTimers() {
  const timers = new Map();
  let nextId = 0;
  return {
    setTimeout(fn, delay) { const id = nextId++; timers.set(id, { fn, delay }); return id; },
    clearTimeout(id) { timers.delete(id); },
    run(predicate) {
      const entry = [...timers.entries()].find(([, timer]) => predicate(timer.delay));
      assert.ok(entry, 'expected a scheduled mock event');
      timers.delete(entry[0]);
      entry[1].fn();
    },
    size: () => timers.size,
  };
}

function monitoring(getTree, clock = Date, options = {}) {
  const ids = new Map();
  const document = {
    handlers: {}, body: element(),
    getElementById(id) { if (!ids.has(id)) ids.set(id, element()); return ids.get(id); },
    createElement: element,
    addEventListener(name, fn) { this.handlers[name] = fn; },
  };
  const callbacks = {};
  const toasts = [];
  const resetBindings = [];
  const apiResets = [];
  const mockPoints = [];
  let requests = 0;
  const timers = options.timers || { setTimeout, clearTimeout };
  const math = Object.create(Math);
  math.random = options.random || Math.random;
  const context = vm.createContext({
    document, window: {}, setTimeout: timers.setTimeout, clearTimeout: timers.clearTimeout, Date: clock, Math: math, console,
    ApiClient: {
      getMonitoringTree: () => { requests++; return getTree(); },
      resetChargePoint: async (code, type) => { apiResets.push({ code, type }); return { status: 'Accepted' }; },
    },
    SseClient: { on: (name, fn) => { callbacks[name] = fn; }, connect() {} },
    RealtimeStatus: { subscribe() {}, connect() {}, disconnect() {} },
    RestartButton: { createMarkup: () => '', bindEvents() {} },
    showToast: message => toasts.push(message),
  });
  if (options.realModules) {
    document.getElementById('monitoring-grid').dataset.canReset = 'true';
    vm.runInContext(read('realtime_status.js'), context);
    vm.runInContext(read('restart_button.js'), context);
    const bind = context.window.RestartButton.bindEvents;
    context.window.RestartButton.bindEvents = (body, bindings) => { resetBindings.push(bindings); bind(body, bindings); };
    const connect = context.window.RealtimeStatus.connect;
    context.window.RealtimeStatus.connect = points => { mockPoints.splice(0, mockPoints.length, ...points); connect(points); };
  }
  vm.runInContext(read('pages/monitoring_grid.js'), context);
  document.handlers.DOMContentLoaded();
  return { document, callbacks, toasts, apiResets, mockPoints, resetBindings,
    mock: context.window.RealtimeStatus, restart: context.window.RestartButton,
    confirm: () => document.body.children[0].querySelector('#restart-confirm-ok').handlers.click(),
    openDetail: () => document.getElementById('monitoring-grid').children[0].querySelector('.station-card__open').handlers.click(),
    toggleMock: () => document.getElementById('btn-toggle-mock').handlers.click(),
    html: () => document.getElementById('monitoring-grid').children.map(child => child.innerHTML).join(''),
    pointHtml(code) { return this.html().match(/<section class="cp-tile"[\s\S]*?<\/section>/g).find(html => html.includes(`data-cp-code="${code}"`)); },
    requests: () => requests, total: () => Number(document.getElementById('mon-total').textContent) };
}

const tree = [{ id: 42, name: 'Real station', address: '', status: 'active', charge_points: [
  { id: 1, code: 'REAL-01', status: 'online', ocpp_status: 'Available', connectors: [
    { connector_id: 1, status: 'rảnh', ocpp_status: 'Available' },
  ] },
] }];

test('empty API tree stays empty, without invented demo points', async () => {
  const page = monitoring(async () => []);
  await flush();
  assert.equal(page.total(), 0);
  assert.equal(page.document.getElementById('btn-toggle-mock').classList.contains('is-active'), false);
});

test('API failure shows an error, without invented online points', async () => {
  const page = monitoring(async () => { throw Error('offline'); });
  await flush();
  assert.equal(page.total(), 0);
  assert.match(page.document.getElementById('monitoring-grid').children[0].innerHTML, /Không tải được dữ liệu/);
});

test('temporary API failure retains the last real tree and reports staleness', async () => {
  let fail = false;
  const page = monitoring(async () => { if (fail) throw Error('offline'); return tree; });
  await flush();
  fail = true;
  page.callbacks._connected();
  await flush();
  assert.equal(page.total(), 1);
  assert.match(page.toasts.at(-1), /dữ liệu đã tải trước đó/);
});

test('demo data appears only after explicit selection and resists pending API responses', async () => {
  let resolve;
  const page = monitoring(() => new Promise(done => { resolve = done; }));
  page.document.getElementById('btn-toggle-mock').handlers.click();
  assert.equal(page.total(), 20);
  resolve([]);
  await flush();
  page.callbacks._connected();
  assert.equal(page.total(), 20);
  assert.equal(page.requests(), 1);
});

test('SSE reconnect reloads the complete tree and status events update connectors', async () => {
  const page = monitoring(async () => structuredClone(tree));
  await flush();
  page.callbacks._connected();
  await flush();
  assert.equal(page.requests(), 2);
  page.callbacks.status_update({ station_id: 42, charge_points: [{ ...tree[0].charge_points[0], connectors: [
    { connector_id: 1, status: 'bận', ocpp_status: 'Charging' },
  ] }] });
  assert.equal(Number(page.document.getElementById('mon-charging').textContent), 1);
});

test('mock events address all 20 displayed points and only their declared connectors', async () => {
  const timers = mockTimers();
  let random = 0.9;
  const page = monitoring(async () => tree, Date, { realModules: true, timers, random: () => random });
  await flush();
  page.toggleMock();
  assert.equal(page.mockPoints.length, 20);
  const events = [];
  page.mock.subscribe('status_change', payload => events.push(payload));
  for (let index = 0; index < 20; index++) {
    random = index / 20 + 0.001;
    const previous = events.length;
    timers.run(delay => delay >= 5000);
    const emitted = events.slice(previous);
    assert.ok(emitted.length > 0);
    for (const event of emitted) {
      const point = page.mockPoints[index];
      assert.equal(event.charge_point_code, point.code);
      assert.ok(point.connectors.some(connector => connector.connector_id === event.connector_id));
    }
  }
  page.mock.disconnect();
  assert.equal(timers.size(), 0);
});

test('mock status changes update the grid, connector totals and an open drawer', async () => {
  const timers = mockTimers();
  const randoms = [];
  const page = monitoring(async () => tree, Date, {
    realModules: true, timers, random: () => randoms.length ? randoms.shift() : 0.9,
  });
  await flush();
  page.toggleMock();
  page.openDetail();
  const previous = Number(page.document.getElementById('mon-charging').textContent);
  randoms.push(0, 0, 2 / 9, 0.9);
  timers.run(delay => delay >= 5000);
  assert.equal(Number(page.document.getElementById('mon-charging').textContent), previous + 1);
  assert.equal(page.mockPoints[0].connectors[0].ocpp_status, 'Charging');
  assert.match(page.pointHtml('CP-HN-01'), /Đang sạc/);
  assert.match(page.document.getElementById('detail-body').innerHTML, /CP-HN-01/);
  assert.equal(page.mockPoints[0].last_seen_at.length, 24);
  page.mock.disconnect();
});

for (const type of ['Soft', 'Hard']) {
  test(`confirmed demo Reset ${type} recovers the grid and drawer without calling backend`, async () => {
    const timers = mockTimers();
    const page = monitoring(async () => tree, Date, { realModules: true, timers });
    await flush();
    page.toggleMock();
    page.openDetail();
    const command = page.restart.handleRestart('CP-HN-01', type, false, element(), page.resetBindings.at(-1));
    assert.equal(page.apiResets.length, 0);
    assert.equal(page.mockPoints[0].status, 'online');
    page.confirm();
    await command;
    assert.equal(page.apiResets.length, 0);
    assert.equal(page.mockPoints[0].status, 'offline');
    assert.ok(page.mockPoints[0].connectors.every(connector => connector.status === 'unknown'));
    assert.match(page.pointHtml('CP-HN-01'), /Ngoại tuyến/);
    assert.match(page.document.getElementById('detail-body').innerHTML, /data-cp-code="CP-HN-01"[\s\S]*?data-cp-offline="true"/);
    assert.match(page.toasts.at(-1), new RegExp(`chấp nhận Reset ${type}`));

    // Refresh must retain the current mock state while the restart timer runs.
    page.document.getElementById('btn-refresh-monitoring').handlers.click();
    assert.equal(page.mockPoints[0].status, 'offline');
    assert.match(page.pointHtml('CP-HN-01'), /Ngoại tuyến/);
    assert.equal(page.requests(), 1);
    timers.run(delay => delay === 2000);
    assert.equal(page.mockPoints[0].status, 'online');
    assert.ok(page.mockPoints[0].connectors.every(connector => connector.status === 'rảnh' && connector.ocpp_status === 'Available'));
    assert.doesNotMatch(page.pointHtml('CP-HN-01'), /Ngoại tuyến/);
    assert.match(page.document.getElementById('detail-body').innerHTML, /data-cp-code="CP-HN-01"[\s\S]*?data-cp-offline="false"/);
    page.mock.disconnect();
  });
}

test('demo Reset rejects offline, unknown, invalid and duplicate commands', async () => {
  const timers = mockTimers();
  const page = monitoring(async () => tree, Date, { realModules: true, timers });
  await flush();
  page.toggleMock();
  await assert.rejects(page.mock.resetChargePoint('CP-HN-04', 'Soft'), /ngoại tuyến/);
  await assert.rejects(page.mock.resetChargePoint('MISSING', 'Soft'), /không thuộc/);
  await assert.rejects(page.mock.resetChargePoint('CP-HN-01', 'Other'), /không hợp lệ/);
  assert.equal(timers.size(), 1);
  await page.mock.resetChargePoint('CP-HN-01', 'Soft');
  await assert.rejects(page.mock.resetChargePoint('CP-HN-01', 'Hard'), /đang khởi động lại/);
  assert.equal(timers.size(), 2);
  assert.equal(page.apiResets.length, 0);
  page.mock.disconnect();
  await assert.rejects(page.mock.resetChargePoint('CP-HN-01', 'Soft'), /không thuộc/);
});

test('random mock updates cannot bring a restarting point online early', async () => {
  const timers = mockTimers();
  const page = monitoring(async () => tree, Date, { realModules: true, timers, random: () => 0 });
  await flush();
  page.toggleMock();
  await page.mock.resetChargePoint('CP-HN-01', 'Soft');
  timers.run(delay => delay >= 5000);
  assert.equal(page.mockPoints[0].status, 'offline');
  timers.run(delay => delay === 2000);
  assert.equal(page.mockPoints[0].status, 'online');
  page.mock.disconnect();
});

test('demo Reset rechecks offline state after confirmation', async () => {
  const timers = mockTimers();
  const page = monitoring(async () => tree, Date, { realModules: true, timers, random: () => 0 });
  await flush();
  page.toggleMock();
  page.openDetail();
  const command = page.restart.handleRestart('CP-HN-01', 'Soft', false, element(), page.resetBindings.at(-1));
  timers.run(delay => delay >= 5000); // A status event followed by loss of connection.
  page.confirm();
  await command;
  assert.match(page.toasts.at(-1), /ngoại tuyến/);
  assert.equal(page.apiResets.length, 0);
  assert.equal(timers.size(), 1);
  page.mock.disconnect();
});

test('switching away from demo cancels its pending restart and all event timers', async () => {
  const timers = mockTimers();
  const page = monitoring(async () => structuredClone(tree), Date, { realModules: true, timers });
  await flush();
  page.toggleMock();
  await page.mock.resetChargePoint('CP-HN-01', 'Soft');
  assert.equal(timers.size(), 2);
  page.toggleMock();
  await flush();
  assert.equal(timers.size(), 0);
  assert.equal(page.total(), 1);
  assert.match(page.html(), /REAL-01/);
  assert.doesNotMatch(page.html(), /CP-HN/);
  assert.equal(page.mock.isConnected(), false);
  page.toggleMock();
  assert.equal(timers.size(), 1);
  assert.equal(page.mockPoints[0].status, 'online');
  page.mock.disconnect();
});

test('confirmation from an old data source cannot send a Reset after switching', async () => {
  const timers = mockTimers();
  const page = monitoring(async () => tree, Date, { realModules: true, timers });
  await flush();
  page.toggleMock();
  page.openDetail();
  const command = page.restart.handleRestart('CP-HN-01', 'Soft', false, element(), page.resetBindings.at(-1));
  page.toggleMock();
  await flush();
  page.toggleMock();
  page.confirm();
  await command;
  assert.equal(page.apiResets.length, 0);
  assert.equal(page.mockPoints[0].status, 'online');
  assert.equal(timers.size(), 1);
  assert.match(page.toasts.at(-1), /Nguồn dữ liệu đã thay đổi/);
  page.mock.disconnect();
});

test('API mode Reset still sends the selected code and type to backend', async () => {
  const timers = mockTimers();
  const page = monitoring(async () => tree, Date, { realModules: true, timers });
  await flush();
  page.openDetail();
  const command = page.restart.handleRestart('REAL-01', 'Hard', false, element(), page.resetBindings.at(-1));
  page.confirm();
  await command;
  assert.deepEqual(page.apiResets, [{ code: 'REAL-01', type: 'Hard' }]);
  assert.equal(timers.size(), 0);
});

test('demo connection label stays explicit when backend SSE disconnects', async () => {
  const timers = mockTimers();
  const page = monitoring(async () => tree, Date, { realModules: true, timers });
  await flush();
  page.toggleMock();
  page.callbacks._error();
  assert.equal(page.document.getElementById('sse-label').textContent, 'Đang mô phỏng');
  page.callbacks._connected();
  assert.equal(page.document.getElementById('sse-label').textContent, 'Đang mô phỏng');
  assert.equal(page.requests(), 1);
  page.toggleMock();
  await flush();
  assert.equal(page.document.getElementById('sse-label').textContent, 'Đang theo dõi');
  assert.equal(timers.size(), 0);
});

function protectedForm(onSubmit) {
  const form = element();
  const button = element();
  button.textContent = 'Lưu';
  form.querySelector = () => button;
  const window = {};
  const context = vm.createContext({ window, document: { createElement: element },
    FormData: class { entries() { return [['name', 'Station']]; } },
  });
  vm.runInContext(read('form_guard.js'), context);
  window.FormGuard.protect(form, onSubmit, { keepDisabledOnSuccess: true, onError() {} });
  return { button, submit: () => form.handlers.submit({ preventDefault() {} }) };
}

test('form rejects simultaneous submits and stays disabled after successful save', async () => {
  let complete;
  let calls = 0;
  const form = protectedForm(() => { calls++; return new Promise(resolve => { complete = resolve; }); });
  const first = form.submit();
  await form.submit();
  assert.equal(calls, 1);
  complete();
  await first;
  await form.submit();
  assert.equal(calls, 1);
  assert.equal(form.button.disabled, true);
});

test('form becomes usable again after save failure', async () => {
  let calls = 0;
  const form = protectedForm(async () => { calls++; throw Error('failed'); });
  await form.submit();
  assert.equal(form.button.disabled, false);
  assert.equal(form.button.textContent, 'Lưu');
  await form.submit();
  assert.equal(calls, 2);
});

function restartClient(reset) {
  const document = { body: element(), createElement: element, addEventListener() {} };
  const window = {};
  vm.runInContext(read('restart_button.js'), vm.createContext({ document, window,
    ApiClient: { resetChargePoint: reset }, showToast() {},
  }));
  return { module: window.RestartButton,
    confirm: () => document.body.children[0].querySelector('#restart-confirm-ok').handlers.click() };
}

test('Reset requires confirmation and allows only one pending command per point', async () => {
  let calls = 0;
  let complete;
  const client = restartClient(() => { calls++; return new Promise(resolve => { complete = resolve; }); });
  const first = client.module.handleRestart('CP-01', 'Soft', false, element());
  await client.module.handleRestart('CP-01', 'Soft', false, element());
  assert.equal(calls, 0);
  client.confirm();
  await flush();
  assert.equal(calls, 1);
  await client.module.handleRestart('CP-01', 'Hard', false, element());
  assert.equal(calls, 1);
  complete({ status: 'Accepted' });
  await first;
});

test('opening another Reset confirmation releases the old dialog waiter', async () => {
  const client = restartClient(async () => ({}));
  const first = client.module.showConfirm('CP-01', 'Soft');
  const second = client.module.showConfirm('CP-02', 'Hard');
  assert.equal(await first, false);
  client.confirm();
  assert.equal(await second, true);
});

test('offline point does not send Reset', async () => {
  let calls = 0;
  const client = restartClient(async () => { calls++; return {}; });
  await client.module.handleRestart('OFFLINE', 'Soft', true, element());
  assert.equal(calls, 0);
});

test('bound Reset button forwards the chosen type to the provided mock transport', async () => {
  let backendCalls = 0;
  const calls = [];
  const client = restartClient(async () => { backendCalls++; return {}; });
  const button = element();
  button.dataset = { cpCode: 'CP-HN-01', cpOffline: 'false' };
  const wrapper = element();
  wrapper.querySelector('.restart-controls__type').value = 'Hard';
  button.closest = () => wrapper;
  client.module.bindEvents({ querySelectorAll: () => [button] }, {
    resetChargePoint: async (code, type) => { calls.push({ code, type }); return { status: 'Accepted' }; },
    isCurrentSource: () => true,
  });
  button.handlers.click.call(button);
  assert.equal(calls.length, 0);
  client.confirm();
  await flush();
  assert.deepEqual(calls, [{ code: 'CP-HN-01', type: 'Hard' }]);
  assert.equal(backendCalls, 0);
  assert.equal(button.disabled, false);
});

for (const timestamp of ['2026-10-04T13:10:22', '2026-10-04T18:10:22+05:00']) {
  test(`last-seen time preserves the UTC instant for ${timestamp}`, async () => {
    class IsoDate extends Date {
      toLocaleString() { return this.toISOString(); }
    }
    const data = structuredClone(tree);
    data[0].charge_points[0].status = 'offline';
    data[0].charge_points[0].last_seen_at = timestamp;
    const page = monitoring(async () => data, IsoDate);
    await flush();
    const html = page.document.getElementById('monitoring-grid').children[0].innerHTML;
    assert.match(html, /Liên lạc lần cuối: 2026-10-04T13:10:22.000Z/);
  });
}

test('SSE errors keep EventSource alive for native reconnection', () => {
  const instances = [];
  class FakeEventSource {
    static CLOSED = 2;
    constructor(url, options) { this.url = url; this.options = options; this.readyState = 0; this.closes = 0; instances.push(this); }
    addEventListener() {}
    close() { this.closes++; this.readyState = FakeEventSource.CLOSED; }
  }
  const window = {};
  vm.runInContext(read('sse_client.js'), vm.createContext({ window, EventSource: FakeEventSource }));
  let connections = 0;
  let errors = 0;
  window.SseClient.on('_connected', () => connections++);
  window.SseClient.on('_error', () => errors++);
  window.SseClient.connect('/api/monitoring/sse');
  instances[0].onopen();
  instances[0].onerror({});
  instances[0].onopen();
  assert.equal(connections, 2);
  assert.equal(errors, 1);
  assert.equal(instances.length, 1);
  assert.equal(instances[0].closes, 0);
  assert.equal(instances[0].options.withCredentials, true);
  window.SseClient.disconnect();
  assert.equal(instances[0].closes, 1);
});
