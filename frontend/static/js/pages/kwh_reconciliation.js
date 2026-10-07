/**
 * SCRUM-184 — Xuất bảng đối chiếu kết quả kWh
 * Người thực hiện: Phạm Văn Tuấn (Frontend Developer)
 * Reviewer: Vy Hoàng Tú
 *
 * Chiến lược dữ liệu:
 *   1. Gọi GET /api/reconciliation/kwh  (API thật khi BE xong)
 *   2. Fallback: đọc file JSON mẫu SCRUM-183 (mock)
 *   3. Render bảng, lọc, sắp xếp, tìm kiếm, xuất CSV / Markdown
 */

'use strict';

/* ── Constants ──────────────────────────────────────────── */
const API_ENDPOINT = '/api/reconciliation/kwh';
const MOCK_ENDPOINT = '/static/data/kwh_reconciliation_sample.json';

/* ── State ──────────────────────────────────────────────── */
let allSessions = [];
let filteredSessions = [];
let sortState = { col: 'session_id', dir: 'asc' };
let activeFilter = 'all';
let searchQuery = '';

/* ── DOM refs ───────────────────────────────────────────── */
const tbody        = document.getElementById('recon-tbody');
const searchInput  = document.getElementById('recon-search');
const filterBtns   = document.querySelectorAll('.recon-filter-btn[data-filter]');
const exportCsvBtn = document.getElementById('recon-export-csv');
const exportMdBtn  = document.getElementById('recon-export-md');
const totalSessions    = document.getElementById('stat-total-sessions');
const matchedSessions  = document.getElementById('stat-matched');
const mismatchSessions = document.getElementById('stat-mismatch');
const matchPct         = document.getElementById('stat-match-pct');
const totalSystemKwh   = document.getElementById('stat-system-kwh');
const totalSimKwh      = document.getElementById('stat-sim-kwh');
const totalDiffKwh     = document.getElementById('stat-diff-kwh');
const verdictBanner    = document.getElementById('recon-verdict');
const metaTitle        = document.getElementById('recon-meta-title');
const metaGenerated    = document.getElementById('recon-meta-generated');
const metaTolerance    = document.getElementById('recon-meta-tolerance');
const rowCountEl       = document.getElementById('recon-row-count');

/* ── Bootstrap ──────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  renderSkeletons();
  loadData();
  bindEvents();
});

/* ── Data loading ───────────────────────────────────────── */
async function loadData() {
  try {
    const res = await fetch(API_ENDPOINT, { credentials: 'include' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    initPage(json);
  } catch (_) {
    // Fallback to mock JSON (dữ liệu mẫu SCRUM-183)
    try {
      const res = await fetch(MOCK_ENDPOINT);
      if (!res.ok) throw new Error('mock not found');
      const json = await res.json();
      showMockNotice();
      initPage(json);
    } catch (err) {
      showError('Không thể tải dữ liệu đối chiếu. Vui lòng thử lại sau.');
    }
  }
}

/* ── Init page with data ────────────────────────────────── */
function initPage(data) {
  const { metadata, summary, sessions } = data;

  /* Meta */
  if (metaTitle)     metaTitle.textContent     = metadata.title || '—';
  if (metaGenerated) metaGenerated.textContent = formatDateTime(metadata.generated_at);
  if (metaTolerance) metaTolerance.textContent = `≤ ${metadata.tolerance_kwh} kWh`;

  /* Summary cards */
  setText(totalSessions,    summary.total_sessions);
  setText(matchedSessions,  summary.matched_sessions);
  setText(mismatchSessions, summary.mismatched_sessions);
  setText(matchPct,         `${summary.match_percentage.toFixed(1)}%`);
  setText(totalSystemKwh,   `${summary.total_system_kwh.toFixed(3)} kWh`);
  setText(totalSimKwh,      `${summary.total_simulator_kwh.toFixed(3)} kWh`);
  setText(totalDiffKwh,     `${summary.total_difference_kwh.toFixed(3)} kWh`);

  /* Verdict */
  if (verdictBanner) {
    const passed = summary.verdict === 'PASSED';
    verdictBanner.className = `recon-verdict recon-verdict--${passed ? 'passed' : 'failed'}`;
    verdictBanner.innerHTML = `
      <div class="recon-verdict__icon">${passed ? '✓' : '✗'}</div>
      <span>${passed
        ? `Tất cả ${summary.matched_sessions}/${summary.total_sessions} phiên đều khớp — sai số trong ngưỡng cho phép`
        : `${summary.mismatched_sessions} phiên không khớp — cần xem xét lại`
      }</span>
      <span class="recon-verdict__meta">${summary.match_percentage.toFixed(1)}% MATCH</span>
    `;
  }

  /* Table */
  allSessions = sessions;
  applyFiltersAndRender();
}

/* ── Filter + Search + Sort ─────────────────────────────── */
function applyFiltersAndRender() {
  let result = [...allSessions];

  /* Filter by status */
  if (activeFilter !== 'all') {
    result = result.filter(s => s.status.toLowerCase() === activeFilter.toLowerCase());
  }

  /* Search */
  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    result = result.filter(s =>
      s.charge_point_code.toLowerCase().includes(q) ||
      String(s.session_id).includes(q) ||
      (s.notes || '').toLowerCase().includes(q)
    );
  }

  /* Sort */
  result.sort((a, b) => {
    const aVal = a[sortState.col] ?? '';
    const bVal = b[sortState.col] ?? '';
    const cmp = typeof aVal === 'number'
      ? aVal - bVal
      : String(aVal).localeCompare(String(bVal));
    return sortState.dir === 'asc' ? cmp : -cmp;
  });

  filteredSessions = result;
  renderTable(result);
}

/* ── Render table rows ──────────────────────────────────── */
function renderTable(sessions) {
  if (!tbody) return;

  if (sessions.length === 0) {
    tbody.innerHTML = `
      <tr><td colspan="10">
        <div class="recon-empty">
          <div class="recon-empty__icon">🔍</div>
          <div class="recon-empty__title">Không tìm thấy phiên nào</div>
          <div class="recon-empty__sub">Thử thay đổi bộ lọc hoặc từ khoá tìm kiếm.</div>
        </div>
      </td></tr>`;
    if (rowCountEl) rowCountEl.textContent = '0 phiên';
    return;
  }

  tbody.innerHTML = sessions.map((s, idx) => {
    const statusClass  = statusToClass(s.status);
    const statusLabel  = statusToLabel(s.status);
    const diffClass    = diffToClass(s.difference_kwh);
    const dcClass      = s.disconnect_count >= 3 ? 'disconnect-badge--hot' : '';

    return `
    <tr id="row-session-${s.session_id}" data-status="${s.status}">
      <td>${idx + 1}</td>
      <td><strong>${escHtml(s.charge_point_code)}</strong></td>
      <td>${s.connector_id}</td>
      <td>${s.meter_start_wh.toLocaleString('vi-VN')}</td>
      <td>${s.meter_stop_wh.toLocaleString('vi-VN')}</td>
      <td>
        <span class="disconnect-badge ${dcClass}">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2.5"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M18.36 6.64a9 9 0 1 1-12.73 0"/>
            <line x1="12" y1="2" x2="12" y2="12"/>
          </svg>
          ${s.disconnect_count}×
        </span>
      </td>
      <td>${s.system_kwh.toFixed(3)}</td>
      <td>${s.simulator_kwh.toFixed(3)}</td>
      <td class="${diffClass}">${s.difference_kwh.toFixed(3)}</td>
      <td>
        <span class="status-badge ${statusClass}">
          <span class="status-badge__dot" aria-hidden="true"></span>
          ${statusLabel}
        </span>
      </td>
      <td class="notes-cell">${escHtml(s.notes || '—')}</td>
    </tr>`;
  }).join('');

  if (rowCountEl) rowCountEl.textContent = `${sessions.length} phiên`;
}

/* ── Bind events ────────────────────────────────────────── */
function bindEvents() {
  /* Filter buttons */
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      activeFilter = btn.dataset.filter;
      applyFiltersAndRender();
    });
  });

  /* Search */
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      searchQuery = searchInput.value.trim();
      applyFiltersAndRender();
    });
  }

  /* Sort by column header click */
  document.querySelectorAll('.recon-table thead th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.sort;
      if (sortState.col === col) {
        sortState.dir = sortState.dir === 'asc' ? 'desc' : 'asc';
      } else {
        sortState = { col, dir: 'asc' };
      }
      updateSortIcons(th, sortState.dir);
      applyFiltersAndRender();
    });
  });

  /* Export CSV */
  if (exportCsvBtn) {
    exportCsvBtn.addEventListener('click', exportCsv);
  }

  /* Export Markdown */
  if (exportMdBtn) {
    exportMdBtn.addEventListener('click', exportMarkdown);
  }
}

/* ── Sort icon update ───────────────────────────────────── */
function updateSortIcons(activeTh, dir) {
  document.querySelectorAll('.recon-table thead th[data-sort]').forEach(th => {
    th.classList.remove('sorted-asc', 'sorted-desc');
    const icon = th.querySelector('.sort-icon');
    if (icon) icon.textContent = '↕';
  });
  activeTh.classList.add(dir === 'asc' ? 'sorted-asc' : 'sorted-desc');
  const icon = activeTh.querySelector('.sort-icon');
  if (icon) icon.textContent = dir === 'asc' ? '↑' : '↓';
}

/* ── Export CSV ─────────────────────────────────────────── */
function exportCsv() {
  const headers = [
    'STT', 'Mã trụ', 'Đầu nối', 'Đo đầu (Wh)', 'Đo cuối (Wh)',
    'Ngắt nối', 'System kWh', 'Simulator kWh', 'Chênh lệch kWh',
    'Trạng thái', 'Ghi chú'
  ];

  const rows = filteredSessions.map((s, i) => [
    i + 1,
    s.charge_point_code,
    s.connector_id,
    s.meter_start_wh,
    s.meter_stop_wh,
    s.disconnect_count,
    s.system_kwh.toFixed(3),
    s.simulator_kwh.toFixed(3),
    s.difference_kwh.toFixed(3),
    s.status,
    `"${(s.notes || '').replace(/"/g, '""')}"`
  ]);

  const csv = [headers, ...rows].map(r => r.join(',')).join('\r\n');
  downloadText(csv, `kwh_reconciliation_${dateSuffix()}.csv`, 'text/csv;charset=utf-8;');
}

/* ── Export Markdown ────────────────────────────────────── */
function exportMarkdown() {
  const sep = '|---|---|---|---:|---:|---:|---:|---:|---:|---|---|';
  const header = '| STT | Mã trụ | Đầu nối | Đo đầu (Wh) | Đo cuối (Wh) | Ngắt nối | System kWh | Sim kWh | Δ kWh | Trạng thái | Ghi chú |';

  const rows = filteredSessions.map((s, i) =>
    `| ${i+1} | ${s.charge_point_code} | ${s.connector_id} | ${s.meter_start_wh.toLocaleString()} | ${s.meter_stop_wh.toLocaleString()} | ${s.disconnect_count}× | ${s.system_kwh.toFixed(3)} | ${s.simulator_kwh.toFixed(3)} | ${s.difference_kwh.toFixed(3)} | ${s.status} | ${s.notes || '—'} |`
  );

  const md = [
    `# Bảng đối chiếu kWh — SCRUM-184`,
    `_Xuất lúc: ${new Date().toLocaleString('vi-VN')}_`,
    '',
    header,
    sep,
    ...rows
  ].join('\n');

  downloadText(md, `kwh_reconciliation_${dateSuffix()}.md`, 'text/markdown;charset=utf-8;');
}

/* ── Render skeletons while loading ─────────────────────── */
function renderSkeletons() {
  if (!tbody) return;
  tbody.innerHTML = Array.from({ length: 6 }).map(() => `
    <tr><td colspan="11"><div class="recon-skeleton"></div></td></tr>
  `).join('');
}

/* ── Show mock data notice ──────────────────────────────── */
function showMockNotice() {
  const notice = document.getElementById('recon-mock-notice');
  if (notice) notice.style.display = 'flex';
}

/* ── Show error ─────────────────────────────────────────── */
function showError(msg) {
  if (!tbody) return;
  tbody.innerHTML = `
    <tr><td colspan="11">
      <div class="recon-empty">
        <div class="recon-empty__icon">⚠️</div>
        <div class="recon-empty__title">${msg}</div>
      </div>
    </td></tr>`;
}

/* ── Helpers ────────────────────────────────────────────── */
function setText(el, val) {
  if (el) el.textContent = val;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function statusToClass(status) {
  const map = {
    'MATCH': 'status-badge--match',
    'MISMATCH': 'status-badge--mismatch',
    'MISSING_IN_SYSTEM': 'status-badge--missing-system',
    'MISSING_IN_SIMULATOR': 'status-badge--missing-simulator',
  };
  return map[status] || 'status-badge--mismatch';
}

function statusToLabel(status) {
  const map = {
    'MATCH': 'Khớp',
    'MISMATCH': 'Lệch',
    'MISSING_IN_SYSTEM': 'Thiếu (CSMS)',
    'MISSING_IN_SIMULATOR': 'Thiếu (Sim)',
  };
  return map[status] || status;
}

function diffToClass(diff) {
  if (diff === 0)    return 'diff-zero';
  if (diff <= 0.001) return 'diff-warn';
  return 'diff-error';
}

function formatDateTime(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('vi-VN', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  } catch { return iso; }
}

function dateSuffix() {
  return new Date().toISOString().slice(0, 10).replace(/-/g, '');
}

function downloadText(content, filename, mime) {
  const blob = new Blob(['\uFEFF' + content], { type: mime });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
