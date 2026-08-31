function pokazAsset(path) {
    var v = window.__STATIC_ASSET_V || '';
    if (!v) return path;
    return path + (path.indexOf('?') >= 0 ? '&' : '?') + 't=' + encodeURIComponent(v);
}

function isWebStandalonePokaz() {
    const meta = document.querySelector('meta[name="web-standalone-mode"]');
    return !!(meta && meta.getAttribute('content') === '1');
}

function isPokazAdminFromMeta() {
    const meta = document.querySelector('meta[name="pokaz-is-admin"]');
    return !!(meta && meta.getAttribute('content') === '1');
}

function applyPokazAdminUi() {
    window.pokazIsAdmin = true;
    const btn = document.getElementById('openPokazCardEditorBtn');
    if (btn) btn.style.display = 'inline-block';
    const pipBtn = document.getElementById('openPokazPipCountCardEditorBtn');
    if (pipBtn) pipBtn.style.display = 'inline-block';
    const screenshotAdmin = document.getElementById('pokazScreenshotAdminContainer');
    if (screenshotAdmin) screenshotAdmin.style.display = 'block';
    const fontScaleSelect = document.getElementById('pokazScreenshotFontScaleSelect');
    if (fontScaleSelect && typeof pokazScreenshotFontScale !== 'undefined') {
        fontScaleSelect.value = String(pokazScreenshotFontScale);
    }
}

function ensureHtml2Canvas() {
    if (typeof window.html2canvas === 'function') {
        return Promise.resolve(window.html2canvas);
    }
    if (window.__html2canvasLoading) return window.__html2canvasLoading;
    window.__html2canvasLoading = new Promise(function (resolve, reject) {
        const s = document.createElement('script');
        s.src = pokazAsset('/static/js/vendor/html2canvas.min.js');
        s.async = true;
        s.onload = function () {
            if (typeof window.html2canvas === 'function') resolve(window.html2canvas);
            else reject(new Error('html2canvas missing'));
        };
        s.onerror = function () { reject(new Error('html2canvas load failed')); };
        document.head.appendChild(s);
    });
    return window.__html2canvasLoading;
}

function pokazHtml2Canvas(options) {
    options = Object.assign({}, options || {});
    const userIgnore = options.ignoreElements;
    options.ignoreElements = function (el) {
        if (el && el.classList && (
            el.classList.contains('web-standalone-back') ||
            el.classList.contains('web-cabinet-header')
        )) {
            return true;
        }
        return typeof userIgnore === 'function' ? !!userIgnore(el) : false;
    };
    return ensureHtml2Canvas().then(function (html2canvas) {
        return html2canvas(document.body, options);
    });
}

function ensureContentEditorCss() {
    if (document.querySelector('link[data-content-editor-css]')) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = pokazAsset('/static/css/content_editor.css');
    link.setAttribute('data-content-editor-css', '1');
    document.head.appendChild(link);
}

async function ensureContentEditor() {
    if (window.contentEditor) return window.contentEditor;
    if (window.__pokazContentEditorPromise) return window.__pokazContentEditorPromise;
    window.__pokazContentEditorPromise = (async function () {
        ensureContentEditorCss();
        const q = (window.__STATIC_ASSET_V || '')
            ? ('?t=' + encodeURIComponent(window.__STATIC_ASSET_V))
            : '';
        const [storageBridge, core] = await Promise.all([
            import('/static/js/content-editor/infra/storage_telegram_bridge.js' + q),
            import('/static/js/content-editor/core/content_editor_core.js' + q),
        ]);
        if (storageBridge.shouldClearEditorStorageOnBoot && storageBridge.shouldClearEditorStorageOnBoot()) {
            storageBridge.clearContentEditorLocalStorage();
            storageBridge.clearContentEditorIndexedDB();
        }
        const editor = await core.createContentEditorCore();
        window.contentEditor = editor;
        return editor;
    })();
    try {
        return await window.__pokazContentEditorPromise;
    } catch (e) {
        window.__pokazContentEditorPromise = null;
        throw e;
    }
}


document.addEventListener('DOMContentLoaded', function () {
    const i18nEl = document.getElementById('pokaz-i18n');
    if (i18nEl && i18nEl.textContent) {
        try {
            const i18n = JSON.parse(i18nEl.textContent);
            document.querySelectorAll('[data-i18n]').forEach(el => {
                const k = el.getAttribute('data-i18n');
                if (i18n[k]) el.textContent = i18n[k];
            });
            document.querySelectorAll('[data-i18n-title]').forEach(el => {
                const k = el.getAttribute('data-i18n-title');
                if (i18n[k]) el.setAttribute('title', i18n[k]);
            });
            document.querySelectorAll('[data-i18n-aria-label]').forEach(el => {
                const k = el.getAttribute('data-i18n-aria-label');
                if (i18n[k]) el.setAttribute('aria-label', i18n[k]);
            });
            document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
                const k = el.getAttribute('data-i18n-placeholder');
                if (i18n[k]) el.setAttribute('placeholder', i18n[k]);
            });

            window.POKAZ_I18N = i18n;
            const yesText = i18n.yes || 'Да';
            const noText = i18n.no || 'Нет';
            document.querySelectorAll('.toggle-btn').forEach(btn => {
                const el = document.getElementById(btn.dataset.target);
                if (el) btn.textContent = el.value === '1' ? yesText : noText;
            });
            window.POKAZ_YES = yesText;
            window.POKAZ_NO = noText;
        } catch (e) { console.warn('Pokaz i18n parse error:', e); }
    }

    const langSwitcher = document.getElementById('lang-switcher');
    if (langSwitcher) {
        langSwitcher.addEventListener('click', function (e) {
            e.preventDefault();
            const params = new URLSearchParams(window.location.search);
            const currentLang = params.get('lang') || 'ru';
            params.set('lang', currentLang === 'ru' ? 'en' : 'ru');
            window.location.search = params.toString();
        });
    }

    const screenshotBtn = document.getElementById('screenshotBtn');
    const screenSaveBtn = document.getElementById('screenSaveBtn');
    const screenUploadBtn = document.getElementById('screenUploadBtn');

    if (screenshotBtn) {
        screenshotBtn.style.backgroundImage = "url('" + pokazAsset('/static/Screen.webp') + "')";
    }
    if (screenSaveBtn) {
        screenSaveBtn.style.backgroundImage = "url('" + pokazAsset('/static/ScreenSave.webp') + "')";
    }
    if (screenUploadBtn) {
        screenUploadBtn.style.backgroundImage = "url('" + pokazAsset('/static/ScreenUpload.webp') + "')";
    }
    if (isWebStandalonePokaz()) {
        if (screenshotBtn) screenshotBtn.title = 'Скачать скриншот';
        if (screenSaveBtn) screenSaveBtn.title = 'Добавить скриншот в архив';
        if (screenUploadBtn) screenUploadBtn.title = 'Скачать архив со скриншотами';
    }

    const hintsTableToggle = document.getElementById('hintsTableToggle');
    const hintsTableContainer = document.getElementById('hintsTableContainer');
    if (hintsTableToggle && hintsTableContainer) {
        hintsTableToggle.addEventListener('click', function () {
            hintsTableContainer.classList.toggle('collapsed');
            const isCollapsed = hintsTableContainer.classList.contains('collapsed');
            const i18n = window.POKAZ_I18N || {};
            hintsTableToggle.setAttribute('aria-label', isCollapsed ? (i18n.expand_table || 'Развернуть таблицу') : (i18n.collapse_table || 'Свернуть таблицу'));
            if (typeof updateGameTypeButtonMode === 'function') updateGameTypeButtonMode();
        });
    }

    const hidePointDropdownsCheckbox = document.getElementById('hidePointDropdownsCheckbox');
    const boardWrapper = document.querySelector('.board-wrapper');
    const selectorsWrapper = document.querySelector('.selectors-wrapper');
    if (hidePointDropdownsCheckbox && boardWrapper && selectorsWrapper) {
        function updateBoardWrapperMargin() {
            if (hidePointDropdownsCheckbox.checked) {
                boardWrapper.style.marginTop = '0';
                selectorsWrapper.style.paddingTop = '0';
            } else {
                boardWrapper.style.marginTop = '';
                selectorsWrapper.style.paddingTop = '';
            }
        }
        hidePointDropdownsCheckbox.addEventListener('change', updateBoardWrapperMargin);
        updateBoardWrapperMargin();
    }
});


    document.addEventListener('DOMContentLoaded', function () {
        try {
            if (window.Telegram && window.Telegram.WebApp) {
                const tg = window.Telegram.WebApp;
                const allowFullscreen = (document.querySelector('meta[name="webapp-fullscreen-enabled"]') || {}).content === '1';
                tg.ready();
                tg.expand();
                try {
                    const canFullscreen =
                        allowFullscreen &&
                        typeof tg.requestFullscreen === 'function' &&
                        (typeof tg.isVersionAtLeast !== 'function' || tg.isVersionAtLeast('8.0'));
                    if (canFullscreen && !tg.isFullscreen) {
                        tg.requestFullscreen();
                    }
                } catch (fsErr) {
                    console.warn('requestFullscreen(pokaz) failed:', fsErr);
                }
            }
        } catch (e) {
            console.warn('Telegram WebApp init failed:', e);
        }

        let positions = {
            first: {},
            second: {}
        };

        /** Снимок позиций и хода в момент нажатия show-button (все позиции шашек + чей ход) */
        let showButtonSnapshot = null;

        /** История сделанных ходов */
        let moveHistory = [];

        /** Текущий индекс в истории (0 = до первого хода, length = текущая позиция) */
        let historyIndex = 0;

        let currentGameType = 'манигейм';

        /** Создаёт копию текущих позиций */
        function snapshotPositions() {
            return {
                first: { ...positions.first },
                second: { ...positions.second }
            };
        }

        /** Меняет местами белые и чёрные шашки (включая бар) */
        function swapCheckerColors() {
            const tempFirst = JSON.parse(JSON.stringify(positions.first));
            const tempSecond = JSON.parse(JSON.stringify(positions.second));
            positions.first = tempSecond;
            positions.second = tempFirst;
        }

        /** Меняет местами цвет хода и владельца куба */
        function swapTurnAndCubeColors() {
            const turnSelect = document.getElementById('turn-select');
            if (turnSelect && turnSelect.value) {
                turnSelect.value = turnSelect.value === 'white' ? 'black' : 'white';
                updateTurnSelect();
            }
            const cubeOwnerSelect = document.getElementById('cube-owner-select');
            if (cubeOwnerSelect && cubeOwnerSelect.value) {
                cubeOwnerSelect.value = cubeOwnerSelect.value === 'white' ? 'black' : 'white';
                updateCubeOwnerSelect();
            }
        }

        /** Записывает ход в историю */
        function recordMove(entry) {
            moveHistory.push(entry);
        }

        /** Очищает историю ходов */
        function clearMoveHistory() {
            moveHistory = [];
            historyIndex = 0;
        }

        /**
         * Переводит строку подсказки по кубу (например "No double, take (33.3%)") на текущий язык.
         * Части строки разделяются запятой, текст в скобках сохраняется без перевода.
         */
        function translateCubeAction(str) {
            if (!str || typeof str !== 'string') return str;
            const i18n = window.POKAZ_I18N || {};
            const translations = {
                'no double': i18n.cube_no_double || 'не удваивать',
                'double': i18n.cube_double || 'удвоить',
                'take': i18n.cube_take || 'принять',
                'pass': i18n.cube_pass || 'сдаться'
            };
            const result = str.split(',').map(part => {
                const match = part.match(/^([^(]*)(\(.*\))?$/);
                const textPart = (match ? match[1] : part).trim();
                const parenPart = match && match[2] ? match[2] : '';
                const key = textPart.toLowerCase();
                const translated = translations[key] !== undefined ? translations[key] : textPart.toLowerCase();
                return translated + parenPart;
            }).join(', ');
            return result.charAt(0).toUpperCase() + result.slice(1);
        }

        /**
         * Строит HTML таблицы подсказок из данных API.
         * @param {Object} hintsData - hints: [...] при успехе или error: string при ошибке
         * @returns Object с полями html (string) и firstHint (Object|null)
         */
        function buildHintsTableFromData(hintsData, selectedHintIndex) {
            if (!hintsData) return { html: '', firstHint: null };
            const i18n = window.POKAZ_I18N || {};
            if (hintsData.error) {
                return { html: '<div class="error">' + hintsData.error + '</div>', firstHint: null };
            }
            const hints = hintsData.hints || [];
            if (hints.length === 0) {
                return { html: '<div class="error">' + (i18n.impossible_move || 'невозможный ход') + '</div>', firstHint: null };
            }
            const firstHint = hints[0];
            let tableHtml = '';
            if (firstHint.type === 'move') {
                const firstEq = hints.length > 0 ? hints[0].eq : null;
                tableHtml = '<table><tr><th>' + (i18n.table_header_move || 'Ход') + '</th><th>%</th><th>%</th><th>' + (i18n.table_header_equity || 'Эквити') + '</th><th><button class="eye-button" type="button" id="restore-position-btn" title="' + (i18n.restore_position || 'Восстановить сохранённую позицию') + '"><i class="fa fa-reply"></i></button></th></tr>';
                hints.forEach((hint, index) => {
                    if (hint.probs && hint.probs.length >= 2) {
                        const prob1 = hint.probs[0] ? (hint.probs[0] * 100).toFixed(1) : '-';
                        const prob2 = hint.probs[1] ? (hint.probs[1] * 100).toFixed(1) : '-';
                        const eq = hint.eq ? hint.eq.toFixed(3) : '-';
                        const displayEq = (firstEq !== null && hint.eq !== undefined && index > 0)
                            ? '(' + (hint.eq - firstEq).toFixed(3) + ')'
                            : eq;
                        const move = hint.move || '-';
                        let rowClass = '';
                        if (selectedHintIndex === index) {
                            rowClass = 'hint-row-selected';
                        } else if (index === 0 && selectedHintIndex === undefined) {
                            rowClass = 'hint-best';
                        }
                        const rowClassAttr = rowClass ? ` class="${rowClass}"` : '';
                        tableHtml += `<tr data-hint-index="${index}"${rowClassAttr}><td>${move}</td><td>${prob1}</td><td>${prob2}</td><td>${displayEq}</td><td><button class="eye-button" type="button"><i class="fa fa-eye"></i></button></td></tr>`;
                    }
                });
                tableHtml += '</table>';
            } else if (firstHint.type === 'cube_hint') {
                tableHtml = '<table class="cube-hints-table"><tr><th>' + (i18n.table_header_action || 'Действие') + '</th><th>' + (i18n.table_header_equity || 'Эквити') + '</th><th><div class="cube-hints-header-spacer"></div></th></tr>';
                (firstHint.cubeful_equities || []).forEach((hint, index) => {
                    const eq = hint.eq ? hint.eq.toFixed(3) : '-';
                    let displayAction = hint.action_1 || '';
                    if (hint.action_2) displayAction += `, ${hint.action_2}`;
                    const rawAction1 = (hint.action_1 || '').toLowerCase().trim();
                    const rawAction2 = (hint.action_2 || '').toLowerCase().trim();
                    displayAction = translateCubeAction(displayAction);
                    const rowClass = index === 0 ? 'hint-best' : '';
                    const rowClassAttr = rowClass ? ` class="${rowClass}"` : '';
                    let actionCell = '';
                    if (rawAction1 === 'no double') {
                        actionCell = `<button class="eye-button cube-eye-btn" type="button" data-cube-action="no-double" title="${i18n.random_dice || 'Случайные кубики'}"><i class="fa fa-eye"></i></button>`;
                    } else if (rawAction1 === 'double' && rawAction2 === 'take') {
                        actionCell = `<button class="eye-button cube-eye-btn" type="button" data-cube-action="double-take" title="${i18n.next_cube || 'Следующий куб'}"><i class="fa fa-eye"></i></button>`;
                    } else {
                        actionCell = '';
                    }
                    tableHtml += `<tr${rowClassAttr} data-action-1="${rawAction1}" data-action-2="${rawAction2}"><td>${displayAction}</td><td>${eq}</td><td>${actionCell}</td></tr>`;
                });
                if (firstHint.prefer_action) {
                    let preferText = translateCubeAction(firstHint.prefer_action);
                    preferText = preferText.replace(/([^\s])\(/g, '$1 (');
                    tableHtml += `<tr><td colspan="3" style="text-align: center; font-weight: bold;">${preferText}</td></tr>`;
                }
                tableHtml += '</table>';
            } else {
                return { html: '<div class="error">' + (i18n.unknown_hint_type || 'Unknown hint type') + '</div>', firstHint: null };
            }
            return { html: tableHtml, firstHint };
        }

        /** Флаг: куб уже меняли в текущей таблице (можно только один раз) */
        let cubeValueChangedInCurrentTable = false;
        /** Состояние до «Удвоить, принять» — для отмены при последующем «Не удваивать» */
        let stateBeforeDoubleTake = null;

        /** Куб на максимуме (из селектора макс куба) — блокируем Удвоить/Не удваивать */
        function isCubeAtMax() {
            const maxCubeSelect = (typeof currentGameType !== 'undefined' && currentGameType === 'матч') ?
                document.getElementById('max-cube-select') :
                document.getElementById('max-cube-select-m');
            if (!maxCubeSelect) return false;
            const maxCubeValue = parseInt(maxCubeSelect.options[maxCubeSelect.selectedIndex]?.text || '64', 10);
            const cubeShown = parseInt(document.getElementById('cube-shown-select')?.value || '0', 10);
            const cubeValue = parseInt(document.getElementById('cube-value-select')?.value || '0', 10);
            const cubeDisplayValue = cubeShown !== 0 ? cubeShown : cubeValue;
            return cubeDisplayValue > 0 && cubeDisplayValue >= maxCubeValue;
        }

        /** Привязывает обработчики к глазикам в таблице куба */
        function attachCubeTableEyeButtons(hintsTable) {
            if (!hintsTable) return;
            cubeValueChangedInCurrentTable = false;
            stateBeforeDoubleTake = null;
            const cubeAtMax = isCubeAtMax();
            const cubeEyeBtns = hintsTable.querySelectorAll('.cube-hints-table .cube-eye-btn');
            cubeEyeBtns.forEach((button) => {
                if (cubeAtMax) button.disabled = true;
                const action = button.getAttribute('data-cube-action');
                button.addEventListener('click', () => {
                    if (action === 'no-double') {
                        if (cubeValueChangedInCurrentTable && stateBeforeDoubleTake) {
                            const cubeValueSelect = document.getElementById('cube-value-select');
                            const cubeShownSelect = document.getElementById('cube-shown-select');
                            const cubeOwnerSelect = document.getElementById('cube-owner-select');
                            const dice1Select = document.getElementById('dice1-select');
                            const dice2Select = document.getElementById('dice2-select');
                            if (cubeValueSelect) cubeValueSelect.value = stateBeforeDoubleTake.cubeValue;
                            if (cubeShownSelect && stateBeforeDoubleTake.cubeShown !== undefined) cubeShownSelect.value = stateBeforeDoubleTake.cubeShown;
                            if (cubeOwnerSelect) cubeOwnerSelect.value = stateBeforeDoubleTake.cubeOwner;
                            if (dice1Select) dice1Select.value = stateBeforeDoubleTake.dice1;
                            if (dice2Select) dice2Select.value = stateBeforeDoubleTake.dice2;
                            cubeValueChangedInCurrentTable = false;
                            stateBeforeDoubleTake = null;
                            hintsTable.querySelectorAll('.cube-eye-btn[data-cube-action="double-take"]').forEach(b => b.disabled = false);
                            if (typeof updateCubeSelectorDisplay === 'function') {
                                updateCubeSelectorDisplay('value');
                                updateCubeSelectorDisplay('shown');
                            }
                            if (typeof updateCubeOwnerSelect === 'function') updateCubeOwnerSelect();
                            if (typeof updateDiceSelectorDisplay === 'function') {
                                updateDiceSelectorDisplay(1);
                                updateDiceSelectorDisplay(2);
                            }
                        }
                        const dice1 = Math.floor(Math.random() * 6) + 1;
                        const dice2 = Math.floor(Math.random() * 6) + 1;
                        const dice1Select = document.getElementById('dice1-select');
                        const dice2Select = document.getElementById('dice2-select');
                        if (dice1Select) dice1Select.value = dice1.toString();
                        if (dice2Select) dice2Select.value = dice2.toString();
                        if (typeof updateDiceSelectorDisplay === 'function') {
                            updateDiceSelectorDisplay(1);
                            updateDiceSelectorDisplay(2);
                        }
                        if (typeof drawBoard === 'function') drawBoard();
                    } else if (action === 'double-take') {
                        if (cubeValueChangedInCurrentTable) return;
                        const CUBE_VALUES = [2, 4, 8, 16, 32, 64];
                        const cubeValueSelect = document.getElementById('cube-value-select');
                        const cubeShownSelect = document.getElementById('cube-shown-select');
                        const cubeOwnerSelect = document.getElementById('cube-owner-select');
                        const turnSelect = document.getElementById('turn-select');
                        const dice1Select = document.getElementById('dice1-select');
                        const dice2Select = document.getElementById('dice2-select');
                        if (!cubeValueSelect) return;
                        stateBeforeDoubleTake = {
                            cubeValue: cubeValueSelect.value,
                            cubeShown: cubeShownSelect ? cubeShownSelect.value : '0',
                            cubeOwner: cubeOwnerSelect ? cubeOwnerSelect.value : 'white',
                            dice1: dice1Select ? dice1Select.value : '0',
                            dice2: dice2Select ? dice2Select.value : '0'
                        };
                        const cubeShown = parseInt(cubeShownSelect?.value || '0', 10);
                        const cubeValue = parseInt(cubeValueSelect.value, 10) || 0;
                        const displayVal = cubeShown !== 0 ? cubeShown : cubeValue;
                        const idx = CUBE_VALUES.indexOf(displayVal);
                        const nextDisplay = idx >= 0 && idx < CUBE_VALUES.length - 1 ? CUBE_VALUES[idx + 1] : (displayVal === 0 ? 2 : displayVal);
                        if (cubeShown !== 0) {
                            cubeShownSelect.value = nextDisplay.toString();
                            cubeValueSelect.value = getPrevCubeValue(nextDisplay).toString();
                            if (typeof updateCubeSelectorDisplay === 'function') updateCubeSelectorDisplay('shown');
                        } else {
                            cubeValueSelect.value = nextDisplay.toString();
                        }
                        if (dice1Select) dice1Select.value = '0';
                        if (dice2Select) dice2Select.value = '0';
                        const turn = turnSelect ? turnSelect.value : 'white';
                        const oppositeOwner = turn === 'white' ? 'black' : 'white';
                        if (cubeOwnerSelect) cubeOwnerSelect.value = oppositeOwner;
                        if (typeof updateDiceSelectorDisplay === 'function') {
                            updateDiceSelectorDisplay(1);
                            updateDiceSelectorDisplay(2);
                        }
                        cubeValueChangedInCurrentTable = true;
                        hintsTable.querySelectorAll('.cube-eye-btn[data-cube-action="double-take"]').forEach(b => b.disabled = true);
                        if (typeof updateCubeSelectorDisplay === 'function') updateCubeSelectorDisplay('value');
                        if (typeof updateCubeOwnerSelect === 'function') updateCubeOwnerSelect();
                        if (typeof drawBoard === 'function') drawBoard();
                    }
                });
            });
        }

        /** Привязывает обработчики к кнопкам eye-button в таблице подсказок */
        function attachHintsTableEyeButtons(hintsTable, snapshot, entry) {
            if (!hintsTable || !snapshot) return;
            const eyeButtons = hintsTable.querySelectorAll('.eye-button');
            eyeButtons.forEach((button) => {
                if (button.closest('.cube-hints-table')) return;
                if (button.id === 'restore-position-btn') {
                    button.addEventListener('click', () => {
                        if (!showButtonSnapshot || !showButtonSnapshot.positions) return;
                        positions.first = { ...showButtonSnapshot.positions.first };
                        positions.second = { ...showButtonSnapshot.positions.second };
                        const whiteBar = positions.first.bar || 0;
                        const blackBar = positions.second.bar || 0;
                        const whiteBarSelect = document.getElementById('white-bar-select');
                        const blackBarSelect = document.getElementById('black-bar-select');
                        if (whiteBarSelect) whiteBarSelect.value = whiteBar.toString();
                        if (blackBarSelect) blackBarSelect.value = blackBar.toString();
                        if (showButtonSnapshot.turn) {
                            const turnSelect = document.getElementById('turn-select');
                            if (turnSelect) {
                                turnSelect.value = showButtonSnapshot.turn;
                                updateTurnSelect();
                            }
                        }
                        if (moveHistory.length > 0 && moveHistory[moveHistory.length - 1].dice) {
                            const d = moveHistory[moveHistory.length - 1].dice;
                            const dice1Select = document.getElementById('dice1-select');
                            const dice2Select = document.getElementById('dice2-select');
                            if (dice1Select) dice1Select.value = d.dice1 || '0';
                            if (dice2Select) dice2Select.value = d.dice2 || '0';
                            if (typeof updateDiceSelectorDisplay === 'function') {
                                updateDiceSelectorDisplay(1);
                                updateDiceSelectorDisplay(2);
                            }
                        }
                        updateSelectOptions(getSelectedCheckerColor());
                        updateBarSelects();
                        if (typeof drawBoard === 'function') drawBoard();
                    });
                    return;
                }
                button.addEventListener('click', () => {
                    const row = button.closest('tr');
                    const moveCell = row ? row.querySelector('td:first-child') : null;
                    const gnuMoveStr = moveCell ? moveCell.textContent.trim() : '';
                    if (!gnuMoveStr) return;
                    const hintIndex = row ? parseInt(row.getAttribute('data-hint-index'), 10) : undefined;
                    if (entry && hintIndex !== undefined && !isNaN(hintIndex)) {
                        entry.selectedHintIndex = hintIndex;
                        hintsTable.querySelectorAll('tr[data-hint-index]').forEach(r => r.classList.remove('hint-row-selected'));
                        row.classList.add('hint-row-selected');
                    }
                    if (showButtonSnapshot && showButtonSnapshot.positions) {
                        positions.first = { ...showButtonSnapshot.positions.first };
                        positions.second = { ...showButtonSnapshot.positions.second };
                        updateBarSelects();
                    }
                    const playerTurn = (showButtonSnapshot && showButtonSnapshot.turn) || document.getElementById('turn-select').value;
                    applyMoveToBoard(gnuMoveStr, playerTurn);
                });
            });
        }

        /** Восстанавливает таблицу подсказок из записи истории (по данным API) */
        function applyHintsTableFromEntry(entry) {
            const hintsTable = document.getElementById('hintsTable');
            const hintsTableContainer = document.querySelector('.hints-table');
            if (!hintsTable || !hintsTableContainer) return;

            if (entry.hintsData) {
                const { html, firstHint } = buildHintsTableFromData(entry.hintsData, entry.selectedHintIndex);
                hintsTable.innerHTML = html;
                hintsTable.classList.add('active');
                hintsTableContainer.classList.add('active');
                showButtonSnapshot = {
                    positions: { first: { ...entry.positionsAfter.first }, second: { ...entry.positionsAfter.second } },
                    turn: entry.turnAfter
                };
                if (firstHint && firstHint.type === 'move') {
                    attachHintsTableEyeButtons(hintsTable, showButtonSnapshot, entry);
                }
                if (firstHint && firstHint.type === 'cube_hint') {
                    attachCubeTableEyeButtons(hintsTable);
                }
                if (typeof updateGameTypeButtonMode === 'function') updateGameTypeButtonMode();
            } else {
                hintsTable.innerHTML = '';
                hintsTable.classList.remove('active');
                hintsTableContainer.classList.remove('active');
            }
        }

        /** Восстанавливает кубики (dice) из записи истории */
        function applyDiceFromEntry(entry) {
            if (!entry.dice) return;
            const dice1Select = document.getElementById('dice1-select');
            const dice2Select = document.getElementById('dice2-select');
            if (dice1Select) dice1Select.value = entry.dice.dice1 || '0';
            if (dice2Select) dice2Select.value = entry.dice.dice2 || '0';
            if (typeof updateDiceSelectorDisplay === 'function') {
                updateDiceSelectorDisplay(1);
                updateDiceSelectorDisplay(2);
            }
        }

        /** Восстанавливает состояние кубика из записи истории */
        function applyCubeStateFromEntry(entry) {
            if (!entry.cubeState) return;
            const cs = entry.cubeState;
            const cubeValueSelect = document.getElementById('cube-value-select');
            const cubeShownSelect = document.getElementById('cube-shown-select');
            const cubeOwnerSelect = document.getElementById('cube-owner-select');
            if (cubeValueSelect) {
                cubeValueSelect.value = cs.cubeValue || '0';
                updateCubeSelectorDisplay('value');
            }
            if (cubeShownSelect) {
                cubeShownSelect.value = cs.cubeShown || '0';
                updateCubeSelectorDisplay('shown');
            }
            if (cubeOwnerSelect) {
                cubeOwnerSelect.value = cs.cubeOwner || 'white';
                updateCubeOwnerSelect();
            }
            const isMatch = currentGameType === 'матч';
            const maxCubeSelect = isMatch ? document.getElementById('max-cube-select') : document.getElementById('max-cube-select-m');
            if (maxCubeSelect && cs.maxCube) {
                maxCubeSelect.value = cs.maxCube;
                const maxCubeButton = isMatch ? document.getElementById('max-cube-button') : document.getElementById('max-cube-button-m');
                if (maxCubeButton && maxCubeSelect.options[maxCubeSelect.selectedIndex]) {
                    maxCubeButton.textContent = maxCubeSelect.options[maxCubeSelect.selectedIndex].text;
                }
                if (typeof filterCubeOptions === 'function') filterCubeOptions();
            }
            if (typeof updateCubeSelectorsVisibility === 'function') updateCubeSelectorsVisibility();
        }

        /** Восстанавливает позиции и ход из записи истории */
        function applyHistoryEntry(entry) {
            positions.first = { ...entry.positionsAfter.first };
            positions.second = { ...entry.positionsAfter.second };
            const turn = entry.turnAfter;
            document.getElementById('turn-select').value = turn;
            const whiteBar = document.getElementById('white-bar-select');
            const blackBar = document.getElementById('black-bar-select');
            if (whiteBar) whiteBar.value = (positions.first.bar || 0).toString();
            if (blackBar) blackBar.value = (positions.second.bar || 0).toString();
            updateTurnSelect();
            updateSelectOptions(getSelectedCheckerColor());
            updateBarSelects();
            for (let point = 1; point <= 24; point++) {
                const select = document.getElementById(`point-${point}`);
                const targetPositions = getSelectedCheckerColor() === 'white' ? positions.first : positions.second;
                if (select) select.value = (targetPositions[point.toString()] || 0).toString();
                updatePointSelectorDisplay(point);
            }
            applyCubeStateFromEntry(entry);
            applyDiceFromEntry(entry);
            drawBoard();
            applyHintsTableFromEntry(entry);
        }

        /** Восстанавливает начальную позицию (до первого хода) */
        function applyInitialPosition() {
            const entry = moveHistory[0];
            if (!entry) return;
            positions.first = { ...entry.positionsBefore.first };
            positions.second = { ...entry.positionsBefore.second };
            const turn = entry.turnBefore;
            document.getElementById('turn-select').value = turn;
            const whiteBar = document.getElementById('white-bar-select');
            const blackBar = document.getElementById('black-bar-select');
            if (whiteBar) whiteBar.value = (positions.first.bar || 0).toString();
            if (blackBar) blackBar.value = (positions.second.bar || 0).toString();
            updateTurnSelect();
            updateSelectOptions(getSelectedCheckerColor());
            updateBarSelects();
            for (let point = 1; point <= 24; point++) {
                const select = document.getElementById(`point-${point}`);
                const targetPositions = getSelectedCheckerColor() === 'white' ? positions.first : positions.second;
                if (select) select.value = (targetPositions[point.toString()] || 0).toString();
                updatePointSelectorDisplay(point);
            }
            drawBoard();
        }

        /** Обновляет состояние кнопок навигации по истории */
        function updateHistoryButtons() {
            const backBtn = document.getElementById('history-back-btn');
            const forwardBtn = document.getElementById('history-forward-btn');
            if (!backBtn || !forwardBtn) return;
            const canGoBack = historyIndex > 1 && moveHistory.length > 0;
            const canGoForward = historyIndex < moveHistory.length && moveHistory.length > 0;
            backBtn.classList.toggle('disabled', !canGoBack);
            forwardBtn.classList.toggle('disabled', !canGoForward);
        }

        /** Переход назад по истории */
        function goBackInHistory() {
            if (historyIndex <= 1 || moveHistory.length === 0) return;
            if (document.getElementById('history-back-btn')?.classList.contains('disabled')) return;
            historyIndex--;
            applyHistoryEntry(moveHistory[historyIndex - 1]);
            updateHistoryButtons();
        }

        /** Переход вперёд по истории */
        function goForwardInHistory() {
            if (historyIndex >= moveHistory.length || moveHistory.length === 0) return;
            if (document.getElementById('history-forward-btn')?.classList.contains('disabled')) return;
            historyIndex++;
            if (historyIndex === moveHistory.length) {
                const last = moveHistory[moveHistory.length - 1];
                positions.first = { ...last.positionsAfter.first };
                positions.second = { ...last.positionsAfter.second };
                document.getElementById('turn-select').value = last.turnAfter;
                const whiteBar = document.getElementById('white-bar-select');
                const blackBar = document.getElementById('black-bar-select');
                if (whiteBar) whiteBar.value = (positions.first.bar || 0).toString();
                if (blackBar) blackBar.value = (positions.second.bar || 0).toString();
                updateTurnSelect();
                updateSelectOptions(getSelectedCheckerColor());
                updateBarSelects();
                for (let point = 1; point <= 24; point++) {
                    const select = document.getElementById(`point-${point}`);
                    const targetPositions = getSelectedCheckerColor() === 'white' ? positions.first : positions.second;
                    if (select) select.value = (targetPositions[point.toString()] || 0).toString();
                    updatePointSelectorDisplay(point);
                }
                applyCubeStateFromEntry(last);
                applyDiceFromEntry(last);
                drawBoard();
                applyHintsTableFromEntry(last);
            } else {
                applyHistoryEntry(moveHistory[historyIndex - 1]);
            }
            updateHistoryButtons();
        }

        // Функция для обновления текста типа игры
        function updateGameTypeLabel() {
            const gameTypeLabel = document.getElementById('game-type-label');
            if (!gameTypeLabel) return;
            const i18n = window.POKAZ_I18N || {};
            if (currentGameType === 'матч') {
                const matchLength = document.getElementById('match_lenght')?.value || '5';
                const lowerScore = parseInt(document.getElementById('lower-score')?.value || '0');
                const upperScore = parseInt(document.getElementById('upper-score')?.value || '0');
                const tpl = i18n.match_to_tpl || 'Матч до __LENGTH__. Счет __LOWER__-__UPPER__';
                gameTypeLabel.textContent = tpl
                    .replace(/__LENGTH__/g, matchLength)
                    .replace(/__LOWER__/g, lowerScore)
                    .replace(/__UPPER__/g, upperScore)
                    // Обратная совместимость со старым шаблоном перевода.
                    .replace(/__MAX__/g, lowerScore)
                    .replace(/__MIN__/g, upperScore);
            } else {
                gameTypeLabel.textContent = i18n.moneygame || 'Манигейм';
            }
        }

        const canvas = document.getElementById('boardCanvas');
        const ctx = canvas.getContext('2d');
        const boardWrapper = document.querySelector('.board-wrapper');
        const BOARD_CANVAS_LOGICAL_SIZE = 800;
        const BOARD_POINT_NUMBER_FONT_PX = 30;

        // Load images
        const boardImg = new Image();
        boardImg.src = '/static/board.webp';
        const whiteChecker = new Image();
        whiteChecker.src = '/static/white_checker.webp';
        const blackChecker = new Image();
        blackChecker.src = '/static/black_checker.webp';

        // Load dice images
        const Dice1w = new Image();
        Dice1w.src = pokazAsset('/static/1w.webp');
        const Dice2w = new Image();
        Dice2w.src = pokazAsset('/static/2w.webp');
        const Dice3w = new Image();
        Dice3w.src = pokazAsset('/static/3w.webp');
        const Dice4w = new Image();
        Dice4w.src = pokazAsset('/static/4w.webp');
        const Dice5w = new Image();
        Dice5w.src = pokazAsset('/static/5w.webp');
        const Dice6w = new Image();
        Dice6w.src = pokazAsset('/static/6w.webp');

        const Dice1b = new Image();
        Dice1b.src = pokazAsset('/static/1b.webp');
        const Dice2b = new Image();
        Dice2b.src = pokazAsset('/static/2b.webp');
        const Dice3b = new Image();
        Dice3b.src = pokazAsset('/static/3b.webp');
        const Dice4b = new Image();
        Dice4b.src = pokazAsset('/static/4b.webp');
        const Dice5b = new Image();
        Dice5b.src = pokazAsset('/static/5b.webp');
        const Dice6b = new Image();
        Dice6b.src = pokazAsset('/static/6b.webp');

        // Load cube images
        const Double2 = new Image();
        Double2.src = pokazAsset('/static/Double2.webp');
        const Double4 = new Image();
        Double4.src = pokazAsset('/static/Double4.webp');
        const Double8 = new Image();
        Double8.src = pokazAsset('/static/Double8.webp');
        const Double16 = new Image();
        Double16.src = pokazAsset('/static/Double16.webp');
        const Double32 = new Image();
        Double32.src = pokazAsset('/static/Double32.webp');
        const Double64 = new Image();
        Double64.src = pokazAsset('/static/Double64.webp');

        const diceImages = {
            white: {
                1: Dice1w,
                2: Dice2w,
                3: Dice3w,
                4: Dice4w,
                5: Dice5w,
                6: Dice6w
            },
            black: {
                1: Dice1b,
                2: Dice2b,
                3: Dice3b,
                4: Dice4b,
                5: Dice5b,
                6: Dice6b
            }
        };

        const cubeImages = {
            2: Double2,
            4: Double4,
            8: Double8,
            16: Double16,
            32: Double32,
            64: Double64
        };

        function getX(point) {
            if (point >= 13 && point <= 18) {
                const baseX = 50 + (point - 13) * 60;
                return baseX - (point === 13 ? 8 : 0);
            } else if (point >= 19 && point <= 24) {
                return 450 + (point - 19) * 60;
            } else if (point >= 7 && point <= 12) {
                const baseX = 50 + (12 - point) * 60;
                return baseX - (point === 12 ? 4 : 0);
            } else if (point >= 1 && point <= 6) {
                return 450 + (6 - point) * 60;
            }
            return 0;
        }

        function getBaseY(point) {
            return (point > 12) ? 70 : 690;
        }

        function updateSelectOptions(color) {
            const targetPositions = color === 'white' ? positions.first : positions.second;
            const otherPositions = color === 'white' ? positions.second : positions.first;
            const totalCheckers = getTotalCheckers(targetPositions);
            for (let point = 1; point <= 24; point++) {
                const select = document.getElementById(`point-${point}`);
                const dropdown = document.getElementById(`point-${point}-dropdown`);
                if (!select) continue;
                const currentOnPoint = targetPositions[point.toString()] || 0;
                const occupiedByOther = otherPositions[point.toString()] > 0;
                const baseMax = occupiedByOther ? 0 : 15;
                const maxForThis = Math.min(baseMax, 15 - (totalCheckers - currentOnPoint));
                select.innerHTML = '';
                for (let i = 0; i <= 15; i++) {
                    const option = document.createElement('option');
                    option.value = i;
                    option.textContent = i;
                    select.appendChild(option);
                }
                select.value = currentOnPoint;
                if (dropdown) {
                    dropdown.querySelectorAll('.point-option').forEach(opt => {
                        const val = parseInt(opt.getAttribute('data-value'));
                        opt.style.display = val <= maxForThis ? '' : 'none';
                    });
                }
                updatePointSelectorDisplay(point);
            }
        }

        // Bar selector display functions
        function updateBarSelectorDisplay(barType) {
            const select = document.getElementById(`${barType}-bar-select`);
            const button = document.getElementById(`${barType}-bar-button`);
            const value = parseInt(select.value) || 0;

            button.textContent = value.toString();
        }

        function updateAllBarSelectors() {
            updateBarSelectorDisplay('white');
            updateBarSelectorDisplay('black');
        }

        function updateBarSelects() {
            const whiteBarSelect = document.getElementById('white-bar-select');
            const blackBarSelect = document.getElementById('black-bar-select');
            const whiteBarDropdown = document.getElementById('white-bar-dropdown');
            const blackBarDropdown = document.getElementById('black-bar-dropdown');

            if (whiteBarSelect) {
                const currentBar = parseInt(whiteBarSelect.value) || 0;
                const totalCheckers = getTotalCheckers(positions.first);
                const maxForThis = 15 - (totalCheckers - currentBar);
                whiteBarSelect.innerHTML = '';
                for (let i = 0; i <= maxForThis; i++) {
                    const option = document.createElement('option');
                    option.value = i;
                    option.textContent = i;
                    whiteBarSelect.appendChild(option);
                }
                whiteBarSelect.value = currentBar;

                // Update dropdown options visibility
                if (whiteBarDropdown) {
                    whiteBarDropdown.querySelectorAll('.bar-option').forEach(opt => {
                        const val = parseInt(opt.getAttribute('data-value'));
                        opt.style.display = val <= maxForThis ? 'block' : 'none';
                    });
                }
                updateBarSelectorDisplay('white');
            }
            if (blackBarSelect) {
                const currentBar = parseInt(blackBarSelect.value) || 0;
                const totalCheckers = getTotalCheckers(positions.second);
                const maxForThis = 15 - (totalCheckers - currentBar);
                blackBarSelect.innerHTML = '';
                for (let i = 0; i <= maxForThis; i++) {
                    const option = document.createElement('option');
                    option.value = i;
                    option.textContent = i;
                    blackBarSelect.appendChild(option);
                }
                blackBarSelect.value = currentBar;

                // Update dropdown options visibility
                if (blackBarDropdown) {
                    blackBarDropdown.querySelectorAll('.bar-option').forEach(opt => {
                        const val = parseInt(opt.getAttribute('data-value'));
                        opt.style.display = val <= maxForThis ? 'block' : 'none';
                    });
                }
                updateBarSelectorDisplay('black');
            }
        }

        function createDropdowns() {
            const scale = canvas.offsetWidth / 800;
            for (let point = 1; point <= 24; point++) {
                const wrapper = document.createElement('div');
                wrapper.className = 'point-selector-custom';
                wrapper.dataset.point = point.toString();

                const button = document.createElement('div');
                button.className = 'point-selector-button';
                button.id = `point-${point}-button`;
                button.textContent = '0';

                const dropdown = document.createElement('div');
                dropdown.className = 'point-selector-dropdown ' + (point > 12 ? 'point-dropdown-upper' : 'point-dropdown-lower');
                dropdown.id = `point-${point}-dropdown`;
                for (let i = 0; i <= 15; i++) {
                    const opt = document.createElement('div');
                    opt.className = 'point-option';
                    opt.setAttribute('data-value', i.toString());
                    opt.textContent = i.toString();
                    dropdown.appendChild(opt);
                }

                const select = document.createElement('select');
                select.id = `point-${point}`;
                select.className = 'sr-only';
                select.style.display = 'none';
                select.value = 0;
                for (let i = 0; i <= 15; i++) {
                    const opt = document.createElement('option');
                    opt.value = i;
                    opt.textContent = i;
                    select.appendChild(opt);
                }

                wrapper.appendChild(button);
                wrapper.appendChild(dropdown);
                wrapper.appendChild(select);

                updateDropdownPosition(wrapper, point, scale);

                select.addEventListener('change', updateBoard);

                boardWrapper.appendChild(wrapper);
            }
            updateSelectOptions('white');
            updateBarSelects();
            initPointSelectors();
        }

        function updateDropdownPosition(wrapper, point, scale) {
            const x = (getX(point) - (point > 12 ? 25 : 25)) * scale;
            let y_text;
            if (point > 12) {
                y_text = 20;
            } else {
                y_text = 750;
            }
            const offset = point > 12 ? -70 : 43;
            const y = (y_text + offset) * scale;
            const size = 55 * scale;
            wrapper.style.left = x + 'px';
            wrapper.style.top = y + 'px';
            wrapper.style.width = size + 'px';
            wrapper.style.height = size + 'px';
            wrapper.style.fontSize = (26 * scale) + 'px';
        }

        function updateDomPipsScale() {
            if (!boardWrapper || !canvas) return;
            const renderedWidth = canvas.getBoundingClientRect().width;
            if (!renderedWidth) return;
            const scale = renderedWidth / BOARD_CANVAS_LOGICAL_SIZE;
            boardWrapper.style.setProperty('--board-ui-scale', scale.toFixed(4));
            ['black-pips', 'red-pips'].forEach((id) => {
                const el = document.getElementById(id);
                if (!el) return;
                el.style.fontSize = '';
                el.style.padding = '';
                el.style.borderRadius = '';
            });
        }

        if (typeof ResizeObserver !== 'undefined' && canvas) {
            const boardScaleObserver = new ResizeObserver(() => updateDomPipsScale());
            boardScaleObserver.observe(canvas);
        }
        window.addEventListener('resize', updateDomPipsScale);
        updateDomPipsScale();

        function updateAllDropdownPositions() {
            const scale = canvas.offsetWidth / 800;
            for (let point = 1; point <= 24; point++) {
                const wrapper = document.querySelector(`.point-selector-custom[data-point="${point}"]`);
                if (wrapper) {
                    updateDropdownPosition(wrapper, point, scale);
                }
            }
            updateDomPipsScale();
        }

        function updatePointSelectorDisplay(point) {
            const select = document.getElementById(`point-${point}`);
            const button = document.getElementById(`point-${point}-button`);
            if (!select || !button) return;
            const value = parseInt(select.value) || 0;
            button.textContent = value.toString();
        }

        function initPointSelectors() {
            for (let point = 1; point <= 24; point++) {
                const button = document.getElementById(`point-${point}-button`);
                const dropdown = document.getElementById(`point-${point}-dropdown`);
                const select = document.getElementById(`point-${point}`);

                if (!button || !dropdown || !select) continue;

                dropdown.classList.remove('active');

                button.addEventListener('click', (e) => {
                    e.stopPropagation();
                    document.querySelectorAll('.point-selector-dropdown, .dice-selector-dropdown, .cube-selector-dropdown, .bar-selector-dropdown, .match-selector-dropdown').forEach(d => {
                        if (d !== dropdown) d.classList.remove('active');
                    });
                    dropdown.classList.toggle('active');
                });

                dropdown.querySelectorAll('.point-option').forEach(option => {
                    option.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const value = option.getAttribute('data-value');
                        select.value = value;
                        select.dispatchEvent(new Event('change'));
                        updatePointSelectorDisplay(point);
                        dropdown.classList.remove('active');
                    });
                });
            }
        }

        function drawCheckers(player, img, positions, currentPlayer) {
            ctx.font = `bold ${BOARD_POINT_NUMBER_FONT_PX}px Arial`;
            ctx.fillStyle = '#ffffff';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';

            if (player === currentPlayer) {
                const invertCheckbox = document.getElementById('invertNumberingCheckbox');
                const userInvert = invertCheckbox ? invertCheckbox.checked : false;
                const turnColor = document.getElementById('turn-select')?.value || 'white';
                const autoInvert = (turnColor === 'black');
                // Итоговая инверсия: автоматически меняется при смене хода,
                // а чекбокс даёт пользователю возможность "перевернуть" базовую ориентацию
                const invertNumbers = (autoInvert !== userInvert);

                for (let point = 1; point <= 24; point++) {
                    const x = getX(point);
                    let y = getBaseY(point);
                    const dy = getDy(point);

                    const displayPoint = invertNumbers ? (25 - point) : point;
                    ctx.fillText(displayPoint, x, point > 12 ? y - 50 : y + 60);
                }
            }

            for (let pointStr in positions) {
                if (pointStr === 'bar' || pointStr === 'off') continue;
                const point = parseInt(pointStr);
                let count = positions[pointStr];
                const x = getX(point);
                let y = getBaseY(point);
                const dy = getDy(point);

                for (let i = 0; i < Math.min(count, 5); i++) {
                    ctx.drawImage(img, x - 31.25, y + (i * dy) - 31.25, 62.5, 62.5);
                }

                if (count > 5) {
                    const lastCheckerY = y + (4 * dy);
                    // Устанавливаем противоположный цвет текста
                    ctx.fillStyle = (player === 'first') ? '#000000' : '#ffffff';
                    ctx.fillText(`${count}`, x, lastCheckerY);
                    // Возвращаем белый цвет для остального текста
                    ctx.fillStyle = '#ffffff';
                }
            }

            const barX = 400;

            // Определяем позицию бара с учетом инвертирования
            let barY, barDy;
            if (upperPlayerColor === 'black') {
                // Стандартно: second (черные) сверху, first (белые) снизу
                barY = (player === 'second') ? 220 : 520;
                barDy = (player === 'second') ? 55 : -55;
            } else {
                // Инвертировано: first (белые) сверху, second (черные) снизу
                barY = (player === 'first') ? 220 : 520;
                barDy = (player === 'first') ? 55 : -55;
            }

            if (positions.bar && positions.bar !== 0) {
                let y = barY;
                for (let i = 0; i < Math.min(Math.abs(positions.bar), 2); i++) {
                    ctx.drawImage(img, barX - 31.25, y + (i * barDy) - 31.25, 62.5, 62.5);
                }
                if (Math.abs(positions.bar) > 2) {
                    const lastCheckerY = y + (1 * barDy);
                    // Черный текст для белых шашек, белый для черных
                    ctx.fillStyle = (player === 'first') ? '#000000' : '#ffffff';
                    ctx.fillText(`${Math.abs(positions.bar)}`, barX, lastCheckerY);
                    // Возвращаем белый цвет для остального текста
                    ctx.fillStyle = '#ffffff';
                }
            }
        }

        function getDy(point) {
            return (point > 12) ? 55 : -55;
        }

        // Calculate pips (pip count) for a player
        function calculatePips(positions, player) {
            let totalPips = 0;
            for (let pointStr in positions) {
                if (pointStr === 'bar') {
                    totalPips += Math.abs(positions[pointStr]) * 25;
                } else if (pointStr === 'off') {
                    // Checkers that are off don't count
                } else {
                    const point = parseInt(pointStr);
                    const count = positions[pointStr];
                    let effectivePoint;
                    if (player === 'first') {
                        effectivePoint = point;
                    } else {
                        effectivePoint = 25 - point;
                    }
                    totalPips += count * effectivePoint;
                }
            }
            return totalPips;
        }

        // Draw pip count box
        function drawPipBox(x, y, pips, isWhite) {
            const boxWidth = 60;
            const boxHeight = 40;

            // Draw background
            ctx.fillStyle = isWhite ? '#ffffff' : '#000000';
            ctx.fillRect(x - boxWidth / 2, y - boxHeight / 2, boxWidth, boxHeight);

            // Draw text
            ctx.fillStyle = isWhite ? '#000000' : '#ffffff';
            ctx.font = `bold ${BOARD_POINT_NUMBER_FONT_PX}px Arial`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(`${pips}`, x, y);
        }

        function drawBoard() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(boardImg, 0, 0, canvas.width, canvas.height);

            drawCheckers('first', whiteChecker, positions.first, 'first');
            drawCheckers('second', blackChecker, positions.second, 'second');

            // Draw dice
            const d1 = parseInt(document.getElementById('dice1-select').value);
            const d2 = parseInt(document.getElementById('dice2-select').value);
            const turn = document.getElementById('turn-select').value; // 'white' or 'black'

            if (d1 > 0 || d2 > 0) {
                const diceY = 350;
                let diceX1, diceX2;
                let diceSet;

                // Determine if current turn player is upper or lower
                let isUpperPlayer;
                if (upperPlayerColor === 'black') {
                    // Standard: black is upper, white is lower
                    isUpperPlayer = (turn === 'black');
                } else {
                    // Inverted: white is upper, black is lower
                    isUpperPlayer = (turn === 'white');
                }

                // Upper player dice on left, lower player dice on right
                if (isUpperPlayer) {
                    diceX1 = 130;
                    diceX2 = 220;
                } else {
                    diceX1 = 530;
                    diceX2 = 620;
                }

                // Select dice images based on player color
                diceSet = (turn === 'white') ? diceImages.white : diceImages.black;

                if (diceSet[d1]) ctx.drawImage(diceSet[d1], diceX1, diceY, 60, 60);
                if (diceSet[d2]) ctx.drawImage(diceSet[d2], diceX2, diceY, 60, 60);
            }

            // Draw cube
            const cubeValue = parseInt(document.getElementById('cube-value-select').value);
            const cubeOwner = document.getElementById('cube-owner-select').value;
            const cubeShown = parseInt(document.getElementById('cube-shown-select').value);
            const dice1 = parseInt(document.getElementById('dice1-select').value);
            const dice2 = parseInt(document.getElementById('dice2-select').value);
            // Отображение: при cubeShown !== 0 показываем cubeShown, иначе cubeValue (оставляем тем же)
            const cubeDisplayValue = cubeShown !== 0 ? cubeShown : cubeValue;

            if (cubeDisplayValue >= 0) {
                let img;
                if (cubeDisplayValue === 0) {
                    img = cubeImages[64];
                } else {
                    img = cubeImages[cubeDisplayValue];
                }
                if (img) {
                    let cubeX = 375;
                    let cubeY = 350;

                    // Determine if cube owner is upper or lower player
                    let isUpperPlayer;
                    if (upperPlayerColor === 'black') {
                        // Standard: black is upper, white is lower
                        isUpperPlayer = (cubeOwner === 'black');
                    } else {
                        // Inverted: white is upper, black is lower
                        isUpperPlayer = (cubeOwner === 'white');
                    }

                    if (cubeShown !== 0) {
                        // Cube shown (on bar): upper player left, lower player right
                        cubeX = isUpperPlayer ? 175 : 575;
                        cubeY = 350;
                    } else {
                        if (cubeValue !== 0) {
                            // Cube not shown: upper player top, lower player bottom
                            cubeY = isUpperPlayer ? 100 : 600;
                        }
                    }
                    ctx.drawImage(img, cubeX, cubeY, 50, 50);
                }
            }

            // Draw pips (pip count), possibly repositioning instead of hiding
            const hidePipsCheckbox = document.getElementById('hidePipsCheckbox');
            const hidePointDropdownsCheckbox = document.getElementById('hidePointDropdownsCheckbox');
            const hidePips = hidePipsCheckbox && hidePipsCheckbox.checked;
            const repositionPips = hidePointDropdownsCheckbox && hidePointDropdownsCheckbox.checked;

            // Расчет пипсов с учетом инвертирования
            let whitePips, blackPips;
            if (upperPlayerColor === 'white') {
                // Инвертировано: белые теперь идут от 24 к 1, черные от 1 к 24
                whitePips = calculatePips(positions.first, 'second');
                blackPips = calculatePips(positions.second, 'first');
            } else {
                // Стандартно: белые от 1 к 24, черные от 24 к 1
                whitePips = calculatePips(positions.first, 'first');
                blackPips = calculatePips(positions.second, 'second');
            }

            if (!hidePips) {
                if (repositionPips) {
                    // update DOM pip counters and draw overlay for screenshots
                    const blackDiv = document.getElementById('black-pips');
                    const redDiv = document.getElementById('red-pips');
                    if (blackDiv && redDiv) {
                        if (upperPlayerColor === 'black') {
                            blackDiv.innerText = `${blackPips}`;
                            redDiv.innerText = `${whitePips}`;
                        } else {
                            blackDiv.innerText = `${whitePips}`;
                            redDiv.innerText = `${blackPips}`;
                        }
                        // choose classes so colors follow which player is upper/lower
                        if (upperPlayerColor === 'black') {
                            blackDiv.className = 'pips-above-board';
                            redDiv.className = 'pips-below-board';
                        } else {
                            blackDiv.className = 'pips-above-board-white';
                            redDiv.className = 'pips-below-board-black';
                        }
                        blackDiv.style.display = 'block';
                        redDiv.style.display = 'block';
                    }

                    // draw on canvas for screenshots (same as board_viewer/hint_viewer)
                    if (upperPlayerColor === 'black') {
                        ctx.fillStyle = '#000000';
                        ctx.fillRect(650, -50, 150, 50);
                        ctx.fillStyle = '#ffffff';
                        ctx.font = `bold ${BOARD_POINT_NUMBER_FONT_PX}px Arial`;
                        ctx.textAlign = 'center';
                        ctx.fillText(`${blackPips}`, 725, -20);

                        ctx.fillStyle = '#ffffff';
                        ctx.fillRect(650, 800, 150, 50);
                        ctx.fillStyle = '#000000';
                        ctx.fillText(`${whitePips}`, 725, 830);
                    } else {
                        ctx.fillStyle = '#000000';
                        ctx.fillRect(650, -50, 150, 50);
                        ctx.fillStyle = '#ffffff';
                        ctx.font = `bold ${BOARD_POINT_NUMBER_FONT_PX}px Arial`;
                        ctx.textAlign = 'center';
                        ctx.fillText(`${whitePips}`, 725, -20);

                        ctx.fillStyle = '#ffffff';
                        ctx.fillRect(650, 800, 150, 50);
                        ctx.fillStyle = '#000000';
                        ctx.fillText(`${blackPips}`, 725, 830);
                    }
                } else {
                    // original inline pips boxes on canvas
                    const pipCenterX = 760;
                    const upperPipsY = 360;  // Above center
                    const lowerPipsY = 400;  // Below center

                    if (upperPlayerColor === 'black') {
                        drawPipBox(pipCenterX, upperPipsY, blackPips, false);
                        drawPipBox(pipCenterX, lowerPipsY, whitePips, true);
                    } else {
                        drawPipBox(pipCenterX, upperPipsY, whitePips, true);
                        drawPipBox(pipCenterX, lowerPipsY, blackPips, false);
                    }
                    // hide DOM pips if present
                    const blackDiv = document.getElementById('black-pips');
                    const redDiv = document.getElementById('red-pips');
                    if (blackDiv) blackDiv.style.display = 'none';
                    if (redDiv) redDiv.style.display = 'none';
                }
            } else {
                // hide DOM pips when pips are explicitly hidden
                const blackDiv = document.getElementById('black-pips');
                const redDiv = document.getElementById('red-pips');
                if (blackDiv) blackDiv.style.display = 'none';
                if (redDiv) redDiv.style.display = 'none';
            }

            // Draw checkers off (выброшенные шашки)
            const whiteTotalOnBoard = getTotalCheckers(positions.first);
            const blackTotalOnBoard = getTotalCheckers(positions.second);
            const whiteCheckersOff = 15 - whiteTotalOnBoard;
            const blackCheckersOff = 15 - blackTotalOnBoard;

            const offX = 785;
            const upperOffY = 200;  // Top position
            const lowerOffY = 600;  // Bottom position

            ctx.font = `bold ${BOARD_POINT_NUMBER_FONT_PX}px Arial`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';

            // Determine which player is upper/lower based on upperPlayerColor
            if (upperPlayerColor === 'black') {
                // Standard: black upper, white lower
                ctx.fillStyle = '#ffffff';
                ctx.fillText(`${blackCheckersOff}`, offX, upperOffY);
                ctx.fillStyle = '#ffffff';
                ctx.fillText(`${whiteCheckersOff}`, offX, lowerOffY);
            } else {
                // Inverted: white upper, black lower
                ctx.fillStyle = '#ffffff';
                ctx.fillText(`${whiteCheckersOff}`, offX, upperOffY);
                ctx.fillStyle = '#ffffff';
                ctx.fillText(`${blackCheckersOff}`, offX, lowerOffY);
            }
            updateDomPipsScale();
        }

        function getTotalCheckers(pos) {
            let total = 0;
            for (let key in pos) {
                if (key === 'off') continue;
                total += Math.abs(Number(pos[key]) || 0);
            }
            return total;
        }

        /** Копия позиций с явным off = 15 − (пункты + бар) для визуала в редакторе/карточках. */
        function withComputedOffCount(pos) {
            const copy = JSON.parse(JSON.stringify(pos || {}));
            copy.off = Math.max(0, 15 - getTotalCheckers(copy));
            return copy;
        }

        function getSelectedCheckerColor() {
            const selectedBtn = document.querySelector('.checker-btn.selected');
            return selectedBtn ? selectedBtn.dataset.color : 'white';
        }

        function setSelectedCheckerColor(color) {
            document.querySelectorAll('.checker-btn').forEach(btn => {
                btn.classList.toggle('selected', btn.dataset.color === color);
            });
        }

        function updateBoard() {
            // Update positions from dropdowns
            const color = getSelectedCheckerColor();
            const targetPositions = color === 'white' ? positions.first : positions.second;
            const otherPositions = color === 'white' ? positions.second : positions.first;

            for (let point = 1; point <= 24; point++) {
                const select = document.getElementById(`point-${point}`);
                const count = parseInt(select.value);
                const oldCount = targetPositions[point.toString()] || 0;

                if (count > 0) {
                    const newTotal = getTotalCheckers(targetPositions) - oldCount + count;
                    if (newTotal > 15) {
                        alert('Максимум 15 шашек на цвет!');
                        select.value = oldCount;
                        continue;
                    }
                    targetPositions[point.toString()] = count;
                } else {
                    delete targetPositions[point.toString()];
                }
            }
            drawBoard();
            updateSelectOptions(color);
            updateBarSelects();
        }

        function updateTurnSelect() {
            const turnInput = document.getElementById('turn-select');
            const turnBtn = document.getElementById('turn-select-btn');
            const val = turnInput.value || 'white';
            if (turnBtn) {
                turnBtn.className = 'checker-toggle-btn ' + val;
                turnBtn.dataset.color = val;
            }
            // Update dice selectors when turn changes
            if (typeof updateAllDiceSelectors === 'function') {
                updateAllDiceSelectors();
                if (typeof updateDiceDropdownImages === 'function') {
                    updateDiceDropdownImages();
                }
            }
            // Update turn label
            updateTurnLabel();
        }


        function updateCubeOwnerSelect() {
            const cubeOwnerInput = document.getElementById('cube-owner-select');
            const cubeOwnerBtn = document.getElementById('cube-owner-select-btn');
            const val = cubeOwnerInput.value || 'white';
            if (cubeOwnerBtn) {
                cubeOwnerBtn.className = 'checker-toggle-btn ' + val;
                cubeOwnerBtn.dataset.color = val;
            }
        }

        // Функция синхронизации цветов куба и хода
        function syncCubeOwnerAndTurn() {
            const cubeShown = document.getElementById('cube-shown-select').value;
            if (cubeShown !== '0') {
                const cubeOwner = document.getElementById('cube-owner-select').value;
                const oppositeColor = cubeOwner === 'white' ? 'black' : 'white';
                document.getElementById('turn-select').value = oppositeColor;
                updateTurnSelect();
            }
        }
        let imagesLoaded = 0;
        const totalImages = 21;
        let upperPlayerColor = 'black'; // 'black' or 'white' - который игрок сверху (при 'black' нижний игрок — белые)
        window.pokazIsAdmin = false;
        let latestHintsData = null;

        // XGID string from server (if provided) - read from hidden script element
        const initialXgidElement = document.getElementById('initial-xgid-data');
        const initialXgid = initialXgidElement ? JSON.parse(initialXgidElement.textContent) : null;

        function currentChatIdForEditor() {
            try {
                if (window.Telegram && window.Telegram.WebApp) {
                    const unsafe = window.Telegram.WebApp.initDataUnsafe;
                    const id = unsafe && unsafe.user ? unsafe.user.id : null;
                    if (id != null) return String(id);
                }
            } catch (_e) { /* ignore */ }
            const qp = new URLSearchParams(window.location.search || '');
            return String(qp.get('chat_id') || '');
        }

        async function checkPokazAdminStatus() {
            if (isPokazAdminFromMeta()) {
                applyPokazAdminUi();
                return;
            }
            try {
                let initData = '';
                if (window.Telegram && window.Telegram.WebApp) {
                    initData = window.Telegram.WebApp.initData || '';
                }
                if (!initData) return;
                const response = await fetch('/api/check_admin', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ initData: initData })
                });
                if (!response.ok) return;
                const data = await response.json().catch(() => ({}));
                if (data && data.is_admin) {
                    applyPokazAdminUi();
                }
            } catch (e) {
                console.error('checkPokazAdminStatus:', e);
            }
        }

        function imageLoaded() {
            imagesLoaded++;
            if (imagesLoaded === totalImages) {
                createDropdowns();

                // Initialize hide point dropdowns checkbox handler
                const hidePointDropdownsCheckbox = document.getElementById('hidePointDropdownsCheckbox');
                if (hidePointDropdownsCheckbox) {
                    // restore state from localStorage
                    const savedDpState = localStorage.getItem('hidePointDropdownsCheckbox');
                    if (savedDpState === 'true') hidePointDropdownsCheckbox.checked = true;
                    const applyDropdowns = (checked) => {
                        const dropdowns = document.querySelectorAll('.point-selector-custom');
                        dropdowns.forEach(d => { d.style.display = checked ? 'none' : ''; });
                    };
                    // initial hide if needed
                    applyDropdowns(hidePointDropdownsCheckbox.checked);
                    // and initial board-wrapper margin (no top margin when dropdowns are hidden)
                    const boardWrapper = document.querySelector('.board-wrapper');
                    if (boardWrapper) {
                        if (hidePointDropdownsCheckbox.checked) {
                            boardWrapper.style.marginTop = '0';
                        } else {
                            boardWrapper.style.marginTop = '';
                        }
                    }
                    hidePointDropdownsCheckbox.addEventListener('change', (e) => {
                        const checked = e.target.checked;
                        localStorage.setItem('hidePointDropdownsCheckbox', checked);
                        applyDropdowns(checked);
                        // keep board-wrapper margin in sync on user toggle as well
                        const bw = document.querySelector('.board-wrapper');
                        if (bw) {
                            if (checked) {
                                bw.style.marginTop = '0';
                            } else {
                                bw.style.marginTop = '';
                            }
                        }
                        // reposition pips above/below board whenever dropdown visibility toggles
                        drawBoard();
                    });
                }

                drawBoard();
                updateTurnSelect();
                updateCubeOwnerSelect();
                updateCubeSelectorsVisibility();
                setupDropdownCloseHandler();
                initDiceSelectors();
                initCubeSelectors();
                initBarSelectors();
                initMatchSelectors();
                // Ensure all match dropdowns are closed on initialization
                document.querySelectorAll('.match-selector-dropdown').forEach(d => {
                    d.classList.remove('active');
                });
                // Initialize score options filter
                filterScoreOptions();
                // Initialize turn label
                updateTurnLabel();
                // Синхронизация цветов при загрузке
                const cubeShown = document.getElementById('cube-shown-select').value;
                if (cubeShown !== '0') {
                    syncCubeOwnerAndTurn();
                }
                document.getElementById('lower-score').addEventListener('change', () => {
                    filterScoreOptions();
                    drawBoard();
                    updateGameTypeLabel();
                });
                document.getElementById('upper-score').addEventListener('change', () => {
                    filterScoreOptions();
                    drawBoard();
                    updateGameTypeLabel();
                });
                document.getElementById('match_lenght').addEventListener('change', () => {
                    filterScoreOptions();
                    drawBoard();
                    updateGameTypeLabel();
                });
                document.querySelectorAll('.checker-btn').forEach(btn => {
                    btn.addEventListener('click', () => {
                        const newColor = btn.dataset.color;
                        setSelectedCheckerColor(newColor);
                        updateSelectOptions(newColor);
                        for (let point = 1; point <= 24; point++) {
                            const select = document.getElementById(`point-${point}`);
                            const targetPositions = newColor === 'white' ? positions.first : positions.second;
                            select.value = targetPositions[point.toString()] || 0;
                        }
                        updateBarSelects();
                        drawBoard();
                    });
                });
                document.getElementById('white-bar-select').addEventListener('change', (e) => {
                    const count = parseInt(e.target.value);
                    if (count > 0) {
                        positions.first.bar = count;
                    } else {
                        delete positions.first.bar;
                    }
                    drawBoard();
                    updateSelectOptions('white');
                    updateBarSelects();
                });
                document.getElementById('black-bar-select').addEventListener('change', (e) => {
                    const count = parseInt(e.target.value);
                    if (count > 0) {
                        positions.second.bar = count;
                    } else {
                        delete positions.second.bar;
                    }
                    drawBoard();
                    updateSelectOptions('black');
                    updateBarSelects();
                });

                // Add click handler for canvas to place checkers
                canvas.addEventListener('click', handleCanvasClick);
                canvas.addEventListener('touchstart', handleCanvasTouchStart);
                canvas.addEventListener('touchend', handleCanvasTouchEnd);
            }

            // Initialize cube options filter
            filterCubeOptions();

            // Check if XGID string is provided via URL parameter or template variable
            let xgidString = null;

            // First, try to get from URL parameter
            const urlParams = new URLSearchParams(window.location.search);
            xgidString = urlParams.get('xgid');

            // Apply invert_colors from URL (when coming from hint_viewer with inverted board)
            const invertParam = urlParams.get('invert');
            if (invertParam === '1') {
                upperPlayerColor = 'white';
                const lowerPlayerButton = document.getElementById('lowerPlayerButton');
                if (lowerPlayerButton) {
                    lowerPlayerButton.classList.remove('white');
                    lowerPlayerButton.classList.add('black');
                    lowerPlayerButton.setAttribute('data-color', 'black');
                }
                const invertNumberingCheckbox = document.getElementById('invertNumberingCheckbox');
                if (invertNumberingCheckbox) {
                    invertNumberingCheckbox.checked = true;
                }
            }

            // If not in URL, try to get from template variable (if passed from server)
            if (!xgidString && initialXgid) {
                xgidString = initialXgid;
            }

            // Log incoming XGID string
            if (xgidString) {
                console.log('Incoming XGID string:', xgidString);
                console.log('XGID source:', urlParams.get('xgid') ? 'URL parameter' : 'template variable');
            } else {
                console.log('No XGID string provided');
            }

            // Parse XGID if provided
            if (xgidString) {
                try {
                    parseXGID(xgidString);
                } catch (error) {
                    console.error('Error parsing XGID:', error);
                    console.error('Failed XGID string:', xgidString);
                    alert('Ошибка при загрузке позиции из XGID строки: ' + error.message);
                }
            }
        }

        // Variables to track touch start position for swipe detection
        let touchStartX = 0;
        let touchStartY = 0;
        let touchStartTime = 0;

        // Handle canvas touch start event
        function handleCanvasTouchStart(event) {
            const touch = event.touches[0];
            const rect = canvas.getBoundingClientRect();
            touchStartX = touch.clientX - rect.left;
            touchStartY = touch.clientY - rect.top;
            touchStartTime = Date.now();
        }

        // Function to determine which point was clicked based on canvas coordinates
        function getPointFromCoordinates(canvasX, canvasY) {
            const scale = canvas.offsetWidth / 800;
            const x = canvasX / scale;
            const y = canvasY / scale;

            // Check each point to see if click is within its area
            for (let point = 1; point <= 24; point++) {
                const pointX = getX(point);
                const pointY = getBaseY(point);

                const triangleWidth = 50;
                const triangleHeight = 300;
                // Check if click is within the triangle bounds
                const isInXRange = Math.abs(x - pointX) <= triangleWidth / 2;
                const isInYRange = point > 12
                    ? (y >= pointY && y <= pointY + triangleHeight)  // upper points (13-24)
                    : (y <= pointY && y >= pointY - triangleHeight); // lower points (1-12)

                if (isInXRange && isInYRange) {
                    return point;
                }
            }

            return null; // No point found
        }

        // Определяет, попал ли клик по кубику на доске. Возвращает 1 или 2 (номер кубика) или null.
        function getDiceFromCoordinates(canvasX, canvasY) {
            const d1 = parseInt(document.getElementById('dice1-select').value);
            const d2 = parseInt(document.getElementById('dice2-select').value);
            if (d1 === 0 && d2 === 0) return null;

            const scale = canvas.offsetWidth / 800;
            const x = canvasX / scale;
            const y = canvasY / scale;

            const diceY = 350;
            const diceSize = 60;
            let diceX1, diceX2;

            const turn = document.getElementById('turn-select').value;
            let isUpperPlayer;
            if (upperPlayerColor === 'black') {
                isUpperPlayer = (turn === 'black');
            } else {
                isUpperPlayer = (turn === 'white');
            }

            if (isUpperPlayer) {
                diceX1 = 130;
                diceX2 = 220;
            } else {
                diceX1 = 530;
                diceX2 = 620;
            }

            if (d1 > 0 && x >= diceX1 && x <= diceX1 + diceSize && y >= diceY && y <= diceY + diceSize) return 1;
            if (d2 > 0 && x >= diceX2 && x <= diceX2 + diceSize && y >= diceY && y <= diceY + diceSize) return 2;
            return null;
        }

        // Увеличивает значение кубика на 1 (после 6 → 1)
        function incrementDiceOnClick(diceNum) {
            const select = document.getElementById(`dice${diceNum}-select`);
            if (!select) return;
            let val = parseInt(select.value) || 0;
            if (val === 0) return;
            val = val >= 6 ? 1 : val + 1;
            select.value = val.toString();
            updateDiceSelectorDisplay(diceNum);
            drawBoard();
        }

        // Handle canvas click event
        function handleCanvasClick(event) {
            const rect = canvas.getBoundingClientRect();
            const x = event.clientX - rect.left;
            const y = event.clientY - rect.top;

            const diceNum = getDiceFromCoordinates(x, y);
            if (diceNum !== null) {
                incrementDiceOnClick(diceNum);
                return;
            }
            addCheckerAtPosition(x, y);
        }

        // Handle canvas touch event
        function handleCanvasTouchEnd(event) {
            event.preventDefault();
            const rect = canvas.getBoundingClientRect();
            const touch = event.changedTouches[0];
            const x = touch.clientX - rect.left;
            const y = touch.clientY - rect.top;

            // Calculate distance from touch start to touch end
            const deltaX = Math.abs(x - touchStartX);
            const deltaY = Math.abs(y - touchStartY);
            const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);

            // Calculate touch duration
            const touchDuration = Date.now() - touchStartTime;

            // Only add checker if it's a tap (not a swipe)
            // Threshold: less than 15px movement and duration between 50ms and 500ms
            const isSwipe = distance > 15;
            const isTooQuick = touchDuration < 50;
            const isTooLong = touchDuration > 500;

            if (!isSwipe && !isTooQuick && !isTooLong) {
                const diceNum = getDiceFromCoordinates(x, y);
                if (diceNum !== null) {
                    incrementDiceOnClick(diceNum);
                } else {
                    addCheckerAtPosition(x, y);
                }
            }
        }

        // Remove one checker at the clicked position
        function removeCheckerAtPosition(x, y) {
            const point = getPointFromCoordinates(x, y);

            if (point === null) {
                return; // Click was not on a valid point
            }

            // Check both colors to see which one has checkers here
            const whiteCount = positions.first[point.toString()] || 0;
            const blackCount = positions.second[point.toString()] || 0;

            if (whiteCount > 0) {
                // Remove white checker
                const newCount = whiteCount - 1;
                if (newCount === 0) {
                    delete positions.first[point.toString()];
                } else {
                    positions.first[point.toString()] = newCount;
                }

                // Update the select element
                const select = document.getElementById(`point-${point}`);
                if (select) {
                    select.value = newCount;
                }

                // Redraw board and update options
                drawBoard();
                updateSelectOptions('white');
            } else if (blackCount > 0) {
                // Remove black checker
                const newCount = blackCount - 1;
                if (newCount === 0) {
                    delete positions.second[point.toString()];
                } else {
                    positions.second[point.toString()] = newCount;
                }

                // Update the select element
                const select = document.getElementById(`point-${point}`);
                if (select) {
                    select.value = newCount;
                }

                // Redraw board and update options
                drawBoard();
                updateSelectOptions('black');
            }
        }

        // Add one checker at the clicked position
        function addCheckerAtPosition(x, y) {
            // Check current mode
            if (currentMode === 'delete') {
                removeCheckerAtPosition(x, y);
                return;
            }

            const point = getPointFromCoordinates(x, y);

            if (point === null) {
                return; // Click was not on a valid point
            }

            const color = getSelectedCheckerColor();
            const targetPositions = color === 'white' ? positions.first : positions.second;
            const otherPositions = color === 'white' ? positions.second : positions.first;

            // Check if the point is occupied by the other color
            const occupiedByOther = (otherPositions[point.toString()] || 0) > 0;
            if (occupiedByOther) {
                return; // Cannot place checker on opponent's point
            }

            // Get current count and check if we can add one more
            const currentCount = targetPositions[point.toString()] || 0;
            const totalCheckers = getTotalCheckers(targetPositions);

            if (totalCheckers >= 15) {
                return; // Already have 15 checkers placed
            }

            if (currentCount >= 15) {
                return; // Cannot have more than 15 checkers on one point
            }

            // Add one checker
            const newCount = currentCount + 1;
            targetPositions[point.toString()] = newCount;

            // Update the select element
            const select = document.getElementById(`point-${point}`);
            if (select) {
                select.value = newCount;
            }

            // Redraw board and update options
            drawBoard();
            updateSelectOptions(color);
        }

        boardImg.onload = imageLoaded;
        whiteChecker.onload = imageLoaded;
        blackChecker.onload = imageLoaded;
        Dice1w.onload = imageLoaded;
        Dice2w.onload = imageLoaded;
        Dice3w.onload = imageLoaded;
        Dice4w.onload = imageLoaded;
        Dice5w.onload = imageLoaded;
        Dice6w.onload = imageLoaded;
        Dice1b.onload = imageLoaded;
        Dice2b.onload = imageLoaded;
        Dice3b.onload = imageLoaded;
        Dice4b.onload = imageLoaded;
        Dice5b.onload = imageLoaded;
        Dice6b.onload = imageLoaded;
        Double2.onload = imageLoaded;
        Double4.onload = imageLoaded;
        Double8.onload = imageLoaded;
        Double16.onload = imageLoaded;
        Double32.onload = imageLoaded;
        Double64.onload = imageLoaded;


        /** Возвращает предыдущее значение в последовательности куба (0,2,4,8,16,32,64). Для 0 возвращает 0. */
        function getPrevCubeValue(val) {
            const CUBE_SEQUENCE = [0, 2, 4, 8, 16, 32, 64];
            const num = parseInt(val, 10) || 0;
            const idx = CUBE_SEQUENCE.indexOf(num);
            if (idx <= 0) return 0;
            return CUBE_SEQUENCE[idx - 1];
        }

        function updateCubeSelectorsVisibility() {
            const cubeShown = document.getElementById('cube-shown-select').value;
            const diceSection = document.querySelectorAll('.turn-dice-section')[1];
            const diceLabel = document.querySelectorAll('.turn-dice-labels label')[1];
            const cubeValueOptions = document.querySelector('.cube-value-options');
            const cubeValueLabel = document.querySelector('.cube-controls-labels label[for="cube-value-select"]');
            if (cubeShown !== '0') {
                if (diceSection) diceSection.style.display = 'none';
                if (diceLabel) diceLabel.style.display = 'none';
                if (cubeValueOptions) cubeValueOptions.style.display = 'none';
                if (cubeValueLabel) cubeValueLabel.style.display = 'none';
            } else {
                if (diceSection) diceSection.style.display = 'flex';
                if (diceLabel) diceLabel.style.display = '';
                if (cubeValueOptions) cubeValueOptions.style.display = 'flex';
                if (cubeValueLabel) cubeValueLabel.style.display = '';
            }
            // Update dice selectors display when visibility changes
            if (cubeShown === '0') {
                updateAllDiceSelectors();
            }
        }

        document.getElementById('cube-shown-select').addEventListener('change', () => {
            updateCubeSelectorDisplay('shown');
            updateCubeSelectorsVisibility();
            const cubeShown = document.getElementById('cube-shown-select').value;
            // cube-value-select = cube-shown-select - 1 (на одно меньше). При 0 оба = 0.
            document.getElementById('cube-value-select').value = getPrevCubeValue(cubeShown).toString();
            if (cubeShown !== '0') {
                document.getElementById('dice1-select').value = '0';
                document.getElementById('dice2-select').value = '0';
                updateAllDiceSelectors();
                // Синхронизация: сделать цвета противоположными
                syncCubeOwnerAndTurn();
            } else {
                // При значении 0, оба должны быть белыми
                document.getElementById('turn-select').value = 'white';
                document.getElementById('cube-owner-select').value = 'white';
                updateTurnSelect();
                updateCubeOwnerSelect();
            }
            updateCubeSelectorDisplay('value');
            drawBoard();
        });
        function generateXGID() {
            let xgid = "";
            const invertPositions = (upperPlayerColor === 'white');

            // Определяем какие позиции использовать для верхнего и нижнего игроков
            const upperPositions = invertPositions ? positions.first : positions.second;
            const lowerPositions = invertPositions ? positions.second : positions.first;

            // Bar для верхнего игрока (первый символ в XGID)
            const upperBar = upperPositions.bar || 0;
            if (upperBar === 0) {
                xgid += "-";
            } else if (upperBar <= 15) {
                // Верхний игрок = строчные буквы (a-o)
                xgid += String.fromCharCode(96 + upperBar);
            }

            for (let point = 1; point <= 24; point++) {
                // XGID позиции не инвертируются, всегда идут от 1 до 24
                // Меняется только то, какие шашки считаются нижними/верхними
                const lowerCount = lowerPositions[point] || 0;
                const upperCount = upperPositions[point] || 0;

                if (lowerCount > 0) {
                    if (lowerCount <= 15) {
                        // Нижний = заглавные (A-O)
                        xgid += String.fromCharCode(64 + lowerCount);
                    }
                } else if (upperCount > 0) {
                    if (upperCount <= 15) {
                        // Верхний = строчные (a-o)
                        xgid += String.fromCharCode(96 + upperCount);
                    }
                } else {
                    xgid += "-";
                }
            }

            // Bar для нижнего игрока (последний символ перед ':' в XGID)
            const lowerBar = lowerPositions.bar || 0;
            if (lowerBar === 0) {
                xgid += "-";
            } else if (lowerBar <= 15) {
                // Нижний игрок = заглавные буквы (A-O)
                xgid += String.fromCharCode(64 + lowerBar);
            }
            xgid += ':'
            const cubeValue = parseInt(document.getElementById('cube-value-select').value);
            const cubeShown = parseInt(document.getElementById('cube-shown-select').value);
            const cubeDisplayValue = cubeShown !== 0 ? cubeShown : cubeValue;
            let exponent = 0;
            if (cubeDisplayValue >= 2) {
                exponent = Math.log2(cubeDisplayValue);
                if (cubeShown !== 0) exponent -= 1;
            }
            xgid += exponent.toString();
            xgid += ':'
            const cubeOwner = document.getElementById('cube-owner-select').value;
            let cubePosition = 0;
            if (cubeValue !== 0) {
                // Определяем владельца куба в терминах upper/lower
                // В XGID: 1 = lower (нижний), -1 = upper (верхний)
                let isLowerPlayer;
                if (invertPositions) {
                    // white стал верхним, black стал нижним
                    isLowerPlayer = (cubeOwner === 'black');
                } else {
                    // white нижний, black верхний (стандартное)
                    isLowerPlayer = (cubeOwner === 'white');
                }
                cubePosition = isLowerPlayer ? 1 : -1;
            }
            xgid += cubePosition.toString();
            xgid += ':'
            const turn = document.getElementById('turn-select').value;
            let turnValue = 0;
            // Определяем чей ход в терминах upper/lower
            // В XGID: 1 = lower (нижний), -1 = upper (верхний)
            let isLowerPlayerTurn;
            if (invertPositions) {
                // white стал верхним, black стал нижним
                isLowerPlayerTurn = (turn === 'black');
            } else {
                // white нижний, black верхний (стандартное)
                isLowerPlayerTurn = (turn === 'white');
            }
            turnValue = isLowerPlayerTurn ? 1 : -1;
            xgid += turnValue.toString();
            xgid += ':'
            let cubePart = '';
            const dice1 = parseInt(document.getElementById('dice1-select').value);
            const dice2 = parseInt(document.getElementById('dice2-select').value);
            if (dice1 === 0 && dice2 === 0) {
                cubePart = '00';
            } else if (cubeShown !== 0) {
                cubePart = 'D';
            } else if (dice1 !== 0 || dice2 !== 0) {
                cubePart = dice1.toString() + dice2.toString();
            }
            xgid += cubePart;
            xgid += ':'
            const LowerScore = currentGameType === 'манигейм' ? '0' : document.getElementById('lower-score').value;
            xgid += LowerScore;
            xgid += ':'
            const UpperScore = currentGameType === 'манигейм' ? '0' : document.getElementById('upper-score').value;
            xgid += UpperScore;
            xgid += ':'
            let conventionPart;
            if (currentGameType === 'матч') {
                // При матче: 1 если Кроуфорд активен, 0 если нет
                const crawfordCheckbox = document.getElementById('crawford-checkbox');
                conventionPart = (crawfordCheckbox && crawfordCheckbox.checked) ? '1' : '0';
            } else {
                // При манигейме: jacobi + 2*beaver
                conventionPart = (parseInt(document.getElementById('jacobi-select').value) + 2 * parseInt(document.getElementById('beaver-select').value)).toString();
            }
            xgid += conventionPart;
            xgid += ':'
            const matchLengthPart = currentGameType === 'манигейм' ? '0' : document.getElementById('match_lenght').value;
            xgid += matchLengthPart;
            xgid += ':'
            const maxCubePart = currentGameType === 'матч' ? document.getElementById('max-cube-select').value : document.getElementById('max-cube-select-m').value;
            xgid += maxCubePart;
            return xgid;
        }

        function parseXGID(xgidString) {
            console.log('parseXGID called with string:', xgidString);
            console.log('XGID string length:', xgidString ? xgidString.length : 0);

            if (!xgidString || typeof xgidString !== 'string') {
                console.error('Invalid XGID string:', xgidString);
                return;
            }

            const parts = xgidString.split(':');
            console.log('XGID parts count:', parts.length);
            console.log('XGID parts:', parts);

            if (parts.length < 10) {
                console.error('Invalid XGID format: not enough parts. Expected 10, got', parts.length);
                return;
            }

            clearMoveHistory();

            // Parse board positions
            const boardPart = parts[0];
            if (boardPart.length < 26) {
                console.error('Invalid XGID format: board part too short');
                return;
            }

            // First character: upper bar
            const upperBarChar = boardPart[0];
            const upperBar = (upperBarChar === '-' || upperBarChar === '') ? 0 :
                (upperBarChar >= 'a' && upperBarChar <= 'o') ? upperBarChar.charCodeAt(0) - 96 : 0;

            // Last character before ':': lower bar
            const lowerBarChar = boardPart[boardPart.length - 1];
            const lowerBar = (lowerBarChar === '-' || lowerBarChar === '') ? 0 :
                (lowerBarChar >= 'A' && lowerBarChar <= 'O') ? lowerBarChar.charCodeAt(0) - 64 : 0;

            // Positions 1-24 (characters 1-24)
            const positionsPart = boardPart.substring(1, 25);
            // Clear current positions
            positions.first = {};
            positions.second = {};

            // XGID: lower (A-O) = white/Red, upper (a-o) = black. positions.first=white, positions.second=black
            // При invert=1 маппинг тот же — hint_viewer уже передаёт инвертированные позиции
            const upperPositions = positions.second;
            const lowerPositions = positions.first;

            // Parse positions
            for (let i = 0; i < 24; i++) {
                const point = i + 1;
                const char = positionsPart[i];

                if (char === '-' || !char) {
                    // Empty point
                    continue;
                } else if (char >= 'A' && char <= 'O') {
                    // Lower player (заглавные) -> lowerPositions
                    const count = char.charCodeAt(0) - 64;
                    lowerPositions[point.toString()] = count;
                } else if (char >= 'a' && char <= 'o') {
                    // Upper player (строчные) -> upperPositions
                    const count = char.charCodeAt(0) - 96;
                    upperPositions[point.toString()] = count;
                }
            }

            // Set bars
            if (upperBar > 0) {
                upperPositions.bar = upperBar;
            }
            if (lowerBar > 0) {
                lowerPositions.bar = lowerBar;
            }

            // Parse cube exponent (part 1)
            const exponent = parseInt(parts[1]) || 0;
            const cubeValue = exponent > 0 ? Math.pow(2, exponent) : 0;

            // Parse cube position (part 2)
            const cubePosition = parseInt(parts[2]) || 0;

            // Parse turn (part 3)
            const turnValue = parseInt(parts[3]) || 0;

            // Parse cube part (part 4)
            const cubePart = parts[4] || '00';

            // Parse scores (parts 5-6)
            // First number after cube/dice is lower score, second is upper score
            const lowerScore = parts[5] || '0';
            const upperScore = parts[6] || '0';
            console.log('Parsed scores - lower:', lowerScore, 'upper:', upperScore);

            // Parse convention (part 7)
            const conventionPart = parts[7] || '0';

            // Parse match length (part 8)
            const matchLengthPart = parts[8] || '0';

            // Parse max cube (part 9)
            const maxCubePart = parts[9] || '3';

            // Determine game type based on match length
            const isMatch = matchLengthPart !== '0';
            if (isMatch) {
                // Switch to match mode
                const jbWrap = document.querySelector('.jb-wrap');
                const matchPanel = document.querySelector('.match-panel');
                const gameTypeButton = document.getElementById('game-type-button');
                if (jbWrap && matchPanel && gameTypeButton) {
                    jbWrap.style.display = 'none';
                    matchPanel.style.display = 'flex';
                    gameTypeButton.innerHTML = '<i class="fa fa-trophy"></i>';
                    gameTypeButton.title = (window.POKAZ_I18N || {}).match || 'Матч';
                    currentGameType = 'матч';

                    // Update game type label
                    updateGameTypeLabel();
                    if (typeof setCrawfordControlsVisible === 'function') {
                        setCrawfordControlsVisible(true);
                    }
                }
            } else {
                // Switch to money game mode
                const jbWrap = document.querySelector('.jb-wrap');
                const matchPanel = document.querySelector('.match-panel');
                const gameTypeButton = document.getElementById('game-type-button');
                if (jbWrap && matchPanel && gameTypeButton) {
                    jbWrap.style.display = 'flex';
                    matchPanel.style.display = 'none';
                    gameTypeButton.innerHTML = '<i class="fa fa-rub"></i>';
                    gameTypeButton.title = (window.POKAZ_I18N || {}).moneygame || 'Манигейм';
                    currentGameType = 'манигейм';

                    // Update game type label
                    updateGameTypeLabel();
                    if (typeof setCrawfordControlsVisible === 'function') {
                        setCrawfordControlsVisible(false);
                    }
                }
            }

            // Set scores immediately after switching game type (for match games)
            // Use setTimeout to ensure DOM is updated
            setTimeout(() => {
                if (isMatch) {
                    const lowerScoreSelect = document.getElementById('lower-score');
                    const upperScoreSelect = document.getElementById('upper-score');
                    const lowerScoreButton = document.getElementById('lower-score-button');
                    const upperScoreButton = document.getElementById('upper-score-button');

                    console.log('Setting scores after game type switch - lower:', lowerScore, 'upper:', upperScore);
                    console.log('Score elements found:', {
                        lowerScoreSelect: !!lowerScoreSelect,
                        upperScoreSelect: !!upperScoreSelect,
                        lowerScoreButton: !!lowerScoreButton,
                        upperScoreButton: !!upperScoreButton
                    });

                    if (lowerScoreSelect) {
                        lowerScoreSelect.value = lowerScore;
                        console.log('Set lower-score select value to:', lowerScore);
                        if (lowerScoreButton) {
                            lowerScoreButton.textContent = lowerScore;
                            console.log('Set lower-score button text to:', lowerScore);
                        }
                    } else {
                        console.warn('lower-score select not found');
                    }

                    if (upperScoreSelect) {
                        upperScoreSelect.value = upperScore;
                        console.log('Set upper-score select value to:', upperScore);
                        if (upperScoreButton) {
                            upperScoreButton.textContent = upperScore;
                            console.log('Set upper-score button text to:', upperScore);
                        }
                    } else {
                        console.warn('upper-score select not found');
                    }

                    // Filter score options to ensure they don't exceed match length
                    filterScoreOptions();

                    // Update game type label after setting scores
                    updateGameTypeLabel();
                }
            }, 0);

            // Set cube value (при cubePart='D' — на одно меньше чем cubeShown)
            const cubeValueSelect = document.getElementById('cube-value-select');
            if (cubeValueSelect) {
                cubeValueSelect.value = (cubePart === 'D' ? getPrevCubeValue(cubeValue) : cubeValue).toString();
                updateCubeSelectorDisplay('value');
            }

            // Set cube shown
            let cubeShown = 0;
            if (cubePart === 'D') {
                cubeShown = cubeValue;
            }
            const cubeShownSelect = document.getElementById('cube-shown-select');
            if (cubeShownSelect) {
                cubeShownSelect.value = cubeShown.toString();
                updateCubeSelectorDisplay('shown');
            }

            // Set cube owner: 1 = lower (white), -1 = upper (black) — не зависит от invert
            let cubeOwner = 'white';
            if (cubePosition === 1) {
                cubeOwner = 'white';
            } else if (cubePosition === -1) {
                cubeOwner = 'black';
            }
            const cubeOwnerSelect = document.getElementById('cube-owner-select');
            if (cubeOwnerSelect) {
                cubeOwnerSelect.value = cubeOwner;
                updateCubeOwnerSelect();
            }

            // Set turn based on turnValue
            // XGID turnValue: 1 = lower (white), -1 = upper (black) — не зависит от invert
            let turn = 'white';
            if (turnValue === 1) {
                turn = 'white';
            } else if (turnValue === -1) {
                turn = 'black';
            }
            const turnSelect = document.getElementById('turn-select');
            if (turnSelect) {
                turnSelect.value = turn;
                updateTurnSelect();
            }

            // Set dice
            let dice1 = 0, dice2 = 0;
            if (cubePart !== '00' && cubePart !== 'D' && cubePart.length === 2) {
                dice1 = parseInt(cubePart[0]) || 0;
                dice2 = parseInt(cubePart[1]) || 0;
            }
            const dice1Select = document.getElementById('dice1-select');
            const dice2Select = document.getElementById('dice2-select');
            if (dice1Select) dice1Select.value = dice1.toString();
            if (dice2Select) dice2Select.value = dice2.toString();
            if (dice1 > 0 || dice2 > 0) {
                updateDiceSelectorDisplay(1);
                updateDiceSelectorDisplay(2);
            }

            // Set convention
            if (isMatch) {
                // Crawford checkbox
                const crawfordCheckbox = document.getElementById('crawford-checkbox');
                if (crawfordCheckbox) {
                    crawfordCheckbox.checked = (conventionPart === '1');
                    crawfordCheckbox.dispatchEvent(new Event('change'));
                }
            } else {
                // Jacobi and beaver
                // conventionPart = jacobi + 2*beaver
                const jacobi = conventionPart % 2;
                const beaver = Math.floor(conventionPart / 2);
                const jacobiSelect = document.getElementById('jacobi-select');
                const beaverSelect = document.getElementById('beaver-select');
                if (jacobiSelect) jacobiSelect.value = jacobi.toString();
                if (beaverSelect) beaverSelect.value = beaver.toString();
            }

            // Set match length (pre-last part, part 8)
            if (isMatch) {
                const matchLengthSelect = document.getElementById('match_lenght');
                const matchLengthButton = document.getElementById('match-lenght-button');

                console.log('Setting match length:', matchLengthPart);

                if (matchLengthSelect) {
                    matchLengthSelect.value = matchLengthPart;
                    console.log('Set match_lenght select value to:', matchLengthPart);

                    if (matchLengthButton) {
                        matchLengthButton.textContent = matchLengthPart;
                        console.log('Set match-lenght button text to:', matchLengthPart);
                    } else {
                        console.warn('match-lenght-button not found');
                    }

                    // Update game type label
                    updateGameTypeLabel();
                } else {
                    console.warn('match_lenght select not found');
                }
            }

            // Set max cube
            const maxCubeSelect = isMatch ?
                document.getElementById('max-cube-select') :
                document.getElementById('max-cube-select-m');
            if (maxCubeSelect) {
                maxCubeSelect.value = maxCubePart;
                // Update button text
                const maxCubeButton = isMatch ?
                    document.getElementById('max-cube-button') :
                    document.getElementById('max-cube-button-m');
                if (maxCubeButton) {
                    const optionText = maxCubeSelect.options[maxCubeSelect.selectedIndex].text;
                    maxCubeButton.textContent = optionText;
                }
                // Filter cube options
                filterCubeOptions();
            }

            // Update all selects for positions
            updateSelectOptions('white');
            updateSelectOptions('black');
            updateBarSelects();

            // Redraw board
            drawBoard();
        }

        function handleDiceChange(changedSelectId, otherSelectId) {
            const changedValue = parseInt(document.getElementById(changedSelectId).value);
            const otherSelect = document.getElementById(otherSelectId);
            if (changedValue !== 0 && parseInt(otherSelect.value) === 0) {
                otherSelect.value = '1';
            } else if (changedValue === 0) {
                otherSelect.value = '0';
            }
            drawBoard();
        }

        document.getElementById('turn-select').addEventListener('change', () => {
            drawBoard();
            updateTurnLabel();
        });

        const turnCheckerIndicator = document.getElementById('turn-checker-indicator');
        if (turnCheckerIndicator) {
            turnCheckerIndicator.addEventListener('click', () => {
                const turnInput = document.getElementById('turn-select');
                if (!turnInput) return;
                const newColor = turnInput.value === 'white' ? 'black' : 'white';
                turnInput.value = newColor;
                updateTurnSelect();
                turnInput.dispatchEvent(new Event('change'));
            });
        }

        document.getElementById('cube-value-select').addEventListener('change', () => {
            updateCubeSelectorDisplay('value');
            drawBoard();
        });
        document.getElementById('cube-owner-select').addEventListener('change', drawBoard);
        document.querySelectorAll('.checker-toggle-btn').forEach(btn => {
            btn.addEventListener('click', function () {
                const input = document.getElementById(this.dataset.target);
                if (!input) return;
                const newColor = input.value === 'white' ? 'black' : 'white';
                input.value = newColor;
                if (this.dataset.target === 'turn-select') {
                    updateTurnSelect();
                } else if (this.dataset.target === 'cube-owner-select') {
                    updateCubeOwnerSelect();
                    // При изменении куба синхронизируем с ходом
                    const cubeShown = document.getElementById('cube-shown-select').value;
                    if (cubeShown !== '0') {
                        syncCubeOwnerAndTurn();
                    }
                }
                input.dispatchEvent(new Event('change'));
            });
        });
        // Custom dice selectors
        function updateDiceSelectorDisplay(diceNum) {
            const select = document.getElementById(`dice${diceNum}-select`);
            const button = document.getElementById(`dice${diceNum}-button`);
            const value = parseInt(select.value) || 0;
            const turn = document.getElementById('turn-select').value;

            if (value === 0) {
                button.className = 'dice-selector-button empty';
                button.textContent = '';
                button.innerHTML = '';
            } else {
                button.className = 'dice-selector-button';
                const imgSrc = turn === 'white'
                    ? `/static/${value}w.webp`
                    : `/static/${value}b.webp`;
                button.innerHTML = `<img src="${imgSrc}" alt="${value}">`;
            }
        }

        function updateAllDiceSelectors() {
            updateDiceSelectorDisplay(1);
            updateDiceSelectorDisplay(2);
        }

        function updateDiceDropdownImages() {
            const turn = document.getElementById('turn-select').value;
            // Обновляем только картинки костей (dice1 и dice2), не кубов
            ['dice1-dropdown', 'dice2-dropdown'].forEach(dropdownId => {
                const dropdown = document.getElementById(dropdownId);
                if (dropdown) {
                    dropdown.querySelectorAll('.dice-option img').forEach(img => {
                        const value = img.alt;
                        if (turn === 'white') {
                            img.src = `/static/${value}w.webp`;
                        } else {
                            img.src = img.getAttribute('data-black') || `/static/${value}b.webp`;
                        }
                    });
                }
            });
        }

        // Initialize dice selectors
        function initDiceSelectors() {
            updateAllDiceSelectors();

            // Setup click handlers for buttons
            ['1', '2'].forEach(diceNum => {
                const button = document.getElementById(`dice${diceNum}-button`);
                const dropdown = document.getElementById(`dice${diceNum}-dropdown`);
                const select = document.getElementById(`dice${diceNum}-select`);

                button.addEventListener('click', (e) => {
                    e.stopPropagation();
                    // Close other dropdowns (both dice and cube)
                    document.querySelectorAll('.dice-selector-dropdown, .cube-selector-dropdown').forEach(d => {
                        if (d !== dropdown) d.classList.remove('active');
                    });
                    dropdown.classList.toggle('active');
                });

                // Setup option click handlers
                dropdown.querySelectorAll('.dice-option').forEach(option => {
                    option.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const value = option.getAttribute('data-value');
                        select.value = value;
                        select.dispatchEvent(new Event('change'));
                        updateDiceSelectorDisplay(diceNum);
                        dropdown.classList.remove('active');
                    });
                });
            });

        }

        let dropdownCloseHandlerSetup = false;
        function setupDropdownCloseHandler() {
            if (dropdownCloseHandlerSetup) return;
            dropdownCloseHandlerSetup = true;

            document.addEventListener('click', (e) => {
                if (!e.target.closest('.dice-selector-custom') &&
                    !e.target.closest('.cube-selector-custom') &&
                    !e.target.closest('.bar-selector-custom') &&
                    !e.target.closest('.match-selector-custom') &&
                    !e.target.closest('.point-selector-custom')) {
                    document.querySelectorAll('.dice-selector-dropdown, .cube-selector-dropdown, .bar-selector-dropdown, .match-selector-dropdown, .point-selector-dropdown').forEach(d => {
                        d.classList.remove('active');
                    });
                }
            });
        }

        // Cube selector functions
        function updateCubeSelectorDisplay(selectorType) {
            const select = document.getElementById(`cube-${selectorType}-select`);
            const button = document.getElementById(`cube-${selectorType}-button`);
            const value = parseInt(select.value) || 0;

            if (value === 0) {
                button.className = 'cube-selector-button empty';
                const noText = (window.POKAZ_NO !== undefined ? window.POKAZ_NO : ((window.POKAZ_I18N || {}).no || 'Нет'));
                button.textContent = noText;
                button.innerHTML = noText;
            } else {
                button.className = 'cube-selector-button';
                const imgSrc = `/static/Double${value}.webp`;
                button.innerHTML = `<img src="${imgSrc}" alt="${value}">`;
            }
        }

        function updateAllCubeSelectors() {
            updateCubeSelectorDisplay('value');
            updateCubeSelectorDisplay('shown');
        }

        // Initialize cube selectors
        function initCubeSelectors() {
            updateAllCubeSelectors();

            // Setup click handlers for cube selectors
            ['value', 'shown'].forEach(selectorType => {
                const button = document.getElementById(`cube-${selectorType}-button`);
                const dropdown = document.getElementById(`cube-${selectorType}-dropdown`);
                const select = document.getElementById(`cube-${selectorType}-select`);

                // Убеждаемся, что меню закрыто при инициализации
                if (dropdown) {
                    dropdown.classList.remove('active');
                }

                button.addEventListener('click', (e) => {
                    e.stopPropagation();
                    // Close other dropdowns (both dice and cube)
                    document.querySelectorAll('.dice-selector-dropdown, .cube-selector-dropdown').forEach(d => {
                        if (d !== dropdown) d.classList.remove('active');
                    });
                    dropdown.classList.toggle('active');
                });

                // Setup option click handlers
                dropdown.querySelectorAll('.cube-option').forEach(option => {
                    option.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const value = option.getAttribute('data-value');
                        select.value = value;
                        select.dispatchEvent(new Event('change'));
                        updateCubeSelectorDisplay(selectorType);
                        dropdown.classList.remove('active');
                    });
                });
            });
        }

        // Initialize bar selectors
        function initBarSelectors() {
            updateAllBarSelectors();

            // Setup click handlers for bar selectors
            ['white', 'black'].forEach(barType => {
                const button = document.getElementById(`${barType}-bar-button`);
                const dropdown = document.getElementById(`${barType}-bar-dropdown`);
                const select = document.getElementById(`${barType}-bar-select`);

                // Убеждаемся, что меню закрыто при инициализации
                if (dropdown) {
                    dropdown.classList.remove('active');
                }

                button.addEventListener('click', (e) => {
                    e.stopPropagation();
                    // Close other dropdowns (dice, cube, and other bar)
                    document.querySelectorAll('.dice-selector-dropdown, .cube-selector-dropdown, .bar-selector-dropdown').forEach(d => {
                        if (d !== dropdown) d.classList.remove('active');
                    });
                    dropdown.classList.toggle('active');
                });

                // Setup option click handlers
                dropdown.querySelectorAll('.bar-option').forEach(option => {
                    option.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const value = option.getAttribute('data-value');
                        select.value = value;
                        select.dispatchEvent(new Event('change'));
                        updateBarSelectorDisplay(barType);
                        dropdown.classList.remove('active');
                    });
                });
            });
        }

        function initMatchSelectors() {
            // Setup match panel selectors
            const matchSelectors = [
                { id: 'lower-score', buttonId: 'lower-score-button', dropdownId: 'lower-score-dropdown' },
                { id: 'upper-score', buttonId: 'upper-score-button', dropdownId: 'upper-score-dropdown' },
                { id: 'match_lenght', buttonId: 'match-lenght-button', dropdownId: 'match-lenght-dropdown' },
                { id: 'max-cube-select', buttonId: 'max-cube-button', dropdownId: 'max-cube-dropdown' },
                { id: 'max-cube-select-m', buttonId: 'max-cube-button-m', dropdownId: 'max-cube-dropdown-m' }
            ];

            matchSelectors.forEach(selector => {
                const button = document.getElementById(selector.buttonId);
                const dropdown = document.getElementById(selector.dropdownId);
                const select = document.getElementById(selector.id);

                if (!button || !dropdown || !select) return;

                // Close dropdown by default
                dropdown.classList.remove('active');

                // Button click handler
                button.addEventListener('click', (e) => {
                    e.stopPropagation();
                    // Close all other match dropdowns
                    document.querySelectorAll('.match-selector-dropdown').forEach(d => {
                        if (d !== dropdown) d.classList.remove('active');
                    });
                    dropdown.classList.toggle('active');
                });

                // Option click handlers
                dropdown.querySelectorAll('.match-option').forEach(option => {
                    option.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const value = option.getAttribute('data-value');

                        // Check if selecting score option that exceeds match length
                        if (selector.id === 'lower-score' || selector.id === 'upper-score') {
                            const matchLengthSelect = document.getElementById('match_lenght');
                            if (matchLengthSelect) {
                                const matchLength = parseInt(matchLengthSelect.value) || 5;
                                const scoreValue = parseInt(value) || 0;
                                if (scoreValue > matchLength) {
                                    // Don't allow selection of score greater than match length
                                    return;
                                }
                            }
                        }

                        select.value = value;

                        // Update button text
                        if (selector.id === 'max-cube-select' || selector.id === 'max-cube-select-m') {
                            // For max cube, display the actual cube value (not the option value)
                            button.textContent = option.textContent;
                        } else {
                            button.textContent = value;
                        }

                        select.dispatchEvent(new Event('change'));

                        // Filter score options if match length changed
                        if (selector.id === 'match_lenght') {
                            filterScoreOptions();
                        }

                        // Update game type label if match length or scores changed
                        if (selector.id === 'match_lenght' || selector.id === 'lower-score' || selector.id === 'upper-score') {
                            updateGameTypeLabel();
                        }

                        dropdown.classList.remove('active');
                    });
                });
            });
        }

        // Filter cube options based on max cube value
        function filterCubeOptions() {
            const isMatch = (typeof currentGameType !== 'undefined' && currentGameType === 'матч');
            const maxCubeSelect = isMatch ?
                document.getElementById('max-cube-select') :
                document.getElementById('max-cube-select-m');

            if (!maxCubeSelect) return;

            // Get max cube value (option text, not value)
            const maxCubeValue = parseInt(maxCubeSelect.options[maxCubeSelect.selectedIndex].text);

            // Filter cube-shown dropdown options
            const cubeShownDropdown = document.getElementById('cube-shown-dropdown');
            const cubeShownSelect = document.getElementById('cube-shown-select');
            if (cubeShownDropdown && cubeShownSelect) {
                cubeShownDropdown.querySelectorAll('.cube-option').forEach(option => {
                    const value = parseInt(option.getAttribute('data-value'));
                    if (value > maxCubeValue) {
                        option.style.display = 'none';
                    } else {
                        option.style.display = '';
                    }
                });

                // Check if current value exceeds max cube
                const currentValue = parseInt(cubeShownSelect.value);
                if (currentValue > maxCubeValue) {
                    cubeShownSelect.value = maxCubeValue.toString();
                    document.getElementById('cube-value-select').value = getPrevCubeValue(maxCubeValue).toString();
                    updateCubeSelectorDisplay('shown');
                    updateCubeSelectorDisplay('value');
                }
            }

            // Filter cube-value dropdown options
            const cubeValueDropdown = document.getElementById('cube-value-dropdown');
            const cubeValueSelect = document.getElementById('cube-value-select');
            if (cubeValueDropdown && cubeValueSelect) {
                cubeValueDropdown.querySelectorAll('.cube-option').forEach(option => {
                    const value = parseInt(option.getAttribute('data-value'));
                    if (value > maxCubeValue) {
                        option.style.display = 'none';
                    } else {
                        option.style.display = '';
                    }
                });

                // Check if current value exceeds max cube
                const currentValue = parseInt(cubeValueSelect.value);
                if (currentValue > maxCubeValue) {
                    cubeValueSelect.value = maxCubeValue.toString();
                    updateCubeSelectorDisplay('value');
                }
            }
        }

        // Filter score options based on match length
        function filterScoreOptions() {
            const matchLengthSelect = document.getElementById('match_lenght');
            if (!matchLengthSelect) return;

            const matchLength = parseInt(matchLengthSelect.value) || 5;

            // Filter lower score dropdown options
            const lowerScoreDropdown = document.getElementById('lower-score-dropdown');
            const lowerScoreSelect = document.getElementById('lower-score');
            const lowerScoreButton = document.getElementById('lower-score-button');
            if (lowerScoreDropdown && lowerScoreSelect) {
                lowerScoreDropdown.querySelectorAll('.match-option').forEach(option => {
                    const value = parseInt(option.getAttribute('data-value'));
                    if (value > matchLength) {
                        option.style.display = 'none';
                    } else {
                        option.style.display = '';
                    }
                });

                // Check if current value exceeds match length
                const currentValue = parseInt(lowerScoreSelect.value) || 0;
                if (currentValue > matchLength) {
                    lowerScoreSelect.value = matchLength.toString();
                    if (lowerScoreButton) {
                        lowerScoreButton.textContent = matchLength.toString();
                    }
                    lowerScoreSelect.dispatchEvent(new Event('change'));
                }
            }

            // Filter upper score dropdown options
            const upperScoreDropdown = document.getElementById('upper-score-dropdown');
            const upperScoreSelect = document.getElementById('upper-score');
            const upperScoreButton = document.getElementById('upper-score-button');
            if (upperScoreDropdown && upperScoreSelect) {
                upperScoreDropdown.querySelectorAll('.match-option').forEach(option => {
                    const value = parseInt(option.getAttribute('data-value'));
                    if (value > matchLength) {
                        option.style.display = 'none';
                    } else {
                        option.style.display = '';
                    }
                });

                // Check if current value exceeds match length
                const currentValue = parseInt(upperScoreSelect.value) || 0;
                if (currentValue > matchLength) {
                    upperScoreSelect.value = matchLength.toString();
                    if (upperScoreButton) {
                        upperScoreButton.textContent = matchLength.toString();
                    }
                    upperScoreSelect.dispatchEvent(new Event('change'));
                }
            }
        }

        // Add event listeners for max cube changes
        document.getElementById('max-cube-select').addEventListener('change', filterCubeOptions);
        document.getElementById('max-cube-select-m').addEventListener('change', filterCubeOptions);

        document.getElementById('dice1-select').addEventListener('change', () => {
            handleDiceChange('dice1-select', 'dice2-select');
            updateDiceSelectorDisplay(1);
        });
        document.getElementById('dice2-select').addEventListener('change', () => {
            handleDiceChange('dice2-select', 'dice1-select');
            updateDiceSelectorDisplay(2);
        });
        // DEBUG: XGID - удалить потом
        // function showXGID(xgid) {
        //     document.getElementById('xgid-text').textContent = xgid;
        //     document.getElementById('xgid-display').style.display = 'block';
        // }
        // function hideXGID() {
        //     document.getElementById('xgid-display').style.display = 'none';
        // }
        // document.getElementById('xgid-close').addEventListener('click', hideXGID);

        /**
         * Парсит GNU move строку и возвращает удобный объект для получения информации о ходах.
         * 
         *   - moves: массив всех ходов, каждый элемент - объект с ключами from, to, hit
         *   - fromPositions: массив всех позиций, откуда пошли шашки (без дубликатов, отсортирован)
         *   - toPositions: массив всех позиций, куда пошли шашки (без дубликатов, отсортирован)
         *   - hitPositions: массив позиций, где были хиты (без дубликатов, отсортирован)
         *   - totalMoves: общее количество ходов
         *   - hasHits: true если есть хотя бы один хит
         *   - fromBar: true если есть ход с бара
         *   - toOff: true если есть ход в дом (off)
         * 
         * parseGnuMoveToDict("24/22 13/8")
         * // Returns: {
         * //   moves: [{from: 24, to: 22, hit: false}, {from: 13, to: 8, hit: false}],
         * //   fromPositions: [13, 24],
         * //   toPositions: [8, 22],
         * //   hitPositions: [],
         * //   totalMoves: 2,
         * //   hasHits: false,
         * //   fromBar: false,
         * //   toOff: false
         * // }
         */
        function parseGnuMoveToDict(gnuMoveStr) {
            if (!gnuMoveStr || !gnuMoveStr.trim()) {
                return {
                    moves: [],
                    fromPositions: [],
                    toPositions: [],
                    hitPositions: [],
                    totalMoves: 0,
                    hasHits: false,
                    fromBar: false,
                    toOff: false
                };
            }

            // Нормализуем: убираем пробел перед * (например "13/8 *" -> "13/8*"), чтобы хит учитывался.
            // Форматы: "13/11 7/2*" (два хода, хит на 2) или "13/7/2*" (цепочка 13→7→2 с хитом на 2)
            const normalizedStr = gnuMoveStr.trim().replace(/\s+\*/g, '*');
            const parts = normalizedStr.split(/\s+/);
            const moves = [];

            for (const part of parts) {
                let movePart = part;
                let hit = false;

                // Часть только "*" — хит относится к последнему ходу (предыдущая часть)
                if (movePart === '*' && moves.length > 0) {
                    moves[moves.length - 1].hit = true;
                    continue;
                }

                // Проверяем наличие звездочки в конце (хит)
                if (movePart.endsWith('*')) {
                    hit = true;
                    movePart = movePart.slice(0, -1);
                }

                // Извлекаем количество (например, "24/22(2)")
                let count = 1;
                let base = movePart;
                if (movePart.includes('(') && movePart.endsWith(')')) {
                    const lastParen = movePart.lastIndexOf('(');
                    base = movePart.substring(0, lastParen);
                    const countStr = movePart.substring(lastParen + 1, movePart.length - 1);
                    count = parseInt(countStr, 10) || 1;
                }

                // Разбиваем на сегменты по "/"
                const segments = base.split('/').filter(s => s.length > 0).map(s => s.toLowerCase());
                if (segments.length === 0) {
                    continue;
                }

                // Парсим начальную позицию
                let frStr = segments[0];
                let hitFr = false;
                if (frStr.endsWith('*')) {
                    hitFr = true;
                    frStr = frStr.slice(0, -1);
                }

                let fr;
                if (frStr === 'bar') {
                    fr = 25;
                } else if (frStr === 'off') {
                    fr = 0;
                } else {
                    const num = parseInt(frStr, 10);
                    if (isNaN(num)) {
                        continue;
                    }
                    fr = num;
                }

                // Обрабатываем каждый сегмент пути (prev и lastToInPart — в области видимости части)
                let lastToInPart = fr;
                for (let i = 0; i < count; i++) {
                    let prev = fr;
                    for (let j = 1; j < segments.length; j++) {
                        let seg = segments[j];
                        let hitSeg = false;
                        if (seg.endsWith('*')) {
                            hitSeg = true;
                            seg = seg.slice(0, -1);
                        }

                        let to;
                        if (seg === 'bar') {
                            to = 25;
                        } else if (seg === 'off') {
                            to = 0;
                        } else {
                            const num = parseInt(seg, 10);
                            if (isNaN(num)) {
                                break;
                            }
                            to = num;
                        }

                        moves.push({
                            from: prev,
                            to: to,
                            hit: hitSeg
                        });
                        prev = to;
                        lastToInPart = to;
                    }
                }

                // Применяем хиты
                if (hitFr && moves.length > 0) {
                    // Находим первый ход с этой начальной позицией
                    for (let i = 0; i < moves.length; i++) {
                        if (moves[i].from === fr) {
                            moves[i].hit = true;
                            break;
                        }
                    }
                }

                if (hit && moves.length > 0) {
                    // Находим последний ход с этой конечной позицией (хит в конце части, напр. 7/2* или 13/7/2*)
                    for (let i = moves.length - 1; i >= 0; i--) {
                        if (moves[i].to === lastToInPart) {
                            moves[i].hit = true;
                            break;
                        }
                    }
                }
            }

            if (moves.length === 0) {
                return {
                    moves: [],
                    fromPositions: [],
                    toPositions: [],
                    hitPositions: [],
                    totalMoves: 0,
                    hasHits: false,
                    fromBar: false,
                    toOff: false
                };
            }

            // Извлекаем уникальные позиции
            const fromPositionsSet = new Set();
            const toPositionsSet = new Set();
            const hitPositionsSet = new Set();

            for (const move of moves) {
                fromPositionsSet.add(move.from);
                toPositionsSet.add(move.to);
                if (move.hit) {
                    hitPositionsSet.add(move.to);
                }
            }

            const fromPositions = Array.from(fromPositionsSet).sort((a, b) => a - b);
            const toPositions = Array.from(toPositionsSet).sort((a, b) => a - b);
            const hitPositions = Array.from(hitPositionsSet).sort((a, b) => a - b);

            // Проверяем специальные случаи
            const hasHits = hitPositions.length > 0;
            const fromBar = fromPositions.includes(25);
            const toOff = toPositions.includes(0);

            return {
                moves: moves,
                fromPositions: fromPositions,
                toPositions: toPositions,
                hitPositions: hitPositions,
                totalMoves: moves.length,
                hasHits: hasHits,
                fromBar: fromBar,
                toOff: toOff
            };
        }

        /**
         * Применяет ход к позициям на доске
         * @param {string} gnuMoveStr - строка GNU move
         * @param {string} playerColor - цвет игрока ('white' или 'black')
         */
        function applyMoveToBoard(gnuMoveStr, playerColor) {
            if (!gnuMoveStr || !gnuMoveStr.trim()) {
                return;
            }

            const moveData = parseGnuMoveToDict(gnuMoveStr);
            if (moveData.totalMoves === 0) {
                return;
            }

            const positionsBefore = snapshotPositions();
            const turnBefore = document.getElementById('turn-select')?.value || 'white';

            // Определяем позиции игрока и противника
            const playerPositions = playerColor === 'white' ? positions.first : positions.second;
            const opponentPositions = playerColor === 'white' ? positions.second : positions.first;

            // Функция для инверсии координат точки
            function invertPoint(point) {
                if (point === 0 || point === 25) {
                    return point;
                }
                return 25 - point;
            }

            // Определяем нужно ли инвертировать координаты
            const needInvert = (playerColor === 'white' && upperPlayerColor === 'white') ||
                (playerColor === 'black' && upperPlayerColor === 'black');

            // Применяем каждый ход
            for (const move of moveData.moves) {
                let from = move.from;
                let to = move.to;

                // Инвертируем координаты если нужно
                if (needInvert) {
                    from = invertPoint(from);
                    to = invertPoint(to);
                }

                // Обрабатываем ход с бара
                if (from === 25) {
                    const barCount = playerPositions.bar || 0;
                    if (barCount > 0) {
                        if (barCount === 1) {
                            delete playerPositions.bar;
                        } else {
                            playerPositions.bar = barCount - 1;
                        }
                    }
                } else {
                    // Убираем шашку с начальной позиции
                    const fromKey = from.toString();
                    const fromCount = playerPositions[fromKey] || 0;
                    if (fromCount > 1) {
                        playerPositions[fromKey] = fromCount - 1;
                    } else if (fromCount === 1) {
                        delete playerPositions[fromKey];
                    }
                }

                // Обрабатываем хит
                if (move.hit && to !== 0 && to !== 25) {
                    const toKey = to.toString();
                    const opponentCount = opponentPositions[toKey] || 0;
                    if (opponentCount > 0) {
                        // Убираем шашку противника
                        if (opponentCount === 1) {
                            delete opponentPositions[toKey];
                        } else {
                            opponentPositions[toKey] = opponentCount - 1;
                        }
                        // Добавляем на бар противника
                        opponentPositions.bar = (opponentPositions.bar || 0) + 1;
                    }
                }

                // Добавляем шашку на конечную позицию
                if (to === 25) {
                    // На бар (не должно происходить в нормальном ходе)
                    playerPositions.bar = (playerPositions.bar || 0) + 1;
                } else if (to === 0) {
                    // В дом (off) - не храним отдельно, просто убираем с доски
                } else {
                    const toKey = to.toString();
                    playerPositions[toKey] = (playerPositions[toKey] || 0) + 1;
                }
            }

            // Обновляем селекты и перерисовываем доску
            updateSelectOptions(playerColor);
            updateBarSelects();
            drawBoard();
        }

        document.getElementById('show-button').addEventListener('click', () => {
            // Сохраняем снимок: все позиции шашек (first, second) и чей ход был сделан
            showButtonSnapshot = {
                positions: {
                    first: { ...positions.first },
                    second: { ...positions.second }
                },
                turn: document.getElementById('turn-select').value
            };

            // Записываем текущую позицию в историю при генерации доски
            if (historyIndex < moveHistory.length) {
                clearMoveHistory();
            }
            const snap = snapshotPositions();
            const currentTurn = document.getElementById('turn-select').value;
            const isMatch = currentGameType === 'матч';
            recordMove({
                positionsBefore: { first: { ...snap.first }, second: { ...snap.second } },
                positionsAfter: { first: { ...snap.first }, second: { ...snap.second } },
                move: null,
                playerColor: null,
                turnBefore: currentTurn,
                turnAfter: currentTurn,
                dice: {
                    dice1: document.getElementById('dice1-select').value,
                    dice2: document.getElementById('dice2-select').value
                },
                cubeState: {
                    cubeValue: document.getElementById('cube-value-select').value,
                    cubeShown: document.getElementById('cube-shown-select').value,
                    cubeOwner: document.getElementById('cube-owner-select').value,
                    maxCube: (isMatch ? document.getElementById('max-cube-select') : document.getElementById('max-cube-select-m'))?.value || '3'
                }
            });
            historyIndex = moveHistory.length;
            updateHistoryButtons();

            const xgid = generateXGID();
            // showXGID(xgid); // DEBUG - удалить потом
            const hintsTable = document.getElementById('hintsTable');
            const hintsTableContainer = document.querySelector('.hints-table');

            if (!hintsTable || !hintsTableContainer) {
                alert('Error: Required elements not found');
                return;
            }

            // Получаем chat_id из Telegram WebApp
            let chatId = null;
            if (window.Telegram && window.Telegram.WebApp) {
                const initDataUnsafe = window.Telegram.WebApp.initDataUnsafe;
                chatId = initDataUnsafe && initDataUnsafe.user ? initDataUnsafe.user.id : null;
            }

            // Проверяем наличие chat_id (для отладки можно использовать тестовый ID)
            if (!chatId && !isWebStandalonePokaz()) {
                // Попробуем получить из URL параметра (для тестирования)
                const urlParams = new URLSearchParams(window.location.search);
                chatId = urlParams.get('chat_id');

                if (!chatId) {
                    alert('Не удалось получить chat_id. Запустите приложение через Telegram.');
                    return;
                }
            }

            hintsTable.innerHTML = '<div class="loading">' + ((window.POKAZ_I18N || {}).loading_hints || 'Поиск лучших ходов') + '</div>';
            hintsTable.classList.add('active');
            hintsTableContainer.classList.add('active');
            const hintsUrl = isWebStandalonePokaz()
                ? `/web/pokaz/api/hints?xgid=${encodeURIComponent(xgid)}`
                : `/pokaz/hints?xgid=${encodeURIComponent(xgid)}&chat_id=${chatId}`;
            console.log('Requesting hints with chat_id:', chatId, 'xgid:', xgid);
            fetch(hintsUrl, { signal: AbortSignal.timeout(30000) }) // 30 second timeout
                .then(response => {
                    console.log('Response status:', response.status);
                    if (!response.ok) {
                        const i18n = window.POKAZ_I18N || {};
                        if (response.status === 401) {
                            window.location.href = '/web/hints/login?next=/web/pokaz';
                            throw new Error('Нужна авторизация');
                        }
                        if (response.status === 402) {
                            throw new Error(i18n.error_insufficient_balance || 'Недостаточно баланса для получения подсказок');
                        }
                        if (response.status === 400) {
                            throw new Error(i18n.error_no_chat_id || 'Отсутствует chat_id. Запустите через Telegram.');
                        }
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    const hintsData = { hints: data.hints || [] };
                    latestHintsData = hintsData;
                    if (moveHistory.length > 0) {
                        moveHistory[moveHistory.length - 1].hintsData = hintsData;
                    }
                    const entry = moveHistory.length > 0 ? moveHistory[moveHistory.length - 1] : null;
                    if (entry) {
                        showButtonSnapshot = {
                            positions: { first: { ...entry.positionsAfter.first }, second: { ...entry.positionsAfter.second } },
                            turn: entry.turnAfter
                        };
                    }
                    const { html, firstHint } = buildHintsTableFromData(hintsData, entry ? entry.selectedHintIndex : undefined);
                    hintsTable.innerHTML = html;
                    hintsTable.classList.add('active');
                    hintsTableContainer.classList.add('active');
                    if (firstHint && firstHint.type === 'move' && entry) {
                        attachHintsTableEyeButtons(hintsTable, showButtonSnapshot, entry);
                    }
                    if (firstHint && firstHint.type === 'cube_hint') {
                        attachCubeTableEyeButtons(hintsTable);
                    }
                    if (typeof updateGameTypeButtonMode === 'function') updateGameTypeButtonMode();
                })
                .catch(error => {
                    const hintsData = { error: error.message };
                    latestHintsData = null;
                    if (moveHistory.length > 0) {
                        moveHistory[moveHistory.length - 1].hintsData = hintsData;
                    }
                    const { html } = buildHintsTableFromData(hintsData);
                    hintsTable.innerHTML = html;
                    hintsTable.classList.add('active');
                    hintsTableContainer.classList.add('active');
                });
        });

        // Modal window functions
        const clearModal = document.getElementById('clear-modal');
        const modalCancel = document.getElementById('modal-cancel');
        const modalConfirm = document.getElementById('modal-confirm');

        function showClearModal() {
            clearModal.classList.add('active');
        }

        function hideClearModal() {
            clearModal.classList.remove('active');
        }

        function performClear() {
            clearMoveHistory();
            positions = {
                first: {},
                second: {}
            };

            setSelectedCheckerColor('white');
            document.getElementById('white-bar-select').value = '0';
            document.getElementById('black-bar-select').value = '0';
            currentGameType = 'манигейм';
            document.getElementById('game-type-button').innerHTML = '<i class="fa fa-rub"></i>';
            document.getElementById('game-type-button').title = (window.POKAZ_I18N || {}).moneygame || 'Манигейм';

            // Update game type label
            updateGameTypeLabel();
            document.getElementById('lower-score').value = '0';
            document.getElementById('upper-score').value = '0';
            document.getElementById('match_lenght').value = '5';
            document.getElementById('max-cube-select').value = '3';
            document.getElementById('jacobi-select').value = '1';
            document.getElementById('beaver-select').value = '0';
            document.querySelectorAll('.toggle-btn').forEach(btn => {
                const el = document.getElementById(btn.dataset.target);
                if (el) {
                    const val = el.value;
                    const yesText = window.POKAZ_YES || ((window.POKAZ_I18N || {}).yes || 'Да');
                    const noText = window.POKAZ_NO || ((window.POKAZ_I18N || {}).no || 'Нет');
                    btn.textContent = val === '1' ? yesText : noText;
                    btn.classList.toggle('on', val === '1');
                }
            });
            document.getElementById('max-cube-select-m').value = '3';
            document.getElementById('cube-shown-select').value = '0';
            document.getElementById('cube-value-select').value = '0';
            document.getElementById('dice1-select').value = '0';
            document.getElementById('dice2-select').value = '0';
            updateCubeSelectorsVisibility();
            updateAllDiceSelectors();
            updateAllCubeSelectors();

            document.getElementById('turn-select').value = 'white';
            document.getElementById('cube-owner-select').value = 'white';
            updateTurnSelect();
            updateCubeOwnerSelect();
            updateSelectOptions('white');
            updateBarSelects();

            for (let point = 1; point <= 24; point++) {
                document.getElementById(`point-${point}`).value = '0';
            }

            const matchPanel = document.querySelector('.match-panel');
            const jbWrap = document.querySelector('.jb-wrap');
            if (matchPanel) matchPanel.style.display = 'none';
            if (jbWrap) jbWrap.style.display = 'flex';
            if (typeof setCrawfordControlsVisible === 'function') {
                setCrawfordControlsVisible(false);
            }

            const hintsTableContainer = document.querySelector('.hints-table');
            const hintsTable = document.getElementById('hintsTable');
            hintsTableContainer.classList.remove('active');
            hintsTable.classList.remove('active');
            if (typeof updateGameTypeButtonMode === 'function') updateGameTypeButtonMode();

            // hideXGID(); // DEBUG - удалить потом
            drawBoard();
            hideClearModal();
        }

        // Clear button logic - show modal
        document.getElementById('clear-button').addEventListener('click', () => {
            showClearModal();
        });

        // Modal cancel button
        modalCancel.addEventListener('click', () => {
            hideClearModal();
        });

        // Modal confirm button
        modalConfirm.addEventListener('click', () => {
            performClear();
        });

        // Close modal on background click
        clearModal.addEventListener('click', (e) => {
            if (e.target === clearModal) {
                hideClearModal();
            }
        });

        // Close modal on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && clearModal.classList.contains('active')) {
                hideClearModal();
            }
            if (e.key === 'Escape' && initModal.classList.contains('active')) {
                hideInitModal();
            }
        });

        // Init modal functions
        const initModal = document.getElementById('init-modal');
        const initModalCancel = document.getElementById('init-modal-cancel');
        const initModalConfirm = document.getElementById('init-modal-confirm');

        function showInitModal() {
            initModal.classList.add('active');
        }

        function hideInitModal() {
            initModal.classList.remove('active');
        }

        function performInit() {
            clearMoveHistory();
            // Standard starting positions for backgammon
            const standardWhitePos = { 6: 5, 8: 3, 13: 5, 24: 2 };
            const standardBlackPos = { 1: 2, 12: 5, 17: 3, 19: 5 };

            // If upper player is white, invert positions
            if (upperPlayerColor === 'white') {
                positions.first = { ...standardBlackPos };
                positions.second = { ...standardWhitePos };
            } else {
                positions.first = { ...standardWhitePos };
                positions.second = { ...standardBlackPos };
            }

            setSelectedCheckerColor('white');
            document.getElementById('white-bar-select').value = '0';
            document.getElementById('black-bar-select').value = '0';
            document.getElementById('cube-shown-select').value = '0';
            document.getElementById('cube-value-select').value = '0';
            document.getElementById('dice1-select').value = '0';
            document.getElementById('dice2-select').value = '0';
            updateCubeSelectorsVisibility();
            updateAllDiceSelectors();
            updateAllCubeSelectors();

            updateSelectOptions('white');
            updateBarSelects();

            for (let point = 1; point <= 24; point++) {
                const select = document.getElementById(`point-${point}`);
                select.value = positions.first[point.toString()] || 0;
            }

            const hintsTableContainer = document.querySelector('.hints-table');
            const hintsTable = document.getElementById('hintsTable');
            hintsTableContainer.classList.remove('active');
            hintsTable.classList.remove('active');
            if (typeof updateGameTypeButtonMode === 'function') updateGameTypeButtonMode();

            // hideXGID(); // DEBUG - удалить потом
            drawBoard();
            hideInitModal();
        }

        // Init button logic - show modal
        document.getElementById('init-button').addEventListener('click', () => {
            showInitModal();
        });

        // Init modal cancel button
        initModalCancel.addEventListener('click', () => {
            hideInitModal();
        });

        // Init modal confirm button
        initModalConfirm.addEventListener('click', () => {
            performInit();
        });

        // Close init modal on background click
        initModal.addEventListener('click', (e) => {
            if (e.target === initModal) {
                hideInitModal();
            }
        });

        document.querySelectorAll('.toggle-btn').forEach(btn => {
            btn.addEventListener('click', function () {
                const el = document.getElementById(this.dataset.target);
                if (!el) return;
                const next = el.value === '1' ? '0' : '1';
                el.value = next;
                const yesText = window.POKAZ_YES || ((window.POKAZ_I18N || {}).yes || 'Да');
                const noText = window.POKAZ_NO || ((window.POKAZ_I18N || {}).no || 'Нет');
                this.textContent = next === '1' ? yesText : noText;
                this.classList.toggle('on', next === '1');
            });
        });

        // Mode toggle button for placing/removing checkers
        let currentMode = 'place'; // 'place' or 'delete'
        const modeToggleBtn = document.getElementById('modeToggleBtn');

        modeToggleBtn.addEventListener('click', () => {
            const deleteTitle = (window.POKAZ_I18N || {}).delete_checkers || 'Удаление шашек';
            const placeTitle = (window.POKAZ_I18N || {}).place_checkers || 'Установка шашек';
            if (currentMode === 'place') {
                currentMode = 'delete';
                modeToggleBtn.classList.add('delete-mode');
                modeToggleBtn.innerHTML = '<i class="fa fa-times"></i>';
                modeToggleBtn.title = deleteTitle;
            } else {
                currentMode = 'place';
                modeToggleBtn.classList.remove('delete-mode');
                modeToggleBtn.innerHTML = '<i class="fa fa-mouse-pointer"></i>';
                modeToggleBtn.title = placeTitle;
            }
        });

        // Hide pips checkbox handler
        const hidePipsCheckbox = document.getElementById('hidePipsCheckbox');
        if (hidePipsCheckbox) {
            // restore state from localStorage
            const savedPips = localStorage.getItem('hidePipsCheckbox');
            if (savedPips === 'true') hidePipsCheckbox.checked = true;
            hidePipsCheckbox.addEventListener('change', () => {
                localStorage.setItem('hidePipsCheckbox', hidePipsCheckbox.checked);
                drawBoard();
            });
        }
        // when either checkbox toggles, redraw pips
        if (hidePointDropdownsCheckbox) {
            hidePointDropdownsCheckbox.addEventListener('change', drawBoard);
        }

        const invertNumberingCheckbox = document.getElementById('invertNumberingCheckbox');
        if (invertNumberingCheckbox) {
            invertNumberingCheckbox.addEventListener('change', drawBoard);
        }

        // Lower player toggle button handler (показывает нижнего игрока)
        const lowerPlayerButton = document.getElementById('lowerPlayerButton');
        if (lowerPlayerButton) {
            lowerPlayerButton.addEventListener('click', () => {
                // Toggle - кнопка показывает нижнего игрока (противоположный upperPlayerColor)
                if (upperPlayerColor === 'white') {
                    // Было: белые сверху, черные снизу
                    // Станет: черные сверху, белые снизу
                    upperPlayerColor = 'black';
                    lowerPlayerButton.classList.remove('black');
                    lowerPlayerButton.classList.add('white');
                    lowerPlayerButton.setAttribute('data-color', 'white');
                } else {
                    // Было: черные сверху, белые снизу
                    // Станет: белые сверху, черные снизу
                    upperPlayerColor = 'white';
                    lowerPlayerButton.classList.remove('white');
                    lowerPlayerButton.classList.add('black');
                    lowerPlayerButton.setAttribute('data-color', 'black');
                }
                swapCheckerColors();
                swapTurnAndCubeColors();
                // Автоматически выбрать соответствующую шашку в checker-selector
                const newLowerColor = lowerPlayerButton.dataset.color;
                setSelectedCheckerColor(newLowerColor);
                updateSelectOptions(newLowerColor);
                for (let point = 1; point <= 24; point++) {
                    const select = document.getElementById(`point-${point}`);
                    const targetPositions = newLowerColor === 'white' ? positions.first : positions.second;
                    if (select) select.value = targetPositions[point.toString()] || 0;
                }
                const whiteBarSelect = document.getElementById('white-bar-select');
                const blackBarSelect = document.getElementById('black-bar-select');
                if (whiteBarSelect) whiteBarSelect.value = String(positions.first.bar || 0);
                if (blackBarSelect) blackBarSelect.value = String(positions.second.bar || 0);
                updateBarSelects();
                updateBoard();
            });
        }

        // Crawford checkbox handler
        const crawfordCheckbox = document.getElementById('crawford-checkbox');
        const crawfordLabel = document.getElementById('crawford-label');
        const crawfordWrapper = document.querySelector('.crawford-checkbox-wrapper');
        const cubeControlsBlockWrapper = document.querySelector('.cube-controls-block-wrapper');

        function setCrawfordControlsVisible(visible) {
            if (crawfordLabel) crawfordLabel.style.display = visible ? '' : 'none';
            if (crawfordWrapper) crawfordWrapper.style.display = visible ? 'flex' : 'none';
            if (cubeControlsBlockWrapper) {
                cubeControlsBlockWrapper.classList.toggle('has-crawford', !!visible);
            }
        }

        if (crawfordCheckbox) {
            crawfordCheckbox.addEventListener('change', () => {
                const cubeShownButton = document.getElementById('cube-shown-button');
                const cubeShownDropdown = document.getElementById('cube-shown-dropdown');
                const cubeValueButton = document.getElementById('cube-value-button');
                const cubeValueDropdown = document.getElementById('cube-value-dropdown');
                const cubeOwnerBtn = document.getElementById('cube-owner-select-btn');

                if (crawfordCheckbox.checked) {
                    // Close all cube dropdowns
                    cubeShownDropdown.classList.remove('active');
                    cubeValueDropdown.classList.remove('active');

                    // Show cube-value-options and label
                    const cubeValueOptions = document.querySelector('.cube-value-options');
                    const cubeValueLabel = document.querySelector('.cube-controls-labels label[for="cube-value-select"]');
                    if (cubeValueOptions) cubeValueOptions.style.display = '';
                    if (cubeValueLabel) cubeValueLabel.style.display = '';

                    // Show dice section
                    const diceSection = document.querySelectorAll('.turn-dice-section')[1];
                    const diceLabel = document.querySelectorAll('.turn-dice-labels label')[1];
                    if (diceSection) diceSection.style.display = '';
                    if (diceLabel) diceLabel.style.display = '';

                    // Block and clear all cube controls
                    cubeShownButton.style.pointerEvents = 'none';
                    cubeShownButton.style.opacity = '0.5';
                    cubeValueButton.style.pointerEvents = 'none';
                    cubeValueButton.style.opacity = '0.5';
                    cubeOwnerBtn.style.pointerEvents = 'none';
                    cubeOwnerBtn.style.opacity = '0.5';

                    // Clear values
                    document.getElementById('cube-shown-select').value = '0';
                    document.getElementById('cube-value-select').value = '0';
                    document.getElementById('cube-owner-select').value = 'white';

                    // Update displays
                    {
                        const noText = window.POKAZ_NO || ((window.POKAZ_I18N || {}).no || 'Нет');
                        cubeShownButton.textContent = noText;
                        cubeShownButton.classList.add('empty');
                    }
                    {
                        const noText = window.POKAZ_NO || ((window.POKAZ_I18N || {}).no || 'Нет');
                        cubeValueButton.textContent = noText;
                        cubeValueButton.classList.add('empty');
                    }
                    cubeOwnerBtn.classList.remove('black');
                    cubeOwnerBtn.classList.add('white');
                    cubeOwnerBtn.setAttribute('data-color', 'white');

                    drawBoard();
                } else {
                    // Unblock cube controls
                    cubeShownButton.style.pointerEvents = '';
                    cubeShownButton.style.opacity = '';
                    cubeValueButton.style.pointerEvents = '';
                    cubeValueButton.style.opacity = '';
                    cubeOwnerBtn.style.pointerEvents = '';
                    cubeOwnerBtn.style.opacity = '';

                    // Restore proper visibility based on cube-shown value
                    updateCubeSelectorsVisibility();
                }
            });
        }

        // При открытой доске: скрыть selectors-wrapper и controls-row, показать board-open-controls
        // Управление — всегда под доской; скриншоты — слева от стрелок; aux на широких — под доской
        function relocateScreenshotControls(boardOpen) {
            const screenshotControls = document.getElementById('screenshotControls');
            const boardOpenControls = document.getElementById('boardOpenControls');
            const auxPanel = document.querySelector('.pokaz-aux-panel');
            const spacer = boardOpenControls
                ? boardOpenControls.querySelector('.board-open-controls-spacer')
                : null;
            if (!screenshotControls || !boardOpenControls || !auxPanel) return;

            if (boardOpen) {
                const historyNav = boardOpenControls.querySelector('.history-nav');
                const buttons = boardOpenControls.querySelector('.board-open-controls-buttons');
                const screenshotAnchor = historyNav || buttons;
                if (screenshotControls.parentElement !== boardOpenControls
                    || (screenshotAnchor && screenshotControls.nextElementSibling !== screenshotAnchor)) {
                    if (screenshotAnchor) {
                        boardOpenControls.insertBefore(screenshotControls, screenshotAnchor);
                    } else {
                        boardOpenControls.insertBefore(screenshotControls, boardOpenControls.firstChild);
                    }
                }
                if (spacer) spacer.style.display = 'none';
            } else {
                if (screenshotControls.parentElement !== auxPanel) {
                    auxPanel.insertBefore(screenshotControls, auxPanel.firstChild);
                }
                if (spacer) spacer.style.display = '';
            }
        }

        function relocateHistoryNav(boardOpen) {
            const boardOpenControls = document.getElementById('boardOpenControls');
            const historyNav = document.querySelector('.history-nav');
            const mainStage = document.querySelector('.pokaz-main-stage');
            const boardWrapper = mainStage ? mainStage.querySelector('.board-wrapper') : null;
            if (!boardOpenControls || !historyNav || !boardWrapper) return;

            const isPhone = window.matchMedia('(max-width: 600px)').matches;
            const placeUnderPips = !!(boardOpen && isPhone);

            if (placeUnderPips) {
                const redPips = document.getElementById('red-pips');
                const afterPips = redPips && redPips.parentElement === boardWrapper
                    ? redPips.nextSibling
                    : null;
                if (historyNav.parentElement !== boardWrapper || historyNav.previousElementSibling !== redPips) {
                    if (redPips && redPips.parentElement === boardWrapper) {
                        boardWrapper.insertBefore(historyNav, afterPips);
                    } else {
                        boardWrapper.appendChild(historyNav);
                    }
                }
                boardWrapper.classList.add('has-mobile-history-nav');
            } else {
                if (historyNav.parentElement !== boardOpenControls) {
                    const buttons = boardOpenControls.querySelector('.board-open-controls-buttons');
                    if (buttons) {
                        boardOpenControls.insertBefore(historyNav, buttons);
                    } else {
                        boardOpenControls.appendChild(historyNav);
                    }
                }
                boardWrapper.classList.remove('has-mobile-history-nav');
            }
        }

        function relocatePokazOpenPanels(boardOpen, isWide) {
            const auxPanel = document.querySelector('.pokaz-aux-panel');
            const boardOpenControls = document.getElementById('boardOpenControls');
            const mainStage = document.querySelector('.pokaz-main-stage');
            const side = document.querySelector('.pokaz-side');
            const tools = document.querySelector('.pokaz-tools');
            const turnLabel = document.getElementById('turn-label');
            const boardWrapper = mainStage ? mainStage.querySelector('.board-wrapper') : null;
            if (!mainStage || !side || !tools) return;

            const placeControlsUnderBoard = !!boardOpen;
            const placeAuxUnderBoard = !!(boardOpen && isWide);

            if (placeControlsUnderBoard) {
                if (boardOpenControls) {
                    if (boardWrapper && boardWrapper.nextSibling !== boardOpenControls) {
                        mainStage.insertBefore(boardOpenControls, boardWrapper.nextSibling);
                    } else if (boardOpenControls.parentElement !== mainStage) {
                        mainStage.appendChild(boardOpenControls);
                    }
                }
            } else if (boardOpenControls && boardOpenControls.parentElement !== side) {
                if (turnLabel && turnLabel.parentElement === side) {
                    side.insertBefore(boardOpenControls, turnLabel);
                } else if (tools.parentElement === side) {
                    side.insertBefore(boardOpenControls, tools);
                } else {
                    side.appendChild(boardOpenControls);
                }
            }

            relocateHistoryNav(boardOpen);
            relocateScreenshotControls(boardOpen);

            if (placeAuxUnderBoard) {
                if (auxPanel && auxPanel.parentElement !== mainStage) {
                    mainStage.appendChild(auxPanel);
                } else if (auxPanel && boardOpenControls && auxPanel.previousElementSibling !== boardOpenControls) {
                    mainStage.appendChild(auxPanel);
                }
                tools.classList.add('is-aux-relocated');
            } else {
                if (auxPanel && auxPanel.parentElement !== tools) {
                    tools.appendChild(auxPanel);
                }
                tools.classList.remove('is-aux-relocated');
            }
        }

        function updateBoardOpenState() {
            const hintsTableContainer = document.getElementById('hintsTableContainer');
            const selectorsWrapper = document.querySelector('.selectors-wrapper');
            const controlsRow = document.querySelector('.controls-row');
            const boardOpenControls = document.getElementById('boardOpenControls');
            const container = document.querySelector('.container');
            if (!hintsTableContainer || !selectorsWrapper || !boardOpenControls) return;
            const isTableActive = hintsTableContainer.classList.contains('active');
            const isTableCollapsed = hintsTableContainer.classList.contains('collapsed');
            const isBoardOpen = isTableActive && !isTableCollapsed;
            const isWide = window.matchMedia('(min-width: 900px)').matches;
            if (container) {
                container.classList.toggle('pokaz-board-open', isBoardOpen);
            }
            if (isBoardOpen) {
                selectorsWrapper.style.display = 'none';
                if (controlsRow) controlsRow.style.display = 'none';
                boardOpenControls.classList.add('active');
                resetHintsTableCheckBtn();
                updateHistoryButtons();
            } else {
                selectorsWrapper.style.display = '';
                if (controlsRow) controlsRow.style.display = '';
                boardOpenControls.classList.remove('active');
            }
            relocatePokazOpenPanels(isBoardOpen, isWide);
        }

        window.addEventListener('resize', () => {
            if (typeof updateBoardOpenState === 'function') updateBoardOpenState();
        });

        // Кнопки навигации по истории
        document.getElementById('history-back-btn').addEventListener('click', goBackInHistory);
        document.getElementById('history-forward-btn').addEventListener('click', goForwardInHistory);

        // Сброс кнопки hints-table-check-btn в состояние OK
        function resetHintsTableCheckBtn() {
            const btn = document.getElementById('hints-table-check-btn');
            if (btn) {
                btn.innerHTML = 'OK';
                btn.classList.add('check-mode');
            }
        }

        // Кнопка hints-table-check-btn: OK -> иконка при клике
        document.getElementById('hints-table-check-btn').addEventListener('click', () => {
            const btn = document.getElementById('hints-table-check-btn');
            if (btn && btn.textContent.trim() === 'OK') {
                btn.innerHTML = '<i class="fa fa-check"></i>';
                btn.classList.remove('check-mode');
                const isCubeTable = document.querySelector('#hintsTable .cube-hints-table') !== null;
                if (!isCubeTable) {
                    const turnSelect = document.getElementById('turn-select');
                    if (turnSelect) {
                        turnSelect.value = turnSelect.value === 'white' ? 'black' : 'white';
                        updateTurnSelect();
                    }
                    const dice1Select = document.getElementById('dice1-select');
                    const dice2Select = document.getElementById('dice2-select');
                    if (dice1Select) dice1Select.value = '0';
                    if (dice2Select) dice2Select.value = '0';
                    if (typeof updateDiceSelectorDisplay === 'function') {
                        updateDiceSelectorDisplay(1);
                        updateDiceSelectorDisplay(2);
                    }
                }
                if (typeof drawBoard === 'function') drawBoard();
            }
        });

        // Кнопка зелёного глаза в board-open-controls — запуск анализа
        document.getElementById('board-open-eye-btn').addEventListener('click', () => {
            resetHintsTableCheckBtn();
            document.getElementById('show-button').click();
        });

        // Кнопка случайных кубиков в board-open-controls (без смены хода, без сброса hints-table-check-btn)
        document.getElementById('board-open-random-dice-btn').addEventListener('click', () => {
            const dice1 = Math.floor(Math.random() * 6) + 1;
            const dice2 = Math.floor(Math.random() * 6) + 1;
            const dice1Select = document.getElementById('dice1-select');
            const dice2Select = document.getElementById('dice2-select');
            if (dice1Select) dice1Select.value = dice1.toString();
            if (dice2Select) dice2Select.value = dice2.toString();
            if (typeof updateDiceSelectorDisplay === 'function') {
                updateDiceSelectorDisplay(1);
                updateDiceSelectorDisplay(2);
            }
            if (typeof drawBoard === 'function') drawBoard();
        });

        // Функция обновления кнопки: при открытой таблице подсказок — кнопка «Случайные кубики», иначе — переключатель манигейм/матч
        function updateGameTypeButtonMode() {
            updateBoardOpenState();
            const hintsTableContainer = document.getElementById('hintsTableContainer');
            const gameTypeButton = document.getElementById('game-type-button');
            if (!hintsTableContainer || !gameTypeButton) return;
            const isTableOpen = hintsTableContainer.classList.contains('active') && !hintsTableContainer.classList.contains('collapsed');
            if (isTableOpen) {
                gameTypeButton.innerHTML = '<i class="fa fa-random"></i>';
                gameTypeButton.title = (window.POKAZ_I18N || {}).random_dice || 'Случайные кубики';
                gameTypeButton.classList.add('dice-mode');
            } else {
                gameTypeButton.innerHTML = currentGameType === 'матч' ? '<i class="fa fa-trophy"></i>' : '<i class="fa fa-rub"></i>';
                const i18n = window.POKAZ_I18N || {};
                gameTypeButton.title = currentGameType === 'матч' ? (i18n.match || 'Матч') : (i18n.moneygame || 'Манигейм');
                gameTypeButton.classList.remove('dice-mode');
            }
        }
        window.updateGameTypeButtonMode = updateGameTypeButtonMode;

        // Game type button toggle between money game and match (или случайные кубики, если таблица подсказок открыта)
        document.getElementById('game-type-button').addEventListener('click', () => {
            const hintsTableContainer = document.getElementById('hintsTableContainer');
            const gameTypeButton = document.getElementById('game-type-button');
            const isTableOpen = hintsTableContainer && hintsTableContainer.classList.contains('active') && !hintsTableContainer.classList.contains('collapsed');

            if (isTableOpen) {
                // Режим случайных кубиков
                const dice1 = Math.floor(Math.random() * 6) + 1;
                const dice2 = Math.floor(Math.random() * 6) + 1;
                let newTurn;
                if (showButtonSnapshot && showButtonSnapshot.turn) {
                    newTurn = showButtonSnapshot.turn === 'white' ? 'black' : 'white';
                } else {
                    newTurn = Math.random() < 0.5 ? 'white' : 'black';
                }
                const dice1Select = document.getElementById('dice1-select');
                const dice2Select = document.getElementById('dice2-select');
                if (dice1Select) dice1Select.value = dice1.toString();
                if (dice2Select) dice2Select.value = dice2.toString();
                const turnSelect = document.getElementById('turn-select');
                if (turnSelect) {
                    turnSelect.value = newTurn;
                    updateTurnSelect();
                }
                if (typeof updateDiceSelectorDisplay === 'function') {
                    updateDiceSelectorDisplay(1);
                    updateDiceSelectorDisplay(2);
                }
                if (typeof drawBoard === 'function') drawBoard();
                return;
            }

            const jbWrap = document.querySelector('.jb-wrap');
            const matchPanel = document.querySelector('.match-panel');

            // Toggle visibility
            if (jbWrap.style.display === 'none') {
                // Switch to money game
                jbWrap.style.display = 'flex';
                matchPanel.style.display = 'none';
                gameTypeButton.innerHTML = '<i class="fa fa-rub"></i>';
                gameTypeButton.title = 'Манигейм';
                currentGameType = 'манигейм';

                // Update game type label
                updateGameTypeLabel();

                // Hide Crawford checkbox
                setCrawfordControlsVisible(false);
                if (crawfordCheckbox) {
                    crawfordCheckbox.checked = false;
                    crawfordCheckbox.dispatchEvent(new Event('change'));
                }

                // Filter cube options based on money game max cube
                filterCubeOptions();
            } else {
                // Switch to match
                jbWrap.style.display = 'none';
                matchPanel.style.display = 'flex';
                gameTypeButton.innerHTML = '<i class="fa fa-trophy"></i>';
                gameTypeButton.title = (window.POKAZ_I18N || {}).match || 'Матч';
                currentGameType = 'матч';

                // Update game type label
                updateGameTypeLabel();

                // Show Crawford checkbox
                setCrawfordControlsVisible(true);

                // Filter cube options based on match max cube
                filterCubeOptions();
            }
        });

        window.hintViewerChatId = currentChatIdForEditor();
        // Для конструктора позиций исходного .mat нет: сохраняем карточки с не-.mat именем,
        // чтобы в инфо не предлагалось «скачать исходный mat» и не было путаницы.
        window.hintViewerMatFileName = 'pokaz_position.json';

        window.getHintViewerBoardSnapshot = function () {
            try {
                const turnVal = document.getElementById('turn-select')?.value || 'white';
                const d1 = parseInt(document.getElementById('dice1-select')?.value || '0', 10) || 0;
                const d2 = parseInt(document.getElementById('dice2-select')?.value || '0', 10) || 0;
                const cubeShown = parseInt(document.getElementById('cube-shown-select')?.value || '0', 10) || 0;
                const cubeValue = parseInt(document.getElementById('cube-value-select')?.value || '0', 10) || 0;
                const cubeOwner = document.getElementById('cube-owner-select')?.value || 'white';
                const cubeDisplay = cubeShown !== 0 ? cubeShown : cubeValue;
                const matchLength = currentGameType === 'матч'
                    ? (parseInt(document.getElementById('match_lenght')?.value || '0', 10) || 0)
                    : 0;

                let cubeVisual = null;
                if (cubeDisplay > 0) {
                    if (cubeShown > 0) {
                        cubeVisual = {
                            mode: 'side',
                            value: cubeDisplay,
                            player: cubeOwner === 'white' ? 'red' : 'black'
                        };
                    } else {
                        cubeVisual = { mode: 'center', value: cubeDisplay };
                    }
                }

                return {
                    frameId: `pokaz_${Date.now()}`,
                    gameId: 'pokaz',
                    currentGameNum: null,
                    frameIndex: historyIndex || 0,
                    invertColors: upperPlayerColor === 'white',
                    xgid: typeof generateXGID === 'function' ? generateXGID() : '',
                    positions: {
                        red: withComputedOffCount(positions.first || {}),
                        black: withComputedOffCount(positions.second || {})
                    },
                    cubeVisual: cubeVisual,
                    scores: {
                        matchLength: matchLength,
                        gameRedScore: parseInt(document.getElementById('lower-score')?.value || '0', 10) || 0,
                        gameBlackScore: parseInt(document.getElementById('upper-score')?.value || '0', 10) || 0
                    },
                    turn: {
                        turn: turnVal,
                        action: null,
                        player: turnVal === 'white' ? 'red' : 'black',
                        player_name: turnVal,
                        dice: [d1, d2],
                        cube: cubeDisplay || null,
                        gnu_move: null
                    }
                };
            } catch (e) {
                console.error('getHintViewerBoardSnapshot(pokaz):', e);
                return { error: String(e.message || e) };
            }
        };

        window.getHintViewerCurrentCardData = function () {
            try {
                if (!latestHintsData || !Array.isArray(latestHintsData.hints) || !latestHintsData.hints.length) {
                    return null;
                }
                const first = latestHintsData.hints[0];
                if (first && first.type === 'cube_hint') {
                    return { cube_hints: latestHintsData.hints };
                }
                return { hints: latestHintsData.hints };
            } catch (e) {
                console.error('getHintViewerCurrentCardData(pokaz):', e);
                return null;
            }
        };

        window.openPipCountCardEditor = async function () {
            if (!window.pokazIsAdmin) return;
            let contentEditor;
            try {
                contentEditor = await ensureContentEditor();
            } catch (e) {
                console.error('ensureContentEditor:', e);
                showMessageModal('Редактор карточек не инициализирован', 'error');
                return;
            }
            if (!contentEditor) {
                showMessageModal('Редактор карточек не инициализирован', 'error');
                return;
            }
            try {
                if (typeof contentEditor.openModalWithBestDuplicateCheck === 'function') {
                    await contentEditor.openModalWithBestDuplicateCheck(null, {
                        duplicateMode: 'board_xgid',
                        pipCountImport: true,
                    });
                } else if (typeof contentEditor.openModalWithData === 'function') {
                    contentEditor.openModalWithData(null, { pipCountImport: true });
                } else {
                    throw new Error('ContentEditor не содержит методов открытия редактора');
                }
                if (typeof contentEditor.setupPipCountImportSession === 'function') {
                    await contentEditor.setupPipCountImportSession({ skipLoadTools: true });
                }
            } catch (e) {
                console.error('openPipCountCardEditor failed:', e);
                showMessageModal('Ошибка открытия редактора подсчёта пипсов: ' + String(e.message || e), 'error');
            }
        };

        window.openPokazCardEditor = async function () {
            if (!window.pokazIsAdmin) return;
            let contentEditor;
            try {
                contentEditor = await ensureContentEditor();
            } catch (e) {
                console.error('ensureContentEditor:', e);
                showMessageModal('Редактор карточек не инициализирован', 'error');
                return;
            }
            if (!contentEditor) {
                showMessageModal('Редактор карточек не инициализирован', 'error');
                return;
            }
            const cardData = (typeof window.getHintViewerCurrentCardData === 'function')
                ? window.getHintViewerCurrentCardData()
                : null;

            try {
                if (typeof contentEditor.openModalWithBestDuplicateCheck === 'function') {
                    await contentEditor.openModalWithBestDuplicateCheck(cardData, {
                        duplicateMode: 'board_xgid'
                    });
                } else if (typeof contentEditor.openModalWithDuplicateBoardXgidCheck === 'function') {
                    await contentEditor.openModalWithDuplicateBoardXgidCheck(cardData);
                } else if (typeof contentEditor.openModalWithDuplicateSourceCheck === 'function') {
                    await contentEditor.openModalWithDuplicateSourceCheck(cardData);
                } else if (typeof contentEditor.openModalWithData === 'function') {
                    contentEditor.openModalWithData(cardData);
                } else {
                    throw new Error('ContentEditor не содержит методов открытия редактора');
                }
            } catch (e) {
                console.error('openPokazCardEditor failed:', e);
                try {
                    contentEditor.openModalWithData(cardData);
                } catch (fallbackError) {
                    console.error('openPokazCardEditor fallback failed:', fallbackError);
                }
                const traceText = (e && e.stack) ? e.stack : String((e && e.message) ? e.message : e);
                showMessageModal('Ошибка открытия редактора. Трассировка: ' + traceText, 'error');
            }
        };

        checkPokazAdminStatus();
        window.addEventListener('resize', updateAllDropdownPositions);
    });

    // Функция для обновления текста текущего хода и индикатора шашки (в глобальной области видимости)
    function updateTurnLabel() {
        const turnLabel = document.getElementById('turn-label');
        const turnCheckerIndicator = document.getElementById('turn-checker-indicator');
        if (!turnLabel) return;

        const turnInput = document.getElementById('turn-select');
        const turn = turnInput?.value || 'white';

        const i18n = window.POKAZ_I18N || {};
        if (turn === 'white') {
            turnLabel.textContent = i18n.turn_white || 'Ход белых';
            if (turnCheckerIndicator) {
                turnCheckerIndicator.className = 'turn-checker-indicator white';
            }
        } else {
            turnLabel.textContent = i18n.turn_black || 'Ход черных';
            if (turnCheckerIndicator) {
                turnCheckerIndicator.className = 'turn-checker-indicator black';
            }
        }
    }

    // Показывает модальное окно с иконкой и кнопкой ОК (в левом верхнем углу)
    // type: 'success' | 'error' | 'warning' | 'info'
    const MSG_MODAL_ICONS = {
        success: 'fa-check-circle',
        error: 'fa-times-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    function showMessageModal(message, type) {
        type = type || 'info';
        const overlay = document.getElementById('msgModalOverlay');
        const iconEl = document.getElementById('msgModalIcon');
        const contentEl = document.getElementById('msgModalContent');
        const okBtn = document.getElementById('msgModalOkBtn');
        if (!overlay || !iconEl || !contentEl || !okBtn) return;

        iconEl.className = 'msg-modal-icon ' + type;
        iconEl.innerHTML = '<i class="fa ' + (MSG_MODAL_ICONS[type] || MSG_MODAL_ICONS.info) + '"></i>';
        contentEl.textContent = message;

        const closeModal = () => {
            overlay.classList.remove('show');
            okBtn.onclick = null;
            overlay.onclick = null;
        };

        okBtn.onclick = closeModal;
        overlay.onclick = (e) => { if (e.target === overlay) closeModal(); };

        overlay.classList.add('show');
    }

    // Функции для работы со скриншотами (в глобальной области видимости)
    let pokazScreenshotFontScale = (function () {
        const meta = document.querySelector('meta[name="pokaz-screenshot-font-scale"]');
        const parsed = parseInt(meta?.getAttribute('content') || '100', 10);
        return Number.isNaN(parsed) ? 100 : parsed;
    })();
    let pokazScreenshotFontScaleBackup = [];

    function isPokazScreenshotFontScaleSkipped(el) {
        if (!el || el.nodeType !== 1) return true;
        if (el.id === 'boardCanvas') return true;
        if (el.closest('#boardCanvas')) return true;
        if (el.closest('#pokazScreenshotAdminContainer')) return true;
        if (el.tagName === 'CANVAS') return true;
        return false;
    }

    function applyPokazScreenshotFontScale() {
        const scale = pokazScreenshotFontScale / 100;
        pokazScreenshotFontScaleBackup = [];
        if (scale === 1) return;

        const container = document.querySelector('.container');
        if (!container) return;

        const elements = container.querySelectorAll('*');
        const updates = [];
        elements.forEach((el) => {
            if (isPokazScreenshotFontScaleSkipped(el)) return;
            const px = parseFloat(window.getComputedStyle(el).fontSize);
            if (!px || Number.isNaN(px)) return;
            updates.push({
                el,
                fontSize: el.style.fontSize,
                nextFontSize: `${Math.round(px * scale * 10) / 10}px`,
            });
        });
        updates.forEach(({ el, fontSize, nextFontSize }) => {
            pokazScreenshotFontScaleBackup.push({ el, fontSize });
            el.style.fontSize = nextFontSize;
        });
    }

    function removePokazScreenshotFontScale() {
        pokazScreenshotFontScaleBackup.forEach(({ el, fontSize }) => {
            el.style.fontSize = fontSize;
        });
        pokazScreenshotFontScaleBackup = [];
    }

    function restorePokazScreenshotAdminContainerAfterScreenshot(container, originalDisplay) {
        if (!container) return;
        if (window.pokazIsAdmin && originalDisplay !== null) {
            container.style.display = originalDisplay;
        } else {
            container.style.display = 'none';
        }
    }

    async function savePokazScreenshotFontScale() {
        const select = document.getElementById('pokazScreenshotFontScaleSelect');
        if (!select) return;

        const fontScalePercent = parseInt(select.value, 10);
        pokazScreenshotFontScale = fontScalePercent;

        let initData = '';
        if (window.Telegram && window.Telegram.WebApp) {
            initData = window.Telegram.WebApp.initData;
        }
        if (!initData) {
            showMessageModal('Не удалось сохранить: нет данных Telegram', 'error');
            return;
        }

        try {
            const response = await fetch('/api/pokaz_screenshot_font_scale', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ initData, fontScalePercent })
            });
            if (response.ok) {
                const data = await response.json();
                pokazScreenshotFontScale = data.fontScalePercent;
                select.value = String(pokazScreenshotFontScale);
                showMessageModal('Масштаб шрифта для скриншота сохранён', 'success');
            } else {
                showMessageModal('Не удалось сохранить масштаб шрифта', 'error');
            }
        } catch (error) {
            console.error('Error saving pokaz screenshot font scale:', error);
            showMessageModal('Не удалось сохранить масштаб шрифта', 'error');
        }
    }

    function takeScreenshot() {
        // Скрываем элементы управления перед созданием скриншота
        const screenshotControls = document.getElementById('screenshotControls');
        const actionButtons = document.querySelector('.action-buttons');
        const selectorsWrapper = document.querySelector('.selectors-wrapper');
        const boardOpenControls = document.getElementById('boardOpenControls');
        const xgidDisplay = document.getElementById('xgid-display');
        const cubeControlsWrapper = document.querySelector('.cube-controls-block-wrapper');
        const turnDiceWrapper = document.querySelector('.turn-dice-wrapper');
        const modeToggleContainer = document.querySelector('.mode-toggle-container');
        const dropdowns = document.querySelectorAll('.dropdown, .point-selector-custom');
        const adminCommentContainer = document.querySelector('.admin-comment-container');
        const pokazScreenshotAdminContainer = document.getElementById('pokazScreenshotAdminContainer');
        const originalPokazScreenshotAdminDisplay = pokazScreenshotAdminContainer ? pokazScreenshotAdminContainer.style.display : null;

        const originalScreenshotDisplay = screenshotControls ? screenshotControls.style.display : null;
        const originalActionButtonsDisplay = actionButtons ? actionButtons.style.display : null;
        const originalSelectorsDisplay = selectorsWrapper ? selectorsWrapper.style.display : null;
        const originalBoardOpenDisplay = boardOpenControls ? boardOpenControls.style.display : null;
        const originalXgidDisplay = xgidDisplay ? xgidDisplay.style.display : null;
        const originalCubeControlsDisplay = cubeControlsWrapper ? cubeControlsWrapper.style.display : null;
        const originalTurnDiceDisplay = turnDiceWrapper ? turnDiceWrapper.style.display : null;
        const originalModeToggleContainerDisplay = modeToggleContainer ? modeToggleContainer.style.display : null;
        const originalDropdownsDisplay = Array.from(dropdowns).map(d => d.style.display);
        const originalAdminCommentDisplay = adminCommentContainer ? adminCommentContainer.style.display : null;
        const gameTypeLabel = document.getElementById('game-type-label');
        const originalGameTypeLabelDisplay = gameTypeLabel ? gameTypeLabel.style.display : null;
        const turnLabel = document.getElementById('turn-label');
        const originalTurnLabelDisplay = turnLabel ? turnLabel.style.display : null;
        const body = document.body;
        const originalBodyPaddingTop = body ? body.style.paddingTop : null;

        // Функция для восстановления элементов
        function restoreControls() {
            document.body.classList.remove('screenshot-mode');
            if (screenshotControls && originalScreenshotDisplay !== null) screenshotControls.style.display = originalScreenshotDisplay;
            if (actionButtons && originalActionButtonsDisplay !== null) actionButtons.style.display = originalActionButtonsDisplay;
            if (selectorsWrapper && originalSelectorsDisplay !== null) selectorsWrapper.style.display = originalSelectorsDisplay;
            if (boardOpenControls && originalBoardOpenDisplay !== null) boardOpenControls.style.display = originalBoardOpenDisplay;
            if (xgidDisplay && originalXgidDisplay !== null) xgidDisplay.style.display = originalXgidDisplay;
            if (cubeControlsWrapper && originalCubeControlsDisplay !== null) cubeControlsWrapper.style.display = originalCubeControlsDisplay;
            if (turnDiceWrapper && originalTurnDiceDisplay !== null) turnDiceWrapper.style.display = originalTurnDiceDisplay;
            if (modeToggleContainer && originalModeToggleContainerDisplay !== null) modeToggleContainer.style.display = originalModeToggleContainerDisplay;
            if (adminCommentContainer && originalAdminCommentDisplay !== null) adminCommentContainer.style.display = originalAdminCommentDisplay;
            if (gameTypeLabel && originalGameTypeLabelDisplay !== null) gameTypeLabel.style.display = originalGameTypeLabelDisplay;
            if (turnLabel && originalTurnLabelDisplay !== null) turnLabel.style.display = originalTurnLabelDisplay;
            if (body && originalBodyPaddingTop !== null) body.style.paddingTop = originalBodyPaddingTop;
            dropdowns.forEach((d, i) => {
                if (originalDropdownsDisplay[i] !== undefined) d.style.display = originalDropdownsDisplay[i];
            });
            restorePokazScreenshotAdminContainerAfterScreenshot(pokazScreenshotAdminContainer, originalPokazScreenshotAdminDisplay);
            removePokazScreenshotFontScale();
        }

        // Скрываем элементы
        if (screenshotControls) screenshotControls.style.display = 'none';
        if (actionButtons) actionButtons.style.display = 'none';
        if (selectorsWrapper) selectorsWrapper.style.display = 'none';
        if (boardOpenControls) boardOpenControls.style.display = 'none';
        if (xgidDisplay) xgidDisplay.style.display = 'none';
        if (cubeControlsWrapper) cubeControlsWrapper.style.display = 'none';
        if (turnDiceWrapper) turnDiceWrapper.style.display = 'none';
        if (modeToggleContainer) modeToggleContainer.style.display = 'none';
        if (adminCommentContainer) adminCommentContainer.style.display = 'none';
        if (pokazScreenshotAdminContainer) pokazScreenshotAdminContainer.style.display = 'none';
        dropdowns.forEach(d => d.style.display = 'none');

        // Добавляем отступ сверху для текста типа игры на скриншотах
        if (body) body.style.paddingTop = '5px';

        if (turnLabel) {
            updateTurnLabel();
            turnLabel.style.display = 'block';
        }

        // Скрываем столбец с кнопками в таблице подсказок на скриншоте
        document.body.classList.add('screenshot-mode');

        applyPokazScreenshotFontScale();
        // Создаем скриншот
        pokazHtml2Canvas( {
            useCORS: true,
            allowTaint: true,
            backgroundColor: '#1a1a1a'
        }).then(canvas => {
            restoreControls();
            canvas.toBlob(blob => {
                const file = new File([blob], 'screenshot.png', { type: 'image/png' });

                if (window.Telegram && window.Telegram.WebApp) {
                    const formData = new FormData();
                    formData.append('photo', file);

                    const initDataUnsafe = window.Telegram.WebApp.initDataUnsafe;
                    const chatId = initDataUnsafe && initDataUnsafe.user ? initDataUnsafe.user.id : null;

                    if (chatId) {
                        fetch(`/api/send_screenshot?chat_id=${chatId}`, {
                            method: 'POST',
                            body: formData
                        }).then(async response => {
                            if (response.ok) {
                                showMessageModal('Скриншот отправлен', 'success');
                            } else if (response.status === 402) {
                                const data = await response.json();
                                const msg = (data.detail && typeof data.detail === 'string') ? data.detail : 'Недостаточно баланса для сохранения скриншота. Активируйте промокод или приобретите услугу.';
                                showMessageModal(msg, 'warning');
                            } else {
                                const text = await response.text();
                                console.error('Ошибка сервера:', text);
                                showMessageModal('Ошибка при отправке скриншота', 'error');
                            }
                        }).catch(error => {
                            console.error('Error sending screenshot:', error);
                            showMessageModal('Ошибка при отправке скриншота', 'error');
                        });
                    } else {
                        showMessageModal('Не удалось получить chat_id', 'info');
                    }
                } else {
                    // Если не в Telegram, скачиваем файл
                    const link = document.createElement('a');
                    link.download = 'screenshot.png';
                    link.href = canvas.toDataURL();
                    link.click();
                    showMessageModal('Скриншот сохранён', 'success');
                }
            });
        }).catch(error => {
            console.error('Error creating screenshot:', error);
            showMessageModal('Ошибка при создании скриншота', 'error');
            restoreControls();
        });
    }

    // Функция для сохранения скриншота в буфер
    function saveScreenshot() {
        const screenshotControls = document.getElementById('screenshotControls');
        const actionButtons = document.querySelector('.action-buttons');
        const selectorsWrapper = document.querySelector('.selectors-wrapper');
        const boardOpenControls = document.getElementById('boardOpenControls');
        const xgidDisplay = document.getElementById('xgid-display');
        const cubeControlsWrapper = document.querySelector('.cube-controls-block-wrapper');
        const turnDiceWrapper = document.querySelector('.turn-dice-wrapper');
        const modeToggleContainer = document.querySelector('.mode-toggle-container');
        const dropdowns = document.querySelectorAll('.dropdown, .point-selector-custom');
        const adminCommentContainer = document.querySelector('.admin-comment-container');
        const pokazScreenshotAdminContainer = document.getElementById('pokazScreenshotAdminContainer');
        const originalPokazScreenshotAdminDisplay = pokazScreenshotAdminContainer ? pokazScreenshotAdminContainer.style.display : null;

        const originalScreenshotDisplay = screenshotControls ? screenshotControls.style.display : null;
        const originalActionButtonsDisplay = actionButtons ? actionButtons.style.display : null;
        const originalSelectorsDisplay = selectorsWrapper ? selectorsWrapper.style.display : null;
        const originalBoardOpenDisplay = boardOpenControls ? boardOpenControls.style.display : null;
        const originalXgidDisplay = xgidDisplay ? xgidDisplay.style.display : null;
        const originalCubeControlsDisplay = cubeControlsWrapper ? cubeControlsWrapper.style.display : null;
        const originalTurnDiceDisplay = turnDiceWrapper ? turnDiceWrapper.style.display : null;
        const originalModeToggleContainerDisplay = modeToggleContainer ? modeToggleContainer.style.display : null;
        const originalDropdownsDisplay = Array.from(dropdowns).map(d => d.style.display);
        const originalAdminCommentDisplay = adminCommentContainer ? adminCommentContainer.style.display : null;
        const gameTypeLabel = document.getElementById('game-type-label');
        const originalGameTypeLabelDisplay = gameTypeLabel ? gameTypeLabel.style.display : null;
        const turnLabel = document.getElementById('turn-label');
        const originalTurnLabelDisplay = turnLabel ? turnLabel.style.display : null;
        const body = document.body;
        const originalBodyPaddingTop = body ? body.style.paddingTop : null;

        // Функция для восстановления элементов
        function restoreControls() {
            document.body.classList.remove('screenshot-mode');
            if (screenshotControls && originalScreenshotDisplay !== null) screenshotControls.style.display = originalScreenshotDisplay;
            if (actionButtons && originalActionButtonsDisplay !== null) actionButtons.style.display = originalActionButtonsDisplay;
            if (selectorsWrapper && originalSelectorsDisplay !== null) selectorsWrapper.style.display = originalSelectorsDisplay;
            if (boardOpenControls && originalBoardOpenDisplay !== null) boardOpenControls.style.display = originalBoardOpenDisplay;
            if (xgidDisplay && originalXgidDisplay !== null) xgidDisplay.style.display = originalXgidDisplay;
            if (cubeControlsWrapper && originalCubeControlsDisplay !== null) cubeControlsWrapper.style.display = originalCubeControlsDisplay;
            if (turnDiceWrapper && originalTurnDiceDisplay !== null) turnDiceWrapper.style.display = originalTurnDiceDisplay;
            if (modeToggleContainer && originalModeToggleContainerDisplay !== null) modeToggleContainer.style.display = originalModeToggleContainerDisplay;
            if (adminCommentContainer && originalAdminCommentDisplay !== null) adminCommentContainer.style.display = originalAdminCommentDisplay;
            if (gameTypeLabel && originalGameTypeLabelDisplay !== null) gameTypeLabel.style.display = originalGameTypeLabelDisplay;
            if (turnLabel && originalTurnLabelDisplay !== null) turnLabel.style.display = originalTurnLabelDisplay;
            if (body && originalBodyPaddingTop !== null) body.style.paddingTop = originalBodyPaddingTop;
            dropdowns.forEach((d, i) => {
                if (originalDropdownsDisplay[i] !== undefined) d.style.display = originalDropdownsDisplay[i];
            });
            restorePokazScreenshotAdminContainerAfterScreenshot(pokazScreenshotAdminContainer, originalPokazScreenshotAdminDisplay);
            removePokazScreenshotFontScale();
        }

        if (screenshotControls) screenshotControls.style.display = 'none';
        if (actionButtons) actionButtons.style.display = 'none';
        if (selectorsWrapper) selectorsWrapper.style.display = 'none';
        if (boardOpenControls) boardOpenControls.style.display = 'none';
        if (xgidDisplay) xgidDisplay.style.display = 'none';
        if (cubeControlsWrapper) cubeControlsWrapper.style.display = 'none';
        if (turnDiceWrapper) turnDiceWrapper.style.display = 'none';
        if (modeToggleContainer) modeToggleContainer.style.display = 'none';
        if (adminCommentContainer) adminCommentContainer.style.display = 'none';
        if (pokazScreenshotAdminContainer) pokazScreenshotAdminContainer.style.display = 'none';
        dropdowns.forEach(d => d.style.display = 'none');

        // Добавляем отступ сверху для текста типа игры на скриншотах
        if (body) body.style.paddingTop = '5px';

        if (turnLabel) {
            updateTurnLabel();
            turnLabel.style.display = 'block';
        }

        document.body.classList.add('screenshot-mode');

        applyPokazScreenshotFontScale();
        pokazHtml2Canvas( { useCORS: true, allowTaint: true, backgroundColor: '#1a1a1a' }).then(canvas => {
            removePokazScreenshotFontScale();
            document.body.classList.remove('screenshot-mode');
            canvas.toBlob(blob => {
                if (isWebStandalonePokaz()) {
                    const formData = new FormData();
                    formData.append('photo', blob);
                    fetch('/web/hints/api/save_screenshot', {
                        method: 'POST',
                        body: formData
                    }).then(response => {
                        if (response.ok) {
                            showMessageModal('Скриншот сохранён в буфер', 'success');
                        } else if (response.status === 401) {
                            showMessageModal('Нужна авторизация', 'error');
                        } else {
                            showMessageModal('Ошибка при сохранении скриншота', 'error');
                        }
                        restoreControls();
                    }).catch(error => {
                        console.error('Error saving screenshot:', error);
                        showMessageModal('Ошибка при сохранении скриншота', 'error');
                        restoreControls();
                    });
                    return;
                }
                const initDataUnsafe = window.Telegram.WebApp.initDataUnsafe;
                const chatId = initDataUnsafe && initDataUnsafe.user ? initDataUnsafe.user.id : null;

                if (chatId) {
                    const formData = new FormData();
                    formData.append('photo', blob);
                    fetch(`/api/save_screenshot?chat_id=${chatId}`, {
                        method: 'POST',
                        body: formData
                    }).then(response => {
                        if (response.ok) {
                            showMessageModal('Скриншот сохранён в буфер', 'success');
                        } else {
                            showMessageModal('Ошибка при сохранении скриншота', 'error');
                        }
                        restoreControls();
                    }).catch(error => {
                        console.error('Error saving screenshot:', error);
                        showMessageModal('Ошибка при сохранении скриншота', 'error');
                        restoreControls();
                    });
                } else {
                    showMessageModal('Не удалось получить chat_id', 'info');
                    restoreControls();
                }
            });
        }).catch(error => {
            console.error('Error creating screenshot:', error);
            showMessageModal('Ошибка при создании скриншота', 'error');
            restoreControls();
        });
    }

    function uploadScreenshots() {
        if (isWebStandalonePokaz()) {
            fetch('/web/hints/api/download_screenshots', { method: 'POST' }).then(async response => {
                if (response.status === 401) {
                    showMessageModal('Нужна авторизация', 'error');
                    return;
                }
                if (response.status === 404) {
                    showMessageModal('В архиве нет скриншотов', 'warning');
                    return;
                }
                if (!response.ok) {
                    showMessageModal('Ошибка при скачивании архива', 'error');
                    return;
                }
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'screenshots.zip';
                document.body.appendChild(a);
                a.click();
                a.remove();
                URL.revokeObjectURL(url);
                showMessageModal('Архив скачан', 'success');
            }).catch(error => {
                console.error('Error downloading screenshots:', error);
                showMessageModal('Ошибка при скачивании архива', 'error');
            });
            return;
        }
        const initDataUnsafe = window.Telegram.WebApp.initDataUnsafe;
        const chatId = initDataUnsafe && initDataUnsafe.user ? initDataUnsafe.user.id : null;

        if (chatId) {
            fetch(`/api/upload_screenshots?chat_id=${chatId}`, { method: 'POST' }).then(async response => {
                if (response.ok) {
                    showMessageModal('Скриншоты отправлены', 'success');
                } else if (response.status === 402) {
                    const data = await response.json();
                    const msg = (data.detail && typeof data.detail === 'string') ? data.detail : 'Недостаточно баланса для отправки скриншотов. Активируйте промокод или приобретите услугу.';
                    showMessageModal(msg, 'warning');
                } else {
                    showMessageModal('Ошибка при отправке скриншотов', 'error');
                }
            }).catch(error => {
                console.error('Error uploading screenshots:', error);
                showMessageModal('Ошибка при отправке скриншотов', 'error');
            });
        } else {
            showMessageModal('Не удалось получить chat_id', 'info');
        }
    }

    function openAdminCommentModal() {
        document.getElementById('adminCommentModal').style.display = 'block';
        document.getElementById('adminCommentText').value = '';
    }

    function closeAdminCommentModal() {
        document.getElementById('adminCommentModal').style.display = 'none';
    }

    window.addEventListener('click', function (event) {
        const modal = document.getElementById('adminCommentModal');
        if (event.target == modal) {
            closeAdminCommentModal();
        }
    });

    function sendToAdmin() {
        const text = document.getElementById('adminCommentText').value;
        if (!text.trim()) {
            alert((window.POKAZ_I18N || {}).comment_empty_alert || 'Пожалуйста, введите описание проблемы');
            return;
        }

        const sendBtn = document.getElementById('sendAdminCommentBtn');
        const originalBtnText = sendBtn.innerText;
        sendBtn.disabled = true;
        sendBtn.innerText = 'Отправка...';

        const adminContainer = document.querySelector('.admin-comment-container');
        const originalAdminDisplay = adminContainer.style.display;
        adminContainer.style.display = 'none';

        const modal = document.getElementById('adminCommentModal');
        const originalModalDisplay = modal.style.display;
        modal.style.display = 'none';

        const screenshotControls = document.getElementById('screenshotControls');
        const originalScreenshotDisplay = screenshotControls ? screenshotControls.style.display : null;
        if (screenshotControls) screenshotControls.style.display = 'none';

        const pokazScreenshotAdminContainer = document.getElementById('pokazScreenshotAdminContainer');
        const originalPokazScreenshotAdminDisplay = pokazScreenshotAdminContainer ? pokazScreenshotAdminContainer.style.display : null;
        if (pokazScreenshotAdminContainer) pokazScreenshotAdminContainer.style.display = 'none';

        document.body.classList.add('screenshot-mode');

        applyPokazScreenshotFontScale();
        pokazHtml2Canvas( {
            useCORS: true,
            allowTaint: true,
            backgroundColor: '#1a1a1a'
        }).then(canvas => {
            removePokazScreenshotFontScale();
            document.body.classList.remove('screenshot-mode');
            canvas.toBlob(blob => {
                const initDataUnsafe = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp.initDataUnsafe : null;
                let chatId = null;

                if (initDataUnsafe && initDataUnsafe.user) {
                    chatId = initDataUnsafe.user.id;
                }

                if (!chatId) {
                    const urlParams = new URLSearchParams(window.location.search);
                    chatId = urlParams.get('chat_id');
                }

                if (!chatId) {
                    alert('Не удалось получить chat_id. Запустите приложение через Telegram.');
                    sendBtn.disabled = false;
                    sendBtn.innerText = originalBtnText;
                    adminContainer.style.display = originalAdminDisplay;
                    modal.style.display = originalModalDisplay;
                    if (screenshotControls && originalScreenshotDisplay !== null) screenshotControls.style.display = originalScreenshotDisplay;
                    restorePokazScreenshotAdminContainerAfterScreenshot(pokazScreenshotAdminContainer, originalPokazScreenshotAdminDisplay);
                    removePokazScreenshotFontScale();
                    return;
                }

                const formData = new FormData();
                formData.append('photo', blob);
                formData.append('text', text);
                formData.append('chat_id', chatId);

                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 10000);

                fetch('/api/send_to_admin', {
                    method: 'POST',
                    body: formData,
                    signal: controller.signal
                }).then(async response => {
                    clearTimeout(timeoutId);
                    if (response.ok) {
                        showMessageModal('Ваше сообщение отправлено, ожидайте ответа.', 'success');
                        closeAdminCommentModal();
                    } else if (response.status === 429) {
                        const data = await response.json();
                        const waitText = (data.detail && data.detail.wait_text) ? data.detail.wait_text : 'некоторое время';
                        showMessageModal(`Слишком много запросов. Пожалуйста, подождите ${waitText} перед следующей отправкой.`, 'warning');
                        closeAdminCommentModal();
                    } else if (response.status === 402) {
                        const data = await response.json();
                        const msg = (data.detail && typeof data.detail === 'string') ? data.detail : 'Недостаточно баланса для отправки комментария. Активируйте промокод или приобретите услугу.';
                        showMessageModal(msg, 'warning');
                        closeAdminCommentModal();
                    } else {
                        showMessageModal('Ошибка при отправке сообщения', 'error');
                        closeAdminCommentModal();
                    }
                }).catch(error => {
                    clearTimeout(timeoutId);
                    console.error('Error sending to admin:', error);
                    if (error.name === 'AbortError') {
                        alert('Плохое соединение. Таймаут 10 секунд. Попробуйте позже.');
                    } else {
                        alert('Ошибка при отправке сообщения');
                    }
                    modal.style.display = originalModalDisplay;
                    if (screenshotControls && originalScreenshotDisplay !== null) screenshotControls.style.display = originalScreenshotDisplay;
                    restorePokazScreenshotAdminContainerAfterScreenshot(pokazScreenshotAdminContainer, originalPokazScreenshotAdminDisplay);
                    removePokazScreenshotFontScale();
                }).finally(() => {
                    sendBtn.disabled = false;
                    sendBtn.innerText = originalBtnText;
                    adminContainer.style.display = originalAdminDisplay;
                    if (screenshotControls && originalScreenshotDisplay !== null) screenshotControls.style.display = originalScreenshotDisplay;
                    restorePokazScreenshotAdminContainerAfterScreenshot(pokazScreenshotAdminContainer, originalPokazScreenshotAdminDisplay);
                    removePokazScreenshotFontScale();
                });
            });
        }).catch(error => {
            console.error('Error creating screenshot:', error);
            alert('Ошибка при создании скриншота');
            document.body.classList.remove('screenshot-mode');
            modal.style.display = originalModalDisplay;
            sendBtn.disabled = false;
            sendBtn.innerText = originalBtnText;
            adminContainer.style.display = originalAdminDisplay;
            if (screenshotControls && originalScreenshotDisplay !== null) screenshotControls.style.display = originalScreenshotDisplay;
            restorePokazScreenshotAdminContainerAfterScreenshot(pokazScreenshotAdminContainer, originalPokazScreenshotAdminDisplay);
            removePokazScreenshotFontScale();
        });
    }

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            const adminModal = document.getElementById('adminCommentModal');
            if (adminModal.style.display === 'block') {
                closeAdminCommentModal();
            }
        }
    });

window.takeScreenshot = takeScreenshot;
window.saveScreenshot = saveScreenshot;
window.uploadScreenshots = uploadScreenshots;
window.openAdminCommentModal = openAdminCommentModal;
window.closeAdminCommentModal = closeAdminCommentModal;
window.sendToAdmin = sendToAdmin;

