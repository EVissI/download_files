(function () {
    if (window.__webSupportBooted) return;
    window.__webSupportBooted = true;
    var loginUrl = '/web/hints/login';

    function $(sel, root) {
        return (root || document).querySelector(sel);
    }

    function escapeHtml(value) {
        return String(value || '').replace(/[&<>"']/g, function (ch) {
            return ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;',
            })[ch];
        });
    }

    function formatTime(iso) {
        if (!iso) return '';
        var dt = new Date(iso);
        if (Number.isNaN(dt.getTime())) return '';
        return dt.toLocaleString('ru-RU', {
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
        });
    }

    function renderMessage(msg, mineRole) {
        var mine = msg.role === mineRole;
        var who = msg.role === 'admin' ? ('Поддержка' + (msg.author_login ? ' · ' + msg.author_login : '')) : (msg.author_login || 'Вы');
        var meta = escapeHtml(who) + ' · ' + escapeHtml(formatTime(msg.created_at));
        if (mineRole === 'admin' && msg.role === 'user' && msg.source_tab) {
            meta += ' · <span class="support-msg-source">' + escapeHtml(msg.source_tab) + '</span>';
        }
        var files = (msg.attachments || []).map(function (att) {
            if (att.is_image) {
                return '<a class="support-file-link" href="' + escapeHtml(att.url) + '" target="_blank" rel="noopener">' +
                    '<img class="support-file-thumb" src="' + escapeHtml(att.url) + '" alt="' + escapeHtml(att.filename) + '">' +
                    '</a>';
            }
            return '<a class="support-file-link" href="' + escapeHtml(att.url) + '" target="_blank" rel="noopener">' +
                escapeHtml(att.filename) + '</a>';
        }).join('');
        var body = msg.body ? '<div class="support-msg-body">' + escapeHtml(msg.body) + '</div>' : '';
        var actions = '';
        if (msg.folder_open_url) {
            actions = '<div class="support-msg-actions">' +
                '<a class="support-send-hints-btn support-folder-open-btn" href="' +
                escapeHtml(msg.folder_open_url) + '">' +
                escapeHtml(msg.folder_open_label || 'Открыть папку') +
                '</a></div>';
        } else if (mineRole === 'admin' && msg.can_send_to_hints) {
            actions = '<div class="support-msg-actions">' +
                '<button type="button" class="support-send-hints-btn" data-send-to-hints="' +
                escapeHtml(msg.id) + '">В ошибки</button></div>';
        }
        return '<div class="support-msg ' + (mine ? 'is-mine' : 'is-admin') + '" data-id="' + msg.id + '">' +
            '<div class="support-msg-meta">' + meta + '</div>' +
            body +
            (files ? '<div class="support-files">' + files + '</div>' : '') +
            actions +
            '</div>';
    }

    function appendMessages(box, messages, mineRole) {
        if (!box || !messages || !messages.length) return;
        var html = messages.filter(function (msg) {
            if (!msg || !msg.id) return true;
            return !box.querySelector('.support-msg[data-id="' + msg.id + '"]');
        }).map(function (msg) { return renderMessage(msg, mineRole); }).join('');
        if (!html) return;
        var empty = box.querySelector('.support-empty');
        if (empty) empty.remove();
        box.insertAdjacentHTML('beforeend', html);
        box.scrollTop = box.scrollHeight;
    }

    function lastId(box) {
        var nodes = box.querySelectorAll('.support-msg[data-id]');
        if (!nodes.length) return 0;
        return Number(nodes[nodes.length - 1].getAttribute('data-id') || 0);
    }

    function setBadge(el, count) {
        if (!el) return;
        var n = Number(count || 0);
        var show = n > 0;
        var isDot = el.hasAttribute('data-support-nav-badge')
            || el.hasAttribute('data-support-fab-badge');
        if (isDot) {
            if (el.classList.contains('is-on') === show) return;
            el.classList.toggle('is-on', show);
            return;
        }
        var label = show ? (n > 99 ? '99+' : String(n)) : '';
        if (el.hidden === !show && el.textContent === label) return;
        el.hidden = !show;
        el.textContent = label;
    }

    var NOTIFY_KEY = 'web_support_last_msg_id';
    var USER_NOTIFY_KEY = 'web_support_user_last_msg_id';
    var notifyGestureBound = false;

    function isTopWindow() {
        try { return window === window.top; } catch (e) { return false; }
    }

    function onSupportPage() {
        return (location.pathname.replace(/\/$/, '') || '/') === '/web/support';
    }

    function bindNotifyGesture() {
        if (notifyGestureBound || !isTopWindow()) return;
        notifyGestureBound = true;
        function ask() {
            document.removeEventListener('pointerdown', ask, true);
            if (!window.Notification || Notification.permission !== 'default') return;
            Notification.requestPermission().catch(function () {});
        }
        document.addEventListener('pointerdown', ask, true);
    }

    function notifyUserNewMessage(data) {
        if (!isTopWindow()) return;
        if (!data || data.admin) return;
        var msgId = Number(data.latest_message_id || 0);
        if (!msgId) return;
        var last = 0;
        try { last = Number(localStorage.getItem(USER_NOTIFY_KEY) || 0); } catch (e) {}
        if (!last) {
            try { localStorage.setItem(USER_NOTIFY_KEY, String(msgId)); } catch (e) {}
            return;
        }
        if (msgId <= last) return;
        try { localStorage.setItem(USER_NOTIFY_KEY, String(msgId)); } catch (e) {}
        if (!data.unread) return;
        var panel = $('#supportPanel');
        if (panel && !panel.hidden) return;
        if (!window.Notification || Notification.permission !== 'granted') return;
        try {
            var n = new Notification('Поддержка', {
                body: data.latest_preview || 'Новое сообщение',
                tag: 'web-support-user',
                renotify: true,
            });
            n.onclick = function () {
                n.close();
                window.focus();
                if (window.WebSupportWidget && typeof window.WebSupportWidget.open === 'function') {
                    window.WebSupportWidget.open();
                }
            };
        } catch (e) {}
    }

    function setUserUnread(count) {
        var n = Number(count || 0);
        document.querySelectorAll('[data-support-fab-badge]').forEach(function (el) {
            setBadge(el, n);
        });
        var fab = $('#supportFab');
        if (!fab) return;
        var has = n > 0;
        fab.classList.toggle('is-unread', has);
        fab.setAttribute('aria-label', has ? 'Есть новое сообщение от поддержки' : 'Написать в поддержку');
        fab.setAttribute('title', has ? 'Есть новое сообщение от поддержки' : 'Поддержка');
    }

    function notifyAdminNewMessage(data) {
        if (!isTopWindow()) return;
        if (!data || !data.admin) return;
        var msgId = Number(data.latest_message_id || 0);
        if (!msgId) return;
        var last = 0;
        try { last = Number(localStorage.getItem(NOTIFY_KEY) || 0); } catch (e) {}
        if (!last) {
            try { localStorage.setItem(NOTIFY_KEY, String(msgId)); } catch (e) {}
            return;
        }
        if (msgId <= last) return;
        try { localStorage.setItem(NOTIFY_KEY, String(msgId)); } catch (e) {}
        if (!data.unread) return;
        if (onSupportPage()) return;
        if (!window.Notification || Notification.permission !== 'granted') return;
        var body = (data.latest_login ? data.latest_login + ': ' : '') +
            (data.latest_preview || 'Новое сообщение');
        try {
            var n = new Notification('Поддержка', {
                body: body,
                tag: 'web-support',
                renotify: true,
            });
            n.onclick = function () {
                n.close();
                window.focus();
                var href = '/web/support';
                if (data.latest_thread_id) href += '?thread=' + data.latest_thread_id;
                location.href = href;
            };
        } catch (e) {}
    }

    async function api(url, options) {
        var res = await fetch(url, options);
        if (res.status === 401) {
            window.location.href = loginUrl + '?next=' + encodeURIComponent(location.pathname);
            throw new Error('auth');
        }
        if (res.status === 413) {
            throw new Error(tooLargeMessage());
        }
        var data = {};
        try { data = await res.json(); } catch (e) {}
        if (!res.ok) {
            var detail = data.detail;
            if (detail && typeof detail === 'object') {
                throw new Error(detail.message + (detail.wait_text ? ' · подождите ' + detail.wait_text : ''));
            }
            throw new Error(typeof detail === 'string' ? detail : 'Ошибка');
        }
        return data;
    }

    async function readFileBuffer(file) {
        if (!file) return null;
        if (typeof file.arrayBuffer === 'function') {
            try {
                var buf = await file.arrayBuffer();
                if (buf && buf.byteLength) return buf;
            } catch (e) {}
        }
        if (typeof FileReader !== 'function') return null;
        return new Promise(function (resolve) {
            var reader = new FileReader();
            reader.onload = function () {
                resolve(reader.result && reader.result.byteLength ? reader.result : null);
            };
            reader.onerror = function () { resolve(null); };
            try {
                reader.readAsArrayBuffer(file);
            } catch (e) {
                resolve(null);
            }
        });
    }

    function arrayBufferToBase64(buf) {
        var bytes = new Uint8Array(buf);
        var chunk = 0x8000;
        var parts = [];
        for (var i = 0; i < bytes.length; i += chunk) {
            var slice = bytes.subarray(i, i + chunk);
            parts.push(String.fromCharCode.apply(null, Array.prototype.slice.call(slice)));
        }
        return btoa(parts.join(''));
    }

    async function sendForm(url, text, files, extra) {
        extra = extra || {};
        var payload = {
            text: text || '',
            source_path: extra.source_path || '',
            files: [],
        };
        var list = Array.prototype.slice.call(files || []);
        var total = 0;
        for (var i = 0; i < list.length; i++) {
            var file = list[i];
            if (file && file.size > MAX_FILE_BYTES) {
                throw new Error(tooLargeMessage());
            }
            var buf = await readFileBuffer(file);
            if (!buf || !buf.byteLength) continue;
            if (buf.byteLength > MAX_FILE_BYTES) {
                throw new Error(tooLargeMessage());
            }
            total += buf.byteLength;
            if (total > MAX_TOTAL_BYTES) {
                throw new Error('Суммарный размер вложений больше 30 МБ');
            }
            var name = uniqueUploadName(file, i);
            payload.files.push({
                name: name,
                original_name: file && file.name ? file.name : name,
                content_type: (file && file.type) || 'application/octet-stream',
                data: arrayBufferToBase64(buf),
            });
        }
        if (!String(payload.text || '').trim() && !payload.files.length) {
            throw new Error('Нужен текст или файл');
        }
        return api(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
    }

    var ALLOWED_EXT = {
        '.png': 1, '.jpg': 1, '.jpeg': 1, '.gif': 1, '.webp': 1, '.bmp': 1,
        '.pdf': 1, '.txt': 1, '.zip': 1, '.mat': 1, '.sgf': 1, '.csv': 1,
        '.doc': 1, '.docx': 1, '.xlsx': 1,
    };
    var MAX_ATTACH = 5;
    var MAX_FILE_BYTES = 15 * 1024 * 1024;
    var MAX_TOTAL_BYTES = 30 * 1024 * 1024;

    function tooLargeMessage() {
        return 'Файл слишком большой (макс. 15 МБ)';
    }

    function fileExt(name) {
        var lower = String(name || '').toLowerCase();
        var dot = lower.lastIndexOf('.');
        return dot >= 0 ? lower.slice(dot) : '';
    }

    function uniqueUploadName(file, index) {
        var raw = String((file && file.name) || 'file').split(/[/\\]/).pop() || 'file';
        var ext = fileExt(raw) || extFromMime(file && file.type);
        var base = ext && raw.toLowerCase().slice(-ext.length) === ext ? raw.slice(0, -ext.length) : raw;
        base = base.replace(/[^\w.\-()+ ]+/g, '_').slice(0, 80) || 'file';
        return base + '-' + index + '-' + Date.now() + ext;
    }

    function extFromMime(type) {
        var mime = String(type || '').toLowerCase();
        if (mime.indexOf('jpeg') >= 0) return '.jpg';
        if (mime.indexOf('png') >= 0) return '.png';
        if (mime.indexOf('gif') >= 0) return '.gif';
        if (mime.indexOf('webp') >= 0) return '.webp';
        if (mime.indexOf('bmp') >= 0) return '.bmp';
        if (mime.indexOf('pdf') >= 0) return '.pdf';
        return '';
    }

    function isAllowedFile(file) {
        if (!file) return false;
        if (ALLOWED_EXT[fileExt(file.name)]) return true;
        return String(file.type || '').indexOf('image/') === 0;
    }

    function normalizeFile(file) {
        if (!file) return null;
        if (file.name) return file;
        var type = file.type || 'image/png';
        var ext = '.png';
        if (type.indexOf('jpeg') >= 0) ext = '.jpg';
        else if (type.indexOf('gif') >= 0) ext = '.gif';
        else if (type.indexOf('webp') >= 0) ext = '.webp';
        else if (type.indexOf('bmp') >= 0) ext = '.bmp';
        return new File([file], 'screenshot-' + Date.now() + ext, { type: type });
    }

    function filesFromTransfer(dt) {
        if (!dt) return [];
        var out = [];
        function push(raw) {
            var file = normalizeFile(raw);
            if (!file || !isAllowedFile(file)) return;
            if (out.indexOf(file) !== -1) return;
            out.push(file);
        }
        if (dt.files && dt.files.length) {
            Array.prototype.forEach.call(dt.files, push);
        }
        if (!out.length && dt.items) {
            Array.prototype.forEach.call(dt.items, function (item) {
                if (item && item.kind === 'file') push(item.getAsFile());
            });
        }
        return out;
    }

    function transferHasFiles(e) {
        var types = e.dataTransfer && e.dataTransfer.types;
        if (!types) return false;
        if (typeof types.contains === 'function') return types.contains('Files');
        return Array.prototype.indexOf.call(types, 'Files') !== -1;
    }

    function bindDrop(root, onFiles) {
        if (!root) return;
        var depth = 0;
        root.addEventListener('dragenter', function (e) {
            if (!transferHasFiles(e)) return;
            e.preventDefault();
            depth += 1;
            root.classList.add('is-drop');
        });
        root.addEventListener('dragover', function (e) {
            if (!transferHasFiles(e)) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
        });
        root.addEventListener('dragleave', function () {
            depth -= 1;
            if (depth > 0) return;
            depth = 0;
            root.classList.remove('is-drop');
        });
        root.addEventListener('drop', function (e) {
            if (!transferHasFiles(e)) return;
            e.preventDefault();
            depth = 0;
            root.classList.remove('is-drop');
            onFiles(filesFromTransfer(e.dataTransfer));
        });
    }

    function bindComposer(opts) {
        var textEl = opts.textEl;
        var fileEl = opts.fileEl;
        var chipsEl = opts.chipsEl;
        var statusEl = opts.statusEl;
        var sendBtn = opts.sendBtn;
        var attachBtn = opts.attachBtn;
        var selected = [];

        function refreshChips() {
            if (!chipsEl) return;
            chipsEl.innerHTML = selected.map(function (file, i) {
                return '<span class="support-chip">' +
                    '<span class="support-chip-name">' + escapeHtml(file.name || 'файл') + '</span>' +
                    '<button type="button" class="support-chip-remove" data-index="' + i + '" aria-label="Убрать файл">×</button>' +
                    '</span>';
            }).join('');
        }

        function removeFile(idx) {
            if (idx < 0 || idx >= selected.length) return;
            selected.splice(idx, 1);
            refreshChips();
            if (statusEl) statusEl.textContent = '';
        }

        if (chipsEl && !chipsEl.getAttribute('data-chip-bound')) {
            chipsEl.setAttribute('data-chip-bound', '1');
            chipsEl.addEventListener('click', function (e) {
                var btn = e.target.closest('.support-chip-remove');
                if (!btn) return;
                e.preventDefault();
                e.stopPropagation();
                removeFile(Number(btn.getAttribute('data-index')));
            });
        }

        function addFiles(list) {
            var incoming = Array.prototype.slice.call(list || []);
            if (!incoming.length) return;
            var next = selected.slice();
            var tooLarge = false;
            incoming.forEach(function (raw) {
                if (next.length >= MAX_ATTACH) return;
                var file = normalizeFile(raw);
                if (!file || !file.size || !isAllowedFile(file)) return;
                if (file.size > MAX_FILE_BYTES) {
                    tooLarge = true;
                    return;
                }
                var dup = next.some(function (item) {
                    return item === file || item === raw ||
                        (item.name === file.name && item.size === file.size && item.lastModified === file.lastModified);
                });
                if (dup) return;
                next.push(file);
            });
            var added = next.length - selected.length;
            selected = next;
            if (fileEl) fileEl.value = '';
            refreshChips();
            if (!statusEl) return;
            if (tooLarge) {
                statusEl.textContent = tooLargeMessage();
            } else if (!added) {
                statusEl.textContent = selected.length >= MAX_ATTACH
                    ? 'Можно прикрепить не больше ' + MAX_ATTACH + ' файлов'
                    : 'Этот тип файла не поддерживается';
            } else {
                statusEl.textContent = '';
            }
        }

        if (attachBtn && fileEl) {
            attachBtn.addEventListener('click', function () { fileEl.click(); });
        }
        if (fileEl) {
            fileEl.addEventListener('change', function () {
                addFiles(fileEl.files);
            });
        }
        bindDrop(opts.dropRoot, addFiles);
        var pasteRoot = opts.dropRoot || textEl;
        if (pasteRoot) {
            pasteRoot.addEventListener('paste', function (e) {
                var files = filesFromTransfer(e.clipboardData);
                if (!files.length) return;
                e.preventDefault();
                addFiles(files);
            });
        }

        var sending = false;
        async function submit() {
            if (sending) return;
            var text = (textEl && textEl.value || '').trim();
            if (!text && !selected.length) return;
            var url = typeof opts.url === 'function' ? opts.url() : opts.url;
            if (!url) {
                if (statusEl) statusEl.textContent = 'Выберите диалог';
                return;
            }
            sending = true;
            if (sendBtn) sendBtn.disabled = true;
            if (statusEl) statusEl.textContent = '';
            var pending = selected.slice();
            try {
                var data = await sendForm(url, text, pending, opts.extra && opts.extra());
                if (textEl) textEl.value = '';
                selected = [];
                if (fileEl) fileEl.value = '';
                refreshChips();
                if (opts.onSent) opts.onSent(data.message);
            } catch (e) {
                if (statusEl) statusEl.textContent = e.message || 'Не удалось отправить';
            }
            sending = false;
            if (sendBtn) sendBtn.disabled = false;
        }

        if (sendBtn) sendBtn.addEventListener('click', submit);
        if (textEl) {
            textEl.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    submit();
                }
            });
        }
        return { submit: submit, addFiles: addFiles };
    }

    async function pollUnread() {
        try {
            var data = await api('/web/support/api/unread');
            bindNotifyGesture();
            if (data && data.admin) {
                notifyAdminNewMessage(data);
            } else if (data) {
                notifyUserNewMessage(data);
            }
            document.querySelectorAll('[data-support-nav-badge]').forEach(function (el) {
                setBadge(el, data.admin ? data.unread : 0);
            });
            setUserUnread(data && data.admin ? 0 : (data && data.unread) || 0);
            return data;
        } catch (e) {
            return null;
        }
    }

    function initWidget() {
        var panel = $('#supportPanel');
        var fab = $('#supportFab');
        if (!panel || !fab) return;
        if (panel.getAttribute('data-support-inited')) return;
        panel.setAttribute('data-support-inited', '1');
        var box = $('#supportMessages', panel);
        var closeBtn = $('#supportPanelClose', panel);
        var open = false;
        var loaded = false;

        function setOpen(next) {
            open = next;
            panel.hidden = !open;
            fab.setAttribute('aria-expanded', open ? 'true' : 'false');
            if (open && box) box.scrollTop = box.scrollHeight;
        }

        fab.addEventListener('click', function () {
            setOpen(panel.hidden);
            if (open) pollThread(true);
        });
        if (closeBtn) closeBtn.addEventListener('click', function () { setOpen(false); });

        var composer = bindComposer({
            textEl: $('#supportText', panel),
            fileEl: $('#supportFiles', panel),
            chipsEl: $('#supportChips', panel),
            statusEl: $('#supportStatus', panel),
            sendBtn: $('#supportSend', panel),
            attachBtn: $('#supportAttach', panel),
            dropRoot: panel,
            url: '/web/support/api/thread/messages',
            extra: function () {
                return { source_path: location.pathname || '' };
            },
            onSent: function (message) {
                if (!box) return;
                appendMessages(box, [message], 'user');
                loaded = true;
                setUserUnread(0);
            },
        });

        window.WebSupportWidget = {
            open: function () {
                setOpen(true);
                pollThread(true);
                var textEl = $('#supportText', panel);
                if (textEl) {
                    setTimeout(function () { textEl.focus(); }, 0);
                }
            },
            attachFiles: function (files) {
                if (composer && composer.addFiles) composer.addFiles(files);
            },
            appendMessage: function (message) {
                if (!box || !message) return;
                appendMessages(box, [message], 'user');
                loaded = true;
                setUserUnread(0);
            },
        };

        var pollBusy = false;
        async function pollThread(force) {
            if (!box || (!open && !force)) return;
            if (pollBusy) return;
            pollBusy = true;
            try {
                var after = loaded ? lastId(box) : 0;
                var data = await api('/web/support/api/thread?after_id=' + after + '&mark=1');
                var messages = data.messages || [];
                if (!loaded) {
                    box.innerHTML = messages.length
                        ? ''
                        : '<div class="support-empty">Напишите сообщение — ответит администратор.</div>';
                    loaded = true;
                }
                if (messages.length) appendMessages(box, messages, 'user');
                setUserUnread(0);
            } catch (e) {}
            pollBusy = false;
        }

        pollThread(false);
        setInterval(function () { pollThread(false); }, 4000);
    }

    function initInbox() {
        var root = $('#supportInbox');
        if (!root) return;
        if (root.getAttribute('data-support-inited')) return;
        root.setAttribute('data-support-inited', '1');
        var listEl = $('#supportThreadList');
        var chatEl = $('#supportInboxChat');
        var searchEl = $('#supportInboxSearch');
        var titleEl = $('#supportInboxTitle');
        var box = $('#supportInboxMessages');
        var backBtn = $('#supportInboxBack');
        var deleteBtn = $('#supportInboxDelete');
        var deleteModal = $('#supportDeleteModal');
        var deleteText = $('#supportDeleteText');
        var deleteCancel = $('#supportDeleteCancel');
        var deleteConfirm = $('#supportDeleteConfirm');
        var currentId = 0;
        var currentLogin = '';
        var loaded = false;
        var page = 1;
        var pendingDeleteId = 0;
        var deleting = false;

        function setDeleteBtn(show) {
            if (!deleteBtn) return;
            deleteBtn.hidden = !show;
        }

        function closeDeleteModal() {
            pendingDeleteId = 0;
            if (deleteModal) deleteModal.hidden = true;
            if (deleteConfirm) deleteConfirm.disabled = false;
        }

        function askDeleteThread(id, login) {
            pendingDeleteId = Number(id || 0);
            if (!pendingDeleteId || !deleteModal) return;
            if (deleteText) {
                deleteText.textContent = login
                    ? ('Диалог с «' + login + '» будет удалён без возможности восстановления.')
                    : 'Диалог будет удалён без возможности восстановления.';
            }
            deleteModal.hidden = false;
            if (deleteConfirm) deleteConfirm.focus();
        }

        function openThread(id, login) {
            currentId = Number(id || 0);
            currentLogin = login || '';
            loaded = false;
            root.classList.toggle('is-chat', !!currentId);
            if (titleEl) titleEl.textContent = currentLogin ? ('Диалог · ' + currentLogin) : (currentId ? 'Диалог' : 'Выберите обращение');
            setDeleteBtn(!!currentId);
            if (box) box.innerHTML = currentId ? '<div class="support-empty">Загрузка…</div>' : '<div class="support-inbox-placeholder">Слева список обращений пользователей.</div>';
            document.querySelectorAll('.support-thread-item').forEach(function (btn) {
                btn.classList.toggle('is-active', Number(btn.getAttribute('data-id')) === currentId);
            });
            if (currentId) pollThread(true);
        }

        async function loadList() {
            var q = searchEl ? searchEl.value.trim() : '';
            try {
                var data = await api('/web/support/api/inbox?page=' + page + '&q=' + encodeURIComponent(q));
                setBadge($('[data-support-nav-badge]'), data.unread);
                if (!listEl) return;
                if (!(data.items || []).length) {
                    listEl.innerHTML = '<div class="support-empty">Пока нет обращений.</div>';
                    return;
                }
                listEl.innerHTML = data.items.map(function (item) {
                    return '<div class="support-thread-item' +
                        (item.unread ? ' is-unread' : '') +
                        (item.id === currentId ? ' is-active' : '') +
                        '" data-id="' + item.id + '" data-login="' + escapeHtml(item.login) + '">' +
                        '<button type="button" class="support-thread-main">' +
                        '<span class="support-thread-login">' + escapeHtml(item.login || 'Пользователь') + '</span>' +
                        '<span class="support-thread-preview">' + escapeHtml(item.last_preview || '') + '</span>' +
                        '</button>' +
                        '<button type="button" class="support-thread-delete" data-delete-thread="' + item.id +
                        '" data-login="' + escapeHtml(item.login) + '" aria-label="Удалить чат" title="Удалить чат">×</button>' +
                        '</div>';
                }).join('');
            } catch (e) {
                if (listEl) listEl.innerHTML = '<div class="support-empty">Не удалось загрузить список.</div>';
            }
        }

        var pollBusy = false;
        async function pollThread(force) {
            if (!currentId || !box) return;
            if (!force && document.hidden) return;
            if (pollBusy) return;
            pollBusy = true;
            try {
                var after = loaded ? lastId(box) : 0;
                var data = await api('/web/support/api/threads/' + currentId + '?after_id=' + after + '&mark=1');
                var messages = data.messages || [];
                if (!loaded) {
                    box.innerHTML = messages.length ? '' : '<div class="support-empty">Сообщений пока нет.</div>';
                    loaded = true;
                }
                if (messages.length) appendMessages(box, messages, 'admin');
            } catch (e) {}
            pollBusy = false;
        }

        if (listEl) {
            listEl.addEventListener('click', function (e) {
                var del = e.target.closest('[data-delete-thread]');
                if (del) {
                    e.preventDefault();
                    e.stopPropagation();
                    askDeleteThread(del.getAttribute('data-delete-thread'), del.getAttribute('data-login'));
                    return;
                }
                var item = e.target.closest('.support-thread-item');
                if (!item) return;
                openThread(item.getAttribute('data-id'), item.getAttribute('data-login'));
            });
        }
        if (backBtn) {
            backBtn.addEventListener('click', function () {
                openThread(0, '');
            });
        }
        if (deleteBtn) {
            deleteBtn.addEventListener('click', function () {
                if (!currentId) return;
                askDeleteThread(currentId, currentLogin);
            });
        }
        if (deleteCancel) deleteCancel.addEventListener('click', closeDeleteModal);
        var deleteOverlay = $('#supportDeleteOverlay');
        if (deleteOverlay) deleteOverlay.addEventListener('click', closeDeleteModal);
        document.addEventListener('keydown', function (e) {
            if (e.key !== 'Escape' || !deleteModal || deleteModal.hidden) return;
            closeDeleteModal();
        });
        if (deleteConfirm) {
            deleteConfirm.addEventListener('click', function () {
                if (!pendingDeleteId || deleting) return;
                deleting = true;
                deleteConfirm.disabled = true;
                var statusEl = $('#supportInboxStatus');
                api('/web/support/api/threads/' + pendingDeleteId, { method: 'DELETE' }).then(function () {
                    var removedId = pendingDeleteId;
                    closeDeleteModal();
                    if (Number(currentId) === Number(removedId)) {
                        openThread(0, '');
                    }
                    loadList();
                }).catch(function (err) {
                    if (statusEl) statusEl.textContent = (err && err.message) || 'Не удалось удалить чат';
                    if (deleteConfirm) deleteConfirm.disabled = false;
                }).then(function () {
                    deleting = false;
                });
            });
        }
        var searchTimer = 0;
        if (searchEl) {
            searchEl.addEventListener('input', function () {
                clearTimeout(searchTimer);
                searchTimer = setTimeout(loadList, 250);
            });
        }

        bindComposer({
            textEl: $('#supportInboxText'),
            fileEl: $('#supportInboxFiles'),
            chipsEl: $('#supportInboxChips'),
            statusEl: $('#supportInboxStatus'),
            sendBtn: $('#supportInboxSend'),
            attachBtn: $('#supportInboxAttach'),
            url: function () {
                return currentId ? ('/web/support/api/threads/' + currentId + '/messages') : '';
            },
            onSent: function (message) {
                if (!box || !currentId) return;
                appendMessages(box, [message], 'admin');
                loadList();
            },
        });

        var sendingHints = false;
        if (box) {
            box.addEventListener('click', function (e) {
                var btn = e.target.closest('[data-send-to-hints]');
                if (!btn || !currentId) return;
                e.preventDefault();
                if (sendingHints || btn.disabled) return;
                var messageId = btn.getAttribute('data-send-to-hints');
                if (!messageId) return;
                sendingHints = true;
                btn.disabled = true;
                var statusEl = $('#supportInboxStatus');
                if (statusEl) statusEl.textContent = '';
                api('/web/support/api/threads/' + currentId + '/messages/' + messageId + '/send-to-hints', {
                    method: 'POST',
                }).then(function (data) {
                    window.location.href = (data && data.redirect) || '/web/hints';
                }).catch(function (err) {
                    sendingHints = false;
                    btn.disabled = false;
                    if (statusEl) statusEl.textContent = (err && err.message) || 'Не удалось отправить в Ошибки';
                });
            });
        }

        var params = new URLSearchParams(location.search);
        var initial = Number(params.get('thread') || 0);
        loadList().then(function () {
            if (initial) {
                var btn = listEl && listEl.querySelector('.support-thread-item[data-id="' + initial + '"]');
                openThread(initial, btn ? btn.getAttribute('data-login') : '');
            }
        });
        setInterval(loadList, 8000);
        setInterval(function () { pollThread(false); }, 4000);
    }

    document.addEventListener('click', function (e) {
        if (!e.target.closest('[data-support-nav]')) return;
        if (!isTopWindow()) return;
        if (!window.Notification || Notification.permission !== 'default') return;
        Notification.requestPermission().catch(function () {});
    });

    pollUnread();
    setInterval(pollUnread, 8000);
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            initWidget();
            initInbox();
        });
    } else {
        initWidget();
        initInbox();
    }
})();
