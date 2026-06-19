(function () {

  function toggleGenMode(form) {

    var mode = form.querySelector('[data-payroll-gen-mode]');

    if (!mode) return;

    var monthly = form.querySelectorAll('[data-payroll-monthly]');

    var range = form.querySelectorAll('[data-payroll-range]');

    var isMonthly = mode.value === 'monthly';

    monthly.forEach(function (el) { el.hidden = !isMonthly; });

    range.forEach(function (el) { el.hidden = isMonthly; });

  }



  function updatePayrollProjectField(form) {

    var typeSel = form.querySelector('[data-payroll-employment-type]');

    var projectField = form.querySelector('[data-payroll-project-field]');

    var projectSelect = form.querySelector('[data-payroll-project-select]');

    if (!typeSel || !projectField) return;

    var showProject = typeSel.value === 'subcontractor';

    projectField.hidden = !showProject;

    if (!showProject && projectSelect) {

      projectSelect.value = '';

    }

  }



  function payrollPeriodParams(form) {

    var mode = form.querySelector('[data-payroll-gen-mode]');

    var params = new URLSearchParams();

    params.set('gen_mode', mode ? mode.value : 'monthly');

    if (params.get('gen_mode') === 'monthly') {

      var monthSel = form.querySelector('[name="month"]');

      var yearInput = form.querySelector('[name="year"]');

      if (monthSel) params.set('month', monthSel.value);

      if (yearInput && yearInput.value) params.set('year', yearInput.value);

    } else {

      var start = form.querySelector('[name="period_start"]');

      var end = form.querySelector('[name="period_end"]');

      if (start && start.value) params.set('period_start', start.value);

      if (end && end.value) params.set('period_end', end.value);

    }

    var typeSel = form.querySelector('[data-payroll-employment-type]');

    if (typeSel && typeSel.value) params.set('employment_category', typeSel.value);

    var deptSel = form.querySelector('[name="department"]');

    if (deptSel && deptSel.value) params.set('department', deptSel.value);

    var projectSel = form.querySelector('[data-payroll-project-select]');

    if (projectSel && projectSel.value) params.set('project_id', projectSel.value);

    return params;

  }



  function renderPayrollStaffRows(form, employees) {

    var list = form.querySelector('[data-payroll-staff-list]');

    var messageEl = form.querySelector('[data-payroll-staff-message]');

    if (!list) return;

    list.innerHTML = '';

    employees.forEach(function (emp) {

      var label = document.createElement('label');

      label.className = 'payroll-staff-row';

      label.setAttribute('data-payroll-staff-row', '');

      label.setAttribute('data-emp-filter', emp.emp_filter || '');

      label.style.cssText = 'display: flex; align-items: center; gap: 0.5rem; padding: 0.35rem 0.25rem; border-bottom: 1px dashed var(--erp-border, #e2e8f0);';

      var cb = document.createElement('input');

      cb.type = 'checkbox';

      cb.name = 'employee_ids';

      cb.value = emp.employee_type + ':' + emp.employee_id;

      cb.addEventListener('change', function () {

        updatePayrollSelectedCount(form);

      });

      var span = document.createElement('span');

      var strong = document.createElement('strong');

      strong.textContent = emp.employee_name || '—';

      var hint = document.createElement('span');

      hint.className = 'erp-form-hint';

      var code = emp.employee_code || '—';

      var dept = emp.department ? (' · ' + emp.department) : '';

      hint.textContent = ' — ' + code + ' · ' + (emp.type_label || '') + dept;

      span.appendChild(strong);

      span.appendChild(hint);

      label.appendChild(cb);

      label.appendChild(span);

      list.appendChild(label);

    });

    if (messageEl) {

      messageEl.hidden = employees.length > 0;

    }

    updatePayrollSelectedCount(form, employees.length);

  }



  function setPayrollStaffMessage(form, text) {

    var messageEl = form.querySelector('[data-payroll-staff-message]');

    var list = form.querySelector('[data-payroll-staff-list]');

    if (messageEl) {

      messageEl.textContent = text || '';

      messageEl.hidden = false;

    }

    if (list) list.innerHTML = '';

    updatePayrollSelectedCount(form, 0);

  }



  var payrollFetchToken = 0;



  function fetchPayrollEligibleEmployees(form) {

    var typeSel = form.querySelector('[data-payroll-employment-type]');

    var panel = form.querySelector('[data-payroll-staff-panel]');

    if (!typeSel || !panel) return;

    updatePayrollProjectField(form);

    var category = typeSel.value;

    panel.hidden = !category;

    if (!category) {

      setPayrollStaffMessage(form, 'Select employment type and period to load staff.');

      return;

    }

    var params = payrollPeriodParams(form);

    if (!params.get('employment_category')) {

      setPayrollStaffMessage(form, 'Select employment type and period to load staff.');

      return;

    }

    var token = ++payrollFetchToken;

    setPayrollStaffMessage(form, 'Loading staff for selected period…');

    fetch('/payroll/eligible-employees?' + params.toString(), {

      headers: { 'Accept': 'application/json' },

      credentials: 'same-origin'

    })

      .then(function (res) { return res.json(); })

      .then(function (data) {

        if (token !== payrollFetchToken) return;

        var employees = data.employees || [];

        if (!employees.length) {

          setPayrollStaffMessage(form, data.message || 'No staff with attendance/data for this month.');

          return;

        }

        renderPayrollStaffRows(form, employees);

      })

      .catch(function () {

        if (token !== payrollFetchToken) return;

        setPayrollStaffMessage(form, 'Could not load staff list. Try again.');

      });

  }



  function updatePayrollSelectedCount(form, visibleCount) {

    var counter = form.querySelector('[data-payroll-selected-count]');

    if (!counter) return;

    var checked = form.querySelectorAll('[data-payroll-staff-row]:not([hidden]) input[type="checkbox"]:checked').length;

    if (visibleCount == null) {

      visibleCount = form.querySelectorAll('[data-payroll-staff-row]').length;

    }

    var suffix = visibleCount != null ? (' of ' + visibleCount + ' shown') : '';

    counter.textContent = checked + ' selected' + suffix;

  }



  function bindPayrollStaffPanel(form) {

    var typeSel = form.querySelector('[data-payroll-employment-type]');

    if (!typeSel) return;



    typeSel.addEventListener('change', function () {

      fetchPayrollEligibleEmployees(form);

    });



    ['month', 'year', 'period_start', 'period_end'].forEach(function (name) {

      var el = form.querySelector('[name="' + name + '"]');

      if (el) {

        el.addEventListener('change', function () {

          fetchPayrollEligibleEmployees(form);

        });

        if (name === 'year') {

          el.addEventListener('input', function () {

            fetchPayrollEligibleEmployees(form);

          });

        }

      }

    });



    var deptSel = form.querySelector('[name="department"]');

    if (deptSel) {

      deptSel.addEventListener('change', function () {

        fetchPayrollEligibleEmployees(form);

      });

    }



    var projectSel = form.querySelector('[data-payroll-project-select]');

    if (projectSel) {

      projectSel.addEventListener('change', function () {

        fetchPayrollEligibleEmployees(form);

      });

    }



    var selectAll = form.querySelector('[data-payroll-select-all]');

    if (selectAll) {

      selectAll.addEventListener('click', function () {

        form.querySelectorAll('[data-payroll-staff-row]:not([hidden]) input[type="checkbox"]').forEach(function (cb) {

          cb.checked = true;

        });

        updatePayrollSelectedCount(form);

      });

    }



    var clearAll = form.querySelector('[data-payroll-clear-all]');

    if (clearAll) {

      clearAll.addEventListener('click', function () {

        form.querySelectorAll('[data-payroll-staff-row] input[type="checkbox"]').forEach(function (cb) {

          cb.checked = false;

        });

        updatePayrollSelectedCount(form);

      });

    }



    form.addEventListener('submit', function (event) {

      var category = typeSel.value;

      if (!category) {

        event.preventDefault();

        window.alert('Select employment type: Company Staff or Sub Contractor.');

        return;

      }

      updatePayrollProjectField(form);

      var selected = form.querySelectorAll('[data-payroll-staff-row]:not([hidden]) input[type="checkbox"]:checked');

      if (!selected.length) {

        event.preventDefault();

        var msgEl = form.querySelector('[data-payroll-staff-message]');

        var msg = msgEl && !msgEl.hidden && msgEl.textContent

          ? msgEl.textContent

          : 'Select at least one employee for this payroll run.';

        window.alert(msg);

      }

    });



    fetchPayrollEligibleEmployees(form);

  }



  function bindPayrollLineEditors() {

    document.querySelectorAll('[data-payroll-edit-line]').forEach(function (btn) {

      btn.addEventListener('click', function () {

        var lineId = btn.getAttribute('data-payroll-edit-line');

        document.querySelectorAll('[data-payroll-edit-panel]').forEach(function (panel) {

          panel.hidden = panel.getAttribute('data-payroll-edit-panel') !== lineId;

        });

      });

    });

    document.querySelectorAll('[data-payroll-cancel-edit]').forEach(function (btn) {

      btn.addEventListener('click', function () {

        var lineId = btn.getAttribute('data-payroll-cancel-edit');

        var panel = document.querySelector('[data-payroll-edit-panel="' + lineId + '"]');

        if (panel) panel.hidden = true;

      });

    });

  }



  document.querySelectorAll('[data-payroll-generate-form]').forEach(function (form) {

    var mode = form.querySelector('[data-payroll-gen-mode]');

    if (mode) {

      mode.addEventListener('change', function () {

        toggleGenMode(form);

        fetchPayrollEligibleEmployees(form);

      });

      toggleGenMode(form);

    }

    bindPayrollStaffPanel(form);

  });



  bindPayrollLineEditors();



  function prefillPayrollGenerate(form, options) {

    if (!form || !options) return;

    var mode = form.querySelector('[data-payroll-gen-mode]');

    if (mode) {

      mode.value = 'monthly';

      toggleGenMode(form);

    }

    if (options.month != null) {

      var monthSel = form.querySelector('[name="month"]');

      if (monthSel) monthSel.value = String(options.month);

    }

    if (options.year != null) {

      var yearInput = form.querySelector('[name="year"]');

      if (yearInput) yearInput.value = String(options.year);

    }

    var typeSel = form.querySelector('[data-payroll-employment-type]');

    if (typeSel && options.category) {

      typeSel.value = options.category;

    }

    updatePayrollProjectField(form);

    var projectSel = form.querySelector('[data-payroll-project-select]');

    if (projectSel) {

      projectSel.value = options.projectId ? String(options.projectId) : '';

    }

    fetchPayrollEligibleEmployees(form);

    if (options.employeeRef) {

      window.setTimeout(function () {

        var selector = 'input[name="employee_ids"][value="' + options.employeeRef + '"]';

        var cb = form.querySelector(selector);

        if (cb) {

          cb.checked = true;

          updatePayrollSelectedCount(form);

        }

      }, 450);

    }

    var target = document.getElementById('generate-payroll');

    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });

  }



  function bindPendingPayrollPrefill() {

    document.querySelectorAll('[data-payroll-prefill-generate]').forEach(function (btn) {

      btn.addEventListener('click', function () {

        var form = document.querySelector('[data-payroll-generate-form]');

        if (!form) return;

        prefillPayrollGenerate(form, {

          month: btn.getAttribute('data-prefill-month'),

          year: btn.getAttribute('data-prefill-year'),

          category: btn.getAttribute('data-prefill-category'),

          employeeRef: btn.getAttribute('data-prefill-employee'),

          projectId: btn.getAttribute('data-prefill-project')

        });

      });

    });

  }



  bindPendingPayrollPrefill();



  document.querySelectorAll('[data-payroll-revision-form]').forEach(function (form) {

    var typeSel = form.querySelector('[data-revision-type]');

    var staffBlock = form.querySelector('[data-revision-staff]');

    var workerBlock = form.querySelector('[data-revision-worker]');

    if (!typeSel) return;

    function sync() {

      var isStaff = typeSel.value === 'staff';

      if (staffBlock) staffBlock.hidden = !isStaff;

      if (workerBlock) workerBlock.hidden = isStaff;

    }

    typeSel.addEventListener('change', sync);

    sync();

  });



  document.querySelectorAll('[data-payroll-payment-form]').forEach(function (form) {

    var sel = form.querySelector('[data-payment-line-select]');

    if (!sel) return;

    sel.addEventListener('change', function () {

      var opt = sel.options[sel.selectedIndex];

      if (!opt || !opt.dataset.gross) return;

      var gross = form.querySelector('[data-payment-gross]');

      var ded = form.querySelector('[data-payment-deductions]');

      var net = form.querySelector('[data-payment-net]');

      if (gross) gross.value = opt.dataset.gross;

      if (ded) ded.value = opt.dataset.deductions;

      if (net) net.value = opt.dataset.net;

    });

  });

})();
