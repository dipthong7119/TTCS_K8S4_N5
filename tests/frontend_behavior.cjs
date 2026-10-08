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

function monitoring(getTree, clock = Date, options = {}) {
  const ids = new Map();
  const document = {
    handlers: {}, body: element(),
    getElementById(id) { if (!ids.has(id)) ids.set(id, element()); return ids.get(id); },
    createElement: element,
    addEventListener(name, fn) { this.handlers[name] = fn; },
  };
  if (options.startControls) {
    document.getElementById('detail-body').querySelectorAll = selector =>
      selector === '.start-charging-controls' ? options.startControls : [];
  }
  const callbacks = {};
  const toasts = [];
  const resetBindings = [];
  const apiResets = [];
  let requests = 0;
  const windowHandlers = {};
  const context = vm.createContext({
    document, window: { location: { assign: url => options.redirects?.push(url) }, addEventListener: (name, fn) => { windowHandlers[name] = fn; } }, AbortController, setTimeout: options.setTimeout || setTimeout, clearTimeout: options.clearTimeout || clearTimeout, Date: clock, console,
    ApiClient: {
      remoteStartChargePoint: options.remoteStart || (async () => ({ status: 'Rejected' })),
      listAllSessions: options.listSessions || (async () => ({ items: [] })),
      getCurrentSession: options.currentSession || (async () => null),
      getMonitoringTree: () => { requests++; return getTree(); },
      resetChargePoint: async (code, type) => { apiResets.push({ code, type }); return { status: 'Accepted' }; },
    },
    SseClient: {
      on: (name, fn) => { callbacks[name] = fn; },
      connect() { if (options.sseConnectError) throw Error('EventSource unavailable'); },
    },
    RestartButton: { createMarkup: () => '', bindEvents() {} },
    showToast: message => toasts.push(message),
  });
  if (options.realModules) {
    document.getElementById('monitoring-grid').dataset.canReset = 'true';
    vm.runInContext(read('restart_button.js'), context);
    const bind = context.window.RestartButton.bindEvents;
    context.window.RestartButton.bindEvents = (body, bindings) => { resetBindings.push(bindings); bind(body, bindings); };
  }
  vm.runInContext(read('pages/monitoring_grid.js'), context);
  document.handlers.DOMContentLoaded();
  return { document, callbacks, toasts, apiResets, resetBindings, windowHandlers,
    restart: context.window.RestartButton,
    confirm: () => document.body.children[0].querySelector('#restart-confirm-ok').handlers.click(),
    openDetail: () => document.getElementById('monitoring-grid').children[0].querySelector('.station-card__open').handlers.click(),
    filter(value) {
      document.getElementById('mon-status-filter').value = value;
      document.getElementById('mon-status-filter').handlers.change();
    },
    search(value) {
      document.getElementById('mon-search').value = value;
      document.getElementById('mon-status-filter').handlers.change();
    },
    codes: () => [...document.getElementById('monitoring-grid').children.map(child => child.innerHTML).join('').matchAll(/data-cp-code="([^"]+)"/g)].map(match => match[1]),
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
  assert.match(page.html(), /Không có kết quả/);
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

function mixedTree() {
  const ready = { code: 'CP_AEON_01', status: 'online', ocpp_status: 'Available', connectors: [
    { connector_id: 1, status: 'rảnh', ocpp_status: 'Available', error_code: 'NoError' },
  ] };
  const fault = { code: 'CP_AEON_FAULT', status: 'online', ocpp_status: 'Faulted', connectors: [
    { connector_id: 1, status: 'lỗi', ocpp_status: 'Faulted', error_code: 'GroundFailure' },
    { connector_id: 2, status: 'lỗi', ocpp_status: 'Faulted', error_code: 'GroundFailure' },
  ] };
  return [
    { id: 7, name: 'AEON Mall', status: 'active', charge_points: [ready, fault] },
    { id: 8, name: 'Thủ Thiêm', status: 'maintenance', charge_points: [
      { code: 'CP_DEMO_MAINT_01', status: 'online', ocpp_status: 'Unavailable', connectors: [
        { connector_id: 1, status: 'lỗi', ocpp_status: 'Unavailable', error_code: 'NoError' },
      ] },
    ] },
    { id: 9, name: 'Vincom', status: 'active', charge_points: [{ ...structuredClone(ready), code: 'CP_VINCOM_01' }] },
  ];
}

test('fault filter shows only faulty points in grid, list and drawer; totals count each point once', async () => {
  const data = mixedTree();
  const original = JSON.stringify(data);
  const page = monitoring(async () => data);
  await flush();
  assert.equal(page.total(), 4);
  assert.equal(Number(page.document.getElementById('mon-fault').textContent), 1);
  page.filter('lỗi');
  assert.deepEqual(page.codes(), ['CP_AEON_FAULT']);
  assert.equal(page.document.getElementById('monitoring-grid').children.length, 1);
  page.document.getElementById('view-list').handlers.click();
  assert.equal(page.document.getElementById('monitoring-grid').classList.contains('list-view'), true);
  assert.deepEqual(page.codes(), ['CP_AEON_FAULT']);
  page.openDetail();
  assert.match(page.document.getElementById('detail-body').innerHTML, /CP_AEON_FAULT/);
  assert.doesNotMatch(page.document.getElementById('detail-body').innerHTML, /CP_AEON_01/);
  page.document.getElementById('view-grid').handlers.click();
  assert.equal(page.document.getElementById('monitoring-grid').classList.contains('list-view'), false);
  page.filter('');
  assert.equal(page.codes().length, 4);
  assert.equal(page.total(), 4);
  assert.equal(JSON.stringify(data), original);
});

test('Unavailable is gray and has its own filter even when the API internal status is lỗi', async () => {
  const page = monitoring(async () => mixedTree());
  await flush();
  page.filter('unavailable');
  assert.deepEqual(page.codes(), ['CP_DEMO_MAINT_01']);
  assert.match(page.html(), /badge--offline">Tạm ngừng/);
  assert.doesNotMatch(page.html(), /badge--fault/);
  assert.equal(Number(page.document.getElementById('mon-fault').textContent), 1);
});

test('a faulty connector or non-NoError code marks its point faulty without requiring global Faulted', async () => {
  const data = mixedTree();
  data[0].charge_points[0].connectors[0] = { connector_id: 1, status: 'lỗi', ocpp_status: 'Faulted', error_code: 'NoError' };
  data[2].charge_points[0].connectors[0].error_code = 'GroundFailure';
  const page = monitoring(async () => data);
  await flush();
  page.filter('lỗi');
  assert.deepEqual(page.codes(), ['CP_AEON_01', 'CP_AEON_FAULT', 'CP_VINCOM_01']);
  assert.equal(Number(page.document.getElementById('mon-fault').textContent), 3);
  assert.match(page.pointHtml('CP_VINCOM_01'), /Báo lỗi/);
});

for (const [wanted, raw, connection] of [
  ['online', 'Available', 'online'], ['offline', 'Available', 'offline'],
  ['rảnh', 'Available', 'online'], ['bận', 'Charging', 'online'],
  ['đặt chỗ', 'Reserved', 'online'], ['unknown', 'unknown', 'online'],
]) {
  test(`${wanted} filter excludes other points in the same station`, async () => {
    const data = mixedTree();
    const target = { code: 'MATCH', status: connection, ocpp_status: raw, connectors: [
      { connector_id: 1, status: 'unknown', ocpp_status: raw },
    ] };
    data[0].charge_points = [data[0].charge_points[1], target];
    data.splice(1);
    if (wanted === 'online') data[0].charge_points[0].status = 'offline';
    const page = monitoring(async () => data);
    await flush();
    page.filter(wanted);
    assert.deepEqual(page.codes(), ['MATCH']);
  });
}

test('offline points with stale Available or Charging do not appear as ready or busy', async () => {
  const data = mixedTree();
  data[0].charge_points[0].status = 'offline';
  data[2].charge_points[0].status = 'offline';
  data[2].charge_points[0].connectors[0].ocpp_status = 'Charging';
  const page = monitoring(async () => data);
  await flush();
  page.filter('rảnh');
  assert.deepEqual(page.codes(), []);
  page.filter('bận');
  assert.deepEqual(page.codes(), []);
  assert.equal(Number(page.document.getElementById('mon-charging').textContent), 0);
  page.filter('offline');
  assert.match(page.pointHtml('CP_AEON_01'), /Chưa rõ/);
  assert.doesNotMatch(page.pointHtml('CP_AEON_01'), /Sẵn sàng/);
});

test('searching a point code hides healthy siblings; station search combines with point status', async () => {
  const page = monitoring(async () => mixedTree());
  await flush();
  page.search(' cp_aeon_fault ');
  assert.deepEqual(page.codes(), ['CP_AEON_FAULT']);
  page.search('aeon mall');
  assert.deepEqual(page.codes(), ['CP_AEON_01', 'CP_AEON_FAULT']);
  page.filter('lỗi');
  assert.deepEqual(page.codes(), ['CP_AEON_FAULT']);
  page.search('VINCOM');
  assert.deepEqual(page.codes(), []);
  page.filter('');
  assert.deepEqual(page.codes(), ['CP_VINCOM_01']);
});

test('typing in the search field renders the filtered points after the debounce', async () => {
  const page = monitoring(async () => mixedTree());
  await flush();
  page.document.getElementById('mon-search').value = 'CP_AEON_FAULT';
  page.document.getElementById('mon-search').handlers.input();
  await new Promise(resolve => setTimeout(resolve, 250));
  assert.deepEqual(page.codes(), ['CP_AEON_FAULT']);
});

test('SSE keeps the fault filter and drawer in sync and closes a drawer with no matching points', async () => {
  const data = mixedTree();
  const page = monitoring(async () => data);
  await flush();
  page.filter('lỗi');
  page.openDetail();
  const points = structuredClone(data[0].charge_points);
  // The fault moves from one point to its sibling in the same station.
  points[0].ocpp_status = 'Faulted';
  points[1].ocpp_status = 'Available';
  points[1].connectors.forEach(connector => Object.assign(connector, { status: 'rảnh', ocpp_status: 'Available', error_code: 'NoError' }));
  page.callbacks.status_update({ station_id: 7, charge_points: points });
  assert.deepEqual(page.codes(), ['CP_AEON_01']);
  assert.match(page.document.getElementById('detail-body').innerHTML, /CP_AEON_01/);
  assert.doesNotMatch(page.document.getElementById('detail-body').innerHTML, /CP_AEON_FAULT/);
  points[0].ocpp_status = 'Available';
  page.callbacks.status_update({ station_id: 7, charge_points: points });
  assert.deepEqual(page.codes(), []);
  assert.equal(page.document.getElementById('detail-backdrop').classList.contains('is-hidden'), true);
  assert.equal(Number(page.document.getElementById('mon-fault').textContent), 0);
  points[1].ocpp_status = 'Faulted';
  page.callbacks.status_update({ station_id: 7, charge_points: points });
  assert.deepEqual(page.codes(), ['CP_AEON_FAULT']);
  assert.equal(page.document.getElementById('mon-status-filter').value, 'lỗi');
});

test('reconnect refresh preserves the fault filter and filtered drawer', async () => {
  const page = monitoring(async () => mixedTree());
  await flush();
  page.filter('lỗi');
  page.openDetail();
  page.callbacks._connected();
  await flush();
  assert.deepEqual(page.codes(), ['CP_AEON_FAULT']);
  assert.doesNotMatch(page.document.getElementById('detail-body').innerHTML, /CP_AEON_01/);
  page.callbacks._error();
  assert.equal(page.document.getElementById('sse-label').textContent, 'Đang kết nối lại');
});

for (const closeBy of ['button', 'backdrop', 'Escape']) {
  test(`drawer closes by ${closeBy}, stays closed after SSE and can reopen`, async () => {
    const page = monitoring(async () => mixedTree());
    await flush();
    page.filter('lỗi');
    page.openDetail();
    const backdrop = page.document.getElementById('detail-backdrop');
    assert.equal(backdrop.classList.contains('is-hidden'), false);
    if (closeBy === 'button') page.document.getElementById('detail-close').handlers.click();
    if (closeBy === 'backdrop') backdrop.handlers.click({ target: backdrop, currentTarget: backdrop });
    if (closeBy === 'Escape') page.document.handlers.keydown({ key: 'Escape' });
    assert.equal(backdrop.classList.contains('is-hidden'), true);
    page.callbacks.status_update({ station_id: 7, charge_points: mixedTree()[0].charge_points });
    assert.equal(backdrop.classList.contains('is-hidden'), true);
    page.openDetail();
    assert.equal(backdrop.classList.contains('is-hidden'), false);
    assert.doesNotMatch(page.document.getElementById('detail-body').innerHTML, /CP_AEON_01/);
  });
}

test('clicking inside the drawer does not close it', async () => {
  const page = monitoring(async () => mixedTree());
  await flush();
  page.openDetail();
  const backdrop = page.document.getElementById('detail-backdrop');
  backdrop.handlers.click({ target: page.document.getElementById('detail-body'), currentTarget: backdrop });
  assert.equal(backdrop.classList.contains('is-hidden'), false);
});

test('filter, refresh, view toggle and close buttons still work when SSE cannot start', async () => {
  const page = monitoring(async () => mixedTree(), Date, { sseConnectError: true });
  await flush();
  page.filter('lỗi');
  assert.deepEqual(page.codes(), ['CP_AEON_FAULT']);
  page.document.getElementById('view-list').handlers.click();
  assert.equal(page.document.getElementById('monitoring-grid').classList.contains('list-view'), true);
  page.openDetail();
  page.document.getElementById('detail-close').handlers.click();
  assert.equal(page.document.getElementById('detail-backdrop').classList.contains('is-hidden'), true);
  page.document.getElementById('btn-refresh-monitoring').handlers.click();
  await flush();
  assert.equal(page.requests(), 2);
  assert.deepEqual(page.codes(), ['CP_AEON_FAULT']);
});

test('a late HTTP response cannot overwrite newer SSE state', async () => {
  let resolve;
  let requests = 0;
  const page = monitoring(() => ++requests === 1 ? Promise.resolve(mixedTree()) : new Promise(done => { resolve = done; }));
  await flush();
  page.filter('lỗi');
  page.document.getElementById('btn-refresh-monitoring').handlers.click();
  const points = mixedTree()[0].charge_points.slice(0, 1);
  page.callbacks.status_update({ station_id: 7, charge_points: points });
  assert.deepEqual(page.codes(), []);
  resolve(mixedTree());
  await flush();
  assert.deepEqual(page.codes(), []);
});

test('only the newest of overlapping HTTP loads takes effect', async () => {
  const completions = [];
  const page = monitoring(() => new Promise(done => completions.push(done)));
  page.document.getElementById('btn-refresh-monitoring').handlers.click();
  completions[1](tree);
  await flush();
  completions[0](mixedTree());
  await flush();
  assert.deepEqual(page.codes(), ['REAL-01']);
});

test('Reset from the filtered drawer sends the selected code and type to backend', async () => {
  const page = monitoring(async () => mixedTree(), Date, { realModules: true });
  await flush();
  page.filter('lỗi');
  page.openDetail();
  const command = page.restart.handleRestart('CP_AEON_FAULT', 'Hard', false, element(), page.resetBindings.at(-1));
  assert.equal(page.apiResets.length, 0);
  page.confirm();
  await command;
  assert.deepEqual(page.apiResets, [{ code: 'CP_AEON_FAULT', type: 'Hard' }]);
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
  const document = { body: element(), createElement: element, handlers: {},
    addEventListener(name, fn) { this.handlers[name] = fn; } };
  const window = {};
  vm.runInContext(read('restart_button.js'), vm.createContext({ document, window,
    ApiClient: { resetChargePoint: reset }, showToast() {},
  }));
  return { module: window.RestartButton, document,
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

for (const closeBy of ['close', 'cancel', 'backdrop', 'Escape']) {
  test(`Reset confirmation can be dismissed by ${closeBy} without sending a command`, async () => {
    let calls = 0;
    const client = restartClient(async () => { calls++; return {}; });
    const command = client.module.handleRestart('CP-01', 'Soft', false, element());
    const modal = client.document.body.children[0];
    if (closeBy === 'close') modal.querySelector('#restart-confirm-close').handlers.click();
    if (closeBy === 'cancel') modal.querySelector('#restart-confirm-cancel').handlers.click();
    if (closeBy === 'backdrop') modal.handlers.click({ target: modal });
    if (closeBy === 'Escape') client.document.handlers.keydown({ key: 'Escape' });
    await command;
    assert.equal(calls, 0);
    assert.equal(modal.classList.contains('is-hidden'), true);
    const again = client.module.showConfirm('CP-01', 'Hard');
    client.confirm();
    assert.equal(await again, true);
  });
}

test('offline point does not send Reset', async () => {
  let calls = 0;
  const client = restartClient(async () => { calls++; return {}; });
  await client.module.handleRestart('OFFLINE', 'Soft', true, element());
  assert.equal(calls, 0);
});

test('bound Reset button forwards the chosen type to the provided transport', async () => {
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

function authClient(fetchResponse) {
  const redirects = [];
  const window = { location: { origin: 'http://localhost:8000', pathname: '/monitoring',
    search: '?status=fault', replace: url => redirects.push(url) } };
  const context = vm.createContext({ window, fetch: fetchResponse, URL });
  vm.runInContext(read('api_client.js'), context);
  return { api: window.ApiClient, redirects };
}

test('protected API 401 preserves the requested page; failed login stays on the form', async () => {
  const client = authClient(async () => ({ ok: false, status: 401,
    headers: { get: () => 'application/json' }, json: async () => ({ detail: 'Unauthorized' }) }));
  await assert.rejects(client.api.get('/auth/me'), error => error.status === 401);
  assert.deepEqual(client.redirects, ['/login?next=%2Fmonitoring%3Fstatus%3Dfault']);
  client.redirects.length = 0;
  await assert.rejects(client.api.login('a@example.com', 'wrong'), error => error.status === 401);
  assert.equal(client.redirects.length, 0);
});

test('API 204 has no body and AbortSignal cancellation is preserved', async () => {
  const controller = new AbortController();
  const client = authClient(async (_, config) => {
    assert.equal(config.signal, controller.signal);
    return { ok: true, status: 204, headers: { get: () => '' },
      text: async () => { throw Error('204 must not parse a body'); } };
  });
  assert.equal(await client.api.get('/sessions/current', { signal: controller.signal }), null);
  const aborted = new DOMException('Cancelled', 'AbortError');
  const cancellation = authClient(async () => { throw aborted; });
  await assert.rejects(cancellation.api.get('/auth/me'), error => error === aborted);
});

function loginPage(login, search = '') {
  const ids = new Map();
  const document = {
    getElementById(id) {
      if (id === 'auth-context') return null;
      if (!ids.has(id)) {
        const item = element();
        item.style = {}; item.validity = { valid: true }; item.attributes = {};
        item.setAttribute = (key, value) => { item.attributes[key] = value; };
        ids.set(id, item);
      }
      return ids.get(id);
    },
    querySelectorAll: () => [], createElement: element,
  };
  const form = document.getElementById('login-form');
  form.elements = { email: document.getElementById('email'), password: document.getElementById('password') };
  form.elements.email.value = 'owner@example.com';
  form.elements.password.value = 'ValidPassword123!'; form.elements.password.type = 'password';
  const button = element(); button.textContent = 'Đăng nhập'; form.querySelector = () => button;
  const destinations = [];
  const window = { location: { origin: 'http://localhost:8000', pathname: '/login', search,
    assign: url => destinations.push(url), replace: url => destinations.push(url) } };
  const context = vm.createContext({ document, window, URL, URLSearchParams, ApiClient: { login },
    FormData: class { entries() { return Object.entries(form.elements).map(([name, input]) => [name, input.value]); } },
  });
  vm.runInContext(read('auth_guard.js'), context);
  context.AuthGuard = window.AuthGuard;
  vm.runInContext(read('form_guard.js'), context);
  vm.runInContext(read('pages/login.js'), context);
  return { document, button, destinations, guard: window.AuthGuard,
    submit: () => form.handlers.submit({ preventDefault() {} }) };
}

test('next accepts permitted local routes and rejects external or unauthorized destinations', () => {
  const page = loginPage(async () => ({}));
  const safe = value => page.guard.safeNext(value, ['driver']);
  assert.equal(safe('/sessions/mine?tab=current#details'), '/sessions/mine?tab=current#details');
  for (const next of ['https://example.com', '//example.com', '/\\example.com', '/monitoring', '/unknown']) {
    assert.equal(safe(next), null, next);
  }
});

test('login password toggle changes type and accessible state; typing dismisses errors', () => {
  const page = loginPage(async () => ({}));
  const input = page.document.getElementById('password');
  const toggle = page.document.getElementById('password-toggle');
  toggle.handlers.click();
  assert.equal(input.type, 'text'); assert.equal(toggle.attributes['aria-pressed'], 'true');
  toggle.handlers.click();
  assert.equal(input.type, 'password'); assert.equal(toggle.attributes['aria-pressed'], 'false');
  page.document.getElementById('login-alert').style.display = 'flex';
  input.handlers.input();
  assert.equal(page.document.getElementById('login-alert').style.display, 'none');
});

test('invalid login stays editable, then valid login blocks duplicate submits during redirect', async () => {
  let calls = 0;
  let resolveLogin;
  const page = loginPage(() => { calls++; return new Promise(resolve => { resolveLogin = resolve; }); }, '?next=/monitoring');
  page.document.getElementById('email').validity.valid = false;
  await page.submit();
  assert.equal(calls, 0); assert.equal(page.button.disabled, false);
  page.document.getElementById('email').validity.valid = true;
  const pending = page.submit();
  await page.submit(); assert.equal(calls, 1);
  resolveLogin({ roles: ['station_owner'], redirect_to: '/stations' });
  await pending; await page.submit();
  assert.equal(calls, 1); assert.equal(page.button.disabled, true);
  assert.deepEqual(page.destinations, ['/monitoring']);
});

test('failed login displays the server message and allows retry', async () => {
  const page = loginPage(async () => { throw { status: 401, message: 'Wrong credentials' }; });
  await page.submit();
  assert.equal(page.document.getElementById('login-alert-text').textContent, 'Wrong credentials');
  assert.equal(page.document.getElementById('login-alert').style.display, 'flex');
  assert.equal(page.button.disabled, false);
});

test('legacy mock query and special passwords always use the login API', async () => {
  for (const password of ['success', 'wrong', 'locked']) {
    const calls = [];
    const page = loginPage(async (email, submittedPassword) => {
      calls.push({ email, password: submittedPassword });
      throw { status: 401, message: 'Wrong credentials' };
    }, '?mock=1');
    page.document.getElementById('email').value = 'missing@example.test';
    page.document.getElementById('password').value = password;
    await page.submit();
    assert.deepEqual(calls, [{ email: 'missing@example.test', password }]);
    assert.equal(page.document.getElementById('login-alert-text').textContent, 'Wrong credentials');
    assert.equal(page.button.disabled, false);
    assert.deepEqual(page.destinations, []);
  }
});

test('valid login follows the server response even with the legacy mock query', async () => {
  let calls = 0;
  const page = loginPage(async () => {
    calls++;
    return { roles: ['station_owner'], redirect_to: '/stations' };
  }, '?mock=1');
  await page.submit();
  assert.equal(calls, 1);
  assert.deepEqual(page.destinations, ['/stations']);
  assert.equal(page.button.disabled, true);
});


// SCRUM-194: run the real drawer handlers and API contract with a deterministic clock.
async function startPage(options = {}) {
  const controls = element();
  const select = controls.querySelector('[data-start-connector]');
  const button = controls.querySelector('[data-start-charging]');
  const tag = controls.querySelector('[data-start-tag]');
  const message = controls.querySelector('[data-start-message]');
  button.dataset.cpCode = 'REAL-01';
  const timers = new Map(); let timerId = 0; let now = Date.now();
  class Clock extends Date { static now() { return now; } }
  const calls = []; const redirects = [];
  const page = monitoring(options.getTree || (async () => structuredClone(tree)), Clock, {
    startControls: [controls], redirects,
    remoteStart: async (...args) => { calls.push(args); return options.remoteStart ? options.remoteStart(...args) : { status: 'Rejected' }; },
    listSessions: options.listSessions, currentSession: options.currentSession,
    setTimeout: (fn, ms) => { const id = ++timerId; timers.set(id, { fn, time: now + ms }); return id; },
    clearTimeout: id => timers.delete(id),
  });
  page.document.getElementById('auth-context').textContent = JSON.stringify({ roles: options.roles || ['driver'] });
  await flush(); page.openDetail();
  select.value = '1'; select.handlers.change(); tag.value = 'CARD-01'; tag.handlers.input();
  return { ...page, select, button, tag, message, calls, timers, redirects,
    click: () => button.handlers.click(),
    elapseWithoutTimers(ms) { now += ms; },
    async advance(ms) {
      now += ms;
      for (const [id, timer] of [...timers]) if (timer.time <= now && timers.delete(id)) await timer.fn();
      await flush();
    },
  };
}

test('SCRUM-191: blocks duplicate commands, survives drawer rerender and waits after Accepted', async () => {
  let resolve;
  const page = await startPage({ remoteStart: () => new Promise(done => { resolve = done; }) });
  const pending = page.click(); await page.click();
  assert.equal(page.calls.length, 1); assert.equal(page.button.disabled, true);
  assert.equal(page.select.disabled, true); assert.equal(page.tag.disabled, true);
  page.openDetail(); await page.click(); assert.equal(page.calls.length, 1);
  resolve({ status: 'Accepted' }); await pending;
  assert.equal(page.button.disabled, true); assert.match(page.message.textContent, /chờ phiên/);
  await page.advance(60000);
  assert.match(page.message.textContent, /Hết thời gian/); assert.equal(page.button.disabled, false);
  assert.equal(page.timers.size, 0); assert.equal(page.calls[0][3].signal.aborted, true);
});

test('SCRUM-192: Rejected suggests checking cable and allows retry', async () => {
  const page = await startPage(); await page.click();
  assert.match(page.message.textContent, /từ chối/); assert.match(page.message.textContent, /súng sạc/);
  assert.equal(page.button.disabled, false); assert.equal(page.timers.size, 0);
  await page.click(); assert.equal(page.calls.length, 2);
});

for (const [status, expected] of [[409, /đang bận/], [504, /Hết thời gian/], [502, /từ chối/], [0, /Mất mạng/]]) {
  test(`SCRUM-192: API error ${status} releases controls`, async () => {
    const page = await startPage({ remoteStart: async () => { throw { status, message: status === 0 ? 'Mất mạng' : 'error' }; } });
    await page.click(); assert.match(page.message.textContent, expected);
    assert.equal(page.button.disabled, false); assert.equal(page.timers.size, 0);
  });
}

test('SCRUM-191: timeout ignores a late Accepted response and never navigates', async () => {
  let resolve;
  const page = await startPage({ remoteStart: () => new Promise(done => { resolve = done; }) });
  const pending = page.click(); await page.advance(60000);
  resolve({ status: 'Accepted' }); await pending;
  assert.match(page.message.textContent, /Hết thời gian/); assert.deepEqual(page.redirects, []);
  assert.equal(page.timers.size, 0);
});

test('SCRUM-194: only a new session on the chosen point and connector navigates to T-48', async () => {
  let session = { id: 1, charge_point_code: 'OTHER', connector_number: 1, started_at: new Date().toISOString() };
  const page = await startPage({ remoteStart: async () => ({ status: 'Accepted' }), currentSession: async () => session });
  await page.click(); assert.deepEqual(page.redirects, []);
  session = { ...session, charge_point_code: 'REAL-01', connector_number: 2 };
  await page.advance(2000); assert.deepEqual(page.redirects, []);
  session = { ...session, connector_number: 1, started_at: '2000-01-01T00:00:00Z' };
  await page.advance(2000); assert.deepEqual(page.redirects, []);
  session.started_at = new Date(Date.now() + 10000).toISOString();
  await page.advance(2000); assert.deepEqual(page.redirects, ['/sessions/mine']);
  assert.match(page.message.textContent, /đã bắt đầu/); assert.equal(page.timers.size, 0);
});

test('SCRUM-191: delayed deadline timer cannot accept a response after 60 seconds', async () => {
  let resolve;
  let polls = 0;
  const page = await startPage({ remoteStart: () => new Promise(done => { resolve = done; }),
    currentSession: async () => { polls++; return null; } });
  const pending = page.click();
  page.elapseWithoutTimers(60000);
  resolve({ status: 'Accepted' }); await pending;
  assert.match(page.message.textContent, /Hết thời gian/);
  assert.equal(page.button.disabled, false);
  assert.equal(polls, 0);
  assert.equal(page.timers.size, 0);
});

test('SCRUM-191: delayed session response after deadline cannot report success', async () => {
  let resolve;
  const page = await startPage({ remoteStart: async () => ({ status: 'Accepted' }),
    currentSession: () => new Promise(done => { resolve = done; }) });
  const pending = page.click(); await flush();
  page.elapseWithoutTimers(60000);
  resolve({ charge_point_code: 'REAL-01', connector_number: 1, started_at: new Date().toISOString() });
  await pending;
  assert.match(page.message.textContent, /Hết thời gian/);
  assert.deepEqual(page.redirects, []);
  assert.equal(page.timers.size, 0);
});

test('SCRUM-191: returning after pagehide allows retry and ignores the previous command', async () => {
  const resolves = [];
  const page = await startPage({ remoteStart: () => new Promise(done => resolves.push(done)) });
  const first = page.click();
  page.windowHandlers.pagehide();
  assert.equal(page.button.disabled, false);
  assert.match(page.message.textContent, /Kiểm tra trạng thái/);
  page.openDetail();
  const second = page.click();
  assert.equal(page.calls.length, 2);
  resolves[0]({ status: 'Rejected' }); await first;
  assert.equal(page.button.disabled, true);
  assert.match(page.message.textContent, /Đang gửi/);
  resolves[1]({ status: 'Rejected' }); await second;
  assert.equal(page.button.disabled, false);
  assert.equal(page.timers.size, 0);
});

test('SCRUM-191: an old response after timeout cannot finish or replace a retry', async () => {
  const resolves = [];
  const page = await startPage({ remoteStart: () => new Promise(resolve => resolves.push(resolve)) });
  const first = page.click(); await page.advance(60000);
  const second = page.click();
  resolves[0]({ status: 'Rejected' }); await first;
  assert.equal(page.button.disabled, true); assert.match(page.message.textContent, /Đang gửi/);
  resolves[1]({ status: 'Accepted' }); await second;
  assert.match(page.message.textContent, /chờ phiên/);
  await page.advance(60000); assert.equal(page.timers.size, 0);
});

test('SCRUM-194: operator uses visible session list and navigates to audit only after real session', async () => {
  const page = await startPage({ roles: ['operator'], remoteStart: async () => ({ status: 'Accepted' }),
    listSessions: async () => ({ items: [{ id: 2, charge_point_code: 'REAL-01', connector_number: 1, started_at: new Date().toISOString() }] }) });
  await page.click(); assert.deepEqual(page.redirects, ['/audit']); assert.equal(page.timers.size, 0);
});

test('SCRUM-194: station owner stays on permitted detail page after session starts', async () => {
  const page = await startPage({ roles: ['station_owner'], remoteStart: async () => ({ status: 'Accepted' }),
    listSessions: async () => ({ items: [{ id: 2, charge_point_code: 'REAL-01', connector_number: 1, started_at: new Date().toISOString() }] }) });
  await page.click(); assert.deepEqual(page.redirects, []); assert.match(page.message.textContent, /đã bắt đầu/);
});

test('SCRUM-194: busy/offline connectors and missing or oversized tags cannot send a command', async () => {
  const page = await startPage();
  for (const value of ['', ' ', 'x'.repeat(21)]) {
    page.tag.value = value; page.tag.handlers.input(); await page.click();
    assert.equal(page.button.disabled, true);
  }
  page.tag.value = 'CARD-01'; page.tag.handlers.input();
  page.callbacks.status_update({ station_id: 42, charge_points: [{ ...tree[0].charge_points[0], connectors: [{ connector_id: 1, ocpp_status: 'Charging' }] }] });
  await page.click(); assert.equal(page.calls.length, 0);
  assert.equal(page.button.disabled, true);
});

test('SCRUM-194: remote start API encodes code and sends connector, tag and cancellation signal', async () => {
  const calls = []; const controller = new AbortController();
  const client = authClient(async (url, config) => {
    calls.push({ url, config });
    return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => ({ status: 'Accepted' }) };
  });
  await client.api.remoteStartChargePoint('CP/01', 2, 'TAG', { signal: controller.signal });
  assert.equal(calls[0].url, '/api/charge_points/CP%2F01/remote-start');
  assert.equal(calls[0].config.method, 'POST');
  assert.deepEqual(JSON.parse(calls[0].config.body), { connector_id: 2, id_tag: 'TAG' });
  assert.equal(calls[0].config.signal, controller.signal);
});

test('SCRUM-194: closing and reopening drawer during pending request preserves connector, tag and waiting state', async () => {
  let resolve;
  const page = await startPage({ remoteStart: () => new Promise(done => { resolve = done; }) });
  assert.equal(page.tag.value, 'CARD-01');
  assert.equal(page.select.value, '1');
  const pending = page.click();
  await flush();
  assert.equal(page.calls.length, 1);
  assert.equal(page.button.disabled, true);
  assert.match(page.message.textContent, /Đang gửi yêu cầu/);

  page.document.getElementById('detail-close').handlers.click();
  assert.equal(page.document.getElementById('detail-backdrop').classList.contains('is-hidden'), true);

  const freshControls = element();
  freshControls.querySelector('[data-start-charging]').dataset.cpCode = 'REAL-01';
  page.document.getElementById('detail-body').querySelectorAll = selector =>
    selector === '.start-charging-controls' ? [freshControls] : [];
  page.openDetail();

  const freshSelect = freshControls.querySelector('[data-start-connector]');
  const freshButton = freshControls.querySelector('[data-start-charging]');
  const freshTag = freshControls.querySelector('[data-start-tag]');
  const freshMessage = freshControls.querySelector('[data-start-message]');

  assert.equal(freshSelect.value, '1');
  assert.equal(freshTag.value, 'CARD-01');
  assert.equal(freshSelect.disabled, true);
  assert.equal(freshTag.disabled, true);
  assert.equal(freshButton.disabled, true);
  assert.equal(freshButton.textContent, 'Đang chờ bắt đầu sạc…');
  assert.match(freshMessage.textContent, /Đang gửi yêu cầu/);

  await freshButton.handlers.click();
  assert.equal(page.calls.length, 1);

  await page.advance(60000);
  assert.match(freshMessage.textContent, /Hết thời gian/);
  assert.equal(freshButton.disabled, false);
  assert.equal(freshTag.disabled, false);
  assert.equal(freshSelect.disabled, false);
  assert.equal(freshTag.value, 'CARD-01');

  resolve({ status: 'Accepted' });
  await pending;
});

test('SCRUM-194: leaving page (pagehide) clears pending timers and aborts in-flight request', async () => {
  const page = await startPage({ remoteStart: () => new Promise(() => {}) });
  page.click();
  await flush();
  assert.equal(page.timers.size, 1);
  assert.equal(page.calls[0][3].signal.aborted, false);
  assert.equal(typeof page.windowHandlers.pagehide, 'function');

  page.windowHandlers.pagehide();
  assert.equal(page.timers.size, 0);
  assert.equal(page.calls[0][3].signal.aborted, true);
});

function sessionPage(getSessions) {
  const ids = new Map();
  const document = {
    handlers: {},
    getElementById(id) {
      if (!ids.has(id)) { const el = element(); el.style = {}; ids.set(id, el); }
      return ids.get(id);
    },
    createElement: element,
    addEventListener(name, fn) { this.handlers[name] = fn; },
  };
  document.getElementById('sessions-page').dataset = { scope: 'mine', canRemoteStop: 'false', liveUpdates: 'false' };
  const calls = [], timers = [], toasts = [];
  const api = { listMySessions: async params => { calls.push(params); return getSessions(); },
    getCurrentSession: async () => null };
  vm.runInContext(read('pages/my_session.js'), vm.createContext({ document, window: {}, ApiClient: api,
    Date, Intl, console, setTimeout, clearTimeout, clearInterval() {},
    setInterval: fn => { timers.push(fn); return timers.length; },
    showToast: message => toasts.push(message),
  }));
  document.handlers.DOMContentLoaded();
  return { document, calls, timers, toasts };
}

test('driver session page uses the API and stays empty without fabricated sessions', async () => {
  const page = sessionPage(async () => ({ items: [], total: 0 }));
  await flush();
  assert.equal(page.calls.length, 1);
  assert.match(page.document.getElementById('sessions-tbody').innerHTML, /Chưa có phiên sạc nào/);
  assert.equal(page.document.getElementById('active-session-banner').style.display, 'none');
  assert.equal(page.document.getElementById('no-active-session-card').style.display, 'flex');
  assert.equal(page.timers.length, 0);
});

test('driver session banner displays API energy and never increments energy with a timer', async () => {
  const session = { id: 123, station_name: 'API station', charge_point_code: 'API-01', connector_number: 1,
    started_at: '2026-10-06T00:00:00Z', status: 'active', live_kwh: 1.234 };
  const page = sessionPage(async () => ({ items: [session], total: 1 }));
  await flush();
  assert.match(page.document.getElementById('sessions-tbody').innerHTML, /API-01/);
  assert.equal(page.document.getElementById('active-session-id').textContent, '#123');
  assert.match(page.document.getElementById('active-kwh').innerHTML, /1\.234/);
  assert.equal(page.timers.length, 1);
  page.timers[0]();
  assert.match(page.document.getElementById('active-kwh').innerHTML, /1\.234/);
});

test('driver session API failure reports the error without displaying sample sessions', async () => {
  const page = sessionPage(async () => { throw Error('Server unavailable'); });
  await flush();
  assert.match(page.document.getElementById('sessions-tbody').innerHTML, /Server unavailable/);
  assert.doesNotMatch(page.document.getElementById('sessions-tbody').innerHTML, /8888|EcoCharge/);
  assert.equal(page.document.getElementById('session-count').textContent, 'Lỗi kết nối');
  assert.equal(page.timers.length, 0);
});

const reconciliationSample = JSON.parse(fs.readFileSync(
  path.join(root, 'frontend/static/data/kwh_reconciliation_sample.json'), 'utf8'));
const inventoryTree = [
  { id: 10, name: 'Vincom mới', charge_points: ['CP_VINCOM_01', 'CP_VINCOM_02'] },
  { id: 20, name: 'AEON Mall', charge_points: ['CP_AEON_01', 'CP_AEON_FAULT'] },
  { id: 30, name: 'Thủ Thiêm', charge_points: ['CP_DEMO_MAINT_01'] },
  { id: 40, name: 'Thử nghiệm OCPP', charge_points: Array.from({ length: 20 }, (_, i) => `SIM-${String(i + 1).padStart(2, '0')}`) },
].map(station => ({ ...station, charge_points: station.charge_points.map((code, i) => ({
  id: station.id * 10 + i, code, connectors: [{ connector_id: 1 }],
})) }));

function reconciliationPage(tree = inventoryTree, options = {}) {
  const ids = new Map();
  const document = {
    handlers: {}, querySelectorAll: () => [],
    getElementById(id) {
      if (!ids.has(id)) ids.set(id, { ...element(), style: {} });
      return ids.get(id);
    },
    addEventListener(name, fn) { this.handlers[name] = fn; },
  };
  const requests = [], downloads = [];
  const context = vm.createContext({ document, console, Date, downloads,
    fetch: async url => {
      requests.push(url);
      if (url === '/api/reconciliation/kwh') {
        return { ok: Boolean(options.report), status: options.apiStatus ?? (options.report ? 200 : 404),
          json: async () => options.report };
      }
      if (url === '/static/data/kwh_reconciliation_sample.json') {
        return { ok: true, json: async () => structuredClone(options.sample ?? reconciliationSample) };
      }
      assert.equal(url, '/api/monitoring/tree');
      return { ok: !options.inventoryFailure, json: async () => structuredClone(tree) };
    },
  });
  vm.runInContext(read('pages/kwh_reconciliation.js'), context);
  vm.runInContext('downloadText = (text, filename, mime) => downloads.push({ text, filename, mime });', context);
  document.handlers.DOMContentLoaded();
  return { document, requests, downloads, context,
    state: name => JSON.parse(vm.runInContext(`JSON.stringify(${name})`, context)),
    html: () => document.getElementById('recon-tbody').innerHTML,
    filter(id) {
      document.getElementById('recon-station-filter').value = String(id);
      document.getElementById('recon-station-filter').handlers.change();
    },
    search(query) {
      document.getElementById('recon-search').value = query;
      document.getElementById('recon-search').handlers.input();
    },
    csv: () => document.getElementById('recon-export-csv').handlers.click(),
    markdown: () => document.getElementById('recon-export-md').handlers.click(),
  };
}

test('reconciliation synchronizes fixture codes and station names from the current inventory', async () => {
  const page = reconciliationPage();
  await flush();
  const sessions = page.state('allSessions');
  assert.equal(sessions.length, 20);
  assert.equal(new Set(sessions.map(s => s.charge_point_code)).size, 20);
  assert.equal(sessions[0].station_name, 'Vincom mới');
  assert.equal(sessions[0].station_id, 10);
  assert.equal(sessions[0].system_kwh, 16.2);
  assert.match(page.html(), /CP_VINCOM_01/);
  assert.doesNotMatch(page.html(), />CP01</);
  assert.equal(page.document.getElementById('stat-system-kwh').textContent, '382.350 kWh');
  assert.equal(page.document.getElementById('recon-mock-notice').style.display, 'flex');
});

test('renamed sample devices use registered codes and connector numbers without mutating inventory', async () => {
  const tree = [{ id: 7, name: 'Trạm thực tế', charge_points: [
    { id: 91, code: 'NEW-01', connectors: [{ connector_id: 3 }] },
    { id: 92, code: 'NEW-02', connectors: [{ connector_id: 2 }] },
    { id: 93, code: 'NO-CONNECTORS', connectors: [] },
  ] }];
  const original = JSON.stringify(tree);
  const page = reconciliationPage(tree);
  await flush();
  const sessions = page.state('allSessions');
  assert.deepEqual(sessions.map(s => [s.charge_point_code, s.connector_id]), [['NEW-01', 3], ['NEW-02', 2]]);
  assert.equal(JSON.stringify(tree), original);
  assert.equal(page.document.getElementById('stat-total-sessions').textContent, 2);
  assert.equal(page.document.getElementById('stat-system-kwh').textContent, '39.600 kWh');
});

test('sample reconciliation with no registered devices stays empty and cannot claim a pass', async () => {
  const page = reconciliationPage([]);
  await flush();
  assert.deepEqual(page.state('allSessions'), []);
  assert.equal(page.document.getElementById('stat-total-sessions').textContent, 0);
  assert.match(page.document.getElementById('recon-verdict').innerHTML, /Chưa có phiên đối chiếu/);
  assert.doesNotMatch(page.document.getElementById('recon-verdict').innerHTML, /đều khớp/);
});

test('reconciliation keeps historical energy on its original device even after deletion', async () => {
  const report = structuredClone(reconciliationSample);
  report.metadata.is_sample = false;
  report.sessions = [report.sessions[0], { ...report.sessions[1], charge_point_code: 'DELETED-CP', station_name: 'Trạm cũ', station_id: 999 }];
  const original = JSON.stringify(report);
  const page = reconciliationPage(inventoryTree, { report });
  await flush();
  const sessions = page.state('allSessions');
  assert.equal(sessions[0].station_name, 'Vincom mới');
  assert.equal(sessions[1].charge_point_code, 'DELETED-CP');
  assert.equal(sessions[1].station_name, 'Trạm cũ');
  assert.equal(sessions[1].system_kwh, 23.4);
  assert.equal(JSON.stringify(report), original);
  assert.equal(page.document.getElementById('recon-mock-notice').style.display, undefined);
});

test('station and text filters select the same synchronized rows for display and export', async () => {
  const page = reconciliationPage();
  await flush();
  page.filter(20);
  assert.deepEqual(page.state('filteredSessions').map(s => s.charge_point_code), ['CP_AEON_01', 'CP_AEON_FAULT']);
  page.csv();
  assert.match(page.downloads[0].text, /AEON Mall/);
  assert.doesNotMatch(page.downloads[0].text, /CP_VINCOM/);
  page.filter('');
  page.search('Vincom mới');
  assert.equal(page.state('filteredSessions').length, 2);
  assert.equal(page.document.getElementById('recon-row-count').textContent, '2 phiên');
});

test('exports escape station names and label energy as sample data', async () => {
  const tree = structuredClone(inventoryTree);
  tree[0].name = 'Vincom, "Center" | Q1';
  const page = reconciliationPage(tree);
  await flush();
  page.filter(10);
  page.csv();
  page.markdown();
  assert.match(page.downloads[0].text, /"Vincom, ""Center"" \| Q1"/);
  assert.match(page.downloads[0].text, /Dữ liệu kWh mẫu/);
  assert.match(page.downloads[1].text, /Vincom, "Center" \\\| Q1/);
  assert.match(page.downloads[1].text, /Dữ liệu kWh mẫu/);
  const tableLines = page.downloads[1].text.split('\n').filter(line => line.startsWith('|'));
  assert.equal(tableLines[0].split('|').length, tableLines[1].split('|').length);
});

test('inventory failures never display unsynchronized sample codes', async () => {
  const page = reconciliationPage(inventoryTree, { inventoryFailure: true });
  await flush();
  assert.match(page.html(), /Không thể đồng bộ danh sách trạm và mã trụ/);
  assert.deepEqual(page.state('allSessions'), []);
  assert.doesNotMatch(page.html(), /CP01|CP_VINCOM/);
});

test('reconciliation authorization failures do not fall back to sample data', async () => {
  const page = reconciliationPage(inventoryTree, { apiStatus: 403 });
  await flush();
  assert.equal(page.requests.length, 1);
  assert.match(page.html(), /đăng nhập lại/);
  assert.deepEqual(page.state('allSessions'), []);
});
