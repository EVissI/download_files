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
    }

    document.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-web-theme-toggle]');
        if (!btn) return;
        e.preventDefault();
        apply(current() === 'light' ? 'dark' : 'light');
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', syncButtons);
    } else {
        syncButtons();
    }
})();

(function () {
    var WANT_KEY = 'web_want_fullscreen';
    var leavingPage = false;

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
        if (link.target && link.target !== '_self') return;
        if (fullscreenElement() || getWant()) {
            setWant(true);
            markLeaving();
        }
    }, true);

    document.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-web-fullscreen-toggle]');
        if (!btn) return;
        e.preventDefault();
        if (fullscreenElement()) {
            setWant(false);
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
