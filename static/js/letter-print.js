/* MAXEK letter print screen: print-mode buttons, screen page-gap preview, autoprint. */
(function () {
  "use strict";
  var body = document.body;
  var MM = 96 / 25.4;                       // CSS px per millimetre
  var PAGE = 297 * MM;
  var cs = getComputedStyle(document.documentElement);
  function mm(name, fallback) {
    var v = parseFloat(cs.getPropertyValue(name));
    return (isNaN(v) ? fallback : v) * MM;
  }
  var TOP = mm("--lh-top", 47), BOTTOM = mm("--lh-bottom", 24);

  function setMode(mode) {
    body.classList.toggle("lp-mode-letterhead", mode === "letterhead");
    body.classList.toggle("lp-mode-preprinted", mode === "preprinted");
    document.querySelectorAll("[data-lp-mode]").forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-lp-mode") === mode ? "true" : "false");
    });
    try { history.replaceState(null, "", updateParam(location.href, "mode", mode)); } catch (e) {}
  }
  function updateParam(href, key, value) {
    var u = new URL(href); u.searchParams.set(key, value); u.searchParams.delete("print"); return u.toString();
  }

  // Screen only: push whole blocks past the reserved header/footer of each A4 page so the
  // preview shows where pages break. Print uses the browser's own pagination.
  function clearGaps() {
    document.querySelectorAll("tr.lp-gap").forEach(function (r) { r.remove(); });
  }
  // Phones: scale the 210 mm sheet to the window width (screen only; print is never scaled).
  function fit() {
    var stage = document.getElementById("lp-stage"), sheet = document.querySelector(".lp-sheet");
    if (!stage || !sheet) return;
    var natural = 210 * MM, avail = document.documentElement.clientWidth - 16;
    var scale = Math.min(1, avail / natural);
    if (scale >= 0.999) {
      stage.classList.remove("lp-scaled"); stage.style.width = stage.style.height = "";
      sheet.style.transform = ""; return;
    }
    stage.classList.add("lp-scaled");
    sheet.style.transform = "scale(" + scale + ")";
    stage.style.width = natural * scale + "px";
    stage.style.height = sheet.offsetHeight * scale + 40 + "px";
    stage.style.margin = "8px auto 24px";
  }
  function unfit() {
    var sheet = document.querySelector(".lp-sheet");
    if (sheet) sheet.style.transform = "none";
  }
  function layoutGaps() {
    clearGaps();
    var sheet = document.querySelector(".lp-sheet");
    if (!sheet) return;
    unfit();                                   // measure at natural size
    var base = sheet.getBoundingClientRect().top + window.scrollY;
    var rows = Array.prototype.slice.call(sheet.querySelectorAll("tbody > tr"));
    rows.forEach(function (row) {
      var r = row.getBoundingClientRect();
      var top = r.top + window.scrollY - base, h = r.height;
      var page = Math.floor(top / PAGE);
      var limit = page * PAGE + PAGE - BOTTOM;
      if (h <= PAGE - TOP - BOTTOM && top + h > limit) {
        var gap = document.createElement("tr");
        gap.className = "lp-gap";
        var td = document.createElement("td");
        td.style.height = ((page + 1) * PAGE + TOP - top) + "px";
        gap.appendChild(td);
        row.parentNode.insertBefore(gap, row);
      }
    });
    var count = Math.max(1, Math.ceil((sheet.scrollHeight - 1) / PAGE));
    var el = document.getElementById("lp-pages");
    if (el) el.textContent = count + (count === 1 ? " page" : " pages");
    sheet.style.transform = "";
    fit();
  }

  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-lp-mode]");
    if (!btn) return;
    setMode(btn.getAttribute("data-lp-mode"));
    if (btn.hasAttribute("data-lp-print")) window.print();
  });
  window.addEventListener("beforeprint", clearGaps);
  window.addEventListener("afterprint", layoutGaps);

  var params = new URLSearchParams(location.search);
  var initial = params.get("mode") === "preprinted" ? "preprinted" : "letterhead";
  setMode(initial);
  window.addEventListener("load", function () {
    layoutGaps();
    if (params.get("print") === "1") window.print();
  });
  window.addEventListener("resize", layoutGaps);
})();
