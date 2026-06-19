(function () {
  var form = document.querySelector("[data-staff-bonus-form]");
  if (!form) return;

  function parseNum(v) {
    var n = parseFloat(v);
    return Number.isFinite(n) ? n : 0;
  }

  function el(sel) {
    return form.querySelector(sel);
  }

  function syncMethodPanels() {
    var method = el("[data-bonus-method]").value;
    var perDayWrap = el("[data-bonus-per-day-wrap]");
    var manualWrap = el("[data-bonus-manual-wrap]");
    if (perDayWrap) perDayWrap.hidden = method !== "auto";
    if (manualWrap) manualWrap.hidden = method !== "manual";
    updateCalculatedPreview();
  }

  function updateCalculatedPreview() {
    var method = el("[data-bonus-method]").value;
    var worked = parseNum(el("[data-bonus-worked]").value);
    var perDay = parseNum(el("[data-bonus-per-day]").value);
    var manual = parseNum(el("[data-bonus-manual]").value);
    var calculated = method === "auto" ? perDay * worked : manual;
    calculated = Math.round(calculated * 100) / 100;
    var preview = el("[data-bonus-calculated-preview]");
    var rounded = el("[data-bonus-rounded]");
    if (preview) preview.textContent = calculated.toFixed(2);
    if (rounded && parseNum(rounded.value) <= 0 && calculated > 0) {
      rounded.value = calculated.toFixed(2);
    }
  }

  function applyStats(data) {
    var panel = el("[data-bonus-stats-panel]");
    if (panel) panel.hidden = false;
    el("[data-bonus-worked]").value = data.worked_days;
    el("[data-bonus-leave]").value = data.leave_days;
    el("[data-bonus-ot]").value = data.held_ot_hours;
    var workedDisp = el("[data-bonus-worked-display]");
    var leaveDisp = el("[data-bonus-leave-display]");
    var otDisp = el("[data-bonus-ot-display]");
    if (workedDisp) workedDisp.textContent = data.worked_days;
    if (leaveDisp) leaveDisp.textContent = data.leave_days;
    if (otDisp) otDisp.textContent = data.held_ot_hours;
    var periodLabel = el("[data-bonus-period-label]");
    if (periodLabel) periodLabel.textContent = data.bonus_period || "—";
    var perDay = el("[data-bonus-per-day]");
    if (perDay && data.suggested_per_day_rate > 0) {
      perDay.value = data.suggested_per_day_rate;
    }
    var note = el("[data-bonus-existing-note]");
    if (note) {
      if (data.existing_bonus_id) {
        note.hidden = false;
        note.textContent =
          "Existing bonus for this period (" +
          (data.existing_payment_status || "pending") +
          "). Saving will update the record.";
      } else {
        note.hidden = true;
        note.textContent = "";
      }
    }
    updateCalculatedPreview();
  }

  function loadStats() {
    var staffId = el("[data-bonus-staff]").value;
    var month = el("[data-bonus-month]").value;
    var year = el("[data-bonus-year]").value;
    if (!staffId || !month || !year) {
      alert("Select employee, month, and year.");
      return;
    }
    var url =
      "/api/staff-bonus/attendance-stats?staff_id=" +
      encodeURIComponent(staffId) +
      "&month=" +
      encodeURIComponent(month) +
      "&year=" +
      encodeURIComponent(year);
    fetch(url, { credentials: "same-origin" })
      .then(function (res) {
        return res.json().then(function (body) {
          if (!res.ok) throw new Error(body.error || "Failed to load attendance");
          return body;
        });
      })
      .then(applyStats)
      .catch(function (err) {
        alert(err.message || "Could not load attendance stats.");
      });
  }

  el("[data-bonus-method]").addEventListener("change", syncMethodPanels);
  el("[data-bonus-per-day]").addEventListener("input", updateCalculatedPreview);
  el("[data-bonus-manual]").addEventListener("input", updateCalculatedPreview);
  el("[data-bonus-worked]").addEventListener("change", updateCalculatedPreview);
  var loadBtn = el("[data-bonus-load-stats]");
  if (loadBtn) loadBtn.addEventListener("click", loadStats);

  syncMethodPanels();
})();
