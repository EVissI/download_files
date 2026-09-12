(function () {
    var KEY = 'web_theme';

    function current() {
        return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
    }

    function syncButtons() {
        var light = current() === 'light';
        document.querySelectorAll('[data-web-theme-toggle]').forEach(function (btn) {
            btn.setAttribute('aria-pressed', light ? 'true' : 'false');
            var label = light ? 'Тёмная тема' : 'Светлая тема';
            btn.title = label;
            btn.setAttribute('aria-label', label);
        });
    }

    function apply(theme) {
        if (theme === 'light') {
            document.documentElement.setAttribute('data-theme', 'light');
        } else {
            document.documentElement.removeAttribute('data-theme');
        }
        try {
            localStorage.setItem(KEY, theme);
        } catch (e) {}
        syncButtons();
        document.querySelectorAll('iframe.web-fs-frame, iframe.web-page-overlay__frame').forEach(function (f) {
            try {
                if (f.contentWindow) {
                    f.contentWindow.postMessage({ type: 'web-theme', theme: theme }, location.origin);
                }
            } catch (err) {}
        });
    }

    document.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-web-theme-toggle]');
        if (!btn) return;
        e.preventDefault();
        apply(current() === 'light' ? 'dark' : 'light');
    });

    window.addEventListener('storage', function (e) {
        if (e.key !== KEY) return;
        apply(e.newValue === 'light' ? 'light' : 'dark');
    });

    window.addEventListener('message', function (e) {
        if (e.origin !== location.origin) return;
        if (!e.data || e.data.type !== 'web-theme') return;
        apply(e.data.theme === 'light' ? 'light' : 'dark');
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', syncButtons);
    } else {
        syncButtons();
    }
})();

(function () {
    if (window !== window.top) return;

    var WANT_KEY = 'web_want_fullscreen';
    var leavingPage = false;
    var frame = null;

    function fullscreenElement() {
        return document.fullscreenElement
            || document.webkitFullscreenElement
            || document.mozFullScreenElement
            || document.msFullscreenElement
            || null;
    }

    function fullscreenSupported() {
        var el = document.documentElement;
        if (document.fullscreenEnabled === false
            || document.webkitFullscreenEnabled === false
            || document.mozFullScreenEnabled === false
            || document.msFullscreenEnabled === false) {
            return false;
        }
        return !!(el.requestFullscreen
            || el.webkitRequestFullscreen
            || el.mozRequestFullScreen
            || el.msRequestFullscreen);
    }

    function getWant() {
        try {
            return sessionStorage.getItem(WANT_KEY) === '1';
        } catch (e) {
            return false;
        }
    }

    function setWant(on) {
        try {
            if (on) sessionStorage.setItem(WANT_KEY, '1');
            else sessionStorage.removeItem(WANT_KEY);
        } catch (e) {}
    }

    function markLeaving() {
        leavingPage = true;
    }

    function requestFullscreen(element) {
        if (element.requestFullscreen) {
            try {
                return element.requestFullscreen({ navigationUI: 'hide' });
            } catch (err) {
                return element.requestFullscreen();
            }
        }
        if (element.webkitRequestFullscreen) return element.webkitRequestFullscreen();
        if (element.mozRequestFullScreen) return element.mozRequestFullScreen();
        if (element.msRequestFullscreen) return element.msRequestFullscreen();
        return Promise.reject(new Error('Fullscreen API is not supported'));
    }

    function exitFullscreen() {
        if (document.exitFullscreen) return document.exitFullscreen();
        if (document.webkitExitFullscreen) return document.webkitExitFullscreen();
        if (document.mozCancelFullScreen) return document.mozCancelFullScreen();
        if (document.msExitFullscreen) return document.msExitFullscreen();
        return Promise.reject(new Error('Fullscreen API is not supported'));
    }

    function headerEl() {
        return document.querySelector('.web-cabinet-header');
    }

    function layoutFrame() {
        if (!frame) return;
        var header = headerEl();
        var top = header ? Math.ceil(header.getBoundingClientRect().height) : 0;
        frame.style.top = top + 'px';
        frame.style.height = 'calc(100dvh - ' + top + 'px)';
    }

    function canonicalNavPath(pathname, search) {
        var cur = String(pathname || '').replace(/\/$/, '') || '/';
        if (cur === '/content-card-view') {
            try {
                var pool = new URLSearchParams(search || '').get('pool');
                if (pool === 'pip_count') return '/web/pip-count';
            } catch (e) {}
            return '/web/cards';
        }
        if (cur === '/match-analysis-view') return '/web/match-analysis';
        if (cur === '/web/hints/view') return '/web/hints';
        if (cur === '/web/board/view') return '/web/board';
        return cur;
    }

    function syncNav(pathname, search) {
        var cur = canonicalNavPath(pathname, search);
        document.querySelectorAll('.web-cabinet-header .service-nav a[href]').forEach(function (a) {
            var path = '';
            try {
                path = new URL(a.href, location.href).pathname.replace(/\/$/, '') || '/';
            } catch (err) {
                return;
            }
            a.classList.toggle('active', cur === path || cur.indexOf(path + '/') === 0);
        });
        var active = document.querySelector('.web-cabinet-header .service-nav a.active');
        if (active && active.scrollIntoView) {
            active.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' });
        }
    }

    function currentFrameHref() {
        try {
            if (frame && frame.contentWindow && frame.contentWindow.location) {
                return frame.contentWindow.location.href;
            }
        } catch (e) {}
        return location.href;
    }

    function onFrameLoad() {
        var doc = null;
        try {
            doc = frame.contentDocument;
        } catch (e) {
            return;
        }
        if (!doc) return;
        var embeddedHeader = doc.querySelector('.web-cabinet-header');
        if (embeddedHeader) embeddedHeader.style.display = 'none';
        try {
            var loc = frame.contentWindow.location;
            if (loc.origin === location.origin) {
                history.replaceState({ webFsShell: true }, '', loc.pathname + loc.search + loc.hash);
                syncNav(loc.pathname, loc.search);
            }
        } catch (e) {}
        layoutFrame();
    }

    function ensureFrame() {
        if (frame) return frame;
        frame = document.createElement('iframe');
        frame.className = 'web-fs-frame';
        frame.title = 'Сервис';
        frame.addEventListener('load', onFrameLoad);
        document.body.appendChild(frame);
        document.body.classList.add('web-fs-shell');
        window.addEventListener('resize', layoutFrame);
        if (window.ResizeObserver && headerEl()) {
            var observer = new ResizeObserver(layoutFrame);
            observer.observe(headerEl());
        }
        layoutFrame();
        return frame;
    }

    function openInShell(href) {
        var url;
        try {
            url = new URL(href, location.href);
        } catch (e) {
            location.href = href;
            return;
        }
        if (url.origin !== location.origin) {
            markLeaving();
            location.href = url.href;
            return;
        }
        ensureFrame();
        frame.src = url.pathname + url.search + url.hash;
    }

    function flattenShell() {
        if (!frame) return;
        markLeaving();
        location.replace(currentFrameHref());
    }

    function pathOf(href, fallbackPath) {
        try {
            return new URL(href, location.href).pathname.replace(/\/$/, '') || '/';
        } catch (e) {
            return fallbackPath || '/';
        }
    }

    function syncButtons() {
        var on = !!fullscreenElement();
        document.documentElement.classList.toggle('web-is-fullscreen', on);
        document.querySelectorAll('[data-web-fullscreen-toggle]').forEach(function (btn) {
            btn.hidden = !fullscreenSupported();
            btn.classList.toggle('is-unavailable', !fullscreenSupported());
            btn.setAttribute('aria-pressed', on ? 'true' : 'false');
            var label = on ? 'Обычный режим' : 'На весь экран';
            btn.title = label;
            btn.setAttribute('aria-label', label);
        });
    }

    function tryRestore() {
        if (!getWant() || !fullscreenSupported() || fullscreenElement()) return;
        Promise.resolve(requestFullscreen(document.documentElement)).catch(function () {});
    }

    function samePage(hrefA, hrefB) {
        try {
            var a = new URL(hrefA, location.href);
            var b = new URL(hrefB, location.href);
            return a.pathname === b.pathname && a.search === b.search && a.hash === b.hash;
        } catch (e) {
            return pathOf(hrefA) === pathOf(hrefB);
        }
    }

    function goToService(href) {
        if (!href) return;
        if (fullscreenElement() || frame) {
            var nowHref = frame ? currentFrameHref() : location.href;
            if (samePage(href, nowHref)) return;
            openInShell(href);
            return;
        }
        var here = location.href;
        if (samePage(href, here)) return;
        markLeaving();
        location.href = href;
    }

    function toggleFullscreen() {
        if (fullscreenElement()) {
            setWant(false);
            if (frame) {
                flattenShell();
                return;
            }
            Promise.resolve(exitFullscreen()).catch(function () {});
            return;
        }
        setWant(true);
        Promise.resolve(requestFullscreen(document.documentElement)).catch(function () {});
    }

    function broadcastFullscreenState() {
        var on = !!fullscreenElement();
        var payload = { type: 'web-fullscreen-state', on: on };
        document.querySelectorAll('iframe.web-page-overlay__frame, iframe.web-fs-frame').forEach(function (ifr) {
            try {
                if (ifr.contentWindow) {
                    ifr.contentWindow.postMessage(payload, location.origin);
                }
            } catch (e) {}
        });
    }

    window.addEventListener('web-go-service', function (e) {
        goToService(e.detail && e.detail.href);
    });
    window.addEventListener('message', function (e) {
        if (e.origin !== location.origin) return;
        if (!e.data) return;
        if (e.data.type === 'web-toggle-fullscreen') {
            toggleFullscreen();
            return;
        }
        if (e.data.type !== 'web-service-nav') return;
        goToService(e.data.href);
    });
    window.addEventListener('pagehide', markLeaving);
    window.addEventListener('beforeunload', markLeaving);

    document.addEventListener('click', function (e) {
        var link = e.target.closest('.service-nav a[href]');
        if (!link) return;
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;
        if (link.target && link.target !== '_self') return;
        if (!fullscreenElement() && !frame) return;
        e.preventDefault();
        goToService(link.href);
    }, true);

    document.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-web-fullscreen-toggle]');
        if (!btn) return;
        e.preventDefault();
        toggleFullscreen();
    });

    function onFsChange() {
        syncButtons();
        broadcastFullscreenState();
        if (fullscreenElement()) {
            setWant(true);
            return;
        }
        setTimeout(function () {
            if (leavingPage) return;
            setWant(false);
            if (frame) flattenShell();
        }, 0);
    }

    ['fullscreenchange', 'webkitfullscreenchange', 'mozfullscreenchange', 'MSFullscreenChange']
        .forEach(function (evt) {
            document.addEventListener(evt, onFsChange);
        });

    function onGesture(e) {
        if (!getWant() || fullscreenElement()) return;
        if (e.target && e.target.closest && e.target.closest('[data-web-fullscreen-toggle]')) return;
        tryRestore();
    }

    document.addEventListener('pointerdown', onGesture, true);
    document.addEventListener('keydown', onGesture, true);
    window.addEventListener('pageshow', tryRestore);

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            syncButtons();
            tryRestore();
        });
    } else {
        syncButtons();
        tryRestore();
    }
})();

(function () {
    var MIN_DX = 72;
    var MAX_OFF_AXIS = 0.6;
    var MAX_MS = 700;
    var startX = 0;
    var startY = 0;
    var startT = 0;
    var tracking = false;

    function isMobile() {
        try {
            return window.matchMedia('(max-width: 760px), (hover: none) and (pointer: coarse)').matches;
        } catch (e) {
            return window.innerWidth <= 760;
        }
    }

    function serviceLinks() {
        var nav = document.querySelector('.service-nav');
        if (!nav) return [];
        return Array.prototype.slice.call(nav.querySelectorAll('a[href]'));
    }

    function currentIndex(links) {
        var path = (location.pathname || '/').replace(/\/$/, '') || '/';
        if (path === '/content-card-view') {
            try {
                var pool = new URLSearchParams(location.search || '').get('pool');
                path = pool === 'pip_count' ? '/web/pip-count' : '/web/cards';
            } catch (e) {
                path = '/web/cards';
            }
        } else if (path === '/match-analysis-view') {
            path = '/web/match-analysis';
        } else if (path === '/web/hints/view') {
            path = '/web/hints';
        } else if (path === '/web/board/view') {
            path = '/web/board';
        }
        var best = -1;
        var bestLen = -1;
        links.forEach(function (a, i) {
            var p = '';
            try {
                p = new URL(a.href, location.href).pathname.replace(/\/$/, '') || '/';
            } catch (err) {
                return;
            }
            if (path === p || path.indexOf(p + '/') === 0) {
                if (p.length > bestLen) {
                    bestLen = p.length;
                    best = i;
                }
            }
        });
        return best;
    }

    function isHScrollable(node) {
        if (!node || node === document.body || node === document.documentElement) return false;
        if (node.scrollWidth <= node.clientWidth + 8) return false;
        try {
            var ox = window.getComputedStyle(node).overflowX;
            return ox === 'auto' || ox === 'scroll';
        } catch (e) {
            return false;
        }
    }

    function ignoreTarget(el) {
        if (!el || !el.closest) return true;
        if (el.closest('canvas, input, textarea, select, option, [contenteditable="true"]')) return true;
        if (el.closest('.web-cabinet-header, .service-nav, .header-actions')) return true;
        if (el.closest('.history-table-wrap, .analyze-table, .ma-audio-modal, .card-preview-modal, .link-modal, .hw-assign-modal, .hw-link-modal, .shuffle-modal, .web-page-overlay')) return true;
        var node = el;
        while (node && node !== document.body) {
            if (isHScrollable(node)) return true;
            node = node.parentElement;
        }
        return false;
    }

    function goKeepFullscreen(href) {
        if (!href) return;
        if (window !== window.top) {
            window.top.postMessage({ type: 'web-service-nav', href: href }, location.origin);
            return;
        }
        window.dispatchEvent(new CustomEvent('web-go-service', { detail: { href: href } }));
    }

    window.webNavigateKeepFullscreen = goKeepFullscreen;

    function navigate(href) {
        try {
            if (navigator.vibrate) navigator.vibrate(8);
        } catch (e) {}
        goKeepFullscreen(href);
    }

    function point(e) {
        if (e.changedTouches && e.changedTouches[0]) return e.changedTouches[0];
        if (e.touches && e.touches[0]) return e.touches[0];
        return e;
    }

    function onStart(e) {
        if (!isMobile()) return;
        if (e.touches && e.touches.length !== 1) {
            tracking = false;
            return;
        }
        if (ignoreTarget(e.target)) {
            tracking = false;
            return;
        }
        var t = point(e);
        startX = t.clientX;
        startY = t.clientY;
        startT = Date.now();
        tracking = true;
    }

    function onMove(e) {
        if (!tracking) return;
        if (e.touches && e.touches.length !== 1) {
            tracking = false;
            return;
        }
        var t = point(e);
        var dx = t.clientX - startX;
        var dy = t.clientY - startY;
        if (Math.abs(dy) > 28 && Math.abs(dy) > Math.abs(dx)) tracking = false;
    }

    function onEnd(e) {
        if (!tracking) return;
        tracking = false;
        if (!isMobile()) return;
        var t = point(e);
        var dx = t.clientX - startX;
        var dy = t.clientY - startY;
        if (Math.abs(dx) < MIN_DX) return;
        if (Math.abs(dy) > Math.abs(dx) * MAX_OFF_AXIS) return;
        if (Date.now() - startT > MAX_MS) return;
        var links = serviceLinks();
        if (links.length < 2) return;
        var i = currentIndex(links);
        if (i < 0) return;
        var next = dx < 0
            ? (i + 1) % links.length
            : (i - 1 + links.length) % links.length;
        navigate(links[next].href);
    }

    document.addEventListener('touchstart', onStart, { passive: true, capture: true });
    document.addEventListener('touchmove', onMove, { passive: true, capture: true });
    document.addEventListener('touchend', onEnd, { passive: true, capture: true });
    document.addEventListener('touchcancel', function () { tracking = false; }, { passive: true });
})();

(function () {
    var OVERLAY_ID = 'web-page-overlay';
    var MSG_CLOSE = 'web-cabinet-overlay-close';
    var bound = false;

    function isEmbed() {
        try {
            return new URLSearchParams(location.search).get('embed') === '1' && window !== window.parent;
        } catch (e) {
            return false;
        }
    }

    function isOverlayViewPath(pathname) {
        var p = String(pathname || '').replace(/\/$/, '') || '/';
        return p === '/web/hints/view'
            || p === '/web/board/view'
            || p === '/content-card-view'
            || p === '/match-analysis-view';
    }

    function closeEmbed() {
        if (!isEmbed()) return false;
        try {
            window.parent.postMessage({ type: MSG_CLOSE }, location.origin);
            return true;
        } catch (e) {
            return false;
        }
    }

    window.webCloseEmbeddedOverlay = closeEmbed;

    if (window !== window.top) {
        document.addEventListener('click', function (e) {
            var fsBtn = e.target.closest('[data-web-fullscreen-toggle]');
            if (fsBtn) {
                e.preventDefault();
                e.stopPropagation();
                try {
                    window.top.postMessage({ type: 'web-toggle-fullscreen' }, location.origin);
                } catch (err) {}
                return;
            }
            if (!isEmbed()) return;
            var home = e.target.closest('a.ma-home-btn, button.ma-home-btn');
            if (!home) return;
            e.preventDefault();
            closeEmbed();
        }, true);
        window.addEventListener('message', function (e) {
            if (e.origin !== location.origin) return;
            if (!e.data || e.data.type !== 'web-fullscreen-state') return;
            var on = !!e.data.on;
            document.documentElement.classList.toggle('web-is-fullscreen', on);
            document.querySelectorAll('[data-web-fullscreen-toggle]').forEach(function (btn) {
                btn.hidden = false;
                btn.setAttribute('aria-pressed', on ? 'true' : 'false');
                var label = on ? 'Обычный режим' : 'На весь экран';
                btn.title = label;
                btn.setAttribute('aria-label', label);
            });
        });
        function showEmbedFsButtons() {
            document.querySelectorAll('[data-web-fullscreen-toggle]').forEach(function (btn) {
                btn.hidden = false;
            });
        }
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', showEmbedFsButtons);
        } else {
            showEmbedFsButtons();
        }
        if (isEmbed()) return;
    }

    function publicUrl(href) {
        var url = new URL(href, location.href);
        url.searchParams.delete('embed');
        return url.pathname + url.search + url.hash;
    }

    function embedUrl(href) {
        var url = new URL(href, location.href);
        url.searchParams.set('embed', '1');
        return url.pathname + url.search + url.hash;
    }

    function overlayEl() {
        return document.getElementById(OVERLAY_ID);
    }

    function isOpen() {
        var wrap = overlayEl();
        return !!(wrap && !wrap.hidden);
    }

    function closeOverlay(opts) {
        var fromPop = !!(opts && opts.fromPopstate);
        var wrap = overlayEl();
        var wasOpen = wrap && !wrap.hidden;
        if (wrap) {
            wrap.hidden = true;
            wrap.setAttribute('aria-hidden', 'true');
            document.body.classList.remove('web-page-overlay-open');
            var frame = wrap.querySelector('iframe');
            if (frame) frame.src = 'about:blank';
        }
        if (wasOpen && !fromPop && history.state && history.state.webPageOverlay) {
            history.back();
        }
    }

    function ensureOverlay() {
        var wrap = overlayEl();
        if (wrap) return wrap;
        wrap = document.createElement('div');
        wrap.id = OVERLAY_ID;
        wrap.className = 'web-page-overlay';
        wrap.hidden = true;
        wrap.setAttribute('aria-hidden', 'true');
        var frame = document.createElement('iframe');
        frame.className = 'web-page-overlay__frame';
        frame.title = 'Просмотр';
        frame.setAttribute('allow', 'fullscreen; autoplay; microphone');
        wrap.appendChild(frame);
        document.body.appendChild(wrap);
        return wrap;
    }

    function bindOverlay() {
        if (bound) return;
        bound = true;
        window.addEventListener('message', function (e) {
            if (e.origin !== location.origin) return;
            if (!e.data || e.data.type !== MSG_CLOSE) return;
            closeOverlay();
        });
        window.addEventListener('popstate', function () {
            if (history.state && history.state.webPageOverlay) {
                openOverlay(history.state.href || location.href, { fromPopstate: true });
                return;
            }
            if (isOpen()) closeOverlay({ fromPopstate: true });
        });
        document.addEventListener('click', function (e) {
            var a = e.target.closest('a[href]');
            if (!a) return;
            if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;
            if (a.target && a.target !== '_self' && a.target !== '') return;
            var url;
            try {
                url = new URL(a.href, location.href);
            } catch (err) {
                return;
            }
            if (url.origin !== location.origin) return;
            if (!isOverlayViewPath(url.pathname)) return;
            e.preventDefault();
            openOverlay(url.pathname + url.search + url.hash);
        }, true);
    }

    function openOverlay(href, opts) {
        if (!href) return;
        bindOverlay();
        var fromPop = !!(opts && opts.fromPopstate);
        var wrap = ensureOverlay();
        var already = isOpen();
        var frameEl = wrap.querySelector('iframe');
        var shown = publicUrl(href);
        wrap.hidden = false;
        wrap.setAttribute('aria-hidden', 'false');
        document.body.classList.add('web-page-overlay-open');
        frameEl.src = embedUrl(href);
        if (fromPop) return;
        var state = { webPageOverlay: true, href: shown };
        if (already && history.state && history.state.webPageOverlay) {
            history.replaceState(state, '', shown);
        } else {
            history.pushState(state, '', shown);
        }
    }

    window.webOpenPageOverlay = openOverlay;
    bindOverlay();
})();

(function () {
    var NET = 'Плохое соединение с интернетом — проверьте связь';
    var CREATE = 'Не удалось сделать скриншот. Попробуйте ещё раз.';
    var SAVE = 'Не удалось сохранить скриншот. Попробуйте ещё раз.';
    var SEND = 'Не удалось отправить скриншот. Попробуйте ещё раз.';
    var ARCHIVE = 'Не удалось скачать архив со скриншотами. Попробуйте ещё раз.';
    var ARCHIVE_SEND = 'Не удалось отправить архив со скриншотами. Попробуйте ещё раз.';
    var SERVER = 'Сервер временно недоступен. Попробуйте позже.';

    function byKind(kind) {
        if (kind === 'save') return SAVE;
        if (kind === 'send') return SEND;
        if (kind === 'archive') return ARCHIVE;
        if (kind === 'archive_send') return ARCHIVE_SEND;
        return CREATE;
    }

    function isNetworkish(err) {
        try {
            if (typeof navigator !== 'undefined' && navigator.onLine === false) return true;
        } catch (e) {}
        if (!err) return false;
        var name = String(err.name || '');
        var msg = String(err.message || err || '');
        if (name === 'NetworkError' || name === 'AbortError') return true;
        return /failed to fetch|networkerror|load failed|offline|internet|connection|timeout|таймаут|network/i.test(msg);
    }

    window.webScreenshotErrorMessage = function (kind, cause) {
        var status = 0;
        if (typeof cause === 'number') status = cause;
        else if (cause && typeof cause.status === 'number') status = cause.status;
        if (status === 401) return 'Нужна авторизация';
        if (status >= 500) return SERVER;
        if (status > 0) return byKind(kind);
        if (isNetworkish(cause)) return NET;
        return byKind(kind);
    };
})();


/* Бургер шапки кабинета: на узких экранах навигация и кнопки живут
   в выпадающей панели. */
(function () {
    var burger = document.getElementById('web-burger');
    var menu = document.getElementById('web-header-menu');
    if (!burger || !menu) return;

    function setOpen(open) {
        menu.classList.toggle('is-open', open);
        burger.setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    burger.addEventListener('click', function (e) {
        e.stopPropagation();
        setOpen(!menu.classList.contains('is-open'));
    });
    // переход по ссылке или нажатие кнопки закрывают панель
    menu.addEventListener('click', function (e) {
        if (e.target.closest('a, button')) setOpen(false);
    });
    document.addEventListener('click', function (e) {
        if (!menu.contains(e.target) && !burger.contains(e.target)) setOpen(false);
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') setOpen(false);
    });
    // на широком экране панель не нужна: иначе после поворота телефона
    // она осталась бы висеть поверх обычной шапки
    window.addEventListener('resize', function () {
        if (window.innerWidth > 760) setOpen(false);
    });
})();
