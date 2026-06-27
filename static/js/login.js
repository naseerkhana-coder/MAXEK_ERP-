(function () {
  var STORAGE_USERNAMES = "maxek_saved_usernames";
  var STORAGE_LAST_USERNAME = "maxek_last_username";
  var STORAGE_LAST_COMPANY = "maxek_last_company_code";
  var MAX_USERNAMES = 12;

  function loadUsernames() {
    try {
      var raw = localStorage.getItem(STORAGE_USERNAMES);
      var list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list.filter(Boolean) : [];
    } catch (e) {
      return [];
    }
  }

  function saveUsername(name) {
    if (!name) return;
    var list = loadUsernames().filter(function (u) {
      return u.toLowerCase() !== name.toLowerCase();
    });
    list.unshift(name);
    localStorage.setItem(STORAGE_USERNAMES, JSON.stringify(list.slice(0, MAX_USERNAMES)));
    localStorage.setItem(STORAGE_LAST_USERNAME, name);
  }

  function saveCompanyCode(code) {
    if (code) {
      localStorage.setItem(STORAGE_LAST_COMPANY, code);
    }
  }

  function initPasswordToggle() {
    var toggle = document.querySelector(".toggle-pass");
    var pass = document.getElementById("password");
    if (!toggle || !pass) return;
    toggle.addEventListener("click", function () {
      var show = pass.type === "password";
      pass.type = show ? "text" : "password";
      toggle.setAttribute("aria-label", show ? "Hide password" : "Show password");
      var icon = toggle.querySelector("i");
      if (icon) {
        icon.className = "fa-solid " + (show ? "fa-eye-slash" : "fa-eye");
      }
    });
  }

  function initRememberedFields() {
    var usernameInput = document.getElementById("username");
    var companyInput = document.getElementById("company_code");
    var datalist = document.getElementById("login-usernames");

    if (datalist) {
      var names = loadUsernames();
      datalist.innerHTML = "";
      names.forEach(function (name) {
        var opt = document.createElement("option");
        opt.value = name;
        datalist.appendChild(opt);
      });
    }

    if (usernameInput && !usernameInput.value) {
      var remembered =
        usernameInput.getAttribute("data-remembered-user") ||
        localStorage.getItem(STORAGE_LAST_USERNAME) ||
        "";
      if (remembered) {
        usernameInput.value = remembered;
      }
    }

    if (companyInput && !companyInput.value) {
      var company = localStorage.getItem(STORAGE_LAST_COMPANY);
      if (company) {
        companyInput.value = company;
      }
    }
  }

  function initFormSubmit() {
    var form = document.querySelector(".login-form");
    var btn = document.querySelector(".login-submit");
    if (!form) return;

    form.addEventListener("submit", function () {
      var username = form.querySelector('input[name="username"]');
      var company = form.querySelector('input[name="company_code"]');
      if (username && username.value.trim()) {
        saveUsername(username.value.trim());
      }
      if (company && company.value.trim()) {
        saveCompanyCode(company.value.trim());
      }
      if (btn) {
        btn.classList.add("is-loading");
        btn.disabled = true;
      }
    });
  }

  function initFocus() {
    var password = document.getElementById("password");
    if (password && password.value) return;
    ["company_code", "username", "password"].some(function (id) {
      var el = document.getElementById(id);
      if (el && !el.value) {
        el.focus();
        return true;
      }
      return false;
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initPasswordToggle();
    initRememberedFields();
    initFormSubmit();
    initFocus();
  });
})();
