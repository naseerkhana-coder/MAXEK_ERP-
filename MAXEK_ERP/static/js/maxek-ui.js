document.addEventListener('DOMContentLoaded', function () {
  const layout = document.querySelector('.maxek-layout');
  const sidebar = document.querySelector('.tool-rail');
  const toggle = document.querySelector('[data-sidebar-toggle]');
  const overlay = document.querySelector('.sidebar-overlay');
  const subbar = document.getElementById('department-subbar');
  const subbarReopen = document.querySelector('[data-subbar-reopen]');
  const SUBBAR_STORAGE_PREFIX = 'maxek-subbar-collapsed:';
  const LEGACY_SUBBAR_KEY = 'maxek-subbar-collapsed';

  function getSubbarSlug() {
    return subbar ? subbar.getAttribute('data-subbar-key') || subbar.getAttribute('data-subbar-slug') || '' : '';
  }

  function subbarStorageKey(slug) {
    return SUBBAR_STORAGE_PREFIX + (slug || 'default');
  }

  function isSubbarCollapsedForSlug(slug) {
    if (!slug) return false;
    try {
      return sessionStorage.getItem(subbarStorageKey(slug)) === '1';
    } catch (err) {
      return false;
    }
  }

  function setSubbarCollapsed(slug, collapsed) {
    if (!slug) return;
    try {
      if (collapsed) {
        sessionStorage.setItem(subbarStorageKey(slug), '1');
      } else {
        sessionStorage.removeItem(subbarStorageKey(slug));
      }
      sessionStorage.removeItem(LEGACY_SUBBAR_KEY);
    } catch (err) {
      /* ignore storage errors */
    }
  }

  function syncSubbarVisibility() {
    if (!subbar) return;
    const slug = getSubbarSlug();
    const collapsed = isSubbarCollapsedForSlug(slug);
    subbar.classList.toggle('is-collapsed', collapsed);
    if (subbarReopen) {
      subbarReopen.hidden = !collapsed;
      subbarReopen.classList.toggle('is-visible', collapsed);
    }
  }

  function closeSidebar() {
    sidebar?.classList.remove('open');
    overlay?.classList.remove('visible');
    toggle?.setAttribute('aria-expanded', 'false');
    const icon = toggle?.querySelector('i');
    if (icon) {
      icon.classList.remove('fa-xmark');
      icon.classList.add('fa-bars');
    }
  }

  function openSidebar() {
    sidebar?.classList.add('open');
    overlay?.classList.add('visible');
    toggle?.setAttribute('aria-expanded', 'true');
    const icon = toggle?.querySelector('i');
    if (icon) {
      icon.classList.remove('fa-bars');
      icon.classList.add('fa-xmark');
    }
  }

  toggle?.addEventListener('click', function () {
    if (sidebar?.classList.contains('open')) {
      closeSidebar();
    } else {
      openSidebar();
    }
  });

  document.querySelectorAll('[data-sidebar-close]').forEach(function (button) {
    button.addEventListener('click', closeSidebar);
  });

  overlay?.addEventListener('click', closeSidebar);

  document.querySelectorAll('[data-subbar-close]').forEach(function (button) {
    button.addEventListener('click', function () {
      setSubbarCollapsed(getSubbarSlug(), true);
      syncSubbarVisibility();
    });
  });

  subbarReopen?.addEventListener('click', function () {
    setSubbarCollapsed(getSubbarSlug(), false);
    syncSubbarVisibility();
  });

  if (subbar) {
    try {
      sessionStorage.removeItem(LEGACY_SUBBAR_KEY);
    } catch (err) {
      /* ignore storage errors */
    }
    syncSubbarVisibility();
    subbar.querySelectorAll('a.department-subbar-link[data-module-anchor]').forEach(function (link) {
      link.addEventListener('click', function (event) {
        const anchorId = link.getAttribute('data-module-anchor');
        if (!anchorId) return;
        let linkUrl;
        try {
          linkUrl = new URL(link.href, window.location.origin);
        } catch (err) {
          return;
        }
        if (linkUrl.pathname !== window.location.pathname) {
          return;
        }
        const target = document.getElementById(anchorId);
        if (!target) {
          return;
        }
        event.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        history.replaceState(null, '', linkUrl.pathname + linkUrl.search + '#' + anchorId);
        subbar.querySelectorAll('.department-subbar-link').forEach(function (item) {
          item.classList.toggle('active', item === link);
        });
      });
    });
  }

  const datetimeEl = document.getElementById('header-datetime');
  if (datetimeEl) {
    const tz = datetimeEl.getAttribute('data-timezone') || 'Asia/Kolkata';
    const formatter = new Intl.DateTimeFormat('en-IN', {
      timeZone: tz,
      weekday: 'long',
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });

    function refreshHeaderClock() {
      const parts = formatter.formatToParts(new Date());
      const pick = function (type) {
        const part = parts.find(function (item) { return item.type === type; });
        return part ? part.value : '';
      };
      const weekday = pick('weekday');
      const day = pick('day');
      const month = pick('month');
      const year = pick('year');
      const hour = pick('hour');
      const minute = pick('minute');
      datetimeEl.textContent = weekday + ', ' + day + ' ' + month + ' ' + year + ' | ' + hour + ':' + minute;
    }

    refreshHeaderClock();
    window.setInterval(refreshHeaderClock, 30000);
  }

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

  function activateDashView(root, viewName, options) {
    const opts = options || {};
    const normalized = viewName === 'operations' ? 'operations' : 'overview';
    root.querySelectorAll('[data-dash-tab]').forEach(function (tab) {
      const isActive = tab.getAttribute('data-dash-tab') === normalized;
      tab.classList.toggle('active', isActive);
      tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });
    root.querySelectorAll('[data-dash-panel]').forEach(function (panel) {
      const isActive = panel.getAttribute('data-dash-panel') === normalized;
      panel.classList.toggle('active', isActive);
      if (isActive) {
        panel.removeAttribute('hidden');
      } else {
        panel.setAttribute('hidden', '');
      }
    });
    document.querySelectorAll('[data-dash-subbar-anchor]').forEach(function (link) {
      link.classList.toggle('active', link.getAttribute('data-dash-subbar-anchor') === normalized);
    });
    if (opts.updateHash !== false) {
      const nextHash = normalized === 'operations' ? '#operations' : '#overview';
      if (window.location.hash !== nextHash) {
        history.replaceState(null, '', window.location.pathname + window.location.search + nextHash);
      }
    }
  }

  document.querySelectorAll('[data-dash-tabs]').forEach(function (root) {
    root.querySelectorAll('[data-dash-tab]').forEach(function (tab) {
      tab.addEventListener('click', function () {
        activateDashView(root, tab.getAttribute('data-dash-tab') || 'overview');
      });
    });

    root.querySelectorAll('[data-dash-subbar-anchor]').forEach(function (link) {
      link.addEventListener('click', function (event) {
        event.preventDefault();
        const anchor = link.getAttribute('data-dash-subbar-anchor') || 'overview';
        activateDashView(root, anchor, { updateHash: false });
      });
    });

    function syncDashFromHash() {
      const hash = (window.location.hash || '').replace('#', '').toLowerCase();
      const view = hash === 'operations' ? 'operations' : 'overview';
      activateDashView(root, view, { updateHash: hash !== 'operations' && hash !== 'overview' });
    }

    syncDashFromHash();
    window.addEventListener('hashchange', syncDashFromHash);
  });
});
