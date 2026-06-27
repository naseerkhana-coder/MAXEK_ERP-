(function () {
  function setProjectSectionVisible(el, show) {
    el.hidden = !show;
    el.querySelectorAll('input, select, textarea, button').forEach(function (input) {
      if (input.type === 'hidden') return;
      input.disabled = !show;
    });
  }

  function toggleSections(root, type) {
    var isGov = type === 'Government';
    root.querySelectorAll('[data-project-section="government"]').forEach(function (el) {
      setProjectSectionVisible(el, isGov);
    });
    root.querySelectorAll('[data-project-section="private"]').forEach(function (el) {
      setProjectSectionVisible(el, !isGov);
    });
  }

  function toggleGovCompletion(root) {
    var modeInput = root.querySelector('[name="completion_mode"]:checked');
    var mode = modeInput ? modeInput.value : 'months';
    root.querySelectorAll('[data-gov-completion="months"]').forEach(function (el) {
      el.hidden = mode !== 'months';
    });
    root.querySelectorAll('[data-gov-completion="date"]').forEach(function (el) {
      el.hidden = mode !== 'date';
    });
  }

  function parseNum(value) {
    var n = parseFloat(value);
    return isNaN(n) ? 0 : n;
  }

  function initSecurityDepositCalc(form) {
    var quoted = form.querySelector('#project_quoted_amount');
    var pct = form.querySelector('#project_security_pct');
    var amount = form.querySelector('#project_security_amount');
    if (!quoted || !pct || !amount) return;

    var manual = amount.dataset.manual === '1';
    amount.addEventListener('input', function () {
      manual = true;
      amount.dataset.manual = '1';
    });

    function applyCalc() {
      if (manual) return;
      var q = parseNum(quoted.value);
      var p = parseNum(pct.value);
      if (q > 0 && p >= 0) {
        amount.value = (Math.round(q * p) / 100).toFixed(2);
        amount.classList.add('has-value');
      }
    }

    quoted.addEventListener('input', function () {
      manual = false;
      amount.dataset.manual = '0';
      applyCalc();
    });
    pct.addEventListener('input', function () {
      manual = false;
      amount.dataset.manual = '0';
      applyCalc();
    });
    applyCalc();
  }

  function applyBillPledgingVisibility(row) {
    var pledgingSelect = row.querySelector('[data-bill-pledging-select]');
    var enabled = pledgingSelect && pledgingSelect.value === '1';
    row.querySelectorAll('[data-bill-pledging-detail]').forEach(function (field) {
      field.hidden = !enabled;
      field.querySelectorAll('input, select').forEach(function (input) {
        input.disabled = !enabled;
      });
    });
    var pledgingHint = row.querySelector('[data-guarantee-field="pledging"].erp-form-hint');
    if (pledgingHint) {
      pledgingHint.hidden = false;
    }
  }

  function applyBgRowVisibility(row) {
    applyBillPledgingVisibility(row);
  }

  function renumberBgRows(container) {
    var bgContainer = container.querySelector('[data-bg-rows-container]');
    if (!bgContainer) return;
    bgContainer.querySelectorAll('[data-bg-row]').forEach(function (row, idx) {
      var badge = row.querySelector('[data-bg-label], .erp-row-badge');
      if (badge) badge.textContent = 'BG ' + (idx + 1);
    });
  }

  function initGuaranteeRows(form) {
    var container = form.querySelector('[data-guarantee-rows]');
    if (!container) return;
    var bgTemplate = container.querySelector('[data-bg-row-template]');
    var addBtn = container.querySelector('[data-bg-add]');
    var bgContainer = container.querySelector('[data-bg-rows-container]');
    var pendingOptions = [];
    try {
      pendingOptions = JSON.parse(container.getAttribute('data-pending-bills') || '[]');
    } catch (e) {
      pendingOptions = [];
    }

    function bindRow(row) {
      applyBgRowVisibility(row);
      var pledgingSelect = row.querySelector('[data-bill-pledging-select]');
      if (pledgingSelect) {
        pledgingSelect.addEventListener('change', function () {
          applyBillPledgingVisibility(row);
        });
      }
      var pendingSelect = row.querySelector('[data-pending-bill-select]');
      populatePendingBillSelect(pendingSelect, pendingOptions);
      if (pendingSelect) {
        pendingSelect.addEventListener('change', function () {
          var selected = pendingSelect.options[pendingSelect.selectedIndex];
          var pledged = row.querySelector('[name="guarantee_row_pledged_amount[]"]');
          var amount = row.querySelector('[name="guarantee_row_amount[]"]');
          if (selected && selected.getAttribute('data-amount')) {
            var val = parseFloat(selected.getAttribute('data-amount') || '0').toFixed(2);
            if (pledged && !pledged.value) pledged.value = val;
            if (amount && !amount.value) amount.value = val;
          }
        });
      }
    }

    container.querySelectorAll('[data-guarantee-row]').forEach(bindRow);
    renumberBgRows(container);

    if (addBtn && bgTemplate && bgContainer) {
      addBtn.addEventListener('click', function () {
        var clone = bgTemplate.content.firstElementChild.cloneNode(true);
        bgContainer.appendChild(clone);
        bindRow(clone);
        renumberBgRows(container);
      });
    }

    container.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-bg-remove]');
      if (!btn) return;
      var row = btn.closest('[data-bg-row]');
      if (!bgContainer || !row) return;
      var rows = bgContainer.querySelectorAll('[data-bg-row]');
      if (rows.length > 1) {
        row.remove();
        renumberBgRows(container);
      }
    });

    form.addEventListener('submit', function () {
      var rows = container.querySelectorAll('[data-guarantee-row]');
      rows.forEach(function (row, idx) {
        var fileInput = row.querySelector('[data-guarantee-file]');
        if (fileInput && fileInput.files && fileInput.files.length) {
          fileInput.setAttribute('name', 'guarantee_row_document_' + idx);
        } else if (fileInput) {
          fileInput.removeAttribute('name');
        }
      });
    });
  }

  function populatePendingBillSelect(select, options) {
    if (!select || select.dataset.populated === '1') return;
    var current = select.value;
    options.forEach(function (opt) {
      var option = document.createElement('option');
      option.value = opt.ref;
      option.textContent = opt.label;
      option.setAttribute('data-amount', opt.amount);
      select.appendChild(option);
    });
    if (current) select.value = current;
    select.dataset.populated = '1';
  }

  function updateBillSubmissionSummary(container) {
    if (!container) return;
    var submittedTotal = 0;
    var approvedTotal = 0;
    container.querySelectorAll('[data-bill-submission-row]').forEach(function (row) {
      var submitted = row.querySelector('[data-bill-submitted]');
      var approved = row.querySelector('[data-bill-approved]');
      submittedTotal += parseNum(submitted ? submitted.value : 0);
      approvedTotal += parseNum(approved ? approved.value : 0);
    });
    var pending = Math.max(submittedTotal - approvedTotal, 0);
    var summary = container.querySelector('[data-bill-submission-summary]');
    if (!summary) return;
    var submittedEl = summary.querySelector('[data-summary-submitted]');
    var approvedEl = summary.querySelector('[data-summary-approved]');
    var pendingEl = summary.querySelector('[data-summary-pending]');
    if (submittedEl) submittedEl.textContent = submittedTotal.toFixed(2);
    if (approvedEl) approvedEl.textContent = approvedTotal.toFixed(2);
    if (pendingEl) pendingEl.textContent = pending.toFixed(2);
  }

  function initBillSubmissionRows(form) {
    var container = form.querySelector('[data-bill-submission-rows]');
    if (!container) return;
    var template = container.querySelector('[data-bill-submission-row-template]');
    var addBtn = container.querySelector('[data-bill-submission-add]');

    function bindRow(row) {
      row.querySelectorAll('[data-bill-submitted], [data-bill-approved]').forEach(function (input) {
        input.addEventListener('input', function () {
          updateBillSubmissionSummary(container);
        });
      });
    }

    container.querySelectorAll('[data-bill-submission-row]').forEach(bindRow);
    updateBillSubmissionSummary(container);

    if (addBtn && template) {
      addBtn.addEventListener('click', function () {
        var clone = template.content.firstElementChild.cloneNode(true);
        container.insertBefore(clone, addBtn);
        bindRow(clone);
      });
    }

    container.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-bill-submission-remove]');
      if (!btn) return;
      var row = btn.closest('[data-bill-submission-row]');
      var rows = container.querySelectorAll('[data-bill-submission-row]');
      if (row && rows.length > 1) {
        row.remove();
        updateBillSubmissionSummary(container);
      }
    });
  }

  function initProjectForm() {
    var form = document.querySelector('[data-master-form="project"]');
    if (!form) return;
    var typeSelect = form.querySelector('[name="project_type"]');
    var applyType = function () {
      toggleSections(form, typeSelect ? typeSelect.value : 'Private');
      toggleGovCompletion(form);
    };
    if (typeSelect) {
      typeSelect.addEventListener('change', applyType);
      applyType();
    }
    form.querySelectorAll('[name="completion_mode"]').forEach(function (radio) {
      radio.addEventListener('change', function () {
        toggleGovCompletion(form);
      });
    });
    toggleGovCompletion(form);
    initSecurityDepositCalc(form);
    initGuaranteeRows(form);
  }

  function initBillPendingForm() {
    var form = document.querySelector('[data-bill-pending-form]');
    if (form) initBillSubmissionRows(form);
  }

  function fillStaffFields(data) {
    var form = document.querySelector('[data-master-form="user"]');
    if (!form || !data) return;
    var username = form.querySelector('[name="username"]');
    var employeeName = form.querySelector('[name="employee_name"]');
    var department = form.querySelector('[name="department"]');
    var designation = form.querySelector('[name="designation_id"]');
    if (username && data.employee_code) username.value = data.employee_code;
    if (employeeName) employeeName.value = data.staff_name || '';
    if (department && data.department) {
      department.value = data.department;
    }
    if (designation && data.designation_id) {
      designation.value = String(data.designation_id);
    }
  }

  function initStaffPicker() {
    var form = document.querySelector('[data-master-form="user"]');
    if (!form) return;
    var select = form.querySelector('[name="staff_id"]');
    if (!select) return;
    select.addEventListener('change', function () {
      var id = select.value;
      if (!id) return;
      fetch('/api/staff/' + encodeURIComponent(id), { credentials: 'same-origin' })
        .then(function (res) { return res.ok ? res.json() : null; })
        .then(fillStaffFields)
        .catch(function () {});
    });
  }

  function toggleMakerPanel() {
    var form = document.querySelector('[data-master-form="user"]');
    if (!form) return;
    var workflowRole = form.querySelector('[name="workflow_role"]');
    var panel = form.querySelector('[data-maker-panel]');
    if (!workflowRole || !panel) return;
    var apply = function () {
      panel.hidden = workflowRole.value !== 'Maker';
    };
    workflowRole.addEventListener('change', apply);
    apply();
  }

  function initMakerRows() {
    var container = document.querySelector('[data-maker-rows]');
    var addBtn = document.querySelector('[data-maker-add]');
    if (!container || !addBtn) return;
    var max = parseInt(container.getAttribute('data-max') || '15', 10);
    var template = container.querySelector('[data-maker-row-template]');
    if (!template) return;

    var countRows = function () {
      return container.querySelectorAll('[data-maker-row]:not([data-maker-row-template])').length;
    };

    addBtn.addEventListener('click', function () {
      if (countRows() >= max) return;
      var clone = template.cloneNode(true);
      clone.hidden = false;
      clone.removeAttribute('data-maker-row-template');
      clone.setAttribute('data-maker-row', '');
      container.appendChild(clone);
      if (countRows() >= max) addBtn.disabled = true;
    });

    container.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-maker-remove]');
      if (!btn) return;
      var row = btn.closest('[data-maker-row]');
      if (row && !row.hasAttribute('data-maker-row-template')) {
        row.remove();
        addBtn.disabled = countRows() >= max;
      }
    });

    if (countRows() >= max) addBtn.disabled = true;
  }

  function initTabPermissions() {
    var panel = document.querySelector('[data-tab-permissions-panel]');
    if (!panel) return;
    var userId = panel.querySelector('[data-perm-user-id]');
    var deptSelect = panel.querySelector('[data-perm-department]');
    var grid = panel.querySelector('[data-perm-grid]');
    var emptyHint = panel.querySelector('[data-perm-empty]');
    var statusEl = panel.querySelector('[data-perm-status]');
    var saveBtn = panel.querySelector('[data-perm-save]');
    if (!userId || !deptSelect || !grid || !saveBtn) return;

    var currentDept = '';

    function setStatus(msg, isError) {
      if (!statusEl) return;
      if (!msg) {
        statusEl.hidden = true;
        statusEl.textContent = '';
        return;
      }
      statusEl.hidden = false;
      statusEl.textContent = msg;
      statusEl.style.color = isError ? 'var(--erp-danger, #c0392b)' : '';
    }

    function renderTabs(tabs) {
      grid.innerHTML = '';
      if (!tabs || !tabs.length) {
        grid.hidden = true;
        if (emptyHint) {
          emptyHint.hidden = false;
          emptyHint.textContent = 'No modules configured for this department.';
        }
        saveBtn.disabled = true;
        return;
      }
      tabs.forEach(function (tab) {
        var label = document.createElement('label');
        var input = document.createElement('input');
        input.type = 'checkbox';
        input.name = 'perm_tab';
        input.value = tab.tab_key;
        if (tab.granted) input.checked = true;
        label.appendChild(input);
        label.appendChild(document.createTextNode(' ' + (tab.label || tab.tab_key)));
        grid.appendChild(label);
      });
      grid.hidden = false;
      if (emptyHint) emptyHint.hidden = true;
      saveBtn.disabled = false;
    }

    function loadTabs() {
      var dept = deptSelect.value;
      currentDept = dept;
      if (!dept) {
        grid.hidden = true;
        saveBtn.disabled = true;
        if (emptyHint) {
          emptyHint.hidden = false;
          emptyHint.textContent = 'Choose a department to load its module list.';
        }
        setStatus('');
        return;
      }
      setStatus('Loading modules…');
      fetch(
        '/api/settings/users/' + encodeURIComponent(userId.value) + '/department-tabs?department='
          + encodeURIComponent(dept),
        { credentials: 'same-origin' }
      )
        .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
        .then(function (result) {
          if (!result.ok) throw new Error((result.data && result.data.error) || 'Load failed');
          if (deptSelect.value !== currentDept) return;
          renderTabs(result.data.tabs || []);
          setStatus('');
        })
        .catch(function (err) {
          setStatus(err.message || 'Could not load tab list', true);
        });
    }

    deptSelect.addEventListener('change', loadTabs);

    saveBtn.addEventListener('click', function () {
      var dept = deptSelect.value;
      if (!dept) return;
      var keys = [];
      grid.querySelectorAll('input[name="perm_tab"]:checked').forEach(function (el) {
        keys.push(el.value);
      });
      saveBtn.disabled = true;
      setStatus('Saving…');
      fetch('/api/settings/users/' + encodeURIComponent(userId.value) + '/department-tabs', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ department: dept, tabs: keys }),
      })
        .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
        .then(function (result) {
          if (!result.ok) throw new Error((result.data && result.data.error) || 'Save failed');
          setStatus('Tab access saved (' + (result.data.saved || keys.length) + ' modules).');
          saveBtn.disabled = false;
        })
        .catch(function (err) {
          setStatus(err.message || 'Save failed', true);
          saveBtn.disabled = false;
        });
    });
  }

  function initProjectClientModal() {
    var projectForm = document.querySelector('[data-master-form="project"]');
    var modal = document.getElementById('new-client-modal');
    if (!projectForm || !modal) return;

    var openBtn = document.getElementById('open-new-client-modal');
    var clientSelect = projectForm.querySelector('[name="client_id"]');

    function showModal() {
      document.querySelectorAll('.erp-modal').forEach(function (other) {
        if (other !== modal) {
          other.hidden = true;
          other.setAttribute('aria-hidden', 'true');
        }
      });
      modal.hidden = false;
      modal.setAttribute('aria-hidden', 'false');
      var firstField = modal.querySelector('input:not([type="hidden"]), select, textarea');
      if (firstField) firstField.focus();
    }

    function hideModal() {
      modal.hidden = true;
      modal.setAttribute('aria-hidden', 'true');
    }

    if (openBtn) {
      openBtn.addEventListener('click', function (event) {
        event.preventDefault();
        showModal();
      });
    }

    modal.querySelectorAll('[data-modal-close]').forEach(function (control) {
      control.addEventListener('click', function (event) {
        event.preventDefault();
        hideModal();
      });
    });

    var params = new URLSearchParams(window.location.search);
    var selectedClient = params.get('select_client');
    if (selectedClient && clientSelect) {
      clientSelect.value = selectedClient;
      clientSelect.classList.add('has-value');
      if (window.history.replaceState) {
        params.delete('select_client');
        var query = params.toString();
        var nextUrl = window.location.pathname
          + (query ? '?' + query : '')
          + window.location.hash;
        window.history.replaceState({}, '', nextUrl);
      }
    }

    if (window.location.hash === '#add-project') {
      var anchor = document.getElementById('add-project');
      if (anchor) {
        window.requestAnimationFrame(function () {
          anchor.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
      }
    }

    var codeDisplay = document.getElementById('project_code_display');
    if (codeDisplay && !codeDisplay.textContent.trim()) {
      codeDisplay.textContent = '104';
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    initProjectForm();
    initBillPendingForm();
    initProjectClientModal();
    initStaffPicker();
    toggleMakerPanel();
    initMakerRows();
    initTabPermissions();
  });
})();
