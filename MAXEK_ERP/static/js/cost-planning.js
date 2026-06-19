(function () {
  function parseNum(value) {
    var n = parseFloat(value);
    return Number.isFinite(n) ? n : 0;
  }

  function boqQty(form) {
    var display = form.querySelector("[data-cp-boq-qty-display]");
    if (!display) return 0;
    var text = (display.textContent || "").trim();
    var match = text.match(/^([\d.]+)/);
    return match ? parseNum(match[1]) : 0;
  }

  function recalcMaterialRow(row, qty) {
    var factor = parseNum(row.querySelector(".cp-factor") && row.querySelector(".cp-factor").value);
    var rate = parseNum(row.querySelector(".cp-rate") && row.querySelector(".cp-rate").value);
    var plannedQty = Math.round(qty * factor * 10000) / 10000;
    var amount = Math.round(plannedQty * rate * 100) / 100;
    var pq = row.querySelector(".cp-planned-qty");
    var pa = row.querySelector(".cp-planned-amt");
    if (pq) pq.value = plannedQty;
    if (pa) pa.value = amount.toFixed(2);
  }

  function recalcHoursRow(row, qty) {
    var hpu = parseNum(row.querySelector(".cp-hpu") && row.querySelector(".cp-hpu").value);
    var rate = parseNum(row.querySelector(".cp-rate") && row.querySelector(".cp-rate").value);
    var hours = Math.round(qty * hpu * 10000) / 10000;
    var amount = Math.round(hours * rate * 100) / 100;
    var ph = row.querySelector(".cp-planned-hrs");
    var pa = row.querySelector(".cp-planned-amt");
    if (ph) ph.value = hours;
    if (pa) pa.value = amount.toFixed(2);
  }

  function recalcAll(form) {
    var qty = boqQty(form);
    form.querySelectorAll("[data-cp-material-row]").forEach(function (row) {
      recalcMaterialRow(row, qty);
    });
    form.querySelectorAll("[data-cp-manpower-row], [data-cp-machinery-row]").forEach(function (row) {
      recalcHoursRow(row, qty);
    });
  }

  function bindRemove(btn) {
    btn.addEventListener("click", function () {
      var row = btn.closest("tr");
      if (row) row.remove();
    });
  }

  function addRow(container, templateHtml, rowAttr) {
    var wrap = document.createElement("tbody");
    wrap.innerHTML = "<tr " + rowAttr + ">" + templateHtml + "</tr>";
    var row = wrap.querySelector("tr");
    container.appendChild(row);
    row.querySelectorAll("[data-cp-remove-row]").forEach(bindRemove);
    return row;
  }

  function loadBoqMasters(projectId, boqSelect, selectedBoq) {
    if (!boqSelect) return;
    boqSelect.innerHTML = '<option value="">Select BOQ</option>';
    if (!projectId) return;
    fetch("/api/projects/" + encodeURIComponent(projectId) + "/boq-items")
      .then(function (r) { return r.json(); })
      .then(function (items) {
        var boqIds = {};
        (items || []).forEach(function (item) {
          if (!item.boq_number || !item.boq_id) return;
          if (boqIds[item.boq_id]) return;
          boqIds[item.boq_id] = item.boq_number;
          var opt = document.createElement("option");
          opt.value = item.boq_id;
          opt.textContent = item.boq_number;
          opt.dataset.boqNumber = item.boq_number;
          if (selectedBoq && String(item.boq_id) === String(selectedBoq)) {
            opt.selected = true;
          }
          boqSelect.appendChild(opt);
        });
      });
  }

  function loadBoqItems(projectId, itemSelect, boqNumber, selectedItem) {
    if (!itemSelect) return;
    itemSelect.innerHTML = '<option value="">Select BOQ item</option>';
    if (!projectId) return;
    fetch("/api/projects/" + encodeURIComponent(projectId) + "/boq-items")
      .then(function (r) { return r.json(); })
      .then(function (items) {
        (items || []).forEach(function (item) {
          if (boqNumber && item.boq_number !== boqNumber) return;
          var opt = document.createElement("option");
          opt.value = item.id;
          opt.textContent = (item.item_code || "BOQ" + item.line_no) + " — " + (item.item_description || "");
          opt.dataset.quantity = item.quantity;
          opt.dataset.unit = item.unit || "";
          opt.dataset.boqId = item.boq_id || "";
          if (selectedItem && String(item.id) === String(selectedItem)) {
            opt.selected = true;
          }
          itemSelect.appendChild(opt);
        });
        if (itemSelect.value) {
          itemSelect.dispatchEvent(new Event("change"));
        }
      });
  }

  function loadDprActuals(boqItemId, hintEl) {
    if (!boqItemId || !hintEl) return;
    fetch("/api/cost-planning/dpr-actuals?boq_item_id=" + encodeURIComponent(boqItemId))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) return;
        hintEl.textContent =
          "DPR actuals (read-only): Qty " + (data.actual_quantity || 0) +
          ", Manpower " + (data.actual_manpower_hours || 0) + " hrs, Equipment " +
          (data.actual_equipment_hours || 0) + " hrs, Progress " +
          (data.actual_progress_percent || 0) + "%";
      })
      .catch(function () {});
  }

  function initCostPlanForm(form) {
    var projectSel = form.querySelector("[data-cp-project-select]");
    var boqSel = form.querySelector("[data-cp-boq-select]");
    var itemSel = form.querySelector("[data-cp-boq-item-select]");
    var qtyDisplay = form.querySelector("[data-cp-boq-qty-display]");
    var hintEl = form.querySelector("[data-cp-dpr-actuals-hint]");

    function syncBoqItems() {
      var boqOpt = boqSel && boqSel.selectedOptions[0];
      var boqNum = boqOpt ? (boqOpt.dataset.boqNumber || boqOpt.textContent) : "";
      loadBoqItems(projectSel && projectSel.value, itemSel, boqNum, itemSel && itemSel.value);
    }

    if (projectSel) {
      projectSel.addEventListener("change", function () {
        loadBoqMasters(projectSel.value, boqSel);
        if (itemSel) itemSel.innerHTML = '<option value="">Select BOQ item</option>';
        if (qtyDisplay) qtyDisplay.textContent = "—";
      });
      if (projectSel.value && boqSel && boqSel.options.length <= 1) {
        loadBoqMasters(projectSel.value, boqSel, boqSel.value);
      }
    }

    if (boqSel) {
      boqSel.addEventListener("change", function () {
        syncBoqItems();
      });
    }

    if (itemSel) {
      itemSel.addEventListener("change", function () {
        var opt = itemSel.selectedOptions[0];
        if (!opt || !opt.value) {
          if (qtyDisplay) qtyDisplay.textContent = "—";
          return;
        }
        if (qtyDisplay) {
          qtyDisplay.textContent = (opt.dataset.quantity || "0") + " " + (opt.dataset.unit || "");
        }
        if (boqSel && opt.dataset.boqId) {
          boqSel.value = opt.dataset.boqId;
        }
        recalcAll(form);
        loadDprActuals(opt.value, hintEl);
        fetch("/api/cost-planning/boq-item/" + encodeURIComponent(opt.value))
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.existing_cost_plan_id && !form.querySelector('input[name="cost_plan_id"]')) {
              hintEl.textContent += " — Cost plan already exists (ID " + data.existing_cost_plan_id + ").";
            }
          })
          .catch(function () {});
      });
      if (itemSel.value) itemSel.dispatchEvent(new Event("change"));
    }

    form.querySelectorAll("[data-cp-remove-row]").forEach(bindRemove);

    form.addEventListener("input", function (e) {
      if (e.target.matches(".cp-factor, .cp-hpu, .cp-rate")) {
        var row = e.target.closest("tr");
        if (!row) return;
        if (row.hasAttribute("data-cp-material-row")) {
          recalcMaterialRow(row, boqQty(form));
        } else {
          recalcHoursRow(row, boqQty(form));
        }
      }
    });

    form.querySelectorAll("[data-cp-equipment-select]").forEach(function (sel) {
      sel.addEventListener("change", function () {
        var opt = sel.selectedOptions[0];
        var row = sel.closest("tr");
        if (!opt || !row) return;
        var rateInp = row.querySelector(".cp-rate");
        var idInp = row.querySelector('input[name="equipment_id[]"]');
        if (rateInp && opt.dataset.hourly) rateInp.value = opt.dataset.hourly;
        if (idInp) idInp.value = opt.dataset.eqId || "";
        recalcHoursRow(row, boqQty(form));
      });
    });

    var addAct = form.querySelector("[data-cp-add-activity]");
    if (addAct) {
      addAct.addEventListener("click", function () {
        var container = form.querySelector("[data-cp-activity-rows]");
        addRow(
          container,
          '<td><input name="activity_name[]" class="boq-input" list="cp-activity-suggestions"></td>' +
            '<td><input name="activity_unit[]" class="boq-input"></td>' +
            '<td><input name="activity_planned_qty[]" type="number" step="0.01" class="boq-input" value="0"></td>' +
            '<td><button type="button" class="erp-btn erp-btn-ghost erp-btn-sm" data-cp-remove-row><i class="fa-solid fa-trash"></i></button></td>',
          'data-cp-activity-row'
        );
      });
    }

    var addMat = form.querySelector("[data-cp-add-material]");
    if (addMat) {
      addMat.addEventListener("click", function () {
        var container = form.querySelector("[data-cp-material-rows]");
        var row = addRow(
          container,
          '<td><input name="material_name[]" class="boq-input"></td>' +
            '<td><input name="material_unit[]" class="boq-input"></td>' +
            '<td><input name="consumption_factor[]" type="number" step="0.0001" class="boq-input cp-factor" value="0"></td>' +
            '<td><input name="material_rate[]" type="number" step="0.01" class="boq-input cp-rate" value="0"></td>' +
            '<td><input type="text" class="boq-input cp-planned-qty" readonly value="0"></td>' +
            '<td><input type="text" class="boq-input cp-planned-amt" readonly value="0"></td>' +
            '<td><input type="hidden" name="material_activity_id[]" value=""><button type="button" class="erp-btn erp-btn-ghost erp-btn-sm" data-cp-remove-row><i class="fa-solid fa-trash"></i></button></td>',
          "data-cp-material-row"
        );
        recalcMaterialRow(row, boqQty(form));
      });
    }

    var addMp = form.querySelector("[data-cp-add-manpower]");
    if (addMp) {
      addMp.addEventListener("click", function () {
        var container = form.querySelector("[data-cp-manpower-rows]");
        var row = addRow(
          container,
          '<td><input name="trade_name[]" class="boq-input"></td>' +
            '<td><input name="planned_manpower[]" type="number" step="0.01" class="boq-input" value="0"></td>' +
            '<td><input name="hours_per_unit[]" type="number" step="0.0001" class="boq-input cp-hpu" value="0"></td>' +
            '<td><input name="labour_rate[]" type="number" step="0.01" class="boq-input cp-rate" value="0"></td>' +
            '<td><input type="text" class="boq-input cp-planned-hrs" readonly value="0"></td>' +
            '<td><input type="text" class="boq-input cp-planned-amt" readonly value="0"></td>' +
            '<td><input type="hidden" name="manpower_activity_id[]" value=""><button type="button" class="erp-btn erp-btn-ghost erp-btn-sm" data-cp-remove-row><i class="fa-solid fa-trash"></i></button></td>',
          "data-cp-manpower-row"
        );
        recalcHoursRow(row, boqQty(form));
      });
    }

    var addMach = form.querySelector("[data-cp-add-machinery]");
    if (addMach) {
      addMach.addEventListener("click", function () {
        var container = form.querySelector("[data-cp-machinery-rows]");
        var row = addRow(
          container,
          '<td><select name="equipment_type[]" class="boq-input"><option value="">Type</option></select>' +
            '<input type="hidden" name="equipment_id[]" value=""></td>' +
            '<td><input name="machinery_hours_per_unit[]" type="number" step="0.0001" class="boq-input cp-hpu" value="0"></td>' +
            '<td><input name="hourly_rate[]" type="number" step="0.01" class="boq-input cp-rate" value="0"></td>' +
            '<td><input type="text" class="boq-input cp-planned-hrs" readonly value="0"></td>' +
            '<td><input type="text" class="boq-input cp-planned-amt" readonly value="0"></td>' +
            '<td><input type="hidden" name="machinery_activity_id[]" value=""><button type="button" class="erp-btn erp-btn-ghost erp-btn-sm" data-cp-remove-row><i class="fa-solid fa-trash"></i></button></td>',
          "data-cp-machinery-row"
        );
        recalcHoursRow(row, boqQty(form));
      });
    }

    recalcAll(form);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.querySelector("[data-cost-plan-form]");
    if (form) initCostPlanForm(form);
  });
})();
