(function () {
  'use strict';

  var shell = document.querySelector('[data-pro-dash-shell]');
  if (!shell) {
    return;
  }

  var sidebarStorageKey = 'maxek-pro-dash-sidebar-collapsed';
  var closedTabsStorageKey = 'maxek-pro-dash-closed-tabs';

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

  function getVisibleTabs() {
    return Array.prototype.filter.call(
      shell.querySelectorAll('[data-pro-dash-tab]'),
      function (tab) {
        return !tab.classList.contains('is-hidden');
      }
    );
  }

  function getClosedTabIds() {
    try {
      var raw = localStorage.getItem(closedTabsStorageKey);
      if (!raw) {
        return [];
      }
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (err) {
      return [];
    }
  }

  function saveClosedTabIds(ids) {
    try {
      localStorage.setItem(closedTabsStorageKey, JSON.stringify(ids));
    } catch (err) {
      /* ignore */
    }
  }

  function activateTab(tab) {
    if (!tab || tab.classList.contains('is-hidden')) {
      return;
    }

    var target = tab.getAttribute('data-pro-dash-tab');
    if (!target) {
      return;
    }

    var tabs = shell.querySelectorAll('[data-pro-dash-tab]');
    var panels = shell.querySelectorAll('[data-pro-dash-panel]');

    tabs.forEach(function (item) {
      var active = item === tab;
      item.classList.toggle('is-active', active);
      item.setAttribute('aria-selected', active ? 'true' : 'false');
    });

    panels.forEach(function (panel) {
      var show = panel.getAttribute('data-pro-dash-panel') === target;
      panel.hidden = !show;
    });
  }

  function closeTab(tab) {
    var tabId = tab.getAttribute('data-pro-dash-tab');
    if (!tabId) {
      return;
    }

    var visibleTabs = getVisibleTabs();
    if (visibleTabs.length <= 1) {
      return;
    }

    var wasActive = tab.classList.contains('is-active');
    tab.classList.add('is-hidden');
    tab.classList.remove('is-active');
    tab.setAttribute('aria-selected', 'false');

    var panel = shell.querySelector('[data-pro-dash-panel="' + tabId + '"]');
    if (panel) {
      panel.hidden = true;
    }

    var closedIds = getClosedTabIds();
    if (closedIds.indexOf(tabId) === -1) {
      closedIds.push(tabId);
      saveClosedTabIds(closedIds);
    }

    if (wasActive) {
      var nextTab = getVisibleTabs()[0];
      if (nextTab) {
        activateTab(nextTab);
      }
    }
  }

  function initLayoutTabs() {
    var tabs = shell.querySelectorAll('[data-pro-dash-tab]');
    if (!tabs.length) {
      return;
    }

    var closedIds = getClosedTabIds();
    tabs.forEach(function (tab) {
      var tabId = tab.getAttribute('data-pro-dash-tab');
      if (tabId && closedIds.indexOf(tabId) !== -1) {
        tab.classList.add('is-hidden');
        tab.classList.remove('is-active');
        tab.setAttribute('aria-selected', 'false');
        var panel = shell.querySelector('[data-pro-dash-panel="' + tabId + '"]');
        if (panel) {
          panel.hidden = true;
        }
      }
    });

    var visibleTabs = getVisibleTabs();
    if (!visibleTabs.length) {
      tabs.forEach(function (tab) {
        tab.classList.remove('is-hidden');
      });
      saveClosedTabIds([]);
      visibleTabs = getVisibleTabs();
    }

    var activeTab = visibleTabs.find(function (tab) {
      return tab.classList.contains('is-active');
    });
    if (!activeTab) {
      activateTab(visibleTabs[0]);
    }

    tabs.forEach(function (tab) {
      tab.addEventListener('click', function (event) {
        if (event.target.closest('.pro-dash-tab-close')) {
          return;
        }
        activateTab(tab);
      });

      var closeBtn = tab.querySelector('.pro-dash-tab-close');
      if (closeBtn) {
        closeBtn.addEventListener('click', function (event) {
          event.preventDefault();
          event.stopPropagation();
          closeTab(tab);
        });
      }
    });
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
