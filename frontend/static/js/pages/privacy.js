/**
 * pages/privacy.js — SCRUM-92: Quyền riêng tư & Xóa dữ liệu (Nghị định 13/2023/NĐ-CP)
 *
 * AC (Acceptance Criteria):
 *  AC1 — Tài xế gửi yêu cầu xóa thông tin cá nhân & lịch sử di chuyển (vị trí GPS các trạm đã sạc).
 *  AC2 — Kiểm tra số dư ví (Balance Pre-check): nếu ví còn số dư dương (> 0 ₫) thì cảnh báo phải rút/hoàn tiền trước; chỉ cho phép duyệt khi số dư = 0 ₫.
 *  AC3 — Sau khi duyệt, ẩn danh hóa thông tin cá nhân và định danh phiên sạc; giữ nguyên số liệu doanh thu và sổ cái theo luật kế toán.
 *  AC4 — Tiến độ yêu cầu (Timeline): Gửi yêu cầu -> Thẩm định số dư -> Phê duyệt -> Ẩn danh hóa.
 *  AC5 — Cho phép tài xế hủy yêu cầu khi đang ở trạng thái Chờ duyệt (Pending).
 *  AC6 — Giao diện quản trị viên (Admin/Operator/DPO) thẩm định, duyệt ẩn danh hóa hoặc từ chối kèm lý do.
 */

(function () {
  'use strict';

  /* ── State ────────────────────────────────────────────────────────────── */
  let _currentDriverBalance = 0;
  let _activeRequest = null;
  let _adminRequests = [];
  let _adminLoadError = null;
  let _selectedReqId = null;

  /* ── Helpers ──────────────────────────────────────────────────────────── */
  function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  }

  function fmtVnd(n) {
    if (n == null) return '0 ₫';
    return Number(n).toLocaleString('vi-VN') + ' ₫';
  }

  function fmtDatetime(iso) {
    if (!iso) return '—';
    const d = new Date((/Z|[+-]\d{2}:\d{2}$/i).test(iso) ? iso : iso + 'Z');
    return isNaN(d) ? '—' : d.toLocaleString('vi-VN', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  }

  function showToast(msg, type = 'info') {
    if (window.showToast) {
      window.showToast(msg, type);
      return;
    }
    const t = document.createElement('div');
    t.className = `toast toast--${type}`;
    t.textContent = msg;
    t.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:9999;padding:12px 20px;border-radius:8px;background:#1e293b;color:#fff;box-shadow:0 4px 12px rgba(0,0,0,0.15);font-size:14px;';
    if (type === 'success') t.style.background = '#15803d';
    if (type === 'error') t.style.background = '#b91c1c';
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3500);
  }

  /* ── Driver View Functions ────────────────────────────────────────────── */
  async function loadDriverData() {
    let profile;
    try {
      profile = await ApiClient.getPrivacyProfile();
    } catch (error) {
      showToast(error?.message || 'Không tải được hồ sơ quyền riêng tư.', 'error');
      const balanceEl = document.getElementById('wallet-check-amount');
      if (balanceEl) balanceEl.textContent = 'Không tải được';
      const submitBtn = document.getElementById('btn-submit-deletion');
      if (submitBtn) submitBtn.disabled = true;
      return;
    }

    _currentDriverBalance = Number(profile.balance_vnd || 0);

    // Update UI elements
    const nameEl = document.getElementById('profile-name');
    const emailEl = document.getElementById('profile-email');
    const phoneEl = document.getElementById('profile-phone');
    const plateEl = document.getElementById('profile-plate');
    const sessionsEl = document.getElementById('profile-sessions-count');

    if (nameEl) nameEl.textContent = profile.display_name || 'Tài xế';
    if (emailEl) emailEl.textContent = profile.email || '—';
    if (phoneEl) phoneEl.textContent = profile.phone || 'Không lưu';
    if (plateEl) plateEl.textContent = profile.plate_number || 'Không lưu';
    if (sessionsEl) sessionsEl.textContent = profile.charging_sessions_count ?? 0;

    // Check balance logic (AC S-57)
    const amountEl = document.getElementById('wallet-check-amount');
    const tagWallet = document.getElementById('tag-wallet-status');
    const alertPos = document.getElementById('alert-positive-balance');
    const alertZero = document.getElementById('alert-zero-balance');
    const submitBtn = document.getElementById('btn-submit-deletion');

    if (amountEl) amountEl.textContent = fmtVnd(_currentDriverBalance);

    if (_currentDriverBalance !== 0) {
      if (tagWallet) {
        tagWallet.className = 'tag tag--warning';
        tagWallet.textContent = 'Chưa bằng 0';
      }
      if (alertPos) alertPos.classList.remove('is-hidden');
      if (alertZero) alertZero.classList.add('is-hidden');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.title = 'Vui lòng rút hoặc hoàn tiền toàn bộ số dư trước khi nộp yêu cầu';
      }
    } else {
      if (tagWallet) {
        tagWallet.className = 'tag tag--success';
        tagWallet.textContent = 'Hợp lệ';
      }
      if (alertPos) alertPos.classList.add('is-hidden');
      if (alertZero) alertZero.classList.remove('is-hidden');
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.title = '';
      }
    }

    // Check active request
    _activeRequest = profile.active_request || null;
    renderDriverRequestState();
  }

  function renderDriverRequestState() {
    const cardForm = document.getElementById('card-request-form');
    const cardActive = document.getElementById('card-active-request');

    if (!_activeRequest || ['cancelled', 'rejected'].includes(_activeRequest.status)) {
      if (cardForm) cardForm.classList.remove('is-hidden');
      if (cardActive) cardActive.classList.add('is-hidden');
    } else {
      if (cardForm) cardForm.classList.add('is-hidden');
      if (cardActive) cardActive.classList.remove('is-hidden');

      const codeEl = document.getElementById('active-req-code');
      const badgeEl = document.getElementById('active-req-badge');
      const descEl = document.getElementById('active-req-desc');
      const timeEl = document.getElementById('tl-time-submit');
      const stepReview = document.getElementById('tl-step-review');
      const stepAnon = document.getElementById('tl-step-anonymize');
      const btnCancel = document.getElementById('btn-cancel-request');

      if (codeEl) codeEl.textContent = `Mã yêu cầu: #${_activeRequest.id}`;
      if (timeEl) timeEl.textContent = fmtDatetime(_activeRequest.created_at);

      if (_activeRequest.status === 'pending') {
        if (badgeEl) {
          badgeEl.className = 'tag tag--warning';
          badgeEl.textContent = 'Đang xử lý';
        }
        if (descEl) descEl.textContent = 'Yêu cầu của bạn đang được Chuyên viên Quản vệ Dữ liệu (DPO) tiếp nhận và thẩm định điều kiện.';
        if (stepReview) stepReview.className = 'timeline-step is-current';
        if (stepAnon) stepAnon.className = 'timeline-step';
        if (btnCancel) btnCancel.classList.remove('is-hidden');
      } else if (_activeRequest.status === 'approved') {
        if (badgeEl) {
          badgeEl.className = 'tag tag--success';
          badgeEl.textContent = 'Đã hoàn tất';
        }
        if (descEl) descEl.textContent = 'Dữ liệu cá nhân và lịch sử vị trí sạc của bạn đã được ẩn danh hóa thành công.';
        if (stepReview) stepReview.className = 'timeline-step is-complete';
        if (stepAnon) stepAnon.className = 'timeline-step is-complete';
        if (btnCancel) btnCancel.classList.add('is-hidden');
      } else if (_activeRequest.status === 'rejected') {
        if (badgeEl) {
          badgeEl.className = 'tag tag--danger';
          badgeEl.textContent = 'Bị từ chối';
        }
        if (descEl) descEl.textContent = `Yêu cầu bị từ chối: ${_activeRequest.reject_reason || 'Chưa đáp ứng điều kiện số dư ví hoặc phiên sạc'}`;
        if (btnCancel) btnCancel.classList.add('is-hidden');
      }
    }
  }

  /* ── Admin View Functions ─────────────────────────────────────────────── */
  async function loadAdminData() {
    try {
      const requests = await ApiClient.listDataDeletionRequests();
      _adminRequests = requests.items || [];
      _adminLoadError = null;
    } catch (error) {
      _adminRequests = [];
      _adminLoadError = error?.message || 'Không tải được danh sách yêu cầu.';
      showToast(error?.message || 'Không tải được danh sách yêu cầu.', 'error');
    }
    updateAdminStats();
    renderAdminTable();
  }

  function updateAdminStats() {
    if (_adminLoadError) {
      ['adm-stat-total', 'adm-stat-pending', 'adm-stat-approved', 'adm-stat-rejected']
        .forEach(id => { const el = document.getElementById(id); if (el) el.textContent = '—'; });
      const countEl = document.getElementById('adm-req-count');
      if (countEl) countEl.textContent = 'Không tải được';
      return;
    }
    const total = _adminRequests.length;
    const pending = _adminRequests.filter(x => x.status === 'pending').length;
    const approved = _adminRequests.filter(x => x.status === 'approved').length;
    const rejected = _adminRequests.filter(x => x.status === 'rejected').length;

    const tEl = document.getElementById('adm-stat-total');
    const pEl = document.getElementById('adm-stat-pending');
    const aEl = document.getElementById('adm-stat-approved');
    const rEl = document.getElementById('adm-stat-rejected');

    if (tEl) tEl.textContent = total;
    if (pEl) pEl.textContent = pending;
    if (aEl) aEl.textContent = approved;
    if (rEl) rEl.textContent = rejected;

    const countEl = document.getElementById('adm-req-count');
    if (countEl) countEl.textContent = `${total} yêu cầu`;
  }

  function renderAdminTable() {
    const tbody = document.getElementById('adm-tbody');
    if (!tbody) return;

    if (_adminLoadError) {
      tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state">
        <div class="empty-state__title">Không tải được danh sách yêu cầu</div>
        <div class="empty-state__desc">${esc(_adminLoadError)}</div>
      </div></td></tr>`;
      return;
    }

    const search = document.getElementById('adm-filter-search')?.value.toLowerCase().trim() || '';
    const statusFilter = document.getElementById('adm-filter-status')?.value || '';

    const filtered = _adminRequests.filter(item => {
      if (statusFilter && item.status !== statusFilter) return false;
      if (search) {
        const text = `${item.driver_name} ${item.driver_email} ${item.driver_phone} ${item.plate_number}`.toLowerCase();
        if (!text.includes(search)) return false;
      }
      return true;
    });

    if (!filtered.length) {
      tbody.innerHTML = `<tr><td colspan="7">
        <div class="empty-state">
          <div class="empty-state__icon">📋</div>
          <div class="empty-state__title">Không có yêu cầu nào</div>
          <div class="empty-state__desc">Chưa có tài xế nào gửi yêu cầu xóa dữ liệu phù hợp với bộ lọc</div>
        </div>
      </td></tr>`;
      return;
    }

    tbody.innerHTML = filtered.map(item => {
      const isPending = item.status === 'pending';
      const isBalanceZero = (item.balance_vnd || 0) === 0;
      const isNoActiveSessions = (item.active_sessions_count || 0) === 0;
      const canApprove = isPending && isBalanceZero && isNoActiveSessions;

      let statusBadge = '';
      if (item.status === 'pending') {
        statusBadge = '<span class="req-badge req-badge--pending">Chờ phê duyệt</span>';
      } else if (item.status === 'approved') {
        statusBadge = '<span class="req-badge req-badge--approved">Đã ẩn danh hóa</span>';
      } else if (item.status === 'rejected') {
        statusBadge = '<span class="req-badge req-badge--rejected">Bị từ chối</span>';
      } else {
        statusBadge = '<span class="req-badge req-badge--cancelled">Đã hủy</span>';
      }

      let balanceDisplay = '';
      if (Number(item.balance_vnd) !== 0) {
        balanceDisplay = `<span style="color:hsl(0,70%,45%);font-weight:700;">${fmtVnd(item.balance_vnd)}</span>
          <div style="font-size:10px;color:hsl(0,70%,45%);">Số dư phải đúng 0 ₫</div>`;
      } else {
        balanceDisplay = `<span style="color:hsl(140,65%,38%);font-weight:700;">0 ₫</span>
          <div style="font-size:10px;color:hsl(140,65%,38%);">Đủ điều kiện</div>`;
      }

      return `<tr data-id="${item.id}">
        <td style="white-space:nowrap;font-size:var(--font-size-xs);">${fmtDatetime(item.created_at)}</td>
        <td>
          <div style="font-weight:600;font-size:var(--font-size-sm);">${esc(item.driver_name)}</div>
          <div style="font-size:11px;color:var(--color-text-secondary);">${esc(item.driver_email)} · ${esc(item.plate_number)}</div>
        </td>
        <td>
          <div style="font-size:var(--font-size-xs);font-weight:500;">${esc(item.reason_label || item.reason)}</div>
          <div style="font-size:11px;color:var(--color-text-secondary);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(item.reason_detail)}">
            ${esc(item.reason_detail || '—')}
          </div>
        </td>
        <td class="text-right">${balanceDisplay}</td>
        <td class="text-center font-mono" style="font-size:var(--font-size-xs);">
          ${item.active_sessions_count > 0 ? `<span class="tag tag--danger">${item.active_sessions_count} phiên</span>` : '<span style="color:var(--color-text-secondary);">0</span>'}
        </td>
        <td>${statusBadge}</td>
        <td class="text-right" style="white-space:nowrap;">
          ${isPending ? `
            <button class="btn btn--primary btn--sm btn-adm-approve" data-id="${item.id}" type="button" ${!canApprove ? 'disabled title="Ví còn tiền hoặc có phiên đang chạy"' : ''}>
              Duyệt ẩn danh
            </button>
            <button class="btn btn--secondary btn--sm btn-adm-reject" data-id="${item.id}" type="button">
              Từ chối
            </button>
          ` : `
            <span style="font-size:11px;color:var(--color-text-secondary);">Đã xử lý</span>
          `}
        </td>
      </tr>`;
    }).join('');

    // Attach event listeners for buttons
    tbody.querySelectorAll('.btn-adm-approve').forEach(btn => {
      btn.addEventListener('click', () => openApproveModal(btn.dataset.id));
    });
    tbody.querySelectorAll('.btn-adm-reject').forEach(btn => {
      btn.addEventListener('click', () => openRejectModal(btn.dataset.id));
    });
  }

  function openApproveModal(id) {
    const item = _adminRequests.find(x => String(x.id) === String(id));
    if (!item) return;
    _selectedReqId = id;

    const summaryEl = document.getElementById('approve-summary-content');
    if (summaryEl) {
      summaryEl.innerHTML = `
        <div class="approve-summary__item">
          <span class="approve-summary__label">Tài xế</span>
          <span class="approve-summary__value">${esc(item.driver_name)} (${esc(item.driver_email)})</span>
        </div>
        <div class="approve-summary__item">
          <span class="approve-summary__label">Biển số</span>
          <span class="approve-summary__value">${esc(item.plate_number)}</span>
        </div>
        <div class="approve-summary__item">
          <span class="approve-summary__label">Số dư ví</span>
          <span class="approve-summary__value">${fmtVnd(item.balance_vnd)} (Xác nhận = 0 ₫)</span>
        </div>
        <div class="approve-summary__item approve-summary__item--full">
          <span class="approve-summary__label">Lý do yêu cầu</span>
          <span class="approve-summary__value">${esc(item.reason_label || item.reason)}</span>
        </div>
      `;
    }

    document.getElementById('modal-approve-dialog')?.classList.remove('is-hidden');
  }

  function openRejectModal(id) {
    _selectedReqId = id;
    const input = document.getElementById('reject-reason-input');
    if (input) input.value = '';
    document.getElementById('modal-reject-dialog')?.classList.remove('is-hidden');
  }

  function closeModals() {
    document.getElementById('modal-approve-dialog')?.classList.add('is-hidden');
    document.getElementById('modal-reject-dialog')?.classList.add('is-hidden');
    _selectedReqId = null;
  }

  /* ── DOMContentLoaded ────────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', () => {
    const root = document.getElementById('privacy-root');
    const isDriver = root?.dataset.isDriver === 'true';
    const tabDriver = document.getElementById('tab-driver-view');
    const tabAdmin = document.getElementById('tab-admin-view');
    const secDriver = document.getElementById('section-driver-view');
    const secAdmin = document.getElementById('section-admin-view');

    if (isDriver) {
      loadDriverData();
    } else {
      secDriver?.classList.add('is-hidden');
      secAdmin?.classList.remove('is-hidden');
      loadAdminData();
    }

    if (tabDriver && tabAdmin) {
      tabDriver.addEventListener('click', () => {
        tabDriver.classList.add('is-active');
        tabDriver.setAttribute('aria-selected', 'true');
        tabAdmin.classList.remove('is-active');
        tabAdmin.setAttribute('aria-selected', 'false');
        secDriver?.classList.remove('is-hidden');
        secAdmin?.classList.add('is-hidden');
      });

      tabAdmin.addEventListener('click', () => {
        tabAdmin.classList.add('is-active');
        tabAdmin.setAttribute('aria-selected', 'true');
        tabDriver.classList.remove('is-active');
        tabDriver.setAttribute('aria-selected', 'false');
        secAdmin?.classList.remove('is-hidden');
        secDriver?.classList.add('is-hidden');
        loadAdminData();
      });
    }

    // 3. Driver Form submission
    const form = document.getElementById('form-privacy-deletion');
    if (form) {
      form.addEventListener('submit', async e => {
        e.preventDefault();

        if (_currentDriverBalance !== 0) {
          showToast('Số dư ví phải đúng bằng 0 đồng trước khi gửi yêu cầu.', 'error');
          return;
        }

        const reasonSelect = document.getElementById('req-reason-select');
        const reasonDetail = document.getElementById('req-reason-detail')?.value.trim();
        const pwd = document.getElementById('req-password-confirm')?.value;
        const agree = document.getElementById('req-agree-terms')?.checked;

        if (!reasonSelect?.value) {
          showToast('Vui lòng chọn lý do yêu cầu', 'error');
          return;
        }
        if (!pwd) {
          showToast('Vui lòng nhập mật khẩu xác nhận', 'error');
          return;
        }
        if (!agree) {
          showToast('Vui lòng xác nhận cam kết điều khoản', 'error');
          return;
        }

        const payload = {
          reason: reasonSelect.value,
          reason_label: reasonSelect.options[reasonSelect.selectedIndex].text,
          reason_detail: reasonDetail,
          password: pwd,
        };

        const submitBtn = document.getElementById('btn-submit-deletion');
        submitBtn.disabled = true;
        try {
          _activeRequest = await ApiClient.requestDataDeletion(payload);
          document.getElementById('req-password-confirm').value = '';
          showToast('Đã nộp yêu cầu xóa dữ liệu cá nhân thành công', 'success');
          renderDriverRequestState();
        } catch (error) {
          showToast(error?.message || 'Không gửi được yêu cầu.', 'error');
        } finally {
          submitBtn.disabled = _currentDriverBalance !== 0;
        }
      });
    }

    // 4. Cancel Request by Driver
    const btnCancel = document.getElementById('btn-cancel-request');
    if (btnCancel) {
      btnCancel.addEventListener('click', async () => {
        if (!confirm('Bạn có chắc chắn muốn hủy yêu cầu xóa dữ liệu này?')) return;
        try {
          _activeRequest = await ApiClient.cancelDataDeletionRequest(_activeRequest.id);
          showToast('Đã hủy yêu cầu xóa dữ liệu', 'info');
          renderDriverRequestState();
        } catch (error) {
          showToast(error?.message || 'Không hủy được yêu cầu.', 'error');
        }
      });
    }

    // 5. Admin Filters
    const admFilters = document.getElementById('adm-filters');
    if (admFilters) {
      admFilters.addEventListener('submit', e => {
        e.preventDefault();
        renderAdminTable();
      });
    }
    document.getElementById('btn-adm-reset')?.addEventListener('click', () => {
      admFilters?.reset();
      renderAdminTable();
    });

    // 6. Admin Modal Handlers
    document.getElementById('modal-approve-close')?.addEventListener('click', closeModals);
    document.getElementById('modal-approve-cancel')?.addEventListener('click', closeModals);
    document.getElementById('modal-approve-backdrop')?.addEventListener('click', closeModals);

    document.getElementById('modal-reject-close')?.addEventListener('click', closeModals);
    document.getElementById('modal-reject-cancel')?.addEventListener('click', closeModals);
    document.getElementById('modal-reject-backdrop')?.addEventListener('click', closeModals);

    document.getElementById('modal-approve-confirm')?.addEventListener('click', async () => {
      if (!_selectedReqId) return;
      try {
        await ApiClient.approveDataDeletionRequest(_selectedReqId);
        showToast('Đã phê duyệt và hoàn tất ẩn danh hóa dữ liệu', 'success');
        closeModals();
        await loadAdminData();
      } catch (error) {
        showToast(error?.message || 'Không thể phê duyệt yêu cầu.', 'error');
      }
    });

    document.getElementById('modal-reject-confirm')?.addEventListener('click', async () => {
      if (!_selectedReqId) return;
      const reason = document.getElementById('reject-reason-input')?.value.trim();
      if (!reason) {
        showToast('Vui lòng nhập lý do từ chối', 'error');
        return;
      }
      try {
        await ApiClient.rejectDataDeletionRequest(_selectedReqId, { reason });
        showToast('Đã từ chối yêu cầu xóa dữ liệu', 'info');
        closeModals();
        await loadAdminData();
      } catch (error) {
        showToast(error?.message || 'Không thể từ chối yêu cầu.', 'error');
      }
    });

    // ESC to close modals
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') closeModals();
    });
  });
})();
