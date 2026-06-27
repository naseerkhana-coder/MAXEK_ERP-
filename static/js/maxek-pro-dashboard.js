(function () {
  'use strict';

  var shell = document.querySelector('[data-pro-dash-shell]');
  if (!shell) {
    return;
  }

  var sidebarStorageKey = 'maxek-pro-dash-sidebar-collapsed';
  var layoutStorageKey = 'maxek-pro-dash-layout';
  var legacyClosedTabsKey = 'maxek-pro-dash-closed-tabs';

  function setSidebarCollapsed(collapsed) {
    shell.classList.toggle('is-sidebar-collapsed', collapsed);
    try {
      localStorage.setItem(sidebarStorageKey, collapsed ? '1' : '0');
    } catch (err) {
      /* ignore */
    }
  }

  try {
    if (localStorage.getItem(sidebarStorageKey) === '1') {
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

  var backBtn = shell.querySelector('[data-pro-back]');
  if (backBtn) {
    backBtn.addEventListener('click', function () {
      if (window.history.length > 1) {
        window.history.back();
        return;
      }
      window.location.href = backBtn.getAttribute('data-fallback-url') || '/dashboard';
    });
  }

  var layoutTabs = Array.prototype.slice.call(
    shell.querySelectorAll('[data-pro-dash-tab]')
  );
  var layoutPanels = Array.prototype.slice.call(
    shell.querySelectorAll('[data-pro-dash-panel]')
  );

  function activateLayout(layoutId) {
    if (!layoutId) {
      return;
    }

    var hasPanel = layoutPanels.some(function (panel) {
      return panel.getAttribute('data-pro-dash-panel') === layoutId;
    });
    if (!hasPanel) {
      return;
    }

    layoutTabs.forEach(function (tab) {
      var active = tab.getAttribute('data-pro-dash-tab') === layoutId;
      tab.classList.toggle('is-active', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
    });

    layoutPanels.forEach(function (panel) {
      var show = panel.getAttribute('data-pro-dash-panel') === layoutId;
      panel.hidden = !show;
    });

    try {
      sessionStorage.setItem(layoutStorageKey, layoutId);
    } catch (err) {
      /* ignore */
    }

    if (window.location.hash !== '#' + layoutId) {
      history.replaceState(null, '', '#' + layoutId);
    }
  }

  function initLayoutTabs() {
    if (!layoutTabs.length || !layoutPanels.length) {
      return;
    }

    try {
      localStorage.removeItem(legacyClosedTabsKey);
    } catch (err) {
      /* ignore */
    }

    layoutTabs.forEach(function (tab) {
      tab.classList.remove('is-hidden');
      tab.addEventListener('click', function () {
        activateLayout(tab.getAttribute('data-pro-dash-tab'));
      });
    });

    var initialLayout = 'default';
    var hashLayout = (window.location.hash || '').replace(/^#/, '');
    if (hashLayout && layoutPanels.some(function (panel) {
      return panel.getAttribute('data-pro-dash-panel') === hashLayout;
    })) {
      initialLayout = hashLayout;
    } else {
      try {
        var stored = sessionStorage.getItem(layoutStorageKey);
        if (stored && layoutPanels.some(function (panel) {
          return panel.getAttribute('data-pro-dash-panel') === stored;
        })) {
          initialLayout = stored;
        }
      } catch (err) {
        /* ignore */
      }
    }

    activateLayout(initialLayout);
  }

  initLayoutTabs();

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
