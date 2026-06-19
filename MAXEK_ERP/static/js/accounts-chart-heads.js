(function () {
  function filterHeads(heads, accountType) {
    if (!accountType) return heads;
    var want = accountType.toLowerCase();
    return heads.filter(function (h) {
      return String(h.account_type || '').toLowerCase() === want;
    });
  }

  function populateHeadSelect(select, heads, placeholder) {
    if (!select || !heads || !heads.length) return false;
    var current = select.value;
    select.innerHTML = '';
    var blank = document.createElement('option');
    blank.value = '';
    blank.textContent = placeholder || 'Select Head of Account';
    select.appendChild(blank);
    heads.forEach(function (h) {
      var opt = document.createElement('option');
      opt.value = String(h.id);
      opt.textContent = (h.code || '') + ' \u2014 ' + (h.name || '');
      opt.setAttribute('data-req-project', h.requires_project ? '1' : '0');
      opt.setAttribute('data-req-vendor', h.requires_vendor ? '1' : '0');
      opt.setAttribute('data-gst', h.default_gst_applicable ? '1' : '0');
      select.appendChild(opt);
    });
    if (current) select.value = current;
    select.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }

  function readEmbeddedHeads(accountType) {
    var jsonEl = document.getElementById('chart-heads-json');
    if (!jsonEl || !jsonEl.textContent) return [];
    try {
      return filterHeads(JSON.parse(jsonEl.textContent), accountType);
    } catch (err) {
      return [];
    }
  }

  function fetchHeads(accountType) {
    var url = '/api/accounts/chart-heads';
    if (accountType) url += '?account_type=' + encodeURIComponent(accountType);
    return fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) { return data.heads || []; })
      .catch(function () { return []; });
  }

  function ensureChartHeadSelect(select) {
    if (!select || select.options.length > 1) return Promise.resolve(false);
    var accountType = select.getAttribute('data-head-filter') || '';
    var placeholder = select.options[0] ? select.options[0].textContent : 'Select Head of Account';
    var embedded = readEmbeddedHeads(accountType);
    if (populateHeadSelect(select, embedded, placeholder)) return Promise.resolve(true);
    return fetchHeads(accountType).then(function (heads) {
      return populateHeadSelect(select, heads, placeholder);
    });
  }

  function initChartHeadSelects() {
    var selects = document.querySelectorAll('[data-head-select]');
    if (!selects.length) return;
    Promise.all(Array.prototype.map.call(selects, ensureChartHeadSelect)).catch(function () { /* silent */ });
  }

  window.MaxekAccounts = window.MaxekAccounts || {};
  window.MaxekAccounts.ensureChartHeadSelect = ensureChartHeadSelect;
  window.MaxekAccounts.populateHeadSelect = populateHeadSelect;

  document.addEventListener('DOMContentLoaded', initChartHeadSelects);
})();
