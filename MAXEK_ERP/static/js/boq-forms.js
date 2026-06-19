(function () {
  var DEFAULT_ROW_COUNT = 3;

  function parseNum(value) {
    var n = parseFloat(value);
    return Number.isFinite(n) ? n : 0;
  }

  function formatAmount(n) {
    return parseNum(n).toFixed(2);
  }

  function lineAmount(row) {
    var qty = parseNum(row.querySelector(".boq-qty") && row.querySelector(".boq-qty").value);
    var rate = parseNum(row.querySelector(".boq-rate") && row.querySelector(".boq-rate").value);
    return Math.round(qty * rate * 100) / 100;
  }

  function renumberRows(container) {
    var rows = container.querySelectorAll("[data-boq-row]");
    rows.forEach(function (row, idx) {
      var cell = row.querySelector(".boq-line-no");
      if (cell) cell.textContent = "BOQ" + String(idx + 1);
    });
  }

  function updateBoqNumberPreview(form) {
    var display = form.querySelector("[data-boq-number-display]");
    var select = form.querySelector("[data-boq-project-select]");
    if (!display || !select || form.querySelector('input[name="boq_id"]')) return;
    var projectId = select.value;
    if (!projectId) {
      display.textContent = "Select project";
      return;
    }
    fetch("/api/projects/" + encodeURIComponent(projectId) + "/next-boq-number")
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data && data.next_boq_number) {
          display.textContent = data.next_boq_number;
        }
      })
      .catch(function () {});
  }

  function recalcForm(form) {
    var rows = form.querySelectorAll("[data-boq-row]");
    var grand = 0;
    rows.forEach(function (row) {
      var amount = lineAmount(row);
      var amountInput = row.querySelector(".boq-amount");
      if (amountInput) amountInput.value = formatAmount(amount);
      grand += amount;
    });
    var grandEl = form.querySelector("[data-boq-grand-total]");
    if (grandEl) grandEl.textContent = formatAmount(grand);
  }

  function countRows(container) {
    return container.querySelectorAll("[data-boq-row]").length;
  }

  function cloneRowFromTemplate(template) {
    var clone = template.cloneNode(true);
    clone.hidden = false;
    clone.removeAttribute("data-boq-row-template");
    clone.setAttribute("data-boq-row", "");
    clone.querySelectorAll("input").forEach(function (el) {
      if (el.classList.contains("boq-amount")) {
        el.value = "0.00";
      } else {
        el.value = "";
      }
    });
    clone.querySelectorAll("textarea").forEach(function (el) {
      el.value = "";
    });
    clone.querySelectorAll("select").forEach(function (el) {
      el.selectedIndex = 0;
    });
    return clone;
  }

  function resetBoqLines(form) {
    var container = form.querySelector("[data-boq-rows]");
    var template = form.querySelector("[data-boq-row-template]");
    var addBtn = form.querySelector("[data-boq-add]");
    if (!container || !template) return;

    container.querySelectorAll("[data-boq-row]").forEach(function (row) {
      row.remove();
    });

    for (var i = 0; i < DEFAULT_ROW_COUNT; i += 1) {
      container.appendChild(cloneRowFromTemplate(template));
    }

    renumberRows(container);
    if (addBtn) addBtn.disabled = countRows(container) >= parseInt(form.getAttribute("data-max-lines") || "25", 10);
    recalcForm(form);
  }

  function clearContinueQueryParams() {
    if (!window.history || !window.history.replaceState) return;
    var url = new URL(window.location.href);
    url.searchParams.delete("continue_prompt");
    url.searchParams.delete("saved");
    url.searchParams.delete("project_id");
    window.history.replaceState({}, "", url.pathname + url.hash);
  }

  function initContinuePrompt(form) {
    var modal = document.getElementById("boq-continue-modal");
    if (!modal || modal.hidden) return;

    var dashboardUrl = modal.getAttribute("data-dashboard-url") || "/";
    var yesButtons = modal.querySelectorAll("[data-boq-continue-yes]");
    var noButtons = modal.querySelectorAll("[data-boq-continue-no]");

    yesButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        modal.hidden = true;
        modal.setAttribute("aria-hidden", "true");
        clearContinueQueryParams();
        resetBoqLines(form);
        var projectSelect = form.querySelector('select[name="project_id"]');
        projectSelect?.focus();
        document.getElementById("boq-form")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });

    noButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        window.location.href = dashboardUrl;
      });
    });
  }

  function initBoqForm() {
    var form = document.querySelector("[data-boq-form]");
    if (!form) return;
    var container = form.querySelector("[data-boq-rows]");
    var template = form.querySelector("[data-boq-row-template]");
    var addBtn = form.querySelector("[data-boq-add]");
    var maxLines = parseInt(form.getAttribute("data-max-lines") || "25", 10);

    var syncAddButton = function () {
      if (addBtn) addBtn.disabled = countRows(container) >= maxLines;
    };

    form.addEventListener("input", function (e) {
      if (e.target.matches(".boq-qty, .boq-rate")) {
        recalcForm(form);
      }
    });

    form.addEventListener("change", function (e) {
      if (e.target.matches(".boq-qty, .boq-rate")) {
        recalcForm(form);
      }
    });

    if (addBtn && template && container) {
      addBtn.addEventListener("click", function () {
        if (countRows(container) >= maxLines) return;
        container.appendChild(cloneRowFromTemplate(template));
        renumberRows(container);
        syncAddButton();
        recalcForm(form);
      });

      container.addEventListener("click", function (e) {
        var btn = e.target.closest("[data-boq-remove]");
        if (!btn) return;
        var row = btn.closest("[data-boq-row]");
        if (!row || countRows(container) <= 1) return;
        row.remove();
        renumberRows(container);
        syncAddButton();
        recalcForm(form);
      });
    }

    syncAddButton();
    recalcForm(form);
    initContinuePrompt(form);

    var projectSelect = form.querySelector("[data-boq-project-select]");
    if (projectSelect) {
      projectSelect.addEventListener("change", function () {
        updateBoqNumberPreview(form);
      });
      updateBoqNumberPreview(form);
    }
  }

  document.addEventListener("DOMContentLoaded", initBoqForm);
})();
