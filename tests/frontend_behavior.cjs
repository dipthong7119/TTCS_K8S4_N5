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
  const context = vm.createContext({
    document, window: {}, setTimeout, clearTimeout, Date: clock, console,
    ApiClient: {
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
  return { document, callbacks, toasts, apiResets, resetBindings,
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

test('connector selection enables only usable options and start button clearly reports UI preview', async () => {
  const controls = element();
  const select = controls.querySelector('[data-start-connector]');
  const button = controls.querySelector('[data-start-charging]');
  const message = controls.querySelector('[data-start-message]');
  select.selectedOptions = [{ disabled: false }]; button.dataset.cpCode = 'REAL-01';
  const page = monitoring(async () => tree, Date, { startControls: [controls] });
  await flush(); page.openDetail();
  select.handlers.change(); assert.equal(button.disabled, true);
  select.value = '1'; select.handlers.change(); assert.equal(button.disabled, false);
  button.handlers.click();
  assert.match(message.textContent, /REAL-01, đầu nối 1/);
  assert.match(message.textContent, /chưa gửi yêu cầu sạc/);
  select.selectedOptions[0].disabled = true;
  select.handlers.change(); assert.equal(button.disabled, true);
  button.handlers.click(); assert.equal(message.textContent, '');
  assert.equal(page.apiResets.length, 0);
});
