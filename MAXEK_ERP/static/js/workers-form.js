(function () {
  function syncHasValue(field) {
    if (!field) return;
    field.classList.toggle('has-value', field.value !== '');
  }

  function formatRateAmount(value) {
    var num = Number(value);
    if (!Number.isFinite(num)) return '—';
    return num.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 });
  }

  function formatRateUnit(value) {
    if (value === 'Day') return 'Per Day';
    if (value === 'Hour') return 'Per Hour';
    return value || '—';
  }

  function initWorkerForm() {
    var form = document.querySelector('[data-worker-form]');
    if (!form) return;

    var isEditMode = form.getAttribute('data-edit-mode') === '1';
    var editSubId = form.getAttribute('data-subcontractor-id') || '';
    var editTrade = form.getAttribute('data-trade-name') || '';
    var editWorkerCode = form.getAttribute('data-worker-code') || '';

    var subcontractorName = form.querySelector('#worker_subcontractor_name');
    var subcontractorCode = form.querySelector('#worker_subcontractor_code');
    var subcontractorId = form.querySelector('#worker_subcontractor_id');
    var workerCodePreview = form.querySelector('#worker_code_preview');
    var tradeSelect = form.querySelector('#worker_trade_name');
    var rateSummary = form.querySelector('#worker_rate_summary');
    var rateSalary = form.querySelector('#worker_rate_salary');
    var rateHours = form.querySelector('#worker_rate_hours');
    var rateUnit = form.querySelector('#worker_rate_unit');
    var defaultWorkerCode = workerCodePreview ? workerCodePreview.value : '';
    var manpowerRates = [];

    function getSelectedSubcontractorOption() {
      var source = subcontractorName && subcontractorName.value
        ? subcontractorName
        : subcontractorCode;
      if (!source || !source.value) return null;
      return source.options[source.selectedIndex];
    }

    function syncSubcontractorHidden() {
      var value = '';
      if (subcontractorName && subcontractorName.value) {
        value = subcontractorName.value;
      } else if (subcontractorCode && subcontractorCode.value) {
        value = subcontractorCode.value;
      }
      if (subcontractorId) subcontractorId.value = value;
    }

    function syncWorkerCodePreview() {
      if (!workerCodePreview) return;
      if (isEditMode) {
        workerCodePreview.value = editWorkerCode || defaultWorkerCode;
        syncHasValue(workerCodePreview);
        return;
      }
      var option = getSelectedSubcontractorOption();
      workerCodePreview.value = option
        ? (option.getAttribute('data-next-code') || defaultWorkerCode)
        : defaultWorkerCode;
      syncHasValue(workerCodePreview);
    }

    function clearRateDisplay() {
      if (rateSalary) rateSalary.textContent = '—';
      if (rateHours) rateHours.textContent = '—';
      if (rateUnit) rateUnit.textContent = '—';
      if (rateSummary) rateSummary.hidden = true;
    }

    function clearTradeAndRates() {
      manpowerRates = [];
      if (!tradeSelect) return;
      tradeSelect.innerHTML = '<option value="">Select subcontractor first</option>';
      tradeSelect.value = '';
      tradeSelect.disabled = true;
      syncHasValue(tradeSelect);
      clearRateDisplay();
    }

    function populateTradeOptions(rates, selectedTrade) {
      if (!tradeSelect) return;
      tradeSelect.innerHTML = '<option value="">Select trade</option>';
      rates.forEach(function (rate) {
        var option = document.createElement('option');
        option.value = rate.trade_name;
        option.textContent = rate.trade_name;
        option.setAttribute('data-working-hours', rate.working_hours);
        option.setAttribute('data-salary-amount', rate.salary_amount);
        option.setAttribute('data-rate-unit', rate.rate_unit || 'Day');
        if (selectedTrade && selectedTrade === rate.trade_name) {
          option.selected = true;
        }
        tradeSelect.appendChild(option);
      });
      tradeSelect.disabled = rates.length === 0;
      if (rates.length === 0) {
        tradeSelect.innerHTML = '<option value="">No trades configured for this subcontractor</option>';
      }
      syncHasValue(tradeSelect);
      applyTradeRate();
    }

    function applyTradeRate() {
      if (!tradeSelect) return;
      var option = tradeSelect.options[tradeSelect.selectedIndex];
      if (!option || !option.value) {
        clearRateDisplay();
        return;
      }
      if (rateSalary) {
        rateSalary.textContent = formatRateAmount(option.getAttribute('data-salary-amount'));
      }
      if (rateHours) {
        rateHours.textContent = option.getAttribute('data-working-hours') || '—';
      }
      if (rateUnit) {
        rateUnit.textContent = formatRateUnit(option.getAttribute('data-rate-unit'));
      }
      if (rateSummary) rateSummary.hidden = false;
    }

    function loadManpowerRates(subcontractorIdValue, selectedTrade) {
      clearTradeAndRates();
      if (!subcontractorIdValue) return;
      fetch('/api/subcontractors/' + encodeURIComponent(subcontractorIdValue) + '/manpower-rates')
        .then(function (response) {
          if (!response.ok) throw new Error('Failed to load trades');
          return response.json();
        })
        .then(function (data) {
          manpowerRates = Array.isArray(data) ? data : [];
          populateTradeOptions(manpowerRates, selectedTrade || '');
        })
        .catch(function () {
          if (tradeSelect) {
            tradeSelect.innerHTML = '<option value="">Unable to load trades</option>';
            tradeSelect.disabled = true;
          }
        });
    }

    function syncSubcontractorFromName() {
      if (!subcontractorName || !subcontractorCode) return;
      subcontractorCode.value = subcontractorName.value;
      syncHasValue(subcontractorCode);
      syncSubcontractorHidden();
      if (!isEditMode) syncWorkerCodePreview();
      loadManpowerRates(subcontractorName.value, isEditMode ? '' : '');
    }

    function syncSubcontractorFromCode() {
      if (!subcontractorName || !subcontractorCode) return;
      subcontractorName.value = subcontractorCode.value;
      syncHasValue(subcontractorName);
      syncSubcontractorHidden();
      if (!isEditMode) syncWorkerCodePreview();
      loadManpowerRates(subcontractorCode.value, isEditMode ? '' : '');
    }

    if (subcontractorName) {
      subcontractorName.addEventListener('change', syncSubcontractorFromName);
    }
    if (subcontractorCode) {
      subcontractorCode.addEventListener('change', syncSubcontractorFromCode);
    }
    if (tradeSelect) {
      tradeSelect.addEventListener('change', applyTradeRate);
    }

    form.addEventListener('submit', function (event) {
      syncSubcontractorHidden();
      if (!subcontractorId || !subcontractorId.value) {
        event.preventDefault();
        window.alert('Select a subcontractor first.');
        return;
      }
      if (!tradeSelect || !tradeSelect.value) {
        event.preventDefault();
        window.alert('Select a trade from the subcontractor manpower rates.');
      }
    });

    if (isEditMode && editSubId) {
      syncSubcontractorHidden();
      syncWorkerCodePreview();
      loadManpowerRates(editSubId, editTrade);
      if (subcontractorName) syncHasValue(subcontractorName);
      if (subcontractorCode) syncHasValue(subcontractorCode);
    } else {
      syncWorkerCodePreview();
    }
  }

  document.addEventListener('DOMContentLoaded', initWorkerForm);
})();
