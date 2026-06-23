/**
 * Модалка «Правильно» / «Неправильно» для интерактивов карточки.
 */

let _feedbackModalBound = false;

/** На странице карточки монтируем внутрь #contentCardViewRoot — иначе в Telegram WebView fixed на body может не попасть в видимую область. */
function getInteractiveFeedbackMountEl() {
    if (typeof document === 'undefined') return null;
    if (typeof window !== 'undefined' && window.__CONTENT_CARD_VIEW_ONLY__ === true) {
        const root = document.getElementById('contentCardViewRoot');
        if (root) return root;
    }
    return document.body;
}

export function closeInteractiveBestMoveFeedbackModal() {
    const root = document.getElementById('ceInteractiveBestMoveFeedbackModal');
    if (!root) return;
    root.style.display = 'none';
    root.setAttribute('aria-hidden', 'true');
    if (typeof window !== 'undefined' && window.__CONTENT_CARD_VIEW_ONLY__ === true) {
        document.body.style.overflow = 'hidden';
    } else {
        document.body.style.overflow = '';
    }
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
    const mount = getInteractiveFeedbackMountEl() || document.body;
    mount.appendChild(root);

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
 * @param {string} message
 */
export function openInteractiveBestMoveFeedbackModal(message) {
    if (typeof document === 'undefined') return;
    const root = ensureInteractiveBestMoveFeedbackModal();
    const textEl = document.getElementById('ceInteractiveBestMoveFeedbackText');
    const btn = document.getElementById('ceInteractiveBestMoveFeedbackOkBtn');
    if (textEl) textEl.textContent = message != null ? String(message) : '';
    const mount = getInteractiveFeedbackMountEl() || document.body;
    mount.appendChild(root);
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
