export async function deleteCurrentContentCardFrameImpl(editor) {
    if (typeof window === 'undefined' || window.__CONTENT_CARD_VIEW_ONLY__ !== true) return;
    if (!editor._contentCardAdminMeta || editor._contentCardViewCardId == null) return;
    if (editor.cardPreviewRefs.length <= 1) return;
    if (!confirm('Удалить текущий кадр? Действие нельзя отменить.')) return;

    const initData = (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || '';
    if (!initData) {
        editor.showNotification('Нет init_data для сохранения', 'warning');
        return;
    }

    const idx = editor.cardPreviewIndex;
    const nextRefs = editor.cardPreviewRefs.filter((_, i) => i !== idx);
    const nextIndex = Math.min(idx, nextRefs.length - 1);
    const framesList = nextRefs.map((r, order) => ({
        frameId: r.frameId,
        saveSlotIndex: r.saveSlotIndex != null ? r.saveSlotIndex : 0,
        order,
        payload: r.payload ? JSON.parse(JSON.stringify(r.payload)) : null,
    }));
    const framesWrapper = editor.wrapContentCardFramesWithShared(framesList);

    const deleteBtn = document.getElementById('contentCardViewDeleteFrameBtn');
    if (deleteBtn) deleteBtn.disabled = true;

    try {
        const response = await fetch('/api/content_cards/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                init_data: initData,
                content_card_id: editor._contentCardViewCardId,
                frames: framesWrapper,
            }),
        });
        let respData = {};
        try {
            respData = await response.json();
        } catch (e) {
            respData = {};
        }
        if (!response.ok) {
            let msg = respData.detail;
            if (Array.isArray(msg)) {
                msg = msg.map((x) => (x.msg || JSON.stringify(x))).join('; ');
            } else if (msg && typeof msg === 'object') {
                msg = JSON.stringify(msg);
            }
            throw new Error(msg || `Ошибка ${response.status}`);
        }
        editor.cardPreviewRefs = nextRefs.map((r) => ({
            frameId: r.frameId,
            saveSlotIndex: r.saveSlotIndex != null ? r.saveSlotIndex : 0,
            payload: r.payload ? JSON.parse(JSON.stringify(r.payload)) : null,
            storageKey: null,
        }));
        editor.cardPreviewIndex = nextIndex;
        editor.refreshCardPreviewUI();
        editor.showNotification('Кадр удалён', 'success');
    } catch (err) {
        console.error('deleteCurrentContentCardFrame:', err);
        editor.showNotification('Не удалось удалить кадр: ' + (err.message || err), 'error');
    } finally {
        if (deleteBtn) deleteBtn.disabled = false;
        editor.refreshCardPreviewUI();
    }
}

export function buildEmptyContentCardFramePayloadImpl(editor) {
    const cid = editor._contentCardViewCardId != null ? editor._contentCardViewCardId : 0;
    const frameId = `cc_${cid}_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
    return {
        version: 1,
        frameId,
        saveSlotIndex: 0,
        savedAt: new Date().toISOString(),
        board: null,
        cardData: null,
        editor: {
            boardCanvasToggle: true,
            canvasBackground: '#ffffff',
            showBoardMatchBanner: false,
        },
        elements: [],
    };
}

export function openContentCardAddFrameModalImpl(editor) {
    if (typeof window === 'undefined' || window.__CONTENT_CARD_VIEW_ONLY__ !== true) return;
    if (!editor._contentCardAdminMeta || editor._contentCardViewCardId == null) return;
    const modal = document.getElementById('contentCardAddFrameModal');
    const sel = document.getElementById('contentCardAddFramePositionSelect');
    if (!modal || !sel) return;
    const n = editor.cardPreviewRefs.length;
    sel.innerHTML = '';
    for (let pos = 1; pos <= n + 1; pos++) {
        const opt = document.createElement('option');
        opt.value = String(pos);
        if (n === 0) {
            opt.textContent = 'Позиция 1';
        } else if (pos === n + 1) {
            opt.textContent = `В конец (${n + 1}-й кадр)`;
        } else {
            opt.textContent = `Позиция ${pos} (${pos}-й кадр)`;
        }
        sel.appendChild(opt);
    }
    const defaultPos = n === 0 ? 1 : Math.min(editor.cardPreviewIndex + 2, n + 1);
    sel.value = String(defaultPos);
    modal.style.display = 'flex';
    modal.setAttribute('aria-hidden', 'false');
    requestAnimationFrame(() => sel.focus());
}

export function closeContentCardAddFrameModalImpl(_editor) {
    const modal = document.getElementById('contentCardAddFrameModal');
    if (!modal) return;
    modal.style.display = 'none';
    modal.setAttribute('aria-hidden', 'true');
}

export async function confirmContentCardAddFrameImpl(editor) {
    if (typeof window === 'undefined' || window.__CONTENT_CARD_VIEW_ONLY__ !== true) return;
    if (!editor._contentCardAdminMeta || editor._contentCardViewCardId == null) return;

    const initData = (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || '';
    if (!initData) {
        editor.showNotification('Нет init_data для сохранения', 'warning');
        return;
    }

    const sel = document.getElementById('contentCardAddFramePositionSelect');
    const confirmBtn = document.getElementById('contentCardAddFrameConfirmBtn');
    if (!sel) return;

    const n = editor.cardPreviewRefs.length;
    const pos = parseInt(sel.value, 10);
    if (!Number.isFinite(pos) || pos < 1 || pos > n + 1) {
        editor.showNotification('Некорректная позиция', 'warning');
        return;
    }
    const insertIndex = pos - 1;

    const newPayload = editor.buildEmptyContentCardFramePayload();
    const newRef = {
        frameId: newPayload.frameId,
        saveSlotIndex: 0,
        payload: newPayload,
        storageKey: null,
    };

    const refs = editor.cardPreviewRefs.map((r) => ({
        frameId: r.frameId,
        saveSlotIndex: r.saveSlotIndex != null ? r.saveSlotIndex : 0,
        payload: r.payload ? JSON.parse(JSON.stringify(r.payload)) : null,
        storageKey: null,
    }));
    refs.splice(insertIndex, 0, newRef);

    const framesList = refs.map((r, order) => ({
        frameId: r.frameId,
        saveSlotIndex: r.saveSlotIndex != null ? r.saveSlotIndex : 0,
        order,
        payload: r.payload ? JSON.parse(JSON.stringify(r.payload)) : null,
    }));
    const framesWrapper = editor.wrapContentCardFramesWithShared(framesList);

    if (confirmBtn) confirmBtn.disabled = true;
    try {
        await editor.uploadPayloadMediaToS3(newPayload);
        const response = await fetch('/api/content_cards/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                init_data: initData,
                content_card_id: editor._contentCardViewCardId,
                frames: framesWrapper,
            }),
        });
        let respData = {};
        try {
            respData = await response.json();
        } catch (e) {
            respData = {};
        }
        if (!response.ok) {
            let msg = respData.detail;
            if (Array.isArray(msg)) {
                msg = msg.map((x) => (x.msg || JSON.stringify(x))).join('; ');
            } else if (msg && typeof msg === 'object') {
                msg = JSON.stringify(msg);
            }
            throw new Error(msg || `Ошибка ${response.status}`);
        }
        editor.cardPreviewRefs = refs.map((r) => ({
            frameId: r.frameId,
            saveSlotIndex: r.saveSlotIndex != null ? r.saveSlotIndex : 0,
            payload: r.payload ? JSON.parse(JSON.stringify(r.payload)) : null,
            storageKey: null,
        }));
        editor.cardPreviewIndex = insertIndex;
        editor.closeContentCardAddFrameModal();
        editor.refreshCardPreviewUI();
        editor.showNotification('Кадр добавлен', 'success');
    } catch (err) {
        console.error('confirmContentCardAddFrame:', err);
        editor.showNotification('Не удалось добавить кадр: ' + (err.message || err), 'error');
    } finally {
        if (confirmBtn) confirmBtn.disabled = false;
    }
}

export function openContentCardAdminInfoModalImpl(editor) {
    if (!editor._contentCardAdminMeta) return;
    const modal = document.getElementById('contentCardAdminInfoModal');
    const body = document.getElementById('contentCardAdminInfoBody');
    if (!modal || !body) return;
    const rawFn = String(editor._contentCardAdminMeta.file_name || '').trim();
    const fnEsc = editor.escapeHtml(rawFn || '—');
    const sharedBoard = editor._contentCardSharedContext && editor._contentCardSharedContext.board
        ? editor._contentCardSharedContext.board
        : null;
    const isPokazSource =
        sharedBoard &&
        typeof sharedBoard === 'object' &&
        String(sharedBoard.gameId || '').toLowerCase() === 'pokaz';
    const canDownloadMat =
        rawFn &&
        rawFn.toLowerCase().endsWith('.mat') &&
        !isPokazSource &&
        editor._contentCardViewCardId != null;
    const fileDd = canDownloadMat
        ? `<dd><button type="button" class="content-card-admin-info-file-link">${fnEsc}</button></dd>`
        : `<dd>${fnEsc}</dd>`;
    const labels = Array.isArray(editor._contentCardAdminMeta.labels) ? editor._contentCardAdminMeta.labels : [];
    const parts = labels
        .map((x) => (typeof x === 'string' ? x.trim() : String(x)))
        .filter(Boolean);
    let labelsBlock;
    if (parts.length) {
        labelsBlock =
            '<ul class="content-card-admin-info-labels">' +
            parts.map((t) => `<li>${editor.escapeHtml(t)}</li>`).join('') +
            '</ul>';
    } else {
        labelsBlock = '<p class="content-card-admin-info-empty">Нет меток</p>';
    }
    const rawNotes = String(editor._contentCardAdminMeta.notes || '').trim();
    const notesBlock = rawNotes
        ? `<p>${editor.escapeHtml(rawNotes)}</p>`
        : '<p class="content-card-admin-info-empty">Нет примечаний</p>';
    body.innerHTML =
        `<dl class="content-card-admin-info-dl">` +
        `<dt>Файл</dt>${fileDd}` +
        `<dt>Метки <button type="button" class="content-card-admin-info-edit-btn" id="contentCardEditLabelsBtn" style="margin-left:8px;"><i class="fa fa-pencil" aria-hidden="true"></i></button></dt>` +
        `<dd>${labelsBlock}</dd>` +
        `<dt>Примечания <button type="button" class="content-card-admin-info-edit-btn" id="contentCardEditNotesBtn" style="margin-left:8px;"><i class="fa fa-pencil" aria-hidden="true"></i></button></dt>` +
        `<dd>${notesBlock}</dd>` +
        `</dl>`;
    const fileBtn = body.querySelector('.content-card-admin-info-file-link');
    if (fileBtn) {
        fileBtn.addEventListener('click', (e) => {
            e.preventDefault();
            editor.downloadContentCardHintMat();
        });
    }
    const labelsBtn = body.querySelector('#contentCardEditLabelsBtn');
    if (labelsBtn) {
        labelsBtn.addEventListener('click', (e) => {
            e.preventDefault();
            editor.openContentCardAdminLabelsEditModal();
        });
    }
    const notesBtn = body.querySelector('#contentCardEditNotesBtn');
    if (notesBtn) {
        notesBtn.addEventListener('click', (e) => {
            e.preventDefault();
            editor.openContentCardAdminNotesEditModal();
        });
    }
    modal.style.display = 'flex';
    modal.setAttribute('aria-hidden', 'false');
}

export function closeContentCardAdminInfoModalImpl(_editor) {
    const modal = document.getElementById('contentCardAdminInfoModal');
    if (!modal) return;
    modal.style.display = 'none';
    modal.setAttribute('aria-hidden', 'true');
}

export function ensureViewOnlyEditorMountedImpl(editor) {
    if (window.__CONTENT_CARD_VIEW_ONLY__ !== true || editor._viewOnlyEditorMounted) {
        return;
    }
    editor.createModal();
    editor.setupEventListeners();
    editor.setupCanvasEvents();
    editor._viewOnlyEditorMounted = true;
}

export async function openEditorFromContentCardViewImpl(editor) {
    if (window.__CONTENT_CARD_VIEW_ONLY__ !== true || !editor._contentCardViewCardId) {
        return;
    }
    if (!editor._contentCardAdminMeta) {
        editor.showNotification('Редактирование доступно только администраторам', 'warning');
        return;
    }
    const ref = editor.cardPreviewRefs[editor.cardPreviewIndex];
    if (!ref || !ref.payload) {
        editor.showNotification('Нет данных кадра', 'warning');
        return;
    }
    editor.ensureViewOnlyEditorMounted();
    if (!editor.modal || !editor.canvas) {
        editor.showNotification('Не удалось открыть редактор', 'error');
        return;
    }
    let payload;
    try {
        payload = JSON.parse(JSON.stringify(ref.payload));
    } catch (e) {
        editor.showNotification('Не удалось загрузить кадр', 'error');
        return;
    }
    editor.applyContentCardSharedToEditorPayload(payload);
    editor._suspendContentCardViewOnlyForEditor();
    editor.closeCardPreviewModal();
    editor.editorOpenedFromContentCardView = true;
    editor.editorOpenedFromPreview = true;
    editor.previewEditStorageKey = '__content_card_view__';
    editor.previewEditFrameId = ref.frameId;
    editor.previewEditSaveSlotIndex = ref.saveSlotIndex != null ? ref.saveSlotIndex : 0;
    editor._contentCardEditFrameIndex = editor.cardPreviewIndex;
    editor.openModalWithData(payload.cardData || null, { fromPreviewRestore: true });
    await editor.restoreCanvasFromPayload(payload);
}
