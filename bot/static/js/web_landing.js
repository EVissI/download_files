/**
 * Общее для публичных страниц (/web, /web/faq, /web/articles): меню-бургер,
 * смена темы и просмотр картинок на весь экран - скриншотов лендинга и
 * картинок в статьях и ответах FAQ.
 */
(function () {
    var burger = document.getElementById('lbg-burger');
    var menu = document.getElementById('lbg-menu');

    function setMenuOpen(open) {
        if (!burger || !menu) return;
        menu.classList.toggle('is-open', open);
        burger.setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    if (burger && menu) {
        burger.addEventListener('click', function (e) {
            e.stopPropagation();
            setMenuOpen(!menu.classList.contains('is-open'));
        });
        menu.addEventListener('click', function (e) {
            if (e.target.closest('a')) setMenuOpen(false);
        });
        document.addEventListener('click', function (e) {
            if (!menu.contains(e.target) && !burger.contains(e.target)) setMenuOpen(false);
        });
        window.addEventListener('resize', function () {
            if (window.innerWidth > 820) setMenuOpen(false);
        });
    }

    var themeBtn = document.getElementById('lbg-theme-toggle');
    if (themeBtn) {
        themeBtn.addEventListener('click', function () {
            var root = document.documentElement;
            var next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
            if (next === 'light') root.setAttribute('data-theme', 'light');
            else root.removeAttribute('data-theme');
            try { localStorage.setItem('web_theme', next); } catch (e) {}
        });
    }

    // --- просмотр на весь экран ----------------------------------------------

    var box = null;
    var boxImg = null;

    function buildBox() {
        box = document.createElement('div');
        box.className = 'lbg-lightbox';
        box.setAttribute('role', 'dialog');
        box.setAttribute('aria-modal', 'true');
        box.setAttribute('aria-label', 'Подробный просмотр');
        box.hidden = true;
        box.innerHTML = '<img alt="">'
            + '<button type="button" class="lbg-lightbox__close" aria-label="Закрыть">&times;</button>';
        boxImg = box.querySelector('img');
        box.addEventListener('click', closeBox);
        document.body.appendChild(box);
    }

    function openBox(src, alt) {
        if (!src) return;
        if (!box) buildBox();
        boxImg.src = src;
        boxImg.alt = alt || '';
        box.hidden = false;
        document.body.style.overflow = 'hidden';
    }

    function closeBox() {
        if (!box || box.hidden) return;
        box.hidden = true;
        boxImg.src = '';
        document.body.style.overflow = '';
    }

    // Скриншот шага: пара картинок под тёмную и светлую тему либо одна.
    function shotOf(btn) {
        var light = document.documentElement.getAttribute('data-theme') === 'light';
        return btn.querySelector(light ? '.lbg-shot--light' : '.lbg-shot--dark')
            || btn.querySelector('img');
    }

    // В режиме правки клик по картинке - это выбор нового файла, не просмотр.
    document.addEventListener('click', function (e) {
        if (document.body.classList.contains('lp-editing')) return;
        var shotBtn = e.target.closest('.lbg-shotbox');
        if (shotBtn) {
            var shot = shotOf(shotBtn);
            if (shot) openBox(shot.getAttribute('src'), shot.getAttribute('alt'));
            return;
        }
        var img = e.target.closest('.lbg-figure img');
        if (img) openBox(img.getAttribute('src'), img.getAttribute('alt'));
    });

    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape') return;
        setMenuOpen(false);
        closeBox();
    });
})();
