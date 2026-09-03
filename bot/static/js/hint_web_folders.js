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
    var folderViewUpBtn = document.getElementById('folderViewUpBtn');

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
        if (removeBtn) {
            removeBtn.hidden = !inFolder;
            removeBtn.setAttribute('aria-hidden', inFolder ? 'false' : 'true');
            removeBtn.disabled = !inFolder || !ids.length;
        }
    }

    function navigateToFolder(folderId, replace) {
        writeFolderIdToUrl(folderId, replace);
        historyApi.setFolderId(folderId);
        loadCurrentFolderView();
        updateSelectionUi();
    }

    function goHome(replace) {
        currentFolderMeta = null;
        if (titleEl) titleEl.textContent = 'История загрузок';
        if (folderViewBar) {
            folderViewBar.classList.remove('is-visible');
            folderViewBar.setAttribute('aria-hidden', 'true');
        }
        navigateToFolder(null, replace);
    }

    function renderFolderBar(meta) {
        if (!folderViewBar || !folderViewSubfolders) return;
        if (!meta || !meta.folder) {
            folderViewBar.classList.remove('is-visible');
            folderViewBar.setAttribute('aria-hidden', 'true');
            if (titleEl) titleEl.textContent = 'История загрузок';
            updateSelectionUi();
            return;
        }
        if (titleEl) titleEl.textContent = meta.folder.name || 'Папка';
        folderViewSubfolders.innerHTML = '';
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
        if (folderViewUpBtn) {
            var hasParent = !!(meta.parent && meta.parent.id);
            folderViewUpBtn.title = hasParent ? 'В родительскую папку' : 'Ко всем загрузкам';
            folderViewUpBtn.setAttribute('aria-label', folderViewUpBtn.title);
        }
        folderViewBar.classList.add('is-visible');
        folderViewBar.setAttribute('aria-hidden', 'false');
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
            goHome(true);
        });
    }

    function afterFolderStructureChanged(deletedFolderId) {
        return loadFolderTreeData().then(function () {
            if (manageModal && manageModal.classList.contains('is-open')) refreshManageList();
            if (pickModal && pickModal.classList.contains('is-open')) refreshPickList();
            if (createParentModal && createParentModal.classList.contains('is-open')) refreshCreateParentList();
            var currentId = historyApi.getFolderId();
            if (currentId) {
                if (deletedFolderId != null && Number(deletedFolderId) === Number(currentId)) {
                    goHome(true);
                    return;
                }
                if (!folderExistsInTree(folderTreeData, currentId)) {
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

    function refreshPickList() {
        if (!pickTree) return;
        pickTree.innerHTML = '';
        if (!folderTreeData.length) {
            pickTree.appendChild(emptyTreeMessage('Папок пока нет. Сначала создайте папку.'));
            return;
        }
        folderTreeData.forEach(function (node) {
            pickTree.appendChild(buildPickNode(node));
        });
    }

    function refreshCreateParentList() {
        if (!createParentTree) return;
        createParentTree.innerHTML = '';
        folderTreeData.forEach(function (node) {
            createParentTree.appendChild(buildCreateParentNode(node));
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
        row.appendChild(nameWrap);

        var right = document.createElement('span');
        right.className = 'hw-folder-node__right';
        var count = document.createElement('span');
        count.className = 'hw-folder-node__count';
        count.textContent = node.direct_files_count ? String(node.direct_files_count) : '';
        right.appendChild(count);

        var actions = document.createElement('span');
        actions.className = 'hw-folder-node__actions';
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
        right.appendChild(actions);
        row.appendChild(right);
        wrap.appendChild(row);
        appendChildren(wrap, node, expandedManageIds, buildManageNode);
        return wrap;
    }

    function closeActionModal() {
        setOpen(actionModal, false);
        folderActionUploadIds = [];
    }

    function showHint(text) {
        if (historyApi.showToast) {
            historyApi.showToast(text);
            return;
        }
        window.alert(text);
    }

    function openActionModal() {
        var ids = historyApi.getSelectedUploadIds();
        if (!ids.length) {
            showHint('Сначала выберите матчи');
            return;
        }
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
    if (folderViewUpBtn) {
        folderViewUpBtn.addEventListener('click', function () {
            var parent = currentFolderMeta && currentFolderMeta.parent;
            if (parent && parent.id) {
                navigateToFolder(parent.id);
                return;
            }
            goHome(false);
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

    window.addEventListener('popstate', function () {
        var folderId = readFolderIdFromUrl();
        historyApi.setFolderId(folderId, true);
        loadCurrentFolderView();
        updateSelectionUi();
    });

    historyApi.onSelectionChange = updateSelectionUi;
    historyApi.afterRender = updateSelectionUi;

    var initialId = readFolderIdFromUrl();
    if (initialId) {
        historyApi.setFolderId(initialId, true);
        loadCurrentFolderView();
    }
    updateSelectionUi();
})();
