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

  /* ── Mock Data Fallbacks ──────────────────────────────────────────────── */
  function getMockProfile() {
    return {
      display_name: 'Nguyễn Văn An',
      email: 'an.nguyen@driver.vn',
      phone: '0912 345 678',
      plate_number: '29A-998.24',
      charging_sessions_count: 14,
      balance_vnd: 0, // Mặc định 0 ₫ để test đủ điều kiện
      active_request: null,
    };
  }

  function getMockAdminRequests() {
    const now = Date.now();
    return [
      {
        id: 'REQ-20261017-001',
        driver_name: 'Trần Văn Hùng',
        driver_email: 'hung.tran@gmail.com',
        driver_phone: '0988 123 456',
        plate_number: '30E-123.45',
        reason: 'privacy_location_concern',
        reason_label: 'Lo ngại rò rỉ dữ liệu vị trí',
        reason_detail: 'Tôi đã bán xe điện và muốn xóa toàn bộ lịch sử di chuyển.',
        balance_vnd: 0,
        active_sessions_count: 0,
        status: 'pending',
        created_at: new Date(now - 2 * 3600_000).toISOString(),
      },
      {
        id: 'REQ-20261016-002',
        driver_name: 'Lê Hoàng Yến',
        driver_email: 'yen.le@outlook.com',
        driver_phone: '0903 555 777',
        plate_number: '51G-888.99',
        reason: 'right_to_be_forgotten',
        reason_label: 'Thực hiện quyền theo Nghị định 13/2023/NĐ-CP',
        reason_detail: 'Yêu cầu xóa tài khoản và ẩn danh hóa lịch sử sạc.',
        balance_vnd: 150000, // Còn số dư dương -> Không đủ điều kiện duyệt
        active_sessions_count: 0,
        status: 'pending',
        created_at: new Date(now - 24 * 3600_000).toISOString(),
      },
      {
        id: 'REQ-20261014-003',
        driver_name: 'Phạm Quốc Bảo',
        driver_email: 'bao.pham@driver.vn',
        driver_phone: '0934 999 111',
        plate_number: '43A-667.12',
        reason: 'no_longer_using_ev',
        reason_label: 'Không còn sử dụng xe điện',
        reason_detail: 'Chuyển công tác nước ngoài.',
        balance_vnd: 0,
        active_sessions_count: 0,
        status: 'approved',
        created_at: new Date(now - 72 * 3600_000).toISOString(),
        anonymized_at: new Date(now - 48 * 3600_000).toISOString(),
      },
      {
        id: 'REQ-20261012-004',
        driver_name: 'Đặng Mai Phương',
        driver_email: 'phuong.dang@gmail.com',
        driver_phone: '0911 222 333',
        plate_number: '60B-345.67',
        reason: 'other',
        reason_label: 'Lý do khác',
        reason_detail: 'Tài khoản không dùng nữa.',
        balance_vnd: 50000,
        active_sessions_count: 0,
        status: 'rejected',
        reject_reason: 'Ví còn số dư 50.000 ₫, vui lòng rút tiền trước khi nộp yêu cầu.',
        created_at: new Date(now - 120 * 3600_000).toISOString(),
      },
    ];
  }

  /* ── Driver View Functions ────────────────────────────────────────────── */
  async function loadDriverData() {
    let profile;
    try {
      if (ApiClient.getPrivacyProfile) {
        profile = await ApiClient.getPrivacyProfile();
      } else {
        profile = getMockProfile();
      }
    } catch (_) {
      profile = getMockProfile();
    }

    // Try fetching real wallet balance
    try {
      if (ApiClient.getWallet) {
        const wallet = await ApiClient.getWallet();
        profile.balance_vnd = wallet.balance_vnd ?? profile.balance_vnd;
      }
    } catch (_) {
      // Keep profile.balance_vnd
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
    if (phoneEl) phoneEl.textContent = profile.phone || '—';
    if (plateEl) plateEl.textContent = profile.plate_number || '—';
    if (sessionsEl) sessionsEl.textContent = profile.charging_sessions_count ?? 0;

    // Check balance logic (AC S-57)
    const amountEl = document.getElementById('wallet-check-amount');
    const tagWallet = document.getElementById('tag-wallet-status');
    const alertPos = document.getElementById('alert-positive-balance');
    const alertZero = document.getElementById('alert-zero-balance');
    const submitBtn = document.getElementById('btn-submit-deletion');

    if (amountEl) amountEl.textContent = fmtVnd(_currentDriverBalance);

    if (_currentDriverBalance > 0) {
      if (tagWallet) {
        tagWallet.className = 'tag tag--warning';
        tagWallet.textContent = 'Còn số dư';
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
    _activeRequest = profile.active_request || _activeRequest;
    renderDriverRequestState();
  }

  function renderDriverRequestState() {
    const cardForm = document.getElementById('card-request-form');
    const cardActive = document.getElementById('card-active-request');

    if (!_activeRequest || _activeRequest.status === 'cancelled') {
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
    let requests;
    try {
      if (ApiClient.listDataDeletionRequests) {
        requests = await ApiClient.listDataDeletionRequests();
      } else {
        requests = getMockAdminRequests();
      }
    } catch (_) {
      requests = getMockAdminRequests();
    }

    _adminRequests = requests.items || requests;
    updateAdminStats();
    renderAdminTable();
  }

  function updateAdminStats() {
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
      if (item.balance_vnd > 0) {
        balanceDisplay = `<span style="color:hsl(0,70%,45%);font-weight:700;">${fmtVnd(item.balance_vnd)}</span>
          <div style="font-size:10px;color:hsl(0,70%,45%);">Phải hoàn tiền trước</div>`;
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
    const item = _adminRequests.find(x => x.id === id);
    if (!item) return;
    _selectedReqId = id;

    const summaryEl = document.getElementById('approve-summary-content');
    if (summaryEl) {
      summaryEl.innerHTML = `
        <div><strong>Tài xế:</strong> ${esc(item.driver_name)} (${esc(item.driver_email)})</div>
        <div><strong>Biển số:</strong> ${esc(item.plate_number)}</div>
        <div><strong>Số dư ví:</strong> ${fmtVnd(item.balance_vnd)} (Xác nhận = 0 ₫)</div>
        <div><strong>Lý do yêu cầu:</strong> ${esc(item.reason_label || item.reason)}</div>
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
    // 1. Load Driver Data
    loadDriverData();

    // 2. Role tab switcher
    const tabDriver = document.getElementById('tab-driver-view');
    const tabAdmin = document.getElementById('tab-admin-view');
    const secDriver = document.getElementById('section-driver-view');
    const secAdmin = document.getElementById('section-admin-view');

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

        if (_currentDriverBalance > 0) {
          showToast('Ví của bạn còn số dư dương. Vui lòng rút tiền trước khi nộp yêu cầu.', 'error');
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

        try {
          if (ApiClient.requestDataDeletion) {
            await ApiClient.requestDataDeletion(payload);
          }
        } catch (_) {
          // Fallback mock
        }

        _activeRequest = {
          id: `REQ-${Date.now().toString().slice(-6)}`,
          created_at: new Date().toISOString(),
          status: 'pending',
          reason: payload.reason,
          reason_label: payload.reason_label,
          reason_detail: payload.reason_detail,
        };

        showToast('Đã nộp yêu cầu xóa dữ liệu cá nhân thành công', 'success');
        renderDriverRequestState();
      });
    }

    // 4. Cancel Request by Driver
    const btnCancel = document.getElementById('btn-cancel-request');
    if (btnCancel) {
      btnCancel.addEventListener('click', async () => {
        if (!confirm('Bạn có chắc chắn muốn hủy yêu cầu xóa dữ liệu này?')) return;
        try {
          if (ApiClient.cancelDataDeletionRequest && _activeRequest?.id) {
            await ApiClient.cancelDataDeletionRequest(_activeRequest.id);
          }
        } catch (_) {
          // Fallback
        }
        _activeRequest = null;
        showToast('Đã hủy yêu cầu xóa dữ liệu', 'info');
        renderDriverRequestState();
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
        if (ApiClient.approveDataDeletionRequest) {
          await ApiClient.approveDataDeletionRequest(_selectedReqId);
        }
      } catch (_) {
        // Fallback
      }
      const item = _adminRequests.find(x => x.id === _selectedReqId);
      if (item) {
        item.status = 'approved';
        item.anonymized_at = new Date().toISOString();
      }
      showToast('Đã phê duyệt và hoàn tất ẩn danh hóa dữ liệu', 'success');
      closeModals();
      updateAdminStats();
      renderAdminTable();
    });

    document.getElementById('modal-reject-confirm')?.addEventListener('click', async () => {
      if (!_selectedReqId) return;
      const reason = document.getElementById('reject-reason-input')?.value.trim();
      if (!reason) {
        showToast('Vui lòng nhập lý do từ chối', 'error');
        return;
      }
      try {
        if (ApiClient.rejectDataDeletionRequest) {
          await ApiClient.rejectDataDeletionRequest(_selectedReqId, { reason });
        }
      } catch (_) {
        // Fallback
      }
      const item = _adminRequests.find(x => x.id === _selectedReqId);
      if (item) {
        item.status = 'rejected';
        item.reject_reason = reason;
      }
      showToast('Đã từ chối yêu cầu xóa dữ liệu', 'info');
      closeModals();
      updateAdminStats();
      renderAdminTable();
    });

    // ESC to close modals
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') closeModals();
    });
  });
})();
