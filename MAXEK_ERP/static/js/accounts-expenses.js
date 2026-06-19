(function () {
  function parseNum(val) {
    var n = parseFloat(val);
    return isNaN(n) ? 0 : n;
  }

  function calcLine(row) {
    var qty = parseNum(row.querySelector('[data-qty]')?.value);
    var rate = parseNum(row.querySelector('[data-rate]')?.value);
    var gst = parseNum(row.querySelector('[data-gst]')?.value);
    var taxType = row.querySelector('[data-tax-type]')?.value || 'CGST_SGST';
    var taxable = Math.round(qty * rate * 100) / 100;
    var taxTotal = Math.round(taxable * gst / 100 * 100) / 100;
    var cgst = 0;
    var sgst = 0;
    var igst = 0;
    if (taxType === 'IGST') {
      igst = taxTotal;
    } else {
      cgst = Math.round(taxTotal / 2 * 100) / 100;
      sgst = Math.round((taxTotal - cgst) * 100) / 100;
    }
    var total = Math.round((taxable + cgst + sgst + igst) * 100) / 100;
    var setCell = function (sel, val) {
      var el = row.querySelector(sel);
      if (el) el.textContent = val.toFixed(2);
    };
    setCell('[data-taxable]', taxable);
    setCell('[data-cgst]', cgst);
    setCell('[data-sgst]', sgst);
    setCell('[data-igst]', igst);
    setCell('[data-line-total]', total);
    return { taxable: taxable, cgst: cgst, sgst: sgst, igst: igst, total: total };
  }

  function recalcTotals(tbody) {
    var sub = 0;
    var cgst = 0;
    var sgst = 0;
    var igst = 0;
    var grand = 0;
    tbody.querySelectorAll('[data-expense-line]').forEach(function (row) {
      var line = calcLine(row);
      sub += line.taxable;
      cgst += line.cgst;
      sgst += line.sgst;
      igst += line.igst;
      grand += line.total;
    });
    var set = function (sel, val) {
      var el = document.querySelector(sel);
      if (el) el.textContent = val.toFixed(2);
    };
    set('[data-total-subtotal]', sub);
    set('[data-total-cgst]', cgst);
    set('[data-total-sgst]', sgst);
    set('[data-total-igst]', igst);
    set('[data-total-grand]', grand);
  }

  function bindRow(row, tbody) {
    row.querySelectorAll('input, select').forEach(function (el) {
      el.addEventListener('input', function () { recalcTotals(tbody); });
      el.addEventListener('change', function () { recalcTotals(tbody); });
    });
    var removeBtn = row.querySelector('[data-remove-line]');
    if (removeBtn) {
      removeBtn.addEventListener('click', function () {
        if (tbody.querySelectorAll('[data-expense-line]').length <= 1) return;
        row.remove();
        recalcTotals(tbody);
      });
    }
  }

  function applyHeadRules(form) {
    var select = form.querySelector('[data-head-select]');
    if (!select) return;
    var option = select.options[select.selectedIndex];
    var reqProject = option && option.getAttribute('data-req-project') === '1';
    var reqVendor = option && option.getAttribute('data-req-vendor') === '1';
    var projectField = form.querySelector('[data-field-project]');
    var vendorField = form.querySelector('[data-field-vendor]');
    if (projectField) {
      projectField.querySelector('select').required = reqProject;
      projectField.style.display = reqProject ? '' : '';
    }
    if (vendorField) {
      vendorField.querySelector('input').required = reqVendor;
    }
    var defaultGst = option && option.getAttribute('data-gst') === '1';
    if (defaultGst) {
      form.querySelectorAll('[data-gst]').forEach(function (gstSel) {
        if (parseNum(gstSel.value) === 0) gstSel.value = '18';
      });
      recalcTotals(form.querySelector('[data-expense-lines-body]'));
    }
  }

  function togglePettyCash(form) {
    var source = form.querySelector('[data-payment-source]');
    var wrap = form.querySelector('[data-petty-cash-wrap]');
    if (!source || !wrap) return;
    var show = source.value === 'Petty Cash';
    wrap.hidden = !show;
    var sel = wrap.querySelector('select');
    if (sel) sel.required = show;
  }

  function initExpenseForm() {
    var form = document.querySelector('[data-accounts-expense-form]');
    if (!form) return;
    var tbody = form.querySelector('[data-expense-lines-body]');
    if (!tbody) return;

    tbody.querySelectorAll('[data-expense-line]').forEach(function (row) {
      bindRow(row, tbody);
    });

    form.querySelector('[data-add-line]')?.addEventListener('click', function () {
      var first = tbody.querySelector('[data-expense-line]');
      if (!first) return;
      var clone = first.cloneNode(true);
      clone.querySelectorAll('input').forEach(function (inp) {
        if (inp.name === 'quantity[]') inp.value = '1';
        else if (inp.name === 'rate[]') inp.value = '0';
        else inp.value = '';
      });
      clone.querySelectorAll('[data-taxable],[data-cgst],[data-sgst],[data-igst],[data-line-total]').forEach(function (cell) {
        cell.textContent = '0.00';
      });
      tbody.appendChild(clone);
      bindRow(clone, tbody);
      recalcTotals(tbody);
    });

    form.querySelector('[data-head-select]')?.addEventListener('change', function () {
      applyHeadRules(form);
    });
    form.querySelector('[data-payment-source]')?.addEventListener('change', function () {
      togglePettyCash(form);
    });

    applyHeadRules(form);
    togglePettyCash(form);
    recalcTotals(tbody);
  }

  document.addEventListener('DOMContentLoaded', function () {
    var select = document.querySelector('[data-head-select]');
    var start = function () { initExpenseForm(); };
    if (select && window.MaxekAccounts && window.MaxekAccounts.ensureChartHeadSelect) {
      window.MaxekAccounts.ensureChartHeadSelect(select).finally(start);
    } else {
      start();
    }
  });
})();
