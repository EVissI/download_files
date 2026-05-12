/**
 * Интерактив «лучший ход» на странице просмотра карточки (не в мини-превью шаблонов).
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
        if (!hint || !hint.probs || hint.probs.length < 2) continue;
        moves.push(String(hint.move != null ? hint.move : '-'));
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

function fillInteractiveBlock(block, result, editor) {
    const grid = block.querySelector('[data-ce-interactive-grid]');
    if (!grid) return;
    grid.innerHTML = '';

    if (result.error) {
        const p = document.createElement('p');
        p.className = 'ce-interactive-best-move__msg';
        p.textContent = result.message || 'Интерактив недоступен';
        grid.appendChild(p);
        return;
    }

    const slots = shuffleInPlace(result.slots.map((s) => ({ ...s })));
    const cardId = editor._contentCardViewCardId;
    const auth = editor.getContentCardApiAuthPayload();

    slots.forEach((slot) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'ce-interactive-best-move__btn';
        btn.textContent = slot.label;
        if (slot.disabled) {
            btn.disabled = true;
            btn.classList.add('ce-interactive-best-move__btn--disabled');
        } else {
            btn.addEventListener('click', () => {
                if (!cardId || !auth) return;
                const correct = !!slot.isCorrect;
                void fetch('/api/content_cards/interactive/record', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        ...auth,
                        content_card_id: Number(cardId),
                        correct,
                    }),
                }).catch((e) => console.warn('interactive/record:', e));
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
        grid.appendChild(btn);
    });
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
