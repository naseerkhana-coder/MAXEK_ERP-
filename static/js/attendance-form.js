(function () {
  function syncHasValue(field) {
    if (!field) return;
    field.classList.toggle('has-value', field.value !== '');
  }

  function getSelectedWorkerOption(nameSelect, idSelect) {
    var source = nameSelect && nameSelect.value ? nameSelect : idSelect;
    if (!source || !source.value) return null;
    return source.options[source.selectedIndex];
  }

  function setRowVisible(row, visible) {
    if (!row) return;
    row.hidden = !visible;
    Array.prototype.forEach.call(row.querySelectorAll('select, input, textarea, button'), function (el) {
      el.disabled = !visible;
    });
  }

  function initAttendanceForm() {
    var form = document.querySelector('[data-attendance-form]');
    if (!form) return;

    var staffType = form.querySelector('#attendance_staff_type');
    var companyNameRow = form.querySelector('#attendance_company_worker_name_row');
    var companyIdRow = form.querySelector('#attendance_company_worker_id_row');
    var subNameRow = form.querySelector('#attendance_subcontractor_name_row');
    var subIdRow = form.querySelector('#attendance_subcontractor_id_row');
    var subWorkerNameRow = form.querySelector('#attendance_sub_worker_name_row');
    var subWorkerIdRow = form.querySelector('#attendance_sub_worker_id_row');
    var companyWorkerName = form.querySelector('#attendance_company_worker_name');
    var companyWorkerId = form.querySelector('#attendance_company_worker_id');
    var subcontractorName = form.querySelector('#attendance_subcontractor_name');
    var subcontractorId = form.querySelector('#attendance_subcontractor_id');
    var subWorkerName = form.querySelector('#attendance_sub_worker_name');
    var subWorkerId = form.querySelector('#attendance_sub_worker_id');
    var workerRef = form.querySelector('#attendance_worker_ref');
    var projectNumber = form.querySelector('#attendance_project_number');
    var projectName = form.querySelector('#attendance_project_name');
    var verifyPanel = form.querySelector('#attendance_worker_verify');
    var photoImg = form.querySelector('#attendance_worker_photo');
    var photoEmpty = form.querySelector('#attendance_worker_photo_empty');
    var verifyName = form.querySelector('#attendance_worker_verify_name');
    var verifyCode = form.querySelector('#attendance_worker_verify_code');
    var tradeRow = form.querySelector('#attendance_trade_row');
    var designationRow = form.querySelector('#attendance_designation_row');
    var tradeSelect = form.querySelector('#attendance_trade_id');
    var designationSelect = form.querySelector('#attendance_designation_id');
    var breakHoursInput = form.querySelector('#attendance_break_hours');
    var photosBase = form.getAttribute('data-photos-base') || '/static/photos/';
    var subcontractorOnly = form.getAttribute('data-subcontractor-only') === '1';

    function toggleTradeDesignationRows() {
      var type = staffType ? staffType.value : '';
      var isCompany = type === 'Company Staff';
      var isSub = type === 'Sub Contractor Staff';
      setRowVisible(tradeRow, isSub);
      setRowVisible(designationRow, isCompany);
      if (!isSub && tradeSelect && !tradeSelect.disabled) {
        tradeSelect.value = '';
        syncHasValue(tradeSelect);
      }
      if (!isCompany && designationSelect && !designationSelect.disabled) {
        designationSelect.value = '';
        syncHasValue(designationSelect);
      }
    }

    function setMasterFieldLocked(selectEl, rowEl, locked) {
      if (!selectEl) return;
      var addBtn = rowEl ? rowEl.querySelector('.erp-inline-action') : null;
      if (locked && selectEl.value) {
        selectEl.disabled = true;
        if (addBtn) addBtn.hidden = true;
      } else {
        selectEl.disabled = false;
        if (addBtn) addBtn.hidden = false;
      }
    }

    function applyEmployeeMasterFields(option) {
      var isCompany = staffType && staffType.value === 'Company Staff';
      var isSub = staffType && staffType.value === 'Sub Contractor Staff';
      if (!option || !option.value) {
        setMasterFieldLocked(tradeSelect, tradeRow, false);
        setMasterFieldLocked(designationSelect, designationRow, false);
        return;
      }
      var designationId = option.getAttribute('data-designation-id') || '';
      var tradeId = option.getAttribute('data-trade-id') || '';

      if (isCompany && designationSelect) {
        if (designationId) {
          designationSelect.value = designationId;
          syncHasValue(designationSelect);
          setMasterFieldLocked(designationSelect, designationRow, true);
        } else {
          designationSelect.value = '';
          syncHasValue(designationSelect);
          setMasterFieldLocked(designationSelect, designationRow, false);
        }
      }

      if (isSub && tradeSelect) {
        if (tradeId) {
          tradeSelect.value = tradeId;
          syncHasValue(tradeSelect);
          setMasterFieldLocked(tradeSelect, tradeRow, true);
        } else {
          tradeSelect.value = '';
          syncHasValue(tradeSelect);
          setMasterFieldLocked(tradeSelect, tradeRow, false);
        }
      }

      var workingHours = option.getAttribute('data-working-hours') || '';
      if (breakHoursInput && workingHours && !isNaN(parseFloat(workingHours))) {
        breakHoursInput.value = workingHours;
        syncHasValue(breakHoursInput);
      }
    }

    function initMasterModals() {
      var tradeModal = document.getElementById('new-trade-modal');
      var designationModal = document.getElementById('new-designation-modal');
      var openTradeBtn = document.getElementById('open-new-trade-modal');
      var openDesignationBtn = document.getElementById('open-new-designation-modal');

      function showModal(modal) {
        if (!modal) return;
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

      function hideModal(modal) {
        if (!modal) return;
        modal.hidden = true;
        modal.setAttribute('aria-hidden', 'true');
      }

      if (openTradeBtn && tradeModal) {
        openTradeBtn.addEventListener('click', function (event) {
          event.preventDefault();
          showModal(tradeModal);
        });
        tradeModal.querySelectorAll('[data-modal-close]').forEach(function (control) {
          control.addEventListener('click', function (event) {
            event.preventDefault();
            hideModal(tradeModal);
          });
        });
      }

      if (openDesignationBtn && designationModal) {
        openDesignationBtn.addEventListener('click', function (event) {
          event.preventDefault();
          showModal(designationModal);
        });
        designationModal.querySelectorAll('[data-modal-close]').forEach(function (control) {
          control.addEventListener('click', function (event) {
            event.preventDefault();
            hideModal(designationModal);
          });
        });
      }

      var params = new URLSearchParams(window.location.search);
      var selectedTrade = params.get('select_trade');
      var selectedDesignation = params.get('select_designation');
      if (selectedTrade && tradeSelect) {
        tradeSelect.value = selectedTrade;
        syncHasValue(tradeSelect);
        if (staffType) {
          staffType.value = 'Sub Contractor Staff';
          syncHasValue(staffType);
          toggleStaffTypeSections();
        }
      }
      if (selectedDesignation && designationSelect) {
        designationSelect.value = selectedDesignation;
        syncHasValue(designationSelect);
        if (staffType) {
          staffType.value = 'Company Staff';
          syncHasValue(staffType);
          toggleStaffTypeSections();
        }
      }
      if ((selectedTrade || selectedDesignation) && window.history.replaceState) {
        if (selectedTrade) params.delete('select_trade');
        if (selectedDesignation) params.delete('select_designation');
        var query = params.toString();
        var nextUrl = window.location.pathname
          + (query ? '?' + query : '')
          + window.location.hash;
        window.history.replaceState({}, '', nextUrl);
      }
    }

    function activeWorkerSelects() {
      if (staffType && staffType.value === 'Sub Contractor Staff') {
        return { nameSelect: subWorkerName, idSelect: subWorkerId };
      }
      if (staffType && staffType.value === 'Company Staff') {
        return { nameSelect: companyWorkerName, idSelect: companyWorkerId };
      }
      return { nameSelect: null, idSelect: null };
    }

    function syncWorkerRef() {
      var active = activeWorkerSelects();
      var value = '';
      if (active.nameSelect && active.nameSelect.value) {
        value = active.nameSelect.value;
      } else if (active.idSelect && active.idSelect.value) {
        value = active.idSelect.value;
      }
      if (workerRef) workerRef.value = value;
    }

    function updateWorkerPhoto() {
      var active = activeWorkerSelects();
      var option = getSelectedWorkerOption(active.nameSelect, active.idSelect);
      if (!option || !option.value) {
        if (verifyPanel) verifyPanel.hidden = true;
        applyEmployeeMasterFields(null);
        syncWorkerRef();
        return;
      }

      var label = option.getAttribute('data-worker-label') || option.textContent.trim();
      var code = option.getAttribute('data-worker-code') || '';
      var photoFile = option.getAttribute('data-worker-photo') || '';

      if (verifyPanel) verifyPanel.hidden = false;
      if (verifyName) verifyName.textContent = label;
      if (verifyCode) verifyCode.textContent = code ? 'ID: ' + code : '';

      if (photoFile && photoImg) {
        photoImg.src = photosBase + photoFile;
        photoImg.alt = label + ' photo';
        photoImg.hidden = false;
        if (photoEmpty) photoEmpty.hidden = true;
      } else {
        if (photoImg) {
          photoImg.removeAttribute('src');
          photoImg.hidden = true;
        }
        if (photoEmpty) photoEmpty.hidden = false;
      }
      syncWorkerRef();
      applyEmployeeMasterFields(option);
    }

    function syncCompanyWorkerFromName() {
      if (!companyWorkerName || !companyWorkerId) return;
      companyWorkerId.value = companyWorkerName.value;
      syncHasValue(companyWorkerId);
      updateWorkerPhoto();
    }

    function syncCompanyWorkerFromId() {
      if (!companyWorkerName || !companyWorkerId) return;
      companyWorkerName.value = companyWorkerId.value;
      syncHasValue(companyWorkerName);
      updateWorkerPhoto();
    }

    function syncSubcontractorFromName() {
      if (!subcontractorName || !subcontractorId) return;
      subcontractorId.value = subcontractorName.value;
      syncHasValue(subcontractorId);
      filterSubcontractorWorkers();
    }

    function syncSubcontractorFromId() {
      if (!subcontractorName || !subcontractorId) return;
      subcontractorName.value = subcontractorId.value;
      syncHasValue(subcontractorName);
      filterSubcontractorWorkers();
    }

    function syncSubWorkerFromName() {
      if (!subWorkerName || !subWorkerId) return;
      subWorkerId.value = subWorkerName.value;
      syncHasValue(subWorkerId);
      updateWorkerPhoto();
    }

    function syncSubWorkerFromId() {
      if (!subWorkerName || !subWorkerId) return;
      subWorkerName.value = subWorkerId.value;
      syncHasValue(subWorkerName);
      updateWorkerPhoto();
    }

    function filterSubcontractorWorkers() {
      var isSub = staffType && staffType.value === 'Sub Contractor Staff';
      if (!isSub) {
        setRowVisible(subWorkerNameRow, false);
        setRowVisible(subWorkerIdRow, false);
        return;
      }

      var selectedSubId = subcontractorName ? subcontractorName.value : '';
      var hasSub = !!selectedSubId;

      [subWorkerName, subWorkerId].forEach(function (select) {
        if (!select) return;
        Array.prototype.forEach.call(select.options, function (option, index) {
          if (index === 0) {
            option.hidden = false;
            return;
          }
          var subId = option.getAttribute('data-subcontractor-id') || '';
          var matches = hasSub && subId === selectedSubId;
          option.hidden = !matches;
          if (!matches && option.selected) {
            option.selected = false;
          }
        });
        if (!hasSub) {
          select.value = '';
        } else if (select.value) {
          var current = select.options[select.selectedIndex];
          if (!current || current.hidden) {
            select.value = '';
          }
        }
        syncHasValue(select);
      });

      setRowVisible(subWorkerNameRow, hasSub);
      setRowVisible(subWorkerIdRow, hasSub);
      updateWorkerPhoto();
    }

    function clearCompanyWorkerSelection() {
      if (companyWorkerName) {
        companyWorkerName.value = '';
        syncHasValue(companyWorkerName);
      }
      if (companyWorkerId) {
        companyWorkerId.value = '';
        syncHasValue(companyWorkerId);
      }
    }

    function clearSubcontractorSelection() {
      if (subcontractorName) {
        subcontractorName.value = '';
        syncHasValue(subcontractorName);
      }
      if (subcontractorId) {
        subcontractorId.value = '';
        syncHasValue(subcontractorId);
      }
      if (subWorkerName) {
        subWorkerName.value = '';
        syncHasValue(subWorkerName);
      }
      if (subWorkerId) {
        subWorkerId.value = '';
        syncHasValue(subWorkerId);
      }
    }

    function toggleStaffTypeSections() {
      var type = staffType ? staffType.value : '';
      var isCompany = type === 'Company Staff';
      var isSub = type === 'Sub Contractor Staff';

      setRowVisible(companyNameRow, isCompany);
      setRowVisible(companyIdRow, isCompany);
      setRowVisible(subNameRow, isSub);
      setRowVisible(subIdRow, isSub);

      if (!isCompany) clearCompanyWorkerSelection();
      if (!isSub) {
        clearSubcontractorSelection();
        setRowVisible(subWorkerNameRow, false);
        setRowVisible(subWorkerIdRow, false);
      } else {
        filterSubcontractorWorkers();
      }

      if (verifyPanel && !isCompany && !isSub) verifyPanel.hidden = true;
      setMasterFieldLocked(tradeSelect, tradeRow, false);
      setMasterFieldLocked(designationSelect, designationRow, false);
      toggleTradeDesignationRows();
      updateWorkerPhoto();
    }

    function syncProjectFromNumber() {
      if (!projectNumber || !projectName) return;
      projectName.value = projectNumber.value;
      syncHasValue(projectName);
    }

    function syncProjectFromName() {
      if (!projectNumber || !projectName) return;
      projectNumber.value = projectName.value;
      syncHasValue(projectNumber);
    }

    if (staffType) {
      staffType.addEventListener('change', toggleStaffTypeSections);
    }
    if (companyWorkerName) {
      companyWorkerName.addEventListener('change', syncCompanyWorkerFromName);
    }
    if (companyWorkerId) {
      companyWorkerId.addEventListener('change', syncCompanyWorkerFromId);
    }
    if (subcontractorName) {
      subcontractorName.addEventListener('change', syncSubcontractorFromName);
    }
    if (subcontractorId) {
      subcontractorId.addEventListener('change', syncSubcontractorFromId);
    }
    if (subWorkerName) {
      subWorkerName.addEventListener('change', syncSubWorkerFromName);
    }
    if (subWorkerId) {
      subWorkerId.addEventListener('change', syncSubWorkerFromId);
    }
    if (projectNumber) {
      projectNumber.addEventListener('change', syncProjectFromNumber);
    }
    if (projectName) {
      projectName.addEventListener('change', syncProjectFromName);
    }

    form.addEventListener('submit', function (event) {
      syncWorkerRef();
      form.querySelectorAll('select, input, textarea').forEach(function (el) {
        el.disabled = false;
      });
      if (!workerRef || !workerRef.value) {
        event.preventDefault();
        window.alert('Select a worker before saving attendance.');
      }
    });

    var editWorkerRef = form.getAttribute('data-edit-worker-ref') || '';
    var editStaffType = form.getAttribute('data-edit-staff-type') || '';
    var editSubcontractorId = form.getAttribute('data-edit-subcontractor-id') || '';

    if (editStaffType && staffType) {
      staffType.value = editStaffType;
      syncHasValue(staffType);
      toggleStaffTypeSections();
      if (editStaffType === 'Company Staff' && editWorkerRef) {
        if (companyWorkerName) companyWorkerName.value = editWorkerRef;
        syncCompanyWorkerFromName();
      } else if (editStaffType === 'Sub Contractor Staff') {
        if (subcontractorName && editSubcontractorId) {
          subcontractorName.value = editSubcontractorId;
          syncSubcontractorFromName();
        }
        if (subWorkerName && editWorkerRef) {
          subWorkerName.value = editWorkerRef;
          syncSubWorkerFromName();
        }
      }
    } else if (subcontractorOnly && staffType) {
      staffType.value = 'Sub Contractor Staff';
      syncHasValue(staffType);
      toggleStaffTypeSections();
    } else if (staffType && staffType.value) {
      toggleStaffTypeSections();
    }

    if (projectName && projectName.value) {
      syncProjectFromName();
    } else if (projectNumber && projectNumber.value) {
      syncProjectFromNumber();
    }

    initMasterModals();
    if (!(staffType && staffType.value) && !subcontractorOnly) {
      toggleTradeDesignationRows();
    }
    initSubcontractorBulkAttendance();
  }

  function initSubcontractorBulkAttendance() {
    var bulkForm = document.querySelector('[data-sub-bulk-form]');
    if (!bulkForm) return;

    var singleCard = document.getElementById('add-attendance');
    var bulkCard = document.getElementById('sub-bulk-attendance');
    var modeSingleBtn = document.getElementById('sub_att_mode_single');
    var modeBulkBtn = document.getElementById('sub_att_mode_bulk');
    var subSelect = bulkForm.querySelector('#bulk_subcontractor_id');
    var tradeSelect = bulkForm.querySelector('#bulk_trade_id');
    var tbody = bulkForm.querySelector('#bulk_worker_tbody');
    var checklistWrap = bulkForm.querySelector('#bulk_worker_checklist_wrap');
    var selectAll = bulkForm.querySelector('#bulk_select_all');
    var workerCount = bulkForm.querySelector('#bulk_worker_count');
    var projectNumber = bulkForm.querySelector('#bulk_project_number');
    var projectName = bulkForm.querySelector('#bulk_project_name');
    var defaultStatus = bulkForm.querySelector('#bulk_default_status');
    var applyBtn = bulkForm.querySelector('#bulk_apply_to_ticked');
    var statusOptions = ['Present', 'Absent', 'Half Day', 'Leave'];
    var workersCache = [];

    function setSubMode(mode) {
      var isBulk = mode === 'bulk';
      if (singleCard) singleCard.hidden = isBulk;
      if (bulkCard) bulkCard.hidden = !isBulk;
      if (modeSingleBtn) {
        modeSingleBtn.classList.toggle('erp-btn-primary', !isBulk);
        modeSingleBtn.classList.toggle('erp-btn-ghost', isBulk);
      }
      if (modeBulkBtn) {
        modeBulkBtn.classList.toggle('erp-btn-primary', isBulk);
        modeBulkBtn.classList.toggle('erp-btn-ghost', !isBulk);
      }
      if (isBulk && window.location.hash === '#sub-bulk-attendance') {
        bulkCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }

    if (modeSingleBtn) {
      modeSingleBtn.addEventListener('click', function () {
        setSubMode('single');
        if (window.history.replaceState) {
          window.history.replaceState({}, '', window.location.pathname + window.location.search + '#add-attendance');
        }
      });
    }
    if (modeBulkBtn) {
      modeBulkBtn.addEventListener('click', function () {
        setSubMode('bulk');
        if (window.history.replaceState) {
          window.history.replaceState({}, '', window.location.pathname + window.location.search + '#sub-bulk-attendance');
        }
      });
    }

    if (window.location.hash === '#sub-bulk-attendance') {
      setSubMode('bulk');
    } else {
      setSubMode('single');
    }

    function syncProjectFromNumber() {
      if (!projectNumber || !projectName) return;
      projectName.value = projectNumber.value;
      syncHasValue(projectName);
    }

    function syncProjectFromName() {
      if (!projectNumber || !projectName) return;
      projectNumber.value = projectName.value;
      syncHasValue(projectNumber);
    }

    if (projectNumber) projectNumber.addEventListener('change', syncProjectFromNumber);
    if (projectName) projectName.addEventListener('change', syncProjectFromName);

    function renderStatusSelect(workerId, selected) {
      var html = '<select name="bulk_status_' + workerId + '" class="bulk-row-status">';
      statusOptions.forEach(function (st) {
        html += '<option value="' + st + '"' + (st === selected ? ' selected' : '') + '>' + st + '</option>';
      });
      html += '</select>';
      return html;
    }

    function updateWorkerCount() {
      if (!workerCount || !tbody) return;
      var boxes = tbody.querySelectorAll('input[name="bulk_workers"]:checked');
      workerCount.textContent = boxes.length + ' of ' + workersCache.length + ' selected';
    }

    function renderWorkerRows(workers) {
      workersCache = workers || [];
      if (!tbody) return;
      tbody.innerHTML = '';
      if (!workersCache.length) {
        if (checklistWrap) checklistWrap.hidden = true;
        return;
      }
      workersCache.forEach(function (worker) {
        var tr = document.createElement('tr');
        tr.innerHTML =
          '<td><input type="checkbox" name="bulk_workers" value="' + worker.id + '" checked></td>' +
          '<td>' + (worker.worker_name || '—') + '</td>' +
          '<td>' + (worker.worker_code || '—') + '</td>' +
          '<td>' + (worker.trade_name || worker.designation || '—') + '</td>' +
          '<td>' + renderStatusSelect(worker.id, defaultStatus ? defaultStatus.value : 'Present') + '</td>';
        tbody.appendChild(tr);
      });
      if (checklistWrap) checklistWrap.hidden = false;
      if (selectAll) selectAll.checked = true;
      tbody.querySelectorAll('input[name="bulk_workers"]').forEach(function (box) {
        box.addEventListener('change', updateWorkerCount);
      });
      updateWorkerCount();
    }

    function loadTrades(subId) {
      if (!tradeSelect) return Promise.resolve();
      tradeSelect.innerHTML = '<option value="">Loading trades...</option>';
      tradeSelect.disabled = true;
      return fetch('/api/subcontractors/' + subId + '/attendance-trades')
        .then(function (res) { return res.json(); })
        .then(function (trades) {
          tradeSelect.innerHTML = '<option value="">Select trade</option>';
          trades.forEach(function (trade) {
            var opt = document.createElement('option');
            opt.value = trade.trade_id || trade.trade_name;
            opt.textContent = trade.trade_name;
            opt.setAttribute('data-trade-name', trade.trade_name);
            if (trade.trade_id) {
              opt.setAttribute('data-trade-id', trade.trade_id);
            }
            tradeSelect.appendChild(opt);
          });
          tradeSelect.disabled = false;
          syncHasValue(tradeSelect);
        })
        .catch(function () {
          tradeSelect.innerHTML = '<option value="">Select trade</option>';
          tradeSelect.disabled = false;
        });
    }

    function loadWorkers(subId, tradeId, tradeName) {
      var url = '/api/subcontractors/' + subId + '/attendance-workers?';
      if (tradeId) {
        url += 'trade_id=' + encodeURIComponent(tradeId);
      } else if (tradeName) {
        url += 'trade_name=' + encodeURIComponent(tradeName);
      }
      return fetch(url)
        .then(function (res) { return res.json(); })
        .then(function (workers) {
          renderWorkerRows(workers);
        })
        .catch(function () {
          renderWorkerRows([]);
        });
    }

    if (subSelect) {
      subSelect.addEventListener('change', function () {
        var subId = subSelect.value;
        renderWorkerRows([]);
        if (!subId) {
          if (tradeSelect) {
            tradeSelect.innerHTML = '<option value="">Select trade</option>';
            tradeSelect.disabled = true;
          }
          return;
        }
        loadTrades(subId);
      });
    }

    if (tradeSelect) {
      tradeSelect.addEventListener('change', function () {
        var subId = subSelect ? subSelect.value : '';
        if (!subId || !tradeSelect.value) {
          renderWorkerRows([]);
          return;
        }
        var opt = tradeSelect.options[tradeSelect.selectedIndex];
        var tradeId = opt.getAttribute('data-trade-id') || '';
        var tradeName = opt.getAttribute('data-trade-name') || tradeSelect.value;
        loadWorkers(subId, tradeId, tradeName);
      });
    }

    if (selectAll && tbody) {
      selectAll.addEventListener('change', function () {
        tbody.querySelectorAll('input[name="bulk_workers"]').forEach(function (box) {
          box.checked = selectAll.checked;
        });
        updateWorkerCount();
      });
    }

    if (applyBtn) {
      applyBtn.addEventListener('click', function () {
        var status = defaultStatus ? defaultStatus.value : 'Present';
        tbody.querySelectorAll('tr').forEach(function (row) {
          var box = row.querySelector('input[name="bulk_workers"]');
          var statusEl = row.querySelector('.bulk-row-status');
          if (box && box.checked && statusEl) {
            statusEl.value = status;
          }
        });
      });
    }

    bulkForm.addEventListener('submit', function (event) {
      var checked = tbody ? tbody.querySelectorAll('input[name="bulk_workers"]:checked') : [];
      if (!checked.length) {
        event.preventDefault();
        window.alert('Select at least one worker to save bulk attendance.');
      }
    });

    var dateInput = bulkForm.querySelector('#bulk_attendance_date');
    if (dateInput && !dateInput.value) {
      var today = new Date();
      var mm = String(today.getMonth() + 1).padStart(2, '0');
      var dd = String(today.getDate()).padStart(2, '0');
      dateInput.value = today.getFullYear() + '-' + mm + '-' + dd;
      syncHasValue(dateInput);
    }
  }

  document.addEventListener('DOMContentLoaded', initAttendanceForm);
})();
