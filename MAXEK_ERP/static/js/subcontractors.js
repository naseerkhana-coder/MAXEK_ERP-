document.addEventListener('DOMContentLoaded', function () {
  const form = document.querySelector('[data-subcontractor-form]');
  const isEditMode = form && form.getAttribute('data-edit-mode') === '1';
  const nameInput = document.querySelector('[data-sub-name-input]');
  const codePreview = document.querySelector('[data-sub-code-preview]');
  const rateTypeSelect = document.querySelector('[data-rate-type-select]');
  const manpowerSection = document.querySelector('[data-manpower-section]');
  const boqSection = document.querySelector('[data-boq-section]');
  const addBoqCard = document.querySelector('[data-boq-add-section]');
  let previewTimer = null;

  function syncRateSections() {
    if (!rateTypeSelect) return;
    const isBoq = rateTypeSelect.value === 'BOQ Base Rate';
    if (manpowerSection) manpowerSection.style.display = isBoq ? 'none' : '';
    if (boqSection) boqSection.style.display = isBoq ? '' : 'none';
    if (addBoqCard) addBoqCard.style.display = isBoq ? '' : 'none';
  }

  function refreshCodePreview() {
    if (isEditMode) return;
    if (!nameInput || !codePreview) return;
    const name = nameInput.value.trim();
    if (!name) {
      codePreview.value = '';
      return;
    }
    fetch('/api/subcontractors/preview-code?name=' + encodeURIComponent(name))
      .then(function (res) { return res.json(); })
      .then(function (data) {
        codePreview.value = data.code || '';
      })
      .catch(function () {
        codePreview.value = '';
      });
  }

  if (nameInput && !isEditMode) {
    nameInput.addEventListener('input', function () {
      clearTimeout(previewTimer);
      previewTimer = setTimeout(refreshCodePreview, 250);
    });
    refreshCodePreview();
  }

  function bindBoqRecalc(root) {
    (root || document).querySelectorAll('[data-boq-rate], [data-boq-qty]').forEach(function (input) {
      input.addEventListener('input', function () {
        const row = input.closest('tr');
        if (!row) return;
        const rateInput = row.querySelector('[data-boq-rate]');
        const qtyInput = row.querySelector('[data-boq-qty]');
        const totalInput = row.querySelector('[data-boq-total]');
        if (!rateInput || !qtyInput || !totalInput) return;
        const r = parseFloat(rateInput.value || '0') || 0;
        const q = parseFloat(qtyInput.value || '0') || 0;
        totalInput.value = (r * q).toFixed(2);
      });
    });
  }

  if (rateTypeSelect) {
    rateTypeSelect.addEventListener('change', syncRateSections);
    syncRateSections();
  }

  function initManpowerRows() {
    const container = document.querySelector('[data-manpower-rows]');
    const addBtn = document.querySelector('[data-manpower-add]');
    if (!container || !addBtn) return;

    const max = parseInt(container.getAttribute('data-max') || '7', 10);
    const template = container.querySelector('[data-manpower-row-template]');
    if (!template) return;

    function countRows() {
      return container.querySelectorAll('[data-manpower-row]:not([data-manpower-row-template])').length;
    }

    function syncRemoveButtons() {
      const rows = container.querySelectorAll('[data-manpower-row]:not([data-manpower-row-template])');
      const showRemove = rows.length > 1;
      rows.forEach(function (row) {
        const btn = row.querySelector('[data-manpower-remove]');
        if (btn) btn.hidden = !showRemove;
      });
    }

    addBtn.addEventListener('click', function () {
      if (countRows() >= max) return;
      const clone = template.cloneNode(true);
      clone.hidden = false;
      clone.removeAttribute('data-manpower-row-template');
      clone.setAttribute('data-manpower-row', '');
      clone.querySelectorAll('input').forEach(function (el) { el.value = ''; });
      clone.querySelectorAll('select').forEach(function (el) { el.selectedIndex = 0; });
      container.appendChild(clone);
      addBtn.disabled = countRows() >= max;
      syncRemoveButtons();
    });

    container.addEventListener('click', function (e) {
      const btn = e.target.closest('[data-manpower-remove]');
      if (!btn) return;
      const row = btn.closest('[data-manpower-row]');
      if (row && !row.hasAttribute('data-manpower-row-template')) {
        row.remove();
        addBtn.disabled = countRows() >= max;
        syncRemoveButtons();
      }
    });

    addBtn.disabled = countRows() >= max;
    syncRemoveButtons();
  }

  initManpowerRows();

  function initNewTradeModal() {
    var tradeModal = document.getElementById('new-trade-modal');
    var openTradeBtn = document.getElementById('open-new-trade-modal');
    if (!tradeModal) return;

    function showModal(modal) {
      document.querySelectorAll('.erp-modal').forEach(function (other) {
        if (other !== modal) {
          other.hidden = true;
          other.setAttribute('aria-hidden', 'true');
        }
      });
      modal.hidden = false;
      modal.setAttribute('aria-hidden', 'false');
      var firstField = modal.querySelector('input:not([type="hidden"]), select, textarea');
      if (firstField) firstField.focus();
    }

    function hideModal(modal) {
      modal.hidden = true;
      modal.setAttribute('aria-hidden', 'true');
    }

    if (openTradeBtn) {
      openTradeBtn.addEventListener('click', function (event) {
        event.preventDefault();
        showModal(tradeModal);
      });
    }

    tradeModal.querySelectorAll('[data-modal-close]').forEach(function (control) {
      control.addEventListener('click', function (event) {
        event.preventDefault();
        hideModal(tradeModal);
      });
    });
  }

  function applySelectedTrade() {
    var section = document.querySelector('[data-manpower-section]');
    if (!section) return;
    var selectedName = section.getAttribute('data-select-trade-name');
    if (!selectedName) return;
    var selects = section.querySelectorAll('select[data-trade-select]');
    for (var i = 0; i < selects.length; i++) {
      if (!selects[i].value) {
        selects[i].value = selectedName;
        return;
      }
    }
    if (selects.length) selects[0].value = selectedName;
  }

  initNewTradeModal();
  applySelectedTrade();

  function escapeCell(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function bindBoqLoader(projectSelect, loadButton, tbody) {
    if (!projectSelect || !loadButton || !tbody) return;

    function projectLabel() {
      const option = projectSelect.options[projectSelect.selectedIndex];
      return option && option.value ? option.text : '—';
    }

    function renderRows(items) {
      tbody.innerHTML = '';
      if (!items.length) {
        tbody.innerHTML = '<tr><td colspan="7">No BOQ items found for this project.</td></tr>';
        return;
      }
      const projectText = projectLabel();
      items.forEach(function (item) {
        const tr = document.createElement('tr');
        const rate = Number(item.rate || 0);
        const qty = Number(item.quantity || 0);
        const total = Number(item.amount || (rate * qty));
        const boqNumber = item.boq_number || '';
        const description = item.item_description || '';
        const unit = item.unit || '';
        tr.innerHTML =
          '<td>' + escapeCell(projectText) + '</td>' +
          '<td><input name="sb_unit[]" value="' + escapeCell(unit) + '" readonly></td>' +
          '<td>' +
          '<input type="hidden" name="sb_boq_item_id[]" value="' + escapeCell(item.id || '') + '">' +
          '<input type="hidden" name="sb_boq_number[]" value="' + escapeCell(boqNumber) + '">' +
          '<input value="' + escapeCell(boqNumber || '—') + '" readonly>' +
          '</td>' +
          '<td>' +
          '<input type="hidden" name="sb_item_description[]" value="' + escapeCell(description) + '">' +
          '<input value="' + escapeCell(description || '—') + '" readonly>' +
          '</td>' +
          '<td><input name="sb_rate[]" type="number" step="0.01" min="0" value="' + rate.toFixed(2) + '" data-boq-rate></td>' +
          '<td><input name="sb_quantity[]" type="number" step="0.01" min="0" value="' + qty.toFixed(2) + '" data-boq-qty></td>' +
          '<td><input name="sb_total_amount[]" type="number" step="0.01" min="0" value="' + total.toFixed(2) + '" data-boq-total></td>';
        tbody.appendChild(tr);
      });
      bindBoqRecalc(tbody);
    }

    loadButton.addEventListener('click', function () {
      const projectId = projectSelect.value;
      if (!projectId) {
        tbody.innerHTML = '<tr><td colspan="7">Select a project first.</td></tr>';
        return;
      }
      tbody.innerHTML = '<tr><td colspan="7">Loading BOQ items…</td></tr>';
      fetch('/api/projects/' + encodeURIComponent(projectId) + '/boq-items')
        .then(function (res) {
          if (!res.ok) throw new Error('load failed');
          return res.json();
        })
        .then(function (data) {
          const items = Array.isArray(data) ? data : [];
          renderRows(items);
        })
        .catch(function () {
          tbody.innerHTML = '<tr><td colspan="7">Unable to load BOQ items.</td></tr>';
        });
    });
  }

  bindBoqLoader(
    document.getElementById('boq_project_id'),
    document.querySelector('[data-load-boq-items]'),
    document.querySelector('[data-boq-rates-body]')
  );
  bindBoqLoader(
    document.querySelector('[data-boq-project-select-add]'),
    document.querySelector('[data-load-boq-items-add]'),
    document.querySelector('[data-boq-rates-body-add]')
  );

  bindBoqRecalc(document.querySelector('[data-boq-rates-body]'));
});
