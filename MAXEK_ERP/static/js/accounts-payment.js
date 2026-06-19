(function () {
  function toggleMode(form) {
    var mode = form.querySelector('[data-payment-mode]');
    var pcField = form.querySelector('[data-petty-cash-field]');
    var bankFields = form.querySelectorAll('[data-bank-field]');
    if (!mode) return;
    var isPetty = mode.value === 'Petty Cash';
    if (pcField) pcField.hidden = !isPetty;
    bankFields.forEach(function (el) {
      el.style.display = isPetty ? 'none' : '';
    });
    var pcSel = form.querySelector('#pv_petty_cash_id');
    if (pcSel) pcSel.required = isPetty;
  }

  function loadPettyCashOptions(selectEl, preselect) {
    if (!selectEl) return;
    fetch('/api/accounts/petty-cash-settled')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var items = data.items || [];
        selectEl.innerHTML = '<option value="">Select settled petty cash</option>';
        items.forEach(function (item) {
          var opt = document.createElement('option');
          opt.value = item.id;
          opt.textContent = item.label;
          opt.setAttribute('data-amount', item.transferred_amount || 0);
          opt.setAttribute('data-project-id', item.project_id || '');
          if (preselect && String(preselect) === String(item.id)) opt.selected = true;
          selectEl.appendChild(opt);
        });
        selectEl.addEventListener('change', function () {
          var option = selectEl.options[selectEl.selectedIndex];
          if (!option || !option.value) return;
          var amountInput = document.querySelector('[name="amount"]');
          var projectSelect = document.querySelector('[name="project_id"]');
          var amt = parseFloat(option.getAttribute('data-amount') || '0');
          if (amountInput && amt > 0 && !amountInput.value) {
            amountInput.value = amt.toFixed(2);
          }
          var pid = option.getAttribute('data-project-id');
          if (projectSelect && pid && !projectSelect.value) {
            projectSelect.value = pid;
          }
          fetch('/api/accounts/petty-cash-balance/' + option.value)
            .then(function (r) { return r.json(); })
            .then(function (data) {
              var hint = form.querySelector('[data-pc-balance]');
              if (!hint) {
                hint = document.createElement('p');
                hint.setAttribute('data-pc-balance', '1');
                hint.style.fontSize = '0.85rem';
                hint.style.color = '#64748b';
                pcField.appendChild(hint);
              }
              hint.textContent = 'Available petty cash balance: ₹' + (data.balance || 0).toFixed(2);
            })
            .catch(function () { /* silent */ });
        });
      })
      .catch(function () { /* silent */ });
  }

  function initPaymentForm() {
    var form = document.querySelector('[data-payment-voucher-form]');
    if (!form) return;
    var mode = form.querySelector('[data-payment-mode]');
    if (mode) {
      mode.addEventListener('change', function () { toggleMode(form); });
    }
    toggleMode(form);
    loadPettyCashOptions(form.querySelector('#pv_petty_cash_id'), window.PV_PRESELECT_PC || null);
  }

  document.addEventListener('DOMContentLoaded', function () {
    var selects = document.querySelectorAll('[data-head-select]');
    var ready = Promise.resolve();
    if (window.MaxekAccounts && window.MaxekAccounts.ensureChartHeadSelect && selects.length) {
      ready = Promise.all(Array.prototype.map.call(selects, window.MaxekAccounts.ensureChartHeadSelect));
    }
    ready.finally(function () {
      initPaymentForm();
      document.querySelectorAll('[data-add-alloc-row]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var tbody = document.querySelector('#alloc-table tbody');
          if (!tbody) return;
          var row = tbody.querySelector('tr');
          if (row) tbody.appendChild(row.cloneNode(true));
        });
      });
    });
  });
})();
