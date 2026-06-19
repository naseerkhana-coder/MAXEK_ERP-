(function () {
  function syncHasValue(field) {
    if (!field) return;
    field.classList.toggle('has-value', field.value !== '');
  }

  function initMonthlyAttendanceForm() {
    var form = document.querySelector('[data-monthly-attendance-form]');
    if (!form) return;

    form.querySelectorAll('select, input').forEach(function (field) {
      syncHasValue(field);
      field.addEventListener('change', function () {
        syncHasValue(field);
      });
      field.addEventListener('input', function () {
        syncHasValue(field);
      });
    });

    var monthInput = form.querySelector('#monthly_year_month');
    if (monthInput && !monthInput.value) {
      var now = new Date();
      var ym = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
      monthInput.value = ym;
      syncHasValue(monthInput);
    }
  }

  document.addEventListener('DOMContentLoaded', initMonthlyAttendanceForm);
})();
