/** Read-only audit log table and filters. */
(function () {
  'use strict';

  const PAGE_SIZE = 50;
  let page = 1;
  let total = 0;

  function escHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[char]);
  }

  function displayAction(action) {
    const labels = {
      'charge_point.reset.accepted': 'Reset trụ thành công',
      'charge_point.reset.rejected': 'Trụ từ chối Reset',
      'charge_point.reset.failed': 'Gửi lệnh Reset thất bại',
      'remote_stop.accepted': 'Gửi lệnh dừng thành công',
      'remote_stop.rejected': 'Trụ từ chối lệnh dừng',
      'remote_stop.failed': 'Gửi lệnh dừng thất bại'
    };
    return labels[action] || action;
  }

  function getFilters() {
    const form = document.getElementById('audit-filters');
    const params = Object.fromEntries(new FormData(form).entries());
    Object.keys(params).forEach(key => { if (!params[key]) delete params[key]; });
    return params;
  }

  async function loadLogs() {
    const params = { ...getFilters(), page, page_size: PAGE_SIZE };
    const body = document.getElementById('audit-tbody');
    body.innerHTML = '<tr><td colspan="6" class="text-center">Đang tải nhật ký...</td></tr>';
    try {
      const data = await ApiClient.listAuditLogs(params);
      total = data.total || 0;
      if (!data.items?.length) {
        body.innerHTML = '<tr><td colspan="6"><div class="empty-state"><div class="empty-state__title">Chưa có nhật ký phù hợp</div><div class="empty-state__desc">Thao tác Reset và dừng phiên từ xa sẽ được ghi tại đây.</div></div></td></tr>';
      } else {
        body.innerHTML = data.items.map(item => {
          const actor = item.actor_name || item.actor_email || 'Thiết bị OCPP';
          const details = JSON.stringify(item.details || {});
          return `<tr>
            <td class="audit-nowrap">${escHtml(new Date(item.created_at).toLocaleString('vi-VN'))}</td>
            <td>${escHtml(actor)}${item.actor_email && item.actor_name ? `<small class="audit-subtext">${escHtml(item.actor_email)}</small>` : ''}</td>
            <td>${escHtml(displayAction(item.action))}</td>
            <td>${escHtml(item.object_type)}${item.object_id ? ` #${escHtml(item.object_id)}` : ''}</td>
            <td><code>${escHtml(item.charge_point_code || '—')}</code></td>
            <td class="audit-details">${escHtml(details)}</td>
          </tr>`;
        }).join('');
      }
      const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
      document.getElementById('audit-count').textContent = `${total} sự kiện`;
      document.getElementById('audit-page-label').textContent = `Trang ${page} / ${pages}`;
      document.getElementById('audit-prev').disabled = page <= 1;
      document.getElementById('audit-next').disabled = page >= pages;
    } catch (err) {
      body.innerHTML = `<tr><td colspan="6" class="text-center">${escHtml(err.message || 'Không tải được nhật ký')}</td></tr>`;
      document.getElementById('audit-count').textContent = 'Lỗi tải dữ liệu';
      showToast(err.message || 'Lỗi tải nhật ký', 'error');
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    loadLogs();
    document.getElementById('audit-filters').addEventListener('submit', event => {
      event.preventDefault();
      page = 1;
      loadLogs();
    });
    document.getElementById('audit-prev').addEventListener('click', () => {
      if (page > 1) { page -= 1; loadLogs(); }
    });
    document.getElementById('audit-next').addEventListener('click', () => {
      if (page * PAGE_SIZE < total) { page += 1; loadLogs(); }
    });
  });
})();
