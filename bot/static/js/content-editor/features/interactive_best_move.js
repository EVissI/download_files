/**
 * Интерактив «лучший ход»: страница карточки, превью редактора и канвас редактора.
 */

const _featureCacheQs = (() => {
    try {
        return new URL(import.meta.url).search || '';
    } catch (_e) {
        return '';
    }
})();

function withFeatureCacheQs(relativePath) {
    const resolved = new URL(relativePath, import.meta.url).href;
    const q = _featureCacheQs;
    if (!q || resolved.includes('?')) return resolved;
    return resolved + q;
}

const { openInteractiveBestMoveFeedbackModal } = await import(
    withFeatureCacheQs('./interactive_feedback_modal.js')
);

export { openInteractiveBestMoveFeedbackModal };

const CE_IBM_LOG = '[CE:interactive-best-move]';

export const INTERACTIVE_BEST_MOVE_FEEDBACK_DEFAULT_OK = 'Правильно';
export const INTERACTIVE_BEST_MOVE_FEEDBACK_DEFAULT_BAD = 'Неправильно';

/** Типы данных, по которым строится интерактив. */
export const INTERACTIVE_TABLE_TYPE_HINTS = 'hints';
export const INTERACTIVE_TABLE_TYPE_CUBE = 'cube';

const INTERACTIVE_TITLE_HINTS = 'Выбери лучший ход';
const INTERACTIVE_TITLE_CUBE = 'Выбери лучшее действие';

function normalizeInteractiveTableType(value) {
    return String(value || '').trim().toLowerCase() === INTERACTIVE_TABLE_TYPE_CUBE
        ? INTERACTIVE_TABLE_TYPE_CUBE
        : INTERACTIVE_TABLE_TYPE_HINTS;
}

/** Тип таблицы (hints/cube), по которой построен блок интерактива. */
export function getInteractiveTableTypeFromBlock(block) {
    if (!block) return INTERACTIVE_TABLE_TYPE_HINTS;
    const attr =
        typeof block.getAttribute === 'function'
            ? block.getAttribute('data-ce-interactive-table-type')
            : null;
    const ds = block.dataset || {};
    const candidate = attr || ds.ceInteractiveTableType || ds.ce_interactive_table_type;
    return normalizeInteractiveTableType(candidate);
}

/** Тип таблицы из сохранённого payload (до десериализации в DOM). */
export function parseInteractiveTableTypeFromSavedElement(item) {
    if (!item || typeof item !== 'object') return INTERACTIVE_TABLE_TYPE_HINTS;
    const ds = item.dataset && typeof item.dataset === 'object' ? item.dataset : {};
    const candidates = [
        ds.ceInteractiveTableType,
        ds.ce_interactive_table_type,
        item.ceInteractiveTableType,
        item.ce_interactive_table_type,
        item.interactiveTableType,
        item.interactive_table_type,
    ];
    for (let i = 0; i < candidates.length; i++) {
        const v = candidates[i];
        if (v != null && String(v).trim() !== '') return normalizeInteractiveTableType(v);
    }
    return INTERACTIVE_TABLE_TYPE_HINTS;
}

/** Перенастроить заголовок блока интерактива под выбранный тип таблицы. */
export function syncInteractiveBlockTitleByType(block, tableType) {
    if (!block) return;
    const title = block.querySelector('.ce-interactive-best-move__title');
    if (!title) return;
    title.textContent =
        normalizeInteractiveTableType(tableType) === INTERACTIVE_TABLE_TYPE_CUBE
            ? INTERACTIVE_TITLE_CUBE
            : INTERACTIVE_TITLE_HINTS;
}

/**
 * Настройка из кабинета карточек ("Открыть подсказки").
 * Если выключена или отсутствует — блоки интерактива на странице карточки прячем.
 */
const INTERACTIVE_OPEN_HINTS_STORAGE_KEY = 'cards_cabinet_open_hints_v1';

function isInteractiveHintsOpenForUser() {
    if (typeof window === 'undefined') return true;
    try {
        const raw = window.localStorage ? window.localStorage.getItem(INTERACTIVE_OPEN_HINTS_STORAGE_KEY) : null;
        if (raw === null || raw === undefined) return true;
        return raw !== '0' && raw !== 'false';
    } catch (_e) {
        return true;
    }
}

function shuffleInPlace(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        const t = arr[i];
        arr[i] = arr[j];
        arr[j] = t;
    }
    return arr;
}

function getInteractiveFeedbackTexts(gridEl) {
    const block =
        gridEl && gridEl.closest ? gridEl.closest('.canvas-element') || gridEl.closest('.ce-interactive-best-move') : null;
    const okRaw =
        block && block.dataset && block.dataset.ceInteractiveFeedbackOk != null
            ? String(block.dataset.ceInteractiveFeedbackOk).trim()
            : '';
    const badRaw =
        block && block.dataset && block.dataset.ceInteractiveFeedbackBad != null
            ? String(block.dataset.ceInteractiveFeedbackBad).trim()
            : '';
    return {
        ok: okRaw || INTERACTIVE_BEST_MOVE_FEEDBACK_DEFAULT_OK,
        bad: badRaw || INTERACTIVE_BEST_MOVE_FEEDBACK_DEFAULT_BAD,
    };
}

/** Сколько строк с probs даёт cardData (как у таблицы ходов). Победа → 1. */
/**
 * Сохранённый payload может хранить счётчик как dataset.ceInteractiveButtonCount или под другим ключом после JSON/API.
 * @param {HTMLElement | null} el
 * @returns {number} число или NaN — тогда clampInteractiveButtonCount подставит defaultCount
 */
export function parseCeInteractiveButtonCountRaw(el) {
    if (!el) return NaN;
    const ga =
        typeof el.getAttribute === 'function' ? el.getAttribute('data-ce-interactive-button-count') : null;
    if (ga != null && String(ga).trim() !== '') {
        const n = parseInt(ga, 10);
        if (Number.isFinite(n)) return n;
    }
    const ds = el.dataset || {};
    const keys = ['ceInteractiveButtonCount', 'ce_interactive_button_count'];
    for (let i = 0; i < keys.length; i++) {
        const v = ds[keys[i]];
        if (v != null && String(v).trim() !== '') {
            const n = parseInt(v, 10);
            if (Number.isFinite(n)) return n;
        }
    }
    return NaN;
}

/**
 * Число кнопок из объекта элемента кадра в JSON (payload.elements[]), до десериализации в DOM.
 * Бэкенд / исторические сохранения могли класть поле не только в dataset.
 */
export function parseCeInteractiveButtonCountFromSavedElement(item) {
    if (!item || typeof item !== 'object') return NaN;
    const ds = item.dataset && typeof item.dataset === 'object' ? item.dataset : {};
    /* Корневые поля приоритетнее dataset: иначе дефолт «4» в dataset перекрывает актуальное значение из API/старых сохранений. */
    const candidates = [
        item.ceInteractiveButtonCount,
        item.ce_interactive_button_count,
        item.interactiveButtonCount,
        item.interactive_button_count,
        ds.ceInteractiveButtonCount,
        ds.ce_interactive_button_count,
    ];
    for (let i = 0; i < candidates.length; i++) {
        const v = candidates[i];
        if (v != null && String(v).trim() !== '') {
            const n = parseInt(String(v), 10);
            if (Number.isFinite(n) && n >= 1) return n;
        }
    }
    return NaN;
}

/**
 * Для превью карточки сначала берём счётчик из payload.elements (истина из API), затем из DOM.
 */
export function resolveInteractiveButtonCountRaw(block, payload) {
    const els = payload && Array.isArray(payload.elements) ? payload.elements : null;
    if (els && block) {
        let item = block.id ? els.find((e) => e && e.id === block.id) : null;
        if (!item) {
            const ibm = els.filter(
                (e) => e && (e.toolId === 'interactive-best-move' || e.tool_id === 'interactive-best-move')
            );
            if (ibm.length === 1) item = ibm[0];
        }
        if (item) {
            const fromJson = parseCeInteractiveButtonCountFromSavedElement(item);
            if (Number.isFinite(fromJson)) return fromJson;
        }
    }
    return parseCeInteractiveButtonCountRaw(block);
}

export function countInteractiveMovesFromCardData(cardData) {
    if (!cardData || typeof cardData !== 'object') return 0;
    if (cardData.action === 'win') return 1;
    const hints = Array.isArray(cardData.hints) ? cardData.hints : [];
    let n = 0;
    for (let i = 0; i < hints.length; i++) {
        const hint = hints[i];
        if (!hint || !hint.probs || hint.probs.length < 2) continue;
        n++;
    }
    return n;
}

/** Сколько кубических действий даёт cube_hints[0].cubeful_equities (как в createCubeTable). */
export function countInteractiveCubeActionsFromCardData(cardData) {
    if (!cardData || typeof cardData !== 'object') return 0;
    const ch = Array.isArray(cardData.cube_hints) ? cardData.cube_hints : null;
    const ch0 = ch && ch.length ? ch[0] : null;
    const ce = ch0 && Array.isArray(ch0.cubeful_equities) ? ch0.cubeful_equities : null;
    return ce ? ce.length : 0;
}

/** Универсальный счётчик: для hints — ходы с probs, для cube — cubeful_equities. */
export function countInteractiveAvailableFromCardData(cardData, tableType) {
    return normalizeInteractiveTableType(tableType) === INTERACTIVE_TABLE_TYPE_CUBE
        ? countInteractiveCubeActionsFromCardData(cardData)
        : countInteractiveMovesFromCardData(cardData);
}

/**
 * Не меньше 2 кнопок, если доступно ≥2 ходов; при одном варианте (победа / один ход) — 1.
 * Значение «1» из UI не выбирается при нескольких ходах.
 */
export function clampInteractiveButtonCount(raw, maxAvailable, defaultCount = 4) {
    const max = Math.floor(Math.max(0, Number(maxAvailable) || 0));
    let n = parseInt(raw, 10);
    if (!Number.isFinite(n) || n < 1) n = defaultCount;
    if (max <= 0) return Math.min(n, defaultCount);
    if (max === 1) return 1;
    return Math.min(Math.max(2, n), max);
}

/**
 * @param {object | null | undefined} cardData
 * @param {number} [buttonCount=4] — желаемое число активных кнопок (не больше числа доступных ходов)
 * @param {'hints'|'cube'} [tableType='hints'] — по какой таблице строим интерактив
 * @returns {{ error: boolean, message?: string, slots: Array<{ label: string, disabled: boolean, isCorrect: boolean }> }}
 */
export function buildInteractiveSlotsFromCardData(cardData, buttonCount = 4, tableType = INTERACTIVE_TABLE_TYPE_HINTS) {
    const type = normalizeInteractiveTableType(tableType);

    if (!cardData || typeof cardData !== 'object') {
        if (typeof console !== 'undefined' && console.info) {
            console.info(CE_IBM_LOG, 'buildInteractiveSlotsFromCardData: cardData пустой или не объект', {
                cardData,
                tableType: type,
            });
        }
        return {
            error: true,
            message:
                type === INTERACTIVE_TABLE_TYPE_CUBE
                    ? 'Интерактив недоступен: нет таблицы по кубу'
                    : 'Интерактив недоступен: нет таблицы ходов',
            slots: [],
        };
    }

    if (type === INTERACTIVE_TABLE_TYPE_CUBE) {
        /* Те же строки, что и в createCubeTable(): cubeful_equities из первого элемента cube_hints. */
        const ch = Array.isArray(cardData.cube_hints) ? cardData.cube_hints : [];
        const ch0 = ch.length ? ch[0] : null;
        const equities = ch0 && Array.isArray(ch0.cubeful_equities) ? ch0.cubeful_equities : [];
        const actions = [];
        for (let i = 0; i < equities.length; i++) {
            const h = equities[i];
            if (!h) continue;
            let label = h.action_1 != null ? String(h.action_1) : '';
            if (h.action_2 != null && String(h.action_2).trim() !== '') {
                label = label ? `${label}, ${h.action_2}` : String(h.action_2);
            }
            actions.push(label || '-');
        }

        if (actions.length === 0) {
            if (typeof console !== 'undefined' && console.info) {
                console.info(CE_IBM_LOG, 'buildInteractiveSlotsFromCardData(cube): нет cubeful_equities', {
                    cubeHintsLen: ch.length,
                });
            }
            return {
                error: true,
                message: 'Интерактив недоступен: нет таблицы по кубу',
                slots: [],
            };
        }

        const n = clampInteractiveButtonCount(buttonCount, actions.length, 4);
        const slots = [];
        for (let j = 0; j < n; j++) {
            slots.push({
                label: actions[j],
                disabled: false,
                isCorrect: j === 0,
            });
        }
        if (typeof console !== 'undefined' && console.debug) {
            console.debug(CE_IBM_LOG, 'buildInteractiveSlotsFromCardData(cube): ok', {
                actionsLen: actions.length,
                buttonCount: n,
                labels: actions.slice(0, n),
            });
        }
        return { error: false, slots };
    }

    if (cardData.action === 'win') {
        const name = cardData.player_name != null ? cardData.player_name : cardData.player || '';
        const pts = cardData.points != null ? cardData.points : '';
        const move = `Победа ${name} (${pts} очков)`;
        const maxWin = 1;
        const n = clampInteractiveButtonCount(buttonCount, maxWin, 4);
        const slots = [];
        for (let j = 0; j < n; j++) {
            if (j === 0) {
                slots.push({ label: move, disabled: false, isCorrect: true });
            } else {
                slots.push({ label: '—', disabled: true, isCorrect: false });
            }
        }
        return { error: false, slots };
    }

    /* Те же строки, что и в createHintsTable(): только подсказки с probs (как в таблице на холсте). */
    const hints = Array.isArray(cardData.hints) ? cardData.hints : [];
    const moves = [];
    for (let i = 0; i < hints.length; i++) {
        const hint = hints[i];
        if (!hint) continue;
        if (!hint.probs || hint.probs.length < 2) continue;
        moves.push(String(hint.move != null ? hint.move : '-'));
    }

    if (moves.length === 0) {
        const withProbs = hints.filter((h) => h && Array.isArray(h.probs) && h.probs.length >= 2).length;
        if (typeof console !== 'undefined' && console.info) {
            console.info(CE_IBM_LOG, 'buildInteractiveSlotsFromCardData: нет ходов с probs (как у таблицы)', {
                hintsLen: hints.length,
                hintsWithProbsGe2: withProbs,
                action: cardData.action,
                sampleHint0: hints[0]
                    ? {
                          hasMove: hints[0].move != null,
                          probsLen: Array.isArray(hints[0].probs) ? hints[0].probs.length : 0,
                      }
                    : null,
            });
        }
        return {
            error: true,
            message: 'Интерактив недоступен: нет таблицы ходов',
            slots: [],
        };
    }

    const n = clampInteractiveButtonCount(buttonCount, moves.length, 4);
    const slots = [];
    for (let j = 0; j < n; j++) {
        slots.push({
            label: moves[j],
            disabled: false,
            isCorrect: j === 0,
        });
    }
    if (typeof console !== 'undefined' && console.debug) {
        console.debug(CE_IBM_LOG, 'buildInteractiveSlotsFromCardData: ok', {
            movesLen: moves.length,
            buttonCount: n,
            labels: moves.slice(0, n),
        });
    }
    return { error: false, slots };
}

/**
 * @param {HTMLElement | null} gridEl
 * @param {{ error: boolean, message?: string, slots: Array<{ label: string, disabled: boolean, isCorrect: boolean }> }} result
 * @param {{ dryRun?: boolean, recordEditor?: * }} [options] — dryRun: без записи на сервер; recordEditor: для записи (страница карточки)
 */
function fillInteractiveBestMoveGridFromResult(gridEl, result, options = {}) {
    if (!gridEl) {
        if (typeof console !== 'undefined' && console.warn) {
            console.warn(CE_IBM_LOG, 'fillInteractiveBestMoveGridFromResult: gridEl отсутствует');
        }
        return;
    }
    const dryRun = !!options.dryRun;
    const recordEditor = options.recordEditor || null;

    gridEl.innerHTML = '';

    if (result.error) {
        if (typeof console !== 'undefined' && console.info) {
            console.info(CE_IBM_LOG, 'fillInteractiveBestMoveGridFromResult: показ сообщения об ошибке', {
                dryRun,
                message: result.message,
            });
        }
        const p = document.createElement('p');
        p.className = 'ce-interactive-best-move__msg';
        p.textContent = result.message || 'Интерактив недоступен';
        gridEl.appendChild(p);
        return;
    }

    const slots = shuffleInPlace(result.slots.map((s) => ({ ...s })));
    const cardId = recordEditor && recordEditor._contentCardViewCardId;
    const auth = recordEditor && recordEditor.getContentCardApiAuthPayload
        ? recordEditor.getContentCardApiAuthPayload()
        : null;

    slots.forEach((slot) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'ce-interactive-best-move__btn';
        btn.textContent = slot.label;
        if (slot.disabled) {
            btn.disabled = true;
            btn.classList.add('ce-interactive-best-move__btn--disabled');
        } else {
            btn.addEventListener('mousedown', (e) => {
                if (e && typeof e.stopPropagation === 'function') {
                    e.stopPropagation();
                }
            });
            btn.addEventListener('click', (e) => {
                if (e && typeof e.stopPropagation === 'function') {
                    e.stopPropagation();
                }
                const correct = !!slot.isCorrect;
                if (!dryRun && recordEditor && cardId && auth) {
                    void fetch('/api/content_cards/interactive/record', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            ...auth,
                            content_card_id: Number(cardId),
                            correct,
                        }),
                    }).catch((err) => console.warn('interactive/record:', err));
                }
                btn.classList.add(
                    correct ? 'ce-interactive-best-move__btn--flash-ok' : 'ce-interactive-best-move__btn--flash-bad'
                );
                window.setTimeout(() => {
                    btn.classList.remove(
                        'ce-interactive-best-move__btn--flash-ok',
                        'ce-interactive-best-move__btn--flash-bad'
                    );
                }, 450);
                const { ok, bad } = getInteractiveFeedbackTexts(gridEl);
                openInteractiveBestMoveFeedbackModal(correct ? ok : bad);
            });
        }
        gridEl.appendChild(btn);
    });
}

/**
 * Редактор и превью (без записи на сервер): как у игрока на карточке — перемешивание и клики с подсветкой.
 *
 * @param {HTMLElement | null} gridEl
 * @param {object | null | undefined} cardData — уже смерженный эффективный cardData
 * @param {number} [buttonCount=4]
 */
export function fillInteractiveEditorPreviewGrid(gridEl, cardData, buttonCount = 4, tableType = INTERACTIVE_TABLE_TYPE_HINTS) {
    const result = buildInteractiveSlotsFromCardData(cardData, buttonCount, tableType);
    fillInteractiveBestMoveGridFromResult(gridEl, result, { dryRun: true });
}

/**
 * Слоты из уже известных подписей ходов (например, разобранных с таблицы на холсте).
 * @param {string[]} moves
 * @param {number} [buttonCount=4]
 */
export function buildInteractiveSlotsFromMoveStrings(moves, buttonCount = 4) {
    if (!moves || !Array.isArray(moves) || moves.length === 0) {
        return {
            error: true,
            message: 'Интерактив недоступен: нет таблицы ходов',
            slots: [],
        };
    }
    const n = clampInteractiveButtonCount(buttonCount, moves.length, 4);
    const slots = [];
    for (let j = 0; j < n; j++) {
        slots.push({
            label: String(moves[j]),
            disabled: false,
            isCorrect: j === 0,
        });
    }
    return { error: false, slots };
}

/** Редактор: подставить уже посчитанный результат (например, после fallback с DOM таблицы). */
export function fillInteractiveBestMoveEditorGridFromResult(gridEl, result) {
    fillInteractiveBestMoveGridFromResult(gridEl, result, { dryRun: true });
}

export function fillInteractiveBlock(block, result, editor) {
    const grid = block.querySelector('[data-ce-interactive-grid]');
    if (!grid) return;
    fillInteractiveBestMoveGridFromResult(grid, result, { dryRun: false, recordEditor: editor });
}

/**
 * @param {*} editor — ContentEditor
 * @param {object | null} payload — уже смерженный getPayloadForCardPreviewRender
 */
export function setupInteractiveBestMoveAfterCardPreviewRender(editor, payload) {
    if (typeof window === 'undefined' || window.__CONTENT_CARD_VIEW_ONLY__ !== true) return;
    if (!editor || !editor._contentCardViewCardId) return;
    const host = document.getElementById('cardPreviewFrameHost');
    if (!host) return;

    const cardData = payload && payload.cardData && typeof payload.cardData === 'object' ? payload.cardData : null;
    const hintsOpenForUser = isInteractiveHintsOpenForUser();

    const blocks = host.querySelectorAll('.canvas-element[data-tool-id="interactive-best-move"]');
    blocks.forEach((block) => {
        if (!hintsOpenForUser) {
            // Чекбокс «Открыть подсказки» в кабинете снят — на всех кадрах скрываем интерактив у пользователя.
            block.style.display = 'none';
            block.setAttribute('aria-hidden', 'true');
            return;
        }
        block.style.display = '';
        block.removeAttribute('aria-hidden');

        const tableType = getInteractiveTableTypeFromBlock(block);
        syncInteractiveBlockTitleByType(block, tableType);

        const raw = resolveInteractiveButtonCountRaw(block, payload);
        const maxM = countInteractiveAvailableFromCardData(cardData, tableType);
        const btn = clampInteractiveButtonCount(raw, Math.max(1, maxM), 4);
        if (block.dataset) block.dataset.ceInteractiveButtonCount = String(btn);
        const built = buildInteractiveSlotsFromCardData(cardData, btn, tableType);
        fillInteractiveBlock(block, built, editor);
    });
}
