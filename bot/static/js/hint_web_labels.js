(function () {
    var historyApi = window.hintWebHistory;
    if (!historyApi || !historyApi.enableUserLabels) return;

    var apiBase = historyApi.apiBase || '/web/hints';
    var loginUrl = historyApi.loginUrl || '/web/hints/login';
    var labelDraft = [];
    var labelEditUploadId = null;
    var presets = [];

    var filterEl = document.getElementById('historyLabelFilter');
    var presetsBtn = document.getElementById('manageLabelPresetsBtn');
    var editModal = document.getElementById('fileLabelsModal');
    var editList = document.getElementById('fileLabelsModalList');
    var editInput = document.getElementById('fileLabelsModalInput');
    var editMsg = document.getElementById('fileLabelsModalMsg');
    var presetsModal = document.getElementById('labelPresetsModal');
    var presetsList = document.getElementById('labelPresetsModalList');
    var presetsInput = document.getElementById('labelPresetsModalInput');
    var presetsMsg = document.getElementById('labelPresetsModalMsg');

    function setOpen(el, open) {
        if (!el) return;
        el.classList.toggle('is-open', !!open);
        el.setAttribute('aria-hidden', open ? 'false' : 'true');
    }

    function labelApi(method, path, body) {
        var opts = {
            method: method,
            headers: { Accept: 'application/json' },
            credentials: 'same-origin',
        };
        if (body != null) {
            opts.headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(body);
        }
        return fetch(apiBase + path, opts).then(function (res) {
            if (res.status === 401) {
                window.location.href = loginUrl;
                throw new Error('Нужна авторизация');
            }
            return res.json().then(function (data) {
                if (!res.ok) {
                    var detail = data && data.detail;
                    throw new Error(typeof detail === 'string' ? detail : (res.statusText || 'Ошибка'));
                }
                return data;
            });
        });
    }

    function escapeHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function writeLabelToUrl(label) {
        var url = new URL(window.location.href);
        if (label) url.searchParams.set('label', label);
        else url.searchParams.delete('label');
        window.history.replaceState({}, '', url);
    }

    function currentFilter() {
        return historyApi.getLabelFilter ? historyApi.getLabelFilter() : '';
    }

    function applyFilter(label, skipPoll) {
        var next = (label || '').trim();
        if (historyApi.setLabelFilter) historyApi.setLabelFilter(next, skipPoll);
        writeLabelToUrl(next);
        if (filterEl && filterEl.value !== next) filterEl.value = next;
    }

    function fillFilterOptions(labels) {
        if (!filterEl) return;
        var selected = currentFilter();
        filterEl.innerHTML = '';
        var allOpt = document.createElement('option');
        allOpt.value = '';
        allOpt.textContent = 'Все метки';
        filterEl.appendChild(allOpt);
        (labels || []).forEach(function (label) {
            var opt = document.createElement('option');
            opt.value = label;
            opt.textContent = label;
            filterEl.appendChild(opt);
        });
        if (selected && labels && labels.indexOf(selected) === -1) {
            var extra = document.createElement('option');
            extra.value = selected;
            extra.textContent = selected;
            filterEl.appendChild(extra);
        }
        filterEl.value = selected;
    }

    function loadAllLabels() {
        return labelApi('POST', '/api/labels/all').then(function (data) {
            fillFilterOptions((data && data.labels) || []);
        });
    }

    function setEditMsg(text) {
        if (editMsg) editMsg.textContent = text || '';
    }

    function setPresetsMsg(text) {
        if (presetsMsg) presetsMsg.textContent = text || '';
    }

    function renderEditList() {
        if (!editList) return;
        editList.innerHTML = '';
        if (!labelDraft.length) {
            var empty = document.createElement('span');
            empty.className = 'hw-labels-empty';
            empty.textContent = 'Пока нет меток';
            editList.appendChild(empty);
            return;
        }
        labelDraft.forEach(function (label, idx) {
            var chip = document.createElement('span');
            chip.className = 'hw-label-chip hw-label-chip--edit';
            chip.appendChild(document.createTextNode(label));
            var rm = document.createElement('button');
            rm.type = 'button';
            rm.className = 'hw-label-chip__remove';
            rm.setAttribute('aria-label', 'Убрать метку');
            rm.textContent = '×';
            rm.addEventListener('click', function () {
                labelDraft.splice(idx, 1);
                renderEditList();
            });
            chip.appendChild(rm);
            editList.appendChild(chip);
        });
    }

    function addDraftFromInput() {
        if (!editInput) return;
        var value = (editInput.value || '').trim();
        if (!value) return;
        if (labelDraft.indexOf(value) === -1) labelDraft.push(value);
        editInput.value = '';
        renderEditList();
        editInput.focus();
    }

    function openEditModal(uploadId, labels) {
        labelEditUploadId = uploadId;
        labelDraft = (labels || []).slice();
        setEditMsg('');
        renderEditList();
        if (editInput) editInput.value = '';
        setOpen(editModal, true);
        if (editInput) editInput.focus();
    }

    function closeEditModal() {
        setOpen(editModal, false);
        labelEditUploadId = null;
        labelDraft = [];
        setEditMsg('');
    }

    function saveEditModal() {
        if (!labelEditUploadId) return;
        labelApi('POST', '/api/labels/set', {
            upload_id: labelEditUploadId,
            labels: labelDraft.slice(),
        }).then(function () {
            closeEditModal();
            return loadAllLabels();
        }).then(function () {
            if (historyApi.pollHistory) historyApi.pollHistory();
        }).catch(function (e) {
            setEditMsg(e.message || String(e));
        });
    }

    function renderPresetsList() {
        if (!presetsList) return;
        presetsList.innerHTML = '';
        if (!presets.length) {
            var empty = document.createElement('p');
            empty.className = 'hw-labels-empty';
            empty.textContent = 'Пресетов пока нет.';
            presetsList.appendChild(empty);
            return;
        }
        presets.forEach(function (preset) {
            var row = document.createElement('div');
            row.className = 'hw-labels-preset-row';
            var useBtn = document.createElement('button');
            useBtn.type = 'button';
            useBtn.className = 'ghost hw-labels-preset-value';
            useBtn.textContent = preset.value;
            useBtn.title = 'Добавить к меткам файла';
            useBtn.addEventListener('click', function () {
                if (labelDraft.indexOf(preset.value) === -1) labelDraft.push(preset.value);
                renderEditList();
                if (!editModal || !editModal.classList.contains('is-open')) {
                    if (historyApi.showToast) historyApi.showToast('Пресет: «' + preset.value + '»');
                }
            });
            var del = document.createElement('button');
            del.type = 'button';
            del.className = 'ghost hw-labels-preset-del';
            del.title = 'Удалить пресет';
            del.textContent = '×';
            del.addEventListener('click', function () {
                labelApi('POST', '/api/labels/presets/delete', { preset_id: preset.id }).then(function () {
                    return loadPresets();
                }).catch(function (e) {
                    setPresetsMsg(e.message || String(e));
                });
            });
            row.appendChild(useBtn);
            row.appendChild(del);
            presetsList.appendChild(row);
        });
    }

    function loadPresets() {
        return labelApi('POST', '/api/labels/presets').then(function (data) {
            presets = (data && data.presets) || [];
            renderPresetsList();
        });
    }

    function openPresetsModal() {
        setPresetsMsg('');
        if (presetsInput) presetsInput.value = '';
        setOpen(presetsModal, true);
        loadPresets().catch(function (e) {
            setPresetsMsg(e.message || String(e));
        });
        if (presetsInput) presetsInput.focus();
    }

    function closePresetsModal() {
        setOpen(presetsModal, false);
        setPresetsMsg('');
    }

    function addPresetFromInput() {
        if (!presetsInput) return;
        var value = (presetsInput.value || '').trim();
        if (!value) {
            setPresetsMsg('Введите текст пресета');
            return;
        }
        setPresetsMsg('');
        labelApi('POST', '/api/labels/presets/create', { value: value }).then(function () {
            presetsInput.value = '';
            if (labelDraft.indexOf(value) === -1) labelDraft.push(value);
            renderEditList();
            return loadPresets();
        }).then(function () {
            presetsInput.focus();
        }).catch(function (e) {
            setPresetsMsg(e.message || String(e));
        });
    }

    if (filterEl) {
        filterEl.addEventListener('change', function () {
            applyFilter(filterEl.value);
        });
    }
    if (presetsBtn) presetsBtn.addEventListener('click', openPresetsModal);

    var historyEl = document.getElementById('history');
    if (historyEl) {
        historyEl.addEventListener('click', function (ev) {
            if (ev.target.closest('.history-item-labels')) {
                ev.stopPropagation();
            }
            var btn = ev.target.closest('[data-edit-labels]');
            if (!btn) return;
            ev.preventDefault();
            ev.stopPropagation();
            var uploadId = parseInt(btn.getAttribute('data-edit-labels'), 10);
            if (!(uploadId > 0)) return;
            var labels = [];
            var raw = btn.getAttribute('data-labels');
            if (raw) {
                try {
                    var parsed = JSON.parse(raw);
                    if (Array.isArray(parsed)) {
                        parsed.forEach(function (item) {
                            var text = String(item || '').trim();
                            if (text) labels.push(text);
                        });
                    }
                } catch (e) {}
            }
            if (!labels.length) {
                var itemEl = btn.closest('.history-item');
                if (itemEl) {
                    itemEl.querySelectorAll('.history-item-labels .hw-label-chip').forEach(function (chip) {
                        var text = (chip.textContent || '').trim();
                        if (text) labels.push(text);
                    });
                }
            }
            openEditModal(uploadId, labels);
        });
    }

    if (document.getElementById('fileLabelsModalOverlay')) {
        document.getElementById('fileLabelsModalOverlay').addEventListener('click', closeEditModal);
    }
    if (document.getElementById('fileLabelsModalCancelBtn')) {
        document.getElementById('fileLabelsModalCancelBtn').addEventListener('click', closeEditModal);
    }
    if (document.getElementById('fileLabelsModalAddBtn')) {
        document.getElementById('fileLabelsModalAddBtn').addEventListener('click', addDraftFromInput);
    }
    if (document.getElementById('fileLabelsModalSaveBtn')) {
        document.getElementById('fileLabelsModalSaveBtn').addEventListener('click', saveEditModal);
    }
    if (document.getElementById('fileLabelsOpenPresetsBtn')) {
        document.getElementById('fileLabelsOpenPresetsBtn').addEventListener('click', openPresetsModal);
    }
    if (editInput) {
        editInput.addEventListener('keydown', function (ev) {
            if (ev.key === 'Enter') {
                ev.preventDefault();
                addDraftFromInput();
            }
        });
    }
    if (document.getElementById('labelPresetsModalOverlay')) {
        document.getElementById('labelPresetsModalOverlay').addEventListener('click', closePresetsModal);
    }
    if (document.getElementById('labelPresetsModalCloseBtn')) {
        document.getElementById('labelPresetsModalCloseBtn').addEventListener('click', closePresetsModal);
    }
    if (document.getElementById('labelPresetsModalAddBtn')) {
        document.getElementById('labelPresetsModalAddBtn').addEventListener('click', addPresetFromInput);
    }
    if (presetsInput) {
        presetsInput.addEventListener('keydown', function (ev) {
            if (ev.key === 'Enter') {
                ev.preventDefault();
                addPresetFromInput();
            }
        });
    }

    if (filterEl && currentFilter()) filterEl.value = currentFilter();
    loadAllLabels().catch(function () {});
})();
