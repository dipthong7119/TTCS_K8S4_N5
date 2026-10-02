/**
 * restart_button.js — Nút khởi động lại trụ sạc (SCRUM-134)
 *
 * Module cung cấp hàm tạo và xử lý nút Restart cho từng trụ trên lưới giám sát.
 * Bao gồm:
 *   - Hộp xác nhận (confirm dialog) trước khi gửi lệnh
 *   - Toast báo lỗi khi trụ ngoại tuyến
 *   - Loading state khi đang gửi lệnh
 *   - Tự disable khi trụ offline
 *
 * Giai đoạn mock: gọi mock API thay vì ApiClient.resetChargePoint thật.
 * Khi backend SCRUM-107 & API SCRUM-134 sẵn sàng: bỏ mock, dùng ApiClient thật.
 *
 * Sử dụng:
 *   RestartButton.createButton(chargePoint, container);
 *   RestartButton.handleRestart(chargePointCode, resetType);
 */

const RestartButton = (() => {
  'use strict';

  // ── ID dùng cho confirm modal (đảm bảo unique) ───────────────────────
  const MODAL_ID = 'restart-confirm-modal';
  let _modalEl = null;
  let _pendingResolve = null;

  /**
   * Tạo modal xác nhận (lazy — chỉ tạo 1 lần, tái sử dụng)
   */
  function _ensureModal() {
    if (_modalEl) return _modalEl;

    const backdrop = document.createElement('div');
    backdrop.id = MODAL_ID;
    backdrop.className = 'modal-backdrop is-hidden';
    backdrop.setAttribute('role', 'dialog');
    backdrop.setAttribute('aria-modal', 'true');
    backdrop.setAttribute('aria-labelledby', 'restart-confirm-title');

    backdrop.innerHTML = `
      <div class="modal">
        <div class="modal__header">
          <h2 class="modal__title" id="restart-confirm-title">Xác nhận khởi động lại</h2>
          <button class="modal__close" id="restart-confirm-close" type="button" aria-label="Đóng">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
                 stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal__body" id="restart-confirm-body">
          <div class="restart-confirm__icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                 stroke-linecap="round" stroke-linejoin="round">
              <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"></path>
              <line x1="12" y1="9" x2="12" y2="13"></line>
              <line x1="12" y1="17" x2="12.01" y2="17"></line>
            </svg>
          </div>
          <p class="restart-confirm__message" id="restart-confirm-msg">
            Bạn có chắc muốn khởi động lại trụ sạc này?
          </p>
          <p class="restart-confirm__sub">
            Hành động này sẽ tạm ngắt dịch vụ trên trụ. Phiên sạc đang diễn ra (nếu có) sẽ bị gián đoạn.
          </p>
        </div>
        <div class="modal__footer">
          <button class="btn btn--secondary" id="restart-confirm-cancel" type="button">Hủy</button>
          <button class="btn btn--danger" id="restart-confirm-ok" type="button">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <polyline points="23 4 23 10 17 10"></polyline>
              <path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"></path>
            </svg>
            Khởi động lại
          </button>
        </div>
      </div>`;

    document.body.appendChild(backdrop);
    _modalEl = backdrop;

    // Sự kiện đóng modal
    const closeBtn = backdrop.querySelector('#restart-confirm-close');
    const cancelBtn = backdrop.querySelector('#restart-confirm-cancel');
    const okBtn = backdrop.querySelector('#restart-confirm-ok');

    closeBtn.addEventListener('click', () => _resolveConfirm(false));
    cancelBtn.addEventListener('click', () => _resolveConfirm(false));
    okBtn.addEventListener('click', () => _resolveConfirm(true));
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) _resolveConfirm(false);
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !backdrop.classList.contains('is-hidden')) {
        _resolveConfirm(false);
      }
    });

    return _modalEl;
  }

  function _resolveConfirm(result) {
    if (_modalEl) _modalEl.classList.add('is-hidden');
    if (_pendingResolve) {
      _pendingResolve(result);
      _pendingResolve = null;
    }
  }

  /**
   * Hiển thị hộp xác nhận.
   * @param {string} cpCode - mã trụ sạc
   * @param {string} resetType - 'Soft' hoặc 'Hard'
   * @returns {Promise<boolean>} true nếu người dùng xác nhận
   */
  function showConfirm(cpCode, resetType) {
    const modal = _ensureModal();
    const typeLabel = resetType === 'Hard' ? 'cứng (Hard)' : 'mềm (Soft)';
    const msg = modal.querySelector('#restart-confirm-msg');
    msg.textContent = `Bạn có chắc muốn khởi động lại ${typeLabel} trụ "${cpCode}"?`;
    modal.classList.remove('is-hidden');
    modal.querySelector('#restart-confirm-ok').focus();

    return new Promise((resolve) => {
      _pendingResolve = resolve;
    });
  }



  /**
   * Xử lý gửi lệnh restart cho trụ sạc.
   * @param {string} cpCode     - mã trụ
   * @param {string} resetType  - 'Soft' | 'Hard'
   * @param {boolean} isOffline - trụ đang ngoại tuyến?
   * @param {HTMLButtonElement} [buttonEl] - nút gốc để cập nhật trạng thái
   */
  async function handleRestart(cpCode, resetType, isOffline, buttonEl) {
    // Kiểm tra trạng thái ngoại tuyến
    if (isOffline) {
      if (typeof showToast === 'function') {
        showToast(`Trụ "${cpCode}" đang ngoại tuyến — không thể gửi lệnh khởi động lại.`, 'error', 5000);
      }
      return;
    }

    // Hiển thị hộp xác nhận
    const confirmed = await showConfirm(cpCode, resetType);
    if (!confirmed) return;

    // Cập nhật trạng thái nút
    if (buttonEl) {
      buttonEl.disabled = true;
      buttonEl.classList.add('btn--loading');
      buttonEl.querySelector('.restart-btn__label').textContent = 'Đang gửi…';
    }

    try {
      const result = await ApiClient.resetChargePoint(cpCode, resetType);

      if (typeof showToast === 'function') {
        showToast(result.message || 'Lệnh khởi động lại đã được gửi', 'success');
      }
    } catch (error) {
      if (typeof showToast === 'function') {
        showToast(error.message || 'Không gửi được lệnh khởi động lại', 'error');
      }
    } finally {
      if (buttonEl) {
        buttonEl.disabled = false;
        buttonEl.classList.remove('btn--loading');
        buttonEl.querySelector('.restart-btn__label').textContent = 'Khởi động lại';
      }
    }
  }

  /**
   * Tạo HTML cho nút restart và select kiểu reset.
   * @param {Object} chargePoint - { id, code, status, ... }
   * @returns {string} HTML markup
   */
  function createMarkup(chargePoint) {
    const isOffline = chargePoint.status === 'offline';
    const escapedCode = String(chargePoint.code ?? '').replace(/[&<>"']/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[char]);

    return `<div class="restart-controls" data-restart-cp="${escapedCode}">
      <div class="restart-controls__row">
        <select class="form-select restart-controls__type"
                id="restart-type-${chargePoint.id}"
                aria-label="Kiểu khởi động lại trụ ${escapedCode}">
          <option value="Soft">Mềm (Soft)</option>
          <option value="Hard">Cứng (Hard)</option>
        </select>
        <button class="btn btn--danger btn--sm restart-btn"
                id="restart-btn-${chargePoint.id}"
                type="button"
                data-cp-code="${escapedCode}"
                data-cp-offline="${isOffline}"
                ${isOffline ? 'disabled' : ''}
                aria-label="Khởi động lại trụ ${escapedCode}">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="23 4 23 10 17 10"></polyline>
            <path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"></path>
          </svg>
          <span class="restart-btn__label">Khởi động lại</span>
        </button>
      </div>
      ${isOffline ? `<p class="restart-controls__offline-hint">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        Trụ đang ngoại tuyến
      </p>` : ''}
    </div>`;
  }

  /**
   * Gắn sự kiện click cho tất cả nút restart trong một container.
   * @param {HTMLElement} container - phần tử cha chứa các nút
   */
  function bindEvents(container) {
    container.querySelectorAll('.restart-btn').forEach(btn => {
      btn.addEventListener('click', function () {
        const cpCode = this.dataset.cpCode;
        const isOffline = this.dataset.cpOffline === 'true';
        const wrapper = this.closest('.restart-controls');
        const select = wrapper?.querySelector('.restart-controls__type');
        const resetType = select ? select.value : 'Soft';
        handleRestart(cpCode, resetType, isOffline, this);
      });
    });
  }

  return { createMarkup, bindEvents, handleRestart, showConfirm };
})();

window.RestartButton = RestartButton;
