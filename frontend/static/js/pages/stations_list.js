/**
 * pages/stations_list.js — JS đặc thù trang danh sách trạm (T-09, SCRUM-105)
 * Giới hạn: ~100 dòng — logic tái sử dụng (API, pagination) ở shared files.
 * Mọi gọi API đi qua ApiClient (api_client.js) — không rải fetch trực tiếp.
 */
(function () {
  'use strict';

  let _stations = [];
  let _page = 1;
  const PAGE_SIZE = 10;

  // ── Labels & classes trạng thái (khớp schema stations: active/inactive/maintenance) ──
  const STATUS_LABELS = {
    active:      'Hoạt động',
    inactive:    'Tạm dừng',
    maintenance: 'Bảo trì',
  };
  const STATUS_CLASS = {
    active:      'badge--online',
    inactive:    'badge--offline',
    maintenance: 'badge--warning',
  };

  // ── Tải danh sách trạm từ API ──
  async function loadStations() {
    const search = document.getElementById('station-search').value.trim();
    const status = document.getElementById('status-filter').value;
    const tbody  = document.getElementById('station-tbody');

    // Hiện loading
    tbody.innerHTML = `
      <tr><td colspan="6" style="text-align:center;padding:40px;color:var(--color-text-muted);">
        <div style="display:flex;align-items:center;justify-content:center;gap:10px;">
          <div class="spinner" aria-hidden="true"></div><span>Đang tải...</span>
        </div>
      </td></tr>`;

    try {
      const params = { page: _page, page_size: PAGE_SIZE };
      if (search) params.search = search;
      if (status) params.status = status;

      const data  = await ApiClient.listStations(params);
      _stations   = data.items || data;
      const total = data.total ?? _stations.length;

      renderTable(_stations);
      renderStats(_stations);
      updateCount(total);
      renderPagination(total);
    } catch (err) {
      tbody.innerHTML = `
        <tr><td colspan="6" style="text-align:center;padding:40px;">
          <div class="empty-state">
            <div class="empty-state__icon">⚠️</div>
            <div class="empty-state__title">Không tải được dữ liệu</div>
            <div class="empty-state__desc">${escHtml(err.message || 'Lỗi kết nối máy chủ')}</div>
          </div>
        </td></tr>`;
      showToast(err.message || 'Không tải được danh sách trạm', 'error');
    }
  }

  // ── Cập nhật thẻ thống kê ──
  function renderStats(stations) {
    const counts = { active: 0, inactive: 0, maintenance: 0 };
    stations.forEach(s => { if (counts[s.status] !== undefined) counts[s.status]++; });
    document.getElementById('stat-total').textContent       = stations.length;
    document.getElementById('stat-active').textContent      = counts.active;
    document.getElementById('stat-maintenance').textContent = counts.maintenance;
    document.getElementById('stat-inactive').textContent    = counts.inactive;
  }

  // ── Render bảng danh sách ──
  function renderTable(stations) {
    const tbody = document.getElementById('station-tbody');
    if (!stations.length) {
      tbody.innerHTML = `
        <tr><td colspan="6">
          <div class="empty-state">
            <div class="empty-state__icon">🏗️</div>
            <div class="empty-state__title">Chưa có trạm nào</div>
            <div class="empty-state__desc">Bấm <strong>Thêm trạm mới</strong> để bắt đầu</div>
          </div>
        </td></tr>`;
      return;
    }

    tbody.innerHTML = stations.map(s => {
      const statusLabel = STATUS_LABELS[s.status] || 'Không rõ';
      const statusClass = STATUS_CLASS[s.status]  || 'badge--neutral';
      return `
        <tr>
          <td><strong>${escHtml(s.name)}</strong></td>
          <td class="td-address" title="${escHtml(s.address || '')}">${escHtml(s.address || '—')}</td>
          <td>
            <span class="cp-count">
              ${s.charge_point_count ?? '—'}
              <span class="cp-count__sub"> trụ</span>
            </span>
          </td>
          <td>
            <span class="badge ${statusClass}" aria-label="Trạng thái: ${statusLabel}">
              ${statusLabel}
            </span>
          </td>
          <td class="td-date">${fmtDate(s.created_at)}</td>
          <td class="text-right">
            <div class="station-row-actions">
              <a href="/stations/${s.id}/edit"
                 class="btn btn--ghost btn--icon-sm"
                 aria-label="Sửa trạm ${escHtml(s.name)}">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                     stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
              </a>
              <button class="btn btn--ghost btn--icon-sm"
                      data-delete-id="${s.id}"
                      data-delete-name="${escHtml(s.name)}"
                      type="button"
                      aria-label="Xoá trạm ${escHtml(s.name)}">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                     stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <polyline points="3 6 5 6 21 6"/>
                  <path d="M19 6l-1 14H6L5 6"/>
                  <path d="M10 11v6"/><path d="M14 11v6"/>
                  <path d="M9 6V4h6v2"/>
                </svg>
              </button>
            </div>
          </td>
        </tr>`;
    }).join('');

    // Gắn event xoá
    tbody.querySelectorAll('[data-delete-id]').forEach(btn => {
      btn.addEventListener('click', () =>
        openDeleteModal(btn.dataset.deleteId, btn.dataset.deleteName));
    });
  }

  // ── Hiện số lượng kết quả ──
  function updateCount(total) {
    document.getElementById('result-count').textContent = `${total} trạm`;
  }

  // ── Phân trang ──
  function renderPagination(total) {
    const pages = Math.ceil(total / PAGE_SIZE);
    const pg    = document.getElementById('pagination');
    pg.innerHTML = '';
    if (pages <= 1) return;

    const prev = makePageBtn('‹', _page === 1, () => { _page--; loadStations(); }, 'Trang trước');
    pg.appendChild(prev);

    const maxShow = 5;
    let start = Math.max(1, _page - Math.floor(maxShow / 2));
    let end   = Math.min(pages, start + maxShow - 1);
    if (end - start + 1 < maxShow) start = Math.max(1, end - maxShow + 1);

    if (start > 1) pg.appendChild(makeEllipsis());
    for (let i = start; i <= end; i++) {
      pg.appendChild(makePageBtn(String(i), false, () => { _page = i; loadStations(); }, `Trang ${i}`, i === _page));
    }
    if (end < pages) pg.appendChild(makeEllipsis());

    const next = makePageBtn('›', _page === pages, () => { _page++; loadStations(); }, 'Trang sau');
    pg.appendChild(next);
  }

  function makePageBtn(text, disabled, onClick, label, active = false) {
    const b = document.createElement('button');
    b.className = 'pagination__btn' + (active ? ' is-active' : '');
    b.textContent = text;
    b.disabled = disabled;
    b.setAttribute('aria-label', label);
    if (active) b.setAttribute('aria-current', 'page');
    b.addEventListener('click', onClick);
    return b;
  }

  function makeEllipsis() {
    const span = document.createElement('span');
    span.className = 'pagination__ellipsis';
    span.textContent = '…';
    span.setAttribute('aria-hidden', 'true');
    return span;
  }

  // ── Modal xoá ──
  let _deleteId = null;

  function openDeleteModal(id, name) {
    _deleteId = id;
    document.getElementById('delete-station-name').textContent = name;
    document.getElementById('delete-modal').classList.remove('is-hidden');
    document.getElementById('delete-confirm').focus();
  }

  function closeDeleteModal() {
    document.getElementById('delete-modal').classList.add('is-hidden');
    _deleteId = null;
  }

  // ── Tiện ích ──
  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleDateString('vi-VN',
        { day: '2-digit', month: '2-digit', year: 'numeric' });
    } catch { return '—'; }
  }

  // ── Khởi động ──
  document.addEventListener('DOMContentLoaded', () => {
    loadStations();

    // Tìm kiếm có debounce
    let _debounce;
    document.getElementById('station-search').addEventListener('input', () => {
      clearTimeout(_debounce);
      _debounce = setTimeout(() => { _page = 1; loadStations(); }, 350);
    });

    // Lọc trạng thái
    document.getElementById('status-filter').addEventListener('change', () => {
      _page = 1;
      loadStations();
    });

    // Nút làm mới
    document.getElementById('btn-refresh').addEventListener('click', () => {
      _page = 1;
      loadStations();
    });

    // Modal xoá — mở/đóng
    document.getElementById('delete-modal-close').addEventListener('click', closeDeleteModal);
    document.getElementById('delete-cancel').addEventListener('click', closeDeleteModal);
    document.getElementById('delete-modal').addEventListener('click', e => {
      if (e.target === e.currentTarget) closeDeleteModal();
    });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') closeDeleteModal();
    });

    // Modal xoá — xác nhận
    document.getElementById('delete-confirm').addEventListener('click', async () => {
      if (!_deleteId) return;
      const btn = document.getElementById('delete-confirm');
      btn.disabled = true;
      btn.textContent = 'Đang xoá...';
      try {
        await ApiClient.deleteStation(_deleteId);
        showToast('Đã xoá trạm thành công', 'success');
        closeDeleteModal();
        _page = 1;
        loadStations();
      } catch (err) {
        showToast(err.message || 'Xoá thất bại', 'error');
      } finally {
        btn.disabled = false;
        btn.textContent = 'Xoá trạm';
      }
    });
  });
})();
