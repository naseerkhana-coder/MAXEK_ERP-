document.addEventListener('DOMContentLoaded', function () {
  var actionModal = document.getElementById('action-modal');
  var reopenModal = document.getElementById('reopen-modal');

  function bindModal(modal, formId, cancelId, openFn) {
    if (!modal) return;
    var form = document.getElementById(formId);
    var cancelBtn = document.getElementById(cancelId);
    var backdrop = modal.querySelector('.reject-modal-backdrop');
    function closeModal() { modal.hidden = true; }
    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);
    if (backdrop) backdrop.addEventListener('click', closeModal);
    return { form: form, closeModal: closeModal, open: openFn };
  }

  var actionForm = document.getElementById('action-form');
  var actionTitle = document.getElementById('action-modal-title');
  var actionApproval = document.getElementById('action-approval-id');
  var actionType = document.getElementById('action-type');
  var actionRole = document.getElementById('action-role');
  var actionComment = document.getElementById('action-comment');
  var actionLabel = document.getElementById('action-comment-label');
  var actionSubmit = document.getElementById('action-submit');

  function openActionModal(approvalId, role, action) {
    if (!actionModal) return;
    actionApproval.value = approvalId;
    actionRole.value = role || 'checker';
    actionType.value = action;
    actionComment.value = '';
    var titles = {
      verify: 'Verify — Optional Comment',
      approve: 'Approve — Optional Comment',
      reject: 'Reject — Reason Required'
    };
    var labels = {
      verify: 'Verify Comment (optional)',
      approve: 'Approve Comment (optional)',
      reject: 'Reject Reason (mandatory)'
    };
    actionTitle.textContent = titles[action] || 'Workflow Action';
    actionLabel.textContent = labels[action] || 'Comment';
    actionComment.required = action === 'reject';
    actionSubmit.textContent = action === 'reject' ? 'Reject' : (action === 'verify' ? 'Verify' : 'Approve');
    actionModal.hidden = false;
    actionComment.focus();
  }

  bindModal(actionModal, 'action-form', 'action-cancel');

  document.querySelectorAll('.js-action-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      openActionModal(
        btn.getAttribute('data-approval-id'),
        btn.getAttribute('data-role'),
        btn.getAttribute('data-action')
      );
    });
  });

  document.querySelectorAll('.js-reject-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      openActionModal(
        btn.getAttribute('data-approval-id'),
        btn.getAttribute('data-role'),
        'reject'
      );
    });
  });

  if (actionForm) {
    actionForm.addEventListener('submit', function (e) {
      if (actionType.value === 'reject' && !actionComment.value.trim()) {
        e.preventDefault();
        actionComment.focus();
      }
    });
  }

  var reopenForm = document.getElementById('reopen-form');
  var reopenApproval = document.getElementById('reopen-approval-id');
  var reopenReason = document.getElementById('reopen-reason');

  bindModal(reopenModal, 'reopen-form', 'reopen-cancel');

  document.querySelectorAll('.js-reopen-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (!reopenModal) return;
      reopenApproval.value = btn.getAttribute('data-approval-id');
      reopenReason.value = '';
      reopenModal.hidden = false;
      reopenReason.focus();
    });
  });

  if (reopenForm) {
    reopenForm.addEventListener('submit', function (e) {
      if (!reopenReason.value.trim()) {
        e.preventDefault();
        reopenReason.focus();
      }
    });
  }

  var deleteModal = document.getElementById('delete-modal');
  var deleteForm = document.getElementById('delete-form');
  var deleteRecordId = document.getElementById('delete-record-id');
  var deleteTable = document.getElementById('delete-table');
  var deleteModuleId = document.getElementById('delete-module-id');
  var deleteRedirect = document.getElementById('delete-redirect-to');

  bindModal(deleteModal, 'delete-form', 'delete-cancel');

  document.querySelectorAll('.js-delete-record').forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (!deleteModal) return;
      deleteRecordId.value = btn.getAttribute('data-record-id') || '';
      deleteTable.value = btn.getAttribute('data-delete-table') || '';
      deleteModuleId.value = btn.getAttribute('data-module-id') || '';
      deleteRedirect.value = btn.getAttribute('data-redirect-to') || 'dashboard';
      deleteModal.hidden = false;
    });
  });

  document.querySelectorAll('[data-transaction-tabs]').forEach(function (wrap) {
    wrap.querySelectorAll('.transaction-tab').forEach(function (tab) {
      tab.addEventListener('click', function () {
        var target = tab.getAttribute('data-tab');
        wrap.querySelectorAll('.transaction-tab').forEach(function (t) { t.classList.remove('active'); });
        wrap.querySelectorAll('.transaction-tab-panel').forEach(function (p) { p.classList.remove('active'); });
        tab.classList.add('active');
        var panel = wrap.querySelector('[data-panel="' + target + '"]');
        if (panel) panel.classList.add('active');
      });
    });
  });
});
