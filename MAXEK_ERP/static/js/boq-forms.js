(function () {
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
      if (cell) cell.textContent = String(idx + 1);
    });
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

    if (addBtn && template && container) {
      addBtn.addEventListener("click", function () {
        if (countRows(container) >= maxLines) return;
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
        clone.querySelectorAll("select").forEach(function (el) {
          el.selectedIndex = 0;
        });
        container.appendChild(clone);
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
  }

  document.addEventListener("DOMContentLoaded", initBoqForm);
})();
