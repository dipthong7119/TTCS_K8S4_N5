/**
 * pages/stations_list.js — JS đặc thù trang danh sách trạm
 * Max ~100 dòng — logic tái sử dụng (API, pagination) trong shared files
 */
(function () {
  'use strict';

  let _stations = [];
  let _page = 1;
  const PAGE_SIZE = 10;

  async function loadStations() {
    const search = document.getElementById('station-search').value.trim();
    const status = document.getElementById('status-filter').value;
    try {
      const data = await ApiClient.listStations({ search, status, page: _page, page_size: PAGE_SIZE });
      _stations = data.items || data;
      renderTable(_stations);
      renderStats(_stations);
      updateCount(data.total || _stations.length);
      renderPagination(data.total || _stations.length);
    } catch (err) {
      showToast(err.message || 'Không tải được danh sách trạm', 'error');
    }
  }

  function renderStats(stations) {
    const total   = stations.length;
    const online  = stations.filter(s => s.status === 'online').length;
    const offline = stations.filter(s => s.status === 'offline').length;
    const charging = stations.filter(s => s.active_sessions > 0).length;
    document.getElementById('stat-total').textContent    = total;
    document.getElementById('stat-online').textContent   = online;
    document.getElementById('stat-offline').textContent  = offline;
    document.getElementById('stat-charging').textContent = charging;
  }

  const STATUS_LABELS = { online: 'Trực tuyến', offline: 'Ngoại tuyến', fault: 'Lỗi' };
  const STATUS_CLASS  = { online: 'badge--online', offline: 'badge--offline', fault: 'badge--fault' };

  function renderTable(stations) {
    const tbody = document.getElementById('station-tbody');
    if (!stations.length) {
      tbody.innerHTML = '<tr><td colspan="6"><div class="empty-state"><div class="empty-state__icon">🏗️</div><div class="empty-state__title">Chưa có trạm nào</div><div class="empty-state__desc">Thêm trạm sạc đầu tiên của bạn</div></div></td></tr>';
      return;
    }
    tbody.innerHTML = stations.map(s => `
      <tr>
        <td><strong>${escHtml(s.name)}</strong></td>
        <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escHtml(s.address || '')}">${escHtml(s.address || '—')}</td>
        <td><span class="cp-count">${s.charge_point_count ?? '—'}<span class="cp-count__sub"> trụ</span></span></td>
        <td><span class="badge ${STATUS_CLASS[s.status] || 'badge--neutral'}">${STATUS_LABELS[s.status] || 'Không rõ'}</span></td>
        <td style="color:var(--color-text-secondary);font-size:var(--font-size-xs);">${fmtDate(s.created_at)}</td>
        <td class="text-right">
          <div class="station-row-actions">
            <a href="/stations/${s.id}/edit" class="btn btn--ghost btn--icon-sm" aria-label="Sửa trạm ${escHtml(s.name)}">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </a>
            <button class="btn btn--ghost btn--icon-sm" data-delete-id="${s.id}" data-delete-name="${escHtml(s.name)}" type="button" aria-label="Xoá trạm ${escHtml(s.name)}">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
            </button>
          </div>
        </td>
      </tr>`).join('');

    // Delete buttons
    tbody.querySelectorAll('[data-delete-id]').forEach(btn => {
      btn.addEventListener('click', () => openDeleteModal(btn.dataset.deleteId, btn.dataset.deleteName));
    });
  }

  function updateCount(total) {
    document.getElementById('result-count').textContent = `${total} trạm`;
  }

  function renderPagination(total) {
    const pages = Math.ceil(total / PAGE_SIZE);
    const pg = document.getElementById('pagination');
    pg.innerHTML = '';
    if (pages <= 1) return;
    const prev = document.createElement('button');
    prev.className = 'pagination__btn'; prev.textContent = '‹'; prev.disabled = _page === 1;
    prev.addEventListener('click', () => { _page--; loadStations(); });
    pg.appendChild(prev);
    for (let i = 1; i <= pages; i++) {
      const b = document.createElement('button');
      b.className = 'pagination__btn' + (i === _page ? ' is-active' : '');
      b.textContent = i;
      b.setAttribute('aria-label', `Trang ${i}`);
      if (i === _page) b.setAttribute('aria-current', 'page');
      b.addEventListener('click', () => { _page = i; loadStations(); });
      pg.appendChild(b);
    }
    const next = document.createElement('button');
    next.className = 'pagination__btn'; next.textContent = '›'; next.disabled = _page === pages;
    next.addEventListener('click', () => { _page++; loadStations(); });
    pg.appendChild(next);
  }

  // ── Delete modal ──
  let _deleteId = null;
  function openDeleteModal(id, name) {
    _deleteId = id;
    document.getElementById('delete-station-name').textContent = name;
    document.getElementById('delete-modal').classList.remove('is-hidden');
  }
  function closeDeleteModal() {
    document.getElementById('delete-modal').classList.add('is-hidden');
    _deleteId = null;
  }

  // ── Utilities ──
  function escHtml(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
  function fmtDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('vi-VN', { day:'2-digit', month:'2-digit', year:'numeric' });
  }

  // ── Init ──
  document.addEventListener('DOMContentLoaded', () => {
    loadStations();

    let _debounce;
    document.getElementById('station-search').addEventListener('input', () => {
      clearTimeout(_debounce);
      _debounce = setTimeout(() => { _page = 1; loadStations(); }, 350);
    });
    document.getElementById('status-filter').addEventListener('change', () => { _page = 1; loadStations(); });
    document.getElementById('btn-refresh').addEventListener('click', loadStations);

    document.getElementById('delete-modal-close').addEventListener('click', closeDeleteModal);
    document.getElementById('delete-cancel').addEventListener('click', closeDeleteModal);
    document.getElementById('delete-modal').addEventListener('click', e => { if (e.target === e.currentTarget) closeDeleteModal(); });

    document.getElementById('delete-confirm').addEventListener('click', async () => {
      if (!_deleteId) return;
      try {
        await ApiClient.deleteStation(_deleteId);
        showToast('Đã xoá trạm thành công', 'success');
        closeDeleteModal();
        loadStations();
      } catch (err) {
        showToast(err.message || 'Xoá thất bại', 'error');
      }
    });
  });
})();
