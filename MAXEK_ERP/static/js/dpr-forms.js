(function () {
  var VOLUME_UNITS = { Cum: 1, cum: 1, m3: 1, M3: 1, CUM: 1 };
  var AREA_UNITS = { Sqm: 1, sqm: 1, m2: 1, M2: 1, SQM: 1, Sqft: 1 };
  var STEEL_UNITS = { Kg: 1, kg: 1, MT: 1, mt: 1, Ton: 1, ton: 1, Tonne: 1, tonne: 1 };

  var state = {
    boqItems: [],
    steelShapes: [],
    equipmentMaster: [],
    pendingShapeSelect: null,
  };

  function parseNum(v) {
    var n = parseFloat(v);
    return Number.isFinite(n) ? n : 0;
  }

  function average(vals) {
    var nums = vals.filter(function (v) { return v > 0; });
    if (!nums.length) return 0;
    return nums.reduce(function (a, b) { return a + b; }, 0) / nums.length;
  }

  function unitType(unit) {
    if (VOLUME_UNITS[unit]) return "volume";
    if (AREA_UNITS[unit]) return "area";
    if (STEEL_UNITS[unit]) return "steel";
    return "simple";
  }

  function steelWeightKg(dia, lengthM, bars) {
    if (dia <= 0 || lengthM <= 0 || bars <= 0) return 0;
    return (dia * dia * lengthM * bars) / 162;
  }

  function getForm() {
    return document.querySelector("[data-dpr-form]");
  }

  function syncProjectHidden(form) {
    var idSel = form.querySelector("[data-dpr-project-id]");
    var hidden = form.querySelector("#dpr_project_id_hidden");
    if (hidden && idSel) hidden.value = idSel.value || "";
  }

  function syncProjectDropdowns(form, source) {
    var idSel = form.querySelector("[data-dpr-project-id]");
    var nameSel = form.querySelector("[data-dpr-project-name]");
    if (!idSel || !nameSel) return;
    if (source === "id") {
      nameSel.value = idSel.value;
    } else {
      idSel.value = nameSel.value;
    }
    syncProjectHidden(form);
    loadBoqItems(form, idSel.value);
  }

  function uniqueBoqNumbers(items) {
    var seen = {};
    var list = [];
    items.forEach(function (item) {
      var num = item.boq_number || "";
      if (num && !seen[num]) {
        seen[num] = true;
        list.push(num);
      }
    });
    return list;
  }

  function boqItemsForNumber(boqNumber) {
    return state.boqItems.filter(function (i) { return i.boq_number === boqNumber; });
  }

  function isBillClient(form) {
    var sel = form.querySelector("[data-dpr-bill-client]");
    return sel && sel.value === "yes";
  }

  function updateBillingMode(form) {
    var billYes = isBillClient(form);
    var resourcePanel = form.querySelector("[data-dpr-resource-panel]");
    var costingHidden = form.querySelector("#dpr_for_costing");
    var hintYes = form.querySelector("[data-dpr-hint-yes]");
    var hintNo = form.querySelector("[data-dpr-hint-no]");
    if (resourcePanel) resourcePanel.hidden = billYes;
    if (costingHidden) costingHidden.value = billYes ? "no" : "yes";
    if (hintYes) hintYes.hidden = !billYes;
    if (hintNo) hintNo.hidden = billYes;
    if (!billYes && resourcePanel && !form.querySelector("[data-dpr-manpower-row]")) {
      addManpowerRow(form);
    }
  }

  function fillBoqDropdowns(form) {
    var numSel = form.querySelector("[data-dpr-boq-number]");
    var descSel = form.querySelector("[data-dpr-boq-description]");
    if (!numSel || !descSel) return;

    var numbers = uniqueBoqNumbers(state.boqItems);
    var continueBoq = form.getAttribute("data-continue-boq") || "";

    numSel.innerHTML = '<option value="">Select BOQ Number</option>';
    numbers.forEach(function (num) {
      var opt = document.createElement("option");
      opt.value = num;
      opt.textContent = num;
      if (continueBoq && continueBoq === num) opt.selected = true;
      numSel.appendChild(opt);
    });

    var filterNum = numSel.value || continueBoq;
    fillDescriptionDropdown(form, filterNum);
    numSel.disabled = !state.boqItems.length;
    descSel.disabled = !state.boqItems.length;

    if (filterNum) {
      var matches = boqItemsForNumber(filterNum);
      if (matches.length === 1) selectBoqItem(form, matches[0].id);
    }
  }

  function fillDescriptionDropdown(form, boqNumber) {
    var descSel = form.querySelector("[data-dpr-boq-description]");
    if (!descSel) return;
    descSel.innerHTML = '<option value="">Select BOQ Description</option>';
    state.boqItems.forEach(function (item) {
      if (boqNumber && item.boq_number !== boqNumber) return;
      var opt = document.createElement("option");
      opt.value = item.id;
      opt.textContent = (item.line_no ? item.line_no + ". " : "") + (item.item_description || "—");
      opt.dataset.boqNumber = item.boq_number || "";
      opt.dataset.unit = item.unit || "";
      opt.dataset.description = item.item_description || "";
      descSel.appendChild(opt);
    });
  }

  function selectBoqItem(form, itemId) {
    var item = state.boqItems.find(function (i) { return String(i.id) === String(itemId); });
    if (!item) return;
    var numSel = form.querySelector("[data-dpr-boq-number]");
    var descSel = form.querySelector("[data-dpr-boq-description]");
    var numHidden = form.querySelector("#dpr_boq_number_hidden");
    var descHidden = form.querySelector("#dpr_boq_description_hidden");
    var unitDisplay = form.querySelector("[data-dpr-unit-display]");
    var unitHidden = form.querySelector("#dpr_unit_hidden");
    var boqQtyDisplay = form.querySelector("[data-dpr-boq-qty-display]");

    if (numSel) numSel.value = item.boq_number || "";
    if (descSel) descSel.value = String(item.id);
    if (numHidden) numHidden.value = item.boq_number || "";
    if (descHidden) descHidden.value = item.item_description || "";
    if (unitDisplay) unitDisplay.value = item.unit || "";
    if (unitHidden) unitHidden.value = item.unit || "";
    if (boqQtyDisplay) boqQtyDisplay.value = item.quantity != null ? String(item.quantity) : "";
    showMeasurementPanel(form, item.unit || "");
    showActivitiesPanel(form, true);
    refreshBoqProgress(form);
  }

  function showActivitiesPanel(form, show) {
    var panel = form.querySelector("[data-dpr-activities-panel]");
    if (!panel) return;
    panel.hidden = !show;
    if (show && !panel.querySelector("[data-dpr-activity-row]")) {
      addActivityRow(form);
    }
  }

  function refreshBoqProgress(form) {
    var descSel = form.querySelector("[data-dpr-boq-description]");
    var panel = form.querySelector("[data-dpr-boq-progress-panel]");
    var balanceDisplay = form.querySelector("[data-dpr-balance-qty-display]");
    if (!descSel || !descSel.value || !panel) {
      if (panel) panel.hidden = true;
      if (balanceDisplay) balanceDisplay.value = "";
      return;
    }
    var reportDateInp = form.querySelector("#dpr_report_date");
    var todayQty = parseNum((form.querySelector("[data-dpr-calculated-qty]") || {}).textContent);
    var url = "/api/dpr/boq-progress?boq_item_id=" + encodeURIComponent(descSel.value)
      + "&today_qty=" + encodeURIComponent(String(todayQty));
    if (reportDateInp && reportDateInp.value) {
      url += "&report_date=" + encodeURIComponent(reportDateInp.value);
    }
    fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) return;
        panel.hidden = false;
        var unit = data.unit || "";
        function fmt(v) { return Number(v || 0).toFixed(4) + (unit ? " " + unit : ""); }
        var set = function (sel, val) {
          var el = panel.querySelector(sel);
          if (el) el.textContent = val;
        };
        set("[data-dpr-progress-boq]", fmt(data.boq_quantity));
        set("[data-dpr-progress-today]", fmt(data.today_quantity));
        set("[data-dpr-progress-executed]", fmt(data.projected_executed || data.total_executed));
        set("[data-dpr-progress-balance]", fmt(data.projected_balance != null ? data.projected_balance : data.balance_quantity));
        set("[data-dpr-progress-completion]", (data.projected_completion_percent != null ? data.projected_completion_percent : data.completion_percent) + "%");
        if (balanceDisplay) balanceDisplay.value = fmt(data.balance_quantity);
      });
  }

  function showMeasurementPanel(form, unit) {
    var panel = form.querySelector("[data-dpr-measurement-panel]");
    var vol = form.querySelector("[data-dpr-volume-panel]");
    var area = form.querySelector("[data-dpr-area-panel]");
    var steel = form.querySelector("[data-dpr-steel-panel]");
    var simple = form.querySelector("[data-dpr-simple-panel]");
    var ut = unitType(unit);
    if (!panel) return;
    panel.hidden = !unit;
    if (vol) {
      vol.hidden = ut !== "volume";
      if (ut === "volume") resetDimensionPanel(vol, ut);
    }
    if (area) {
      area.hidden = ut !== "area";
      if (ut === "area") resetDimensionPanel(area, ut);
    }
    if (steel) {
      steel.hidden = ut !== "steel";
      if (ut === "steel" && !steel.querySelector("[data-dpr-steel-line]")) addSteelLine(form);
    }
    if (simple) {
      simple.hidden = ut !== "simple";
      if (ut === "simple" && !simple.querySelector("[data-dpr-simple-row]")) {
        addSimpleMeasurementRow(form);
        addSimpleMeasurementRow(form);
      }
    }
    recalcQuantity(form);
    refreshBoqProgress(form);
  }

  function resetDimensionPanel(panel, ut) {
    panel.querySelectorAll("[data-dpr-readings]").forEach(function (c) { c.innerHTML = ""; });
    var dims = ut === "volume" ? ["length", "width", "depth"] : ["length", "width"];
    dims.forEach(function (dim) {
      var container = panel.querySelector('[data-dpr-readings="' + dim + '"]');
      if (!container) return;
      addReadingRow(container, dim);
      addReadingRow(container, dim);
    });
  }

  function addReadingRow(container, dim) {
    var row = document.createElement("div");
    row.className = "dpr-reading-row";
    row.innerHTML =
      '<input type="number" min="0" step="0.001" data-reading="' + dim + '" placeholder="Enter ' + dim + '">' +
      '<button type="button" class="erp-btn erp-btn-ghost erp-btn-sm" data-remove-reading><i class="fa-solid fa-trash"></i></button>';
    row.querySelector("[data-remove-reading]").addEventListener("click", function () {
      if (container.children.length > 1) row.remove();
      recalcQuantity(getForm());
    });
    row.querySelector("input").addEventListener("input", function () { recalcQuantity(getForm()); });
    container.appendChild(row);
  }

  function activeMeasurementPanel(form) {
    var unit = (form.querySelector("#dpr_unit_hidden") || {}).value || "";
    var ut = unitType(unit);
    if (ut === "volume") return form.querySelector("[data-dpr-volume-panel]");
    if (ut === "area") return form.querySelector("[data-dpr-area-panel]");
    if (ut === "steel") return form.querySelector("[data-dpr-steel-panel]");
    if (ut === "simple") return form.querySelector("[data-dpr-simple-panel]");
    return null;
  }

  function collectReadings(form, dim) {
    var scope = activeMeasurementPanel(form) || form;
    var inputs = scope.querySelectorAll('[data-reading="' + dim + '"]');
    var vals = [];
    inputs.forEach(function (inp) { vals.push(parseNum(inp.value)); });
    return vals;
  }

  function recalcQuantity(form) {
    if (!form) return;
    var unit = (form.querySelector("#dpr_unit_hidden") || {}).value || "";
    var ut = unitType(unit);
    var qty = 0;
    var unitEl = form.querySelector("[data-dpr-calculated-unit]");
    if (unitEl) unitEl.textContent = unit;

    if (ut === "volume") {
      var al = average(collectReadings(form, "length"));
      var aw = average(collectReadings(form, "width"));
      var ad = average(collectReadings(form, "depth"));
      qty = al * aw * ad;
    } else if (ut === "area") {
      qty = average(collectReadings(form, "length")) * average(collectReadings(form, "width"));
    } else if (ut === "steel") {
      form.querySelectorAll("[data-dpr-steel-line]").forEach(function (line) {
        qty += parseNum(line.querySelector("[data-steel-qty]") && line.querySelector("[data-steel-qty]").textContent);
      });
    } else {
      var rows = [];
      form.querySelectorAll("[data-dpr-simple-row]").forEach(function (row) {
        rows.push(parseNum((row.querySelector("[data-simple-qty]") || {}).value));
      });
      var useAverage = form.querySelector("[data-dpr-use-average]") && form.querySelector("[data-dpr-use-average]").checked;
      var positive = rows.filter(function (v) { return v > 0; });
      if (useAverage && positive.length) {
        qty = positive.reduce(function (a, b) { return a + b; }, 0) / positive.length;
      } else {
        qty = rows.reduce(function (a, b) { return a + b; }, 0);
      }
      var totalEl = form.querySelector("[data-dpr-simple-total]");
      var avgEl = form.querySelector("[data-dpr-simple-avg]");
      var total = rows.reduce(function (a, b) { return a + b; }, 0);
      if (totalEl) totalEl.textContent = total.toFixed(4);
      if (avgEl) avgEl.textContent = positive.length ? (total / positive.length).toFixed(4) : "0.0000";
    }

    var el = form.querySelector("[data-dpr-calculated-qty]");
    if (el) el.textContent = qty.toFixed(4);
    refreshBoqProgress(form);
  }

  function recalcSteelLine(line, unit) {
    var dia = parseNum(line.querySelector("[data-steel-dia]") && line.querySelector("[data-steel-dia]").value);
    var bars = parseInt(line.querySelector("[data-steel-bars]") && line.querySelector("[data-steel-bars]").value, 10) || 0;
    var shapeSel = line.querySelector("[data-steel-shape]");
    var formula = "straight";
    var cuttingM = 0;
    if (shapeSel && shapeSel.selectedOptions[0]) {
      formula = shapeSel.selectedOptions[0].dataset.formula || "straight";
    }
    if (formula === "straight") {
      cuttingM = parseNum(line.querySelector("[data-steel-cutting]") && line.querySelector("[data-steel-cutting]").value);
    } else {
      var sides = [];
      line.querySelectorAll("[data-steel-side]").forEach(function (inp) {
        sides.push(parseNum(inp.value));
      });
      var sumMm = sides.filter(function (v) { return v > 0; }).reduce(function (a, b) { return a + b; }, 0);
      cuttingM = sumMm / 1000;
    }
    var kg = steelWeightKg(dia, cuttingM, bars);
    var lineQty = (unit === "MT" || unit === "mt") ? kg / 1000 : kg;
    var qtyEl = line.querySelector("[data-steel-qty]");
    if (qtyEl) qtyEl.textContent = lineQty.toFixed(4);
    recalcQuantity(getForm());
  }

  function addSteelLine(form) {
    var template = form.querySelector("[data-dpr-steel-line-template]");
    var container = form.querySelector("[data-dpr-steel-lines]");
    if (!template || !container) return;
    var line = template.content.cloneNode(true).querySelector("[data-dpr-steel-line]");
    bindSteelLine(form, line);
    container.appendChild(line);
    recalcSteelLine(line, (form.querySelector("#dpr_unit_hidden") || {}).value || "");
  }

  function bindSteelLine(form, line) {
    var unit = (form.querySelector("#dpr_unit_hidden") || {}).value || "";
    line.querySelector("[data-dpr-remove-steel-line]").addEventListener("click", function () {
      line.remove();
      recalcQuantity(form);
    });
    ["data-steel-bars", "data-steel-dia", "data-steel-cutting"].forEach(function (sel) {
      var el = line.querySelector("[" + sel + "]");
      if (el) el.addEventListener("input", function () { recalcSteelLine(line, unit); });
      if (el) el.addEventListener("change", function () { recalcSteelLine(line, unit); });
    });
    var shapeSel = line.querySelector("[data-steel-shape]");
    if (shapeSel) {
      shapeSel.addEventListener("change", function () {
        if (shapeSel.value === "new") {
          state.pendingShapeSelect = shapeSel;
          openShapeModal();
          shapeSel.value = "";
          return;
        }
        var opt = shapeSel.selectedOptions[0];
        var formula = opt ? opt.dataset.formula : "straight";
        var sides = opt ? parseInt(opt.dataset.sides, 10) || 1 : 1;
        var cuttingWrap = line.querySelector("[data-steel-cutting-wrap]");
        var sidesWrap = line.querySelector("[data-steel-sides-wrap]");
        if (cuttingWrap) cuttingWrap.hidden = formula !== "straight";
        if (sidesWrap) {
          sidesWrap.hidden = formula === "straight";
          if (formula !== "straight") buildSteelSides(line, sides);
        }
        recalcSteelLine(line, unit);
      });
    }
    var addSideBtn = line.querySelector("[data-steel-add-side]");
    if (addSideBtn) {
      addSideBtn.addEventListener("click", function () {
        addSteelSideInput(line.querySelector("[data-steel-sides]"));
        recalcSteelLine(line, unit);
      });
    }
  }

  function buildSteelSides(line, count) {
    var container = line.querySelector("[data-steel-sides]");
    if (!container) return;
    container.innerHTML = "";
    for (var i = 0; i < count; i += 1) addSteelSideInput(container);
  }

  function addSteelSideInput(container) {
    var row = document.createElement("div");
    row.className = "dpr-reading-row";
    row.innerHTML =
      '<input type="number" min="0" step="0.1" data-steel-side placeholder="Side mm">' +
      '<button type="button" class="erp-btn erp-btn-ghost erp-btn-sm" data-remove-side><i class="fa-solid fa-trash"></i></button>';
    row.querySelector("input").addEventListener("input", function () {
      recalcSteelLine(container.closest("[data-dpr-steel-line]"), (getForm().querySelector("#dpr_unit_hidden") || {}).value || "");
    });
    row.querySelector("[data-remove-side]").addEventListener("click", function () {
      if (container.children.length > 1) row.remove();
      recalcSteelLine(container.closest("[data-dpr-steel-line]"), (getForm().querySelector("#dpr_unit_hidden") || {}).value || "");
    });
    container.appendChild(row);
  }

  function workerOptionKey(w) {
    var source = w.worker_source || "worker";
    return source + ":" + w.id;
  }

  function parseWorkerOptionKey(key) {
    if (!key) return { id: null, source: "worker" };
    var parts = String(key).split(":");
    if (parts.length === 2) {
      return { id: parseInt(parts[1], 10), source: parts[0] };
    }
    return { id: parseInt(key, 10), source: "worker" };
  }

  function matchTradeOption(tradeSel, designation) {
    if (!tradeSel || !designation) return;
    var trade = String(designation).trim();
    if (!trade) return;
    var found = false;
    Array.prototype.forEach.call(tradeSel.options, function (opt) {
      if (opt.value && opt.value.toLowerCase() === trade.toLowerCase()) found = true;
    });
    if (found) {
      tradeSel.value = trade;
      return;
    }
    var opt = document.createElement("option");
    opt.value = trade;
    opt.textContent = trade;
    tradeSel.appendChild(opt);
    tradeSel.value = trade;
  }

  function populateWorkerSelects(row, workers) {
    var idSel = row.querySelector("[data-mp-worker-id]");
    var nameSel = row.querySelector("[data-mp-worker-name]");
    if (!idSel || !nameSel) return;

    idSel.innerHTML = '<option value="">Select Worker ID</option>';
    nameSel.innerHTML = '<option value="">Select Worker Name</option>';
    workers.forEach(function (w) {
      var key = workerOptionKey(w);
      var code = w.worker_code || "—";
      var label = w.worker_name || code || ("Worker #" + w.id);

      var idOpt = document.createElement("option");
      idOpt.value = key;
      idOpt.textContent = code;
      idOpt.dataset.workerName = label;
      idOpt.dataset.trade = w.designation || "";
      idOpt.dataset.workerSource = w.worker_source || "worker";
      idOpt.dataset.workerId = String(w.id);
      idSel.appendChild(idOpt);

      var nameOpt = document.createElement("option");
      nameOpt.value = key;
      nameOpt.textContent = label;
      nameOpt.dataset.workerCode = code;
      nameOpt.dataset.trade = w.designation || "";
      nameOpt.dataset.workerSource = w.worker_source || "worker";
      nameOpt.dataset.workerId = String(w.id);
      nameSel.appendChild(nameOpt);
    });

    idSel.disabled = !workers.length;
    nameSel.disabled = !workers.length;
  }

  function syncManpowerWorkerFromId(row) {
    var idSel = row.querySelector("[data-mp-worker-id]");
    var nameSel = row.querySelector("[data-mp-worker-name]");
    var tradeSel = row.querySelector("[data-mp-trade]");
    if (!idSel || !nameSel) return;
    nameSel.value = idSel.value;
    var opt = idSel.selectedOptions[0];
    if (opt && opt.value && tradeSel) matchTradeOption(tradeSel, opt.dataset.trade || "");
    else if (tradeSel && !idSel.value) tradeSel.value = "";
  }

  function syncManpowerWorkerFromName(row) {
    var idSel = row.querySelector("[data-mp-worker-id]");
    var nameSel = row.querySelector("[data-mp-worker-name]");
    var tradeSel = row.querySelector("[data-mp-trade]");
    if (!idSel || !nameSel) return;
    idSel.value = nameSel.value;
    var opt = nameSel.selectedOptions[0];
    if (opt && opt.value && tradeSel) matchTradeOption(tradeSel, opt.dataset.trade || "");
    else if (tradeSel && !nameSel.value) tradeSel.value = "";
  }

  function loadWorkersForRow(row, done) {
    var subSel = row.querySelector("[data-mp-subcontractor]");
    var idSel = row.querySelector("[data-mp-worker-id]");
    var nameSel = row.querySelector("[data-mp-worker-name]");
    var tradeSel = row.querySelector("[data-mp-trade]");
    if (!idSel || !nameSel) return;

    idSel.innerHTML = '<option value="">Select Worker ID</option>';
    nameSel.innerHTML = '<option value="">Select Worker Name</option>';
    idSel.disabled = true;
    nameSel.disabled = true;
    if (tradeSel) tradeSel.value = "";

    var subId = subSel ? subSel.value : "";
    var url = "/api/dpr/workers" + (subId ? "?subcontractor_id=" + encodeURIComponent(subId) : "");
    fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (rows) {
        populateWorkerSelects(row, rows || []);
        if (typeof done === "function") done(rows || []);
      });
  }

  function addManpowerRow(form) {
    var template = form.querySelector("[data-dpr-manpower-template]");
    var container = form.querySelector("[data-dpr-manpower-rows]");
    if (!template || !container) return;
    var row = template.content.cloneNode(true).querySelector("[data-dpr-manpower-row]");
    var subSel = row.querySelector("[data-mp-subcontractor]");
    var idSel = row.querySelector("[data-mp-worker-id]");
    var nameSel = row.querySelector("[data-mp-worker-name]");
    if (subSel) {
      subSel.addEventListener("change", function () {
        loadWorkersForRow(row);
      });
    }
    if (idSel) {
      idSel.addEventListener("change", function () {
        syncManpowerWorkerFromId(row);
      });
    }
    if (nameSel) {
      nameSel.addEventListener("change", function () {
        syncManpowerWorkerFromName(row);
      });
    }
    row.querySelector("[data-dpr-remove-manpower]").addEventListener("click", function () { row.remove(); });
    container.appendChild(row);
    loadWorkersForRow(row);
  }

  function buildMeasurementPayload(form) {
    var unit = (form.querySelector("#dpr_unit_hidden") || {}).value || "";
    var ut = unitType(unit);
    if (ut === "volume") {
      return {
        lengths: collectReadings(form, "length"),
        widths: collectReadings(form, "width"),
        depths: collectReadings(form, "depth"),
      };
    }
    if (ut === "area") {
      return {
        lengths: collectReadings(form, "length"),
        widths: collectReadings(form, "width"),
      };
    }
    if (ut === "steel") {
      var lines = [];
      form.querySelectorAll("[data-dpr-steel-line]").forEach(function (line) {
        var shapeSel = line.querySelector("[data-steel-shape]");
        var opt = shapeSel && shapeSel.selectedOptions[0];
        var sides = [];
        line.querySelectorAll("[data-steel-side]").forEach(function (inp) { sides.push(inp.value); });
        lines.push({
          description: (line.querySelector("[data-steel-description]") || {}).value || "",
          num_bars: (line.querySelector("[data-steel-bars]") || {}).value || 0,
          diameter_mm: (line.querySelector("[data-steel-dia]") || {}).value || 0,
          shape_id: shapeSel ? shapeSel.value : null,
          formula_type: opt ? opt.dataset.formula : "straight",
          cutting_length: (line.querySelector("[data-steel-cutting]") || {}).value || 0,
          side_measurements: sides,
        });
      });
      return { lines: lines };
    }
    return buildSimpleMeasurementPayload(form);
  }

  function addSimpleMeasurementRow(form) {
    var template = form.querySelector("[data-dpr-simple-row-template]");
    var container = form.querySelector("[data-dpr-simple-rows]");
    if (!template || !container) return;
    var row = template.content.cloneNode(true).querySelector("[data-dpr-simple-row]");
    row.querySelector("[data-dpr-remove-simple-row]").addEventListener("click", function () {
      if (container.children.length > 1) row.remove();
      recalcQuantity(form);
    });
    row.querySelectorAll("[data-simple-qty], [data-simple-description]").forEach(function (inp) {
      inp.addEventListener("input", function () { recalcQuantity(form); });
    });
    container.appendChild(row);
    recalcQuantity(form);
  }

  function addActivityRow(form) {
    var template = form.querySelector("[data-dpr-activity-template]");
    var container = form.querySelector("[data-dpr-activity-rows]");
    if (!template || !container) return;
    var row = template.content.cloneNode(true).querySelector("[data-dpr-activity-row]");
    var actSel = row.querySelector("[data-act-name]");
    var customWrap = row.querySelector("[data-act-custom-wrap]");
    if (actSel) {
      actSel.addEventListener("change", function () {
        if (customWrap) customWrap.hidden = actSel.value !== "__custom__";
        recalcActivityTotal(form);
      });
    }
    row.querySelectorAll("[data-act-qty], [data-act-custom]").forEach(function (inp) {
      inp.addEventListener("input", function () { recalcActivityTotal(form); });
    });
    row.querySelector("[data-dpr-remove-activity]").addEventListener("click", function () { row.remove(); recalcActivityTotal(form); });
    container.appendChild(row);
    recalcActivityTotal(form);
  }

  function recalcActivityTotal(form) {
    var total = 0;
    form.querySelectorAll("[data-dpr-activity-row]").forEach(function (row) {
      total += parseNum((row.querySelector("[data-act-qty]") || {}).value);
    });
    var el = form.querySelector("[data-dpr-activity-total]");
    if (el) el.textContent = total.toFixed(4);
  }

  function buildActivitiesPayload(form) {
    var rows = [];
    form.querySelectorAll("[data-dpr-activity-row]").forEach(function (row) {
      var sel = row.querySelector("[data-act-name]");
      var name = "";
      if (sel && sel.value === "__custom__") {
        name = ((row.querySelector("[data-act-custom]") || {}).value || "").trim();
      } else if (sel) {
        name = sel.value || "";
      }
      var qty = parseNum((row.querySelector("[data-act-qty]") || {}).value);
      if (!name || qty <= 0) return;
      rows.push({ activity_name: name, quantity: qty });
    });
    return rows;
  }

  function buildSimpleMeasurementPayload(form) {
    var rows = [];
    form.querySelectorAll("[data-dpr-simple-row]").forEach(function (row) {
      var desc = ((row.querySelector("[data-simple-description]") || {}).value || "").trim();
      var qty = (row.querySelector("[data-simple-qty]") || {}).value || 0;
      if (!desc && parseNum(qty) <= 0) return;
      rows.push({ description: desc, quantity: qty });
    });
    return {
      rows: rows,
      use_average: !!(form.querySelector("[data-dpr-use-average]") && form.querySelector("[data-dpr-use-average]").checked),
    };
  }

  function buildManpowerPayload(form) {
    var rows = [];
    form.querySelectorAll("[data-dpr-manpower-row]").forEach(function (row) {
      var idSel = row.querySelector("[data-mp-worker-id]");
      var nameSel = row.querySelector("[data-mp-worker-name]");
      var key = (idSel && idSel.value) || (nameSel && nameSel.value) || "";
      var parsed = parseWorkerOptionKey(key);
      var opt = idSel && idSel.selectedOptions[0];
      var workerName = "";
      if (opt && opt.dataset.workerName) workerName = opt.dataset.workerName;
      else if (nameSel && nameSel.selectedOptions[0]) workerName = nameSel.selectedOptions[0].textContent.trim();

      rows.push({
        subcontractor_id: (row.querySelector("[data-mp-subcontractor]") || {}).value || null,
        worker_id: parsed.id,
        worker_source: parsed.source,
        worker_name: workerName,
        trade_name: (row.querySelector("[data-mp-trade]") || {}).value || "",
        hours_worked: (row.querySelector("[data-mp-hours]") || {}).value || 0,
        remarks: (row.querySelector("[data-mp-remarks]") || {}).value || "",
      });
    });
    return rows;
  }

  function addMaterialRow(form) {
    var template = form.querySelector("[data-dpr-material-template]");
    var container = form.querySelector("[data-dpr-materials-rows]");
    if (!template || !container) return;
    var row = template.content.cloneNode(true).querySelector("[data-dpr-material-row]");
    row.querySelector("[data-dpr-remove-material]").addEventListener("click", function () { row.remove(); });
    container.appendChild(row);
  }

  function uniqueEquipmentTypes() {
    var seen = {};
    var types = [];
    state.equipmentMaster.forEach(function (eq) {
      var t = eq.equipment_type || "";
      if (t && !seen[t]) {
        seen[t] = true;
        types.push(t);
      }
    });
    return types.sort();
  }

  function equipmentByRegNo(regNo) {
    return state.equipmentMaster.find(function (eq) { return eq.reg_no === regNo; });
  }

  function equipmentByType(eqType) {
    return state.equipmentMaster.find(function (eq) { return eq.equipment_type === eqType; });
  }

  function populateEquipmentSelects(row) {
    var regSel = row.querySelector("[data-eq-reg-no]");
    var typeSel = row.querySelector("[data-eq-type]");
    if (regSel) {
      regSel.innerHTML = '<option value="">Reg No</option>';
      state.equipmentMaster.forEach(function (eq) {
        var opt = document.createElement("option");
        opt.value = eq.reg_no || "";
        opt.textContent = (eq.reg_no || "—") + " — " + (eq.equipment_name || "");
        regSel.appendChild(opt);
      });
    }
    if (typeSel) {
      typeSel.innerHTML = '<option value="">Equipment Type</option>';
      uniqueEquipmentTypes().forEach(function (t) {
        var opt = document.createElement("option");
        opt.value = t;
        opt.textContent = t;
        typeSel.appendChild(opt);
      });
    }
  }

  function applyEquipmentMaster(row, eq) {
    if (!eq) return;
    var nameInp = row.querySelector("[data-eq-name]");
    var ownerInp = row.querySelector("[data-eq-owner]");
    var regSel = row.querySelector("[data-eq-reg-no]");
    var typeSel = row.querySelector("[data-eq-type]");
    var rateTypeSel = row.querySelector("[data-eq-rate-type]");
    var rateInp = row.querySelector("[data-eq-rate]");
    if (nameInp) nameInp.value = eq.equipment_name || "";
    if (ownerInp) ownerInp.value = eq.owner_type || "";
    if (regSel) regSel.value = eq.reg_no || "";
    if (typeSel) typeSel.value = eq.equipment_type || "";
    if (rateTypeSel && rateInp) {
      if (parseNum(eq.km_rate) > 0 && parseNum(eq.hourly_rate) <= 0) {
        rateTypeSel.value = "km";
        rateInp.value = eq.km_rate;
      } else if (parseNum(eq.trip_rate) > 0 && parseNum(eq.hourly_rate) <= 0) {
        rateTypeSel.value = "trip";
        rateInp.value = eq.trip_rate;
      } else {
        rateTypeSel.value = "hourly";
        rateInp.value = eq.hourly_rate || 0;
      }
      toggleEquipmentRateFields(row);
    }
    recalcEquipmentRow(row);
  }

  function toggleEquipmentRateFields(row) {
    var rateType = (row.querySelector("[data-eq-rate-type]") || {}).value || "hourly";
    var tripsWrap = row.querySelector("[data-eq-trips-wrap]");
    var rateInp = row.querySelector("[data-eq-rate]");
    if (tripsWrap) tripsWrap.hidden = rateType !== "trip";
    if (rateInp) rateInp.readOnly = rateType === "lump_sum" ? false : rateInp.readOnly;
  }

  function recalcEquipmentRow(row) {
    var start = parseNum((row.querySelector("[data-eq-start]") || {}).value);
    var end = parseNum((row.querySelector("[data-eq-end]") || {}).value);
    var worked = Math.max(end - start, 0);
    var workedEl = row.querySelector("[data-eq-worked]");
    if (workedEl) workedEl.textContent = worked.toFixed(2);

    var rateType = (row.querySelector("[data-eq-rate-type]") || {}).value || "hourly";
    var rate = parseNum((row.querySelector("[data-eq-rate]") || {}).value);
    var trips = parseNum((row.querySelector("[data-eq-trips]") || {}).value);
    var amount = 0;
    if (rateType === "hourly") amount = worked * rate;
    else if (rateType === "km") amount = worked * rate;
    else if (rateType === "trip") amount = trips * rate;
    else amount = rate;
    var amountEl = row.querySelector("[data-eq-amount]");
    if (amountEl) amountEl.textContent = amount.toFixed(2);
  }

  function bindEquipmentRow(row) {
    populateEquipmentSelects(row);
    var regSel = row.querySelector("[data-eq-reg-no]");
    var typeSel = row.querySelector("[data-eq-type]");
    if (regSel) {
      regSel.addEventListener("change", function () {
        applyEquipmentMaster(row, equipmentByRegNo(regSel.value));
        if (typeSel) typeSel.value = (equipmentByRegNo(regSel.value) || {}).equipment_type || "";
      });
    }
    if (typeSel) {
      typeSel.addEventListener("change", function () {
        if (!regSel || !regSel.value) applyEquipmentMaster(row, equipmentByType(typeSel.value));
      });
    }
    ["data-eq-start", "data-eq-end", "data-eq-rate", "data-eq-trips"].forEach(function (sel) {
      var el = row.querySelector("[" + sel + "]");
      if (el) el.addEventListener("input", function () { recalcEquipmentRow(row); });
    });
    var rateTypeSel = row.querySelector("[data-eq-rate-type]");
    if (rateTypeSel) {
      rateTypeSel.addEventListener("change", function () {
        toggleEquipmentRateFields(row);
        recalcEquipmentRow(row);
      });
    }
    row.querySelector("[data-dpr-remove-equipment]").addEventListener("click", function () { row.remove(); });
  }

  function loadEquipmentMaster(callback) {
    fetch("/api/dpr/equipment")
      .then(function (r) { return r.json(); })
      .then(function (rows) {
        state.equipmentMaster = rows || [];
        if (callback) callback();
      });
  }

  function addEquipmentRow(form) {
    var template = form.querySelector("[data-dpr-equipment-template]");
    var container = form.querySelector("[data-dpr-equipment-rows]");
    if (!template || !container) return;
    var row = template.content.cloneNode(true).querySelector("[data-dpr-equipment-row]");
    bindEquipmentRow(row);
    container.appendChild(row);
  }

  function buildMaterialsPayload(form) {
    var rows = [];
    form.querySelectorAll("[data-dpr-material-row]").forEach(function (row) {
      var name = ((row.querySelector("[data-mat-name]") || {}).value || "").trim();
      if (!name) return;
      rows.push({
        material_name: name,
        quantity: (row.querySelector("[data-mat-qty]") || {}).value || 0,
        unit: (row.querySelector("[data-mat-unit]") || {}).value || "",
        remarks: (row.querySelector("[data-mat-remarks]") || {}).value || "",
      });
    });
    return rows;
  }

  function buildEquipmentPayload(form) {
    var rows = [];
    form.querySelectorAll("[data-dpr-equipment-row]").forEach(function (row) {
      var name = ((row.querySelector("[data-eq-name]") || {}).value || "").trim();
      var regNo = (row.querySelector("[data-eq-reg-no]") || {}).value || "";
      var eqType = (row.querySelector("[data-eq-type]") || {}).value || "";
      if (!name && !regNo && !eqType) return;
      var start = parseNum((row.querySelector("[data-eq-start]") || {}).value);
      var end = parseNum((row.querySelector("[data-eq-end]") || {}).value);
      var worked = Math.max(end - start, 0);
      rows.push({
        equipment_name: name,
        reg_no: regNo,
        equipment_type: eqType,
        owner_type: (row.querySelector("[data-eq-owner]") || {}).value || "",
        start_reading: start,
        end_reading: end,
        worked_units: worked,
        hours_used: worked,
        rate_type: (row.querySelector("[data-eq-rate-type]") || {}).value || "hourly",
        trips: parseNum((row.querySelector("[data-eq-trips]") || {}).value),
        rate: parseNum((row.querySelector("[data-eq-rate]") || {}).value),
        amount: parseNum((row.querySelector("[data-eq-amount]") || {}).textContent),
        remarks: (row.querySelector("[data-eq-remarks]") || {}).value || "",
      });
    });
    return rows;
  }

  function loadBoqItems(form, projectId, done) {
    state.boqItems = [];
    if (!projectId) {
      fillBoqDropdowns(form);
      showMeasurementPanel(form, "");
      if (typeof done === "function") done();
      return;
    }
    fetch("/api/projects/" + projectId + "/boq-items")
      .then(function (r) { return r.json(); })
      .then(function (items) {
        state.boqItems = items || [];
        fillBoqDropdowns(form);
        var continueBoq = form.getAttribute("data-continue-boq");
        var editBoqNumber = form.getAttribute("data-edit-boq-number");
        var boqToSelect = continueBoq || editBoqNumber;
        if (boqToSelect) {
          var numSel = form.querySelector("[data-dpr-boq-number]");
          if (numSel) numSel.value = boqToSelect;
          fillDescriptionDropdown(form, boqToSelect);
          var matches = boqItemsForNumber(boqToSelect);
          var editBoqItem = form.getAttribute("data-edit-boq-item");
          if (editBoqItem) {
            selectBoqItem(form, editBoqItem);
          } else if (matches.length === 1) {
            selectBoqItem(form, matches[0].id);
          } else if (matches.length > 1) {
            var descId = form.getAttribute("data-continue-boq-item");
            if (descId) selectBoqItem(form, descId);
          }
        }
        if (typeof done === "function") done();
      });
  }

  function openShapeModal() {
    var modal = document.getElementById("dpr-new-shape-modal");
    if (modal) {
      modal.hidden = false;
      modal.setAttribute("aria-hidden", "false");
    }
  }

  function closeShapeModal() {
    var modal = document.getElementById("dpr-new-shape-modal");
    if (modal) {
      modal.hidden = true;
      modal.setAttribute("aria-hidden", "true");
    }
  }

  function saveNewShape() {
    var name = (document.getElementById("dpr_new_shape_name") || {}).value || "";
    var sides = (document.getElementById("dpr_new_shape_sides") || {}).value || "6";
    var formula = (document.getElementById("dpr_new_shape_formula") || {}).value || "perimeter";
    if (!name.trim()) return;
    var body = new FormData();
    body.append("shape_name", name.trim());
    body.append("side_count", sides);
    body.append("formula_type", formula);
    fetch("/api/steel-shapes", { method: "POST", body: body })
      .then(function (r) { return r.json(); })
      .then(function (shape) {
        document.querySelectorAll("[data-steel-shape]").forEach(function (sel) {
          var newOpt = document.createElement("option");
          newOpt.value = shape.id;
          newOpt.textContent = shape.shape_name;
          newOpt.dataset.sides = shape.side_count;
          newOpt.dataset.formula = shape.formula_type;
          var newMarker = sel.querySelector('option[value="new"]');
          if (newMarker) sel.insertBefore(newOpt, newMarker);
          else sel.appendChild(newOpt);
        });
        if (state.pendingShapeSelect) {
          state.pendingShapeSelect.value = String(shape.id);
          state.pendingShapeSelect.dispatchEvent(new Event("change"));
          state.pendingShapeSelect = null;
        }
        closeShapeModal();
      });
  }

  function parseJsonAttr(form, attr, fallback) {
    var raw = form.getAttribute(attr);
    if (!raw) return fallback;
    try {
      return JSON.parse(raw);
    } catch (e) {
      return fallback;
    }
  }

  function fillDimensionReadings(form, dim, values) {
    var panel = activeMeasurementPanel(form);
    if (!panel) return;
    var container = panel.querySelector('[data-dpr-readings="' + dim + '"]');
    if (!container) return;
    container.innerHTML = "";
    var nums = (values && values.length) ? values : [0, 0];
    nums.forEach(function (v) {
      addReadingRow(container, dim);
      var inp = container.lastElementChild && container.lastElementChild.querySelector("input");
      if (inp) inp.value = v;
    });
  }

  function prefillSteelLine(form, lineData) {
    addSteelLine(form);
    var container = form.querySelector("[data-dpr-steel-lines]");
    var line = container && container.lastElementChild;
    if (!line) return;
    var descInp = line.querySelector("[data-steel-description]");
    if (descInp) descInp.value = lineData.description || lineData.line_description || "";
    var barsInp = line.querySelector("[data-steel-bars]");
    if (barsInp) barsInp.value = lineData.num_bars != null ? lineData.num_bars : "";
    var diaSel = line.querySelector("[data-steel-dia]");
    if (diaSel && lineData.diameter_mm != null) diaSel.value = String(lineData.diameter_mm);
    var shapeSel = line.querySelector("[data-steel-shape]");
    if (shapeSel && lineData.shape_id) {
      shapeSel.value = String(lineData.shape_id);
      shapeSel.dispatchEvent(new Event("change"));
    }
    var cuttingInp = line.querySelector("[data-steel-cutting]");
    var cuttingVal = lineData.cutting_length_m != null ? lineData.cutting_length_m : lineData.cutting_length;
    if (cuttingInp && cuttingVal != null) cuttingInp.value = cuttingVal;
    var sides = lineData.side_measurements;
    if (typeof sides === "string") {
      try { sides = JSON.parse(sides); } catch (e) { sides = []; }
    }
    if (Array.isArray(sides) && sides.length) {
      var sidesWrap = line.querySelector("[data-steel-sides-wrap]");
      var sidesContainer = line.querySelector("[data-steel-sides]");
      if (sidesWrap && sidesContainer) {
        sidesWrap.hidden = false;
        sidesContainer.innerHTML = "";
        sides.forEach(function (sideVal) {
          addSteelSideInput(sidesContainer);
          var sideInp = sidesContainer.lastElementChild && sidesContainer.lastElementChild.querySelector("input");
          if (sideInp) sideInp.value = sideVal;
        });
      }
    }
    recalcSteelLine(line, (form.querySelector("#dpr_unit_hidden") || {}).value || "");
  }

  function prefillSimpleRows(form, payload) {
    var container = form.querySelector("[data-dpr-simple-rows]");
    if (!container) return;
    container.innerHTML = "";
    var rows = payload.rows || [];
    if (!rows.length) {
      addSimpleMeasurementRow(form);
      addSimpleMeasurementRow(form);
      return;
    }
    rows.forEach(function (rowData) {
      addSimpleMeasurementRow(form);
      var row = container.lastElementChild;
      if (!row) return;
      var descInp = row.querySelector("[data-simple-description]");
      var qtyInp = row.querySelector("[data-simple-qty]");
      if (descInp) descInp.value = rowData.description || "";
      if (qtyInp) qtyInp.value = rowData.quantity != null ? rowData.quantity : "";
    });
    var useAvg = form.querySelector("[data-dpr-use-average]");
    if (useAvg) useAvg.checked = !!payload.use_average;
  }

  function prefillActivityRows(form, activities) {
    var container = form.querySelector("[data-dpr-activity-rows]");
    if (!container || !activities.length) return;
    container.innerHTML = "";
    activities.forEach(function (act) {
      addActivityRow(form);
      var row = container.lastElementChild;
      if (!row) return;
      var actSel = row.querySelector("[data-act-name]");
      var name = act.activity_name || act.name || "";
      if (actSel) {
        var found = false;
        Array.prototype.forEach.call(actSel.options, function (opt) {
          if (opt.value === name) found = true;
        });
        if (found) {
          actSel.value = name;
        } else {
          actSel.value = "__custom__";
          actSel.dispatchEvent(new Event("change"));
          var customInp = row.querySelector("[data-act-custom]");
          if (customInp) customInp.value = name;
        }
      }
      var qtyInp = row.querySelector("[data-act-qty]");
      if (qtyInp) qtyInp.value = act.quantity != null ? act.quantity : "";
    });
    recalcActivityTotal(form);
  }

  function prefillMaterialRows(form, materials) {
    var container = form.querySelector("[data-dpr-materials-rows]");
    if (!container || !materials.length) return;
    container.innerHTML = "";
    materials.forEach(function (mat) {
      addMaterialRow(form);
      var row = container.lastElementChild;
      if (!row) return;
      var nameInp = row.querySelector("[data-mat-name]");
      var qtyInp = row.querySelector("[data-mat-qty]");
      var unitInp = row.querySelector("[data-mat-unit]");
      var remInp = row.querySelector("[data-mat-remarks]");
      if (nameInp) nameInp.value = mat.material_name || "";
      if (qtyInp) qtyInp.value = mat.quantity != null ? mat.quantity : "";
      if (unitInp) unitInp.value = mat.unit || "";
      if (remInp) remInp.value = mat.remarks || "";
    });
  }

  function prefillEquipmentRows(form, equipment) {
    var container = form.querySelector("[data-dpr-equipment-rows]");
    if (!container || !equipment.length) return;
    container.innerHTML = "";
    equipment.forEach(function (eq) {
      addEquipmentRow(form);
      var row = container.lastElementChild;
      if (!row) return;
      var regSel = row.querySelector("[data-eq-reg-no]");
      if (regSel && eq.reg_no) regSel.value = eq.reg_no;
      if (regSel && eq.reg_no) regSel.dispatchEvent(new Event("change"));
      var typeSel = row.querySelector("[data-eq-type]");
      if (typeSel && eq.equipment_type) typeSel.value = eq.equipment_type;
      var nameInp = row.querySelector("[data-eq-name]");
      if (nameInp && eq.equipment_name) nameInp.value = eq.equipment_name;
      var ownerInp = row.querySelector("[data-eq-owner]");
      if (ownerInp && eq.owner_type) ownerInp.value = eq.owner_type;
      var startInp = row.querySelector("[data-eq-start]");
      if (startInp && eq.start_reading != null) startInp.value = eq.start_reading;
      var endInp = row.querySelector("[data-eq-end]");
      if (endInp && eq.end_reading != null) endInp.value = eq.end_reading;
      var rateTypeSel = row.querySelector("[data-eq-rate-type]");
      if (rateTypeSel && eq.rate_type) {
        rateTypeSel.value = eq.rate_type;
        toggleEquipmentRateFields(row);
      }
      var tripsInp = row.querySelector("[data-eq-trips]");
      if (tripsInp && eq.trips != null) tripsInp.value = eq.trips;
      var rateInp = row.querySelector("[data-eq-rate]");
      if (rateInp && eq.rate != null) rateInp.value = eq.rate;
      var remInp = row.querySelector("[data-eq-remarks]");
      if (remInp) remInp.value = eq.remarks || "";
      recalcEquipmentRow(row);
    });
  }

  function selectWorkerOnRow(row, workerId) {
    if (!workerId) return;
    var idSel = row.querySelector("[data-mp-worker-id]");
    var nameSel = row.querySelector("[data-mp-worker-name]");
    if (!idSel || !nameSel) return;
    var key = null;
    Array.prototype.forEach.call(idSel.options, function (opt) {
      if (opt.dataset.workerId === String(workerId)) key = opt.value;
    });
    if (!key) key = "worker:" + workerId;
    if (Array.prototype.some.call(idSel.options, function (opt) { return opt.value === key; })) {
      idSel.value = key;
      syncManpowerWorkerFromId(row);
    }
  }

  function prefillManpowerRows(form, manpower) {
    var container = form.querySelector("[data-dpr-manpower-rows]");
    if (!container || !manpower.length) return;
    container.innerHTML = "";
    var pending = manpower.length;
    manpower.forEach(function (mp) {
      addManpowerRow(form);
      var row = container.lastElementChild;
      if (!row) return;
      var subSel = row.querySelector("[data-mp-subcontractor]");
      if (subSel && mp.subcontractor_id != null) subSel.value = String(mp.subcontractor_id);
      var tradeSel = row.querySelector("[data-mp-trade]");
      if (tradeSel && mp.trade_name) matchTradeOption(tradeSel, mp.trade_name);
      var hoursInp = row.querySelector("[data-mp-hours]");
      if (hoursInp) hoursInp.value = mp.hours_worked != null ? mp.hours_worked : "";
      var remInp = row.querySelector("[data-mp-remarks]");
      if (remInp) remInp.value = mp.remarks || "";
      loadWorkersForRow(row, function () {
        selectWorkerOnRow(row, mp.worker_id);
        pending -= 1;
      });
    });
  }

  function applyEditPrefill(form) {
    if (!form.getAttribute("data-edit-measurement")) return;

    var billClient = form.getAttribute("data-edit-bill-client");
    if (billClient) {
      var billSel = form.querySelector("[data-dpr-bill-client]");
      if (billSel) billSel.value = billClient;
    }
    var forCosting = form.getAttribute("data-edit-for-costing");
    var costingHidden = form.querySelector("#dpr_for_costing");
    if (costingHidden && forCosting) costingHidden.value = forCosting;
    updateBillingMode(form);

    var payload = parseJsonAttr(form, "data-edit-payload", {});
    var unit = (form.querySelector("#dpr_unit_hidden") || {}).value || "";
    var ut = unitType(unit);

    if (ut === "volume") {
      fillDimensionReadings(form, "length", payload.lengths);
      fillDimensionReadings(form, "width", payload.widths);
      fillDimensionReadings(form, "depth", payload.depths);
    } else if (ut === "area") {
      fillDimensionReadings(form, "length", payload.lengths);
      fillDimensionReadings(form, "width", payload.widths);
    } else if (ut === "steel") {
      var steelContainer = form.querySelector("[data-dpr-steel-lines]");
      if (steelContainer) steelContainer.innerHTML = "";
      var steelLines = payload.lines || parseJsonAttr(form, "data-edit-steel-lines", []);
      if (steelLines.length) {
        steelLines.forEach(function (line) { prefillSteelLine(form, line); });
      } else {
        addSteelLine(form);
      }
    } else {
      prefillSimpleRows(form, payload);
    }

    if (payload.activities && payload.activities.length) {
      showActivitiesPanel(form, true);
      prefillActivityRows(form, payload.activities);
    }
    if (payload.materials && payload.materials.length) {
      prefillMaterialRows(form, payload.materials);
    }
    if (payload.equipment && payload.equipment.length) {
      prefillEquipmentRows(form, payload.equipment);
    }

    var manpower = parseJsonAttr(form, "data-edit-manpower", []);
    if (manpower.length) prefillManpowerRows(form, manpower);

    recalcQuantity(form);
    prepareFormPayload(form);
  }

  function initContinueModal(form) {
    var modal = document.getElementById("dpr-continue-modal");
    if (!modal || modal.hidden) return;
    modal.querySelectorAll("[data-dpr-continue-no]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        modal.hidden = true;
        form.removeAttribute("data-continue-boq");
        form.setAttribute("data-continue-project", "");
        var descSel = form.querySelector("[data-dpr-boq-description]");
        var numSel = form.querySelector("[data-dpr-boq-number]");
        if (descSel) descSel.value = "";
        if (numSel) numSel.value = "";
        showMeasurementPanel(form, "");
      });
    });
    modal.querySelector("[data-dpr-continue-yes]").addEventListener("click", function () {
      modal.hidden = true;
      var projectId = modal.getAttribute("data-continue-project");
      var boqNum = modal.getAttribute("data-continue-boq");
      form.setAttribute("data-continue-project", projectId || "");
      form.setAttribute("data-continue-boq", boqNum || "");
      clearMeasurementFields(form);
      if (projectId) loadBoqItems(form, projectId);
    });
  }

  function clearMeasurementFields(form) {
    form.querySelectorAll("[data-dpr-readings]").forEach(function (c) { c.innerHTML = ""; });
    var steel = form.querySelector("[data-dpr-steel-lines]");
    if (steel) steel.innerHTML = "";
    var simpleRows = form.querySelector("[data-dpr-simple-rows]");
    if (simpleRows) simpleRows.innerHTML = "";
    var ut = unitType((form.querySelector("#dpr_unit_hidden") || {}).value || "");
    if (ut === "steel") addSteelLine(form);
    else if (ut === "volume") resetDimensionPanel(form.querySelector("[data-dpr-volume-panel]"), ut);
    else if (ut === "area") resetDimensionPanel(form.querySelector("[data-dpr-area-panel]"), ut);
    else if (ut === "simple") {
      addSimpleMeasurementRow(form);
      addSimpleMeasurementRow(form);
    }
    recalcQuantity(form);
  }
  function prepareFormPayload(form) {
    syncProjectHidden(form);
    updateBillingMode(form);
    var mpPayload = form.querySelector("[data-dpr-manpower-payload]");
    var mPayload = form.querySelector("[data-dpr-measurement-payload]");
    var matPayload = form.querySelector("[data-dpr-materials-payload]");
    var eqPayload = form.querySelector("[data-dpr-equipment-payload]");
    var actPayload = form.querySelector("[data-dpr-activities-payload]");
    if (mPayload) mPayload.value = JSON.stringify(buildMeasurementPayload(form));
    if (mpPayload) mpPayload.value = JSON.stringify(buildManpowerPayload(form));
    if (matPayload) matPayload.value = JSON.stringify(buildMaterialsPayload(form));
    if (eqPayload) eqPayload.value = JSON.stringify(buildEquipmentPayload(form));
    if (actPayload) actPayload.value = JSON.stringify(buildActivitiesPayload(form));
  }

  function setDprStatus(form, status) {
    var hidden = form.querySelector("#dpr_status");
    if (hidden) hidden.value = status;
  }

  function filterAttachMeasurements() {
    var uploadForm = document.querySelector("[data-dpr-upload-form]");
    if (!uploadForm) return;
    var projectSel = uploadForm.querySelector("#dpr_attach_project");
    var dateInp = uploadForm.querySelector("#dpr_attach_date");
    var measureSel = uploadForm.querySelector("#dpr_attach_measurement");
    if (!measureSel) return;
    var projectId = projectSel ? projectSel.value : "";
    var reportDate = dateInp ? dateInp.value : "";
    Array.prototype.forEach.call(measureSel.options, function (opt, idx) {
      if (idx === 0) {
        opt.hidden = false;
        return;
      }
      var matchProject = !projectId || opt.getAttribute("data-project") === projectId;
      var matchDate = !reportDate || opt.getAttribute("data-date") === reportDate;
      opt.hidden = !(matchProject && matchDate);
    });
  }

  function initDprUploadForm() {
    var uploadForm = document.querySelector("[data-dpr-upload-form]");
    if (!uploadForm) return;
    var dateInp = uploadForm.querySelector("#dpr_attach_date");
    if (dateInp && !dateInp.value) {
      dateInp.value = new Date().toISOString().slice(0, 10);
    }
    var mainForm = getForm();
    var attachProject = uploadForm.querySelector("#dpr_attach_project");
    var attachDate = uploadForm.querySelector("#dpr_attach_date");
    if (mainForm && attachProject) {
      var mainProject = mainForm.querySelector("[data-dpr-project-id]");
      var mainDate = mainForm.querySelector("#dpr_report_date");
      if (mainProject && mainProject.value && !attachProject.value) attachProject.value = mainProject.value;
      if (mainDate && mainDate.value && attachDate && !attachDate.value) attachDate.value = mainDate.value;
    }
    if (attachProject) attachProject.addEventListener("change", filterAttachMeasurements);
    if (attachDate) attachDate.addEventListener("change", filterAttachMeasurements);
    filterAttachMeasurements();

    if (window.location.hash === "#dpr-site-upload") {
      var uploadSection = document.getElementById("dpr-site-upload");
      if (uploadSection) {
        window.requestAnimationFrame(function () {
          uploadSection.scrollIntoView({ behavior: "smooth", block: "start" });
        });
      }
    }
  }

  function initDprForm() {
    var form = getForm();
    if (!form) return;

    var dateInp = form.querySelector("#dpr_report_date");
    if (dateInp && !dateInp.value) {
      dateInp.value = new Date().toISOString().slice(0, 10);
    }

    form.querySelector("[data-dpr-project-id]").addEventListener("change", function () {
      syncProjectDropdowns(form, "id");
    });
    form.querySelector("[data-dpr-project-name]").addEventListener("change", function () {
      syncProjectDropdowns(form, "name");
    });

    form.querySelector("[data-dpr-boq-number]").addEventListener("change", function () {
      var num = form.querySelector("[data-dpr-boq-number]").value;
      form.querySelector("#dpr_boq_number_hidden").value = num;
      fillDescriptionDropdown(form, num);
      var matches = boqItemsForNumber(num);
      if (matches.length === 1) {
        selectBoqItem(form, matches[0].id);
      } else {
        form.querySelector("[data-dpr-boq-description]").value = "";
        form.querySelector("#dpr_boq_description_hidden").value = "";
        form.querySelector("[data-dpr-unit-display]").value = "";
        form.querySelector("#dpr_unit_hidden").value = "";
        showMeasurementPanel(form, "");
        showActivitiesPanel(form, false);
      }
    });

    form.querySelector("[data-dpr-boq-description]").addEventListener("change", function () {
      var id = form.querySelector("[data-dpr-boq-description]").value;
      selectBoqItem(form, id);
    });

    form.querySelectorAll("[data-dpr-add-reading]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var dim = btn.getAttribute("data-dpr-add-reading");
        var scope = btn.closest("[data-dpr-volume-panel], [data-dpr-area-panel]");
        var container = scope ? scope.querySelector('[data-dpr-readings="' + dim + '"]') : null;
        if (container) addReadingRow(container, dim);
      });
    });

    form.querySelector("[data-dpr-add-steel-line]").addEventListener("click", function () {
      addSteelLine(form);
    });

    var billClientSel = form.querySelector("[data-dpr-bill-client]");
    if (billClientSel) {
      billClientSel.addEventListener("change", function () { updateBillingMode(form); });
      updateBillingMode(form);
    }

    form.querySelector("[data-dpr-add-manpower]").addEventListener("click", function () {
      addManpowerRow(form);
    });

    var addMatBtn = form.querySelector("[data-dpr-add-material]");
    if (addMatBtn) addMatBtn.addEventListener("click", function () { addMaterialRow(form); });

    var addEqBtn = form.querySelector("[data-dpr-add-equipment]");
    if (addEqBtn) addEqBtn.addEventListener("click", function () { addEquipmentRow(form); });

    var addActBtn = form.querySelector("[data-dpr-add-activity]");
    if (addActBtn) addActBtn.addEventListener("click", function () { addActivityRow(form); });

    var addSimpleBtn = form.querySelector("[data-dpr-add-simple-row]");
    if (addSimpleBtn) addSimpleBtn.addEventListener("click", function () { addSimpleMeasurementRow(form); });

    var useAvg = form.querySelector("[data-dpr-use-average]");
    if (useAvg) useAvg.addEventListener("change", function () { recalcQuantity(form); });

    if (dateInp) dateInp.addEventListener("change", function () { refreshBoqProgress(form); });

    form.querySelectorAll("[data-dpr-set-status]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        setDprStatus(form, btn.getAttribute("data-dpr-set-status") || "submitted");
        prepareFormPayload(form);
      });
    });

    var saveMpBtn = form.querySelector("[data-dpr-save-manpower]");
    if (saveMpBtn) {
      saveMpBtn.addEventListener("click", function () {
        prepareFormPayload(form);
        var count = form.querySelectorAll("[data-dpr-manpower-row]").length;
        window.alert(count ? (count + " manpower row(s) ready — submit DPR to save.") : "Add at least one worker row.");
      });
    }

    var saveEqBtn = form.querySelector("[data-dpr-save-equipment]");
    if (saveEqBtn) {
      saveEqBtn.addEventListener("click", function () {
        prepareFormPayload(form);
        var count = form.querySelectorAll("[data-dpr-equipment-row]").length;
        window.alert(count ? (count + " equipment row(s) ready — submit DPR to save.") : "Add at least one equipment row.");
      });
    }

    form.addEventListener("submit", function () {
      prepareFormPayload(form);
    });

    form.querySelectorAll("[data-dpr-save-measurement], [data-dpr-save-measurement-inline], [data-dpr-save-draft]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var status = btn.getAttribute("data-dpr-set-status") || "submitted";
        setDprStatus(form, status);
        prepareFormPayload(form);
      });
    });

    loadEquipmentMaster(function () {
      var continueProject = form.getAttribute("data-continue-project");
      var editProject = form.getAttribute("data-edit-project");
      var projectToLoad = continueProject || editProject;
      if (projectToLoad) {
        syncProjectHidden(form);
        loadBoqItems(form, projectToLoad, function () {
          applyEditPrefill(form);
        });
      }
    });

    document.querySelectorAll("[data-dpr-shape-cancel]").forEach(function (btn) {
      btn.addEventListener("click", closeShapeModal);
    });
    var shapeSave = document.querySelector("[data-dpr-shape-save]");
    if (shapeSave) shapeSave.addEventListener("click", saveNewShape);

    initContinueModal(form);
    initDprUploadForm();
  }

  document.addEventListener("DOMContentLoaded", initDprForm);
})();
