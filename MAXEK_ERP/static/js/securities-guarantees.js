(function () {
  var TYPE_SECTIONS = {
    'Treasury Deposit': [
      'common-financial', 'treasury', 'dates', 'dates-deposit', 'dates-release',
      'interest', 'purpose', 'upload'
    ],
    'Security Deposit': [
      'common-financial', 'treasury', 'dates', 'dates-deposit', 'dates-release',
      'interest', 'purpose', 'upload'
    ],
    'Performance Bank Guarantee': [
      'common-financial', 'bg', 'dates', 'dates-bg', 'purpose', 'upload'
    ],
    'Additional Bank Guarantee': [
      'common-financial', 'bg', 'dates', 'dates-bg', 'purpose', 'upload'
    ],
    'Pending Bill Retention': [
      'retention', 'dates', 'dates-deposit', 'dates-release', 'common-financial', 'purpose'
    ],
    'EMD': [
      'common-financial', 'emd', 'dates', 'dates-deposit', 'dates-bg', 'purpose', 'upload'
    ]
  };

  function syncHasValue(field) {
    if (!field) return;
    field.classList.toggle('has-value', field.value !== '');
  }

  function daysBetween(start, end) {
    if (!start || !end) return 0;
    var s = new Date(start);
    var e = new Date(end);
    if (isNaN(s.getTime()) || isNaN(e.getTime())) return 0;
    return Math.max(Math.round((e - s) / 86400000), 0);
  }

  function calcInterest() {
    var principal = parseFloat(document.getElementById('sg_deposit_amount')?.value || 0);
    var rate = parseFloat(document.getElementById('sg_interest_rate')?.value || 0);
    var issue = document.querySelector('[name="issue_date"]')?.value
      || document.querySelector('[name="deposit_date"]')?.value;
    var maturity = document.querySelector('[name="maturity_date"]')?.value
      || document.querySelector('[name="expiry_date"]')?.value;
    var interestField = document.getElementById('sg_interest_amount');
    var totalField = document.getElementById('sg_total_recoverable');
    if (!interestField || !rate || !principal) return;
    var days = daysBetween(issue, maturity);
    var interest = Math.round(principal * rate / 100 * days / 365 * 100) / 100;
    interestField.value = interest || '';
    syncHasValue(interestField);
    if (totalField) {
      totalField.value = Math.round((principal + interest) * 100) / 100;
      syncHasValue(totalField);
    }
  }

  function calcRetention() {
    var bill = parseFloat(document.getElementById('sg_bill_amount')?.value || 0);
    var pct = parseFloat(document.getElementById('sg_retention_percent')?.value || 0);
    var retentionField = document.getElementById('sg_retention_amount');
    var depositField = document.getElementById('sg_deposit_amount');
    if (!retentionField || !bill || !pct) return;
    var amt = Math.round(bill * pct / 100 * 100) / 100;
    retentionField.value = amt;
    syncHasValue(retentionField);
    if (depositField && !depositField.value) {
      depositField.value = amt;
      syncHasValue(depositField);
    }
  }

  function applyTypeSections(typeSelect) {
    var type = typeSelect ? typeSelect.value : '';
    var allowed = TYPE_SECTIONS[type] || [];
    document.querySelectorAll('[data-sg-section]').forEach(function (el) {
      var section = el.getAttribute('data-sg-section');
      var show = allowed.indexOf(section) !== -1;
      el.hidden = !show;
      el.querySelectorAll('input, select, textarea').forEach(function (input) {
        if (!show) {
          input.removeAttribute('required');
        }
      });
    });
    var deposit = document.getElementById('sg_deposit_amount');
    if (deposit) {
      if (type === 'Pending Bill Retention') {
        deposit.removeAttribute('required');
      } else {
        deposit.setAttribute('required', 'required');
      }
    }
  }

  function loadProjectDetails(projectId) {
    if (!projectId) return;
    fetch('/api/projects/' + projectId + '/security-details')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) return;
        var map = {
          sg_client_name: data.client_name,
          sg_agreement_number: data.agreement_number,
          sg_agreement_date: data.agreement_date,
          sg_work_order_number: data.work_order_number,
          sg_contract_value: data.contract_value,
          sg_project_name: data.project_name,
          sg_project_code_hidden: data.project_code
        };
        Object.keys(map).forEach(function (id) {
          var el = document.getElementById(id);
          if (el && map[id] !== undefined) {
            el.value = map[id];
            syncHasValue(el);
          }
        });
      })
      .catch(function () {});
  }

  function initSecuritiesForm() {
    var form = document.querySelector('[data-securities-form]');
    if (!form) return;

    var typeSelect = form.querySelector('#sg_security_type');
    var projectCode = form.querySelector('#sg_project_code');
    var projectId = form.querySelector('#sg_project_id');

    function syncProjectFromCode() {
      if (!projectCode || !projectId) return;
      projectId.value = projectCode.value;
      syncHasValue(projectId);
      loadProjectDetails(projectCode.value);
    }

    function syncProjectFromId() {
      if (!projectCode || !projectId) return;
      projectCode.value = projectId.value;
      syncHasValue(projectCode);
      loadProjectDetails(projectId.value);
    }

    if (typeSelect) {
      applyTypeSections(typeSelect);
      typeSelect.addEventListener('change', function () {
        applyTypeSections(typeSelect);
      });
    }

    if (projectCode) projectCode.addEventListener('change', syncProjectFromCode);
    if (projectId) projectId.addEventListener('change', syncProjectFromId);

    ['sg_deposit_amount', 'sg_interest_rate'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener('input', calcInterest);
    });
    ['issue_date', 'deposit_date', 'maturity_date', 'expiry_date'].forEach(function (name) {
      var el = form.querySelector('[name="' + name + '"]');
      if (el) el.addEventListener('change', calcInterest);
    });
    ['sg_bill_amount', 'sg_retention_percent'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener('input', calcRetention);
    });

    if (projectId && projectId.value) {
      loadProjectDetails(projectId.value);
    }
  }

  document.addEventListener('DOMContentLoaded', initSecuritiesForm);
})();
