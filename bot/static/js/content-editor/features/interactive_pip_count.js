/**
 * Интерактив «Подсчёт пипсов»: таймер, поля ввода, проверка по снимку доски.
 */

/* Статический import без ?t= в WebView кешируется отдельно — пробрасываем query из этого модуля. */
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

export const INTERACTIVE_PIP_COUNT_FEEDBACK_DEFAULT_OK = 'Правильно';
export const INTERACTIVE_PIP_COUNT_FEEDBACK_DEFAULT_BAD = 'Неправильно';

const PIP_ACTION_IDLE = 'idle';
const PIP_ACTION_RUNNING = 'running';
const PIP_ACTION_STOPPED = 'stopped';

/** @type {WeakMap<HTMLElement, object>} */
const pipRuntimeByBlock = new WeakMap();

const PIP_MOBILE_INPUT_MIRROR_MAX_WIDTH = 768;

/** @type {HTMLElement|null} */
let pipInputMirrorEl = null;
/** @type {HTMLInputElement|null} */
let pipInputMirrorActiveInput = null;
let pipInputMirrorViewportBound = false;
let pipInputMirrorKeyboardWasOpen = false;

function isNarrowPipInputViewport() {
    if (typeof window === 'undefined') return false;
    return window.innerWidth <= PIP_MOBILE_INPUT_MIRROR_MAX_WIDTH;
}

function ensurePipInputMirrorEl() {
    if (pipInputMirrorEl) return pipInputMirrorEl;
    if (typeof document === 'undefined') return null;
    const el = document.createElement('div');
    el.className = 'ce-pip-count-input-mirror';
    el.hidden = true;
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
    el.setAttribute('aria-hidden', 'true');
    el.innerHTML =
        '<span class="ce-pip-count-input-mirror__label"></span>' +
        '<span class="ce-pip-count-input-mirror__value"></span>';
    document.body.appendChild(el);
    pipInputMirrorEl = el;
    return el;
}

function getLayoutViewportHeight() {
    if (typeof window === 'undefined') return 0;
    return window.innerHeight || document.documentElement.clientHeight || 0;
}

function isPipMobileKeyboardOpen() {
    const vv = typeof window !== 'undefined' ? window.visualViewport : null;
    const layoutH = getLayoutViewportHeight();
    if (!vv || layoutH <= 0) return false;
    return vv.height < layoutH * 0.82;
}

function positionPipInputMirror() {
    if (!pipInputMirrorEl || pipInputMirrorEl.hidden) return;
    const vv = typeof window !== 'undefined' ? window.visualViewport : null;
    if (!vv) {
        pipInputMirrorEl.style.top = '72px';
        return;
    }
    const visibleTop = vv.offsetTop;
    const visibleH = vv.height;
    const offsetInVisible = Math.max(64, Math.min(visibleH * 0.4, visibleH - 72));
    pipInputMirrorEl.style.top = `${Math.round(visibleTop + offsetInVisible)}px`;
}

function syncPipInputMirrorWithViewport() {
    if (!pipInputMirrorEl || pipInputMirrorEl.hidden || !pipInputMirrorActiveInput) return;

    const keyboardOpen = isPipMobileKeyboardOpen();
    if (keyboardOpen) {
        pipInputMirrorKeyboardWasOpen = true;
        positionPipInputMirror();
        return;
    }

    if (pipInputMirrorKeyboardWasOpen) {
        pipInputMirrorKeyboardWasOpen = false;
        hidePipInputMirror();
        return;
    }

    positionPipInputMirror();
}

function bindPipInputMirrorViewport() {
    if (pipInputMirrorViewportBound || typeof window === 'undefined') return;
    pipInputMirrorViewportBound = true;
    const onViewportChange = () => syncPipInputMirrorWithViewport();
    window.addEventListener('resize', onViewportChange);
    if (window.visualViewport) {
        window.visualViewport.addEventListener('resize', onViewportChange);
        window.visualViewport.addEventListener('scroll', onViewportChange);
    }
}

function getPipInputFieldLabel(input) {
    const field = input && input.closest ? input.closest('.ce-interactive-pip-count__field') : null;
    const labelEl = field ? field.querySelector('.ce-interactive-pip-count__field-label') : null;
    return labelEl ? String(labelEl.textContent || '').trim() : '';
}

function formatPipInputMirrorValue(raw) {
    const t = String(raw ?? '');
    return t !== '' ? t : '—';
}

function showPipInputMirror(input) {
    if (!input || !isNarrowPipInputViewport()) return;
    const el = ensurePipInputMirrorEl();
    if (!el) return;
    bindPipInputMirrorViewport();
    pipInputMirrorKeyboardWasOpen = false;
    pipInputMirrorActiveInput = input;
    const labelEl = el.querySelector('.ce-pip-count-input-mirror__label');
    const valueEl = el.querySelector('.ce-pip-count-input-mirror__value');
    if (labelEl) labelEl.textContent = getPipInputFieldLabel(input) || 'Ввод';
    if (valueEl) valueEl.textContent = formatPipInputMirrorValue(input.value);
    el.hidden = false;
    el.setAttribute('aria-hidden', 'false');
    el.classList.add('ce-pip-count-input-mirror--visible');
    positionPipInputMirror();
    requestAnimationFrame(() => syncPipInputMirrorWithViewport());
}

function updatePipInputMirror(input) {
    if (!pipInputMirrorEl || pipInputMirrorEl.hidden || pipInputMirrorActiveInput !== input) return;
    const valueEl = pipInputMirrorEl.querySelector('.ce-pip-count-input-mirror__value');
    if (valueEl) valueEl.textContent = formatPipInputMirrorValue(input.value);
}

function hidePipInputMirror() {
    pipInputMirrorActiveInput = null;
    pipInputMirrorKeyboardWasOpen = false;
    if (!pipInputMirrorEl) return;
    pipInputMirrorEl.hidden = true;
    pipInputMirrorEl.setAttribute('aria-hidden', 'true');
    pipInputMirrorEl.classList.remove('ce-pip-count-input-mirror--visible');
}

function dismissPipInputKeyboard(input) {
    hidePipInputMirror();
    if (input && typeof input.blur === 'function') {
        try {
            input.blur();
        } catch (_e) {
            /* noop */
        }
    }
}

function unbindPipInputMobileMirror(rt) {
    if (rt && rt.inputMirrorAbort) {
        rt.inputMirrorAbort.abort();
        rt.inputMirrorAbort = null;
    }
    if (pipInputMirrorActiveInput) {
        const block = pipInputMirrorActiveInput.closest(
            '.canvas-element[data-tool-id="interactive-pip-count"], .canvas-element[data-tool-id="interactive-pip-combo"]'
        );
        const activeRt = block ? pipRuntimeByBlock.get(block) : null;
        if (activeRt === rt) {
            hidePipInputMirror();
        }
    }
}

function normalizePipCountInputEl(input) {
    if (!input) return;
    if (input.type === 'number') {
        input.type = 'text';
    }
    input.setAttribute('inputmode', 'numeric');
    input.setAttribute('autocomplete', 'off');
    input.setAttribute('enterkeyhint', 'done');
}

function setInputsInteractionState(block, pipState) {
    const inputs = block.querySelectorAll('[data-ce-pip-upper], [data-ce-pip-lower]');
    inputs.forEach((input) => {
        normalizePipCountInputEl(input);
        if (pipState === PIP_ACTION_RUNNING || pipState === PIP_ACTION_IDLE) {
            input.disabled = false;
            input.readOnly = false;
            input.classList.toggle(
                'ce-interactive-pip-count__input--locked',
                pipState === PIP_ACTION_IDLE
            );
            return;
        }
        input.disabled = true;
        input.readOnly = false;
        input.classList.remove('ce-interactive-pip-count__input--locked');
    });
}

function bindPipInputInteractions(block, rt, options = {}) {
    unbindPipInputMobileMirror(rt);
    const inputs = block.querySelectorAll('[data-ce-pip-upper], [data-ce-pip-lower]');
    if (!inputs.length) return;

    const canStart =
        typeof options.canStart === 'function' ? options.canStart : () => rt.state === PIP_ACTION_IDLE;
    const onStart =
        typeof options.onStart === 'function'
            ? options.onStart
            : (input) => handlePipStart(block, rt, { focusInput: input });

    const controller = new AbortController();
    rt.inputMirrorAbort = controller;
    const { signal } = controller;

    const stopCanvasBubble = (e) => {
        if (e && typeof e.stopPropagation === 'function') {
            e.stopPropagation();
        }
    };

    inputs.forEach((input) => {
        normalizePipCountInputEl(input);

        const tryStartOnInteract = () => {
            if (canStart()) {
                onStart(input);
            }
        };

        input.addEventListener('mousedown', (e) => {
            stopCanvasBubble(e);
            tryStartOnInteract();
        }, { signal });
        input.addEventListener('touchstart', (e) => {
            stopCanvasBubble(e);
            tryStartOnInteract();
        }, { signal, passive: true });

        input.addEventListener(
            'focus',
            () => {
                tryStartOnInteract();
                showPipInputMirror(input);
            },
            { signal }
        );

        input.addEventListener(
            'input',
            () => {
                const cleaned = String(input.value || '').replace(/\D/g, '');
                if (cleaned !== input.value) {
                    input.value = cleaned;
                }
                updatePipInputMirror(input);
            },
            { signal }
        );

        input.addEventListener(
            'keydown',
            (e) => {
                if (e.key !== 'Enter') return;
                e.preventDefault();
                dismissPipInputKeyboard(input);
            },
            { signal }
        );

        input.addEventListener(
            'blur',
            () => {
                setTimeout(() => {
                    const active = document.activeElement;
                    if (
                        active &&
                        active.matches &&
                        active.matches('[data-ce-pip-upper], [data-ce-pip-lower]')
                    ) {
                        return;
                    }
                    hidePipInputMirror();
                }, 80);
            },
            { signal }
        );
    });

    const fields = block.querySelectorAll('.ce-interactive-pip-count__field');
    fields.forEach((field) => {
        field.addEventListener('mousedown', stopCanvasBubble, { signal });
        field.addEventListener('touchstart', stopCanvasBubble, { signal, passive: true });
    });
}

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

function getFeedbackTexts(block) {
    const okRaw =
        block && block.dataset && block.dataset.cePipCountFeedbackOk != null
            ? String(block.dataset.cePipCountFeedbackOk).trim()
            : '';
    const badRaw =
        block && block.dataset && block.dataset.cePipCountFeedbackBad != null
            ? String(block.dataset.cePipCountFeedbackBad).trim()
            : '';
    return {
        ok: okRaw || INTERACTIVE_PIP_COUNT_FEEDBACK_DEFAULT_OK,
        bad: badRaw || INTERACTIVE_PIP_COUNT_FEEDBACK_DEFAULT_BAD,
    };
}

function setTimerDisplay(block, text) {
    const el = block.querySelector('[data-ce-pip-timer-display]');
    if (el) el.textContent = text;
}

function getOrCreateRuntime(block) {
    let rt = pipRuntimeByBlock.get(block);
    if (!rt) {
        rt = {
            state: PIP_ACTION_IDLE,
            startedAt: null,
            timerInterval: null,
            dryRun: false,
            recordEditor: null,
            reference: null,
            payload: null,
            sharedContext: null,
            lastGestureAt: 0,
        };
        pipRuntimeByBlock.set(block, rt);
    }
    return rt;
}

function setActionButtonState(block, state) {
    const actionBtn = block.querySelector('[data-ce-pip-action]');
    if (!actionBtn) return;
    actionBtn.dataset.cePipState = state;
    if (state === PIP_ACTION_RUNNING) {
        actionBtn.textContent = 'Стоп';
        actionBtn.classList.add('ce-interactive-pip-count__btn--running');
        actionBtn.disabled = false;
        actionBtn.setAttribute('aria-label', 'Стоп');
    } else if (state === PIP_ACTION_STOPPED) {
        actionBtn.textContent = 'Стоп';
        actionBtn.classList.remove('ce-interactive-pip-count__btn--running');
        actionBtn.disabled = true;
        actionBtn.setAttribute('aria-label', 'Завершено');
    } else {
        actionBtn.textContent = 'Пуск';
        actionBtn.classList.remove('ce-interactive-pip-count__btn--running');
        actionBtn.disabled = false;
        actionBtn.setAttribute('aria-label', 'Пуск');
    }
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

function setInputsDisabled(block, disabled) {
    setInputsInteractionState(block, disabled ? PIP_ACTION_STOPPED : PIP_ACTION_RUNNING);
}

/** Доска в карточках пипсов всегда видна — гейт по «Пуск» отключён. */
export function applyPipCountBoardGateForBlock(_block, _pipState) {}

export function applyPipCountBoardGateForPreviewHost(_hostRoot, _pipState) {}

export function syncPipCountBoardGatesInScope(_rootEl) {}

/** После показа/скрытия результата — пересчитать стек (absolute в редакторе, flex в превью). */
export function syncPipInteractiveLayoutAfterChange(block) {
    if (typeof window === 'undefined' || !block) return;
    const editor = window.contentEditor;
    if (!editor) return;

    const toolId = block.dataset && block.dataset.toolId;
    if (toolId && typeof editor.isPipInteractiveToolId === 'function' && editor.isPipInteractiveToolId(toolId)) {
        if (typeof editor.applyPipInteractiveCanvasLayout === 'function') {
            editor.applyPipInteractiveCanvasLayout(block);
        }
    } else {
        block.style.height = 'auto';
        block.style.overflow = 'visible';
    }

    const inEditorCanvas = !!(block.closest && block.closest('#canvas, #editorCanvasContentLayer'));
    const previewInner = block.closest('.card-preview-surface-inner');

    const applyLayout = () => {
        if (inEditorCanvas && typeof editor.recalculateAllElementPositions === 'function') {
            editor.recalculateAllElementPositions();
            return;
        }
        if (previewInner && typeof editor.refreshCardPreviewScale === 'function') {
            const hostRoot = previewInner.closest('.frame-templates-insert-preview-host');
            editor.refreshCardPreviewScale(hostRoot || null);
        }
    };

    requestAnimationFrame(() => {
        applyLayout();
        requestAnimationFrame(applyLayout);
    });
}

function handlePipStart(block, rt, options = {}) {
    if (rt.state !== PIP_ACTION_IDLE) return;
    rt.state = PIP_ACTION_RUNNING;
    rt.startedAt = Date.now();
    setTimerDisplay(block, '00:00');
    clearTimerInterval(rt);
    rt.timerInterval = setInterval(() => {
        if (!rt.startedAt) return;
        setTimerDisplay(block, formatElapsedMs(Date.now() - rt.startedAt));
    }, 250);
    setActionButtonState(block, PIP_ACTION_RUNNING);
    setInputsInteractionState(block, PIP_ACTION_RUNNING);
    applyPipCountBoardGateForBlock(block, PIP_ACTION_RUNNING);
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

function handlePipStop(block, rt) {
    if (rt.state !== PIP_ACTION_RUNNING) return;
    rt.state = PIP_ACTION_STOPPED;
    clearTimerInterval(rt);
    const elapsed = rt.startedAt ? formatElapsedMs(Date.now() - rt.startedAt) : '00:00';

    const upperInput = block.querySelector('[data-ce-pip-upper]');
    const lowerInput = block.querySelector('[data-ce-pip-lower]');
    const resultEl = block.querySelector('[data-ce-pip-result]');

    const ref = resolveRef(block, rt);
    const userUpper = parseInputPips(upperInput && upperInput.value);
    const userLower = parseInputPips(lowerInput && lowerInput.value);

    let correct = false;
    const detailLines = [];

    if (!ref) {
        detailLines.push('Нет данных доски для проверки.');
    } else {
        const upperOk = userUpper === ref.upperPips;
        const lowerOk = userLower === ref.lowerPips;
        correct = upperOk && lowerOk;
        detailLines.push('Время: ' + elapsed);
        detailLines.push(
            'Верхний: ваш ' +
                (userUpper != null ? userUpper : '—') +
                ', верно ' +
                ref.upperPips +
                (upperOk ? ' ✓' : ' ✗')
        );
        detailLines.push(
            'Нижний: ваш ' +
                (userLower != null ? userLower : '—') +
                ', верно ' +
                ref.lowerPips +
                (lowerOk ? ' ✓' : ' ✗')
        );
    }

    if (resultEl) {
        resultEl.style.display = '';
        resultEl.textContent = detailLines.join('\n');
    }

    syncPipInteractiveLayoutAfterChange(block);

    setActionButtonState(block, PIP_ACTION_STOPPED);
    setInputsDisabled(block, true);
    applyPipCountBoardGateForBlock(block, PIP_ACTION_STOPPED);

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
            }).catch((err) => console.warn('interactive/record (pip-count):', err));
        }
    }

    if (!rt.dryRun) {
        openInteractiveBestMoveFeedbackModal(correct ? ok : bad);
    }
}

function unbindPipActionButton(rt) {
    if (rt && rt.actionAbort) {
        rt.actionAbort.abort();
        rt.actionAbort = null;
    }
    if (rt) {
        rt.actionOnClick = null;
    }
}

function bindPipActionButton(block, rt) {
    unbindPipActionButton(rt);
    const actionBtn = block.querySelector('[data-ce-pip-action]');
    if (!actionBtn) return;

    const controller = new AbortController();
    rt.actionAbort = controller;
    const signal = controller.signal;

    const onMousedown = (e) => {
        if (e && typeof e.stopPropagation === 'function') {
            e.stopPropagation();
        }
    };

    const onAction = (e) => {
        const now = Date.now();
        if (now - (rt.lastGestureAt || 0) < 320) return;
        rt.lastGestureAt = now;

        if (e && typeof e.stopPropagation === 'function') {
            e.stopPropagation();
        }
        if (e && typeof e.preventDefault === 'function' && e.type === 'click') {
            e.preventDefault();
        }
        if (rt.state === PIP_ACTION_IDLE) {
            handlePipStart(block, rt);
        } else if (rt.state === PIP_ACTION_RUNNING) {
            handlePipStop(block, rt);
        }
    };

    rt.actionOnClick = onAction;

    actionBtn.addEventListener('mousedown', onMousedown, { signal });
    actionBtn.addEventListener('click', onAction, { signal });
    actionBtn.addEventListener('touchend', onAction, { signal, passive: false });

    // Telegram Desktop WebView иногда не доставляет addEventListener('click').
    actionBtn.onclick = (e) => {
        onAction(e || window.event);
        return false;
    };
}

function syncPipCountBlockUi(block, options = {}) {
    const rt = getOrCreateRuntime(block);
    clearTimerInterval(rt);
    rt.state = PIP_ACTION_IDLE;
    rt.startedAt = null;
    rt.dryRun = !!options.dryRun;
    rt.recordEditor = options.recordEditor || null;
    rt.reference = options.reference || null;
    rt.payload = options.payload || null;
    rt.sharedContext = options.sharedContext || null;
    rt.lastGestureAt = 0;

    const resultEl = block.querySelector('[data-ce-pip-result]');
    if (resultEl) {
        resultEl.style.display = 'none';
        resultEl.textContent = '';
    }

    setActionButtonState(block, PIP_ACTION_IDLE);
    setInputsInteractionState(block, PIP_ACTION_IDLE);
    setTimerDisplay(block, '00:00');
    bindPipActionButton(block, rt);
    bindPipInputInteractions(block, rt);
    applyPipCountBoardGateForBlock(block, PIP_ACTION_IDLE);

    syncPipInteractiveLayoutAfterChange(block);

    block.dataset.cePipCountBound = '1';
}

export function mountInteractivePipCountBlock(block, options = {}) {
    if (!block) return;
    syncPipCountBlockUi(block, options);
}

export function setupInteractivePipCountAfterCardPreviewRender(editor, payload) {
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

    host.querySelectorAll('.canvas-element[data-tool-id="interactive-pip-count"]').forEach((block) => {
        mountInteractivePipCountBlock(block, {
            dryRun: false,
            recordEditor: recordStats ? editor : null,
            payload,
            sharedContext,
        });
    });
    applyPipCountBoardGateForPreviewHost(host, PIP_ACTION_IDLE);
}

export function bindPipNumericInputFields(block, rt, options = {}) {
    bindPipInputInteractions(block, rt, options);
}

export function setPipNumericInputsInteractionState(block, pipState) {
    setInputsInteractionState(block, pipState);
}

export function normalizePipNumericInputEl(input) {
    normalizePipCountInputEl(input);
}

export function refreshInteractivePipCountPreviewBlocks(editor, payload, rootEl) {
    const host = rootEl || document.getElementById('cardPreviewFrameHost');
    if (!host) return;
    const sharedContext =
        editor && editor._contentCardSharedContext && typeof editor._contentCardSharedContext === 'object'
            ? editor._contentCardSharedContext
            : null;
    host.querySelectorAll('.canvas-element[data-tool-id="interactive-pip-count"]').forEach((block) => {
        mountInteractivePipCountBlock(block, {
            dryRun: true,
            payload,
            sharedContext,
        });
    });
    if (host.querySelector('.canvas-element[data-tool-id="interactive-pip-count"]')) {
        applyPipCountBoardGateForPreviewHost(host, PIP_ACTION_IDLE);
    }
}
