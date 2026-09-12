/**
 * Режим редактирования лендинга. Подключается только админам — обычные
 * посетители этот файл не скачивают.
 *
 * Редактируются все узлы с data-lp (шапка их не имеет). Набор правок намеренно
 * узкий: текст, размер множителем, жирность, цвет и обводка — ничего, что
 * меняет поток вёрстки.
 */
(function () {
    var toggle = document.getElementById('lbg-edit-toggle');
    if (!toggle) return;

    var nodes = [].slice.call(document.querySelectorAll('[data-lp]'));
    if (!nodes.length) return;

    var SIZE_MIN = 0.8;
    var SIZE_MAX = 1.4;
    var SIZE_STEP = 0.05;

    var editing = false;
    var active = null;
    var dirty = {};          // key -> true
    var state = {};          // key -> {text, style}
    var panel = null;

    // Исходники из шаблона для ключей, которые уже переопределены в БД.
    // Для остальных исходник — то, что пришло в разметке.
    var defaults = {};
    try {
        var raw = document.getElementById('lp-defaults');
        if (raw) defaults = JSON.parse(raw.textContent) || {};
    } catch (e) {
        defaults = {};
    }

    nodes.forEach(function (el) {
        var key = el.getAttribute('data-lp');
        var text = el.textContent.trim();
        state[key] = { text: text, style: parseStyle(el) };
        if (!(key in defaults)) defaults[key] = text;
    });

    function defaultText(key) {
        return defaults[key] != null ? defaults[key] : '';
    }

    function isPristine(key) {
        var st = state[key];
        return st.text === defaultText(key) && !Object.keys(st.style).length;
    }

    function parseStyle(el) {
        var raw = el.getAttribute('data-lp-style');
        if (!raw) return {};
        try {
            return JSON.parse(raw) || {};
        } catch (e) {
            return {};
        }
    }

    function applyStyle(el, st) {
        el.style.fontSize = st.size ? st.size.toFixed(2) + 'em' : '';
        el.style.fontWeight = st.bold ? '700' : '';
        el.style.color = st.color || '';
        if (st.stroke) {
            el.style.webkitTextStroke = st.stroke.width + 'px ' + st.stroke.color;
            el.style.paintOrder = 'stroke fill';
        } else {
            el.style.webkitTextStroke = '';
            el.style.paintOrder = '';
        }
    }

    function keyOf(el) {
        return el.getAttribute('data-lp');
    }

    function markDirty(el) {
        dirty[keyOf(el)] = true;
        refreshCounter();
    }

    // --- панель управления -------------------------------------------------

    function buildPanel() {
        panel = document.createElement('div');
        panel.className = 'lbg-ed';
        panel.innerHTML = [
            '<div class="lbg-ed__hint" id="lbg-ed-hint">Кликните по тексту, чтобы изменить его</div>',
            '<div class="lbg-ed__tools" id="lbg-ed-tools">',
            '  <button type="button" data-act="smaller" title="Мельче">A−</button>',
            '  <span class="lbg-ed__size" id="lbg-ed-size">100%</span>',
            '  <button type="button" data-act="bigger" title="Крупнее">A+</button>',
            '  <button type="button" data-act="bold" title="Жирный"><b>Ж</b></button>',
            '  <label class="lbg-ed__color" title="Цвет текста">',
            '    <span>Цвет</span><input type="color" data-act="color" value="#ffffff">',
            '  </label>',
            '  <button type="button" data-act="stroke" title="Обводка">Обводка</button>',
            '  <label class="lbg-ed__color" title="Цвет обводки">',
            '    <input type="color" data-act="stroke-color" value="#000000">',
            '  </label>',
            '  <button type="button" data-act="clear" title="Вернуть исходный текст и оформление">Сброс</button>',
            '</div>',
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
        var n = Object.keys(dirty).length;
        var el = document.getElementById('lbg-ed-counter');
        if (el) el.textContent = n ? 'изменено: ' + n : '';
        var save = panel && panel.querySelector('.lbg-ed__save');
        if (save) save.disabled = !n;
    }

    function refreshTools() {
        var tools = document.getElementById('lbg-ed-tools');
        var hint = document.getElementById('lbg-ed-hint');
        if (!tools) return;
        tools.style.display = active ? 'flex' : 'none';
        if (hint) hint.style.display = active ? 'none' : 'block';
        if (!active) return;

        var st = state[keyOf(active)].style;
        var size = document.getElementById('lbg-ed-size');
        if (size) size.textContent = Math.round((st.size || 1) * 100) + '%';

        var bold = tools.querySelector('[data-act="bold"]');
        if (bold) bold.classList.toggle('is-on', !!st.bold);

        var stroke = tools.querySelector('[data-act="stroke"]');
        if (stroke) stroke.classList.toggle('is-on', !!st.stroke);

        var color = tools.querySelector('[data-act="color"]');
        if (color && st.color) color.value = st.color;

        var sColor = tools.querySelector('[data-act="stroke-color"]');
        if (sColor && st.stroke) sColor.value = st.stroke.color;
    }

    function onPanelClick(e) {
        var btn = e.target.closest('[data-act]');
        if (!btn || btn.tagName === 'INPUT') return;
        var act = btn.getAttribute('data-act');

        if (act === 'save') return save();
        if (act === 'cancel') return cancel();
        if (!active) return;

        var st = state[keyOf(active)].style;

        if (act === 'smaller' || act === 'bigger') {
            var next = (st.size || 1) + (act === 'bigger' ? SIZE_STEP : -SIZE_STEP);
            next = Math.min(SIZE_MAX, Math.max(SIZE_MIN, Math.round(next * 100) / 100));
            if (Math.abs(next - 1) < 0.001) delete st.size;
            else st.size = next;
        } else if (act === 'bold') {
            if (st.bold) delete st.bold;
            else st.bold = true;
        } else if (act === 'stroke') {
            if (st.stroke) {
                delete st.stroke;
            } else {
                var sc = panel.querySelector('[data-act="stroke-color"]');
                st.stroke = { width: 1, color: (sc && sc.value) || '#000000' };
            }
        } else if (act === 'clear') {
            var k = keyOf(active);
            active.textContent = defaultText(k);
            state[k].text = defaultText(k);
            state[k].style = {};
            st = state[k].style;
        }

        applyStyle(active, st);
        markDirty(active);
        refreshTools();
    }

    function onPanelInput(e) {
        var input = e.target.closest('[data-act]');
        if (!input || !active) return;
        var act = input.getAttribute('data-act');
        var st = state[keyOf(active)].style;

        if (act === 'color') {
            st.color = input.value;
        } else if (act === 'stroke-color') {
            st.stroke = { width: (st.stroke && st.stroke.width) || 1, color: input.value };
        } else {
            return;
        }
        applyStyle(active, st);
        markDirty(active);
        refreshTools();
    }

    // --- выбор и правка узлов ---------------------------------------------

    function select(el) {
        if (active === el) return;
        if (active) active.classList.remove('is-lp-active');
        active = el;
        if (active) active.classList.add('is-lp-active');
        refreshTools();
    }

    function onNodeClick(e) {
        if (!editing) return;
        // ссылки внутри режима редактирования никуда не ведут
        if (this.tagName === 'A') e.preventDefault();
        e.stopPropagation();
        select(this);
    }

    function onNodeInput() {
        var key = keyOf(this);
        state[key].text = this.textContent.trim();
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

    function setEditing(on) {
        editing = on;
        document.body.classList.toggle('lp-editing', on);
        toggle.classList.toggle('is-on', on);
        toggle.setAttribute('aria-pressed', on ? 'true' : 'false');

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
            refreshTools();
            refreshCounter();
        } else if (panel) {
            panel.classList.remove('is-open');
            select(null);
        }
    }

    // --- сохранение --------------------------------------------------------

    function save() {
        var keys = Object.keys(dirty);
        if (!keys.length) return;

        var items = keys.map(function (key) {
            var st = state[key].style;
            // пустой текст без стилей сервер понимает как «вернуть шаблонный»
            // и удаляет строку — именно это нужно после «Сброса»
            if (isPristine(key)) return { key: key, text: '', style: null };
            return {
                key: key,
                text: state[key].text,
                style: Object.keys(st).length ? st : null
            };
        });

        var btn = panel.querySelector('.lbg-ed__save');
        btn.disabled = true;
        btn.textContent = 'Сохраняю…';

        fetch('/web/landing/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ items: items })
        }).then(function (r) {
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
        }).then(function () {
            dirty = {};
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
        if (Object.keys(dirty).length &&
            !confirm('Несохранённые правки пропадут. Продолжить?')) return;
        location.reload();
    }

    // --- запуск ------------------------------------------------------------

    toggle.addEventListener('click', function (e) {
        e.preventDefault();
        setEditing(!editing);
    });

    document.addEventListener('click', function (e) {
        if (!editing) return;
        if (e.target.closest('[data-lp]') || e.target.closest('.lbg-ed')) return;
        select(null);
    });

    window.addEventListener('beforeunload', function (e) {
        if (!editing || !Object.keys(dirty).length) return;
        e.preventDefault();
        e.returnValue = '';
    });
})();
