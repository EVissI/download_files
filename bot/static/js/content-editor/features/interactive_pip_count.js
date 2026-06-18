/**
 * Интерактив «Подсчёт пипсов»: таймер, поля ввода, проверка по снимку доски.
 */

import { openInteractiveBestMoveFeedbackModal } from './interactive_best_move.js';
import { resolveReferencePipsFromPayload } from './pip_count_utils.js';

export const INTERACTIVE_PIP_COUNT_FEEDBACK_DEFAULT_OK = 'Правильно';
export const INTERACTIVE_PIP_COUNT_FEEDBACK_DEFAULT_BAD = 'Неправильно';

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

function bindInteractivePipCountBlock(block, options = {}) {
    if (!block || block.dataset.cePipCountBound === '1') return;
    block.dataset.cePipCountBound = '1';

    const dryRun = !!options.dryRun;
    const recordEditor = options.recordEditor || null;
    const reference = options.reference || null;
    const payload = options.payload || null;
    const sharedContext = options.sharedContext || null;

    const startBtn = block.querySelector('[data-ce-pip-start]');
    const stopBtn = block.querySelector('[data-ce-pip-stop]');
    const upperInput = block.querySelector('[data-ce-pip-upper]');
    const lowerInput = block.querySelector('[data-ce-pip-lower]');
    const resultEl = block.querySelector('[data-ce-pip-result]');
    const timerRow = block.querySelector('[data-ce-pip-timer-row]');

    if (timerRow) {
        timerRow.style.display = isShowTimer(block) ? '' : 'none';
    }

    let startedAt = null;
    let timerInterval = null;
    let stopped = false;

    function clearTimerInterval() {
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
    }

    function getElapsedMs() {
        if (!startedAt) return 0;
        return Date.now() - startedAt;
    }

    function updateTimerTick() {
        setTimerDisplay(block, formatElapsedMs(getElapsedMs()));
    }

    function resolveRef() {
        if (reference) return reference;
        return resolveReferencePipsFromPayload(payload, sharedContext);
    }

    function setControlsDisabled(disabled) {
        if (startBtn) startBtn.disabled = disabled && stopped;
        if (stopBtn) stopBtn.disabled = disabled && !startedAt && !stopped;
        if (upperInput) upperInput.disabled = disabled && stopped;
        if (lowerInput) lowerInput.disabled = disabled && stopped;
    }

    if (startBtn) {
        startBtn.addEventListener('mousedown', (e) => e.stopPropagation());
        startBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (stopped) return;
            startedAt = Date.now();
            setTimerDisplay(block, '00:00');
            clearTimerInterval();
            timerInterval = setInterval(updateTimerTick, 250);
            if (startBtn) startBtn.disabled = true;
            if (upperInput) upperInput.focus();
        });
    }

    if (stopBtn) {
        stopBtn.addEventListener('mousedown', (e) => e.stopPropagation());
        stopBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (stopped) return;
            stopped = true;
            clearTimerInterval();
            const elapsed = formatElapsedMs(getElapsedMs());

            const ref = resolveRef();
            const userUpper = parseInputPips(upperInput && upperInput.value);
            const userLower = parseInputPips(lowerInput && lowerInput.value);

            let correct = false;
            let detailLines = [];

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

            setControlsDisabled(true);
            if (startBtn) startBtn.disabled = true;
            if (stopBtn) stopBtn.disabled = true;

            const { ok, bad } = getFeedbackTexts(block);
            if (!dryRun && recordEditor && recordEditor._contentCardViewCardId) {
                const auth =
                    typeof recordEditor.getContentCardApiAuthPayload === 'function'
                        ? recordEditor.getContentCardApiAuthPayload()
                        : null;
                if (auth) {
                    void fetch('/api/content_cards/interactive/record', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            ...auth,
                            content_card_id: Number(recordEditor._contentCardViewCardId),
                            correct,
                        }),
                    }).catch((err) => console.warn('interactive/record (pip-count):', err));
                }
            }

            if (!dryRun) {
                openInteractiveBestMoveFeedbackModal(correct ? ok : bad);
            }
        });
    }

    [upperInput, lowerInput].forEach((inp) => {
        if (!inp) return;
        inp.addEventListener('mousedown', (e) => e.stopPropagation());
        inp.addEventListener('click', (e) => e.stopPropagation());
    });
}

export function mountInteractivePipCountBlock(block, options = {}) {
    if (!block) return;
    bindInteractivePipCountBlock(block, options);
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

    const blocks = host.querySelectorAll('.canvas-element[data-tool-id="interactive-pip-count"]');
    blocks.forEach((block) => {
        block.dataset.cePipCountBound = '';
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
        block.dataset.cePipCountBound = '';
        mountInteractivePipCountBlock(block, {
            dryRun: true,
            payload,
            sharedContext,
        });
    });
}
