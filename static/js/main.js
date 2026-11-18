/* examsmanager — portal front-end behaviour */
(function () {
  'use strict';

  /* ---- flash messages: manual close + auto dismiss ---- */
  document.querySelectorAll('.flash').forEach(function (flash) {
    var close = flash.querySelector('.flash-close');
    function dismiss() {
      flash.classList.add('is-hiding');
      window.setTimeout(function () { flash.remove(); }, 380);
    }
    if (close) { close.addEventListener('click', dismiss); }
    window.setTimeout(dismiss, 6000);
  });

  /* ---- confirmation prompts on destructive actions ---- */
  document.querySelectorAll('form[data-confirm]').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      var message = form.getAttribute('data-confirm') || 'Are you sure?';
      if (!window.confirm(message)) { event.preventDefault(); }
    });
  });
  document.querySelectorAll('[data-confirm-link]').forEach(function (link) {
    link.addEventListener('click', function (event) {
      var message = link.getAttribute('data-confirm-link') || 'Are you sure?';
      if (!window.confirm(message)) { event.preventDefault(); }
    });
  });

  /* ---- client-side table filtering (admin/examiner lists) ---- */
  document.querySelectorAll('[data-filter-table]').forEach(function (input) {
    var table = document.querySelector(input.getAttribute('data-filter-table'));
    if (!table) { return; }
    input.addEventListener('input', function () {
      var term = input.value.trim().toLowerCase();
      table.querySelectorAll('tbody tr').forEach(function (row) {
        row.style.display = row.textContent.toLowerCase().indexOf(term) !== -1 ? '' : 'none';
      });
    });
  });

  /* ---- home register panel: role radio -> registration page ---- */
  var roleButton = document.querySelector('[data-role-redirect]');
  if (roleButton) {
    roleButton.addEventListener('click', function () {
      var checked = document.querySelector('input[name="register-role"]:checked');
      var role = checked ? checked.value : 'student';
      window.location.href = '/auth/register/' + role;
    });
  }

  /* ---- date inputs never allow past dates ---- */
  document.querySelectorAll('input[type="date"]').forEach(function (input) {
    if (!input.min) {
      var today = new Date();
      var mm = String(today.getMonth() + 1).padStart(2, '0');
      var dd = String(today.getDate()).padStart(2, '0');
      input.min = today.getFullYear() + '-' + mm + '-' + dd;
    }
  });

  /* ---- student slot picker: highlight card and build booking URL ---- */
  document.querySelectorAll('form[data-slot-form]').forEach(function (form) {
    var base = form.getAttribute('data-book-base') || '';
    form.addEventListener('submit', function (event) {
      var checked = form.querySelector('input[name="slot_choice"]:checked');
      if (!checked) {
        event.preventDefault();
        window.alert('Please select an examination slot first.');
        return;
      }
      form.action = base.replace(/(\d+)$/, checked.value);
    });
    form.querySelectorAll('.slot-card input[type="radio"]').forEach(function (radio) {
      radio.addEventListener('change', function () {
        form.querySelectorAll('.slot-card').forEach(function (card) {
          card.classList.toggle('selected', card.contains(radio) && radio.checked);
        });
      });
    });
  });

  /* ---- password + confirm quick check on registration/profile forms ---- */
  document.querySelectorAll('form[data-password-check]').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      var pw = form.querySelector('input[name="password"], input[name="new_password"]');
      var confirm = form.querySelector('input[name="confirm_password"]');
      if (pw && confirm && pw.value && pw.value !== confirm.value) {
        event.preventDefault();
        window.alert('Passwords do not match.');
        confirm.focus();
      }
    });
  });

  /* ---- examiner evaluate: live total marks ---- */
  var totalOut = document.querySelector('[data-marks-total]');
  if (totalOut) {
    var recompute = function () {
      var total = 0;
      document.querySelectorAll('input[data-max]').forEach(function (input) {
        var value = parseFloat(input.value);
        if (!isNaN(value)) { total += value; }
      });
      totalOut.textContent = total.toFixed(2);
    };
    document.querySelectorAll('input[data-max]').forEach(function (input) {
      input.addEventListener('input', recompute);
    });
    recompute();
  }
})();
