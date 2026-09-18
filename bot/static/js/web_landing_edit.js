/**
 * Режим редактирования лендинга. Подключается только админам - обычные
 * посетители этот файл не скачивают.
 *
 * Что умеет:
 *   - текст узлов с data-lp, размер множителем, жирность, адрес ссылки;
 *   - цвета текста, обводку, фон блока и фон страницы - в отдельном мини-окне,
 *     каждый цвет по темам (тёмная / светлая);
 *   - пресеты стиля текста: сохранить стиль выделенного и применить в один клик;
 *   - блоки секций: добавить, убрать, перетащить за ручку или сдвинуть
 *     стрелками; целые секции лендинга - стрелками;
 *   - замена картинок.
 *
 * Тексты, стили и фоны копятся и уходят кнопкой «Сохранить». Структура
 * (состав и порядок блоков и секций), картинки и пресеты сохраняются сразу:
 * это отдельные операции, копить их вместе с текстом незачем.
 */
(function () {
    var toggle = document.getElementById('lbg-edit-toggle');
    if (!toggle) return;

    var SIZE_MIN = 0.8;
    var SIZE_MAX = 1.4;
    var SIZE_STEP = 0.05;

    var nodes = [].slice.call(document.querySelectorAll('[data-lp]'));

    var editing = false;
    var active = null;          // выделенный текстовый узел
    var activeBg = null;        // выделенная цель фона без текста (пустое место блока)
    var dirty = {};             // key -> true (тексты и стили)
    var bgDirty = {};           // target -> true
    var state = {};             // key -> {text, style, href?}
    var bgState = {};           // target -> {dark?, light?}
    var panel = null;
    var pop = null;             // мини-окно цветов
    var presetsBox = null;      // окно пресетов

    function readJson(id, fallback) {
        try {
            var el = document.getElementById(id);
            if (el) return JSON.parse(el.textContent) || fallback;
        } catch (e) {}
        return fallback;
    }

    function readAttrJson(el, name) {
        var raw = el && el.getAttribute(name);
        if (!raw) return {};
        try {
            return JSON.parse(raw) || {};
        } catch (e) {
            return {};
        }
    }

    // Исходники из шаблона для ключей, которые уже переопределены в БД.
    // Для остальных исходник - то, что пришло в разметке.
    var defaults = readJson('lp-defaults', {});
    var hrefDefaults = readJson('lp-href-defaults', {});
    var presets = readJson('lp-presets', []);

    nodes.forEach(function (el) {
        var key = el.getAttribute('data-lp');
        var text = el.textContent.trim();
        state[key] = { text: text, style: readAttrJson(el, 'data-lp-style') };
        if (!(key in defaults)) defaults[key] = text;
        if (el.tagName === 'A') {
            // getAttribute, а не .href: браузер достраивает адрес до полного
            var href = el.getAttribute('href') || '';
            state[key].href = href;
            if (!(key in hrefDefaults)) hrefDefaults[key] = href;
        }
    });

    // --- цели фона ------------------------------------------------------------

    var body = document.body;
    var pageName = body.getAttribute('data-lp-page') || '';
    var pageTarget = body.getAttribute('data-lp-page-bg') || '';
    var bgTargets = [].slice.call(document.querySelectorAll('[data-lp-bg]'));

    bgTargets.forEach(function (el) {
        bgState[el.getAttribute('data-lp-bg')] = readAttrJson(el, 'data-lp-bg-style');
    });
    if (pageTarget) bgState[pageTarget] = readAttrJson(body, 'data-lp-bg-style');

    function bgSelector(target) {
        if (target === pageTarget) return 'body.lbg[data-lp-page="' + pageName + '"]';
        return '.lbg [data-lp-bg="' + target + '"]';
    }

    function bgTargetOf(el) {
        var holder = el && el.closest('[data-lp-bg]');
        return holder ? holder.getAttribute('data-lp-bg') : '';
    }

    function bgLabel(target) {
        if (target === pageTarget) return 'страницы';
        var el = document.querySelector('[data-lp-bg="' + target + '"]');
        var title = el && el.querySelector('h1, h2, h3, .lbg-faq__q [data-lp], .lbg-faq-link__title');
        var text = title ? title.textContent.trim() : '';
        if (text.length > 28) text = text.slice(0, 27) + '…';
        return text ? 'блока «' + text + '»' : 'блока';
    }

    // --- общие помощники ------------------------------------------------------

    function defaultHref(key) {
        return hrefDefaults[key] != null ? hrefDefaults[key] : '';
    }

    function defaultText(key) {
        return defaults[key] != null ? defaults[key] : '';
    }

    function isLink(el) {
        return !!el && el.tagName === 'A';
    }

    function keyOf(el) {
        return el.getAttribute('data-lp');
    }

    function isPristine(key) {
        var st = state[key];
        if (st.href !== undefined && st.href !== defaultHref(key)) return false;
        return st.text === defaultText(key) && !Object.keys(st.style).length;
    }

    function copy(obj) {
        return JSON.parse(JSON.stringify(obj || {}));
    }

    // rgb(a) из getComputedStyle -> #rrggbb для <input type="color">
    function toHex(color, fallback) {
        var m = String(color || '').match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?/);
        if (!m || (m[4] !== undefined && parseFloat(m[4]) === 0)) return fallback;
        return '#' + [m[1], m[2], m[3]].map(function (n) {
            var h = parseInt(n, 10).toString(16);
            return h.length === 1 ? '0' + h : h;
        }).join('');
    }

    function currentTheme() {
        return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
    }

    // Видимый сейчас фон элемента: прозрачные слои пропускаем вверх до body.
    function visibleBg(el) {
        var node = el;
        while (node && node.nodeType === 1) {
            var hex = toHex(getComputedStyle(node).backgroundColor, '');
            if (hex) return hex;
            node = node.parentElement;
        }
        return currentTheme() === 'light' ? '#f3f4f6' : '#121212';
    }

    // --- живое превью цветов и фонов ------------------------------------------

    // Цвета и фоны зависят от темы, поэтому идут правилами, а не инлайном.
    // Серверный <style id="lp-colors"> на время правки отключаем: иначе
    // сброшенный цвет продолжал бы показываться до перезагрузки. Всё, что в
    // нём было для этой страницы, уже лежит в state/bgState из атрибутов.
    var serverStyle = document.getElementById('lp-colors');

    function renderLive() {
        var el = document.getElementById('lp-colors-live');
        if (!el) {
            el = document.createElement('style');
            el.id = 'lp-colors-live';
            document.head.appendChild(el);
        }
        if (serverStyle && serverStyle.sheet) serverStyle.sheet.disabled = true;

        // те же привязки к теме, что в landing_text_service (DARK_SCOPE/LIGHT_SCOPE)
        var dark = 'html:not([data-theme="light"]) ';
        var light = 'html[data-theme="light"] ';
        var css = '';
        Object.keys(state).forEach(function (key) {
            var color = state[key].style.color;
            if (!color) return;
            var sel = '.lbg [data-lp="' + key + '"]';
            if (color.dark) css += dark + sel + '{color:' + color.dark + '}';
            if (color.light) css += light + sel + '{color:' + color.light + '}';
        });
        Object.keys(bgState).forEach(function (target) {
            var bg = bgState[target] || {};
            var sel = bgSelector(target);
            if (bg.dark) css += dark + sel + '{background:' + bg.dark + '}';
            if (bg.light) css += light + sel + '{background:' + bg.light + '}';
        });
        el.textContent = css;
    }

    function applyStyle(el, st) {
        el.style.fontSize = st.size ? st.size.toFixed(2) + 'em' : '';
        el.style.fontWeight = st.bold ? '700' : '';
        el.style.color = '';
        if (st.stroke) {
            el.style.webkitTextStroke = st.stroke.width + 'px ' + st.stroke.color;
            el.style.paintOrder = 'stroke fill';
        } else {
            el.style.webkitTextStroke = '';
            el.style.paintOrder = '';
        }
    }

    function markDirty(el) {
        dirty[keyOf(el)] = true;
        refreshCounter();
    }

    function markBgDirty(target) {
        bgDirty[target] = true;
        refreshCounter();
    }

    // --- основная панель ------------------------------------------------------

    function buildPanel() {
        panel = document.createElement('div');
        panel.className = 'lbg-ed';
        panel.innerHTML = [
            '<div class="lbg-ed__row">',
            '  <div class="lbg-ed__hint" id="lbg-ed-hint">Кликните по тексту, чтобы изменить его, или по пустому месту блока - чтобы сменить его фон</div>',
            '  <div class="lbg-ed__tools" id="lbg-ed-tools">',
            '    <button type="button" data-act="smaller" title="Мельче">A−</button>',
            '    <span class="lbg-ed__size" id="lbg-ed-size">100%</span>',
            '    <button type="button" data-act="bigger" title="Крупнее">A+</button>',
            '    <button type="button" data-act="bold" title="Жирный"><b>Ж</b></button>',
            '    <button type="button" data-act="presets" title="Пресеты стилей">Пресеты</button>',
            '    <button type="button" data-act="clear" title="Вернуть исходный текст и оформление">Сброс</button>',
            '  </div>',
            '  <button type="button" class="lbg-ed__colors" data-act="colors" title="Цвет текста, обводка и фон">',
            '    <span class="lbg-ed__swatch" aria-hidden="true"></span>Цвета и фон',
            '  </button>',
            '</div>',
            '<label class="lbg-ed__href" id="lbg-ed-href-box" title="Куда ведёт ссылка">',
            '  <span>Ссылка</span>',
            '  <input type="text" id="lbg-ed-href" data-act="href" spellcheck="false"',
            '         placeholder="/web/analyze или https://…">',
            '</label>',
            '<div class="lbg-ed__actions">',
            '  <span class="lbg-ed__counter" id="lbg-ed-counter"></span>',
            '  <button type="button" class="lbg-ed__cancel" data-act="cancel">Отменить</button>',
            '  <button type="button" class="lbg-ed__save" data-act="save">Сохранить</button>',
            '</div>'
        ].join('');
        document.body.appendChild(panel);
        panel.addEventListener('click', onPanelClick);
        panel.addEventListener('input', onPanelInput);
    }

    function refreshCounter() {
        var n = Object.keys(dirty).length + Object.keys(bgDirty).length;
        var el = document.getElementById('lbg-ed-counter');
        if (el) el.textContent = n ? 'изменено: ' + n : '';
        var save = panel && panel.querySelector('.lbg-ed__save');
        if (save) save.disabled = !n;
    }

    function refreshTools() {
        if (!panel) return;
        var tools = document.getElementById('lbg-ed-tools');
        var hint = document.getElementById('lbg-ed-hint');
        tools.style.display = active ? 'flex' : 'none';
        hint.style.display = active ? 'none' : 'block';
        refreshHrefBox();
        if (active) {
            var st = state[keyOf(active)].style;
            document.getElementById('lbg-ed-size').textContent =
                Math.round((st.size || 1) * 100) + '%';
            tools.querySelector('[data-act="bold"]').classList.toggle('is-on', !!st.bold);
        }
        if (pop && !pop.hidden) fillPop();
        if (presetsBox && !presetsBox.hidden) renderPresets();
        positionFloating();
    }

    function refreshHrefBox() {
        var box = document.getElementById('lbg-ed-href-box');
        var input = document.getElementById('lbg-ed-href');
        var show = !!active && isLink(active);
        box.style.display = show ? 'inline-flex' : 'none';
        if (show) input.value = state[keyOf(active)].href || '';
    }

    function onPanelClick(e) {
        var btn = e.target.closest('[data-act]');
        if (!btn || btn.tagName === 'INPUT') return;
        var act = btn.getAttribute('data-act');

        if (act === 'save') return save();
        if (act === 'cancel') return cancel();
        if (act === 'colors') return togglePop();
        if (!active) return;
        if (act === 'presets') return togglePresets();

        var k = keyOf(active);
        var st = state[k].style;

        if (act === 'smaller' || act === 'bigger') {
            var next = (st.size || 1) + (act === 'bigger' ? SIZE_STEP : -SIZE_STEP);
            next = Math.min(SIZE_MAX, Math.max(SIZE_MIN, Math.round(next * 100) / 100));
            if (Math.abs(next - 1) < 0.001) delete st.size;
            else st.size = next;
        } else if (act === 'bold') {
            if (st.bold) delete st.bold;
            else st.bold = true;
        } else if (act === 'clear') {
            active.textContent = defaultText(k);
            state[k].text = defaultText(k);
            state[k].style = {};
            st = state[k].style;
            if (state[k].href !== undefined) {
                state[k].href = defaultHref(k);
                active.setAttribute('href', state[k].href);
            }
            renderLive();
        }

        applyStyle(active, st);
        markDirty(active);
        refreshTools();
    }

    function onPanelInput(e) {
        var input = e.target.closest('[data-act="href"]');
        if (!input || !active || !isLink(active)) return;
        var key = keyOf(active);
        state[key].href = input.value.trim();
        active.setAttribute('href', state[key].href || defaultHref(key));
        markDirty(active);
    }

    // --- мини-окно цветов -----------------------------------------------------

    function colorPair(prefix, darkTitle, lightTitle) {
        return [
            '<label class="lbg-ed-pop__color" title="' + darkTitle + '">',
            '  <input type="color" data-pop="' + prefix + '-dark"><span>Тёмная</span>',
            '</label>',
            '<label class="lbg-ed-pop__color" title="' + lightTitle + '">',
            '  <input type="color" data-pop="' + prefix + '-light"><span>Светлая</span>',
            '</label>',
            '<button type="button" class="lbg-ed-pop__reset" data-pop="' + prefix + '-reset"',
            ' title="Вернуть как было в шаблоне">По умолчанию</button>'
        ].join('');
    }

    function buildPop() {
        pop = document.createElement('div');
        pop.className = 'lbg-ed-pop';
        pop.hidden = true;
        pop.innerHTML = [
            '<div class="lbg-ed-pop__head">',
            '  <b>Цвета и фон</b>',
            '  <button type="button" class="lbg-ed-pop__close" data-pop="close" aria-label="Закрыть">×</button>',
            '</div>',
            '<div class="lbg-ed-pop__group" data-group="text">',
            '  <div class="lbg-ed-pop__title">Цвет текста</div>',
            '  <div class="lbg-ed-pop__row">' + colorPair('text', 'Цвет в тёмной теме', 'Цвет в светлой теме') + '</div>',
            '</div>',
            '<div class="lbg-ed-pop__group" data-group="stroke">',
            '  <div class="lbg-ed-pop__title">Обводка текста</div>',
            '  <div class="lbg-ed-pop__row">',
            '    <button type="button" data-pop="stroke-toggle">Выкл</button>',
            '    <label class="lbg-ed-pop__color" title="Цвет обводки">',
            '      <input type="color" data-pop="stroke-color" value="#000000"><span>Цвет</span>',
            '    </label>',
            '    <span class="lbg-ed-pop__widths" title="Толщина">',
            '      <button type="button" data-pop="stroke-w" data-w="1">1</button>',
            '      <button type="button" data-pop="stroke-w" data-w="2">2</button>',
            '      <button type="button" data-pop="stroke-w" data-w="3">3</button>',
            '    </span>',
            '  </div>',
            '</div>',
            '<div class="lbg-ed-pop__group" data-group="block">',
            '  <div class="lbg-ed-pop__title" id="lbg-ed-pop-block-title">Фон блока</div>',
            '  <div class="lbg-ed-pop__row">' + colorPair('block', 'Фон в тёмной теме', 'Фон в светлой теме') + '</div>',
            '</div>',
            '<div class="lbg-ed-pop__group" data-group="page">',
            '  <div class="lbg-ed-pop__title">Фон страницы</div>',
            '  <div class="lbg-ed-pop__row">' + colorPair('page', 'Фон страницы в тёмной теме', 'Фон страницы в светлой теме') + '</div>',
            '</div>'
        ].join('');
        document.body.appendChild(pop);
        pop.addEventListener('click', onPopClick);
        pop.addEventListener('input', onPopInput);
    }

    function currentBlockTarget() {
        if (active) return bgTargetOf(active);
        return activeBg || '';
    }

    function setInput(name, value) {
        var input = pop.querySelector('[data-pop="' + name + '"]');
        if (input && value) input.value = value;
    }

    // Поля цвета заполняем сохранённым значением, а если его нет - тем, что
    // сейчас видно на странице: админ начинает крутить от реального цвета.
    function fillPop() {
        var theme = currentTheme();
        var other = theme === 'light' ? 'dark' : 'light';
        var textGroup = pop.querySelector('[data-group="text"]');
        var strokeGroup = pop.querySelector('[data-group="stroke"]');
        var blockGroup = pop.querySelector('[data-group="block"]');
        var pageGroup = pop.querySelector('[data-group="page"]');

        textGroup.hidden = !active;
        strokeGroup.hidden = !active;
        if (active) {
            var st = state[keyOf(active)].style;
            var seen = toHex(getComputedStyle(active).color, theme === 'light' ? '#000000' : '#eeeeee');
            var color = st.color || {};
            setInput('text-' + theme, color[theme] || seen);
            setInput('text-' + other, color[other] || (other === 'light' ? '#000000' : '#eeeeee'));

            var toggleBtn = pop.querySelector('[data-pop="stroke-toggle"]');
            toggleBtn.textContent = st.stroke ? 'Вкл' : 'Выкл';
            toggleBtn.classList.toggle('is-on', !!st.stroke);
            if (st.stroke) setInput('stroke-color', st.stroke.color);
            [].forEach.call(pop.querySelectorAll('[data-pop="stroke-w"]'), function (b) {
                b.classList.toggle('is-on', !!st.stroke && String(st.stroke.width) === b.getAttribute('data-w'));
            });
        }

        var target = currentBlockTarget();
        blockGroup.hidden = !target;
        if (target) {
            document.getElementById('lbg-ed-pop-block-title').textContent = 'Фон ' + bgLabel(target);
            var holder = document.querySelector('[data-lp-bg="' + target + '"]');
            var bg = bgState[target] || {};
            setInput('block-' + theme, bg[theme] || visibleBg(holder));
            setInput('block-' + other, bg[other] || (other === 'light' ? '#e8eaee' : '#1e1e1e'));
        }

        pageGroup.hidden = !pageTarget;
        if (pageTarget) {
            var pbg = bgState[pageTarget] || {};
            setInput('page-' + theme, pbg[theme] || visibleBg(body));
            setInput('page-' + other, pbg[other] || (other === 'light' ? '#f3f4f6' : '#121212'));
        }
    }

    function togglePop(force) {
        if (!pop) buildPop();
        var open = typeof force === 'boolean' ? force : pop.hidden;
        if (open && presetsBox) presetsBox.hidden = true;
        pop.hidden = !open;
        if (open) fillPop();
        positionFloating();
    }

    function setBg(target, theme, value) {
        bgState[target] = bgState[target] || {};
        bgState[target][theme] = value;
        renderLive();
        markBgDirty(target);
    }

    function onPopInput(e) {
        var input = e.target.closest('[data-pop]');
        if (!input) return;
        var name = input.getAttribute('data-pop');
        var parts = name.split('-');
        var group = parts[0];
        var theme = parts[1];

        if (group === 'text' && active) {
            var st = state[keyOf(active)].style;
            st.color = st.color || {};
            st.color[theme] = input.value;
            renderLive();
            markDirty(active);
        } else if (name === 'stroke-color' && active) {
            var sst = state[keyOf(active)].style;
            sst.stroke = { width: (sst.stroke && sst.stroke.width) || 1, color: input.value };
            applyStyle(active, sst);
            markDirty(active);
            fillPop();
        } else if (group === 'block') {
            var target = currentBlockTarget();
            if (target) setBg(target, theme, input.value);
        } else if (group === 'page' && pageTarget) {
            setBg(pageTarget, theme, input.value);
        }
    }

    function onPopClick(e) {
        var btn = e.target.closest('button[data-pop]');
        if (!btn) return;
        var name = btn.getAttribute('data-pop');

        if (name === 'close') return togglePop(false);

        if (name === 'page-reset' && pageTarget) {
            bgState[pageTarget] = {};
            renderLive();
            markBgDirty(pageTarget);
            return fillPop();
        }
        if (name === 'block-reset') {
            var target = currentBlockTarget();
            if (!target) return;
            bgState[target] = {};
            renderLive();
            markBgDirty(target);
            return fillPop();
        }
        if (!active) return;
        var st = state[keyOf(active)].style;

        if (name === 'text-reset') {
            delete st.color;
            renderLive();
        } else if (name === 'stroke-toggle') {
            if (st.stroke) {
                delete st.stroke;
            } else {
                var sc = pop.querySelector('[data-pop="stroke-color"]');
                st.stroke = { width: 1, color: (sc && sc.value) || '#000000' };
            }
        } else if (name === 'stroke-w') {
            var w = parseInt(btn.getAttribute('data-w'), 10) || 1;
            var col = (st.stroke && st.stroke.color)
                || (pop.querySelector('[data-pop="stroke-color"]') || {}).value
                || '#000000';
            st.stroke = { width: w, color: col };
        } else {
            return;
        }
        applyStyle(active, st);
        markDirty(active);
        fillPop();
    }

    // --- пресеты --------------------------------------------------------------

    function buildPresets() {
        presetsBox = document.createElement('div');
        presetsBox.className = 'lbg-ed-pop lbg-ed-presets';
        presetsBox.hidden = true;
        presetsBox.innerHTML = [
            '<div class="lbg-ed-pop__head">',
            '  <b>Пресеты стилей</b>',
            '  <button type="button" class="lbg-ed-pop__close" data-preset="close" aria-label="Закрыть">×</button>',
            '</div>',
            '<div class="lbg-ed-presets__list" id="lbg-ed-presets-list"></div>',
            '<button type="button" class="lbg-ed-presets__save" data-preset="save">+ Сохранить стиль выделенного текста</button>'
        ].join('');
        document.body.appendChild(presetsBox);
        presetsBox.addEventListener('click', onPresetsClick);
    }

    function previewCss(style) {
        var theme = currentTheme();
        var css = 'font-size:' + (style.size || 1).toFixed(2) + 'em;';
        if (style.bold) css += 'font-weight:700;';
        var color = (style.color || {})[theme];
        if (color) css += 'color:' + color + ';';
        if (style.stroke) {
            css += '-webkit-text-stroke:' + style.stroke.width + 'px ' + style.stroke.color
                + ';paint-order:stroke fill;';
        }
        return css;
    }

    function escapeHtml(text) {
        return String(text || '').replace(/[&<>"']/g, function (ch) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
        });
    }

    function renderPresets() {
        var list = document.getElementById('lbg-ed-presets-list');
        if (!presets.length) {
            list.innerHTML = '<p class="lbg-ed-presets__empty">Пока пусто. Выделите текст, '
                + 'настройте его стиль и сохраните - потом он применяется в один клик.</p>';
        } else {
            list.innerHTML = presets.map(function (p) {
                return '<div class="lbg-ed-presets__item">'
                    + '<button type="button" class="lbg-ed-presets__apply" data-preset-apply="' + escapeHtml(p.id) + '"'
                    + (active ? '' : ' disabled') + ' title="Применить к выделенному тексту">'
                    + '<span class="lbg-ed-presets__sample" style="' + escapeHtml(previewCss(p.style)) + '">Аа</span>'
                    + '<span class="lbg-ed-presets__name">' + escapeHtml(p.name) + '</span>'
                    + '</button>'
                    + '<button type="button" class="lbg-ed-presets__del" data-preset-del="' + escapeHtml(p.id) + '"'
                    + ' title="Удалить пресет" aria-label="Удалить пресет">×</button>'
                    + '</div>';
            }).join('');
        }
        var saveBtn = presetsBox.querySelector('[data-preset="save"]');
        var st = active ? state[keyOf(active)].style : null;
        saveBtn.disabled = !st || !Object.keys(st).length;
        saveBtn.title = saveBtn.disabled
            ? 'Сначала выделите текст и задайте ему стиль'
            : 'Запомнить стиль выделенного текста';
    }

    function togglePresets(force) {
        if (!presetsBox) buildPresets();
        var open = typeof force === 'boolean' ? force : presetsBox.hidden;
        if (open && pop) pop.hidden = true;
        presetsBox.hidden = !open;
        if (open) renderPresets();
        positionFloating();
    }

    function savePresets(next) {
        return api('/web/landing/api/presets', { items: next }).then(function (data) {
            presets = data.items || [];
            renderPresets();
        });
    }

    function onPresetsClick(e) {
        var btn = e.target.closest('button');
        if (!btn) return;

        if (btn.getAttribute('data-preset') === 'close') return togglePresets(false);

        if (btn.getAttribute('data-preset') === 'save') {
            if (!active) return;
            var st = state[keyOf(active)].style;
            if (!Object.keys(st).length) return;
            var name = (prompt('Название пресета', 'Мой стиль') || '').trim();
            if (!name) return;
            var id = 'p' + Math.random().toString(16).slice(2, 10);
            savePresets(presets.concat([{ id: id, name: name.slice(0, 40), style: copy(st) }]))
                .catch(function (err) { alert('Не удалось сохранить пресет: ' + err.message); });
            return;
        }

        var applyId = btn.getAttribute('data-preset-apply');
        if (applyId && active) {
            var preset = presets.filter(function (p) { return p.id === applyId; })[0];
            if (!preset) return;
            state[keyOf(active)].style = copy(preset.style);
            applyStyle(active, state[keyOf(active)].style);
            renderLive();
            markDirty(active);
            refreshTools();
            return;
        }

        var delId = btn.getAttribute('data-preset-del');
        if (delId) {
            if (!confirm('Удалить пресет?')) return;
            savePresets(presets.filter(function (p) { return p.id !== delId; }))
                .catch(function (err) { alert('Не удалось удалить пресет: ' + err.message); });
        }
    }

    // Мини-окна висят над панелью и не должны её перекрывать.
    function positionFloating() {
        if (!panel) return;
        var bottom = panel.offsetHeight + 28;
        [pop, presetsBox].forEach(function (box) {
            if (box) box.style.bottom = bottom + 'px';
        });
    }

    // --- выбор узлов и целей фона ---------------------------------------------

    function setActiveBg(target) {
        if (activeBg) {
            var prev = document.querySelector('[data-lp-bg="' + activeBg + '"]');
            if (prev) prev.classList.remove('is-lp-bg-active');
        }
        activeBg = target || null;
        if (activeBg) {
            var el = document.querySelector('[data-lp-bg="' + activeBg + '"]');
            if (el) el.classList.add('is-lp-bg-active');
        }
    }

    function select(el) {
        if (active !== el) {
            if (active) active.classList.remove('is-lp-active');
            active = el;
            if (active) active.classList.add('is-lp-active');
        }
        if (el) setActiveBg(null);
        refreshTools();
    }

    function onNodeClick(e) {
        if (!editing) return;
        // ссылки внутри режима редактирования никуда не ведут, вопрос FAQ
        // внутри <summary> не сворачивает ответ
        if (this.closest('a') || this.closest('summary')) e.preventDefault();
        e.stopPropagation();
        select(this);
    }

    function onNodeInput() {
        state[keyOf(this)].text = this.textContent.trim();
        markDirty(this);
    }

    function onNodePaste(e) {
        // вставляем только текст, иначе в узел попадёт чужая разметка
        e.preventDefault();
        var text = (e.clipboardData || window.clipboardData).getData('text');
        document.execCommand('insertText', false, (text || '').replace(/\s+/g, ' '));
    }

    function onNodeKeydown(e) {
        // Enter не должен плодить <div> внутри заголовка
        if (e.key === 'Enter') e.preventDefault();
        if (e.key === 'Escape') {
            this.blur();
            select(null);
        }
    }

    var EDITOR_UI = '.lbg-ed, .lbg-ed-pop, .lbg-block-tools, .lbg-section-tools, [data-lp-block-add]';

    // Клик мимо текста: по пустому месту блока - выбрать его фон, вовсе мимо -
    // снять выделение. Ссылки-карточки в режиме правки никуда не ведут.
    function onDocumentClick(e) {
        if (!editing) return;
        if (e.target.closest(EDITOR_UI)) return;
        var link = e.target.closest('a');
        if (link && (link.hasAttribute('data-lp-bg') || link.querySelector('[data-lp]') || link.hasAttribute('data-lp'))) {
            e.preventDefault();
        }
        if (e.target.closest('[data-lp]')) return;
        select(null);
        var target = bgTargetOf(e.target);
        setActiveBg(target);
        if (pop && !pop.hidden) fillPop();
    }

    // --- блоки и секции: состав и порядок -------------------------------------

    function api(url, payload) {
        return fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify(payload)
        }).then(function (r) {
            return r.json().catch(function () { return {}; }).then(function (data) {
                if (!r.ok) {
                    var detail = typeof data.detail === 'string' ? data.detail : '';
                    throw new Error(detail || ('HTTP ' + r.status));
                }
                return data;
            });
        });
    }

    function blockOf(el) {
        return el.closest('[data-lp-block]');
    }

    function containerOf(block) {
        return block && block.parentElement && block.parentElement.closest('[data-lp-section]');
    }

    function orderOf(container) {
        return [].filter.call(container.children, function (el) {
            return el.matches('[data-lp-block]');
        }).map(function (el) {
            return el.getAttribute('data-lp-block');
        });
    }

    function saveOrder(container) {
        container.classList.add('is-lp-saving');
        api('/web/landing/api/blocks', {
            section: container.getAttribute('data-lp-section'),
            action: 'move',
            order: orderOf(container)
        }).then(function () {
            container.classList.remove('is-lp-saving');
        }).catch(function (err) {
            alert('Не удалось сохранить порядок: ' + err.message);
            location.reload();
        });
    }

    function siblingBlock(block, dir) {
        var el = dir < 0 ? block.previousElementSibling : block.nextElementSibling;
        while (el && !el.matches('[data-lp-block]')) {
            el = dir < 0 ? el.previousElementSibling : el.nextElementSibling;
        }
        return el;
    }

    function moveBlock(block, dir) {
        var other = siblingBlock(block, dir);
        if (!other) return;
        if (dir < 0) other.before(block);
        else other.after(block);
        flash(block);
        saveOrder(containerOf(block));
    }

    function flash(el) {
        el.classList.remove('is-lp-moved');
        void el.offsetWidth;  // перезапуск анимации
        el.classList.add('is-lp-moved');
    }

    // Перетаскивание: блок становится draggable только пока зажата ручка,
    // иначе выделение текста мышью превращалось бы в перетаскивание.
    var dragEl = null;
    var dragStartOrder = '';

    function onHandleDown() {
        var block = blockOf(this);
        if (block && editing) block.setAttribute('draggable', 'true');
    }

    function onDragStart(e) {
        if (!editing || this.getAttribute('draggable') !== 'true') return;
        dragEl = this;
        dragStartOrder = orderOf(containerOf(this)).join(',');
        this.classList.add('is-lp-dragging');
        e.dataTransfer.effectAllowed = 'move';
        try { e.dataTransfer.setData('text/plain', this.getAttribute('data-lp-block')); } catch (err) {}
    }

    function onDragOver(e) {
        if (!dragEl) return;
        var target = e.target.closest('[data-lp-block]');
        if (!target || target === dragEl || target.parentElement !== dragEl.parentElement) return;
        e.preventDefault();
        var rect = target.getBoundingClientRect();
        var box = target.parentElement.getBoundingClientRect();
        // в сетке из нескольких колонок сравниваем по горизонтали, в столбце - по вертикали
        var horizontal = rect.width < box.width * 0.75;
        var after = horizontal
            ? e.clientX > rect.left + rect.width / 2
            : e.clientY > rect.top + rect.height / 2;
        if (after) target.after(dragEl);
        else target.before(dragEl);
    }

    function onDragEnd() {
        var block = this;
        block.removeAttribute('draggable');
        block.classList.remove('is-lp-dragging');
        var container = containerOf(block);
        dragEl = null;
        if (container && orderOf(container).join(',') !== dragStartOrder) {
            flash(block);
            saveOrder(container);
        }
    }

    function onBlockToolClick(e) {
        var btn = e.target.closest('button');
        if (!btn || !editing) return;
        // панель блока FAQ лежит внутри <summary>: клик не должен сворачивать ответ
        e.preventDefault();
        e.stopPropagation();
        var block = blockOf(btn);
        if (!block) return;
        if (btn.hasAttribute('data-lp-block-up')) moveBlock(block, -1);
        else if (btn.hasAttribute('data-lp-block-down')) moveBlock(block, 1);
        else if (btn.hasAttribute('data-lp-block-del')) removeBlock(btn, block);
    }

    function removeBlock(btn, block) {
        if (!confirm('Убрать блок со страницы?')) return;
        btn.disabled = true;
        api('/web/landing/api/blocks', {
            section: containerOf(block).getAttribute('data-lp-section'),
            action: 'remove',
            block_id: block.getAttribute('data-lp-block')
        }).then(function () { location.reload(); })
            .catch(function (err) {
                btn.disabled = false;
                alert('Не удалось убрать блок: ' + err.message);
            });
    }

    function onBlockAdd(e) {
        e.preventDefault();
        e.stopPropagation();
        if (!editing) return;
        var btn = this;
        btn.disabled = true;
        api('/web/landing/api/blocks', { section: btn.getAttribute('data-lp-block-add'), action: 'add' })
            .then(function () { location.reload(); })
            .catch(function (err) {
                btn.disabled = false;
                alert('Не удалось добавить блок: ' + err.message);
            });
    }

    function pageSections() {
        return [].slice.call(document.querySelectorAll('[data-lp-page-section]'));
    }

    function onSectionToolClick(e) {
        var btn = e.target.closest('button');
        if (!btn || !editing) return;
        e.preventDefault();
        e.stopPropagation();
        var section = btn.closest('[data-lp-page-section]');
        var list = pageSections();
        var index = list.indexOf(section);
        var up = btn.hasAttribute('data-lp-section-up');
        var other = list[index + (up ? -1 : 1)];
        if (!other) return;
        if (up) other.before(section);
        else other.after(section);
        flash(section);
        section.scrollIntoView({ block: 'start', behavior: 'smooth' });
        api('/web/landing/api/sections', {
            order: pageSections().map(function (el) { return el.getAttribute('data-lp-page-section'); })
        }).catch(function (err) {
            alert('Не удалось сохранить порядок секций: ' + err.message);
            location.reload();
        });
    }

    // --- картинки -------------------------------------------------------------

    var imageSlots = [].slice.call(document.querySelectorAll('[data-lp-img]'));
    var filePicker = null;
    var pendingSlot = null;

    function onImageClick(e) {
        if (!editing) return;
        e.preventDefault();
        e.stopPropagation();
        pendingSlot = this;
        if (!filePicker) {
            filePicker = document.createElement('input');
            filePicker.type = 'file';
            filePicker.accept = 'image/png,image/jpeg,image/webp,image/gif';
            filePicker.style.display = 'none';
            filePicker.addEventListener('change', onFilePicked);
            document.body.appendChild(filePicker);
        }
        filePicker.value = '';
        filePicker.click();
    }

    function onFilePicked() {
        var file = filePicker.files && filePicker.files[0];
        var slot = pendingSlot;
        if (!file || !slot) return;

        var data = new FormData();
        data.append('key', slot.getAttribute('data-lp-img'));
        data.append('file', file);
        slot.classList.add('is-lp-uploading');

        fetch('/web/landing/api/upload-image', {
            method: 'POST',
            credentials: 'same-origin',
            body: data
        }).then(function (r) {
            return r.json().then(function (data) {
                if (!r.ok) throw new Error(data.detail || ('HTTP ' + r.status));
                return data;
            });
        }).then(function (data) {
            slot.classList.remove('is-lp-uploading');
            if (slot.tagName === 'IMG') slot.src = data.url;
            else location.reload();  // заглушка станет обычным боксом со скриншотом
        }).catch(function (err) {
            slot.classList.remove('is-lp-uploading');
            alert('Не удалось загрузить картинку: ' + err.message);
        });
    }

    // --- включение режима ---------------------------------------------------

    function setEditing(on) {
        editing = on;
        document.body.classList.toggle('lp-editing', on);
        toggle.classList.toggle('is-on', on);
        toggle.setAttribute('aria-pressed', on ? 'true' : 'false');

        imageSlots.forEach(function (el) {
            if (on) el.addEventListener('click', onImageClick);
            else el.removeEventListener('click', onImageClick);
        });

        nodes.forEach(function (el) {
            if (on) {
                el.setAttribute('contenteditable', 'plaintext-only');
                el.addEventListener('click', onNodeClick);
                el.addEventListener('input', onNodeInput);
                el.addEventListener('paste', onNodePaste);
                el.addEventListener('keydown', onNodeKeydown);
            } else {
                el.removeAttribute('contenteditable');
                el.removeEventListener('click', onNodeClick);
                el.removeEventListener('input', onNodeInput);
                el.removeEventListener('paste', onNodePaste);
                el.removeEventListener('keydown', onNodeKeydown);
            }
        });

        if (on) {
            if (!panel) buildPanel();
            panel.classList.add('is-open');
            renderLive();
            refreshTools();
            refreshCounter();
        } else {
            if (panel) panel.classList.remove('is-open');
            if (pop) pop.hidden = true;
            if (presetsBox) presetsBox.hidden = true;
            select(null);
            setActiveBg(null);
        }
    }

    // --- сохранение -----------------------------------------------------------

    function save() {
        var keys = Object.keys(dirty);
        var targets = Object.keys(bgDirty);
        if (!keys.length && !targets.length) return;

        var items = keys.map(function (key) {
            var st = state[key].style;
            var item;
            // пустой текст без стилей сервер понимает как «вернуть шаблонный»
            // и удаляет строку - именно это нужно после «Сброса»
            if (isPristine(key)) {
                item = { key: key, text: '', style: null };
            } else {
                item = { key: key, text: state[key].text, style: Object.keys(st).length ? st : null };
            }
            if (state[key].href !== undefined) {
                // адрес, совпавший с шаблонным, сервер удалит из БД
                item.href = state[key].href === defaultHref(key) ? '' : state[key].href;
            }
            return item;
        });
        var backgrounds = targets.map(function (target) {
            var bg = bgState[target] || {};
            return { target: target, bg: Object.keys(bg).length ? bg : null };
        });

        var btn = panel.querySelector('.lbg-ed__save');
        btn.disabled = true;
        btn.textContent = 'Сохраняю…';

        api('/web/landing/api/save', { items: items, backgrounds: backgrounds }).then(function () {
            dirty = {};
            bgDirty = {};
            btn.textContent = 'Сохранено';
            setTimeout(function () {
                btn.textContent = 'Сохранить';
                refreshCounter();
            }, 1200);
        }).catch(function (err) {
            btn.disabled = false;
            btn.textContent = 'Сохранить';
            alert('Не удалось сохранить: ' + err.message);
        });
    }

    function cancel() {
        if ((Object.keys(dirty).length || Object.keys(bgDirty).length) &&
            !confirm('Несохранённые правки пропадут. Продолжить?')) return;
        location.reload();
    }

    // --- запуск ---------------------------------------------------------------

    toggle.addEventListener('click', function (e) {
        e.preventDefault();
        setEditing(!editing);
    });

    [].forEach.call(document.querySelectorAll('[data-lp-block-add]'), function (el) {
        el.addEventListener('click', onBlockAdd);
    });
    [].forEach.call(document.querySelectorAll('.lbg-block-tools'), function (el) {
        el.addEventListener('click', onBlockToolClick);
    });
    [].forEach.call(document.querySelectorAll('[data-lp-block-drag]'), function (el) {
        el.addEventListener('mousedown', onHandleDown);
        el.addEventListener('touchstart', onHandleDown, { passive: true });
    });
    [].forEach.call(document.querySelectorAll('[data-lp-block]'), function (el) {
        el.addEventListener('dragstart', onDragStart);
        el.addEventListener('dragend', onDragEnd);
    });
    [].forEach.call(document.querySelectorAll('[data-lp-section]'), function (el) {
        el.addEventListener('dragover', onDragOver);
        el.addEventListener('drop', function (e) { if (dragEl) e.preventDefault(); });
    });
    [].forEach.call(document.querySelectorAll('.lbg-section-tools'), function (el) {
        el.addEventListener('click', onSectionToolClick);
    });
    // отпустили ручку, так и не потащив, - блок снова не перетаскиваемый
    document.addEventListener('mouseup', function () {
        if (dragEl) return;
        [].forEach.call(document.querySelectorAll('[data-lp-block][draggable]'), function (el) {
            el.removeAttribute('draggable');
        });
    });

    document.addEventListener('click', onDocumentClick, true);
    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape' || !editing) return;
        if (pop && !pop.hidden) togglePop(false);
        if (presetsBox && !presetsBox.hidden) togglePresets(false);
    });
    window.addEventListener('resize', positionFloating);

    // смена темы меняет, какой цвет виден сейчас, - обновляем поля окна
    var themeBtn = document.getElementById('lbg-theme-toggle');
    if (themeBtn) {
        themeBtn.addEventListener('click', function () {
            setTimeout(function () {
                if (pop && !pop.hidden) fillPop();
                if (presetsBox && !presetsBox.hidden) renderPresets();
            }, 0);
        });
    }

    window.addEventListener('beforeunload', function (e) {
        if (!editing || (!Object.keys(dirty).length && !Object.keys(bgDirty).length)) return;
        e.preventDefault();
        e.returnValue = '';
    });
})();
