export function initContentCardViewOnlyImpl(editor) {
    editor._contentCardTopLabels = [];
    editor._contentCardViewFileName = '';
    editor._contentCardAdminMeta = null;
    editor._contentCardSharedContext = null;
    if (!document.getElementById('contentCardViewRoot')) {
        document.body.insertAdjacentHTML('beforeend', `
                <div id="contentCardViewRoot" class="card-preview-modal card-preview-modal--fullscreen" style="display: none; min-height: 100vh;" aria-hidden="true">
                    <div class="card-preview-box" style="width: 100%; max-width: 100%; box-sizing: border-box;">
                        <div class="content-card-view-top-spacer" aria-hidden="true"></div>
                        <div class="card-preview-header">
                                <button type="button" id="contentCardViewEditFrameBtn" class="content-card-view-edit-btn" style="display: none;" onclick="contentEditor.openEditorFromContentCardView()" title="Редактировать текущий кадр">
                                    <i class="fa fa-pencil" aria-hidden="true"></i><span class="content-card-view-edit-label"> Редактировать кадр</span>
                                </button>
                                <button type="button" id="contentCardViewAddFrameBtn" class="content-card-view-add-frame-btn" style="display: none;" onclick="contentEditor.openContentCardAddFrameModal()" title="Добавить кадр" aria-label="Добавить кадр">
                                    <i class="fa fa-plus" aria-hidden="true"></i><span class="content-card-view-add-frame-label"> Добавить кадр</span>
                                </button>
                                <button type="button" id="contentCardViewDeleteFrameBtn" class="content-card-view-delete-frame-btn" style="display: none;" onclick="contentEditor.deleteCurrentContentCardFrame()" title="Удалить текущий кадр" aria-label="Удалить кадр">
                                    <i class="fa fa-trash" aria-hidden="true"></i><span class="content-card-view-delete-frame-label"> Удалить кадр</span>
                                </button>
                                <button type="button" id="contentCardViewInfoBtn" class="content-card-view-info-btn" style="display: none;" onclick="contentEditor.openContentCardAdminInfoModal()" aria-label="Информация о карточке" title="Информация">
                                    <i class="fa fa-info-circle" aria-hidden="true"></i>
                                </button>
                        </div>
                        <div class="card-preview-nav">
                            <button type="button" class="card-preview-nav-btn" id="cardPreviewPrevBtn" onclick="contentEditor.cardPreviewPrev()">←</button>
                            <span class="card-preview-counter" id="cardPreviewCounter">0 / 0</span>
                            <button type="button" class="card-preview-nav-btn" id="cardPreviewNextBtn" onclick="contentEditor.cardPreviewNext()">→</button>
                        </div>
                        <div class="card-preview-meta" id="cardPreviewMeta"></div>
                        <div class="card-preview-frame-host" id="cardPreviewFrameHost"></div>
                    </div>
                </div>
                <div id="contentCardAdminInfoModal" class="content-card-admin-info-modal" style="display: none;" aria-hidden="true">
                    <div class="content-card-admin-info-overlay" onclick="contentEditor.closeContentCardAdminInfoModal()"></div>
                    <div class="content-card-admin-info-box" role="dialog" aria-modal="true" aria-labelledby="contentCardAdminInfoTitle">
                        <h3 id="contentCardAdminInfoTitle" class="content-card-admin-info-title">Информация о карточке</h3>
                        <div id="contentCardAdminInfoBody" class="content-card-admin-info-body"></div>
                        <div class="content-card-admin-info-actions">
                            <button type="button" class="content-card-admin-info-close-btn" onclick="contentEditor.closeContentCardAdminInfoModal()">Закрыть</button>
                        </div>
                    </div>
                </div>
            `);
    }
    const _ccb = document.querySelector('#contentCardViewRoot .card-preview-box');
    if (_ccb && !_ccb.querySelector('.content-card-view-top-spacer')) {
        _ccb.insertAdjacentHTML('afterbegin', '<div class="content-card-view-top-spacer" aria-hidden="true"></div>');
    }
    editor.cardPreviewModal = document.getElementById('contentCardViewRoot');
    editor.cardLabelsModal = null;
    editor.modal = null;
    editor.canvas = null;
    editor.toolsList = null;
    editor.propertiesContent = null;
    editor._ensureContentCardAddFrameUi();
}

export function ensureContentCardAddFrameUiImpl(editor) {
    if (!document.getElementById('contentCardAddFrameModal')) {
        document.body.insertAdjacentHTML(
            'beforeend',
            `
                <div id="contentCardAddFrameModal" class="content-card-admin-info-modal" style="display: none;" aria-hidden="true">
                    <div class="content-card-admin-info-overlay" onclick="contentEditor.closeContentCardAddFrameModal()"></div>
                    <div class="content-card-admin-info-box content-card-add-frame-box" role="dialog" aria-modal="true" aria-labelledby="contentCardAddFrameTitle">
                        <h3 id="contentCardAddFrameTitle" class="content-card-admin-info-title">Добавить кадр</h3>
                        <p class="content-card-add-frame-hint">Пустой кадр можно затем заполнить через «Редактировать кадр».</p>
                        <label class="content-card-add-frame-label" for="contentCardAddFramePositionSelect">Позиция в списке</label>
                        <select id="contentCardAddFramePositionSelect" class="content-card-add-frame-select" aria-describedby="contentCardAddFrameTitle"></select>
                        <div class="content-card-admin-info-actions content-card-add-frame-actions">
                            <button type="button" class="content-card-admin-info-close-btn" onclick="contentEditor.closeContentCardAddFrameModal()">Отмена</button>
                            <button type="button" id="contentCardAddFrameConfirmBtn" class="content-card-add-frame-confirm-btn" onclick="contentEditor.confirmContentCardAddFrame()">Добавить</button>
                        </div>
                    </div>
                </div>
                `
        );
    }
    const right = document.querySelector('#contentCardViewRoot .card-preview-header-right');
    if (right && !document.getElementById('contentCardViewAddFrameBtn')) {
        const del = document.getElementById('contentCardViewDeleteFrameBtn');
        if (del) {
            del.insertAdjacentHTML(
                'beforebegin',
                `<button type="button" id="contentCardViewAddFrameBtn" class="content-card-view-add-frame-btn" style="display: none;" onclick="contentEditor.openContentCardAddFrameModal()" title="Добавить кадр" aria-label="Добавить кадр">
                        <i class="fa fa-plus" aria-hidden="true"></i><span class="content-card-view-add-frame-label"> Добавить кадр</span>
                    </button>`
            );
        }
    }
}

export async function bootstrapContentCardViewPageImpl(editor) {
    const params = new URLSearchParams(window.location.search);
    const cardId = params.get('content_card_id');
    const fabToken = String(params.get('fab_token') || '');
    const metaHost = document.getElementById('cardPreviewMeta');
    const showErr = (msg) => {
        const t = editor.escapeHtml(msg);
        if (metaHost) {
            metaHost.innerHTML = `<span class="card-preview-meta-empty">${t}</span>`;
        }
        if (editor.cardPreviewModal) {
            editor.cardPreviewModal.style.display = 'flex';
            editor.cardPreviewModal.setAttribute('aria-hidden', 'false');
        }
    };
    if (!cardId) {
        showErr('Не указан content_card_id в адресе страницы');
        return;
    }
    const initData = (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || '';
    if (!initData && !fabToken) {
        showErr('Откройте страницу из Telegram');
        return;
    }
    try {
        const authPayload = initData ? { init_data: initData } : { fab_token: fabToken };
        const r = await fetch('/api/content_cards/fetch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ...authPayload,
                content_card_id: parseInt(cardId, 10),
            }),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) {
            let msg = data.detail;
            if (Array.isArray(msg)) {
                msg = msg.map((x) => (x.msg || JSON.stringify(x))).join('; ');
            } else if (msg && typeof msg === 'object') {
                msg = JSON.stringify(msg);
            }
            throw new Error(msg || `Ошибка ${r.status}`);
        }
        const titleEl = document.getElementById('contentCardViewTitle');
        if (titleEl) {
            titleEl.textContent = 'Карточка';
        }
        editor._contentCardViewFileName = '';
        editor._contentCardTopLabels = [];
        editor._contentCardViewCardId = parseInt(cardId, 10);
        editor._applyContentCardFetchPayload(data);
        editor.cardPreviewIndex = 0;
        if (editor.cardPreviewModal) {
            editor.cardPreviewModal.style.display = 'flex';
            editor.cardPreviewModal.setAttribute('aria-hidden', 'false');
        }
        document.body.style.overflow = 'hidden';
        window.addEventListener('resize', editor._onCardPreviewResize);
        editor.refreshCardPreviewUI();
    } catch (e) {
        console.error('bootstrapContentCardViewPage:', e);
        showErr(e.message || String(e));
    }
}

export function applyContentCardFetchPayloadImpl(editor, data) {
    const infoBtn = document.getElementById('contentCardViewInfoBtn');
    const editBtn = document.getElementById('contentCardViewEditFrameBtn');
    const addFrameBtn = document.getElementById('contentCardViewAddFrameBtn');
    const deleteFrameBtn = document.getElementById('contentCardViewDeleteFrameBtn');
    if (data.is_content_card_admin && infoBtn && editBtn) {
        editor._contentCardAdminMeta = {
            file_name: data.file_name != null ? String(data.file_name) : '',
            labels: Array.isArray(data.labels) ? data.labels : [],
            notes: data.notes != null ? String(data.notes) : '',
        };
        infoBtn.style.display = '';
        editBtn.style.display = 'inline-flex';
        if (addFrameBtn) addFrameBtn.style.display = 'inline-flex';
        if (deleteFrameBtn) deleteFrameBtn.style.display = 'inline-flex';
    } else {
        editor._contentCardAdminMeta = null;
        if (infoBtn) infoBtn.style.display = 'none';
        if (editBtn) editBtn.style.display = 'none';
        if (addFrameBtn) addFrameBtn.style.display = 'none';
        if (deleteFrameBtn) deleteFrameBtn.style.display = 'none';
    }
    const fw = data.frames || {};
    editor._assignContentCardSharedContextFromWrapper(fw);
    const framesArr = Array.isArray(fw.frames) ? fw.frames.slice() : [];
    framesArr.sort((a, b) => (a.order != null ? a.order : 0) - (b.order != null ? b.order : 0));
    editor.cardPreviewRefs = framesArr.map((f) => ({
        frameId: f.frameId,
        saveSlotIndex: f.saveSlotIndex != null ? f.saveSlotIndex : 0,
        payload: f.payload,
        storageKey: null,
    }));
}

export function assignContentCardSharedContextFromWrapperImpl(editor, fw) {
    editor._contentCardSharedContext = null;
    if (!fw || typeof fw !== 'object') return;
    const raw = fw.sharedContext;
    if (raw && typeof raw === 'object') {
        let board = null;
        let cardData = null;
        if (raw.board != null && typeof raw.board === 'object' && raw.board.error !== 'no_game_data') {
            try {
                board = JSON.parse(JSON.stringify(raw.board));
            } catch (e) {
                board = raw.board;
            }
        }
        if (raw.cardData != null && typeof raw.cardData === 'object') {
            try {
                cardData = JSON.parse(JSON.stringify(raw.cardData));
            } catch (e) {
                cardData = raw.cardData;
            }
        }
        if (board || cardData) {
            editor._contentCardSharedContext = { board, cardData };
        }
        return;
    }
    const framesArr = Array.isArray(fw.frames) ? fw.frames : [];
    editor._contentCardSharedContext = editor._deriveContentCardSharedContextFromFrames(framesArr);
}

export function deriveContentCardSharedContextFromFramesImpl(_editor, framesArr) {
    let board = null;
    let cardData = null;
    for (const f of framesArr) {
        const p = f && f.payload;
        if (!p || typeof p !== 'object') continue;
        if (
            board == null &&
            p.board != null &&
            typeof p.board === 'object' &&
            p.board.error !== 'no_game_data'
        ) {
            try {
                board = JSON.parse(JSON.stringify(p.board));
            } catch (e) {
                board = p.board;
            }
        }
        if (cardData == null && p.cardData && typeof p.cardData === 'object') {
            const h = p.cardData.hints;
            const ch = p.cardData.cube_hints;
            const hasHints = Array.isArray(h) && h.length > 0;
            const hasCube = Array.isArray(ch) && ch.length > 0;
            if (hasHints || hasCube) {
                try {
                    cardData = JSON.parse(JSON.stringify(p.cardData));
                } catch (e) {
                    cardData = p.cardData;
                }
            }
        }
        if (board && cardData) break;
    }
    if (!board && !cardData) return null;
    return { board, cardData };
}

export function mergeSharedUnderFrameCardDataImpl(_editor, sharedCd, frameCd) {
    if (!sharedCd || typeof sharedCd !== 'object') {
        if (!frameCd || typeof frameCd !== 'object') return null;
        try {
            return JSON.parse(JSON.stringify(frameCd));
        } catch (e) {
            return null;
        }
    }
    let o;
    try {
        o = JSON.parse(JSON.stringify(sharedCd));
    } catch (e) {
        return null;
    }
    if (!frameCd || typeof frameCd !== 'object') return Object.keys(o).length ? o : null;
    let f;
    try {
        f = JSON.parse(JSON.stringify(frameCd));
    } catch (e) {
        return Object.keys(o).length ? o : null;
    }
    for (const [k, v] of Object.entries(f)) {
        if (v !== undefined && v !== null) o[k] = v;
    }
    return Object.keys(o).length ? o : null;
}

export function getPayloadForCardPreviewRenderImpl(editor, payload) {
    if (!payload || typeof payload !== 'object') return payload;
    const sc = editor._contentCardSharedContext;
    if (!sc || typeof sc !== 'object' || (!sc.board && !sc.cardData)) {
        return payload;
    }
    let p;
    try {
        p = JSON.parse(JSON.stringify(payload));
    } catch (e) {
        return payload;
    }
    if (p.board == null && sc.board != null && typeof sc.board === 'object') {
        try {
            p.board = JSON.parse(JSON.stringify(sc.board));
        } catch (e) {
            p.board = sc.board;
        }
    }
    if (sc.cardData && typeof sc.cardData === 'object') {
        p.cardData = editor.mergeSharedUnderFrameCardData(sc.cardData, p.cardData);
    }
    return p;
}

export function applyContentCardSharedToEditorPayloadImpl(editor, payload) {
    const sc = editor._contentCardSharedContext;
    if (!sc || typeof sc !== 'object' || !payload || typeof payload !== 'object') return payload;
    if (payload.board == null && sc.board != null && typeof sc.board === 'object') {
        try {
            payload.board = JSON.parse(JSON.stringify(sc.board));
        } catch (e) {
            payload.board = sc.board;
        }
    }
    if (sc.cardData && typeof sc.cardData === 'object') {
        payload.cardData = editor.mergeSharedUnderFrameCardData(sc.cardData, payload.cardData);
    }
    return payload;
}

export function wrapContentCardFramesWithSharedImpl(editor, framesArray) {
    const w = { version: 1, frames: framesArray };
    const sc = editor._contentCardSharedContext;
    if (sc && typeof sc === 'object' && (sc.board || sc.cardData)) {
        w.sharedContext = {
            board: sc.board ? JSON.parse(JSON.stringify(sc.board)) : null,
            cardData: sc.cardData ? JSON.parse(JSON.stringify(sc.cardData)) : null,
        };
    }
    return w;
}
