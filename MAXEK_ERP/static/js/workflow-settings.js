document.addEventListener('DOMContentLoaded', function () {
  var modeSelect = document.getElementById('workflow_mode');
  var makerField = document.getElementById('field-maker');
  var checkerField = document.getElementById('field-checker');
  var approverField = document.getElementById('field-approver');
  var makerSelect = document.getElementById('maker_designation_id');
  var checkerSelect = document.getElementById('checker_designation_id');
  var approverSelect = document.getElementById('approver_designation_id');

  function applyModeRules() {
    if (!modeSelect) return;
    var mode = modeSelect.value;
    var needsMaker = mode !== 'checker_approver_only';
    var needsChecker = mode !== 'maker_only';
    var needsApprover = mode === 'full' || mode === 'checker_approver_only';

    if (makerField) makerField.style.display = needsMaker ? '' : 'none';
    if (checkerField) checkerField.style.display = needsChecker ? '' : 'none';
    if (approverField) approverField.style.display = needsApprover ? '' : 'none';

    if (makerSelect) makerSelect.required = mode === 'maker_only' || mode === 'maker_checker' || mode === 'full';
    if (checkerSelect) checkerSelect.required = needsChecker && mode !== 'maker_only';
    if (approverSelect) approverSelect.required = needsApprover;
  }

  function loadModule(opt) {
    if (!opt || !opt.value) return;
    if (makerSelect) makerSelect.value = opt.dataset.maker || '';
    if (checkerSelect) checkerSelect.value = opt.dataset.checker || '';
    if (approverSelect) approverSelect.value = opt.dataset.approver || '';
    if (modeSelect) modeSelect.value = opt.dataset.mode || 'full';
    applyModeRules();
  }

  var moduleSelect = document.getElementById('module_id');
  if (moduleSelect) {
    moduleSelect.addEventListener('change', function () {
      loadModule(this.options[this.selectedIndex]);
    });
  }
  if (modeSelect) {
    modeSelect.addEventListener('change', applyModeRules);
    applyModeRules();
  }

  document.querySelectorAll('.js-edit-matrix').forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (!moduleSelect) return;
      moduleSelect.value = btn.dataset.module;
      if (makerSelect) makerSelect.value = btn.dataset.maker || '';
      if (checkerSelect) checkerSelect.value = btn.dataset.checker || '';
      if (approverSelect) approverSelect.value = btn.dataset.approver || '';
      if (modeSelect) modeSelect.value = btn.dataset.mode || 'full';
      applyModeRules();
      document.getElementById('configure-form').scrollIntoView({ behavior: 'smooth' });
    });
  });
});
