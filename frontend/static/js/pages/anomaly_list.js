/**
 * pages/anomaly_list.js — Trang danh sách phiên bất thường (T-54)
 */
(function () {
  'use strict';

  const PAGE_SIZE = 15;
  let _page = 1;
  let _pendingStopId = null;
  let _pendingStopCode = null;

  function escHtml(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
  function fmtDatetime(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('vi-VN', { day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit' });
  }

  const REASON_LABEL = {
    offline: 'Trụ ngoại tuyến', negative_kwh: 'Số đo âm',
    no_stop: 'Không có StopTransaction', orphan: 'Orphan message',
  };

  async function loadAnomalies() {
    const reason = document.getElementById('anomaly-reason').value;
    const period = document.getElementById('anomaly-period').value;
    try {
      const data = await ApiClient.listAnomalies({ reason, days: period, page: _page, page_size: PAGE_SIZE });
      const items = data.items || data;
      renderTable(items);
      renderStats(data);
      renderPagination(data.total || items.length);
      document.getElementById('anomaly-result-count').textContent = `${data.total || items.length} phiên`;
    } catch (err) {
      showToast(err.message || 'Lỗi tải dữ liệu', 'error');
    }
  }

  function renderStats(data) {
    document.getElementById('anom-count').textContent    = data.total || '—';
    document.getElementById('anom-offline').textContent  = data.offline_count || '—';
    document.getElementById('anom-negative').textContent = data.negative_kwh_count || '—';
  }

  function renderTable(items) {
    const tbody = document.getElementById('anomaly-tbody');
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="7"><div class="empty-state"><div class="empty-state__icon">✅</div><div class="empty-state__title">Không có phiên bất thường</div><div class="empty-state__desc">Tất cả phiên sạc đang hoạt động bình thường</div></div></td></tr>';
      return;
    }
    tbody.innerHTML = items.map(item => `
      <tr>
        <td><code style="font-family:monospace;font-size:var(--font-size-xs);background:var(--color-surface-alt);padding:2px 6px;border-radius:4px;">#${item.id}</code></td>
        <td>${escHtml(item.station_name||'—')} / <span style="font-family:monospace;">${escHtml(item.charge_point_code||'—')}</span></td>
        <td style="font-size:var(--font-size-xs);">${escHtml(item.driver_id||'—')}</td>
        <td style="white-space:nowrap;font-size:var(--font-size-xs);">${fmtDatetime(item.started_at)}</td>
        <td><span class="badge badge--anomaly">${escHtml(REASON_LABEL[item.anomaly_reason]||item.anomaly_reason||'Bất thường')}</span></td>
        <td style="font-weight:600;">${item.kwh != null ? item.kwh.toFixed(3) : '—'}</td>
        <td class="text-right">
          <div style="display:flex;gap:var(--space-2);justify-content:flex-end;">
            ${item.status === 'active' ? `<button class="btn btn--danger btn--sm" data-stop-id="${item.id}" data-stop-code="${escHtml(item.charge_point_code||'')}" type="button">Dừng từ xa</button>` : ''}
          </div>
        </td>
      </tr>`).join('');

    tbody.querySelectorAll('[data-stop-id]').forEach(btn => {
      btn.addEventListener('click', () => openRemoteStop(btn.dataset.stopId, btn.dataset.stopCode));
    });
  }

  function renderPagination(total) {
    const pages = Math.ceil(total / PAGE_SIZE);
    const pg = document.getElementById('anomaly-pagination');
    pg.innerHTML = '';
    if (pages <= 1) return;
    for (let i = 1; i <= pages; i++) {
      const b = document.createElement('button');
      b.className = 'pagination__btn' + (i === _page ? ' is-active' : '');
      b.textContent = i; b.setAttribute('aria-label', `Trang ${i}`);
      if (i === _page) b.setAttribute('aria-current', 'page');
      b.addEventListener('click', () => { _page = i; loadAnomalies(); });
      pg.appendChild(b);
    }
  }

  // ── Remote stop modal ──
  function openRemoteStop(id, code) {
    _pendingStopId   = id;
    _pendingStopCode = code;
    document.getElementById('stop-session-id').textContent = `#${id}`;
    document.getElementById('stop-cp-code').textContent    = code;
    document.getElementById('remote-stop-modal').classList.remove('is-hidden');
  }
  function closeRemoteStop() {
    document.getElementById('remote-stop-modal').classList.add('is-hidden');
    _pendingStopId = _pendingStopCode = null;
  }

  document.addEventListener('DOMContentLoaded', () => {
    loadAnomalies();

    document.getElementById('anomaly-reason').addEventListener('change',  () => { _page = 1; loadAnomalies(); });
    document.getElementById('anomaly-period').addEventListener('change',  () => { _page = 1; loadAnomalies(); });
    document.getElementById('btn-refresh-anomalies')?.addEventListener('click', loadAnomalies);

    document.getElementById('remote-stop-close')?.addEventListener('click', closeRemoteStop);
    document.getElementById('remote-stop-cancel')?.addEventListener('click', closeRemoteStop);
    document.getElementById('remote-stop-modal')?.addEventListener('click', e => { if (e.target === e.currentTarget) closeRemoteStop(); });

    document.getElementById('remote-stop-confirm')?.addEventListener('click', async () => {
      if (!_pendingStopId) return;
      try {
        await ApiClient.remoteStop(_pendingStopId);
        showToast('Đã gửi lệnh dừng. Đang chờ phản hồi từ trụ...', 'success');
        closeRemoteStop();
        setTimeout(loadAnomalies, 2000);
      } catch (err) {
        showToast(err.message || 'Gửi lệnh thất bại', 'error');
      }
    });
  });
})();
