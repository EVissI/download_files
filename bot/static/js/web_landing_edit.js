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

    // Исходные адреса ссылок — для тех, что уже переопределены в БД.
    var hrefDefaults = {};
    try {
        var rawHrefs = document.getElementById('lp-href-defaults');
        if (rawHrefs) hrefDefaults = JSON.parse(rawHrefs.textContent) || {};
    } catch (e) {
        hrefDefaults = {};
    }

    nodes.forEach(function (el) {
        var key = el.getAttribute('data-lp');
        var text = el.textContent.trim();
        state[key] = { text: text, style: parseStyle(el) };
        if (!(key in defaults)) defaults[key] = text;
        if (el.tagName === 'A') {
            // getAttribute, а не .href: браузер достраивает адрес до полного
            var href = el.getAttribute('href') || '';
            state[key].href = href;
            if (!(key in hrefDefaults)) hrefDefaults[key] = href;
        }
    });

    function defaultHref(key) {
        return hrefDefaults[key] != null ? hrefDefaults[key] : '';
    }

    function isLink(el) {
        return !!el && el.tagName === 'A';
    }

    function defaultText(key) {
        return defaults[key] != null ? defaults[key] : '';
    }

    function isPristine(key) {
        var st = state[key];
        if (st.href !== undefined && st.href !== defaultHref(key)) return false;
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

    // Цвет зависит от темы, поэтому задаётся правилами, а не инлайном.
    // Свой блок идёт после серверного, поэтому перебивает его при равной
    // специфичности — так превью совпадает с тем, что будет после сохранения.
    function renderColors() {
        var el = document.getElementById('lp-colors-live');
        if (!el) {
            el = document.createElement('style');
            el.id = 'lp-colors-live';
            document.head.appendChild(el);
        }
        var css = '';
        Object.keys(state).forEach(function (key) {
            var color = state[key].style.color;
            if (!color) return;
            if (color.dark) css += '.lbg [data-lp="' + key + '"]{color:' + color.dark + '}';
            if (color.light) {
                css += 'html[data-theme="light"] .lbg [data-lp="' + key + '"]{color:'
                    + color.light + '}';
            }
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
            '  <label class="lbg-ed__color" title="Цвет текста в тёмной теме">',
            '    <span>Цвет тёмн.</span><input type="color" data-act="color-dark" value="#eeeeee">',
            '  </label>',
            '  <label class="lbg-ed__color" title="Цвет текста в светлой теме">',
            '    <span>светл.</span><input type="color" data-act="color-light" value="#1c1d21">',
            '  </label>',
            '  <button type="button" data-act="stroke" title="Обводка">Обводка</button>',
            '  <label class="lbg-ed__color" title="Цвет обводки">',
            '    <input type="color" data-act="stroke-color" value="#000000">',
            '  </label>',
            '  <button type="button" data-act="clear" title="Вернуть исходный текст и оформление">Сброс</button>',
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
        refreshHrefBox();
        if (!active) return;

        var st = state[keyOf(active)].style;
        var size = document.getElementById('lbg-ed-size');
        if (size) size.textContent = Math.round((st.size || 1) * 100) + '%';

        var bold = tools.querySelector('[data-act="bold"]');
        if (bold) bold.classList.toggle('is-on', !!st.bold);

        var stroke = tools.querySelector('[data-act="stroke"]');
        if (stroke) stroke.classList.toggle('is-on', !!st.stroke);

        var dark = tools.querySelector('[data-act="color-dark"]');
        if (dark && st.color && st.color.dark) dark.value = st.color.dark;
        var light = tools.querySelector('[data-act="color-light"]');
        if (light && st.color && st.color.light) light.value = st.color.light;

        var sColor = tools.querySelector('[data-act="stroke-color"]');
        if (sColor && st.stroke) sColor.value = st.stroke.color;
    }

    function refreshHrefBox() {
        var box = document.getElementById('lbg-ed-href-box');
        var input = document.getElementById('lbg-ed-href');
        if (!box || !input) return;
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
            if (state[k].href !== undefined) {
                state[k].href = defaultHref(k);
                active.setAttribute('href', state[k].href);
                refreshHrefBox();
            }
            renderColors();
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

        if (act === 'href') {
            if (!isLink(active)) return;
            var key = keyOf(active);
            state[key].href = input.value.trim();
            active.setAttribute('href', state[key].href || defaultHref(key));
            markDirty(active);
            return;
        }
        if (act === 'color-dark' || act === 'color-light') {
            st.color = st.color || {};
            st.color[act === 'color-dark' ? 'dark' : 'light'] = input.value;
            renderColors();
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

        blockAddBtns.forEach(function (el) {
            if (on) el.addEventListener('click', onBlockAdd);
            else el.removeEventListener('click', onBlockAdd);
        });
        blockDelBtns.forEach(function (el) {
            if (on) el.addEventListener('click', onBlockDel);
            else el.removeEventListener('click', onBlockDel);
        });

        imageSlots.forEach(function (el) {
            el.classList.toggle('is-lp-img', on);
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
            refreshTools();
            refreshCounter();
        } else if (panel) {
            panel.classList.remove('is-open');
            select(null);
        }
    }

    // --- картинки ----------------------------------------------------------

    // Картинки меняются сразу по выбору файла, а не по кнопке «Сохранить»:
    // это отдельная операция с загрузкой на сервер, копить её незачем.
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
            if (slot.tagName === 'IMG') {
                slot.src = data.url;
            } else {
                // заглушка без картинки — показываем загруженную и перезагружаем,
                // чтобы разметка стала обычным боксом со скриншотом
                location.reload();
            }
        }).catch(function (err) {
            slot.classList.remove('is-lp-uploading');
            alert('Не удалось загрузить картинку: ' + err.message);
        });
    }

    // --- блоки секций ------------------------------------------------------

    // Состав секций меняется сразу на сервере: это правка структуры, копить
    // её вместе с текстами нельзя — новый блок должен прийти уже отрисованным.
    var blockAddBtns = [].slice.call(document.querySelectorAll('[data-lp-block-add]'));
    var blockDelBtns = [].slice.call(document.querySelectorAll('[data-lp-block-del]'));

    function blockApi(payload) {
        return fetch('/web/landing/api/blocks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify(payload)
        }).then(function (r) {
            return r.json().then(function (data) {
                if (!r.ok) throw new Error(data.detail || ('HTTP ' + r.status));
                return data;
            });
        });
    }

    function sectionOf(el) {
        var holder = el.closest('[data-lp-section]');
        return holder ? holder.getAttribute('data-lp-section') : '';
    }

    function onBlockAdd(e) {
        e.preventDefault();
        e.stopPropagation();
        if (!editing) return;
        var btn = this;
        btn.disabled = true;
        blockApi({ section: btn.getAttribute('data-lp-block-add'), action: 'add' })
            .then(function () { location.reload(); })
            .catch(function (err) {
                btn.disabled = false;
                alert('Не удалось добавить блок: ' + err.message);
            });
    }

    function onBlockDel(e) {
        e.preventDefault();
        e.stopPropagation();
        if (!editing) return;
        var btn = this;
        if (!confirm('Убрать блок со страницы?')) return;
        btn.disabled = true;
        blockApi({
            section: sectionOf(btn),
            action: 'remove',
            block_id: btn.getAttribute('data-lp-block-del')
        }).then(function () { location.reload(); })
            .catch(function (err) {
                btn.disabled = false;
                alert('Не удалось убрать блок: ' + err.message);
            });
    }

    // --- сохранение --------------------------------------------------------

    function save() {
        var keys = Object.keys(dirty);
        if (!keys.length) return;

        var items = keys.map(function (key) {
            var st = state[key].style;
            var item;
            // пустой текст без стилей сервер понимает как «вернуть шаблонный»
            // и удаляет строку — именно это нужно после «Сброса»
            if (isPristine(key)) {
                item = { key: key, text: '', style: null };
            } else {
                item = {
                    key: key,
                    text: state[key].text,
                    style: Object.keys(st).length ? st : null
                };
            }
            if (state[key].href !== undefined) {
                // адрес, совпавший с шаблонным, сервер удалит из БД
                item.href = state[key].href === defaultHref(key) ? '' : state[key].href;
            }
            return item;
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
        if (e.target.closest('[data-lp-block-add], [data-lp-block-del]')) return;
        select(null);
    });

    window.addEventListener('beforeunload', function (e) {
        if (!editing || !Object.keys(dirty).length) return;
        e.preventDefault();
        e.returnValue = '';
    });
})();
