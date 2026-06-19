(function () {
  var STORAGE_KEY = 'maxek_timesheet_draft';

  function readDraft() {
    try {
      return JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '{}');
    } catch (err) {
      return {};
    }
  }

  function writeDraft(patch) {
    var draft = readDraft();
    Object.keys(patch).forEach(function (key) {
      if (patch[key] === undefined || patch[key] === null || patch[key] === '') {
        delete draft[key];
      } else {
        draft[key] = patch[key];
      }
    });
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(draft));
  }

  function clearDraft() {
    sessionStorage.removeItem(STORAGE_KEY);
  }

  function urlContext() {
    var params = new URLSearchParams(window.location.search);
    var ctx = {};
    if (params.get('year_month')) ctx.year_month = params.get('year_month');
    if (params.get('project_id')) ctx.project_id = params.get('project_id');
    return ctx;
  }

  function fieldValue(form, name) {
    var el = form.querySelector('[name="' + name + '"]');
    return el ? el.value : '';
  }

  function setFieldValue(form, name, value) {
    var el = form.querySelector('[name="' + name + '"]');
    if (!el || value === undefined || value === null) return;
    el.value = value;
    if (el.tagName === 'SELECT') {
      el.classList.toggle('has-value', el.value !== '');
    }
  }

  function clearEmployeeFields(form) {
    [
      'employee_id', 'sub_display_name', 'sub_display_code', 'employee_name',
      'employee_code', 'designation', 'working_days', 'leave_days', 'holiday_days',
      'overtime_hours', 'total_days', 'total_salary_paid', 'supervisor_signature', 'remarks',
    ].forEach(function (name) {
      var el = form.querySelector('[name="' + name + '"]');
      if (!el) return;
      if (el.tagName === 'SELECT') {
        el.value = '';
        el.classList.remove('has-value');
      } else if (el.type === 'number') {
        el.value = '0';
      } else {
        el.value = '';
      }
    });
    form.querySelectorAll('input[name^="day_"], select[name^="day_"], textarea[name^="day_"]')
      .forEach(function (el) {
        if (el.tagName === 'SELECT') {
          el.selectedIndex = 0;
        } else {
          el.value = '';
        }
      });
  }

  function applyEmployeeOption(option, form) {
    if (!option || !option.value) return;
    setFieldValue(form, 'employee_name', option.getAttribute('data-employee-name') || '');
    setFieldValue(form, 'employee_code', option.getAttribute('data-employee-code') || '');
    setFieldValue(form, 'designation', option.getAttribute('data-designation') || '');
    setFieldValue(form, 'sub_display_name', option.getAttribute('data-sub-name') || '');
    setFieldValue(form, 'sub_display_code', option.getAttribute('data-sub-code') || '');
    var designationInput = form.querySelector('[name="designation"]');
    if (designationInput && option.getAttribute('data-designation')) {
      designationInput.readOnly = true;
    } else if (designationInput) {
      designationInput.readOnly = false;
    }
  }

  function persistContext(form) {
    writeDraft({
      year_month: fieldValue(form, 'year_month'),
      project_id: fieldValue(form, 'project_id'),
      employee_source: fieldValue(form, 'employee_source'),
    });
  }

  function restoreContext(form) {
    var draft = readDraft();
    var fromUrl = urlContext();
    var ctx = Object.assign({}, draft, fromUrl);
    if (ctx.employee_source) {
      setFieldValue(form, 'employee_source', ctx.employee_source);
    }
    if (ctx.year_month) {
      setFieldValue(form, 'year_month', ctx.year_month);
    }
    if (ctx.project_id) {
      setFieldValue(form, 'project_id', ctx.project_id);
    }
    writeDraft(ctx);
  }

  function initTimesheetForm() {
    var form = document.querySelector('[data-timesheet-form]');
    if (!form) return;

    var source = form.querySelector('#employee_source');
    var select = form.querySelector('#employee_id');
    var clearBtn = form.querySelector('[data-timesheet-clear]');

    if (!source || !select) return;

    function filterOptions() {
      var src = source.value;
      for (var i = 0; i < select.options.length; i++) {
        var opt = select.options[i];
        if (!opt.value) continue;
        opt.hidden = opt.getAttribute('data-source') !== src;
      }
      select.value = '';
      select.classList.remove('has-value');
      clearEmployeeFields(form);
    }

    restoreContext(form);
    filterOptions();
    source.addEventListener('change', function () {
      filterOptions();
      persistContext(form);
    });
    select.addEventListener('change', function () {
      var option = select.options[select.selectedIndex];
      applyEmployeeOption(option, form);
    });

    form.querySelectorAll('[name="year_month"], [name="project_id"]').forEach(function (el) {
      el.addEventListener('change', function () {
        persistContext(form);
      });
    });

    form.addEventListener('submit', function () {
      persistContext(form);
    });

    if (clearBtn) {
      clearBtn.addEventListener('click', function (event) {
        event.preventDefault();
        clearDraft();
        setFieldValue(form, 'year_month', '');
        setFieldValue(form, 'project_id', '');
        if (source) {
          source.value = 'staff';
        }
        filterOptions();
        clearEmployeeFields(form);
      });
    }
  }

  document.addEventListener('DOMContentLoaded', initTimesheetForm);
})();
