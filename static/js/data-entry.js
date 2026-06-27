(function () {
  'use strict';

  function parseNum(value) {
    var n = parseFloat(value);
    return Number.isFinite(n) ? n : 0;
  }

  function isZeroValue(raw) {
    if (raw === '' || raw === null || raw === undefined) return false;
    var n = parseFloat(String(raw).trim());
    return Number.isFinite(n) && n === 0;
  }

  function isNumericInput(el) {
    if (!el || el.readOnly || el.disabled) return false;
    if (el.type === 'number') return true;
    if (el.type === 'text' && el.getAttribute('inputmode') === 'decimal') return true;
    if (el.hasAttribute('data-numeric-input')) return true;
    if (el.hasAttribute('step')) return true;
    if (el.classList && el.classList.contains('erp-field-numeric')) return true;
    return false;
  }

  function syncHasValue(el) {
    if (!el || !el.classList) return;
    el.classList.toggle('has-value', String(el.value || '').trim() !== '');
  }

  function stripNumberFormat(str) {
    return String(str || '').replace(/,/g, '').trim();
  }

  function parseFormattedNum(value) {
    var n = parseFloat(stripNumberFormat(value));
    return Number.isFinite(n) ? n : null;
  }

  function formatIndianNumber(value, decimals) {
    var n = parseFormattedNum(value);
    if (n === null) return '';
    var dec = typeof decimals === 'number' ? decimals : 2;
    var fixed = n.toFixed(dec);
    var parts = fixed.split('.');
    var intPart = parts[0];
    var neg = intPart.charAt(0) === '-';
    if (neg) intPart = intPart.slice(1);
    if (intPart.length <= 3) {
      var shortResult = (neg ? '-' : '') + intPart;
      return dec > 0 ? shortResult + '.' + parts[1] : shortResult;
    }
    var last3 = intPart.slice(-3);
    var rest = intPart.slice(0, -3);
    var grouped = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',');
    var result = (grouped ? grouped + ',' : '') + last3;
    if (neg) result = '-' + result;
    return dec > 0 ? result + '.' + parts[1] : result;
  }

  function formatRate(value) {
    var n = parseFormattedNum(value);
    if (n === null) return '';
    return n.toFixed(2);
  }

  function formatQty(value) {
    var n = parseFormattedNum(value);
    if (n === null) return '';
    return n.toFixed(3);
  }

  function formatKindDecimals(kind) {
    if (kind === 'qty') return 3;
    if (kind === 'rate') return 2;
    return 2;
  }

  function formatElementValue(el, kind) {
    if (!el) return;
    var raw = el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' ? el.value : el.textContent;
    var n = parseFormattedNum(raw);
    if (n === null) return;
    var text = kind === 'qty'
      ? formatQty(n)
      : kind === 'rate'
        ? formatRate(n)
        : formatIndianNumber(n, 2);
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
      el.value = text;
      syncHasValue(el);
    } else {
      el.textContent = text;
    }
  }

  function restoreRawInputValue(el) {
    if (!el || el.readOnly || el.disabled) return;
    var raw = el.dataset.rawValue;
    if (raw !== undefined && raw !== '') {
      el.value = raw;
    } else {
      var n = parseFormattedNum(el.value);
      if (n !== null) el.value = String(n);
    }
    delete el.dataset.rawValue;
    syncHasValue(el);
  }

  function initNumberDisplayFormatting() {
    document.querySelectorAll('[data-format-amount]:not(input):not(textarea), [data-format-rate]:not(input):not(textarea), [data-format-qty]:not(input):not(textarea)').forEach(function (el) {
      var kind = el.hasAttribute('data-format-qty') ? 'qty' : el.hasAttribute('data-format-rate') ? 'rate' : 'amount';
      formatElementValue(el, kind);
    });

    document.querySelectorAll('input[data-format-amount], input[data-format-rate], input[data-format-qty]').forEach(function (el) {
      var kind = el.hasAttribute('data-format-qty') ? 'qty' : el.hasAttribute('data-format-rate') ? 'rate' : 'amount';
      if (String(el.value || '').trim() !== '') formatElementValue(el, kind);

      el.addEventListener('focus', function () {
        restoreRawInputValue(el);
        if (typeof el.select === 'function') {
          try { el.select(); } catch (err) { /* ignore */ }
        }
      });

      el.addEventListener('blur', function () {
        if (String(el.value || '').trim() === '') return;
        var n = parseFormattedNum(el.value);
        if (n === null) return;
        el.dataset.rawValue = String(n);
        formatElementValue(el, kind);
      });
    });

    document.addEventListener('submit', function (event) {
      var form = event.target;
      if (!form || form.tagName !== 'FORM') return;
      form.querySelectorAll('input[data-format-amount], input[data-format-rate], input[data-format-qty]').forEach(function (el) {
        if (el.dataset.rawValue !== undefined && el.dataset.rawValue !== '') {
          el.value = el.dataset.rawValue;
        } else {
          var n = parseFormattedNum(el.value);
          if (n !== null) el.value = String(n);
        }
        delete el.dataset.rawValue;
      });
    }, true);
  }

  /* —— 1. Auto-clear zero on focus —— */
  function initNumericZeroClear() {
    document.addEventListener('focusin', function (event) {
      var el = event.target;
      if (!isNumericInput(el)) return;
      if (!isZeroValue(el.value)) return;
      el.dataset.clearedZero = '1';
      el.value = '';
      syncHasValue(el);
      if (typeof el.select === 'function') {
        try { el.select(); } catch (err) { /* ignore */ }
      }
    }, true);

    document.addEventListener('focusout', function (event) {
      var el = event.target;
      if (!isNumericInput(el)) return;
      if (el.dataset.clearedZero !== '1') return;
      delete el.dataset.clearedZero;
      if (String(el.value || '').trim() === '') {
        el.value = '0';
        syncHasValue(el);
        el.dispatchEvent(new Event('input', { bubbles: true }));
      }
    }, true);
  }

  /* —— 2. Row auto-totals (qty × rate, L × W × D) —— */
  function setCalcValue(el, value) {
    if (!el) return;
    var num = Number.isFinite(value) ? value : 0;
    var text = (Math.round(num * 100) / 100).toFixed(2);
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
      el.value = text;
      syncHasValue(el);
    } else {
      el.textContent = text;
    }
    el.dispatchEvent(new CustomEvent('maxek:calc-updated', { bubbles: true }));
  }

  function recalcRow(row) {
    if (!row) return;
    var qtyEl = row.querySelector('[data-calc-qty]');
    var rateEl = row.querySelector('[data-calc-rate]');
    var amountEl = row.querySelector('[data-calc-amount]');
    if (amountEl && (qtyEl || rateEl)) {
      setCalcValue(amountEl, parseNum(qtyEl && qtyEl.value) * parseNum(rateEl && rateEl.value));
    }

    var lengthEl = row.querySelector('[data-calc-length]');
    var widthEl = row.querySelector('[data-calc-width]');
    var depthEl = row.querySelector('[data-calc-depth]');
    var volumeEl = row.querySelector('[data-calc-volume], [data-calc-product]');
    if (volumeEl && (lengthEl || widthEl || depthEl)) {
      setCalcValue(
        volumeEl,
        parseNum(lengthEl && lengthEl.value)
          * parseNum(widthEl && widthEl.value)
          * parseNum(depthEl && depthEl.value)
      );
    }
  }

  function initAutoTotals() {
    document.addEventListener('input', function (event) {
      var row = event.target.closest('[data-calc-row], tr[data-calc-row]');
      if (!row) return;
      recalcRow(row);
    }, true);

    document.querySelectorAll('[data-calc-row], tr[data-calc-row]').forEach(recalcRow);
  }

  /* —— 3. Excel-style table keyboard navigation —— */
  function tableFocusables(table) {
    return Array.prototype.slice.call(
      table.querySelectorAll(
        'tbody input:not([type="hidden"]):not([readonly]):not([disabled]), '
        + 'tbody select:not([disabled]), '
        + 'tbody textarea:not([readonly]):not([disabled])'
      )
    ).filter(function (el) {
      return el.offsetParent !== null && !el.closest('[hidden]');
    });
  }

  function cellPosition(input) {
    var cell = input.closest('td, th');
    var row = input.closest('tr');
    if (!cell || !row || !row.parentElement) return null;
    return {
      rowIndex: Array.prototype.indexOf.call(row.parentElement.children, row),
      cellIndex: Array.prototype.indexOf.call(row.children, cell),
      table: input.closest('table'),
    };
  }

  function focusTableAt(table, rowIndex, cellIndex) {
    if (!table) return false;
    var body = table.tBodies[0];
    if (!body) return false;
    var row = body.rows[rowIndex];
    if (!row || row.hidden) return false;
    var cell = row.cells[cellIndex];
    if (!cell) return false;
    var target = cell.querySelector(
      'input:not([type="hidden"]):not([readonly]):not([disabled]), '
      + 'select:not([disabled]), textarea:not([readonly]):not([disabled])'
    );
    if (!target) return false;
    target.focus();
    if (isNumericInput(target) && typeof target.select === 'function') {
      try { target.select(); } catch (err) { /* ignore */ }
    }
    return true;
  }

  function moveTableFocus(input, direction) {
    var pos = cellPosition(input);
    if (!pos) return false;
    var table = pos.table;
    if (!table || (!table.hasAttribute('data-entry-table') && !table.classList.contains('erp-table-module'))) {
      return false;
    }
    var body = table.tBodies[0];
    if (!body) return false;

    if (direction === 'next') {
      var list = tableFocusables(table);
      var idx = list.indexOf(input);
      if (idx >= 0 && idx < list.length - 1) {
        list[idx + 1].focus();
        return true;
      }
      return false;
    }

    var rowDelta = direction === 'down' ? 1 : direction === 'up' ? -1 : 0;
    if (!rowDelta) return false;
    var nextRow = pos.rowIndex + rowDelta;
    while (nextRow >= 0 && nextRow < body.rows.length) {
      if (focusTableAt(table, nextRow, pos.cellIndex)) return true;
      nextRow += rowDelta;
    }
    return false;
  }

  function initTableKeyboard() {
    document.addEventListener('keydown', function (event) {
      var el = event.target;
      if (!el || !el.closest('table')) return;
      if (el.tagName !== 'INPUT' && el.tagName !== 'SELECT' && el.tagName !== 'TEXTAREA') return;

      if (event.key === 'Enter' && !event.shiftKey && el.tagName === 'INPUT' && el.type !== 'textarea') {
        if (moveTableFocus(el, 'next')) {
          event.preventDefault();
        }
        return;
      }

      if (event.key === 'ArrowDown') {
        if (moveTableFocus(el, 'down')) event.preventDefault();
        return;
      }

      if (event.key === 'ArrowUp') {
        if (moveTableFocus(el, 'up')) event.preventDefault();
      }
    }, true);
  }

  /* —— 4. Auto-focus first field when a new row is added —— */
  function focusFirstField(row) {
    if (!row) return;
    var first = row.querySelector(
      'input:not([type="hidden"]):not([readonly]):not([disabled]), '
      + 'select:not([disabled]), textarea:not([readonly]):not([disabled])'
    );
    if (!first) return;
    window.setTimeout(function () {
      first.focus();
      if (isNumericInput(first) && typeof first.select === 'function') {
        try { first.select(); } catch (err) { /* ignore */ }
      }
    }, 0);
  }

  function initAutoFocusNewRows() {
    var selectors = [
      '[data-entry-rows]',
      '[data-staff-components]',
      '[data-staff-travel-tiers]',
      '[data-manpower-rows]',
      '[data-boq-rates-body]',
      '[data-bill-submission-rows]',
    ];

    selectors.forEach(function (selector) {
      document.querySelectorAll(selector).forEach(function (container) {
        var observer = new MutationObserver(function (mutations) {
          mutations.forEach(function (mutation) {
            Array.prototype.forEach.call(mutation.addedNodes, function (node) {
              if (!node || node.nodeType !== 1) return;
              var row = null;
              if (node.matches('[data-entry-row], [data-staff-component-row], [data-staff-travel-row], [data-manpower-row], tr')) {
                row = node;
              } else {
                row = node.querySelector('[data-entry-row], [data-staff-component-row], [data-staff-travel-row], [data-manpower-row], tr');
              }
              if (!row || row.hasAttribute('data-manpower-row-template')) return;
              focusFirstField(row);
            });
          });
        });
        observer.observe(container, { childList: true, subtree: false });
      });
    });

    document.addEventListener('click', function (event) {
      var btn = event.target.closest(
        '[data-entry-add-row], [data-manpower-add], [data-staff-add-component], '
        + '[data-staff-add-travel], [data-bill-submission-add], [data-bg-add]'
      );
      if (!btn) return;
      window.setTimeout(function () {
        var container = btn.closest('form') || document;
        var rows = container.querySelectorAll(
          '[data-entry-row]:last-child, [data-staff-component-row]:last-of-type, '
          + '[data-staff-travel-row]:last-of-type, [data-manpower-row]:not([data-manpower-row-template]):last-of-type, '
          + 'tbody tr:last-child'
        );
        if (rows.length) focusFirstField(rows[rows.length - 1]);
      }, 50);
    });
  }

  function initEntryPanelSpacing() {
    document.addEventListener('maxek:entry-opened', function (event) {
      var panel = event.target;
      if (!panel || !panel.classList || !panel.classList.contains('erp-data-entry-panel--wide')) return;
      var first = panel.querySelector(
        'input:not([type="hidden"]):not([readonly]):not([disabled]), '
        + 'select:not([disabled]), textarea:not([readonly]):not([disabled])'
      );
      if (first && typeof first.focus === 'function') {
        window.setTimeout(function () {
          try { first.focus(); } catch (err) { /* ignore */ }
        }, 120);
      }
    });
  }

  function init() {
    initNumericZeroClear();
    initAutoTotals();
    initTableKeyboard();
    initAutoFocusNewRows();
    initNumberDisplayFormatting();
    initEntryPanelSpacing();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.MaxekDataEntry = {
    recalcRow: recalcRow,
    focusFirstField: focusFirstField,
    formatIndianNumber: formatIndianNumber,
    formatRate: formatRate,
    formatQty: formatQty,
    stripNumberFormat: stripNumberFormat,
  };
})();
