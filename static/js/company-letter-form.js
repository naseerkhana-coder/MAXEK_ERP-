/* Company letter form: rich-text body, employee search + autofill. */
(function () {
  "use strict";
  var form = document.getElementById("cl-form");
  if (!form) return;
  var editor = document.getElementById("cl-editor");
  var body = document.getElementById("cl-body");
  var typeSel = document.getElementById("cl-type");
  var offerBody = form.getAttribute("data-offer-body") || "";
  var offerTemplates = {}; // the last offer body we inserted, so we never overwrite typed text

  document.querySelectorAll(".cl-editor-bar [data-cmd]").forEach(function (btn) {
    btn.addEventListener("mousedown", function (e) { e.preventDefault(); });
    btn.addEventListener("click", function () {
      editor.focus();
      document.execCommand(btn.getAttribute("data-cmd"), false, null);
    });
  });
  function sync() { body.value = editor.innerHTML; }
  editor.addEventListener("input", sync);
  form.addEventListener("submit", sync);
  editor.addEventListener("paste", function (e) {          // paste as plain text
    e.preventDefault();
    var text = (e.clipboardData || window.clipboardData).getData("text/plain");
    document.execCommand("insertText", false, text);
  });
  sync();

  function editorIsBlank() { return !editor.textContent.trim(); }
  function setBody(html) { editor.innerHTML = html; sync(); }
  function maybeInsertOffer(html) {
    var untouched = editorIsBlank() || editor.innerHTML === offerTemplates.last;
    if (typeSel.value === "Offer Letter" && untouched) { offerTemplates.last = html; setBody(html); offerTemplates.last = editor.innerHTML; }
  }
  typeSel.addEventListener("change", function () { maybeInsertOffer(offerBody); });

  // Reference number follows the letter date's year only while it is still the suggestion.
  // (The server validates uniqueness either way.)

  var search = document.getElementById("cl-emp-search");
  var results = document.getElementById("cl-emp-results");
  var idField = document.getElementById("cl-employee-id");
  var timer = null;

  function hide() { results.hidden = true; results.innerHTML = ""; }
  function render(list) {
    results.innerHTML = "";
    if (!list.length) { results.innerHTML = '<div style="padding:8px 12px;color:#64748b">No matching employees</div>'; results.hidden = false; return; }
    list.forEach(function (emp) {
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = emp.staff_name + (emp.employee_code ? " (" + emp.employee_code + ")" : "") +
        (emp.designation ? " — " + emp.designation : "") + (emp.status && emp.status !== "Active" ? " [" + emp.status + "]" : "");
      b.addEventListener("click", function () { pick(emp); });
      results.appendChild(b);
    });
    results.hidden = false;
  }
  function pick(emp) {
    hide();
    fetch(form.getAttribute("data-employee-url").replace(/0$/, emp.id), { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (d) {
        idField.value = d.id;
        search.value = d.name + (d.employee_code ? " (" + d.employee_code + ")" : "");
        document.getElementById("cl-rname").value = d.name;
        document.getElementById("cl-rorg").value = d.recipient_org || "";
        if (d.address) document.getElementById("cl-raddr").value = d.address;
        document.getElementById("cl-sal").value = d.salutation;
        offerBody = d.offer_body_html;
        maybeInsertOffer(offerBody);
      })
      .catch(function () { search.setCustomValidity("Could not load that employee."); search.reportValidity(); search.setCustomValidity(""); });
  }
  search.addEventListener("input", function () {
    idField.value = "";                                    // typing again detaches the link
    clearTimeout(timer);
    var q = search.value.trim();
    if (q.length < 2) { hide(); return; }
    timer = setTimeout(function () {
      fetch(form.getAttribute("data-search-url") + "?q=" + encodeURIComponent(q), { credentials: "same-origin", headers: { Accept: "application/json" } })
        .then(function (r) { return r.json(); }).then(function (d) { render(d.employees || []); }).catch(hide);
    }, 200);
  });
  document.addEventListener("click", function (e) { if (!results.contains(e.target) && e.target !== search) hide(); });
})();
