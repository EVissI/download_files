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

    document.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-web-fullscreen-toggle]');
        if (!btn) return;
        e.preventDefault();
        var pending = fullscreenElement()
            ? exitFullscreen()
            : requestFullscreen(document.documentElement);
        Promise.resolve(pending).catch(function () {});
    });

    ['fullscreenchange', 'webkitfullscreenchange', 'mozfullscreenchange', 'MSFullscreenChange']
        .forEach(function (evt) {
            document.addEventListener(evt, syncButtons);
        });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', syncButtons);
    } else {
        syncButtons();
    }
})();
