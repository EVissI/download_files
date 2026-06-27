/**
 * Интерактив «Решение по кубу» (пул pip_count): таймер и выбор из трёх действий по кубу.
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
const {
    applyPipCountBoardGateForBlock,
    applyPipCountBoardGateForPreviewHost,
    syncPipInteractiveLayoutAfterChange,
} = await import(withFeatureCacheQs('./interactive_pip_count.js'));
const { buildDoubleResultText } = await import(withFeatureCacheQs('./pip_result_format.js'));

export const INTERACTIVE_PIP_DOUBLE_TOOL_ID = 'interactive-pip-double';
export const INTERACTIVE_PIP_DOUBLE_DISPLAY_NAME = 'Решение по кубу';

export const PIP_DOUBLE_ANSWER_NO_DOUBLE = 'no_double';
export const PIP_DOUBLE_ANSWER_DOUBLE_TAKE = 'double_take';
export const PIP_DOUBLE_ANSWER_DOUBLE_PASS = 'double_pass';

export const PIP_DOUBLE_ANSWER_OPTIONS = [
    { value: PIP_DOUBLE_ANSWER_NO_DOUBLE, label: 'No double' },
    { value: PIP_DOUBLE_ANSWER_DOUBLE_TAKE, label: 'Double/take' },
    { value: PIP_DOUBLE_ANSWER_DOUBLE_PASS, label: 'Double/pass' },
];

export const INTERACTIVE_PIP_DOUBLE_FEEDBACK_DEFAULT_OK = 'Правильно';
export const INTERACTIVE_PIP_DOUBLE_FEEDBACK_DEFAULT_BAD = 'Неправильно';

const ACTION_IDLE = 'idle';
const ACTION_RUNNING = 'running';
const ACTION_STOPPED = 'stopped';

/** @type {WeakMap<HTMLElement, object>} */
const runtimeByBlock = new WeakMap();

function pad2(n) {
    return n < 10 ? '0' + n : String(n);
}

function formatElapsedMs(ms) {
    const totalSec = Math.max(0, Math.floor(ms / 1000));
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    return pad2(m) + ':' + pad2(s);
}

export function normalizePipDoubleCorrectAnswer(raw) {
    const v = String(raw || '').trim().toLowerCase();
    if (v === PIP_DOUBLE_ANSWER_DOUBLE_TAKE) return PIP_DOUBLE_ANSWER_DOUBLE_TAKE;
    if (v === PIP_DOUBLE_ANSWER_DOUBLE_PASS) return PIP_DOUBLE_ANSWER_DOUBLE_PASS;
    return PIP_DOUBLE_ANSWER_NO_DOUBLE;
}

export function pipDoubleAnswerLabel(value) {
    const v = normalizePipDoubleCorrectAnswer(value);
    const opt = PIP_DOUBLE_ANSWER_OPTIONS.find((o) => o.value === v);
    return opt ? opt.label : PIP_DOUBLE_ANSWER_OPTIONS[0].label;
}

export function ensurePipDoubleDatasetDefaults(block) {
    if (!block) return;
    block.dataset.cePipDoubleCorrectAnswer = normalizePipDoubleCorrectAnswer(
        block.dataset.cePipDoubleCorrectAnswer
    );
    if (!String(block.dataset.cePipDoubleFeedbackOk || '').trim()) {
        block.dataset.cePipDoubleFeedbackOk = INTERACTIVE_PIP_DOUBLE_FEEDBACK_DEFAULT_OK;
    }
    if (!String(block.dataset.cePipDoubleFeedbackBad || '').trim()) {
        block.dataset.cePipDoubleFeedbackBad = INTERACTIVE_PIP_DOUBLE_FEEDBACK_DEFAULT_BAD;
    }
    const titleEl = block.querySelector('.ce-interactive-pip-double__title');
    if (titleEl) titleEl.textContent = INTERACTIVE_PIP_DOUBLE_DISPLAY_NAME;
}

export function getInteractivePipDoubleInnerHtml() {
    return `
                    <div class="ce-interactive-pip-double__inner">
                        <p class="ce-interactive-pip-double__title">${INTERACTIVE_PIP_DOUBLE_DISPLAY_NAME}</p>
                        <div class="ce-interactive-pip-double__controls" data-ce-pip-double-controls>
                            <div class="ce-interactive-pip-double__timer-row" data-ce-pip-double-timer-row>
                                <button type="button" class="ce-interactive-pip-double__btn" data-ce-pip-double-action data-ce-pip-double-state="idle" aria-label="Пуск">Пуск</button>
                                <span class="ce-interactive-pip-double__timer" data-ce-pip-double-timer-display>00:00</span>
                            </div>
                            <div class="ce-interactive-pip-double__choices" data-ce-pip-double-choices hidden></div>
                            <pre class="ce-interactive-pip-double__result" data-ce-pip-double-result style="display:none"></pre>
                        </div>
                    </div>`;
}

function shuffleArray(arr) {
    const copy = arr.slice();
    for (let i = copy.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        const tmp = copy[i];
        copy[i] = copy[j];
        copy[j] = tmp;
    }
    return copy;
}

function getFeedbackTexts(block) {
    const okRaw =
        block && block.dataset && block.dataset.cePipDoubleFeedbackOk != null
            ? String(block.dataset.cePipDoubleFeedbackOk).trim()
            : '';
    const badRaw =
        block && block.dataset && block.dataset.cePipDoubleFeedbackBad != null
            ? String(block.dataset.cePipDoubleFeedbackBad).trim()
            : '';
    return {
        ok: okRaw || INTERACTIVE_PIP_DOUBLE_FEEDBACK_DEFAULT_OK,
        bad: badRaw || INTERACTIVE_PIP_DOUBLE_FEEDBACK_DEFAULT_BAD,
    };
}

function setTimerDisplay(block, text) {
    const el = block.querySelector('[data-ce-pip-double-timer-display]');
    if (el) el.textContent = text;
}

function getOrCreateRuntime(block) {
    let rt = runtimeByBlock.get(block);
    if (!rt) {
        rt = {
            state: ACTION_IDLE,
            startedAt: null,
            timerInterval: null,
            dryRun: false,
            recordEditor: null,
            lastGestureAt: 0,
            choiceAbort: null,
        };
        runtimeByBlock.set(block, rt);
    }
    return rt;
}

function clearTimerInterval(rt) {
    if (rt.timerInterval) {
        clearInterval(rt.timerInterval);
        rt.timerInterval = null;
    }
}

function setStartButtonState(block, state) {
    const actionBtn = block.querySelector('[data-ce-pip-double-action]');
    if (!actionBtn) return;
    actionBtn.dataset.cePipDoubleState = state;
    if (state === ACTION_RUNNING) {
        actionBtn.hidden = true;
        actionBtn.classList.remove('ce-interactive-pip-double__btn--running');
    } else if (state === ACTION_STOPPED) {
        actionBtn.hidden = true;
        actionBtn.classList.remove('ce-interactive-pip-double__btn--running');
        actionBtn.disabled = true;
        actionBtn.setAttribute('aria-label', 'Завершено');
    } else {
        actionBtn.hidden = false;
        actionBtn.textContent = 'Пуск';
        actionBtn.classList.remove('ce-interactive-pip-double__btn--running');
        actionBtn.disabled = false;
        actionBtn.setAttribute('aria-label', 'Пуск');
    }
}

function hideChoices(block) {
    const choicesEl = block.querySelector('[data-ce-pip-double-choices]');
    if (!choicesEl) return;
    choicesEl.hidden = true;
    choicesEl.innerHTML = '';
}

function unbindChoiceButtons(rt) {
    if (rt && rt.choiceAbort) {
        rt.choiceAbort.abort();
        rt.choiceAbort = null;
    }
}

function renderShuffledChoices(block, rt) {
    const choicesEl = block.querySelector('[data-ce-pip-double-choices]');
    if (!choicesEl) return;

    unbindChoiceButtons(rt);
    choicesEl.innerHTML = '';
    const shuffled = shuffleArray(PIP_DOUBLE_ANSWER_OPTIONS);

    shuffled.forEach((opt) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'ce-interactive-pip-double__choice-btn';
        btn.dataset.cePipDoubleChoice = opt.value;
        btn.textContent = opt.label;
        choicesEl.appendChild(btn);
    });

    choicesEl.hidden = false;
    bindChoiceButtons(block, rt);
    syncPipInteractiveLayoutAfterChange(block);
}

function handleChoice(block, rt, chosenValue) {
    if (rt.state !== ACTION_RUNNING) return;

    rt.state = ACTION_STOPPED;
    clearTimerInterval(rt);
    const elapsed = rt.startedAt ? formatElapsedMs(Date.now() - rt.startedAt) : '00:00';
    const correctAnswer = normalizePipDoubleCorrectAnswer(block.dataset.cePipDoubleCorrectAnswer);
    const correct = normalizePipDoubleCorrectAnswer(chosenValue) === correctAnswer;

    const resultEl = block.querySelector('[data-ce-pip-double-result]');
    if (resultEl) {
        resultEl.style.display = '';
        resultEl.textContent = buildDoubleResultText(
            elapsed,
            pipDoubleAnswerLabel(chosenValue),
            pipDoubleAnswerLabel(correctAnswer),
            correct
        );
    }

    setStartButtonState(block, ACTION_STOPPED);
    unbindChoiceButtons(rt);
    hideChoices(block);
    applyPipCountBoardGateForBlock(block, ACTION_STOPPED);
    syncPipInteractiveLayoutAfterChange(block);

    const { ok, bad } = getFeedbackTexts(block);
    if (!rt.dryRun && rt.recordEditor && rt.recordEditor._contentCardViewCardId) {
        const auth =
            typeof rt.recordEditor.getContentCardApiAuthPayload === 'function'
                ? rt.recordEditor.getContentCardApiAuthPayload()
                : null;
        if (auth) {
            void fetch('/api/content_cards/interactive/record', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ...auth,
                    content_card_id: Number(rt.recordEditor._contentCardViewCardId),
                    correct,
                }),
            }).catch((err) => console.warn('interactive/record (pip-double):', err));
        }
    }

    if (!rt.dryRun) {
        openInteractiveBestMoveFeedbackModal(correct ? ok : bad);
    }
}

function choicesElDisable(block, disabled) {
    block.querySelectorAll('[data-ce-pip-double-choice]').forEach((btn) => {
        btn.disabled = disabled;
    });
}

function bindChoiceButtons(block, rt) {
    unbindChoiceButtons(rt);
    const controller = new AbortController();
    rt.choiceAbort = controller;
    const signal = controller.signal;

    block.querySelectorAll('[data-ce-pip-double-choice]').forEach((btn) => {
        const onPick = (e) => {
            const now = Date.now();
            if (now - (rt.lastGestureAt || 0) < 320) return;
            rt.lastGestureAt = now;
            if (e && typeof e.stopPropagation === 'function') e.stopPropagation();
            if (e && typeof e.preventDefault === 'function') e.preventDefault();
            handleChoice(block, rt, btn.dataset.cePipDoubleChoice);
        };

        btn.addEventListener('mousedown', (e) => e.stopPropagation(), { signal });
        btn.addEventListener('click', onPick, { signal });
        btn.addEventListener('touchend', onPick, { signal, passive: false });
        btn.onclick = (e) => {
            onPick(e || window.event);
            return false;
        };
    });
}

function handleStart(block, rt) {
    if (rt.state !== ACTION_IDLE) return;
    rt.state = ACTION_RUNNING;
    rt.startedAt = Date.now();
    setTimerDisplay(block, '00:00');
    clearTimerInterval(rt);
    rt.timerInterval = setInterval(() => {
        if (!rt.startedAt) return;
        setTimerDisplay(block, formatElapsedMs(Date.now() - rt.startedAt));
    }, 250);
    setStartButtonState(block, ACTION_RUNNING);
    renderShuffledChoices(block, rt);
    choicesElDisable(block, false);
    applyPipCountBoardGateForBlock(block, ACTION_RUNNING);
}

function unbindStartButton(rt) {
    if (rt && rt.actionAbort) {
        rt.actionAbort.abort();
        rt.actionAbort = null;
    }
    if (rt) rt.actionOnClick = null;
}

function bindStartButton(block, rt) {
    unbindStartButton(rt);
    const actionBtn = block.querySelector('[data-ce-pip-double-action]');
    if (!actionBtn) return;

    const controller = new AbortController();
    rt.actionAbort = controller;
    const signal = controller.signal;

    const onAction = (e) => {
        const now = Date.now();
        if (now - (rt.lastGestureAt || 0) < 320) return;
        rt.lastGestureAt = now;
        if (e && typeof e.stopPropagation === 'function') e.stopPropagation();
        if (e && typeof e.preventDefault === 'function' && e.type === 'click') e.preventDefault();
        if (rt.state === ACTION_IDLE) {
            handleStart(block, rt);
        }
    };

    rt.actionOnClick = onAction;
    actionBtn.addEventListener('mousedown', (e) => e.stopPropagation(), { signal });
    actionBtn.addEventListener('click', onAction, { signal });
    actionBtn.addEventListener('touchend', onAction, { signal, passive: false });
    actionBtn.onclick = (e) => {
        onAction(e || window.event);
        return false;
    };
}

function syncBlockUi(block, options = {}) {
    const rt = getOrCreateRuntime(block);
    clearTimerInterval(rt);
    rt.state = ACTION_IDLE;
    rt.startedAt = null;
    rt.dryRun = !!options.dryRun;
    rt.recordEditor = options.recordEditor || null;
    rt.lastGestureAt = 0;

    ensurePipDoubleDatasetDefaults(block);

    const resultEl = block.querySelector('[data-ce-pip-double-result]');
    if (resultEl) {
        resultEl.style.display = 'none';
        resultEl.textContent = '';
    }

    hideChoices(block);
    unbindChoiceButtons(rt);
    setStartButtonState(block, ACTION_IDLE);
    setTimerDisplay(block, '00:00');
    bindStartButton(block, rt);
    applyPipCountBoardGateForBlock(block, ACTION_IDLE);
    syncPipInteractiveLayoutAfterChange(block);
    block.dataset.cePipDoubleBound = '1';
}

export function mountInteractivePipDoubleBlock(block, options = {}) {
    if (!block) return;
    syncBlockUi(block, options);
}

export function setupInteractivePipDoubleAfterCardPreviewRender(editor, _payload) {
    if (typeof window === 'undefined') return;
    const host = document.getElementById('cardPreviewFrameHost');
    if (!host) return;

    const viewOnly = window.__CONTENT_CARD_VIEW_ONLY__ === true;
    const editorPreview =
        !viewOnly &&
        editor &&
        editor.cardPreviewModal &&
        editor.cardPreviewModal.style.display === 'flex';

    if (!viewOnly && !editorPreview) return;
    if (viewOnly && (!editor || !editor._contentCardViewCardId)) return;

    const recordStats = viewOnly && !!editor._contentCardViewCardId;

    host.querySelectorAll('.canvas-element[data-tool-id="interactive-pip-double"]').forEach((block) => {
        mountInteractivePipDoubleBlock(block, {
            dryRun: false,
            recordEditor: recordStats ? editor : null,
        });
    });
    applyPipCountBoardGateForPreviewHost(host, ACTION_IDLE);
}

export function refreshInteractivePipDoublePreviewBlocks(_editor, _payload, rootEl) {
    const host = rootEl || document.getElementById('cardPreviewFrameHost');
    if (!host) return;
    host.querySelectorAll('.canvas-element[data-tool-id="interactive-pip-double"]').forEach((block) => {
        mountInteractivePipDoubleBlock(block, { dryRun: true });
    });
    if (host.querySelector('.canvas-element[data-tool-id="interactive-pip-double"]')) {
        applyPipCountBoardGateForPreviewHost(host, ACTION_IDLE);
    }
}
