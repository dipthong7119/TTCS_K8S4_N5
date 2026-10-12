/**
 * pages/audit.js — SCRUM-89: Màn hình xem nhật ký lệnh điều khiển từ xa
 * Lịch sử chỉ đọc (append-only) của mọi lệnh gửi tới trụ sạc kèm người thực hiện.
 */
(function () {
  'use strict';

  const PAGE_SIZE = 50;
  let page = 1;
  let total = 0;
  let currentItems = [];

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[char]);
  }

  function getInitials(name) {
    if (!name) return '?';
    const parts = name.trim().split(/\s+/);
    if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  /**
   * Phân tích và chuẩn hóa nhãn thao tác điều khiển từ xa
   */
  function parseAction(action, details = {}) {
    const command = details.command || '';
    if (action.includes('reset') || command === 'Reset') {
      return {
        label: 'Khởi động lại trụ (Reset)',
        icon: '🔄',
        cmdClass: 'audit-cmd--reset',
      };
    }
    if (action.includes('remote_start') || command === 'RemoteStartTransaction') {
      return {
        label: 'Bắt đầu sạc từ xa (RemoteStart)',
        icon: '⚡',
        cmdClass: 'audit-cmd--remote-start',
      };
    }
    if (action.includes('remote_stop') || command === 'RemoteStopTransaction') {
      return {
        label: 'Dừng sạc từ xa (RemoteStop)',
        icon: '⏹',
        cmdClass: 'audit-cmd--remote-stop',
      };
    }
    if (action.includes('configuration') || command === 'ChangeConfiguration') {
      return {
        label: 'Đổi cấu hình trụ sạc',
        icon: '⚙️',
        cmdClass: 'audit-cmd--config',
      };
    }
    if (action.includes('wallet')) {
      return {
        label: action === 'wallet.manual_topup' ? 'Nạp ví thủ công (Admin)' : 'Giao dịch ví Sandbox',
        icon: '💳',
        cmdClass: 'audit-cmd--wallet',
      };
    }
    return {
      label: action,
      icon: '📋',
      cmdClass: 'audit-cmd--default',
    };
  }

  /**
   * Xác định kết quả của lệnh điều khiển
   */
  function parseOutcome(action, details = {}) {
    const raw = (details.outcome || '').toLowerCase();
    if (raw === 'accepted' || action.endsWith('.accepted') || action.endsWith('.success')) {
      return { text: 'Chấp nhận', badgeClass: 'audit-outcome--accepted' };
    }
    if (raw === 'rejected' || action.endsWith('.rejected')) {
      return { text: 'Từ chối', badgeClass: 'audit-outcome--rejected' };
    }
    if (raw === 'timeout') {
      return { text: 'Hết giờ (Timeout)', badgeClass: 'audit-outcome--failed' };
    }
    if (raw === 'disconnected') {
      return { text: 'Mất kết nối', badgeClass: 'audit-outcome--failed' };
    }
    if (action.endsWith('.failed') || raw === 'call_error' || raw === 'failed') {
      return { text: 'Thất bại', badgeClass: 'audit-outcome--failed' };
    }
    return { text: details.outcome || 'Đã ghi nhận', badgeClass: 'audit-outcome--accepted' };
  }

  function formatObjectType(type, id) {
    const map = {
      charge_point: 'Trụ sạc',
      charging_session: 'Phiên sạc',
      wallet_ledger: 'Sổ cái ví',
      payment_transaction: 'Đơn nạp ví',
    };
    const name = map[type] || type || 'Đối tượng';
    return id ? `${name} #${id}` : name;
  }

  function getFilters() {
    const form = document.getElementById('audit-filters');
    const params = Object.fromEntries(new FormData(form).entries());
    Object.keys(params).forEach(key => {
      const val = (params[key] || '').trim();
      if (!val) {
        delete params[key];
      } else {
        params[key] = val;
      }
    });
    return params;
  }

  async function loadLogs() {
    const params = { ...getFilters(), page, page_size: PAGE_SIZE };
    const tbody = document.getElementById('audit-tbody');
    tbody.innerHTML = '<tr><td colspan="7" class="text-center">Đang tải dữ liệu nhật ký...</td></tr>';

    try {
      const data = await ApiClient.listAuditLogs(params);
      currentItems = data.items || [];
      total = data.total || 0;

      if (!currentItems.length) {
        tbody.innerHTML = `<tr><td colspan="7">
          <div class="empty-state" style="padding: 40px 16px; text-align: center;">
            <div class="empty-state__title" style="font-size: 1.1rem; font-weight: 600; margin-bottom: 8px;">Không tìm thấy sự kiện phù hợp</div>
            <div class="empty-state__desc" style="color: var(--color-text-secondary); font-size: 0.9rem;">Thử điều chỉnh lại bộ lọc mã trụ, người thực hiện hoặc khoảng thời gian.</div>
          </div>
        </td></tr>`;
      } else {
        tbody.innerHTML = currentItems.map((item, index) => {
          const actorName = item.actor_name || item.actor_email || 'Hệ thống / OCPP';
          const actorEmail = item.actor_email || '';
          const initials = getInitials(actorName);
          const timeStr = new Date(item.created_at).toLocaleString('vi-VN', {
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', second: '2-digit',
          });
          const actionMeta = parseAction(item.action, item.details);
          const outcomeMeta = parseOutcome(item.action, item.details);
          const objectLabel = formatObjectType(item.object_type, item.object_id);

          return `<tr>
            <td class="audit-cell-time">${escapeHtml(timeStr)}</td>
            <td>
              <div class="audit-actor-box">
                <span class="audit-actor-avatar" title="${escapeHtml(actorName)}">${escapeHtml(initials)}</span>
                <div class="audit-actor-info">
                  <span class="audit-actor-name">${escapeHtml(actorName)}</span>
                  ${actorEmail && actorName !== actorEmail ? `<span class="audit-actor-email">${escapeHtml(actorEmail)}</span>` : ''}
                </div>
              </div>
            </td>
            <td>
              <span class="audit-cmd-badge ${actionMeta.cmdClass}">
                <span aria-hidden="true">${actionMeta.icon}</span>
                <span>${escapeHtml(actionMeta.label)}</span>
              </span>
            </td>
            <td>${item.charge_point_code ? `<span class="audit-cp-code">${escapeHtml(item.charge_point_code)}</span>` : '<span style="color: var(--color-text-muted);">—</span>'}</td>
            <td><small style="color: var(--color-text-secondary);">${escapeHtml(objectLabel)}</small></td>
            <td>
              <span class="audit-outcome-badge ${outcomeMeta.badgeClass}">
                ${escapeHtml(outcomeMeta.text)}
              </span>
            </td>
            <td class="text-right">
              <button class="btn btn--ghost btn--sm" type="button" data-audit-index="${index}" title="Xem chi tiết tham số và phản hồi">Chi tiết</button>
            </td>
          </tr>`;
        }).join('');

        tbody.querySelectorAll('[data-audit-index]').forEach(btn => {
          btn.addEventListener('click', () => {
            const idx = Number(btn.dataset.auditIndex);
            openDetailDialog(currentItems[idx]);
          });
        });
      }

      const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
      document.getElementById('audit-count').textContent = `${total} sự kiện`;
      document.getElementById('audit-page-label').textContent = `Trang ${page} / ${pages}`;
      document.getElementById('audit-prev').disabled = page <= 1;
      document.getElementById('audit-next').disabled = page >= pages;
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center" style="color: var(--color-danger); padding: 32px 16px;">
        ${escapeHtml(err.message || 'Không tải được dữ liệu nhật ký')}
      </td></tr>`;
      document.getElementById('audit-count').textContent = 'Lỗi tải dữ liệu';
      if (typeof showToast === 'function') {
        showToast(err.message || 'Lỗi tải nhật ký kiểm toán', 'error');
      }
    }
  }

  function openDetailDialog(item) {
    if (!item) return;
    const dialog = document.getElementById('audit-detail-dialog');
    if (!dialog) return;

    const timeStr = new Date(item.created_at).toLocaleString('vi-VN', {
      dateStyle: 'full', timeStyle: 'medium'
    });
    const actorName = item.actor_name || item.actor_email || 'Hệ thống';
    const actionMeta = parseAction(item.action, item.details);
    const outcomeMeta = parseOutcome(item.action, item.details);

    document.getElementById('audit-detail-title').textContent = `Lệnh kiểm toán #${item.id}`;
    document.getElementById('detail-time').textContent = timeStr;
    document.getElementById('detail-actor').textContent = `${actorName}${item.actor_email ? ` (${item.actor_email})` : ''}`;
    document.getElementById('detail-command').textContent = actionMeta.label;
    document.getElementById('detail-cp').textContent = item.charge_point_code || 'Không gắn mã trụ';
    document.getElementById('detail-object').textContent = formatObjectType(item.object_type, item.object_id);
    document.getElementById('detail-outcome').innerHTML = `<span class="audit-outcome-badge ${outcomeMeta.badgeClass}">${escapeHtml(outcomeMeta.text)}</span>`;

    const jsonText = JSON.stringify(item.details || {}, null, 2);
    document.getElementById('detail-json').textContent = jsonText;

    dialog.showModal();
  }

  document.addEventListener('DOMContentLoaded', () => {
    loadLogs();

    // Form submit filter
    const filterForm = document.getElementById('audit-filters');
    filterForm?.addEventListener('submit', event => {
      event.preventDefault();
      page = 1;
      loadLogs();
    });

    // Reset filter
    document.getElementById('btn-reset-filter')?.addEventListener('click', () => {
      filterForm?.reset();
      page = 1;
      loadLogs();
    });

    // Pagination
    document.getElementById('audit-prev')?.addEventListener('click', () => {
      if (page > 1) {
        page -= 1;
        loadLogs();
      }
    });

    document.getElementById('audit-next')?.addEventListener('click', () => {
      if (page * PAGE_SIZE < total) {
        page += 1;
        loadLogs();
      }
    });

    // Detail dialog controls
    const dialog = document.getElementById('audit-detail-dialog');
    const closeDialog = () => dialog?.close();
    document.getElementById('audit-detail-close')?.addEventListener('click', closeDialog);
    document.getElementById('btn-close-dialog')?.addEventListener('click', closeDialog);
    dialog?.addEventListener('click', event => {
      if (event.target === dialog) closeDialog();
    });

    // Copy JSON payload
    document.getElementById('btn-copy-json')?.addEventListener('click', async () => {
      const code = document.getElementById('detail-json')?.textContent || '';
      try {
        await navigator.clipboard.writeText(code);
        if (typeof showToast === 'function') {
          showToast('Đã sao chép nội dung JSON vào bộ nhớ tạm', 'success');
        }
      } catch (_) {
        if (typeof showToast === 'function') {
          showToast('Không thể sao chép JSON', 'error');
        }
      }
    });
  });
})();
