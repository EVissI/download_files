/**
 * Инструмент «Шаблоны»: модалки сохранения/вставки шаблонов кадра (БД), только через ContentEditor.
 */

const ROOT_ID = 'frameTemplatesRootModal';
const NAME_ID = 'frameTemplatesNameModal';
const INSERT_ID = 'frameTemplatesInsertModal';
const DELETE_ID = 'frameTemplatesDeleteConfirmModal';

/** @type {{ root: HTMLElement | null, name: HTMLElement | null, insert: HTMLElement | null, del: HTMLElement | null }} */
let els = {
    root: null,
    name: null,
    insert: null,
    del: null,
};

function show(el) {
    if (!el) return;
    el.style.display = 'flex';
    el.setAttribute('aria-hidden', 'false');
}

function hide(el) {
    if (!el) return;
    el.style.display = 'none';
    el.setAttribute('aria-hidden', 'true');
}

function hideAll() {
    hide(els.root);
    hide(els.name);
    hide(els.insert);
    hide(els.del);
}

function ensureShell() {
    if (els.root && document.body.contains(els.root)) return;

    const mkOverlay = (cls) => {
        const o = document.createElement('div');
        o.className = cls;
        return o;
    };

    const root = document.createElement('div');
    root.id = ROOT_ID;
    root.className = 'frame-templates-modal';
    root.setAttribute('aria-hidden', 'true');
    root.innerHTML = `
        <div class="frame-templates-modal__overlay" data-ft-close="1"></div>
        <div class="frame-templates-modal__box" role="dialog" aria-modal="true">
            <div class="frame-templates-modal__actions">
                <button type="button" class="frame-templates-modal__btn frame-templates-modal__btn--primary" data-ft-save>Сохранить</button>
                <button type="button" class="frame-templates-modal__btn" data-ft-insert>Вставить</button>
            </div>
        </div>`;

    const nameModal = document.createElement('div');
    nameModal.id = NAME_ID;
    nameModal.className = 'frame-templates-modal frame-templates-modal--narrow';
    nameModal.setAttribute('aria-hidden', 'true');
    nameModal.innerHTML = `
        <div class="frame-templates-modal__overlay" data-ft-close="1"></div>
        <div class="frame-templates-modal__box" role="dialog" aria-modal="true">
            <input type="text" class="frame-templates-modal__input" maxlength="200" placeholder="" autocomplete="off" data-ft-name-input />
            <div class="frame-templates-modal__row">
                <button type="button" class="frame-templates-modal__btn" data-ft-name-cancel>Отмена</button>
                <button type="button" class="frame-templates-modal__btn frame-templates-modal__btn--primary" data-ft-name-ok>Ок</button>
            </div>
        </div>`;

    const insertModal = document.createElement('div');
    insertModal.id = INSERT_ID;
    insertModal.className = 'frame-templates-modal frame-templates-modal--wide';
    insertModal.setAttribute('aria-hidden', 'true');
    insertModal.innerHTML = `
        <div class="frame-templates-modal__overlay" data-ft-close="1"></div>
        <div class="frame-templates-modal__box frame-templates-modal__box--scroll" role="dialog" aria-modal="true">
            <button type="button" class="frame-templates-modal__close" data-ft-insert-close aria-label="Закрыть">&times;</button>
            <div class="frame-templates-insert-grid" data-ft-insert-grid></div>
            <p class="frame-templates-insert-empty" data-ft-insert-empty hidden>Нет шаблонов</p>
        </div>`;

    const delModal = document.createElement('div');
    delModal.id = DELETE_ID;
    delModal.className = 'frame-templates-modal frame-templates-modal--narrow';
    delModal.setAttribute('aria-hidden', 'true');
    delModal.innerHTML = `
        <div class="frame-templates-modal__overlay" data-ft-close="1"></div>
        <div class="frame-templates-modal__box" role="dialog" aria-modal="true">
            <p class="frame-templates-delete-msg" data-ft-delete-msg></p>
            <div class="frame-templates-modal__row">
                <button type="button" class="frame-templates-modal__btn" data-ft-delete-cancel>Отмена</button>
                <button type="button" class="frame-templates-modal__btn frame-templates-modal__btn--danger" data-ft-delete-ok>Удалить</button>
            </div>
        </div>`;

    document.body.appendChild(root);
    document.body.appendChild(nameModal);
    document.body.appendChild(insertModal);
    document.body.appendChild(delModal);

    els = { root, name: nameModal, insert: insertModal, del: delModal };
}

/** @type {{ editor: object | null, pendingDeleteId: number | null }} */
const state = {
    editor: null,
    pendingDeleteId: null,
};

/** Крупный payload не кладём в data-атрибуты — только id → объект. */
const insertPayloadById = new Map();

function bindOnce() {
    if (bindOnce.done) return;
    bindOnce.done = true;
    ensureShell();

    els.root.addEventListener('click', (ev) => {
        const t = ev.target;
        if (t && t.closest && t.closest('[data-ft-close]')) {
            hide(els.root);
            return;
        }
        if (t && t.closest && t.closest('[data-ft-save]')) {
            hide(els.root);
            show(els.name);
            const inp = els.name.querySelector('[data-ft-name-input]');
            if (inp) {
                inp.value = '';
                requestAnimationFrame(() => inp.focus());
            }
            return;
        }
        if (t && t.closest && t.closest('[data-ft-insert]')) {
            hide(els.root);
            void openInsertModal(state.editor);
        }
    });

    els.name.addEventListener('click', (ev) => {
        const t = ev.target;
        if (t && t.closest && t.closest('[data-ft-close]')) {
            hide(els.name);
            return;
        }
        if (t && t.closest && t.closest('[data-ft-name-cancel]')) {
            hide(els.name);
            return;
        }
        if (t && t.closest && t.closest('[data-ft-name-ok]')) {
            const inp = els.name.querySelector('[data-ft-name-input]');
            void confirmSaveTemplate(state.editor, inp);
        }
    });

    els.name.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter') {
            ev.preventDefault();
            const inp = els.name.querySelector('[data-ft-name-input]');
            void confirmSaveTemplate(state.editor, inp);
        }
    });

    els.insert.addEventListener('click', (ev) => {
        const t = ev.target;
        if (t && t.closest && t.closest('[data-ft-insert-close]')) {
            hide(els.insert);
            return;
        }
        if (t && t.closest && t.closest('[data-ft-close]')) {
            hide(els.insert);
            return;
        }
        const delBtn = t && t.closest && t.closest('[data-ft-card-delete]');
        if (delBtn) {
            ev.preventDefault();
            ev.stopPropagation();
            const card = delBtn.closest('[data-template-id]');
            const id = card ? parseInt(card.getAttribute('data-template-id') || '0', 10) : 0;
            const nm =
                (card && card.getAttribute('data-template-name')) ||
                '';
            if (id > 0) openDeleteConfirm(state.editor, id, nm);
            return;
        }
        const card = t && t.closest && t.closest('[data-template-id].frame-templates-insert-card');
        if (card && state.editor) {
            const tid = parseInt(card.getAttribute('data-template-id') || '0', 10);
            const payload = insertPayloadById.get(tid);
            if (!payload) {
                state.editor.showNotification('Шаблон не найден', 'error');
                return;
            }
            hide(els.insert);
            hideAll();
            const applyFn =
                typeof state.editor.applyFrameTemplatePayload === 'function'
                    ? state.editor.applyFrameTemplatePayload.bind(state.editor)
                    : state.editor.restoreCanvasFromPayload.bind(state.editor);
            applyFn(payload)
                .then(() => {
                    state.editor.showNotification('Шаблон вставлен', 'success');
                })
                .catch((err) => {
                    console.error('applyFrameTemplatePayload:', err);
                    state.editor.showNotification(
                        'Не удалось вставить шаблон: ' + (err && err.message ? err.message : err),
                        'error'
                    );
                });
        }
    });

    els.del.addEventListener('click', (ev) => {
        const t = ev.target;
        if (t && t.closest && t.closest('[data-ft-close]')) {
            hide(els.del);
            state.pendingDeleteId = null;
            return;
        }
        if (t && t.closest && t.closest('[data-ft-delete-cancel]')) {
            hide(els.del);
            state.pendingDeleteId = null;
            return;
        }
        if (t && t.closest && t.closest('[data-ft-delete-ok]')) {
            const id = state.pendingDeleteId;
            hide(els.del);
            state.pendingDeleteId = null;
            if (id != null) {
                void runDeleteTemplate(state.editor, id);
            }
        }
    });
}
bindOnce.done = false;

async function confirmSaveTemplate(editor, nameInput) {
    const name = (nameInput && nameInput.value ? String(nameInput.value) : '').trim();
    if (!name) {
        editor.showNotification('Введите название', 'warning');
        return;
    }
    hide(els.name);
    hide(els.root);

    const auth = editor.getContentCardApiAuthPayload();
    if (!auth) {
        editor.showNotification('Нужна авторизация (Telegram или fab_token)', 'warning');
        return;
    }

    try {
        const frameId = editor.getFrameIdForSave();
        const saveSlotIndex = editor.allocateNextSaveSlotIndex(frameId);
        let payload = await editor.buildFrameSavePayload(frameId, saveSlotIndex);
        if (typeof editor.sanitizePayloadForTemplate === 'function') {
            payload = editor.sanitizePayloadForTemplate(payload) || payload;
        }
        await editor.uploadPayloadMediaToS3(payload);

        const r = await fetch('/api/content_cards/frame_templates/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...auth, name, payload }),
        });
        let data = {};
        try {
            data = await r.json();
        } catch (_e) {
            data = {};
        }
        if (!r.ok) {
            let msg = data.detail;
            if (Array.isArray(msg)) {
                msg = msg.map((x) => x.msg || JSON.stringify(x)).join('; ');
            } else if (msg && typeof msg === 'object') {
                msg = JSON.stringify(msg);
            }
            throw new Error(msg || `Ошибка ${r.status}`);
        }
        /* В отличие от «Сохранить кадр», шаблон не должен очищать канвас редактора. */
        editor.showNotification('Шаблон сохранён', 'success');
    } catch (e) {
        console.error('frame_templates save:', e);
        editor.showNotification('Не удалось сохранить шаблон: ' + (e.message || e), 'error');
    }
}

async function openInsertModal(editor) {
    const auth = editor.getContentCardApiAuthPayload();
    if (!auth) {
        editor.showNotification('Нужна авторизация', 'warning');
        return;
    }

    insertPayloadById.clear();
    const grid = els.insert.querySelector('[data-ft-insert-grid]');
    const emptyEl = els.insert.querySelector('[data-ft-insert-empty]');
    if (grid) {
        grid.querySelectorAll('.frame-templates-insert-preview-host').forEach((h) => {
            if (h._frameTemplatePreviewRo) {
                try {
                    h._frameTemplatePreviewRo.disconnect();
                } catch (_e) {
                    /* noop */
                }
                h._frameTemplatePreviewRo = null;
            }
        });
        grid.innerHTML = '';
    }

    try {
        const r = await fetch('/api/content_cards/frame_templates/list', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(auth),
        });
        let data = {};
        try {
            data = await r.json();
        } catch (_e) {
            data = {};
        }
        if (!r.ok) {
            let msg = data.detail;
            if (Array.isArray(msg)) {
                msg = msg.map((x) => x.msg || JSON.stringify(x)).join('; ');
            } else if (msg && typeof msg === 'object') {
                msg = JSON.stringify(msg);
            }
            throw new Error(msg || `Ошибка ${r.status}`);
        }
        const list = (data && data.templates) || [];
        insertPayloadById.clear();
        if (emptyEl) {
            emptyEl.hidden = list.length > 0;
        }
        list.forEach((t) => {
            const id = t.id;
            const name = String(t.name || '');
            let payload = t.payload || {};
            if (typeof editor.sanitizePayloadForTemplate === 'function') {
                try {
                    payload = JSON.parse(JSON.stringify(payload));
                } catch (_e) {
                    /* использовать исходный payload */
                }
                editor.sanitizePayloadForTemplate(payload);
            }
            insertPayloadById.set(Number(id), payload);
            const card = document.createElement('div');
            card.className = 'frame-templates-insert-card';
            card.setAttribute('data-template-id', String(id));
            card.setAttribute('data-template-name', name);

            const del = document.createElement('button');
            del.type = 'button';
            del.className = 'frame-templates-insert-card-del';
            del.setAttribute('data-ft-card-delete', '1');
            del.setAttribute('aria-label', 'Удалить');
            del.innerHTML = '&times;';

            const prevHost = document.createElement('div');
            prevHost.className = 'frame-templates-insert-preview-host';

            const title = document.createElement('div');
            title.className = 'frame-templates-insert-card-title';
            title.textContent = name;

            card.appendChild(del);
            card.appendChild(prevHost);
            card.appendChild(title);
            grid.appendChild(card);

            try {
                editor.renderCardPreviewIntoHost(payload, prevHost);
            } catch (e) {
                console.warn('frame_templates preview:', e);
            }
        });
    } catch (e) {
        console.error('frame_templates list:', e);
        editor.showNotification(e.message || String(e), 'error');
        return;
    }

    show(els.insert);
}

function openDeleteConfirm(editor, id, name) {
    state.pendingDeleteId = id;
    const msg = els.del.querySelector('[data-ft-delete-msg]');
    if (msg) {
        const safe = editor.escapeHtml(name || String(id));
        msg.innerHTML = `Удалить шаблон «${safe}»?`;
    }
    show(els.del);
}

async function runDeleteTemplate(editor, templateId) {
    const auth = editor.getContentCardApiAuthPayload();
    if (!auth) {
        editor.showNotification('Нужна авторизация', 'warning');
        return;
    }
    try {
        const r = await fetch('/api/content_cards/frame_templates/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...auth, template_id: templateId }),
        });
        let data = {};
        try {
            data = await r.json();
        } catch (_e) {
            data = {};
        }
        if (!r.ok) {
            let msg = data.detail;
            if (Array.isArray(msg)) {
                msg = msg.map((x) => x.msg || JSON.stringify(x)).join('; ');
            } else if (msg && typeof msg === 'object') {
                msg = JSON.stringify(msg);
            }
            throw new Error(msg || `Ошибка ${r.status}`);
        }
        const card = els.insert.querySelector(`[data-template-id="${templateId}"]`);
        insertPayloadById.delete(Number(templateId));
        if (card && card.parentNode) {
            card.parentNode.removeChild(card);
        }
        const grid = els.insert.querySelector('[data-ft-insert-grid]');
        const emptyEl = els.insert.querySelector('[data-ft-insert-empty]');
        if (grid && emptyEl && !grid.querySelector('.frame-templates-insert-card')) {
            emptyEl.hidden = false;
        }
        editor.showNotification('Шаблон удалён', 'success');
    } catch (e) {
        console.error('frame_templates delete:', e);
        editor.showNotification(e.message || String(e), 'error');
    }
}

/** @param {object} editor — экземпляр ContentEditor */
export function openFrameTemplatesRootModal(editor) {
    bindOnce();
    state.editor = editor;
    hide(els.name);
    hide(els.insert);
    hide(els.del);
    show(els.root);
}
