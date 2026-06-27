(function () {
  'use strict';

  var shell = document.querySelector('[data-pro-dash-shell]');
  if (!shell) {
    return;
  }

  var storageKey = 'maxek-pro-dash-sidebar-collapsed';

  function setSidebarCollapsed(collapsed) {
    shell.classList.toggle('is-sidebar-collapsed', collapsed);
    try {
      localStorage.setItem(storageKey, collapsed ? '1' : '0');
    } catch (err) {
      /* ignore */
    }
  }

  try {
    if (localStorage.getItem(storageKey) === '1') {
      setSidebarCollapsed(true);
    }
  } catch (err) {
    /* ignore */
  }

  var collapseBtn = shell.querySelector('[data-pro-sidebar-collapse]');
  if (collapseBtn) {
    collapseBtn.addEventListener('click', function () {
      setSidebarCollapsed(!shell.classList.contains('is-sidebar-collapsed'));
    });
  }

  var tabs = shell.querySelectorAll('[data-pro-dash-tab]');
  var panels = shell.querySelectorAll('[data-pro-dash-panel]');

  tabs.forEach(function (tab) {
    tab.addEventListener('click', function () {
      var target = tab.getAttribute('data-pro-dash-tab');
      if (!target) {
        return;
      }

      tabs.forEach(function (item) {
        var active = item === tab;
        item.classList.toggle('is-active', active);
        item.setAttribute('aria-selected', active ? 'true' : 'false');
      });

      panels.forEach(function (panel) {
        var show = panel.getAttribute('data-pro-dash-panel') === target;
        panel.hidden = !show;
      });
    });
  });

  shell.querySelectorAll('.pro-dash-range-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var group = btn.closest('.pro-dash-range-tabs');
      if (!group) {
        return;
      }
      group.querySelectorAll('.pro-dash-range-btn').forEach(function (item) {
        item.classList.toggle('is-active', item === btn);
      });
    });
  });

  var searchInput = shell.querySelector('#pro-dash-search');
  if (searchInput) {
    searchInput.addEventListener('click', function () {
      var openBtn = document.querySelector('[data-global-search-open]');
      if (openBtn) {
        openBtn.click();
      }
    });
  }

  var themeBtn = shell.querySelector('.pro-dash-theme-btn');
  if (themeBtn) {
    themeBtn.addEventListener('click', function () {
      var themes = ['command-dark', 'pro-light', 'ultra-color'];
      var current = document.documentElement.getAttribute('data-theme') || 'command-dark';
      var idx = themes.indexOf(current);
      var next = themes[(idx + 1) % themes.length];
      document.documentElement.setAttribute('data-theme', next);
      try {
        localStorage.setItem('maxek-ui-theme', next);
      } catch (err) {
        /* ignore */
      }
    });
  }
})();
