/**
 * pages/my_session.js — Trang lịch sử sạc tài xế (T-48)
 */
(function () {
  'use strict';

  const PAGE_SIZE = 15;
  let _page = 1;
  let _activeTimer = null;
  let _activeStart = null;

  function escHtml(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

  function fmtDatetime(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('vi-VN', { day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit' });
  }

  function fmtVND(amountInt) {
    if (amountInt == null) return '—';
    return new Intl.NumberFormat('vi-VN', { style:'currency', currency:'VND' }).format(amountInt);
  }

  function fmtDuration(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return [h, m, s].map(x => String(x).padStart(2, '0')).join(':');
  }

  async function loadSessions() {
    const period = document.getElementById('session-period').value;
    const status = document.getElementById('session-status-filter').value;
    try {
      const data = await ApiClient.listMySessions({ days: period, status, page: _page, page_size: PAGE_SIZE });
      const items = data.items || data;
      renderTable(items);
      renderStats(data);
      renderPagination(data.total || items.length);
      document.getElementById('session-count').textContent = `${data.total || items.length} phiên`;
      checkActiveSession(items);
    } catch (err) {
      showToast(err.message || 'Lỗi tải phiên sạc', 'error');
    }
  }

  function checkActiveSession(sessions) {
    const active = sessions.find(s => s.status === 'active' || s.status === 'charging');
    const banner = document.getElementById('active-session-banner');
    if (active) {
      banner.style.display = 'flex';
      document.getElementById('active-session-meta').textContent =
        `${active.station_name || ''} / ${active.charge_point_code || ''}`;
      document.getElementById('active-kwh').textContent = `${(active.kwh || 0).toFixed(3)} kWh`;
      _activeStart = new Date(active.started_at);
      startDurationTimer();
    } else {
      banner.style.display = 'none';
      clearInterval(_activeTimer);
    }
  }

  function startDurationTimer() {
    clearInterval(_activeTimer);
    const el = document.getElementById('active-duration');
    _activeTimer = setInterval(() => {
      if (!_activeStart) return;
      const seconds = Math.floor((Date.now() - _activeStart.getTime()) / 1000);
      el.textContent = fmtDuration(seconds);
    }, 1000);
  }

  const STATUS_LABEL = { completed:'Hoàn thành', active:'Đang sạc', charging:'Đang sạc', anomaly:'Bất thường' };
  const STATUS_CLASS = { completed:'badge--available', active:'badge--charging', charging:'badge--charging', anomaly:'badge--anomaly' };

  function renderTable(sessions) {
    const tbody = document.getElementById('sessions-tbody');
    if (!sessions.length) {
      tbody.innerHTML = '<tr><td colspan="8"><div class="empty-state"><div class="empty-state__icon">⚡</div><div class="empty-state__title">Chưa có phiên nào</div><div class="empty-state__desc">Các phiên sạc của bạn sẽ xuất hiện ở đây</div></div></td></tr>';
      return;
    }
    tbody.innerHTML = sessions.map(s => {
      const durSec = s.duration_seconds;
      const dur = durSec != null ? fmtDuration(durSec) : '—';
      return `<tr style="cursor:pointer;" data-session-id="${s.id}">
        <td><code style="font-family:monospace;font-size:var(--font-size-xs);background:var(--color-surface-alt);padding:2px 6px;border-radius:4px;">#${s.id}</code></td>
        <td>${escHtml(s.station_name||'—')} / <span style="font-family:monospace;">${escHtml(s.charge_point_code||'—')}</span></td>
        <td style="white-space:nowrap;font-size:var(--font-size-xs);">${fmtDatetime(s.started_at)}</td>
        <td style="white-space:nowrap;font-size:var(--font-size-xs);">${s.ended_at ? fmtDatetime(s.ended_at) : '<span style="color:var(--color-charging)">Đang sạc</span>'}</td>
        <td style="font-size:var(--font-size-xs);">${dur}</td>
        <td style="font-weight:600;">${s.kwh != null ? s.kwh.toFixed(3) : '—'}</td>
        <td>${fmtVND(s.cost_vnd)}</td>
        <td><span class="badge ${STATUS_CLASS[s.status]||'badge--neutral'}">${STATUS_LABEL[s.status]||'Không rõ'}</span></td>
      </tr>`;
    }).join('');

    tbody.querySelectorAll('[data-session-id]').forEach(row => {
      row.addEventListener('click', () => openDetail(sessions.find(s => s.id == row.dataset.sessionId)));
    });
  }

  function renderStats(data) {
    document.getElementById('s-total').textContent = data.total || '0';
    document.getElementById('s-kwh').textContent = data.total_kwh != null ? data.total_kwh.toFixed(2) : '—';
    document.getElementById('s-cost').textContent = data.total_cost_vnd != null
      ? new Intl.NumberFormat('vi-VN').format(data.total_cost_vnd) + ' ₫' : '—';
  }

  function renderPagination(total) {
    const pages = Math.ceil(total / PAGE_SIZE);
    const pg = document.getElementById('sessions-pagination');
    pg.innerHTML = '';
    if (pages <= 1) return;
    for (let i = 1; i <= pages; i++) {
      const b = document.createElement('button');
      b.className = 'pagination__btn' + (i === _page ? ' is-active' : '');
      b.textContent = i; b.setAttribute('aria-label', `Trang ${i}`);
      if (i === _page) b.setAttribute('aria-current', 'page');
      b.addEventListener('click', () => { _page = i; loadSessions(); });
      pg.appendChild(b);
    }
  }

  function openDetail(session) {
    if (!session) return;
    document.getElementById('session-detail-title').textContent = `Phiên #${session.id}`;
    document.getElementById('session-detail-body').innerHTML = `
      <dl style="display:grid;grid-template-columns:1fr 1fr;gap:var(--space-3) var(--space-6);">
        <div><dt style="font-size:var(--font-size-xs);color:var(--color-text-secondary);font-weight:600;margin-bottom:2px;">Trạm</dt><dd>${escHtml(session.station_name||'—')}</dd></div>
        <div><dt style="font-size:var(--font-size-xs);color:var(--color-text-secondary);font-weight:600;margin-bottom:2px;">Mã trụ</dt><dd><code style="font-family:monospace;">${escHtml(session.charge_point_code||'—')}</code></dd></div>
        <div><dt style="font-size:var(--font-size-xs);color:var(--color-text-secondary);font-weight:600;margin-bottom:2px;">Bắt đầu</dt><dd>${fmtDatetime(session.started_at)}</dd></div>
        <div><dt style="font-size:var(--font-size-xs);color:var(--color-text-secondary);font-weight:600;margin-bottom:2px;">Kết thúc</dt><dd>${session.ended_at ? fmtDatetime(session.ended_at) : 'Đang sạc'}</dd></div>
        <div><dt style="font-size:var(--font-size-xs);color:var(--color-text-secondary);font-weight:600;margin-bottom:2px;">Điện năng</dt><dd style="font-weight:700;">${session.kwh != null ? session.kwh.toFixed(3) + ' kWh' : '—'}</dd></div>
        <div><dt style="font-size:var(--font-size-xs);color:var(--color-text-secondary);font-weight:600;margin-bottom:2px;">Chi phí</dt><dd style="font-weight:700;">${session.cost_vnd != null ? new Intl.NumberFormat('vi-VN',{style:'currency',currency:'VND'}).format(session.cost_vnd) : '—'}</dd></div>
        <div><dt style="font-size:var(--font-size-xs);color:var(--color-text-secondary);font-weight:600;margin-bottom:2px;">Trạng thái</dt><dd><span class="badge ${STATUS_CLASS[session.status]||'badge--neutral'}">${STATUS_LABEL[session.status]||'Không rõ'}</span></dd></div>
        <div><dt style="font-size:var(--font-size-xs);color:var(--color-text-secondary);font-weight:600;margin-bottom:2px;">Lý do kết thúc</dt><dd>${escHtml(session.stop_reason||'—')}</dd></div>
      </dl>`;
    document.getElementById('session-detail-modal').classList.remove('is-hidden');
  }

  document.addEventListener('DOMContentLoaded', () => {
    loadSessions();
    document.getElementById('session-period').addEventListener('change', () => { _page = 1; loadSessions(); });
    document.getElementById('session-status-filter').addEventListener('change', () => { _page = 1; loadSessions(); });
    document.getElementById('session-modal-close')?.addEventListener('click', () => document.getElementById('session-detail-modal').classList.add('is-hidden'));
    document.getElementById('session-detail-modal')?.addEventListener('click', e => { if (e.target === e.currentTarget) e.currentTarget.classList.add('is-hidden'); });

    // SSE for active session update
    SseClient.connect('/api/monitoring/sse');
    SseClient.on('session_update', () => loadSessions());
  });
})();
