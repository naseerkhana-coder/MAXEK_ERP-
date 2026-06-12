document.addEventListener('DOMContentLoaded', function () {
  const layout = document.querySelector('.maxek-layout');
  const sidebar = document.querySelector('.tool-rail');
  const toggle = document.querySelector('[data-sidebar-toggle]');
  const overlay = document.querySelector('.sidebar-overlay');

  function closeSidebar() {
    sidebar?.classList.remove('open');
    overlay?.classList.remove('visible');
  }

  toggle?.addEventListener('click', function () {
    sidebar?.classList.toggle('open');
    overlay?.classList.toggle('visible');
  });

  overlay?.addEventListener('click', closeSidebar);

  document.querySelectorAll('[data-modal-open]').forEach(function (button) {
    button.addEventListener('click', function () {
      const modal = document.getElementById(button.getAttribute('data-modal-open'));
      if (!modal) return;
      modal.hidden = false;
      const firstField = modal.querySelector('input, select, textarea, button');
      firstField?.focus();
    });
  });

  document.querySelectorAll('[data-modal-close]').forEach(function (control) {
    control.addEventListener('click', function () {
      const modal = control.closest('.erp-modal');
      if (modal) modal.hidden = true;
    });
  });

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    document.querySelectorAll('.erp-modal:not([hidden])').forEach(function (modal) {
      modal.hidden = true;
    });
  });

  document.querySelectorAll('.rail-group').forEach(function (group) {
    group.addEventListener('toggle', function () {
      if (!group.open) return;
      document.querySelectorAll('.rail-group[open]').forEach(function (other) {
        if (other !== group && !other.querySelector('.rail-subbtn.active')) {
          other.open = false;
        }
      });
    });
  });

  document.querySelectorAll('[data-table-search]').forEach(function (input) {
    const panel = input.closest('[data-erp-table]');
    const table = panel?.querySelector('table');
    if (!table) return;
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    input.addEventListener('input', function () {
      const term = input.value.trim().toLowerCase();
      let visible = 0;
      rows.forEach(function (row) {
        const match = row.textContent.toLowerCase().includes(term);
        row.style.display = match ? '' : 'none';
        if (match) visible += 1;
      });
      const info = panel.querySelector('[data-page-info]');
      if (info) {
        info.textContent = term
          ? 'Showing ' + visible + ' matching record' + (visible === 1 ? '' : 's')
          : 'Showing ' + rows.length + ' record' + (rows.length === 1 ? '' : 's');
      }
    });
  });

  document.querySelectorAll('[data-table-export]').forEach(function (button) {
    button.addEventListener('click', function () {
      const panel = button.closest('[data-erp-table]');
      const table = panel?.querySelector('table');
      if (!table) return;
      const rows = Array.from(table.querySelectorAll('tr'))
        .filter(function (row) { return row.style.display !== 'none'; })
        .map(function (row) {
          return Array.from(row.children).map(function (cell) {
            return '"' + cell.textContent.trim().replace(/"/g, '""') + '"';
          }).join(',');
        });
      const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = (button.getAttribute('data-table-export') || 'export') + '.csv';
      link.click();
      URL.revokeObjectURL(link.href);
    });
  });

  document.querySelectorAll('.erp-field input, .erp-field select, .erp-field textarea').forEach(function (field) {
    function sync() {
      field.classList.toggle('has-value', field.value !== '');
    }
    field.addEventListener('input', sync);
    field.addEventListener('change', sync);
    sync();
  });

  const category = document.getElementById('worker_category');
  const subcontractorRow = document.getElementById('subcontractor-row');
  if (category && subcontractorRow) {
    function toggleSubcontractor() {
      subcontractorRow.style.display = category.value === 'Sub Contractor Staff' ? '' : 'none';
    }
    category.addEventListener('change', toggleSubcontractor);
    toggleSubcontractor();
  }
});
