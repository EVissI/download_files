/**
 * Интерактив «лучший ход»: страница карточки, превью редактора и канвас редактора.
 */

const CE_IBM_LOG = '[CE:interactive-best-move]';

export const INTERACTIVE_BEST_MOVE_FEEDBACK_DEFAULT_OK = 'Правильно';
export const INTERACTIVE_BEST_MOVE_FEEDBACK_DEFAULT_BAD = 'Неправильно';

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

let _feedbackModalBound = false;

function closeInteractiveBestMoveFeedbackModal() {
    const root = document.getElementById('ceInteractiveBestMoveFeedbackModal');
    if (!root) return;
    root.style.display = 'none';
    root.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
}

function ensureInteractiveBestMoveFeedbackModal() {
    let root = document.getElementById('ceInteractiveBestMoveFeedbackModal');
    if (root) return root;
    root = document.createElement('div');
    root.id = 'ceInteractiveBestMoveFeedbackModal';
    root.className = 'ce-interactive-feedback-modal';
    root.setAttribute('role', 'dialog');
    root.setAttribute('aria-modal', 'true');
    root.setAttribute('aria-hidden', 'true');
    root.style.display = 'none';
    root.innerHTML = `
        <div class="ce-interactive-feedback-modal__backdrop" aria-hidden="true"></div>
        <div class="ce-interactive-feedback-modal__panel">
            <p class="ce-interactive-feedback-modal__text" id="ceInteractiveBestMoveFeedbackText"></p>
            <button type="button" class="ce-interactive-feedback-modal__btn" id="ceInteractiveBestMoveFeedbackOkBtn">OK</button>
        </div>`;
    document.body.appendChild(root);

    const onClose = () => closeInteractiveBestMoveFeedbackModal();
    root.querySelector('.ce-interactive-feedback-modal__backdrop')?.addEventListener('click', onClose);
    root.querySelector('#ceInteractiveBestMoveFeedbackOkBtn')?.addEventListener('click', onClose);

    if (!_feedbackModalBound) {
        _feedbackModalBound = true;
        document.addEventListener('keydown', (e) => {
            if (e.key !== 'Escape') return;
            const r = document.getElementById('ceInteractiveBestMoveFeedbackModal');
            if (r && r.style.display === 'flex') {
                e.preventDefault();
                closeInteractiveBestMoveFeedbackModal();
            }
        });
    }
    return root;
}

/**
 * Модалка «Правильно» / «Неправильно» после выбора хода (редактор, превью, карточка).
 * @param {string} message
 */
export function openInteractiveBestMoveFeedbackModal(message) {
    if (typeof document === 'undefined') return;
    const root = ensureInteractiveBestMoveFeedbackModal();
    const textEl = document.getElementById('ceInteractiveBestMoveFeedbackText');
    const btn = document.getElementById('ceInteractiveBestMoveFeedbackOkBtn');
    if (textEl) textEl.textContent = message != null ? String(message) : '';
    root.style.display = 'flex';
    root.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    window.setTimeout(() => {
        try {
            btn?.focus();
        } catch (_e) {
            /* noop */
        }
    }, 0);
}

/**
 * @param {object | null | undefined} cardData
 * @returns {{ error: boolean, message?: string, slots: Array<{ label: string, disabled: boolean, isCorrect: boolean }> }}
 */
export function buildInteractiveSlotsFromCardData(cardData) {
    if (!cardData || typeof cardData !== 'object') {
        if (typeof console !== 'undefined' && console.info) {
            console.info(CE_IBM_LOG, 'buildInteractiveSlotsFromCardData: cardData пустой или не объект', {
                cardData,
            });
        }
        return {
            error: true,
            message: 'Интерактив недоступен: нет таблицы ходов',
            slots: [],
        };
    }

    if (cardData.action === 'win') {
        const name = cardData.player_name != null ? cardData.player_name : cardData.player || '';
        const pts = cardData.points != null ? cardData.points : '';
        const move = `Победа ${name} (${pts} очков)`;
        return {
            error: false,
            slots: [
                { label: move, disabled: false, isCorrect: true },
                { label: '—', disabled: true, isCorrect: false },
                { label: '—', disabled: true, isCorrect: false },
                { label: '—', disabled: true, isCorrect: false },
            ],
        };
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

    const slots = [];
    for (let j = 0; j < 4; j++) {
        if (j < moves.length) {
            slots.push({
                label: moves[j],
                disabled: false,
                isCorrect: j === 0,
            });
        } else {
            slots.push({ label: '—', disabled: true, isCorrect: false });
        }
    }
    if (typeof console !== 'undefined' && console.debug) {
        console.debug(CE_IBM_LOG, 'buildInteractiveSlotsFromCardData: ok', {
            movesLen: moves.length,
            labels: moves.slice(0, 4),
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
 */
export function fillInteractiveEditorPreviewGrid(gridEl, cardData) {
    const result = buildInteractiveSlotsFromCardData(cardData);
    fillInteractiveBestMoveGridFromResult(gridEl, result, { dryRun: true });
}

/**
 * Слоты из уже известных подписей ходов (например, разобранных с таблицы на холсте).
 * @param {string[]} moves
 */
export function buildInteractiveSlotsFromMoveStrings(moves) {
    if (!moves || !Array.isArray(moves) || moves.length === 0) {
        return {
            error: true,
            message: 'Интерактив недоступен: нет таблицы ходов',
            slots: [],
        };
    }
    const slots = [];
    for (let j = 0; j < 4; j++) {
        if (j < moves.length) {
            slots.push({
                label: String(moves[j]),
                disabled: false,
                isCorrect: j === 0,
            });
        } else {
            slots.push({ label: '—', disabled: true, isCorrect: false });
        }
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
    const built = buildInteractiveSlotsFromCardData(cardData);

    const blocks = host.querySelectorAll(
        '.canvas-element.card-preview-canvas-clone[data-tool-id="interactive-best-move"]'
    );
    blocks.forEach((block) => {
        fillInteractiveBlock(block, built, editor);
    });
}
