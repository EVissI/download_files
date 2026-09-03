(function () {
    var historyApi = window.hintWebHistory;
    if (!historyApi || !historyApi.enableUserFolders) return;

    var apiBase = historyApi.apiBase || '/web/hints';
    var loginUrl = historyApi.loginUrl || '/web/hints/login';

    var folderTreeData = [];
    var expandedManageIds = {};
    var expandedPickIds = {};
    var expandedCreateParentIds = {};
    var folderNamePending = null;
    var folderActionUploadIds = [];
    var folderPickUploadIds = [];
    var folderInsertPending = null;
    var currentFolderMeta = null;

    var manageBtn = document.getElementById('manageFoldersBtn');
    var foldersBtn = document.getElementById('historyFoldersBtn');
    var removeBtn = document.getElementById('historyRemoveFromFolderBtn');
    var titleEl = document.getElementById('historyCardTitle');
    var folderViewBar = document.getElementById('folderViewBar');
    var folderViewSubfolders = document.getElementById('folderViewSubfolders');
    var folderViewBackBtn = document.getElementById('folderViewBackBtn');
    var folderViewHomeBtn = document.getElementById('folderViewHomeBtn');
    var folderViewUpBtn = document.getElementById('folderViewUpBtn');
    var folderNavStack = [];
    var FOLDER_NAV_STACK_MAX = 50;

    var actionModal = document.getElementById('folderActionModal');
    var actionSubtitle = document.getElementById('folderActionModalSubtitle');
    var pickModal = document.getElementById('folderPickModal');
    var pickSubtitle = document.getElementById('folderPickModalSubtitle');
    var pickMsg = document.getElementById('folderPickMsg');
    var pickTree = document.getElementById('folderPickTree');
    var insertModal = document.getElementById('folderInsertConfirmModal');
    var insertText = document.getElementById('folderInsertConfirmModalText');
    var insertMsg = document.getElementById('folderInsertConfirmModalMsg');
    var insertSubmitBtn = document.getElementById('folderInsertConfirmSubmitBtn');
    var createParentModal = document.getElementById('folderCreateParentModal');
    var createParentMsg = document.getElementById('folderCreateParentMsg');
    var createParentTree = document.getElementById('folderCreateParentTree');
    var manageModal = document.getElementById('folderManageModal');
    var manageMsg = document.getElementById('folderManageMsg');
    var manageTree = document.getElementById('folderManageTree');
    var nameModal = document.getElementById('folderNameModal');
    var nameTitle = document.getElementById('folderNameModalTitle');
    var nameSubtitle = document.getElementById('folderNameModalSubtitle');
    var nameInput = document.getElementById('folderNameModalInput');
    var nameMsg = document.getElementById('folderNameModalMsg');
    var nameSubmitBtn = document.getElementById('folderNameModalSubmitBtn');

    var scheduleModal = document.getElementById('folderScheduleModal');
    var scheduleSubtitle = document.getElementById('folderScheduleModalSubtitle');
    var scheduleMeta = document.getElementById('folderScheduleModalMeta');
    var scheduleWeekdayToolbar = document.getElementById('folderScheduleWeekdayToolbar');
    var scheduleWeekdays = document.getElementById('folderScheduleWeekdays');
    var scheduleTimeInput = document.getElementById('folderScheduleTimeInput');
    var scheduleCountInput = document.getElementById('folderScheduleCountInput');
    var scheduleLabels = document.getElementById('folderScheduleLabels');
    var scheduleActiveInput = document.getElementById('folderScheduleActiveInput');
    var scheduleMsg = document.getElementById('folderScheduleModalMsg');
    var scheduleDeleteBtn = document.getElementById('folderScheduleDeleteBtn');
    var scheduleSaveBtn = document.getElementById('folderScheduleSaveBtn');
    var allLabelsCache = [];
    var schedulePending = null;
    var scheduleSelectedWeekdays = {};
    var scheduleSelectedLabels = {};
    var SCHEDULE_DAYS = [
        { value: 'mon', short: 'Пн', full: 'Понедельник' },
        { value: 'tue', short: 'Вт', full: 'Вторник' },
        { value: 'wed', short: 'Ср', full: 'Среда' },
        { value: 'thu', short: 'Чт', full: 'Четверг' },
        { value: 'fri', short: 'Пт', full: 'Пятница' },
        { value: 'sat', short: 'Сб', full: 'Суббота' },
        { value: 'sun', short: 'Вс', full: 'Воскресенье' }
    ];
    var CALENDAR_ICON =
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
        '<rect x="3.5" y="5.5" width="17" height="15" rx="2" stroke="currentColor" stroke-width="1.7"/>' +
        '<path d="M8 3.5v4M16 3.5v4M3.5 10h17" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>' +
        '</svg>';
    var SHARED_ICON =
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
        '<circle cx="9" cy="8" r="2.4" stroke="currentColor" stroke-width="1.7"/>' +
        '<path d="M4.5 18c.4-2.6 2.4-4 4.5-4s4.1 1.4 4.5 4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>' +
        '<circle cx="16.2" cy="8.6" r="2" stroke="currentColor" stroke-width="1.7"/>' +
        '<path d="M15.2 14.2c1.8.2 3.4 1.4 3.8 3.8" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>' +
        '</svg>';
    var SEND_ICON =
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
        '<path d="M4 11.5L20 4l-6.8 16-2.4-6.4L4 11.5Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>' +
        '</svg>';
    var isAdminUser = !!historyApi.isAdmin;
    var shareModal = document.getElementById('folderShareModal');
    var shareSubtitle = document.getElementById('folderShareModalSubtitle');
    var shareSearchInput = document.getElementById('folderShareSearchInput');
    var shareMsg = document.getElementById('folderShareModalMsg');
    var shareTbody = document.getElementById('folderShareUsersTbody');
    var shareSubmitBtn = document.getElementById('folderShareSubmitBtn');
    var shareUsers = [];
    var shareUsersLoaded = false;
    var selectedShareUserId = null;
    var sharePending = null;

    function folderApi(method, path, body) {
        var opts = {
            method: method,
            headers: { 'Accept': 'application/json' },
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

    function folderApiPost(endpoint, body) {
        return folderApi('POST', '/api/folders/' + endpoint, body || {});
    }

    function defaultNewFolderName(prefix) {
        var d = new Date();
        var pad = function (n) { return n < 10 ? '0' + n : String(n); };
        var base = pad(d.getDate()) + '.' + pad(d.getMonth() + 1) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
        return (prefix || 'Папка') + ' ' + base;
    }

    function filesWord(n) {
        var mod10 = n % 10;
        var mod100 = n % 100;
        if (mod10 === 1 && mod100 !== 11) return 'файл';
        if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'файла';
        return 'файлов';
    }

    function readFolderIdFromUrl() {
        var params = new URLSearchParams(window.location.search);
        var raw = params.get('folder_id');
        if (!raw) return null;
        var n = parseInt(raw, 10);
        return n > 0 ? n : null;
    }

    function writeFolderIdToUrl(folderId, replace) {
        var url = new URL(window.location.href);
        if (folderId) url.searchParams.set('folder_id', String(folderId));
        else url.searchParams.delete('folder_id');
        if (replace) window.history.replaceState({}, '', url);
        else window.history.pushState({}, '', url);
    }

    function setOpen(el, open) {
        if (!el) return;
        el.classList.toggle('is-open', !!open);
        el.setAttribute('aria-hidden', open ? 'false' : 'true');
    }

    function loadFolderTreeData() {
        return folderApiPost('tree').then(function (data) {
            folderTreeData = (data && data.folders) || [];
            return folderTreeData;
        });
    }

    function folderExistsInTree(nodes, folderId) {
        if (!Array.isArray(nodes) || folderId == null) return false;
        for (var i = 0; i < nodes.length; i += 1) {
            var node = nodes[i];
            if (!node) continue;
            if (Number(node.id) === Number(folderId)) return true;
            if (folderExistsInTree(node.children, folderId)) return true;
        }
        return false;
    }

    function getNewFolderParentId() {
        return historyApi.getFolderId() || null;
    }

    function updateSelectionUi() {
        var ids = historyApi.getSelectedUploadIds ? historyApi.getSelectedUploadIds() : [];
        var inFolder = !!historyApi.getFolderId();
        var granted = !!(currentFolderMeta && currentFolderMeta.folder && currentFolderMeta.folder.is_granted);
        if (removeBtn) {
            removeBtn.hidden = !inFolder || granted;
            removeBtn.setAttribute('aria-hidden', (!inFolder || granted) ? 'true' : 'false');
            removeBtn.disabled = !inFolder || granted || !ids.length;
        }
    }

    function normalizeFolderId(folderId) {
        if (folderId == null || folderId === '') return null;
        var n = parseInt(folderId, 10);
        return n > 0 ? n : null;
    }

    function sameFolderId(a, b) {
        return normalizeFolderId(a) === normalizeFolderId(b);
    }

    function pruneNavStack(folderId) {
        var skip = normalizeFolderId(folderId);
        if (skip == null) return;
        folderNavStack = folderNavStack.filter(function (id) {
            return !sameFolderId(id, skip);
        });
    }

    function pushNavState(fromId) {
        var current = normalizeFolderId(fromId);
        var last = folderNavStack.length ? folderNavStack[folderNavStack.length - 1] : undefined;
        if (folderNavStack.length && sameFolderId(last, current)) return;
        folderNavStack.push(current);
        if (folderNavStack.length > FOLDER_NAV_STACK_MAX) {
            folderNavStack.shift();
        }
    }

    function getCurrentParentId() {
        var meta = currentFolderMeta;
        if (!meta) return null;
        if (meta.parent && meta.parent.id) return normalizeFolderId(meta.parent.id);
        if (meta.folder && meta.folder.parent_id) return normalizeFolderId(meta.folder.parent_id);
        return null;
    }

    function updateNavButtons() {
        var inFolder = !!historyApi.getFolderId();
        var parentId = getCurrentParentId();
        if (folderViewBackBtn) {
            folderViewBackBtn.disabled = folderNavStack.length === 0;
        }
        if (folderViewHomeBtn) {
            folderViewHomeBtn.disabled = !inFolder;
        }
        if (folderViewUpBtn) {
            folderViewUpBtn.disabled = !parentId;
            folderViewUpBtn.title = parentId ? 'В родительскую папку' : 'На уровень выше';
            folderViewUpBtn.setAttribute('aria-label', folderViewUpBtn.title);
        }
    }

    function navigateToFolder(folderId, replace, fromHistory) {
        var current = historyApi.getFolderId();
        var next = normalizeFolderId(folderId);
        if (!replace && !fromHistory && !sameFolderId(current, next)) {
            pushNavState(current);
        }
        writeFolderIdToUrl(next, replace);
        historyApi.setFolderId(next);
        loadCurrentFolderView();
        updateSelectionUi();
        updateNavButtons();
    }

    function goHome(replace) {
        currentFolderMeta = null;
        if (titleEl) titleEl.textContent = 'История загрузок';
        navigateToFolder(null, replace);
    }

    function goBack() {
        if (!folderNavStack.length) return;
        var prev = folderNavStack.pop();
        navigateToFolder(prev, false, true);
    }

    function renderFolderBar(meta) {
        if (!folderViewBar || !folderViewSubfolders) return;
        folderViewBar.classList.add('is-visible');
        folderViewBar.setAttribute('aria-hidden', 'false');
        folderViewSubfolders.innerHTML = '';
        if (!meta || !meta.folder) {
            if (titleEl) titleEl.textContent = 'История загрузок';
            updateNavButtons();
            updateSelectionUi();
            return;
        }
        if (titleEl) {
            var title = meta.folder.name || 'Папка';
            if (meta.folder.is_granted) title += ' · общая';
            titleEl.textContent = title;
        }
        (meta.child_folders || []).forEach(function (child) {
            var chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'folder-view-bar__chip';
            var cnt = child.direct_files_count || 0;
            chip.textContent = child.name + (cnt ? ' (' + cnt + ')' : '');
            chip.addEventListener('click', function () {
                navigateToFolder(child.id);
            });
            folderViewSubfolders.appendChild(chip);
        });
        updateNavButtons();
        updateSelectionUi();
    }

    function loadCurrentFolderView() {
        var folderId = historyApi.getFolderId();
        if (!folderId) {
            currentFolderMeta = null;
            renderFolderBar(null);
            return Promise.resolve();
        }
        return folderApi('GET', '/api/folders/' + encodeURIComponent(folderId)).then(function (data) {
            currentFolderMeta = data;
            renderFolderBar(data);
        }).catch(function () {
            pruneNavStack(folderId);
            goHome(true);
        });
    }

    function afterFolderStructureChanged(deletedFolderId) {
        return loadFolderTreeData().then(function () {
            if (manageModal && manageModal.classList.contains('is-open')) refreshManageList();
            if (pickModal && pickModal.classList.contains('is-open')) refreshPickList();
            if (createParentModal && createParentModal.classList.contains('is-open')) refreshCreateParentList();
            var currentId = historyApi.getFolderId();
            if (deletedFolderId != null) pruneNavStack(deletedFolderId);
            if (currentId) {
                if (deletedFolderId != null && Number(deletedFolderId) === Number(currentId)) {
                    goHome(true);
                    return;
                }
                if (!folderExistsInTree(folderTreeData, currentId)) {
                    pruneNavStack(currentId);
                    goHome(true);
                    return;
                }
                return loadCurrentFolderView().then(function () {
                    historyApi.pollHistory();
                });
            }
        });
    }

    function emptyTreeMessage(text) {
        var p = document.createElement('p');
        p.className = 'muted';
        p.style.textAlign = 'center';
        p.style.padding = '16px 0';
        p.textContent = text;
        return p;
    }

    function refreshManageList() {
        if (!manageTree) return;
        manageTree.innerHTML = '';
        if (!folderTreeData.length) {
            manageTree.appendChild(emptyTreeMessage('Папок пока нет.'));
            return;
        }
        folderTreeData.forEach(function (node) {
            manageTree.appendChild(buildManageNode(node));
        });
    }

    function ownFolderNodes(nodes) {
        var out = [];
        (nodes || []).forEach(function (node) {
            if (!node || node.is_granted) return;
            out.push(Object.assign({}, node, {
                children: ownFolderNodes(node.children || []),
            }));
        });
        return out;
    }

    function refreshPickList() {
        if (!pickTree) return;
        pickTree.innerHTML = '';
        var nodes = ownFolderNodes(folderTreeData);
        if (!nodes.length) {
            pickTree.appendChild(emptyTreeMessage('Папок пока нет. Сначала создайте папку.'));
            return;
        }
        nodes.forEach(function (node) {
            pickTree.appendChild(buildPickNode(node));
        });
    }

    function refreshCreateParentList() {
        if (!createParentTree) return;
        createParentTree.innerHTML = '';
        ownFolderNodes(folderTreeData).forEach(function (node) {
            createParentTree.appendChild(buildCreateParentNode(node));
        });
    }

    function setFolderScheduleModalMsg(msg) {
        if (scheduleMsg) scheduleMsg.textContent = msg || '';
    }

    function renderFolderScheduleWeekdays() {
        if (!scheduleWeekdays) return;
        scheduleWeekdays.innerHTML = '';
        SCHEDULE_DAYS.forEach(function (day) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'hw-folder-schedule-modal__weekday-btn' +
                (scheduleSelectedWeekdays[day.value] ? ' is-active' : '');
            btn.textContent = day.short;
            btn.title = day.full;
            btn.addEventListener('click', function () {
                scheduleSelectedWeekdays[day.value] = !scheduleSelectedWeekdays[day.value];
                renderFolderScheduleWeekdays();
            });
            scheduleWeekdays.appendChild(btn);
        });
    }

    function setFolderScheduleWeekdays(values) {
        scheduleSelectedWeekdays = {};
        (values || []).forEach(function (value) {
            var key = String(value || '').trim().toLowerCase();
            if (key) scheduleSelectedWeekdays[key] = true;
        });
        renderFolderScheduleWeekdays();
    }

    function getFolderScheduleWeekdays() {
        return SCHEDULE_DAYS
            .map(function (day) { return day.value; })
            .filter(function (value) { return !!scheduleSelectedWeekdays[value]; });
    }

    function renderFolderScheduleWeekdayToolbar() {
        if (!scheduleWeekdayToolbar || scheduleWeekdayToolbar.dataset.ready === '1') return;
        scheduleWeekdayToolbar.dataset.ready = '1';
        [
            { label: 'Будни', values: ['mon', 'tue', 'wed', 'thu', 'fri'] },
            { label: 'Выходные', values: ['sat', 'sun'] },
            { label: 'Все дни', values: ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] },
            { label: 'Очистить', values: [] }
        ].forEach(function (item) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'hw-folder-schedule-modal__toolbar-btn';
            btn.textContent = item.label;
            btn.addEventListener('click', function () {
                setFolderScheduleWeekdays(item.values);
            });
            scheduleWeekdayToolbar.appendChild(btn);
        });
    }

    function renderFolderScheduleLabels(selectedLabels) {
        if (!scheduleLabels) return;
        scheduleLabels.innerHTML = '';
        scheduleSelectedLabels = {};
        (selectedLabels || []).forEach(function (label) {
            var text = String(label || '').trim();
            if (text) scheduleSelectedLabels[text] = true;
        });
        if (!allLabelsCache.length) {
            scheduleLabels.innerHTML =
                '<p style="margin:0;color:var(--web-text-muted);font-size:12px;">Метки не найдены.</p>';
            return;
        }
        allLabelsCache.forEach(function (label) {
            var row = document.createElement('label');
            row.className = 'hw-folder-schedule-modal__label-row';
            var input = document.createElement('input');
            input.type = 'checkbox';
            input.value = label;
            input.checked = !!scheduleSelectedLabels[label];
            input.addEventListener('change', function () {
                if (input.checked) scheduleSelectedLabels[label] = true;
                else delete scheduleSelectedLabels[label];
            });
            var text = document.createElement('span');
            text.textContent = label;
            row.appendChild(input);
            row.appendChild(text);
            scheduleLabels.appendChild(row);
        });
    }

    function getFolderScheduleSelectedLabels() {
        return Object.keys(scheduleSelectedLabels).filter(function (label) {
            return !!scheduleSelectedLabels[label];
        });
    }

    function formatFolderScheduleMeta(schedule) {
        if (!schedule || !schedule.last_run_at) return '';
        try {
            var dt = new Date(schedule.last_run_at);
            if (isNaN(dt.getTime())) return '';
            return 'Последний запуск: ' + dt.toLocaleString('ru-RU');
        } catch (e) {
            return '';
        }
    }

    function closeFolderScheduleModal() {
        setOpen(scheduleModal, false);
        schedulePending = null;
        setFolderScheduleModalMsg('');
        if (scheduleSaveBtn) scheduleSaveBtn.disabled = false;
        if (scheduleDeleteBtn) scheduleDeleteBtn.disabled = false;
    }

    function openFolderScheduleModal(folderId, folderName, existingSchedule) {
        if (!scheduleModal) return;
        schedulePending = {
            folderId: folderId,
            folderName: folderName,
            hasSchedule: !!existingSchedule
        };
        renderFolderScheduleWeekdayToolbar();
        if (scheduleSubtitle) {
            scheduleSubtitle.textContent = '«' + folderName + '»';
        }
        if (scheduleMeta) {
            scheduleMeta.textContent = formatFolderScheduleMeta(existingSchedule);
        }
        var schedule = existingSchedule || {};
        setFolderScheduleWeekdays(schedule.weekdays || ['mon', 'tue', 'wed', 'thu', 'fri']);
        if (scheduleTimeInput) {
            scheduleTimeInput.value = schedule.issue_time_msk || '09:00';
        }
        if (scheduleCountInput) {
            scheduleCountInput.value = String(schedule.cards_per_run || schedule.files_per_run || 1);
        }
        renderFolderScheduleLabels(schedule.labels || []);
        if (scheduleActiveInput) {
            scheduleActiveInput.checked = existingSchedule ? !!schedule.is_active : true;
        }
        if (scheduleDeleteBtn) {
            scheduleDeleteBtn.style.display = existingSchedule ? '' : 'none';
        }
        setFolderScheduleModalMsg('');
        setOpen(scheduleModal, true);
    }

    function ensureAllLabelsLoaded() {
        if (!historyApi.enableUserLabels) {
            allLabelsCache = [];
            return Promise.resolve(allLabelsCache);
        }
        if (allLabelsCache.length) {
            return Promise.resolve(allLabelsCache);
        }
        return folderApi('POST', '/api/labels/all').then(function (data) {
            allLabelsCache = ((data && data.labels) || []).slice();
            return allLabelsCache;
        }).catch(function () {
            allLabelsCache = [];
            return allLabelsCache;
        });
    }

    function loadFolderScheduleAndOpen(folderId, folderName, existingSchedule) {
        ensureAllLabelsLoaded().then(function () {
            if (existingSchedule) {
                openFolderScheduleModal(folderId, folderName, existingSchedule);
                return;
            }
            return folderApiPost('schedule_get', { folder_id: folderId })
                .then(function (data) {
                    openFolderScheduleModal(folderId, folderName, data && data.schedule);
                });
        }).catch(function (e) {
            if (manageMsg) manageMsg.textContent = 'Ошибка: ' + (e.message || e);
        });
    }

    function submitFolderScheduleSave() {
        if (!schedulePending) return;
        var weekdays = getFolderScheduleWeekdays();
        if (!weekdays.length) {
            setFolderScheduleModalMsg('Выберите хотя бы один день недели.');
            return;
        }
        var labels = getFolderScheduleSelectedLabels();
        var timeValue = scheduleTimeInput ? String(scheduleTimeInput.value || '').trim() : '';
        if (!/^\d{2}:\d{2}$/.test(timeValue)) {
            setFolderScheduleModalMsg('Укажите время в формате ЧЧ:ММ.');
            return;
        }
        var filesPerRun = scheduleCountInput ? parseInt(scheduleCountInput.value, 10) : 1;
        if (!filesPerRun || filesPerRun < 1) {
            setFolderScheduleModalMsg('Количество файлов должно быть не меньше 1.');
            return;
        }
        if (scheduleSaveBtn) scheduleSaveBtn.disabled = true;
        setFolderScheduleModalMsg('Сохранение...');
        folderApiPost('schedule_save', {
            folder_id: schedulePending.folderId,
            weekdays: weekdays,
            issue_time_msk: timeValue,
            cards_per_run: filesPerRun,
            labels: historyApi.enableUserLabels ? labels : [],
            is_active: !!(scheduleActiveInput && scheduleActiveInput.checked),
        }).then(function () {
            closeFolderScheduleModal();
            return loadFolderTreeData().then(function () {
                refreshManageList();
                if (manageMsg) manageMsg.textContent = 'Расписание сохранено.';
            });
        }).catch(function (e) {
            setFolderScheduleModalMsg(e.message || String(e));
            if (scheduleSaveBtn) scheduleSaveBtn.disabled = false;
        });
    }

    function submitFolderScheduleDelete() {
        if (!schedulePending || !schedulePending.hasSchedule) return;
        if (!window.confirm('Удалить расписание для «' + schedulePending.folderName + '»?')) return;
        if (scheduleDeleteBtn) scheduleDeleteBtn.disabled = true;
        setFolderScheduleModalMsg('Удаление...');
        folderApiPost('schedule_delete', {
            folder_id: schedulePending.folderId,
        }).then(function () {
            closeFolderScheduleModal();
            return loadFolderTreeData().then(function () {
                refreshManageList();
                if (manageMsg) manageMsg.textContent = 'Расписание удалено.';
            });
        }).catch(function (e) {
            setFolderScheduleModalMsg(e.message || String(e));
            if (scheduleDeleteBtn) scheduleDeleteBtn.disabled = false;
        });
    }

    function setFolderShareMsg(msg) {
        if (shareMsg) shareMsg.textContent = msg || '';
    }

    function closeFolderShareModal() {
        setOpen(shareModal, false);
        sharePending = null;
        selectedShareUserId = null;
        setFolderShareMsg('');
        if (shareSubmitBtn) shareSubmitBtn.disabled = false;
    }

    function renderFolderShareUsers() {
        if (!shareTbody) return;
        shareTbody.innerHTML = '';
        var filterText = String(shareSearchInput ? shareSearchInput.value : '').trim().toLowerCase();
        var rows = shareUsers.filter(function (row) {
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
            shareTbody.appendChild(emptyTr);
            return;
        }
        rows.forEach(function (row) {
            var tr = document.createElement('tr');
            tr.classList.toggle('is-selected', row.id === selectedShareUserId);
            tr.addEventListener('click', function () {
                selectedShareUserId = row.id;
                setFolderShareMsg('');
                renderFolderShareUsers();
            });
            var idTd = document.createElement('td');
            idTd.textContent = String(row.id);
            tr.appendChild(idTd);
            var loginTd = document.createElement('td');
            loginTd.textContent = row.username || '—';
            tr.appendChild(loginTd);
            shareTbody.appendChild(tr);
        });
    }

    function loadFolderShareUsers() {
        if (shareUsersLoaded) {
            renderFolderShareUsers();
            return Promise.resolve();
        }
        if (shareSubmitBtn) shareSubmitBtn.disabled = true;
        return folderApiPost('web_users').then(function (data) {
            shareUsers = Array.isArray(data && data.users) ? data.users : [];
            shareUsersLoaded = true;
            renderFolderShareUsers();
        }).finally(function () {
            if (shareSubmitBtn) shareSubmitBtn.disabled = false;
        });
    }

    function openFolderShareModal(folderId, folderName) {
        if (!shareModal || !isAdminUser) return;
        sharePending = { folderId: folderId, folderName: folderName };
        selectedShareUserId = null;
        if (shareSearchInput) shareSearchInput.value = '';
        if (shareSubtitle) shareSubtitle.textContent = 'Папка «' + folderName + '»';
        setFolderShareMsg('');
        setOpen(shareModal, true);
        loadFolderShareUsers().catch(function (e) {
            setFolderShareMsg(e && e.message ? e.message : 'Ошибка загрузки списка пользователей');
        });
    }

    function submitFolderShare() {
        if (!sharePending) return;
        if (!selectedShareUserId) {
            setFolderShareMsg('Выберите пользователя.');
            return;
        }
        if (shareSubmitBtn) shareSubmitBtn.disabled = true;
        setFolderShareMsg('Отправка...');
        folderApiPost('share', {
            folder_id: sharePending.folderId,
            target_user_id: selectedShareUserId,
        }).then(function (data) {
            closeFolderShareModal();
            if (!manageMsg) return;
            if (data && data.notify_sent) {
                manageMsg.textContent = data.already_had
                    ? 'Доступ уже был. Уведомление отправлено в чат.'
                    : 'Доступ отправлен. Пользователь получит сообщение в чат поддержки.';
            } else if (data && data.notify_error) {
                manageMsg.textContent = 'Доступ выдан, но сообщение в чат не отправилось.';
            } else {
                manageMsg.textContent = data && data.already_had
                    ? 'У пользователя уже есть доступ к этой папке.'
                    : 'Доступ отправлен.';
            }
        }).catch(function (e) {
            setFolderShareMsg(e.message || String(e));
            if (shareSubmitBtn) shareSubmitBtn.disabled = false;
        });
    }

    function toggleFolderShared(node) {
        var next = !node.is_shared;
        folderApiPost('set_shared', {
            folder_id: node.id,
            is_shared: next,
        }).then(function () {
            return loadFolderTreeData().then(function () {
                refreshManageList();
                if (manageMsg) {
                    manageMsg.textContent = next
                        ? 'Папка сделана общей.'
                        : 'Папка больше не общая.';
                }
            });
        }).catch(function (e) {
            if (manageMsg) manageMsg.textContent = 'Ошибка: ' + (e.message || e);
        });
    }

    function buildToggle(expandedMap, node, hasChildren, refresh) {
        var toggle = document.createElement('span');
        toggle.className = 'hw-folder-node__toggle';
        toggle.textContent = hasChildren ? (expandedMap[node.id] ? '▾' : '▸') : '';
        toggle.addEventListener('click', function (ev) {
            ev.stopPropagation();
            if (!hasChildren) return;
            expandedMap[node.id] = !expandedMap[node.id];
            refresh();
        });
        return toggle;
    }

    function appendChildren(wrap, node, expandedMap, builder) {
        if (!(node.children && node.children.length)) return;
        var childrenWrap = document.createElement('div');
        childrenWrap.className = 'hw-folder-node__children';
        node.children.forEach(function (child) {
            childrenWrap.appendChild(builder(child));
        });
        wrap.appendChild(childrenWrap);
    }

    function buildCreateParentNode(node) {
        var wrap = document.createElement('div');
        var hasChildren = node.children && node.children.length;
        wrap.className = 'hw-folder-node hw-folder-node--pick' + (expandedCreateParentIds[node.id] ? ' is-expanded' : '');
        var row = document.createElement('div');
        row.className = 'hw-folder-node__row';
        var toggle = buildToggle(expandedCreateParentIds, node, hasChildren, refreshCreateParentList);
        row.appendChild(toggle);
        var name = document.createElement('span');
        name.className = 'hw-folder-node__name';
        name.textContent = node.name;
        row.appendChild(name);
        var count = document.createElement('span');
        count.className = 'hw-folder-node__count';
        count.textContent = node.direct_files_count ? String(node.direct_files_count) : '';
        row.appendChild(count);
        var pickLabel = document.createElement('span');
        pickLabel.className = 'hw-folder-node__pick-label';
        pickLabel.textContent = 'Подпапка';
        row.appendChild(pickLabel);
        row.addEventListener('click', function (ev) {
            if (ev.target === toggle) return;
            openEmptyFolderNameModal(node.id, node.name);
        });
        wrap.appendChild(row);
        appendChildren(wrap, node, expandedCreateParentIds, buildCreateParentNode);
        return wrap;
    }

    function buildPickNode(node) {
        var wrap = document.createElement('div');
        var hasChildren = node.children && node.children.length;
        wrap.className = 'hw-folder-node hw-folder-node--pick' + (expandedPickIds[node.id] ? ' is-expanded' : '');
        var row = document.createElement('div');
        row.className = 'hw-folder-node__row';
        var toggle = buildToggle(expandedPickIds, node, hasChildren, refreshPickList);
        row.appendChild(toggle);
        var name = document.createElement('span');
        name.className = 'hw-folder-node__name';
        name.textContent = node.name;
        row.appendChild(name);
        var count = document.createElement('span');
        count.className = 'hw-folder-node__count';
        count.textContent = node.direct_files_count ? String(node.direct_files_count) : '';
        row.appendChild(count);
        var pickLabel = document.createElement('span');
        pickLabel.className = 'hw-folder-node__pick-label';
        pickLabel.textContent = 'Выбрать';
        row.appendChild(pickLabel);
        row.addEventListener('click', function (ev) {
            if (ev.target === toggle) return;
            openInsertConfirm(node.id, node.name, folderPickUploadIds);
        });
        wrap.appendChild(row);
        appendChildren(wrap, node, expandedPickIds, buildPickNode);
        return wrap;
    }

    function buildManageNode(node) {
        var wrap = document.createElement('div');
        var hasChildren = node.children && node.children.length;
        wrap.className = 'hw-folder-node' + (expandedManageIds[node.id] ? ' is-expanded' : '');
        var row = document.createElement('div');
        row.className = 'hw-folder-node__row';
        var toggle = buildToggle(expandedManageIds, node, hasChildren, refreshManageList);
        row.appendChild(toggle);

        var nameWrap = document.createElement('span');
        nameWrap.className = 'hw-folder-node__name-wrap';
        var name = document.createElement('span');
        name.className = 'hw-folder-node__name';
        name.textContent = node.name;
        nameWrap.appendChild(name);
        if (node.is_granted) {
            var badge = document.createElement('span');
            badge.className = 'hw-folder-node__badge';
            badge.textContent = 'общая';
            nameWrap.appendChild(badge);
        } else {
            var renameBtn = document.createElement('button');
            renameBtn.type = 'button';
            renameBtn.className = 'hw-folder-node__rename';
            renameBtn.title = 'Переименовать папку';
            renameBtn.setAttribute('aria-label', 'Переименовать папку «' + node.name + '»');
            renameBtn.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 20h4l10.5-10.5a1.4 1.4 0 0 0 0-2L14.5 3.5a1.4 1.4 0 0 0-2 0L3 13v4Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M13.5 5.5l5 5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>';
            renameBtn.addEventListener('click', function (ev) {
                ev.stopPropagation();
                openRenameFolderModal(node.id, node.name);
            });
            nameWrap.appendChild(renameBtn);
        }
        row.appendChild(nameWrap);

        var right = document.createElement('span');
        right.className = 'hw-folder-node__right';
        var count = document.createElement('span');
        count.className = 'hw-folder-node__count';
        count.textContent = node.direct_files_count ? String(node.direct_files_count) : '';
        right.appendChild(count);

        var actions = document.createElement('span');
        actions.className = 'hw-folder-node__actions';
        if (!node.is_granted) {
            if (isAdminUser) {
                var sharedBtn = document.createElement('button');
                sharedBtn.type = 'button';
                sharedBtn.className = 'hw-folder-node__action' + (node.is_shared ? ' hw-folder-node__action--shared-active' : '');
                sharedBtn.innerHTML = SHARED_ICON;
                sharedBtn.title = node.is_shared ? 'Папка общая' : 'Сделать папку общей';
                sharedBtn.setAttribute('aria-label', sharedBtn.title + ': ' + node.name);
                sharedBtn.addEventListener('click', function (ev) {
                    ev.stopPropagation();
                    toggleFolderShared(node);
                });
                actions.appendChild(sharedBtn);
                if (node.is_shared) {
                    var sendBtn = document.createElement('button');
                    sendBtn.type = 'button';
                    sendBtn.className = 'hw-folder-node__action';
                    sendBtn.innerHTML = SEND_ICON;
                    sendBtn.title = 'Отправить доступ';
                    sendBtn.setAttribute('aria-label', 'Отправить доступ к папке «' + node.name + '»');
                    sendBtn.addEventListener('click', function (ev) {
                        ev.stopPropagation();
                        openFolderShareModal(node.id, node.name);
                    });
                    actions.appendChild(sendBtn);
                }
            }
            var scheduleBtn = document.createElement('button');
            scheduleBtn.type = 'button';
            scheduleBtn.className = 'hw-folder-node__action';
            if (node.schedule && node.schedule.is_active) {
                scheduleBtn.className += ' hw-folder-node__action--schedule-active';
            }
            scheduleBtn.innerHTML = CALENDAR_ICON;
            scheduleBtn.title = node.schedule && node.schedule.is_active
                ? 'Расписание активно'
                : 'Настроить расписание';
            scheduleBtn.setAttribute(
                'aria-label',
                (node.schedule && node.schedule.is_active
                    ? 'Расписание активно: '
                    : 'Настроить расписание: ') + node.name
            );
            scheduleBtn.addEventListener('click', function (ev) {
                ev.stopPropagation();
                loadFolderScheduleAndOpen(node.id, node.name, node.schedule || null);
            });
            actions.appendChild(scheduleBtn);
        }
        var goBtn = document.createElement('button');
        goBtn.type = 'button';
        goBtn.className = 'hw-folder-node__action';
        goBtn.title = 'Открыть папку';
        goBtn.textContent = '→';
        goBtn.addEventListener('click', function (ev) {
            ev.stopPropagation();
            closeManageModal();
            navigateToFolder(node.id);
        });
        actions.appendChild(goBtn);
        if (!node.is_granted) {
            var delBtn = document.createElement('button');
            delBtn.type = 'button';
            delBtn.className = 'hw-folder-node__action hw-folder-node__action--danger';
            delBtn.title = 'Удалить папку';
            delBtn.textContent = '×';
            delBtn.addEventListener('click', function (ev) {
                ev.stopPropagation();
                if (!window.confirm('Удалить «' + node.name + '»?')) return;
                folderApiPost('delete', { folder_id: node.id }).then(function () {
                    return afterFolderStructureChanged(node.id);
                }).catch(function (e) {
                    if (manageMsg) manageMsg.textContent = 'Ошибка: ' + (e.message || e);
                });
            });
            actions.appendChild(delBtn);
        }
        right.appendChild(actions);
        row.appendChild(right);
        row.addEventListener('click', function (ev) {
            if (ev.target.closest('.hw-folder-node__toggle, .hw-folder-node__rename, .hw-folder-node__actions')) {
                return;
            }
            closeManageModal();
            navigateToFolder(node.id);
        });
        wrap.appendChild(row);
        appendChildren(wrap, node, expandedManageIds, buildManageNode);
        return wrap;
    }

    function closeActionModal() {
        setOpen(actionModal, false);
        folderActionUploadIds = [];
    }

    var hintEl = null;
    var hintTimer = null;

    function hideHint() {
        if (hintTimer) {
            clearTimeout(hintTimer);
            hintTimer = null;
        }
        if (hintEl) hintEl.classList.remove('is-visible');
    }

    function ensureHintEl() {
        if (hintEl) return hintEl;
        hintEl = document.createElement('div');
        hintEl.className = 'hw-hint';
        hintEl.setAttribute('role', 'status');
        hintEl.innerHTML =
            '<svg class="hw-hint__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
            '<circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.7"/>' +
            '<path d="M12 11v5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>' +
            '<circle cx="12" cy="8" r="1" fill="currentColor"/>' +
            '</svg>' +
            '<span class="hw-hint__text"></span>' +
            '<span class="hw-hint__arrow" aria-hidden="true"></span>';
        document.body.appendChild(hintEl);
        return hintEl;
    }

    function showHint(text, anchor) {
        var el = ensureHintEl();
        var textEl = el.querySelector('.hw-hint__text');
        var arrow = el.querySelector('.hw-hint__arrow');
        if (textEl) textEl.textContent = text;
        el.classList.remove('is-visible', 'is-above', 'is-below');
        el.style.left = '0px';
        el.style.top = '0px';
        el.style.visibility = 'hidden';
        el.style.opacity = '0';

        var rect = (anchor && anchor.getBoundingClientRect)
            ? anchor.getBoundingClientRect()
            : { left: 16, right: 16, top: 16, bottom: 16, width: 0, height: 0 };
        var gap = 10;
        var width = el.offsetWidth || 240;
        var height = el.offsetHeight || 48;
        var vw = window.innerWidth;
        var vh = window.innerHeight;
        var placeAbove = rect.bottom + gap + height > vh - 8 && rect.top - gap - height > 8;
        var left = rect.right - width;
        left = Math.max(12, Math.min(left, vw - width - 12));
        var top = placeAbove ? (rect.top - gap - height) : (rect.bottom + gap);
        top = Math.max(8, Math.min(top, vh - height - 8));
        el.style.left = Math.round(left) + 'px';
        el.style.top = Math.round(top) + 'px';
        el.classList.add(placeAbove ? 'is-above' : 'is-below');
        if (arrow) {
            var arrowLeft = rect.left + rect.width / 2 - left - 5;
            arrow.style.left = Math.max(12, Math.min(arrowLeft, width - 22)) + 'px';
        }
        el.style.visibility = '';
        el.style.opacity = '';
        requestAnimationFrame(function () {
            el.classList.add('is-visible');
        });
        if (hintTimer) clearTimeout(hintTimer);
        hintTimer = setTimeout(hideHint, 2800);
    }

    function openActionModal(ev) {
        var ids = historyApi.getSelectedUploadIds();
        if (!ids.length) {
            showHint('Сначала выберите матчи', (ev && ev.currentTarget) || foldersBtn);
            return;
        }
        hideHint();
        folderActionUploadIds = ids.slice();
        if (actionSubtitle) {
            actionSubtitle.textContent = 'Выбрано файлов: ' + ids.length;
        }
        setOpen(actionModal, true);
    }

    function closePickModal() {
        setOpen(pickModal, false);
        folderPickUploadIds = [];
        if (pickMsg) pickMsg.textContent = '';
    }

    function openPickModal(ids) {
        if (!ids || !ids.length) return;
        folderPickUploadIds = ids.slice();
        if (pickSubtitle) {
            pickSubtitle.textContent = 'Выберите папку · файлов: ' + ids.length;
        }
        if (pickMsg) pickMsg.textContent = '';
        setOpen(pickModal, true);
        loadFolderTreeData().then(refreshPickList).catch(function (e) {
            if (pickMsg) pickMsg.textContent = e.message || String(e);
        });
    }

    function closeInsertConfirm() {
        setOpen(insertModal, false);
        folderInsertPending = null;
        if (insertMsg) insertMsg.textContent = '';
        if (insertSubmitBtn) insertSubmitBtn.disabled = false;
    }

    function openInsertConfirm(folderId, folderName, ids) {
        closePickModal();
        folderInsertPending = {
            folderId: folderId,
            folderName: folderName,
            ids: (ids || []).slice(),
        };
        var n = folderInsertPending.ids.length;
        if (insertText) {
            insertText.textContent = 'Добавить ' + n + ' ' + filesWord(n) + ' в папку «' + folderName + '»?';
        }
        if (insertMsg) insertMsg.textContent = '';
        setOpen(insertModal, true);
    }

    function submitInsertConfirm() {
        if (!folderInsertPending) return;
        if (insertSubmitBtn) insertSubmitBtn.disabled = true;
        if (insertMsg) insertMsg.textContent = 'Вставка…';
        var pending = folderInsertPending;
        folderApiPost('add_items', {
            folder_id: pending.folderId,
            upload_ids: pending.ids,
        }).then(function (data) {
            var added = (data && data.added_count) || 0;
            closeInsertConfirm();
            historyApi.clearSelection();
            updateSelectionUi();
            if (historyApi.getFolderId() === pending.folderId) historyApi.pollHistory();
            window.alert('В папку «' + pending.folderName + '» добавлено файлов: ' + added + '.');
        }).catch(function (e) {
            if (insertMsg) insertMsg.textContent = e.message || String(e);
            if (insertSubmitBtn) insertSubmitBtn.disabled = false;
        });
    }

    function closeCreateParentModal() {
        setOpen(createParentModal, false);
        if (createParentMsg) createParentMsg.textContent = '';
    }

    function openCreateParentModal() {
        if (createParentMsg) createParentMsg.textContent = '';
        setOpen(createParentModal, true);
        loadFolderTreeData().then(refreshCreateParentList).catch(function (e) {
            if (createParentMsg) createParentMsg.textContent = e.message || String(e);
        });
    }

    function closeManageModal() {
        setOpen(manageModal, false);
        if (manageMsg) manageMsg.textContent = '';
    }

    function openManageModal() {
        if (manageMsg) manageMsg.textContent = '';
        setOpen(manageModal, true);
        loadFolderTreeData().then(refreshManageList).catch(function (e) {
            if (manageMsg) manageMsg.textContent = 'Ошибка: ' + (e.message || e);
        });
    }

    function setNameMsg(text) {
        if (nameMsg) nameMsg.textContent = text || '';
    }

    function closeNameModal() {
        setOpen(nameModal, false);
        folderNamePending = null;
        setNameMsg('');
        if (nameSubmitBtn) nameSubmitBtn.disabled = false;
    }

    function openFolderNameModal(options) {
        var opts = options || {};
        folderNamePending = {
            mode: opts.mode || 'empty',
            parentId: Object.prototype.hasOwnProperty.call(opts, 'parentId') ? opts.parentId : null,
            uploadIds: opts.uploadIds || [],
            folderId: opts.folderId != null ? opts.folderId : null,
        };
        if (nameTitle) nameTitle.textContent = opts.title || 'Новая папка';
        if (nameSubtitle) {
            nameSubtitle.textContent = opts.subtitle || '';
            nameSubtitle.style.display = opts.subtitle ? '' : 'none';
        }
        if (nameSubmitBtn) {
            nameSubmitBtn.textContent = opts.submitLabel || (opts.mode === 'rename' ? 'Сохранить' : 'Создать');
            nameSubmitBtn.disabled = false;
        }
        if (nameInput) {
            nameInput.value = String(opts.defaultName != null ? opts.defaultName : defaultNewFolderName('Папка'));
        }
        setNameMsg('');
        setOpen(nameModal, true);
        if (nameInput) {
            nameInput.focus();
            nameInput.select();
        }
    }

    function openEmptyFolderNameModal(parentId, parentName) {
        var isSub = parentId != null;
        closeCreateParentModal();
        openFolderNameModal({
            mode: 'empty',
            parentId: parentId,
            uploadIds: [],
            title: isSub ? 'Новая подпапка' : 'Новая папка',
            subtitle: isSub ? ('Внутри «' + parentName + '»') : 'Корневая папка',
            defaultName: defaultNewFolderName(isSub ? 'Подпапка' : 'Папка'),
        });
    }

    function openRenameFolderModal(folderId, currentName) {
        openFolderNameModal({
            mode: 'rename',
            folderId: folderId,
            title: 'Переименовать папку',
            subtitle: '',
            defaultName: currentName,
            submitLabel: 'Сохранить',
        });
    }

    function openCreateWithSelected(ids) {
        var parentId = getNewFolderParentId();
        openFolderNameModal({
            mode: 'with_files',
            parentId: parentId,
            uploadIds: ids || [],
            title: parentId ? 'Новая подпапка' : 'Новая папка',
            subtitle: 'Выбрано файлов: ' + (ids || []).length,
            defaultName: defaultNewFolderName(parentId ? 'Подпапка' : 'Папка'),
        });
    }

    function submitNameModal() {
        if (!folderNamePending || !nameInput) return;
        var name = String(nameInput.value || '').trim();
        if (!name) {
            setNameMsg('Введите название папки.');
            nameInput.focus();
            return;
        }
        if (nameSubmitBtn) nameSubmitBtn.disabled = true;
        var pending = folderNamePending;
        if (pending.mode === 'rename') {
            setNameMsg('Сохранение…');
            folderApiPost('update', { folder_id: pending.folderId, name: name }).then(function () {
                closeNameModal();
                return afterFolderStructureChanged();
            }).catch(function (e) {
                setNameMsg(e.message || String(e));
                if (nameSubmitBtn) nameSubmitBtn.disabled = false;
            });
            return;
        }
        setNameMsg('Создание…');
        folderApiPost('create', { name: name, parent_id: pending.parentId }).then(function (data) {
            var folder = data && data.folder;
            var createdId = folder && folder.id;
            var ids = pending.uploadIds || [];
            if (createdId && ids.length) {
                return folderApiPost('add_items', { folder_id: createdId, upload_ids: ids }).then(function () {
                    return createdId;
                });
            }
            return createdId;
        }).then(function (createdId) {
            closeNameModal();
            historyApi.clearSelection();
            updateSelectionUi();
            return afterFolderStructureChanged().then(function () {
                if (createdId && pending.mode === 'with_files') {
                    navigateToFolder(createdId);
                }
            });
        }).catch(function (e) {
            setNameMsg(e.message || String(e));
            if (nameSubmitBtn) nameSubmitBtn.disabled = false;
        });
    }

    function removeSelectedFromFolder() {
        var folderId = historyApi.getFolderId();
        var ids = historyApi.getSelectedUploadIds();
        if (!folderId || !ids.length) return;
        folderApiPost('remove_items', { folder_id: folderId, upload_ids: ids }).then(function () {
            historyApi.clearSelection();
            updateSelectionUi();
            historyApi.pollHistory();
            return loadCurrentFolderView();
        }).catch(function (e) {
            window.alert(e.message || String(e));
        });
    }

    if (manageBtn) manageBtn.addEventListener('click', openManageModal);
    if (foldersBtn) foldersBtn.addEventListener('click', openActionModal);
    if (removeBtn) removeBtn.addEventListener('click', removeSelectedFromFolder);
    document.addEventListener('click', function (ev) {
        if (!hintEl || !hintEl.classList.contains('is-visible')) return;
        if (foldersBtn && foldersBtn.contains(ev.target)) return;
        hideHint();
    });
    window.addEventListener('scroll', hideHint, true);
    window.addEventListener('resize', hideHint);
    if (folderViewBackBtn) {
        folderViewBackBtn.addEventListener('click', goBack);
    }
    if (folderViewHomeBtn) {
        folderViewHomeBtn.addEventListener('click', function () {
            if (!historyApi.getFolderId()) return;
            goHome(false);
        });
    }
    if (folderViewUpBtn) {
        folderViewUpBtn.addEventListener('click', function () {
            var parentId = getCurrentParentId();
            if (!parentId) return;
            navigateToFolder(parentId);
        });
    }

    var actionCancel = document.getElementById('folderActionModalCancelBtn');
    var actionCreate = document.getElementById('folderActionCreateBtn');
    var actionInsert = document.getElementById('folderActionInsertBtn');
    if (actionCancel) actionCancel.addEventListener('click', closeActionModal);
    if (document.getElementById('folderActionModalOverlay')) {
        document.getElementById('folderActionModalOverlay').addEventListener('click', closeActionModal);
    }
    if (actionCreate) {
        actionCreate.addEventListener('click', function () {
            var ids = folderActionUploadIds.slice();
            closeActionModal();
            openCreateWithSelected(ids);
        });
    }
    if (actionInsert) {
        actionInsert.addEventListener('click', function () {
            var ids = folderActionUploadIds.slice();
            closeActionModal();
            openPickModal(ids);
        });
    }

    if (document.getElementById('folderPickModalClose')) {
        document.getElementById('folderPickModalClose').addEventListener('click', closePickModal);
    }
    if (document.getElementById('folderPickModalOverlay')) {
        document.getElementById('folderPickModalOverlay').addEventListener('click', closePickModal);
    }
    if (document.getElementById('folderInsertConfirmCancelBtn')) {
        document.getElementById('folderInsertConfirmCancelBtn').addEventListener('click', closeInsertConfirm);
    }
    if (document.getElementById('folderInsertConfirmModalOverlay')) {
        document.getElementById('folderInsertConfirmModalOverlay').addEventListener('click', closeInsertConfirm);
    }
    if (insertSubmitBtn) insertSubmitBtn.addEventListener('click', submitInsertConfirm);

    if (document.getElementById('folderCreateRootBtn')) {
        document.getElementById('folderCreateRootBtn').addEventListener('click', function () {
            openEmptyFolderNameModal(null, '');
        });
    }
    if (document.getElementById('folderCreateParentModalClose')) {
        document.getElementById('folderCreateParentModalClose').addEventListener('click', closeCreateParentModal);
    }
    if (document.getElementById('folderCreateParentModalOverlay')) {
        document.getElementById('folderCreateParentModalOverlay').addEventListener('click', closeCreateParentModal);
    }
    if (document.getElementById('folderManageCreateBtn')) {
        document.getElementById('folderManageCreateBtn').addEventListener('click', openCreateParentModal);
    }
    if (document.getElementById('folderManageModalClose')) {
        document.getElementById('folderManageModalClose').addEventListener('click', closeManageModal);
    }
    if (document.getElementById('folderManageModalOverlay')) {
        document.getElementById('folderManageModalOverlay').addEventListener('click', closeManageModal);
    }
    if (document.getElementById('folderNameModalCancelBtn')) {
        document.getElementById('folderNameModalCancelBtn').addEventListener('click', closeNameModal);
    }
    if (document.getElementById('folderNameModalOverlay')) {
        document.getElementById('folderNameModalOverlay').addEventListener('click', closeNameModal);
    }
    if (nameSubmitBtn) nameSubmitBtn.addEventListener('click', submitNameModal);
    if (nameInput) {
        nameInput.addEventListener('keydown', function (ev) {
            if (ev.key === 'Enter') {
                ev.preventDefault();
                submitNameModal();
            }
        });
    }
    if (document.getElementById('folderScheduleCancelBtn')) {
        document.getElementById('folderScheduleCancelBtn').addEventListener('click', closeFolderScheduleModal);
    }
    if (document.getElementById('folderScheduleModalOverlay')) {
        document.getElementById('folderScheduleModalOverlay').addEventListener('click', closeFolderScheduleModal);
    }
    if (scheduleSaveBtn) scheduleSaveBtn.addEventListener('click', submitFolderScheduleSave);
    if (scheduleDeleteBtn) scheduleDeleteBtn.addEventListener('click', submitFolderScheduleDelete);
    if (document.getElementById('folderShareCancelBtn')) {
        document.getElementById('folderShareCancelBtn').addEventListener('click', closeFolderShareModal);
    }
    if (document.getElementById('folderShareModalOverlay')) {
        document.getElementById('folderShareModalOverlay').addEventListener('click', closeFolderShareModal);
    }
    if (shareSubmitBtn) shareSubmitBtn.addEventListener('click', submitFolderShare);
    if (shareSearchInput) shareSearchInput.addEventListener('input', renderFolderShareUsers);

    window.addEventListener('popstate', function () {
        var folderId = readFolderIdFromUrl();
        historyApi.setFolderId(folderId, true);
        loadCurrentFolderView();
        updateSelectionUi();
        updateNavButtons();
    });

    historyApi.onSelectionChange = updateSelectionUi;
    historyApi.afterRender = updateSelectionUi;

    var initialId = readFolderIdFromUrl();
    if (initialId) {
        historyApi.setFolderId(initialId, true);
        loadCurrentFolderView();
    }
    updateSelectionUi();
    updateNavButtons();
})();
