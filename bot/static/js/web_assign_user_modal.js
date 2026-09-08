(function () {
    var modal = document.getElementById('webAssignUserModal');
    if (!modal) return;

    var overlay = document.getElementById('webAssignUserModalOverlay');
    var titleEl = document.getElementById('webAssignUserModalTitle');
    var subtitleEl = document.getElementById('webAssignUserModalSubtitle');
    var searchInput = document.getElementById('webAssignUserSearchInput');
    var msgEl = document.getElementById('webAssignUserModalMsg');
    var tbody = document.getElementById('webAssignUserUsersTbody');
    var cancelBtn = document.getElementById('webAssignUserCancelBtn');
    var submitBtn = document.getElementById('webAssignUserSubmitBtn');

    var users = [];
    var selectedUserId = null;
    var pending = null;

    function setOpen(open) {
        modal.classList.toggle('is-open', !!open);
        modal.setAttribute('aria-hidden', open ? 'false' : 'true');
    }

    function setMsg(msg) {
        if (msgEl) msgEl.textContent = msg || '';
    }

    function close() {
        setOpen(false);
        pending = null;
        selectedUserId = null;
        users = [];
        setMsg('');
        if (submitBtn) submitBtn.disabled = false;
        if (searchInput) searchInput.value = '';
        if (tbody) tbody.innerHTML = '';
    }

    function render() {
        if (!tbody) return;
        tbody.innerHTML = '';
        var filterText = String(searchInput ? searchInput.value : '').trim().toLowerCase();
        var rows = users.filter(function (row) {
            if (!filterText) return true;
            var idText = String((row && row.id) || '');
            var username = String((row && row.username) || '').toLowerCase();
            return idText.indexOf(filterText) !== -1 || username.indexOf(filterText) !== -1;
        });
        if (!rows.length) {
            var emptyTr = document.createElement('tr');
            var emptyTd = document.createElement('td');
            emptyTd.colSpan = 2;
            emptyTd.textContent = 'Пользователи не найдены.';
            emptyTr.appendChild(emptyTd);
            tbody.appendChild(emptyTr);
            return;
        }
        rows.forEach(function (row) {
            var tr = document.createElement('tr');
            tr.classList.toggle('is-selected', row.id === selectedUserId);
            tr.addEventListener('click', function () {
                selectedUserId = row.id;
                setMsg('');
                render();
            });
            var idTd = document.createElement('td');
            idTd.textContent = String(row.id);
            tr.appendChild(idTd);
            var loginTd = document.createElement('td');
            loginTd.textContent = row.username || '—';
            tr.appendChild(loginTd);
            tbody.appendChild(tr);
        });
    }

    function submit() {
        if (!pending || typeof pending.onSubmit !== 'function') return;
        if (!selectedUserId) {
            setMsg('Выберите пользователя.');
            return;
        }
        if (submitBtn) submitBtn.disabled = true;
        setMsg('Отправка...');
        Promise.resolve(pending.onSubmit(selectedUserId)).then(function (data) {
            var onSuccess = pending.onSuccess;
            close();
            if (typeof onSuccess === 'function') onSuccess(data);
        }).catch(function (e) {
            setMsg((e && e.message) ? e.message : String(e));
            if (submitBtn) submitBtn.disabled = false;
        });
    }

    window.WebAssignUserModal = {
        open: function (opts) {
            opts = opts || {};
            pending = opts;
            selectedUserId = null;
            users = [];
            if (titleEl) titleEl.textContent = opts.title || 'Выбор пользователя';
            if (subtitleEl) subtitleEl.textContent = opts.subtitle || '';
            if (searchInput) searchInput.value = '';
            setMsg('');
            setOpen(true);
            if (submitBtn) submitBtn.disabled = true;
            Promise.resolve(typeof opts.loadUsers === 'function' ? opts.loadUsers() : [])
                .then(function (list) {
                    users = Array.isArray(list) ? list : [];
                    render();
                })
                .catch(function (e) {
                    setMsg((e && e.message) ? e.message : 'Ошибка загрузки списка пользователей');
                })
                .finally(function () {
                    if (submitBtn) submitBtn.disabled = false;
                    if (searchInput) searchInput.focus();
                });
        },
        close: close
    };

    if (cancelBtn) cancelBtn.addEventListener('click', close);
    if (overlay) overlay.addEventListener('click', close);
    if (submitBtn) submitBtn.addEventListener('click', submit);
    if (searchInput) searchInput.addEventListener('input', render);
})();
