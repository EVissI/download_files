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
        if (window === window.top) {
            document.querySelectorAll('iframe.web-fs-frame').forEach(function (f) {
                try {
                    f.contentWindow.postMessage({ type: 'web-theme', theme: theme }, location.origin);
                } catch (err) {}
            });
        }
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

    function syncNav(pathname) {
        var cur = String(pathname || '').replace(/\/$/, '') || '/';
        document.querySelectorAll('.web-cabinet-header .service-nav a[href]').forEach(function (a) {
            var path = '';
            try {
                path = new URL(a.href, location.href).pathname.replace(/\/$/, '') || '/';
            } catch (err) {
                return;
            }
            a.classList.toggle('active', cur === path || cur.indexOf(path + '/') === 0);
        });
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
                syncNav(loc.pathname);
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

    window.addEventListener('pagehide', markLeaving);
    window.addEventListener('beforeunload', markLeaving);

    document.addEventListener('click', function (e) {
        var link = e.target.closest('.service-nav a[href]');
        if (!link) return;
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;
        if (link.target && link.target !== '_self') return;
        if (!fullscreenElement() && !frame) return;
        e.preventDefault();
        var nextPath = pathOf(link.href);
        var nowPath = frame ? pathOf(currentFrameHref(), location.pathname) : pathOf(location.href, location.pathname);
        if (nextPath === nowPath && frame) return;
        if (nextPath === nowPath && !frame) return;
        openInShell(link.href);
    }, true);

    document.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-web-fullscreen-toggle]');
        if (!btn) return;
        e.preventDefault();
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
    });

    function onFsChange() {
        syncButtons();
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
