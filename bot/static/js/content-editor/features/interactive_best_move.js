/**
 * Интерактив «лучший ход»: страница карточки, превью редактора и канвас редактора.
 */

function shuffleInPlace(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        const t = arr[i];
        arr[i] = arr[j];
        arr[j] = t;
    }
    return arr;
}

/**
 * @param {object | null | undefined} cardData
 * @returns {{ error: boolean, message?: string, slots: Array<{ label: string, disabled: boolean, isCorrect: boolean }> }}
 */
export function buildInteractiveSlotsFromCardData(cardData) {
    if (!cardData || typeof cardData !== 'object') {
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

    const hints = Array.isArray(cardData.hints) ? cardData.hints : [];
    const moves = [];
    for (let i = 0; i < hints.length; i++) {
        const hint = hints[i];
        if (!hint) continue;
        const hasProbs = Array.isArray(hint.probs) && hint.probs.length >= 2;
        const moveRaw = hint.move != null ? String(hint.move).trim() : '';
        if (hasProbs) {
            moves.push(String(hint.move != null ? hint.move : '-'));
        } else if (moveRaw !== '') {
            moves.push(String(hint.move));
        }
    }

    if (moves.length === 0) {
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
    return { error: false, slots };
}

/**
 * @param {HTMLElement | null} gridEl
 * @param {{ error: boolean, message?: string, slots: Array<{ label: string, disabled: boolean, isCorrect: boolean }> }} result
 * @param {{ dryRun?: boolean, recordEditor?: * }} [options] — dryRun: без записи на сервер; recordEditor: для записи (страница карточки)
 */
function fillInteractiveBestMoveGridFromResult(gridEl, result, options = {}) {
    if (!gridEl) return;
    const dryRun = !!options.dryRun;
    const recordEditor = options.recordEditor || null;

    gridEl.innerHTML = '';

    if (result.error) {
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
