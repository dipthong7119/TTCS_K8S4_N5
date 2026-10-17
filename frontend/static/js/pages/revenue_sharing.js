(function () {
  'use strict';
  const fromInput = document.getElementById('rev-share-from'),
    toInput = document.getElementById('rev-share-to'),
    errBox = document.getElementById('rev-share-error'),
    loadBox = document.getElementById('rev-share-loading'),
    notReadyBox = document.getElementById('rev-share-not-ready'),
    tbody = document.getElementById('rev-share-tbody'),
    tfoot = document.getElementById('rev-share-tfoot'),
    btnApply = document.getElementById('btn-apply-filter');

  const toIso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  const NOT_READY_TEXT = 'Báo cáo chưa sẵn sàng. Vui lòng thử lại sau.';

  function clearError() {
    if (errBox) { errBox.textContent = ''; errBox.hidden = true; }
  }

  function showError(msg) {
    if (errBox) {
      errBox.textContent = msg;
      errBox.hidden = false;
    }
  }

  function onDateChange() {
    clearError();
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-4">${NOT_READY_TEXT}</td></tr>`;
    }
    if (notReadyBox) notReadyBox.hidden = false;
  }

  function setDates(start, end) {
    fromInput.value = toIso(start);
    toInput.value = toIso(end);
    clearError();
    applyFilter();
  }

  function setQuickFilter(type) {
    const now = new Date();
    if (type === 'today') setDates(now, now);
    else if (type === 'week') {
      const day = now.getDay();
      const mon = new Date(now.getFullYear(), now.getMonth(), now.getDate() + (day === 0 ? -6 : 1 - day));
      setDates(mon, new Date(mon.getFullYear(), mon.getMonth(), mon.getDate() + 6));
    } else if (type === 'month') {
      setDates(new Date(now.getFullYear(), now.getMonth(), 1), new Date(now.getFullYear(), now.getMonth() + 1, 0));
    }
  }

  function applyFilter() {
    clearError();
    const from = fromInput?.value, to = toInput?.value;
    if (!from || !to) {
      showError('Vui lòng chọn đầy đủ ngày bắt đầu và kết thúc.');
      return;
    }
    if (from > to) {
      showError('Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.');
      return;
    }

    if (loadBox) loadBox.hidden = true;
    if (notReadyBox) notReadyBox.hidden = false;
    if (tfoot) tfoot.hidden = true;

    tbody.innerHTML = `<tr>
      <td colspan="5" class="text-center text-muted py-4">${NOT_READY_TEXT}</td>
    </tr>`;
  }

  ['btn-quick-today:today', 'btn-quick-week:week', 'btn-quick-month:month'].forEach(item => {
    const [id, type] = item.split(':');
    document.getElementById(id)?.addEventListener('click', () => setQuickFilter(type));
  });

  btnApply?.addEventListener('click', applyFilter);
  fromInput?.addEventListener('input', onDateChange);
  toInput?.addEventListener('input', onDateChange);

  setQuickFilter('month');
})();
