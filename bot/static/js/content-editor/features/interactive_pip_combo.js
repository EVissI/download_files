/**
 * Интерактив «Пипсы+Решение по кубу»: один таймер, сначала ввод пипсов, затем выбор по кубу, общий результат.
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
const { resolveReferencePipsFromPayload } = await import(withFeatureCacheQs('./pip_count_utils.js'));
const {
    PIP_DOUBLE_ANSWER_OPTIONS,
    normalizePipDoubleCorrectAnswer,
    pipDoubleAnswerLabel,
    INTERACTIVE_PIP_DOUBLE_DISPLAY_NAME,
} = await import(withFeatureCacheQs('./interactive_pip_double.js'));
const {
    applyPipCountBoardGateForBlock,
    applyPipCountBoardGateForPreviewHost,
    syncPipInteractiveLayoutAfterChange,
    bindPipNumericInputFields,
    setPipNumericInputsInteractionState,
    INTERACTIVE_PIP_COUNT_FEEDBACK_DEFAULT_OK,
    INTERACTIVE_PIP_COUNT_FEEDBACK_DEFAULT_BAD,
} = await import(withFeatureCacheQs('./interactive_pip_count.js'));
const { buildComboResultText } = await import(withFeatureCacheQs('./pip_result_format.js'));

export const INTERACTIVE_PIP_COMBO_TOOL_ID = 'interactive-pip-combo';
export const INTERACTIVE_PIP_COMBO_DISPLAY_NAME = 'Пипсы+' + INTERACTIVE_PIP_DOUBLE_DISPLAY_NAME;

const ACTION_IDLE = 'idle';
const ACTION_RUNNING = 'running';
const ACTION_STOPPED = 'stopped';
const PHASE_PIPS = 'pips';
const PHASE_DOUBLE = 'double';

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

function parseInputPips(raw) {
    const t = String(raw ?? '').trim();
    if (t === '') return null;
    const n = parseInt(t, 10);
    return Number.isFinite(n) ? n : null;
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

export function ensurePipComboDatasetDefaults(block) {
    if (!block) return;
    block.dataset.cePipComboDoubleCorrectAnswer = normalizePipDoubleCorrectAnswer(
        block.dataset.cePipComboDoubleCorrectAnswer
    );
    if (!String(block.dataset.cePipComboFeedbackOk || '').trim()) {
        block.dataset.cePipComboFeedbackOk = INTERACTIVE_PIP_COUNT_FEEDBACK_DEFAULT_OK;
    }
    if (!String(block.dataset.cePipComboFeedbackBad || '').trim()) {
        block.dataset.cePipComboFeedbackBad = INTERACTIVE_PIP_COUNT_FEEDBACK_DEFAULT_BAD;
    }
    const titleEl = block.querySelector('.ce-interactive-pip-combo__title');
    if (titleEl) titleEl.textContent = INTERACTIVE_PIP_COMBO_DISPLAY_NAME;
}

export function getInteractivePipComboInnerHtml() {
    return `
                    <div class="ce-interactive-pip-combo__inner">
                        <p class="ce-interactive-pip-combo__title">${INTERACTIVE_PIP_COMBO_DISPLAY_NAME}</p>
                        <div class="ce-interactive-pip-combo__controls" data-ce-pip-combo-controls>
                            <div class="ce-interactive-pip-combo__timer-row" data-ce-pip-combo-timer-row>
                                <button type="button" class="ce-interactive-pip-combo__btn" data-ce-pip-combo-action data-ce-pip-combo-state="idle" aria-label="Пуск">Пуск</button>
                                <span class="ce-interactive-pip-combo__timer" data-ce-pip-combo-timer-display>00:00</span>
                            </div>
                            <div class="ce-interactive-pip-combo__pips" data-ce-pip-combo-pips-section>
                                <div class="ce-interactive-pip-count__inputs">
                                    <label class="ce-interactive-pip-count__field">
                                        <span class="ce-interactive-pip-count__field-label">Верхний</span>
                                        <input type="text" class="ce-interactive-pip-count__input" data-ce-pip-upper inputmode="numeric" autocomplete="off" enterkeyhint="done">
                                    </label>
                                    <label class="ce-interactive-pip-count__field">
                                        <span class="ce-interactive-pip-count__field-label">Нижний</span>
                                        <input type="text" class="ce-interactive-pip-count__input" data-ce-pip-lower inputmode="numeric" autocomplete="off" enterkeyhint="done">
                                    </label>
                                </div>
                            </div>
                            <div class="ce-interactive-pip-double__choices" data-ce-pip-combo-choices hidden></div>
                            <pre class="ce-interactive-pip-combo__result" data-ce-pip-combo-result style="display:none"></pre>
                        </div>
                    </div>`;
}

function getFeedbackTexts(block) {
    const okRaw =
        block && block.dataset && block.dataset.cePipComboFeedbackOk != null
            ? String(block.dataset.cePipComboFeedbackOk).trim()
            : '';
    const badRaw =
        block && block.dataset && block.dataset.cePipComboFeedbackBad != null
            ? String(block.dataset.cePipComboFeedbackBad).trim()
            : '';
    return {
        ok: okRaw || INTERACTIVE_PIP_COUNT_FEEDBACK_DEFAULT_OK,
        bad: badRaw || INTERACTIVE_PIP_COUNT_FEEDBACK_DEFAULT_BAD,
    };
}

function setTimerDisplay(block, text) {
    const el = block.querySelector('[data-ce-pip-combo-timer-display]');
    if (el) el.textContent = text;
}

function getOrCreateRuntime(block) {
    let rt = runtimeByBlock.get(block);
    if (!rt) {
        rt = {
            state: ACTION_IDLE,
            phase: PHASE_PIPS,
            startedAt: null,
            timerInterval: null,
            dryRun: false,
            recordEditor: null,
            reference: null,
            payload: null,
            sharedContext: null,
            lastGestureAt: 0,
            savedUpper: null,
            savedLower: null,
            actionAbort: null,
            choiceAbort: null,
            inputMirrorAbort: null,
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

function resolveRef(block, rt) {
    if (rt.reference) return rt.reference;
    const fromStored = resolveReferencePipsFromPayload(rt.payload, rt.sharedContext);
    if (fromStored) return fromStored;
    return resolveReferencePipsFromPayload(null, null);
}

function setPipsSectionVisible(block, visible) {
    const section = block.querySelector('[data-ce-pip-combo-pips-section]');
    if (section) section.hidden = !visible;
}

function hideChoices(block) {
    const choicesEl = block.querySelector('[data-ce-pip-combo-choices]');
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

function choicesElDisable(block, disabled) {
    block.querySelectorAll('[data-ce-pip-combo-choice]').forEach((btn) => {
        btn.disabled = disabled;
    });
}

function setActionButtonState(block, state, phase) {
    const actionBtn = block.querySelector('[data-ce-pip-combo-action]');
    if (!actionBtn) return;
    actionBtn.dataset.cePipComboState = state;
    if (state === ACTION_RUNNING && phase === PHASE_PIPS) {
        actionBtn.hidden = false;
        actionBtn.textContent = 'Далее';
        actionBtn.classList.add('ce-interactive-pip-combo__btn--running');
        actionBtn.disabled = false;
        actionBtn.setAttribute('aria-label', 'Подтвердить пипсы и перейти к решению по кубу');
    } else if (state === ACTION_RUNNING && phase === PHASE_DOUBLE) {
        actionBtn.hidden = true;
        actionBtn.classList.remove('ce-interactive-pip-combo__btn--running');
    } else if (state === ACTION_STOPPED) {
        actionBtn.hidden = true;
        actionBtn.classList.remove('ce-interactive-pip-combo__btn--running');
        actionBtn.disabled = true;
        actionBtn.setAttribute('aria-label', 'Завершено');
    } else {
        actionBtn.hidden = false;
        actionBtn.textContent = 'Пуск';
        actionBtn.classList.remove('ce-interactive-pip-combo__btn--running');
        actionBtn.disabled = false;
        actionBtn.setAttribute('aria-label', 'Пуск');
    }
}

function renderShuffledChoices(block, rt) {
    const choicesEl = block.querySelector('[data-ce-pip-combo-choices]');
    if (!choicesEl) return;

    unbindChoiceButtons(rt);
    choicesEl.innerHTML = '';
    const shuffled = shuffleArray(PIP_DOUBLE_ANSWER_OPTIONS);

    shuffled.forEach((opt) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'ce-interactive-pip-double__choice-btn';
        btn.dataset.cePipComboChoice = opt.value;
        btn.textContent = opt.label;
        choicesEl.appendChild(btn);
    });

    choicesEl.hidden = false;
    bindChoiceButtons(block, rt);
}

function recordComboStats(block, rt, correct) {
    if (rt.dryRun || !rt.recordEditor || !rt.recordEditor._contentCardViewCardId) return;
    const auth =
        typeof rt.recordEditor.getContentCardApiAuthPayload === 'function'
            ? rt.recordEditor.getContentCardApiAuthPayload()
            : null;
    if (!auth) return;
    void fetch('/api/content_cards/interactive/record', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            ...auth,
            content_card_id: Number(rt.recordEditor._contentCardViewCardId),
            correct,
        }),
    }).catch((err) => console.warn('interactive/record (pip-combo):', err));
}

function finishCombo(block, rt, resultText, overallCorrect) {
    const resultEl = block.querySelector('[data-ce-pip-combo-result]');
    if (resultEl) {
        resultEl.style.display = '';
        resultEl.textContent = resultText;
    }

    rt.state = ACTION_STOPPED;
    clearTimerInterval(rt);
    setActionButtonState(block, ACTION_STOPPED, rt.phase);
    unbindChoiceButtons(rt);
    hideChoices(block);
    applyPipCountBoardGateForBlock(block, ACTION_STOPPED);
    syncPipInteractiveLayoutAfterChange(block);

    const { ok, bad } = getFeedbackTexts(block);
    recordComboStats(block, rt, overallCorrect);

    if (!rt.dryRun) {
        openInteractiveBestMoveFeedbackModal(overallCorrect ? ok : bad);
    }
}

function handleChoice(block, rt, chosenValue) {
    if (rt.state !== ACTION_RUNNING || rt.phase !== PHASE_DOUBLE) return;

    const elapsed = rt.startedAt ? formatElapsedMs(Date.now() - rt.startedAt) : '00:00';
    const ref = resolveRef(block, rt);
    const correctAnswer = normalizePipDoubleCorrectAnswer(block.dataset.cePipComboDoubleCorrectAnswer);
    const doubleCorrect = normalizePipDoubleCorrectAnswer(chosenValue) === correctAnswer;

    let pipsCorrect = false;
    if (ref) {
        const upperOk = rt.savedUpper === ref.upperPips;
        const lowerOk = rt.savedLower === ref.lowerPips;
        pipsCorrect = upperOk && lowerOk;
    }

    const overallCorrect = !!ref && pipsCorrect && doubleCorrect;

    finishCombo(
        block,
        rt,
        buildComboResultText(
            elapsed,
            ref,
            rt.savedUpper,
            rt.savedLower,
            pipDoubleAnswerLabel(chosenValue),
            pipDoubleAnswerLabel(correctAnswer),
            doubleCorrect
        ),
        overallCorrect
    );
}

function bindChoiceButtons(block, rt) {
    unbindChoiceButtons(rt);
    const controller = new AbortController();
    rt.choiceAbort = controller;
    const { signal } = controller.signal;

    block.querySelectorAll('[data-ce-pip-combo-choice]').forEach((btn) => {
        const onPick = (e) => {
            const now = Date.now();
            if (now - (rt.lastGestureAt || 0) < 320) return;
            rt.lastGestureAt = now;
            if (e && typeof e.stopPropagation === 'function') e.stopPropagation();
            if (e && typeof e.preventDefault === 'function') e.preventDefault();
            handleChoice(block, rt, btn.dataset.cePipComboChoice);
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

function handleStart(block, rt, options = {}) {
    if (rt.state !== ACTION_IDLE) return;
    rt.state = ACTION_RUNNING;
    rt.phase = PHASE_PIPS;
    rt.startedAt = Date.now();
    rt.savedUpper = null;
    rt.savedLower = null;
    setTimerDisplay(block, '00:00');
    clearTimerInterval(rt);
    rt.timerInterval = setInterval(() => {
        if (!rt.startedAt) return;
        setTimerDisplay(block, formatElapsedMs(Date.now() - rt.startedAt));
    }, 250);
    setPipsSectionVisible(block, true);
    hideChoices(block);
    setActionButtonState(block, ACTION_RUNNING, PHASE_PIPS);
    setPipNumericInputsInteractionState(block, ACTION_RUNNING);
    applyPipCountBoardGateForBlock(block, ACTION_RUNNING);

    const focusInput =
        options.focusInput && block.contains(options.focusInput)
            ? options.focusInput
            : block.querySelector('[data-ce-pip-upper]');
    if (focusInput) {
        try {
            focusInput.focus();
        } catch (_e) {
            /* noop */
        }
    }
}

function handleConfirmPips(block, rt) {
    if (rt.state !== ACTION_RUNNING || rt.phase !== PHASE_PIPS) return;

    const upperInput = block.querySelector('[data-ce-pip-upper]');
    const lowerInput = block.querySelector('[data-ce-pip-lower]');
    rt.savedUpper = parseInputPips(upperInput && upperInput.value);
    rt.savedLower = parseInputPips(lowerInput && lowerInput.value);

    setPipNumericInputsInteractionState(block, ACTION_STOPPED);
    setPipsSectionVisible(block, false);
    hidePipInputFocus(block);

    rt.phase = PHASE_DOUBLE;
    setActionButtonState(block, ACTION_RUNNING, PHASE_DOUBLE);
    renderShuffledChoices(block, rt);
    choicesElDisable(block, false);
    syncPipInteractiveLayoutAfterChange(block);
}

function hidePipInputFocus(block) {
    block.querySelectorAll('[data-ce-pip-upper], [data-ce-pip-lower]').forEach((input) => {
        try {
            input.blur();
        } catch (_e) {
            /* noop */
        }
    });
}

function unbindActionButton(rt) {
    if (rt && rt.actionAbort) {
        rt.actionAbort.abort();
        rt.actionAbort = null;
    }
    if (rt) rt.actionOnClick = null;
}

function bindActionButton(block, rt) {
    unbindActionButton(rt);
    const actionBtn = block.querySelector('[data-ce-pip-combo-action]');
    if (!actionBtn) return;

    const controller = new AbortController();
    rt.actionAbort = controller;
    const { signal } = controller.signal;

    const onAction = (e) => {
        const now = Date.now();
        if (now - (rt.lastGestureAt || 0) < 320) return;
        rt.lastGestureAt = now;
        if (e && typeof e.stopPropagation === 'function') e.stopPropagation();
        if (e && typeof e.preventDefault === 'function' && e.type === 'click') e.preventDefault();

        if (rt.state === ACTION_IDLE) {
            handleStart(block, rt);
        } else if (rt.state === ACTION_RUNNING && rt.phase === PHASE_PIPS) {
            handleConfirmPips(block, rt);
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

function bindPipInputs(block, rt) {
    bindPipNumericInputFields(block, rt, {
        canStart: () => rt.state === ACTION_IDLE,
        onStart: (input) => handleStart(block, rt, { focusInput: input }),
    });
}

function resetInputs(block) {
    const upperInput = block.querySelector('[data-ce-pip-upper]');
    const lowerInput = block.querySelector('[data-ce-pip-lower]');
    if (upperInput) upperInput.value = '';
    if (lowerInput) lowerInput.value = '';
}

function syncBlockUi(block, options = {}) {
    const rt = getOrCreateRuntime(block);
    clearTimerInterval(rt);
    rt.state = ACTION_IDLE;
    rt.phase = PHASE_PIPS;
    rt.startedAt = null;
    rt.savedUpper = null;
    rt.savedLower = null;
    rt.dryRun = !!options.dryRun;
    rt.recordEditor = options.recordEditor || null;
    rt.reference = options.reference || null;
    rt.payload = options.payload || null;
    rt.sharedContext = options.sharedContext || null;
    rt.lastGestureAt = 0;

    ensurePipComboDatasetDefaults(block);

    const resultEl = block.querySelector('[data-ce-pip-combo-result]');
    if (resultEl) {
        resultEl.style.display = 'none';
        resultEl.textContent = '';
    }

    resetInputs(block);
    setPipsSectionVisible(block, true);
    hideChoices(block);
    unbindChoiceButtons(rt);
    setActionButtonState(block, ACTION_IDLE, PHASE_PIPS);
    setTimerDisplay(block, '00:00');
    setPipNumericInputsInteractionState(block, ACTION_IDLE);
    bindActionButton(block, rt);
    bindPipInputs(block, rt);
    applyPipCountBoardGateForBlock(block, ACTION_IDLE);
    syncPipInteractiveLayoutAfterChange(block);
    block.dataset.cePipComboBound = '1';
}

export function mountInteractivePipComboBlock(block, options = {}) {
    if (!block) return;
    syncBlockUi(block, options);
}

export function setupInteractivePipComboAfterCardPreviewRender(editor, payload) {
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

    const sharedContext =
        editor._contentCardSharedContext && typeof editor._contentCardSharedContext === 'object'
            ? editor._contentCardSharedContext
            : null;

    const recordStats = viewOnly && !!editor._contentCardViewCardId;

    host.querySelectorAll('.canvas-element[data-tool-id="interactive-pip-combo"]').forEach((block) => {
        mountInteractivePipComboBlock(block, {
            dryRun: false,
            recordEditor: recordStats ? editor : null,
            payload,
            sharedContext,
        });
    });
}

export function refreshInteractivePipComboPreviewBlocks(editor, payload, rootEl) {
    const host = rootEl || document.getElementById('cardPreviewFrameHost');
    if (!host) return;
    const sharedContext =
        editor && editor._contentCardSharedContext && typeof editor._contentCardSharedContext === 'object'
            ? editor._contentCardSharedContext
            : null;
    host.querySelectorAll('.canvas-element[data-tool-id="interactive-pip-combo"]').forEach((block) => {
        mountInteractivePipComboBlock(block, {
            dryRun: true,
            payload,
            sharedContext,
        });
    });
}
