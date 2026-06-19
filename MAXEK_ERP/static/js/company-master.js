(function () {
  "use strict";

  var INDIA_FIELDS = [
    { key: "pan", label: "PAN", type: "text", required: true },
    { key: "tan", label: "TAN", type: "text" },
    { key: "cin", label: "CIN / Company Registration", type: "text" },
    { key: "msme_reg_no", label: "MSME Registration No.", type: "text" },
    { key: "msme_category", label: "MSME Category", type: "select", options: ["Micro", "Small", "Medium"] },
    { key: "iec_code", label: "IEC Code", type: "text" },
    { key: "pf_establishment_id", label: "PF Establishment ID", type: "text" },
    { key: "esi_establishment_id", label: "ESI Establishment ID", type: "text" }
  ];

  var SAUDI_FIELDS = [
    { key: "cr_number", label: "Commercial Registration (CR)", type: "text", required: true },
    { key: "cr_issue_date", label: "CR Issue Date", type: "date" },
    { key: "cr_expiry_date", label: "CR Expiry Date", type: "date" },
    { key: "vat_number", label: "VAT Number", type: "text", required: true },
    { key: "zatca_fatoora_id", label: "ZATCA Fatoora ID", type: "text" },
    { key: "gosi_number", label: "GOSI Number", type: "text" },
    { key: "municipality_license", label: "Municipality License", type: "text" }
  ];

  var UAE_FIELDS = [
    { key: "trade_license_no", label: "Trade License No.", type: "text", required: true },
    { key: "trade_license_authority", label: "License Authority", type: "text" },
    { key: "trade_license_expiry", label: "Trade License Expiry", type: "date" },
    { key: "vat_trn", label: "VAT TRN", type: "text", required: true },
    { key: "chamber_membership_no", label: "Chamber Membership No.", type: "text" }
  ];

  var GCC_DEFAULT_FIELDS = [
    { key: "commercial_reg_no", label: "Commercial Registration No.", type: "text", required: true },
    { key: "tax_registration_no", label: "Tax / VAT Registration", type: "text" },
    { key: "license_authority", label: "License Authority", type: "text" },
    { key: "license_expiry", label: "License Expiry", type: "date" }
  ];

  var INDIA_DIRECTOR = [
    { key: "pan", label: "PAN", type: "text" },
    { key: "aadhaar", label: "Aadhaar", type: "text" }
  ];
  var SAUDI_DIRECTOR = [
    { key: "iqama", label: "Iqama No.", type: "text" },
    { key: "passport", label: "Passport No.", type: "text" }
  ];
  var UAE_DIRECTOR = [
    { key: "emirates_id", label: "Emirates ID", type: "text" },
    { key: "passport", label: "Passport No.", type: "text" }
  ];
  var GENERIC_DIRECTOR = [
    { key: "national_id", label: "National ID", type: "text" },
    { key: "passport", label: "Passport No.", type: "text" }
  ];

  function fieldDefsForCountry(country) {
    if (country === "India") return INDIA_FIELDS;
    if (country === "Saudi Arabia") return SAUDI_FIELDS;
    if (country === "UAE") return UAE_FIELDS;
    var cfg = window.COMPANY_GCC_FIELD_CONFIG || {};
    if (cfg[country] && cfg[country].length) return cfg[country];
    return GCC_DEFAULT_FIELDS;
  }

  function directorDefsForCountry(country) {
    if (country === "India") return INDIA_DIRECTOR;
    if (country === "Saudi Arabia") return SAUDI_DIRECTOR;
    if (country === "UAE") return UAE_DIRECTOR;
    return GENERIC_DIRECTOR;
  }

  function renderField(container, field, prefix, values) {
    if (!container) return;
    var wrap = document.createElement("div");
    wrap.className = "erp-field";
    var name = prefix + field.key;
    var val = (values && values[field.key]) || "";
    if (field.type === "select") {
      var sel = document.createElement("select");
      sel.name = name;
      sel.className = "has-value";
      (field.options || []).forEach(function (opt) {
        var o = document.createElement("option");
        o.value = opt;
        o.textContent = opt;
        if (val === opt) o.selected = true;
        sel.appendChild(o);
      });
      wrap.appendChild(sel);
    } else {
      var inp = document.createElement("input");
      inp.name = name;
      inp.type = field.type || "text";
      inp.placeholder = " ";
      if (field.required) inp.required = true;
      inp.value = val;
      wrap.appendChild(inp);
    }
    var lbl = document.createElement("label");
    lbl.textContent = field.label + (field.required ? " *" : "");
    wrap.appendChild(lbl);
    container.appendChild(wrap);
  }

  function renderCountryFields(countrySelect, targetId, prefix, values) {
    var container = document.getElementById(targetId);
    if (!container) return;
    container.innerHTML = "";
    var country = countrySelect ? countrySelect.value : "India";
    var fields = fieldDefsForCountry(country);
    fields.forEach(function (f) {
      renderField(container, f, prefix, values);
    });
    var gstPanel = document.getElementById("gst-registrations-panel");
    if (gstPanel) {
      gstPanel.style.display = country === "India" ? "" : "none";
    }
  }

  function renderDirectorFields(countrySelect, targetId, prefix, values) {
    var container = document.getElementById(targetId);
    if (!container) return;
    container.innerHTML = "";
    var country = countrySelect ? countrySelect.value : "India";
    directorDefsForCountry(country).forEach(function (f) {
      renderField(container, f, prefix, values);
    });
  }

  function bindCountryToggle(selectId, targetId, prefix, values) {
    var sel = document.getElementById(selectId);
    if (!sel) return;
    sel.addEventListener("change", function () {
      renderCountryFields(sel, targetId, prefix, {});
    });
    renderCountryFields(sel, targetId, prefix, values || {});
  }

  function bindDirectorToggle(selectId, targetId, prefix, values) {
    var sel = document.getElementById(selectId);
    if (!sel) return;
    sel.addEventListener("change", function () {
      renderDirectorFields(sel, targetId, prefix, {});
    });
    renderDirectorFields(sel, targetId, prefix, values || {});
  }

  document.addEventListener("DOMContentLoaded", function () {
    var boot = window.COMPANY_MASTER_BOOT || {};
    bindCountryToggle("company-country", "company-country-fields", "cf_", boot.countryFields || {});
    bindCountryToggle("branch-country", "branch-country-fields", "cf_", boot.branchCountryFields || {});
    bindDirectorToggle("director-country", "director-id-fields", "dp_", boot.directorIdFields || {});

    var tabBtns = document.querySelectorAll("[data-company-tab]");
    var panels = document.querySelectorAll("[data-company-panel]");
    tabBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var tab = btn.getAttribute("data-company-tab");
        tabBtns.forEach(function (b) { b.classList.remove("is-active"); });
        btn.classList.add("is-active");
        panels.forEach(function (p) {
          p.hidden = p.getAttribute("data-company-panel") !== tab;
        });
      });
    });
  });
})();
