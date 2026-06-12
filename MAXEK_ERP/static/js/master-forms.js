(function () {
  function toggleSections(root, type) {
    var gov = root.querySelector('[data-project-section="government"]');
    var priv = root.querySelector('[data-project-section="private"]');
    if (!gov || !priv) return;
    var isGov = type === 'Government';
    gov.hidden = !isGov;
    priv.hidden = isGov;
  }

  function toggleGuaranteeSections(root, guaranteeType) {
    var bg = root.querySelector('[data-guarantee-section="bank"]');
    if (!bg) return;
    var show = guaranteeType === 'Bank Guarantee' || guaranteeType === 'Both';
    bg.hidden = !show;
  }

  function initProjectForm() {
    var form = document.querySelector('[data-master-form="project"]');
    if (!form) return;
    var typeSelect = form.querySelector('[name="project_type"]');
    var guaranteeSelect = form.querySelector('[name="guarantee_type"]');
    var applyType = function () {
      toggleSections(form, typeSelect ? typeSelect.value : 'Private');
    };
    var applyGuarantee = function () {
      toggleGuaranteeSections(form, guaranteeSelect ? guaranteeSelect.value : '');
    };
    if (typeSelect) {
      typeSelect.addEventListener('change', applyType);
      applyType();
    }
    if (guaranteeSelect) {
      guaranteeSelect.addEventListener('change', applyGuarantee);
      applyGuarantee();
    }
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

  document.addEventListener('DOMContentLoaded', function () {
    initProjectForm();
    initStaffPicker();
    toggleMakerPanel();
    initMakerRows();
  });
})();
