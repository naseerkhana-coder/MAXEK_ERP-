(function () {
  function showModal(modal) {
    if (!modal) return;
    document.querySelectorAll('.erp-modal').forEach(function (other) {
      if (other !== modal) {
        other.hidden = true;
        other.setAttribute('aria-hidden', 'true');
      }
    });
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
    var firstField = modal.querySelector('input:not([type="hidden"]):not([readonly]), select, textarea');
    if (firstField) firstField.focus();
  }

  function hideModal(modal) {
    if (!modal) return;
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
  }

  function initInlineCreateModals() {
    document.querySelectorAll('[data-open-inline-modal]').forEach(function (btn) {
      var modalId = btn.getAttribute('data-open-inline-modal');
      var modal = modalId ? document.getElementById(modalId) : null;
      if (!modal) return;
      btn.addEventListener('click', function (event) {
        event.preventDefault();
        showModal(modal);
      });
    });

    document.querySelectorAll('[data-inline-create-modal]').forEach(function (modal) {
      modal.querySelectorAll('[data-modal-close]').forEach(function (control) {
        control.addEventListener('click', function (event) {
          event.preventDefault();
          hideModal(modal);
        });
      });
    });
  }

  function applySelectParam(paramName, selector) {
    var params = new URLSearchParams(window.location.search);
    var selected = params.get(paramName);
    if (!selected) return;
    document.querySelectorAll(selector).forEach(function (select) {
      select.value = selected;
      if (select.value === selected) {
        select.classList.add('has-value');
        select.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
    if (window.history.replaceState) {
      params.delete(paramName);
      var query = params.toString();
      var nextUrl = window.location.pathname
        + (query ? '?' + query : '')
        + window.location.hash;
      window.history.replaceState({}, '', nextUrl);
    }
  }

  function scrollToHash() {
    if (!window.location.hash) return;
    var anchor = document.querySelector(window.location.hash);
    if (anchor) {
      window.requestAnimationFrame(function () {
        anchor.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    initInlineCreateModals();
    applySelectParam('select_vendor', '[data-vendor-select]');
    applySelectParam('select_chart_head', '[data-head-select]');
    scrollToHash();
  });
})();
