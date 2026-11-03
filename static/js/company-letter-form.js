/* Company letter form: rich-text body, employee search + autofill. */
(function () {
  "use strict";
  var form = document.getElementById("cl-form");
  if (!form) return;
  var editor = document.getElementById("cl-editor");
  var body = document.getElementById("cl-body");
  var factsBtn = document.getElementById("cl-insert-facts");
  var copySel = document.getElementById("cl-copy-from");
  var factsHtml = "";

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
  function appendBody(html) { editor.innerHTML = (editorIsBlank() ? "" : editor.innerHTML) + html; sync(); }

  // "Insert employee details": only facts held on the staff record, added when asked for.
  if (factsBtn) factsBtn.addEventListener("click", function () { if (factsHtml) appendBody(factsHtml); });

  // Start from the content of an earlier letter; asks first if something is already typed.
  copySel.addEventListener("change", function () {
    var id = copySel.value;
    if (!id) return;
    if (!editorIsBlank() && !window.confirm("Replace the current letter body with the content of the selected letter?")) { copySel.value = ""; return; }
    fetch(form.getAttribute("data-copy-url").replace(/0$/, id), { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (d) {
        setBody(d.body_html || "");
        var subj = form.elements.subject;
        if (subj && !subj.value.trim()) subj.value = d.subject || "";
      })
      .catch(function () { window.alert("Could not load that letter."); })
      .then(function () { copySel.value = ""; });
  });

  // Reference number follows the letter date's year only while it is still the suggestion.
  // (The server validates uniqueness either way.)

  var search = document.getElementById("cl-emp-search");
  if (!search) return;                                    // no employee-data access: no autofill
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
        factsHtml = d.facts_html || "";
        factsBtn.disabled = !factsHtml;
        factsBtn.title = factsHtml ? "Add this employee's recorded details to the body" : "No details recorded";
      })
      .catch(function () { search.setCustomValidity("Could not load that employee."); search.reportValidity(); search.setCustomValidity(""); });
  }
  search.addEventListener("input", function () {
    idField.value = "";                                    // typing again detaches the link
    factsHtml = ""; factsBtn.disabled = true;
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
