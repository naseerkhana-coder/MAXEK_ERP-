/**
 * MAXEK ERP — shared list toolbar, CRUD selection, filters, exports.
 */
(function () {
  'use strict';

  function getToolbar(root) {
    return root || document.querySelector('[data-erp-standard-toolbar]');
  }

  function findCrudTable(bar) {
    var target = bar.getAttribute('data-table-target');
    if (target) {
      var panel = document.querySelector(target);
      if (panel) {
        return panel.querySelector('table') || panel;
      }
    }
    var layout = bar.closest('.erp-module-layout') || bar.closest('.module-layout') || document;
    return layout.querySelector('[data-erp-crud-table]') || layout.querySelector('[data-erp-table] table');
  }

  function rowRecordId(row) {
    return row.getAttribute('data-record-id') || row.getAttribute('data-erp-row-id');
  }

  function selectedRow(bar) {
    var table = findCrudTable(bar);
    if (!table) return null;
    return table.querySelector('tbody tr.is-selected[data-record-id], tbody tr.is-selected[data-erp-row-id]');
  }

  function buildRecordUrl(bar, param, recordId) {
    var endpoint = bar.getAttribute('data-module-endpoint') || 'projects';
    var path = '/' + endpoint.replace(/_/g, '-');
    var anchor = bar.getAttribute('data-form-anchor') || '';
    var url = path + '?' + encodeURIComponent(param) + '=' + encodeURIComponent(recordId);
    if (param === 'edit' && anchor) {
      url += anchor.startsWith('#') ? anchor : '#' + anchor;
    }
    return url;
  }

  function updateCrudButtons(bar) {
    var row = selectedRow(bar);
    var recordId = row ? rowRecordId(row) : '';
    bar.querySelectorAll('[data-erp-toolbar-action]').forEach(function (btn) {
      var action = btn.getAttribute('data-erp-toolbar-action');
      if (action === 'new' || action === 'refresh' || action === 'export-pdf') {
        btn.disabled = false;
        return;
      }
      if (!recordId) {
        btn.disabled = true;
        return;
      }
      if (action === 'delete') {
        btn.disabled = row.getAttribute('data-record-deletable') !== '1';
        return;
      }
      if (action === 'edit') {
        btn.disabled = row.getAttribute('data-record-editable') === '0';
        return;
      }
      btn.disabled = false;
    });
  }

  function selectRow(table, row) {
    var body = table.tagName === 'TABLE' ? table : table.querySelector('table');
    if (!body) body = table;
    body.querySelectorAll('tbody tr.is-selected').forEach(function (tr) {
      tr.classList.remove('is-selected');
    });
    if (row) row.classList.add('is-selected');
    var bar = getToolbar(
      (table.closest('.erp-module-layout') || table.closest('.module-layout') || document)
        .querySelector('[data-erp-standard-toolbar]')
    );
    if (bar) updateCrudButtons(bar);
  }

  function initRowSelection() {
    document.querySelectorAll('[data-erp-crud-table], [data-erp-table] table').forEach(function (table) {
      var target = table.matches('table') ? table : table.querySelector('table');
      if (!target) return;
      target.querySelectorAll('tbody tr[data-record-id], tbody tr[data-erp-row-id]').forEach(function (row) {
        row.tabIndex = 0;
        row.addEventListener('click', function (e) {
          if (e.target.closest('a, button, input, select, textarea, label')) return;
          selectRow(target, row);
        });
        row.addEventListener('keydown', function (e) {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            selectRow(target, row);
          }
        });
      });
    });
  }

  function appendFilterQuery(url, bar) {
    var params = new URLSearchParams(window.location.search);
    ['status', 'date_from', 'date_to', 'sort', 'q'].forEach(function (key) {
      if (!params.has(key)) return;
    });
    var qs = params.toString();
    if (!qs) return url;
    return url + (url.indexOf('?') === -1 ? '?' : '&') + qs;
  }

  function handleToolbarAction(bar, action) {
    var row = selectedRow(bar);
    var recordId = row ? rowRecordId(row) : '';

    if (action === 'new') {
      var newUrl = bar.getAttribute('data-new-url');
      if (newUrl) window.location.href = newUrl;
      return;
    }

    if (action === 'refresh') {
      window.location.reload();
      return;
    }

    if (action === 'export-pdf') {
      var pdfUrl = bar.getAttribute('data-export-pdf-url');
      if (pdfUrl) {
        window.open(appendFilterQuery(pdfUrl, bar), '_blank', 'noopener');
        return;
      }
      var printTarget = bar.getAttribute('data-print-target');
      var target = printTarget ? document.querySelector(printTarget) : findCrudTable(bar);
      if (target) {
        document.body.classList.add('erp-print-table-only');
        target.classList.add('erp-print-focus');
      }
      window.print();
      window.addEventListener('afterprint', function cleanup() {
        document.body.classList.remove('erp-print-table-only');
        if (target) target.classList.remove('erp-print-focus');
        window.removeEventListener('afterprint', cleanup);
      });
      return;
    }

    if (!recordId) return;

    if (action === 'open' || action === 'view') {
      window.location.href = buildRecordUrl(bar, 'view', recordId);
      return;
    }

    if (action === 'edit') {
      window.location.href = buildRecordUrl(bar, 'edit', recordId);
      return;
    }

    if (action === 'delete') {
      var existing = document.querySelector('.js-delete-record[data-record-id="' + recordId + '"]');
      if (existing) {
        existing.click();
        return;
      }
      var modal = document.getElementById('delete-modal');
      if (!modal) return;
      var moduleId = bar.getAttribute('data-module-id') || '';
      var deleteTable = bar.getAttribute('data-delete-table') || '';
      var listUrl = bar.getAttribute('data-list-url') || '';
      document.getElementById('delete-record-id').value = recordId;
      document.getElementById('delete-table').value = deleteTable;
      document.getElementById('delete-module-id').value = moduleId;
      document.getElementById('delete-redirect-to').value = bar.getAttribute('data-module-endpoint') || '';
      modal.hidden = false;
    }
  }

  function initFilterControls() {
    document.querySelectorAll('[data-erp-standard-toolbar]').forEach(function (bar) {
      var status = bar.querySelector('[data-erp-status-filter]');
      var dateFrom = bar.querySelector('[data-erp-date-from]');
      var dateTo = bar.querySelector('[data-erp-date-to]');
      var sort = bar.querySelector('[data-erp-sort]');

      function applyFilters() {
        var params = new URLSearchParams(window.location.search);
        if (status) {
          if (status.value) params.set(status.name || 'status', status.value);
          else params.delete(status.name || 'status');
        }
        if (dateFrom) {
          if (dateFrom.value) params.set(dateFrom.name || 'date_from', dateFrom.value);
          else params.delete(dateFrom.name || 'date_from');
        }
        if (dateTo) {
          if (dateTo.value) params.set(dateTo.name || 'date_to', dateTo.value);
          else params.delete(dateTo.name || 'date_to');
        }
        if (sort && sort.value !== '') {
          params.set(sort.name || 'sort', sort.value);
        } else if (sort) {
          params.delete(sort.name || 'sort');
        }
        var qs = params.toString();
        window.location.href = window.location.pathname + (qs ? '?' + qs : '') + window.location.hash;
      }

      [status, dateFrom, dateTo, sort].forEach(function (el) {
        if (!el) return;
        el.addEventListener('change', applyFilters);
      });

      var exportLink = bar.querySelector('[data-export-excel]');
      if (exportLink && exportLink.tagName === 'A') {
        exportLink.addEventListener('click', function () {
          exportLink.href = appendFilterQuery(exportLink.getAttribute('href'), bar);
        });
      }
    });
  }

  function initToolbarActions() {
    document.querySelectorAll('[data-erp-standard-toolbar]').forEach(function (bar) {
      updateCrudButtons(bar);
      bar.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-erp-toolbar-action]');
        if (!btn || btn.disabled) return;
        e.preventDefault();
        handleToolbarAction(bar, btn.getAttribute('data-erp-toolbar-action'));
      });
    });
  }

  function initPrintOnLoad() {
    if (window.location.search.indexOf('print=1') === -1) return;
    setTimeout(function () {
      window.print();
    }, 400);
  }

  document.addEventListener('DOMContentLoaded', function () {
    initRowSelection();
    initToolbarActions();
    initFilterControls();
    initPrintOnLoad();
  });
})();
