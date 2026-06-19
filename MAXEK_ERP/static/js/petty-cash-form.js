(function () {
  function syncHasValue(field) {
    if (!field) return;
    field.classList.toggle('has-value', field.value !== '');
  }

  function initPettyCashForm() {
    var form = document.querySelector('[data-petty-cash-form]');
    if (!form) return;

    var projectCode = form.querySelector('#pc_project_code');
    var projectName = form.querySelector('#pc_project_name');
    var staffName = form.querySelector('#pc_staff_name');
    var employeeCode = form.querySelector('#pc_employee_code');
    var staffId = form.querySelector('#pc_staff_id');
    var employeeCodeHidden = form.querySelector('#pc_employee_code_hidden');
    var department = form.querySelector('#pc_department');

    function syncProjectFromCode() {
      if (!projectCode || !projectName) return;
      projectName.value = projectCode.value;
      syncHasValue(projectName);
    }

    function syncProjectFromName() {
      if (!projectCode || !projectName) return;
      projectCode.value = projectName.value;
      syncHasValue(projectCode);
    }

    function applyStaffOption(option) {
      if (!option || !option.value) return;
      if (staffId) staffId.value = option.getAttribute('data-id') || option.value || '';
      if (employeeCodeHidden) {
        employeeCodeHidden.value = option.getAttribute('data-code') || '';
      }
      if (department && option.getAttribute('data-dept')) {
        department.value = option.getAttribute('data-dept');
        syncHasValue(department);
      }
    }

    function syncStaffFromName() {
      if (!staffName || !employeeCode) return;
      var option = staffName.options[staffName.selectedIndex];
      if (!option || !option.getAttribute('data-id')) {
        var matchId = null;
        Array.prototype.forEach.call(employeeCode.options, function (opt) {
          if (opt.getAttribute('data-name') === staffName.value) matchId = opt.value;
        });
        employeeCode.value = matchId || '';
      } else {
        employeeCode.value = option.getAttribute('data-id') || '';
        applyStaffOption(option);
      }
      syncHasValue(employeeCode);
    }

    function syncStaffFromCode() {
      if (!staffName || !employeeCode) return;
      var option = employeeCode.options[employeeCode.selectedIndex];
      if (option && option.value) {
        var name = option.getAttribute('data-name') || '';
        staffName.value = name;
        syncHasValue(staffName);
        applyStaffOption(option);
      }
    }

    if (projectCode) projectCode.addEventListener('change', syncProjectFromCode);
    if (projectName) projectName.addEventListener('change', syncProjectFromName);
    if (staffName) staffName.addEventListener('change', syncStaffFromName);
    if (employeeCode) employeeCode.addEventListener('change', syncStaffFromCode);

    if (projectName && projectName.value) syncProjectFromName();
    else if (projectCode && projectCode.value) syncProjectFromCode();
    if (staffName && staffName.value) syncStaffFromName();
    else if (employeeCode && employeeCode.value) syncStaffFromCode();
  }

  function initExpenseStaffSync() {
    var form = document.querySelector('[data-petty-cash-expense-form]');
    if (!form) return;
    var staffName = form.querySelector('#pc_expense_staff_name');
    var employeeCode = form.querySelector('#pc_expense_employee_code');
    var staffId = form.querySelector('#pc_expense_staff_id');

    function syncFromName() {
      if (!staffName || !employeeCode) return;
      var option = staffName.options[staffName.selectedIndex];
      var nameHidden = form.querySelector('#pc_expense_staff_name_hidden');
      var codeHidden = form.querySelector('#pc_expense_employee_code_hidden');
      if (option && option.getAttribute('data-id')) {
        staffId.value = option.getAttribute('data-id');
        employeeCode.value = option.getAttribute('data-id');
        if (nameHidden) nameHidden.value = staffName.value;
        if (codeHidden) codeHidden.value = option.getAttribute('data-code') || '';
      }
      syncHasValue(employeeCode);
    }

    function syncFromCode() {
      if (!staffName || !employeeCode) return;
      var option = employeeCode.options[employeeCode.selectedIndex];
      var nameHidden = form.querySelector('#pc_expense_staff_name_hidden');
      var codeHidden = form.querySelector('#pc_expense_employee_code_hidden');
      if (option && option.value) {
        staffName.value = option.getAttribute('data-name') || '';
        staffId.value = option.value;
        if (nameHidden) nameHidden.value = staffName.value;
        if (codeHidden) codeHidden.value = option.getAttribute('data-code') || '';
        syncHasValue(staffName);
      }
    }

    if (staffName) staffName.addEventListener('change', syncFromName);
    if (employeeCode) employeeCode.addEventListener('change', syncFromCode);
    if (staffName && staffName.value) syncFromName();
  }

  document.addEventListener('DOMContentLoaded', function () {
    initPettyCashForm();
    initExpenseStaffSync();
  });
})();
