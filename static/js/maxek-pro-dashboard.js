(function () {
  'use strict';

  var PRO_THEME_STORAGE_KEY = 'maxek_pro_theme';
  var PRO_THEMES = ['midnight', 'business', 'erp-classic'];
  var DEFAULT_PRO_THEME = 'midnight';

  function normalizeProTheme(theme) {
    return PRO_THEMES.indexOf(theme) >= 0 ? theme : DEFAULT_PRO_THEME;
  }

  function getProThemeTarget() {
    return document.body && document.body.classList.contains('pro-dashboard-mode')
      ? document.body
      : null;
  }

  function applyProTheme(theme, options) {
    var opts = options || {};
    var normalized = normalizeProTheme(theme);
    var target = getProThemeTarget();
    if (target) {
      target.setAttribute('data-pro-theme', normalized);
    }
    if (opts.persist !== false) {
      try {
        localStorage.setItem(PRO_THEME_STORAGE_KEY, normalized);
      } catch (err) {
        /* ignore */
      }
    }
    document.querySelectorAll('[data-pro-theme-switcher] [data-pro-theme]').forEach(function (btn) {
      var isActive = btn.getAttribute('data-pro-theme') === normalized;
      btn.classList.toggle('is-active', isActive);
      btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });
    return normalized;
  }

  function initProTheme() {
    var target = getProThemeTarget();
    if (!target) {
      return;
    }
    var initial = DEFAULT_PRO_THEME;
    try {
      var stored = localStorage.getItem(PRO_THEME_STORAGE_KEY);
      if (stored) {
        initial = normalizeProTheme(stored);
      } else {
        initial = normalizeProTheme(
          target.getAttribute('data-pro-theme') ||
            document.documentElement.getAttribute('data-pro-theme-init') ||
            DEFAULT_PRO_THEME
        );
      }
    } catch (err) {
      initial = normalizeProTheme(target.getAttribute('data-pro-theme') || DEFAULT_PRO_THEME);
    }
    applyProTheme(initial, { persist: false });
  }

  function initProThemeSwitcher(root) {
    if (!root) {
      return;
    }
    root.querySelectorAll('[data-pro-theme]').forEach(function (button) {
      button.addEventListener('click', function () {
        applyProTheme(button.getAttribute('data-pro-theme') || DEFAULT_PRO_THEME);
      });
    });
  }

  initProTheme();
  document.querySelectorAll('[data-pro-theme-switcher]').forEach(initProThemeSwitcher);

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

  window.maxekProTheme = {
    apply: applyProTheme,
    get: function () {
      var target = getProThemeTarget();
      return normalizeProTheme(
        (target && target.getAttribute('data-pro-theme')) || DEFAULT_PRO_THEME
      );
    },
    themes: PRO_THEMES.slice()
  };
})();
