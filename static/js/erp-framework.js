/**
 * MAXEK ERP — shared list toolbar, CRUD selection, filters, exports.
 */
(function () {
  'use strict';

  function moduleUrl(bar, param, recordId, hash) {
    var endpoint = bar.getAttribute('data-module-endpoint') || '';
    if (!endpoint || !recordId) return '';
    var base = '/' + endpoint.replace(/_/g, '-');
    if (window.MAXEK_URL_FOR) {
      try {
        return window.MAXEK_URL_FOR(endpoint, param, recordId, hash);
      } catch (err) {
        /* fall through */
      }
    }
    var url = base + '?' + encodeURIComponent(param) + '=' + encodeURIComponent(recordId);
    if (hash) url += '#' + hash.replace(/^#/, '');
    return url;
  }

  function buildFlaskStyleUrl(endpoint, param, recordId, hash) {
    var path = endpoint.replace(/_/g, '-');
    var url = '/' + path + '?' + param + '=' + recordId;
    if (hash) url += '#' + String(hash).replace(/^#/, '');
    return url;
  }

  function resolveUrl(bar, param, recordId, hash) {
    var endpoint = bar.getAttribute('data-module-endpoint');
    if (!endpoint || !recordId) return '';
    return buildFlaskStyleUrl(endpoint, param, recordId, hash);
  }

  function selectedRow(bar) {
    var table = findCrudTable(bar);
    if (!table) return null;
    return table.querySelector('tbody tr.is-selected[data-record-id]');
  }

  function findCrudTable(bar) {
    var layout = bar.closest('.erp-module-layout') || bar.closest('.module-layout') || document;
    return layout.querySelector('[data-erp-crud-table]');
  }

  function updateCrudButtons(bar) {
    var row = selectedRow(bar);
    var recordId = row ? row.getAttribute('data-record-id') : '';
    var workflow = row ? (row.getAttribute('data-record-workflow') || '') : '';
    var deletable = row ? row.getAttribute('data-record-deletable') === '1' : false;
    bar.querySelectorAll('[data-erp-crud-actions] [data-erp-action]').forEach(function (btn) {
      var action = btn.getAttribute('data-erp-action');
      if (action === 'new') {
        btn.disabled = false;
        return;
      }
      if (!recordId) {
        btn.disabled = true;
        return;
      }
      if (action === 'delete') {
        btn.disabled = !deletable;
        return;
      }
      if (action === 'edit') {
        var editable = row.getAttribute('data-record-editable');
        btn.disabled = editable === '0';
        return;
      }
      btn.disabled = false;
    });
  }

  function selectRow(table, row) {
    table.querySelectorAll('tbody tr.is-selected').forEach(function (tr) {
      tr.classList.remove('is-selected');
    });
    if (row) row.classList.add('is-selected');
    var bar = (table.closest('.erp-module-layout') || table.closest('.module-layout') || document)
      .querySelector('[data-erp-framework]');
    if (bar) updateCrudButtons(bar);
  }

  function initRowSelection() {
    document.querySelectorAll('[data-erp-crud-table]').forEach(function (table) {
      table.querySelectorAll('tbody tr[data-record-id]').forEach(function (row) {
        row.tabIndex = 0;
        row.addEventListener('click', function (e) {
          if (e.target.closest('a, button, input, select, textarea, label')) return;
          selectRow(table, row);
        });
        row.addEventListener('keydown', function (e) {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            selectRow(table, row);
          }
        });
      });
    });
  }

  function appendQuery(url, bar) {
    var form = bar.querySelector('.erp-standard-filter-form');
    if (!form || url.indexOf('?') !== -1) return url;
    var params = new URLSearchParams(new FormData(form));
    var qs = params.toString();
    return qs ? url + '?' + qs : url;
  }

  function handleCrudAction(bar, action) {
    var viewParam = bar.getAttribute('data-view-param') || 'view';
    var editParam = bar.getAttribute('data-edit-param') || 'edit';
    var row = selectedRow(bar);
    var recordId = row ? row.getAttribute('data-record-id') : '';

    if (action === 'new') {
      var trigger = bar.querySelector('[data-erp-add-trigger]');
      var newUrl = bar.getAttribute('data-new-url');
      if (trigger) {
        var selector = trigger.getAttribute('data-erp-add-trigger');
        var el = selector ? document.querySelector(selector) : null;
        if (el) el.click();
        else trigger.click();
      } else if (newUrl) {
        window.location.href = newUrl;
      }
      return;
    }

    if (action === 'refresh') {
      window.location.reload();
      return;
    }

    if (!recordId) return;

    if (action === 'open' || action === 'view') {
      window.location.href = resolveUrl(bar, viewParam, recordId);
      return;
    }

    if (action === 'edit') {
      var editUrl = resolveUrl(bar, editParam, recordId, 'add-project');
      window.location.href = editUrl;
      return;
    }

    if (action === 'delete') {
      var moduleId = bar.getAttribute('data-module-id') || '';
      var deleteTable = bar.getAttribute('data-delete-table') || '';
      var listEndpoint = bar.getAttribute('data-list-endpoint') || bar.getAttribute('data-module-endpoint');
      var deleteBtn = document.querySelector('.js-delete-record[data-record-id="' + recordId + '"]');
      if (deleteBtn) {
        deleteBtn.click();
        return;
      }
      var modal = document.getElementById('delete-modal');
      var form = document.getElementById('delete-form');
      if (!modal || !form) return;
      document.getElementById('delete-record-id').value = recordId;
      document.getElementById('delete-table').value = deleteTable;
      document.getElementById('delete-module-id').value = moduleId;
      document.getElementById('delete-redirect-to').value = listEndpoint || '';
      modal.hidden = false;
    }
  }

  function initToolbarActions() {
    document.querySelectorAll('[data-erp-framework]').forEach(function (bar) {
      updateCrudButtons(bar);
      bar.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-erp-action]');
        if (!btn || btn.disabled) return;
        var action = btn.getAttribute('data-erp-action');
        if (['open', 'view', 'edit', 'delete', 'new', 'refresh'].indexOf(action) === -1) return;
        e.preventDefault();
        handleCrudAction(bar, action);
      });
    });
  }

  function initFilterForms() {
    document.querySelectorAll('[data-erp-filter-form]').forEach(function (form) {
      form.querySelectorAll('select, input[type="date"]').forEach(function (el) {
        el.addEventListener('change', function () {
          if (form.classList.contains('erp-module-toolbar-search-form')) return;
          form.submit();
        });
      });
    });
    document.querySelectorAll('[data-erp-framework] [data-erp-action="excel"]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var bar = btn.closest('[data-erp-framework]');
        var url = bar.getAttribute('data-export-excel-url');
        if (url) {
          window.location.href = appendQuery(url, bar);
        }
      });
    });
    document.querySelectorAll('[data-erp-framework] [data-erp-action="pdf"]').forEach(function (link) {
      link.addEventListener('click', function () {
        var bar = link.closest('[data-erp-framework]');
        var url = bar.getAttribute('data-export-pdf-url') || link.getAttribute('href');
        if (url && bar) {
          link.setAttribute('href', appendQuery(url, bar));
        }
      });
    });
  }

  function initPrintQuery() {
    if (window.location.search.indexOf('print=1') === -1) return;
    setTimeout(function () {
      var target = document.querySelector('[data-erp-crud-table]') || document.querySelector('[data-erp-table]');
      if (target) {
        document.body.classList.add('erp-print-table-only');
        target.classList.add('erp-print-focus');
      }
      window.print();
    }, 500);
  }

  document.addEventListener('DOMContentLoaded', function () {
    initRowSelection();
    initToolbarActions();
    initFilterForms();
    initPrintQuery();
  });
})();
