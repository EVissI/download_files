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

function isShowTimer(block) {
    const v = block && block.dataset ? block.dataset.cePipCountShowTimer : null;
    if (v == null || v === '') return true;
    const s = String(v).trim().toLowerCase();
    return s !== '0' && s !== 'false' && s !== 'no';
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
    return resolveReferencePipsFromPayload(rt.payload, rt.sharedContext);
}

function setInputsDisabled(block, disabled) {
    const upperInput = block.querySelector('[data-ce-pip-upper]');
    const lowerInput = block.querySelector('[data-ce-pip-lower]');
    if (upperInput) upperInput.disabled = disabled;
    if (lowerInput) lowerInput.disabled = disabled;
}

function handlePipStart(block, rt) {
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
    const upperInput = block.querySelector('[data-ce-pip-upper]');
    if (upperInput) {
        try {
            upperInput.focus();
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

    setActionButtonState(block, PIP_ACTION_STOPPED);
    setInputsDisabled(block, true);

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

    const timerRow = block.querySelector('[data-ce-pip-timer-row]');
    if (timerRow) {
        timerRow.style.display = isShowTimer(block) ? '' : 'none';
    }

    const resultEl = block.querySelector('[data-ce-pip-result]');
    if (resultEl) {
        resultEl.style.display = 'none';
        resultEl.textContent = '';
    }

    setActionButtonState(block, PIP_ACTION_IDLE);
    setInputsDisabled(block, false);
    setTimerDisplay(block, '00:00');
    bindPipActionButton(block, rt);

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
}
