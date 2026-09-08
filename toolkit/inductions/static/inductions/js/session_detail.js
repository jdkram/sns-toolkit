// human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-input"
// Extracted from inductions/manage/session_detail.html's inline <script> (September 2026
// quality pass). Wrapped as a factory function (options object, following mailout.js's precedent
// for a many-argument setup call) rather than a bare top-level script, since this page's
// template-side {% if user.is_superuser %} branches inside the JS had to become a runtime
// `opts.isSuperuser` check, and the two hand-built "manage/<slug>/signups/<id>/..." URLs
// (link-existing, remove-signup) had to become URL-pattern arguments matching the
// EDIT_URL_PATTERN/NO_SHOW_URL_PATTERN convention already used elsewhere on this page, rather
// than string-concatenating the slug into JS at render time.
function sessionDetail(opts) {
  "use strict";

  var CSRF = opts.csrf;
  var EDIT_URL_PATTERN = opts.editUrlPattern;
  var NO_SHOW_URL_PATTERN = opts.noShowUrlPattern;
  var SET_CAP_URL = opts.setCapUrl;
  var MARK_ATTENDANCE_URL_PATTERN = opts.markAttendanceUrlPattern;
  var LINK_EXISTING_URL_PATTERN = opts.linkExistingUrlPattern;
  var REMOVE_SIGNUP_URL_PATTERN = opts.removeSignupUrlPattern;
  var isSuperuser = opts.isSuperuser;

  // Exposed here, before anything below can throw: the original inline <script>
  // declared these as bare top-level `function`s, which JS hoists to global scope
  // unconditionally, so the inline onclick="saveCap()"/"adjustRoom(-1)" handlers in
  // the template kept working even if something later in that same script threw.
  // Wrapping everything in this factory function loses that hoisting-to-global
  // behaviour, so the window.* export has to happen up front instead of at the
  // point (much further down) where these were originally defined.
  // (safe to reference before their textual definition below: `function` declarations
  // are hoisted to the top of this function's scope, same as they'd hoist to global
  // scope in a plain top-level script.)
  window.saveCap = saveCap;
  window.adjustRoom = adjustRoom;

  function markAttendanceUrl(signupId) { return MARK_ATTENDANCE_URL_PATTERN.replace('/0/', '/' + signupId + '/'); }
  function linkExistingUrl(signupId) { return LINK_EXISTING_URL_PATTERN.replace('/0/', '/' + signupId + '/'); }
  function removeSignupUrl(signupId) { return REMOVE_SIGNUP_URL_PATTERN.replace('/0/', '/' + signupId + '/'); }

  function escapeHtml(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  /* ── Attendance checkboxes ── */
  document.querySelectorAll('.attendance-cb[data-mark-url]').forEach(function(cb) {
    cb.addEventListener('change', function() {
      var signupId = this.dataset.signupId;
      var url = this.dataset.markUrl;
      var cbEl = this;
      cbEl.disabled = true;

      fetch(url, {
        method: 'POST',
        headers: {'X-CSRFToken': CSRF, 'Accept': 'application/json'},
      })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        cbEl.disabled = false;
        if (data.ok) {
          updateRowStatus(signupId, data.status);
        } else {
          cbEl.checked = !cbEl.checked;
          alert('Error: ' + data.error);
        }
      })
      .catch(function() {
        cbEl.disabled = false;
        cbEl.checked = !cbEl.checked;
        alert('Network error. Please try again.');
      });
    });
  });

  function updateRowStatus(signupId, status) {
    var row = document.getElementById('row-' + signupId);
    var statusEl = document.getElementById('status-' + signupId);
    if (!row) return;

    if (status === 'checked_in') {
      row.classList.add('table-success');
      row.classList.remove('table-secondary');
      statusEl.innerHTML = '<span class="badge bg-success">Checked in</span>';
      document.getElementById('account-' + signupId).innerHTML = '<span class="text-muted small">Pending create →</span>';
    } else {
      row.classList.remove('table-success');
      statusEl.innerHTML = '<span class="badge bg-warning text-dark">Pending</span>';
      var noShowUrl = NO_SHOW_URL_PATTERN.replace('/0/', '/' + signupId + '/');
      document.getElementById('account-' + signupId).innerHTML =
        '<button type="button" class="btn btn-link btn-sm text-muted p-0 no-show-btn"' +
        ' data-signup-id="' + signupId + '" data-url="' + noShowUrl + '"' +
        ' title="Mark as no-show: did not attend">No show</button>';
    }

    var ci = 0;
    document.querySelectorAll('.attendance-cb:checked:not(:disabled)').forEach(function() { ci++; });
    document.querySelectorAll('.attendance-cb[disabled]:checked').forEach(function() { ci++; });
    document.getElementById('checkedin-count').textContent = ci;
    updateMismatch();
  }

  /* ── Select all pending ── */
  var selectAllBtn = document.getElementById('select-all-btn');
  if (selectAllBtn) selectAllBtn.addEventListener('click', function() {
    document.querySelectorAll('.attendance-cb:not(:checked):not([disabled])').forEach(function(cb) {
      cb.checked = true;
      cb.dispatchEvent(new Event('change'));
    });
  });

  /* ── Create accounts ── */
  var createAccountsBtn = document.getElementById('create-accounts-btn');
  if (createAccountsBtn) createAccountsBtn.addEventListener('click', function() {
    var btn = this;
    var pendingCreate = [];
    document.querySelectorAll('.attendance-cb[data-signup-id]:checked').forEach(function(cb) {
      var accountCell = document.getElementById('account-' + cb.dataset.signupId);
      if (accountCell && accountCell.innerHTML.indexOf('Pending create') !== -1) {
        pendingCreate.push(cb.dataset.signupId);
      }
    });

    if (pendingCreate.length === 0) {
      alert('No one is marked as present without an account yet. Tick the attendees first.');
      return;
    }

    if (!confirm('Create accounts and send welcome emails to ' + pendingCreate.length + ' person(s)? This cannot be undone.')) {
      return;
    }

    btn.disabled = true;
    btn.textContent = 'Creating accounts…';
    var resultEl = document.getElementById('create-accounts-result');
    resultEl.style.display = 'none';

    var createUrl = btn.dataset.url;
    var forcedIds = [];
    fetch(createUrl, {
      method: 'POST',
      headers: {'X-CSRFToken': CSRF, 'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'},
      body: forcedIds.length ? 'force_signup_ids=' + forcedIds.join(',') : '',
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      btn.disabled = false;
      btn.textContent = 'Create accounts & send welcome emails';

      if (data.created && data.created.length > 0) {
        data.created.forEach(function(item) {
          var signupId = item.signup_id;
          var cb = document.querySelector('.attendance-cb[data-signup-id="' + signupId + '"]');
          if (cb) { cb.disabled = true; cb.setAttribute('title', 'Account created: locked'); }
          var accountCell = document.getElementById('account-' + signupId);
          if (accountCell) accountCell.innerHTML = '<span class="badge bg-success">Account created</span>';
          var editBtn = document.querySelector('.edit-btn[data-signup-id="' + signupId + '"]');
          if (editBtn) editBtn.style.display = 'none';
          var usernameCell = document.getElementById('username-' + signupId);
          if (usernameCell && item.username) usernameCell.innerHTML = '<code>' + escapeHtml(item.username) + '</code>';
        });
      }

      var msg = '';
      if (data.created && data.created.length) {
        msg += '<div class="alert alert-success py-2 mb-2">✓ Created accounts and sent welcome emails to ' + data.created.length + ' person(s).</div>';
      }
      if (data.errors && data.errors.length) {
        msg += '<div class="alert alert-danger py-2 mb-2"><strong>Errors for ' + data.errors.length + ' person(s):</strong><ul class="mb-0 mt-1">';
        data.errors.forEach(function(e) { msg += '<li>' + escapeHtml(e.name) + ': ' + escapeHtml(e.error) + '</li>'; });
        msg += '</ul></div>';
      }
      if (data.duplicates && data.duplicates.length) {
        msg += '<div class="alert alert-warning py-2 mb-0"><strong>Possible duplicates, action required:</strong>';
        data.duplicates.forEach(function(d) {
          var matchDesc = d.match_type === 'email'
            ? 'email match: ' + escapeHtml(d.existing_email)
            : 'name match: ' + escapeHtml(d.existing_username);
          msg += '<div class="mt-2 border-top pt-2">';
          msg += '<strong>' + escapeHtml(d.name) + '</strong>: existing account found (' + matchDesc + ', username: <code>' + escapeHtml(d.existing_username) + '</code>)<br>';
          msg += '<button class="btn btn-sm btn-outline-secondary mt-1 me-1 link-existing-btn" '
               + 'data-signup-id="' + d.signup_id + '" '
               + 'data-volunteer-id="' + d.existing_volunteer_id + '" '
               + 'data-link-url="' + linkExistingUrl(d.signup_id) + '">'
               + 'Send login link to existing account</button>';
          msg += '<button class="btn btn-sm btn-outline-danger mt-1 force-create-btn" '
               + 'data-signup-id="' + d.signup_id + '" '
               + 'data-create-url="' + createUrl + '">'
               + 'Create new account anyway</button>';
          msg += '</div>';
        });
        msg += '</div>';
      }
      if (msg) { resultEl.innerHTML = msg; resultEl.style.display = ''; }

      /* Wire up link-existing buttons */
      resultEl.querySelectorAll('.link-existing-btn').forEach(function(linkBtn) {
        linkBtn.addEventListener('click', function() {
          var lBtn = this;
          lBtn.disabled = true;
          lBtn.textContent = 'Sending…';
          var formData = new FormData();
          formData.append('existing_volunteer_id', lBtn.dataset.volunteerId);
          fetch(lBtn.dataset.linkUrl, {
            method: 'POST',
            headers: {'X-CSRFToken': CSRF, 'Accept': 'application/json'},
            body: formData,
          })
          .then(function(r) { return r.json(); })
          .then(function(resp) {
            if (resp.ok) {
              lBtn.closest('div.mt-2').innerHTML = '<span class="text-success">✓ Login link sent to existing account.</span>';
            } else {
              lBtn.disabled = false; lBtn.textContent = 'Send login link to existing account';
              alert('Error: ' + (resp.error || 'Unknown error'));
            }
          })
          .catch(function() { lBtn.disabled = false; lBtn.textContent = 'Send login link to existing account'; });
        });
      });

      /* Wire up force-create buttons */
      resultEl.querySelectorAll('.force-create-btn').forEach(function(forceBtn) {
        forceBtn.addEventListener('click', function() {
          var signupId = this.dataset.signupId;
          var fBtn = this;
          fBtn.disabled = true;
          fBtn.textContent = 'Creating…';
          fetch(createUrl, {
            method: 'POST',
            headers: {'X-CSRFToken': CSRF, 'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'},
            body: 'force_signup_ids=' + signupId,
          })
          .then(function(r) { return r.json(); })
          .then(function(resp) {
            if (resp.created && resp.created.length) {
              var item = resp.created[0];
              var cb = document.querySelector('.attendance-cb[data-signup-id="' + signupId + '"]');
              if (cb) { cb.disabled = true; }
              var accountCell = document.getElementById('account-' + signupId);
              if (accountCell) accountCell.innerHTML = '<span class="badge bg-success">Account created</span>';
              fBtn.closest('div.mt-2').innerHTML = '<span class="text-success">✓ New account created: <code>' + escapeHtml(item.username) + '</code>.</span>';
            } else {
              fBtn.disabled = false; fBtn.textContent = 'Create new account anyway';
              var errMsg = (resp.errors && resp.errors.length) ? resp.errors[0].error : 'Unknown error';
              alert('Error: ' + errMsg);
            }
          })
          .catch(function() { fBtn.disabled = false; fBtn.textContent = 'Create new account anyway'; });
        });
      });
    })
    .catch(function() {
      btn.disabled = false;
      btn.textContent = 'Create accounts & send welcome emails';
      resultEl.innerHTML = '<div class="alert alert-danger py-2">Network error. Please try again.</div>';
      resultEl.style.display = '';
    });
  });

  /* ── No-show / undo — event delegation handles dynamically added buttons ── */
  var signupTableEl = document.getElementById('signup-table');
  if (signupTableEl) signupTableEl.addEventListener('click', function(e) {
    var btn = e.target.closest('.no-show-btn, .undo-no-show-btn');
    if (!btn) return;
    var signupId = btn.dataset.signupId;
    var url = btn.dataset.url;

    fetch(url, { method: 'POST', headers: {'X-CSRFToken': CSRF, 'Accept': 'application/json'} })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data.ok) { alert('Error: ' + data.error); return; }
      var row = document.getElementById('row-' + signupId);
      var cb = document.getElementById('cb-' + signupId);
      var statusEl = document.getElementById('status-' + signupId);
      var accountEl = document.getElementById('account-' + signupId);
      if (data.new_status === 'no_show') {
        row.classList.add('table-secondary');
        statusEl.innerHTML = '<span class="badge bg-secondary">No show</span>';
        if (cb) { cb.checked = false; cb.disabled = true; }
        accountEl.innerHTML = '<button type="button" class="btn btn-link btn-sm text-muted p-0 undo-no-show-btn"' +
          ' data-signup-id="' + signupId + '" data-url="' + url + '" title="Undo no-show: return to pending">Undo</button>';
      } else {
        row.classList.remove('table-secondary');
        statusEl.innerHTML = '<span class="badge bg-warning text-dark">Pending</span>';
        if (cb) { cb.disabled = false; }
        accountEl.innerHTML = '<button type="button" class="btn btn-link btn-sm text-muted p-0 no-show-btn"' +
          ' data-signup-id="' + signupId + '" data-url="' + url + '" title="Mark as no-show: did not attend">No show</button>';
      }
    });
  });

  /* ── Inline edit (panopticon) ── */
  // Wrapped in try/catch: a broken bootstrap.Modal() here (pre-existing; see
  // docs/tasks/known-issues.md, Bug AV) must not take out
  // everything textually below it -- cap editor, room counter, keyboard nav,
  // walk-in registration, table sorting, remove-signup all still need to work.
  if (isSuperuser) { try {
    var _editModalEl = document.getElementById('edit-modal');
    var editModal = bootstrap.Modal.getInstance(_editModalEl) || new bootstrap.Modal(_editModalEl);

    var _slugPreview = function(name) {
      var parts = name.trim().split(/\s+/);
      if (!parts[0]) return '(enter name)';
      var first = parts[0];
      var last = parts.length > 1 ? parts[parts.length - 1] : '';
      return (first + last).slice(0, 40) || '(enter name)';
    };

    if (signupTableEl) signupTableEl.addEventListener('click', function(e) {
      var btn = e.target.closest('.edit-btn');
      if (!btn) return;
      var signupId = btn.dataset.signupId;
      document.getElementById('edit-signup-id').value = signupId;
      document.getElementById('edit-name').value = document.getElementById('name-' + signupId).childNodes[0].textContent.trim();
      document.getElementById('edit-email').value = document.getElementById('email-' + signupId).textContent.trim();
      var desiredUsername = btn.dataset.desiredUsername || '';
      document.getElementById('edit-username').value = desiredUsername;
      document.getElementById('edit-username-preview').textContent = desiredUsername || _slugPreview(document.getElementById('edit-name').value);
      document.getElementById('edit-error').style.display = 'none';
      editModal.show();
    });

    document.getElementById('edit-name').addEventListener('input', function() {
      if (!document.getElementById('edit-username').value.trim()) {
        document.getElementById('edit-username-preview').textContent = _slugPreview(this.value);
      }
    });
    document.getElementById('edit-username').addEventListener('input', function() {
      document.getElementById('edit-username-preview').textContent = this.value.trim() || _slugPreview(document.getElementById('edit-name').value);
    });

    document.getElementById('edit-save-btn').addEventListener('click', function() {
      var signupId = document.getElementById('edit-signup-id').value;
      var name = document.getElementById('edit-name').value.trim();
      var email = document.getElementById('edit-email').value.trim();
      var desiredUsername = document.getElementById('edit-username').value.trim();
      var saveBtn = this;
      var errEl = document.getElementById('edit-error');
      errEl.style.display = 'none';

      var url = EDIT_URL_PATTERN.replace('/0/', '/' + signupId + '/');
      var formData = new FormData();
      formData.append('csrfmiddlewaretoken', CSRF);
      if (name) formData.append('name', name);
      if (email) formData.append('email', email);
      formData.append('desired_username', desiredUsername);

      saveBtn.disabled = true;
      fetch(url, {method: 'POST', body: formData, headers: {'Accept': 'application/json'}})
      .then(function(r) { return r.json(); })
      .then(function(data) {
        saveBtn.disabled = false;
        if (data.ok) {
          var nameCell = document.getElementById('name-' + signupId);
          var editBtn = nameCell.querySelector('.edit-btn');
          nameCell.childNodes[0].textContent = data.name + ' ';
          document.getElementById('email-' + signupId).textContent = data.email;
          if (editBtn) editBtn.dataset.desiredUsername = data.desired_username || '';
          var uCell = document.getElementById('username-' + signupId);
          if (uCell) {
            if (data.desired_username) {
              uCell.innerHTML = '<span class="text-muted small"><code>' + escapeHtml(data.desired_username) + '</code><br><small>(pending)</small></span>';
            } else {
              var previewName = document.getElementById('name-' + signupId).childNodes[0].textContent.trim();
              uCell.innerHTML = '<span class="text-muted small"><code>' + escapeHtml(_slugPreview(previewName)) + '</code><br><small>(preview)</small></span>';
            }
          }
          editModal.hide();
        } else {
          errEl.textContent = data.error;
          errEl.style.display = '';
        }
      })
      .catch(function() {
        saveBtn.disabled = false;
        errEl.textContent = 'Network error. Please try again.';
        errEl.style.display = '';
      });
    });
  } catch (err) {
    console.error('session_detail: edit-modal setup failed', err);
  } }

  /* ── Cap editor ── */
  function saveCap() {
    var input = document.getElementById('cap-input');
    var raw = input.value.trim();
    if (raw !== '' && (!/^\d+$/.test(raw))) {
      alert('Enter a whole number, or leave blank for no cap.');
      return;
    }
    var btn = document.getElementById('cap-save-btn');
    btn.disabled = true;
    fetch(SET_CAP_URL, {
      method: 'POST',
      headers: {'X-CSRFToken': CSRF, 'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'},
      body: 'max_signups=' + encodeURIComponent(raw),
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data.ok) { btn.disabled = false; alert('Error: ' + data.error); return; }
      location.reload();
    })
    .catch(function() { btn.disabled = false; alert('Network error. Please try again.'); });
  }
  document.getElementById('cap-input').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') { e.preventDefault(); saveCap(); }
  });

  /* ── Room count ── */
  var roomCount = 0;
  function adjustRoom(delta) {
    roomCount = Math.max(0, roomCount + delta);
    document.getElementById('room-count').textContent = roomCount;
    updateMismatch();
  }
  function updateMismatch() {
    var ci = parseInt(document.getElementById('checkedin-count').textContent, 10);
    var mismatch = document.getElementById('room-mismatch');
    mismatch.style.display = (roomCount > 0 && roomCount !== ci) ? '' : 'none';
  }

  /* ── Initialise counts ── */
  (function() {
    var ci = 0;
    document.querySelectorAll('.attendance-cb:checked').forEach(function() { ci++; });
    document.getElementById('checkedin-count').textContent = ci;
    var acc = 0;
    document.querySelectorAll('#signup-table .badge.bg-success').forEach(function(el) {
      if (el.textContent.trim() === 'Account created') acc++;
    });
    document.getElementById('accounts-count').textContent = acc;
  })();

  /* ── Keyboard navigation ── */
  var _kbIndex = -1;

  function _kbRows() {
    return Array.from(document.querySelectorAll('#signup-table tbody tr'));
  }
  function _kbSelect(idx) {
    var rows = _kbRows();
    rows.forEach(function(r) { r.classList.remove('kb-selected'); });
    if (idx < 0 || idx >= rows.length) { _kbIndex = -1; return; }
    _kbIndex = idx;
    rows[_kbIndex].classList.add('kb-selected');
    rows[_kbIndex].scrollIntoView({block: 'nearest'});
  }

  document.addEventListener('keydown', function(e) {
    if (e.target.matches('input, textarea, select, button')) return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (isSuperuser) {
      var modal = document.getElementById('edit-modal');
      if (modal && modal.classList.contains('show')) return;
    }

    var rows = _kbRows();
    if (e.key === 'j' || e.key === 'ArrowDown') {
      e.preventDefault();
      _kbSelect(Math.min(_kbIndex < 0 ? 0 : _kbIndex + 1, rows.length - 1));
    } else if (e.key === 'k' || e.key === 'ArrowUp') {
      e.preventDefault();
      _kbSelect(Math.max(_kbIndex < 0 ? rows.length - 1 : _kbIndex - 1, 0));
    } else if (_kbIndex >= 0) {
      var row = rows[_kbIndex];
      if (!row) return;
      var signupId = row.id.replace('row-', '');
      if (e.key === 'n') {
        var nsBtn = row.querySelector('.no-show-btn, .undo-no-show-btn');
        if (nsBtn) nsBtn.click();
      } else if (e.key === 'c' || e.key === ' ') {
        e.preventDefault();
        var cb = document.getElementById('cb-' + signupId);
        if (cb && !cb.disabled) { cb.checked = !cb.checked; cb.dispatchEvent(new Event('change')); }
      }
    }
  });

  /* ── Walk-in registration ── */
  var walkinAddBtn = document.getElementById('walkin-add-btn');
  if (walkinAddBtn) {
    walkinAddBtn.addEventListener('click', function() {
      var first = document.getElementById('walkin-first').value.trim();
      var last = document.getElementById('walkin-last').value.trim();
      var email = document.getElementById('walkin-email').value.trim();
      var phone = document.getElementById('walkin-phone').value.trim();
      var address = document.getElementById('walkin-address').value.trim();
      var postcode = document.getElementById('walkin-postcode').value.trim();
      var errEl = document.getElementById('walkin-error');
      errEl.style.display = 'none';

      if (!first) {
        errEl.textContent = 'First name is required.';
        errEl.style.display = '';
        return;
      }
      if (!email) {
        errEl.textContent = 'Email address is required.';
        errEl.style.display = '';
        return;
      }

      var btn = this;
      btn.disabled = true;
      var formData = new FormData();
      formData.append('csrfmiddlewaretoken', CSRF);
      formData.append('first_name', first);
      formData.append('last_name', last);
      formData.append('email', email);
      formData.append('phone', phone);
      formData.append('address', address);
      formData.append('postcode', postcode);

      fetch(btn.dataset.url, {method: 'POST', body: formData, headers: {'Accept': 'application/json'}})
      .then(function(r) { return r.json(); })
      .then(function(data) {
        btn.disabled = false;
        if (!data.ok) {
          errEl.textContent = data.error;
          errEl.style.display = '';
          return;
        }
        // Clear inputs
        document.getElementById('walkin-first').value = '';
        document.getElementById('walkin-last').value = '';
        document.getElementById('walkin-email').value = '';
        document.getElementById('walkin-phone').value = '';
        document.getElementById('walkin-address').value = '';
        document.getElementById('walkin-postcode').value = '';

        // Build and insert a new table row
        var noShowUrl = NO_SHOW_URL_PATTERN.replace('/0/', '/' + data.signup_id + '/');
        var markUrl = markAttendanceUrl(data.signup_id);
        var editBtnHtml = isSuperuser
          ? '<button type="button" class="btn btn-link btn-sm p-0 ms-1 edit-btn"' +
            ' data-signup-id="' + data.signup_id + '" data-desired-username=""' +
            ' title="Edit name/email/username" style="color:#6c757d;">✏</button>'
          : '';
        var removeBtnHtml = isSuperuser
          ? ' &nbsp;·&nbsp; <button type="button" class="btn btn-link btn-sm text-danger p-0 remove-signup-btn"' +
            ' data-signup-id="' + data.signup_id + '" data-url="' + removeSignupUrl(data.signup_id) + '"' +
            ' title="Remove this sign-up">×</button>'
          : '';
        var newRow = document.createElement('tr');
        newRow.id = 'row-' + data.signup_id;
        newRow.innerHTML =
          '<td class="text-center align-middle">' +
            '<input type="checkbox" class="form-check-input attendance-cb"' +
            ' id="cb-' + data.signup_id + '" data-signup-id="' + data.signup_id + '"' +
            ' data-mark-url="' + markUrl + '">' +
          '</td>' +
          '<td id="name-' + data.signup_id + '" class="align-middle">' + escapeHtml(data.name) + editBtnHtml + '</td>' +
          '<td id="email-' + data.signup_id + '" class="align-middle">' + escapeHtml(data.email || '—') + '</td>' +
          '<td id="username-' + data.signup_id + '" class="align-middle">' +
            '<span class="text-muted small"><code>' + escapeHtml(data.preview_username) + '</code></span></td>' +
          '<td class="align-middle text-nowrap">' + escapeHtml(data.signed_up_at) + '</td>' +
          '<td id="status-' + data.signup_id + '" class="align-middle">' +
            '<span class="badge bg-warning text-dark">Pending</span></td>' +
          '<td id="account-' + data.signup_id + '" class="align-middle">' +
            '<button type="button" class="btn btn-link btn-sm text-muted p-0 no-show-btn"' +
            ' data-signup-id="' + data.signup_id + '" data-url="' + noShowUrl + '"' +
            ' title="Mark as no-show: did not attend">No show</button>' + removeBtnHtml + '</td>';

        var tbody = document.querySelector('#signup-table tbody');
        if (tbody) {
          tbody.appendChild(newRow);
          // Wire up attendance checkbox
          var cb = newRow.querySelector('.attendance-cb[data-mark-url]');
          if (cb) {
            cb.addEventListener('change', function() {
              var sid = this.dataset.signupId;
              var url = this.dataset.markUrl;
              var cbEl = this;
              cbEl.disabled = true;
              fetch(url, {method: 'POST', headers: {'X-CSRFToken': CSRF, 'Accept': 'application/json'}})
              .then(function(r) { return r.json(); })
              .then(function(d) {
                cbEl.disabled = false;
                if (d.ok) { updateRowStatus(sid, d.status); }
                else { cbEl.checked = !cbEl.checked; alert('Error: ' + d.error); }
              });
            });
          }
        }

        // Update total count
        var tc = document.getElementById('total-count');
        if (tc) tc.textContent = parseInt(tc.textContent, 10) + 1;

        // Show the table if it was hidden (no signups case)
        var table = document.getElementById('signup-table');
        if (table) table.style.display = '';
      })
      .catch(function() {
        btn.disabled = false;
        errEl.textContent = 'Network error. Please try again.';
        errEl.style.display = '';
      });
    });
  }

  /* ── Over the shoulder mode ── */
  var otsBtn = document.getElementById('ots-btn');
  if (otsBtn) otsBtn.addEventListener('click', function() {
    document.body.classList.toggle('ots-mode');
    var on = document.body.classList.contains('ots-mode');
    otsBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
    // Auto-open walk-in form when mode activates so the new person sees it immediately
    var walkinDetails = document.getElementById('walkin-details');
    if (on && walkinDetails) walkinDetails.open = true;
  });

  /* ── Table sorting ── */
  (function() {
    var table = document.getElementById('signup-table');
    if (!table) return;
    var thead = table.querySelector('thead tr');
    var tbody = table.querySelector('tbody');
    var sortKey = null;
    var sortAsc = true;

    function colIndex(th) {
      return Array.from(thead.children).indexOf(th);
    }

    function cellText(row, idx) {
      var cell = row.cells[idx];
      return cell ? cell.textContent.trim() : '';
    }

    thead.addEventListener('click', function(e) {
      var th = e.target.closest('th[data-sort]');
      if (!th) return;

      var key = th.dataset.sort;
      if (sortKey === key) {
        sortAsc = !sortAsc;
      } else {
        sortKey = key;
        sortAsc = true;
      }

      // Update header indicators
      thead.querySelectorAll('th[data-sort]').forEach(function(h) {
        h.classList.remove('sort-asc', 'sort-desc');
      });
      th.classList.add(sortAsc ? 'sort-asc' : 'sort-desc');

      var idx = colIndex(th);
      var rows = Array.from(tbody.querySelectorAll('tr'));
      rows.sort(function(a, b) {
        var va = cellText(a, idx);
        var vb = cellText(b, idx);
        // For "Signed up" column, parse dates (format "j M H:i" e.g. "5 Jul 14:30")
        if (key === 'signed_up') {
          var da = a.dataset.signedUpTs || 0;
          var db = b.dataset.signedUpTs || 0;
          return sortAsc ? da - db : db - da;
        }
        return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
      });
      rows.forEach(function(r) { tbody.appendChild(r); });
    });

    // Stamp numeric sort keys on rows for date sorting
    tbody.querySelectorAll('tr').forEach(function(row, i) {
      row.dataset.signedUpTs = i; // rows already in chronological order from server
    });
  })();

  /* ── Remove pending signup ── */
  document.addEventListener('click', function(e) {
    var btn = e.target.closest('.remove-signup-btn');
    if (!btn) return;
    if (!confirm('Remove this sign-up? This cannot be undone.')) return;
    var signupId = btn.dataset.signupId;
    var url = btn.dataset.url;
    btn.disabled = true;
    fetch(url, {method: 'POST', headers: {'X-CSRFToken': CSRF, 'Accept': 'application/json'}})
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.ok) {
        var row = document.getElementById('row-' + signupId);
        if (row) row.remove();
        var tc = document.getElementById('total-count');
        if (tc) tc.textContent = Math.max(0, parseInt(tc.textContent, 10) - 1);
      } else {
        btn.disabled = false;
        alert('Error: ' + (data.error || 'Unknown error'));
      }
    })
    .catch(function() { btn.disabled = false; alert('Network error. Please try again.'); });
  });
}
