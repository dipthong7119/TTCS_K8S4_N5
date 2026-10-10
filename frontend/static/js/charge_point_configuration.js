/* SCRUM-60: Form đổi cấu hình trụ dành cho vận hành viên. */
window.ChargePointConfiguration = (() => {
    'use strict';

    const specs = {
        HeartbeatInterval: {
            label: 'Khoảng nhịp tim',
            min: 30,
            max: 3600,
        },
        MeterValueSampleInterval: {
            label: 'Chu kỳ gửi số đo',
            min: 5,
            max: 900,
        },
    };
    const states = new Map();

    function getState(code) {
        if (!states.has(code)) {
            states.set(code, {
                key: 'HeartbeatInterval',
                value: '',
                pending: false,
                message: '',
            });
        }
        return states.get(code);
    }

    function createMarkup(code) {
        const safeCode = String(code).replace(/[&<>"']/g, char => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;',
            '"': '&quot;', "'": '&#39;',
        })[char]);

        return `
      <form data-configuration-code="${safeCode}">
        <h3>Cấu hình trụ</h3>
        <label>
          Cấu hình cần đổi
          <select class="form-select" data-config-key>
            <option value="HeartbeatInterval">Khoảng nhịp tim</option>
            <option value="MeterValueSampleInterval">Chu kỳ gửi số đo</option>
          </select>
        </label>
        <label>
          Giá trị mới (giây)
          <input class="form-input" data-config-value
                 type="number" step="1" required />
        </label>
        <p class="form-hint" data-config-hint></p>
        <button class="btn btn--primary" type="submit">
          Gửi cấu hình
        </button>
        <p data-config-message role="status" aria-live="polite"></p>
      </form>`;
    }

    function bindEvents(root) {
        root.querySelectorAll('[data-configuration-code]').forEach(form => {
            if (form.dataset.bound) return;
            form.dataset.bound = 'true';

            const code = form.dataset.configurationCode;
            const state = getState(code);
            const keyInput = form.querySelector('[data-config-key]');
            const valueInput = form.querySelector('[data-config-value]');
            const button = form.querySelector('button');
            const hint = form.querySelector('[data-config-hint]');
            const message = form.querySelector('[data-config-message]');

            keyInput.value = state.key;
            valueInput.value = state.value;

            const update = () => {
                const spec = specs[state.key];
                valueInput.min = spec.min;
                valueInput.max = spec.max;
                hint.textContent = `Nhập số nguyên từ ${spec.min} đến ${spec.max} giây.`;
                keyInput.disabled = valueInput.disabled = button.disabled = state.pending;
                button.textContent = state.pending ? 'Đang gửi…' : 'Gửi cấu hình';
                message.textContent = state.message;
            };
            state.update = update;

            keyInput.addEventListener('change', () => {
                state.key = keyInput.value;
                state.message = '';
                update();
            });
            valueInput.addEventListener('input', () => {
                state.value = valueInput.value;
            });

            form.addEventListener('submit', async event => {
                event.preventDefault();
                if (state.pending) return;

                const key = state.key;
                const raw = valueInput.value.trim();
                const value = Number(raw);
                const spec = specs[key];

                if (!raw || !Number.isInteger(value) ||
                    value < spec.min || value > spec.max) {
                    state.message = `Giá trị phải là số nguyên từ ${spec.min} đến ${spec.max}.`;
                    update();
                    return;
                }

                if (!window.confirm(`Đổi ${spec.label} của trụ ${code} thành ${value} giây?`)) {
                    return;
                }

                state.pending = true;
                state.message = 'Đang chờ trụ xác nhận cấu hình…';
                update();

                try {
                    const result = await ApiClient.changeChargePointConfiguration(code, key, value);
                    if (result.status === 'reboot_required') {
                        state.message = 'Trụ đã nhận cấu hình. Cần khởi động lại để áp dụng.';
                    } else if (result.status === 'applied') {
                        state.message = `Trụ đã xác nhận áp dụng giá trị ${result.value} giây.`;
                    } else {
                        state.message = 'Phản hồi chưa xác nhận cấu hình được áp dụng.';
                    }
                } catch (error) {
                    state.message = error.message || 'Không thể đổi cấu hình.';
                } finally {
                    state.pending = false;
                    state.update();
                }
            });

            update();
        });
    }

    return { createMarkup, bindEvents };
})();