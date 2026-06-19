(function () {
  function calcReceiptGst() {
    var form = document.querySelector('[data-receipt-voucher-form]');
    if (!form) return;
    var taxable = parseFloat(form.querySelector('[data-rv-taxable]').value || '0');
    var pct = parseFloat(form.querySelector('[data-rv-gst-pct]').value || '0');
    var taxType = form.querySelector('[data-rv-tax-type]').value || 'CGST_SGST';
    var grandInput = form.querySelector('[data-rv-grand-total]');
    var hint = form.querySelector('[data-rv-gst-hint]');
    if (!taxable || taxable <= 0) {
      if (grandInput) grandInput.value = '';
      if (hint) hint.textContent = '';
      return;
    }
    var taxTotal = Math.round(taxable * pct) / 100;
    taxTotal = Math.round(taxTotal * 100) / 100;
    var cgst = 0;
    var sgst = 0;
    var igst = 0;
    if (pct > 0) {
      if (taxType === 'IGST') {
        igst = taxTotal;
      } else {
        cgst = Math.round((taxTotal / 2) * 100) / 100;
        sgst = Math.round((taxTotal - cgst) * 100) / 100;
      }
    }
    var grand = Math.round((taxable + cgst + sgst + igst) * 100) / 100;
    if (grandInput) grandInput.value = grand.toFixed(2);
    if (hint) {
      if (pct > 0) {
        hint.textContent = 'CGST ₹' + cgst.toFixed(2) + ' + SGST ₹' + sgst.toFixed(2) +
          (igst > 0 ? ' + IGST ₹' + igst.toFixed(2) : '') + ' = Grand ₹' + grand.toFixed(2);
      } else {
        hint.textContent = 'No GST — grand total equals taxable value.';
      }
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    var form = document.querySelector('[data-receipt-voucher-form]');
    if (!form) return;
    var ready = Promise.resolve();
    var headSelect = form.querySelector('[data-head-select]');
    if (window.MaxekAccounts && window.MaxekAccounts.ensureChartHeadSelect && headSelect) {
      ready = window.MaxekAccounts.ensureChartHeadSelect(headSelect);
    }
    ready.finally(function () {
      ['input', 'change'].forEach(function (evt) {
        form.querySelector('[data-rv-taxable]').addEventListener(evt, calcReceiptGst);
        form.querySelector('[data-rv-gst-pct]').addEventListener(evt, calcReceiptGst);
        form.querySelector('[data-rv-tax-type]').addEventListener(evt, calcReceiptGst);
      });
      calcReceiptGst();
    });
  });
})();
