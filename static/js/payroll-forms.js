(function () {
  'use strict';

  /* ───────── Generate form: mode / project field ───────── */

  function toggleGenMode(form) {
    var mode = form.querySelector('[data-payroll-gen-mode]');
    if (!mode) return;
    var isMonthly = mode.value === 'monthly';
    form.querySelectorAll('[data-payroll-monthly]').forEach(function (el) { el.hidden = !isMonthly; });
    form.querySelectorAll('[data-payroll-range]').forEach(function (el) { el.hidden = isMonthly; });
  }

  function updatePayrollProjectField(form) {
    var typeSel = form.querySelector('[data-payroll-employment-type]');
    var projectField = form.querySelector('[data-payroll-project-field]');
    var projectSelect = form.querySelector('[data-payroll-project-select]');
    if (!typeSel || !projectField) return;
    var showProject = typeSel.value === 'subcontractor';
    projectField.hidden = !showProject;
    if (!showProject && projectSelect) projectSelect.value = '';
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

  /* ───────── Employee selector ───────── */

  function selectableBoxes(form) {
    return form.querySelectorAll(
      '[data-payroll-staff-row]:not([hidden]) input[type="checkbox"]:not(:disabled)'
    );
  }

  function updatePayrollSelectedCount(form) {
    var counter = form.querySelector('[data-payroll-selected-count]');
    if (!counter) return;
    var rows = form.querySelectorAll('[data-payroll-staff-row]');
    var shown = form.querySelectorAll('[data-payroll-staff-row]:not([hidden])').length;
    var checked = form.querySelectorAll('[data-payroll-staff-row] input[type="checkbox"]:checked').length;
    counter.textContent = checked + ' selected of ' + shown + ' shown' +
      (shown !== rows.length ? ' (' + rows.length + ' total)' : '');
  }

  function renderPayrollStaffRows(form, employees, message) {
    var list = form.querySelector('[data-payroll-staff-list]');
    var messageEl = form.querySelector('[data-payroll-staff-message]');
    if (!list) return;
    list.innerHTML = '';
    employees.forEach(function (emp) {
      var label = document.createElement('label');
      label.className = 'payroll-staff-row' + (emp.selectable === false ? ' is-blocked' : '');
      label.setAttribute('data-payroll-staff-row', '');
      label.setAttribute('data-emp-filter', emp.emp_filter || '');

      var cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.name = 'employee_ids';
      cb.value = emp.employee_type + ':' + emp.employee_id;
      cb.disabled = emp.selectable === false;
      cb.addEventListener('change', function () { updatePayrollSelectedCount(form); });

      var span = document.createElement('span');
      var strong = document.createElement('strong');
      strong.textContent = emp.employee_name || '—';
      var hint = document.createElement('small');
      hint.textContent = (emp.employee_code || '—') + ' · ' + (emp.type_label || '') +
        (emp.department ? ' · ' + emp.department : '');
      span.appendChild(strong);
      span.appendChild(hint);
      if (emp.blocked_reason) {
        var why = document.createElement('small');
        why.className = 'pd-reason';
        why.textContent = emp.blocked_reason;
        span.appendChild(why);
      }
      label.setAttribute('data-search',
        ((emp.employee_name || '') + ' ' + (emp.employee_code || '') + ' ' + (emp.department || '')).toLowerCase());
      label.appendChild(cb);
      label.appendChild(span);
      list.appendChild(label);
    });
    if (messageEl) {
      messageEl.textContent = message || '';
      messageEl.hidden = !message;
    }
    applyStaffSearch(form);
    updatePayrollSelectedCount(form);
  }

  function setPayrollStaffMessage(form, text) {
    var messageEl = form.querySelector('[data-payroll-staff-message]');
    var list = form.querySelector('[data-payroll-staff-list]');
    if (messageEl) {
      messageEl.textContent = text || '';
      messageEl.hidden = false;
    }
    if (list) list.innerHTML = '';
    updatePayrollSelectedCount(form);
  }

  function applyStaffSearch(form) {
    var input = form.querySelector('[data-payroll-staff-search]');
    var needle = input ? input.value.trim().toLowerCase() : '';
    form.querySelectorAll('[data-payroll-staff-row]').forEach(function (row) {
      row.hidden = !!needle && (row.getAttribute('data-search') || '').indexOf(needle) === -1;
    });
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
    var token = ++payrollFetchToken;
    setPayrollStaffMessage(form, 'Loading staff for selected period…');
    fetch('/payroll/eligible-employees?' + params.toString(), {
      headers: { 'Accept': 'application/json' },
      credentials: 'same-origin'
    })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        if (token !== payrollFetchToken) return;
        var employees = data.employees || [];
        if (!employees.length) {
          setPayrollStaffMessage(form, data.message || 'No active employees found for this employment type.');
          return;
        }
        renderPayrollStaffRows(form, employees, data.message || '');
      })
      .catch(function () {
        if (token !== payrollFetchToken) return;
        setPayrollStaffMessage(form, 'Could not load the employee list. Check your connection and change the period to retry.');
      });
  }

  /* ───────── "Can't find someone?" eligibility check ───────── */

  function bindEligibilityCheck(form) {
    var input = form.querySelector('[data-payroll-why-input]');
    var go = form.querySelector('[data-payroll-why-go]');
    var out = form.querySelector('[data-payroll-why-result]');
    if (!input || !go || !out) return;

    function esc(text) {
      var el = document.createElement('div');
      el.textContent = text == null ? '' : String(text);
      return el.innerHTML;
    }

    function run() {
      var q = input.value.trim();
      if (q.length < 2) {
        out.textContent = 'Type at least two characters of a name or code.';
        return;
      }
      var params = payrollPeriodParams(form);
      params.set('q', q);
      out.textContent = 'Checking…';
      fetch('/payroll/eligibility-check?' + params.toString(), {
        headers: { 'Accept': 'application/json' },
        credentials: 'same-origin'
      })
        .then(function (res) {
          if (!res.ok) throw new Error('HTTP ' + res.status);
          return res.json();
        })
        .then(function (data) {
          var results = data.results || [];
          if (!results.length) {
            out.textContent = 'No employee or worker record matches "' + q + '". Check the spelling, or add them in the staff master.';
            return;
          }
          out.innerHTML = results.map(function (r) {
            var verdict = r.selectable
              ? '<span class="ok">Selectable</span>'
              : (r.listed ? '<span class="bad">Listed but blocked</span>' : '<span class="bad">Not listed</span>');
            var reasons = (r.reasons || []).map(function (t) { return '<li>' + esc(t) + '</li>'; }).join('');
            var checks = (r.checks || []).map(function (c) {
              return '<li><span class="' + (c.ok ? 'ok' : 'bad') + '">' + (c.ok ? '✓' : '✗') + '</span> ' +
                esc(c.check) + (c.detail ? ' <span class="pd-muted">— ' + esc(c.detail) + '</span>' : '') + '</li>';
            }).join('');
            return '<div><strong>' + esc(r.employee_name) + '</strong> <span class="pd-muted">' +
              esc(r.employee_code) + '</span> — ' + verdict +
              (reasons ? '<ul>' + reasons + '</ul>' : '') +
              '<ul>' + checks + '</ul></div>';
          }).join('');
        })
        .catch(function () {
          out.textContent = 'The check could not be completed. Try again.';
        });
    }

    go.addEventListener('click', run);
    input.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') {
        event.preventDefault();
        run();
      }
    });
  }

  /* ───────── Generate form wiring ───────── */

  function bindPayrollStaffPanel(form) {
    var typeSel = form.querySelector('[data-payroll-employment-type]');
    if (!typeSel) return;

    typeSel.addEventListener('change', function () { fetchPayrollEligibleEmployees(form); });

    ['month', 'year', 'period_start', 'period_end'].forEach(function (name) {
      var el = form.querySelector('[name="' + name + '"]');
      if (!el) return;
      el.addEventListener('change', function () { fetchPayrollEligibleEmployees(form); });
      if (name === 'year') el.addEventListener('input', function () { fetchPayrollEligibleEmployees(form); });
    });

    var deptSel = form.querySelector('[name="department"]');
    if (deptSel) deptSel.addEventListener('change', function () { fetchPayrollEligibleEmployees(form); });

    var projectSel = form.querySelector('[data-payroll-project-select]');
    if (projectSel) projectSel.addEventListener('change', function () { fetchPayrollEligibleEmployees(form); });

    var search = form.querySelector('[data-payroll-staff-search]');
    if (search) {
      search.addEventListener('input', function () {
        applyStaffSearch(form);
        updatePayrollSelectedCount(form);
      });
    }

    var selectAll = form.querySelector('[data-payroll-select-all]');
    if (selectAll) {
      selectAll.addEventListener('click', function () {
        selectableBoxes(form).forEach(function (cb) { cb.checked = true; });
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
      if (!typeSel.value) {
        event.preventDefault();
        window.alert('Select employment type: Company Staff or Sub Contractor.');
        return;
      }
      updatePayrollProjectField(form);
      var selected = form.querySelectorAll('[data-payroll-staff-row] input[type="checkbox"]:checked:not(:disabled)');
      if (!selected.length) {
        event.preventDefault();
        window.alert('Select at least one employee for this payroll run.');
      }
    });

    bindEligibilityCheck(form);
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

  /* ───────── Dashboard: generate panel, filters, loading state ───────── */

  // The shell's fixed 272px sidebar would leave ~100px of content on a phone. Collapse it to the
  // icon rail for this page only; the choice is not saved, so desktop preferences are untouched.
  (function collapseShellSidebarOnPhones() {
    var shell = document.querySelector('[data-pro-dash-shell]');
    if (shell && document.querySelector('[data-pd]') &&
        window.matchMedia && window.matchMedia('(max-width: 760px)').matches) {
      shell.classList.add('is-sidebar-collapsed');
    }
  })();

  function openGeneratePanel(scroll) {
    var panel = document.querySelector('[data-pd-generate]');
    if (!panel) return null;
    panel.open = true;
    if (scroll) panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return panel;
  }

  document.querySelectorAll('[data-pd-open-generate]').forEach(function (btn) {
    btn.addEventListener('click', function () { openGeneratePanel(true); });
  });
  if (window.location.hash === '#generate-payroll') openGeneratePanel(false);

  function setBusy(on) {
    document.querySelectorAll('[data-pd-table]').forEach(function (el) {
      el.setAttribute('aria-busy', on ? 'true' : 'false');
    });
  }

  document.querySelectorAll('[data-pd-form]').forEach(function (form) {
    form.addEventListener('submit', function () { setBusy(true); });
  });
  document.querySelectorAll('[data-pd-autosubmit]').forEach(function (sel) {
    sel.addEventListener('change', function () {
      var form = sel.form;
      if (!form) return;
      setBusy(true);
      if (form.requestSubmit) form.requestSubmit(); else form.submit();
    });
  });
  // Back/forward cache restores the page with the spinner on; clear it.
  window.addEventListener('pageshow', function () { setBusy(false); });

  /* ───────── Prefill generate form from a dashboard row ───────── */

  function prefillPayrollGenerate(form, options) {
    if (!form || !options) return;
    openGeneratePanel(false);
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
    if (typeSel && options.category) typeSel.value = options.category;
    updatePayrollProjectField(form);
    var projectSel = form.querySelector('[data-payroll-project-select]');
    if (projectSel) projectSel.value = options.projectId ? String(options.projectId) : '';
    fetchPayrollEligibleEmployees(form);
    if (options.employeeRef) {
      var attempts = 0;
      (function tick() {
        var cb = form.querySelector('input[name="employee_ids"][value="' + options.employeeRef + '"]');
        if (cb && !cb.disabled) {
          cb.checked = true;
          updatePayrollSelectedCount(form);
        } else if (attempts++ < 20) {
          window.setTimeout(tick, 150);
        }
      })();
    }
    var target = document.getElementById('generate-payroll');
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

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

  /* ───────── Revisions / payments (unchanged behaviour) ───────── */

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
