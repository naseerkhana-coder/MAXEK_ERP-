document.addEventListener('DOMContentLoaded', function () {
  const category = document.getElementById('worker_category');
  const subcontractorRow = document.getElementById('subcontractor-row');
  const workerCodePreview = document.getElementById('worker_code_preview');
  const subcontractorSelect = document.getElementById('worker_subcontractor_id');
  const defaultWorkerCode = workerCodePreview ? workerCodePreview.value : '';

  function syncWorkerCode() {
    if (!workerCodePreview) return;
    if (category && category.value === 'Sub Contractor Staff' && subcontractorSelect) {
      const option = subcontractorSelect.options[subcontractorSelect.selectedIndex];
      workerCodePreview.value = option?.dataset.nextCode || defaultWorkerCode;
      return;
    }
    workerCodePreview.value = defaultWorkerCode;
  }

  if (category && subcontractorRow) {
    function toggleSubcontractor() {
      const isSubcontractor = category.value === 'Sub Contractor Staff';
      subcontractorRow.style.display = isSubcontractor ? '' : 'none';
      if (!isSubcontractor && subcontractorSelect) {
        subcontractorSelect.value = '';
      }
      syncWorkerCode();
    }
    category.addEventListener('change', toggleSubcontractor);
    toggleSubcontractor();
  }

  if (workerCodePreview && subcontractorSelect) {
    subcontractorSelect.addEventListener('change', syncWorkerCode);
  }
});
