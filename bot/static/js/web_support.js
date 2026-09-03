(function () {
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
        return '<div class="support-msg ' + (mine ? 'is-mine' : 'is-admin') + '" data-id="' + msg.id + '">' +
            '<div class="support-msg-meta">' + meta + '</div>' +
            body +
            (files ? '<div class="support-files">' + files + '</div>' : '') +
            '</div>';
    }

    function appendMessages(box, messages, mineRole) {
        var html = messages.map(function (msg) { return renderMessage(msg, mineRole); }).join('');
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
        var isDot = el.hasAttribute('data-support-nav-badge');
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
    var notifyGestureBound = false;

    function isTopWindow() {
        try { return window === window.top; } catch (e) { return false; }
    }

    function onSupportPage() {
        return (location.pathname.replace(/\/$/, '') || '/') === '/web/support';
    }

    function bindAdminNotifyGesture() {
        if (notifyGestureBound || !isTopWindow()) return;
        notifyGestureBound = true;
        function ask() {
            document.removeEventListener('pointerdown', ask, true);
            if (!window.Notification || Notification.permission !== 'default') return;
            Notification.requestPermission().catch(function () {});
        }
        document.addEventListener('pointerdown', ask, true);
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

    async function sendForm(url, text, files, extra) {
        var form = new FormData();
        form.append('text', text || '');
        Object.keys(extra || {}).forEach(function (key) {
            form.append(key, extra[key]);
        });
        Array.prototype.forEach.call(files || [], function (file) {
            form.append('files', file);
        });
        return api(url, { method: 'POST', body: form });
    }

    var ALLOWED_EXT = {
        '.png': 1, '.jpg': 1, '.jpeg': 1, '.gif': 1, '.webp': 1, '.bmp': 1,
        '.pdf': 1, '.txt': 1, '.zip': 1, '.mat': 1, '.sgf': 1, '.csv': 1,
        '.doc': 1, '.docx': 1, '.xlsx': 1,
    };
    var MAX_ATTACH = 5;

    function fileExt(name) {
        var lower = String(name || '').toLowerCase();
        var dot = lower.lastIndexOf('.');
        return dot >= 0 ? lower.slice(dot) : '';
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
        var seen = {};
        function push(raw) {
            var file = normalizeFile(raw);
            if (!file || !isAllowedFile(file)) return;
            var key = file.name + ':' + file.size + ':' + (file.lastModified || 0);
            if (seen[key]) return;
            seen[key] = 1;
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
            chipsEl.innerHTML = selected.map(function (file) {
                return '<span class="support-chip">' + escapeHtml(file.name) + '</span>';
            }).join('');
        }

        function addFiles(list) {
            var incoming = Array.prototype.slice.call(list || []);
            if (!incoming.length) return;
            var next = selected.slice();
            incoming.forEach(function (raw) {
                if (next.length >= MAX_ATTACH) return;
                var file = normalizeFile(raw);
                if (!file || !isAllowedFile(file)) return;
                var dup = next.some(function (item) {
                    return item.name === file.name
                        && item.size === file.size
                        && item.lastModified === file.lastModified;
                });
                if (dup) return;
                next.push(file);
            });
            var added = next.length - selected.length;
            selected = next;
            if (fileEl) fileEl.value = '';
            refreshChips();
            if (!statusEl) return;
            if (!added) {
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

        async function submit() {
            var text = (textEl && textEl.value || '').trim();
            if (!text && !selected.length) return;
            var url = typeof opts.url === 'function' ? opts.url() : opts.url;
            if (!url) {
                if (statusEl) statusEl.textContent = 'Выберите диалог';
                return;
            }
            sendBtn.disabled = true;
            if (statusEl) statusEl.textContent = '';
            try {
                var data = await sendForm(url, text, selected, opts.extra && opts.extra());
                if (textEl) textEl.value = '';
                selected = [];
                if (fileEl) fileEl.value = '';
                refreshChips();
                if (opts.onSent) opts.onSent(data.message);
            } catch (e) {
                if (statusEl) statusEl.textContent = e.message || 'Не удалось отправить';
            }
            sendBtn.disabled = false;
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
        return { submit: submit };
    }

    async function pollUnread() {
        try {
            var data = await api('/web/support/api/unread');
            if (data && data.admin) {
                bindAdminNotifyGesture();
                notifyAdminNewMessage(data);
            }
            document.querySelectorAll('[data-support-nav-badge]').forEach(function (el) {
                setBadge(el, data.admin ? data.unread : 0);
            });
            document.querySelectorAll('[data-support-fab-badge]').forEach(function (el) {
                setBadge(el, data.admin ? 0 : data.unread);
            });
            return data;
        } catch (e) {
            return null;
        }
    }

    function initWidget() {
        var panel = $('#supportPanel');
        var fab = $('#supportFab');
        if (!panel || !fab) return;
        var box = $('#supportMessages');
        var closeBtn = $('#supportPanelClose');
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

        bindComposer({
            textEl: $('#supportText'),
            fileEl: $('#supportFiles'),
            chipsEl: $('#supportChips'),
            statusEl: $('#supportStatus'),
            sendBtn: $('#supportSend'),
            attachBtn: $('#supportAttach'),
            dropRoot: panel,
            url: '/web/support/api/thread/messages',
            extra: function () {
                return { source_path: location.pathname || '' };
            },
            onSent: function (message) {
                if (!box) return;
                appendMessages(box, [message], 'user');
                loaded = true;
                setBadge($('[data-support-fab-badge]'), 0);
            },
        });

        async function pollThread(force) {
            if (!box || (!open && !force)) return;
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
                setBadge($('[data-support-fab-badge]'), 0);
            } catch (e) {}
        }

        pollThread(false);
        setInterval(function () { pollThread(false); }, 4000);
    }

    function initInbox() {
        var root = $('#supportInbox');
        if (!root) return;
        var listEl = $('#supportThreadList');
        var chatEl = $('#supportInboxChat');
        var searchEl = $('#supportInboxSearch');
        var titleEl = $('#supportInboxTitle');
        var box = $('#supportInboxMessages');
        var backBtn = $('#supportInboxBack');
        var currentId = 0;
        var loaded = false;
        var page = 1;

        function openThread(id, login) {
            currentId = Number(id || 0);
            loaded = false;
            root.classList.toggle('is-chat', !!currentId);
            if (titleEl) titleEl.textContent = login ? ('Диалог · ' + login) : 'Диалог';
            if (box) box.innerHTML = '<div class="support-empty">Загрузка…</div>';
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
                    return '<button type="button" class="support-thread-item' +
                        (item.unread ? ' is-unread' : '') +
                        (item.id === currentId ? ' is-active' : '') +
                        '" data-id="' + item.id + '" data-login="' + escapeHtml(item.login) + '">' +
                        '<span class="support-thread-login">' + escapeHtml(item.login || 'Пользователь') + '</span>' +
                        '<span class="support-thread-preview">' + escapeHtml(item.last_preview || '') + '</span>' +
                        '</button>';
                }).join('');
            } catch (e) {
                if (listEl) listEl.innerHTML = '<div class="support-empty">Не удалось загрузить список.</div>';
            }
        }

        async function pollThread(force) {
            if (!currentId || !box) return;
            if (!force && document.hidden) return;
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
        }

        if (listEl) {
            listEl.addEventListener('click', function (e) {
                var btn = e.target.closest('.support-thread-item');
                if (!btn) return;
                openThread(btn.getAttribute('data-id'), btn.getAttribute('data-login'));
            });
        }
        if (backBtn) {
            backBtn.addEventListener('click', function () {
                currentId = 0;
                root.classList.remove('is-chat');
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
