export function openCardPreviewModalImpl(editor) {
    if (!editor.cardPreviewModal) return;
    editor.cardPreviewRefs = editor.collectSavedFrameRefsForCurrentGame();
    if (editor._resumePreviewStorageKey) {
        const i = editor.cardPreviewRefs.findIndex((r) => r.storageKey === editor._resumePreviewStorageKey);
        editor.cardPreviewIndex = i >= 0 ? i : 0;
        editor._resumePreviewStorageKey = null;
    } else {
        editor.cardPreviewIndex = 0;
    }
    editor.cardPreviewModal.classList.add('card-preview-modal--fullscreen');
    editor.cardPreviewModal.style.display = 'flex';
    editor.cardPreviewModal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    window.addEventListener('resize', editor._onCardPreviewResize);
    editor.refreshCardPreviewUI();
}

export function closeCardPreviewModalImpl(editor) {
    if (!editor.cardPreviewModal) return;
    window.removeEventListener('resize', editor._onCardPreviewResize);
    editor.cardPreviewModal.style.display = 'none';
    editor.cardPreviewModal.setAttribute('aria-hidden', 'true');
    const editorStillOpen = editor.modal && editor.modal.style.display === 'flex';
    document.body.style.overflow = editorStillOpen ? 'hidden' : 'auto';
    const host = document.getElementById('cardPreviewFrameHost');
    if (host) host.innerHTML = '';
}

export function refreshCardPreviewUIImpl(editor) {
    const total = editor.cardPreviewRefs.length;
    const counter = document.getElementById('cardPreviewCounter');
    const meta = document.getElementById('cardPreviewMeta');
    const prevBtn = document.getElementById('cardPreviewPrevBtn');
    const nextBtn = document.getElementById('cardPreviewNextBtn');
    const approveBtn = document.getElementById('cardPreviewApproveBtn');
    const deletePreviewBtn = document.getElementById('cardPreviewDeleteBtn');

    if (counter) {
        counter.textContent = total === 0 ? '0 / 0' : `${editor.cardPreviewIndex + 1} / ${total}`;
    }
    if (prevBtn) prevBtn.disabled = total === 0 || editor.cardPreviewIndex <= 0;
    if (nextBtn) nextBtn.disabled = total === 0 || editor.cardPreviewIndex >= total - 1;
    if (approveBtn) approveBtn.disabled = total === 0;
    if (deletePreviewBtn) deletePreviewBtn.disabled = total === 0;

    const deleteFrameBtn = document.getElementById('contentCardViewDeleteFrameBtn');
    if (deleteFrameBtn && typeof window !== 'undefined' && window.__CONTENT_CARD_VIEW_ONLY__ === true && editor._contentCardAdminMeta) {
        deleteFrameBtn.disabled = total <= 1;
    }

    if (!meta) return;

    if (total === 0) {
        meta.innerHTML = '<span class="card-preview-meta-empty">Нет сохранённых кадров для этой игры</span>';
        editor.renderCardPreviewSurface(null);
        return;
    }

    const ref = editor.cardPreviewRefs[editor.cardPreviewIndex];
    let payload = null;
    if (ref && ref.payload != null && typeof ref.payload === 'object') {
        payload = ref.payload;
    } else if (ref && ref.storageKey) {
        try {
            const raw = localStorage.getItem(ref.storageKey);
            payload = raw ? JSON.parse(raw) : null;
        } catch (e) {
            payload = null;
        }
    }

    meta.innerHTML = '';
    const viewOnlyPage = typeof window !== 'undefined' && window.__CONTENT_CARD_VIEW_ONLY__ === true;
    if (!viewOnlyPage) {
        const labelsKey = editor.getCardLabelsStorageKey();
        const hasStoredLabelsKey = localStorage.getItem(labelsKey) !== null;
        const storedLabels = hasStoredLabelsKey ? editor.loadCardLabelsFromStorage() : null;
        const fallbackLabels = editor._contentCardTopLabels && editor._contentCardTopLabels.length
            ? editor._contentCardTopLabels
            : [];
        const labelsToShow = hasStoredLabelsKey ? storedLabels : fallbackLabels;
        if (labelsToShow.length) {
            const topParts = labelsToShow
                .filter((t) => typeof t === 'string' && t.trim())
                .map((t) => `<span class="card-preview-label-chip">${editor.escapeHtml(t.trim())}</span>`)
                .join(' ');
            if (topParts) {
                meta.insertAdjacentHTML(
                    'beforeend',
                    `<div class="card-preview-meta-line card-preview-meta-labels">Метки карточки: ${topParts}</div>`
                );
            }
        }
    }
    const payloadForRender = mergeLiveCanvasBackgroundIntoPreviewPayload(
        editor,
        payload,
        ref,
        editor.cardPreviewRefs
    );
    editor.renderCardPreviewSurface(payloadForRender);
}

export function reorderCardPreviewElementsBySavedTopImpl(_editor, inner) {
    const elems = Array.from(inner.querySelectorAll('.canvas-element'));
    if (elems.length <= 1) return;
    const meta = elems.map((el, i) => {
        const t = parseInt(el.style.top, 10);
        return { el, top: Number.isNaN(t) ? 0 : t, i };
    });
    meta.sort((a, b) => (a.top !== b.top ? a.top - b.top : a.i - b.i));
    const frag = document.createDocumentFragment();
    meta.forEach(({ el }) => frag.appendChild(el));
    inner.appendChild(frag);
}

/**
 * В просмотре высота текстовых блоков должна зависеть от реального контента
 * и текущей ширины экрана, чтобы избежать наложений на узких экранах
 * и лишних пустых отступов на широких.
 */
function normalizePreviewTextBlockHeights(inner) {
    if (!inner) return;
    const blocks = inner.querySelectorAll(
        '.canvas-element.card-preview-canvas-clone.text-element, .canvas-element.card-preview-canvas-clone.link-element'
    );
    blocks.forEach((el) => {
        const content = el.querySelector('.text-content, .link-text');
        if (!content) return;

        // Не используем сохранённый fixed-height из редактора.
        // В потоке flex высота будет вычислена от текущего content/layout и ширины экрана.
        el.style.height = 'auto';
        el.style.minHeight = '0px';
        el.style.overflow = 'visible';
        content.style.height = 'auto';
        content.style.minHeight = '0px';
        content.style.overflow = 'visible';
    });
}

function normalizePreviewImageBlockHeights(editor, inner) {
    if (!inner) return;
    const blocks = inner.querySelectorAll('.canvas-element.card-preview-canvas-clone.image-element');
    blocks.forEach((el) => {
        const img = el.querySelector('img');
        if (!img) return;
        const apply = () => {
            if (editor && typeof editor.applyResponsiveUploadImageLayout === 'function') {
                const cap = typeof editor.getMaxCanvasWidth === 'function' ? editor.getMaxCanvasWidth() : 800;
                const innerWidth = Math.ceil(inner.getBoundingClientRect().width || inner.clientWidth || 0);
                const targetWidth = innerWidth > 0 ? Math.min(innerWidth, cap) : cap;
                // В просмотре у пользователя не даём image-блокам тянуться на всю ширину экрана.
                // Поведение синхронизировано с редактором (desktop/mobile cap).
                el.style.setProperty('width', `${targetWidth}px`, 'important');
                el.style.setProperty('max-width', `${cap}px`, 'important');
                el.style.alignSelf = 'center';
                el.style.marginLeft = 'auto';
                el.style.marginRight = 'auto';
                editor.applyResponsiveUploadImageLayout(el, { targetWidth, maxWidth: cap });
            }
        };
        apply();
        if (!img.complete) {
            img.addEventListener('load', apply, { once: true });
        }
    });
}

function previewBgPatternSummary(p) {
    if (!p || typeof p !== 'object') return null;
    const u = String(p.imageDataUrl || '');
    const key = String(p.imageS3Key || '').trim();
    return {
        hasDataUrl: u.length > 0,
        dataUrlChars: u.length,
        imageS3Key: key || null,
        interval: p.interval,
        imageWidth: p.imageWidth,
        imageHeight: p.imageHeight,
    };
}

function logPreviewBg(stage, detail) {
    if (typeof console === 'undefined' || typeof console.debug !== 'function') return;
    console.debug('[preview-bg]', stage, detail);
}

function isLatestSavedSlotForFrame(ref, allRefs) {
    const fid = ref && ref.frameId;
    if (!fid) return false;
    let maxSlot = -Infinity;
    for (let i = 0; i < allRefs.length; i++) {
        const r = allRefs[i];
        if (!r || r.frameId !== fid) continue;
        const s = r.saveSlotIndex != null ? r.saveSlotIndex : 0;
        if (s > maxSlot) maxSlot = s;
    }
    if (!Number.isFinite(maxSlot)) return false;
    const refSlot = ref.saveSlotIndex != null ? ref.saveSlotIndex : 0;
    return refSlot === maxSlot;
}

/**
 * Предпросмотр собирает payload из последнего сохранённого JSON (localStorage / сервер),
 * а фон узора живёт только в состоянии редактора до «Сохранить кадр». Подмешиваем актуальный фон,
 * если поверх открыт редактор и показывается тот же кадр, который сейчас редактируется.
 */
function mergeLiveCanvasBackgroundIntoPreviewPayload(editor, payload, ref, allRefs) {
    if (!payload || typeof payload !== 'object' || !editor.canvas) {
        logPreviewBg('mergeLiveCanvasBackground:skip', { reason: 'no payload/canvas' });
        return payload;
    }
    const previewModalOpen =
        editor.cardPreviewModal && editor.cardPreviewModal.style.display === 'flex';
    const editorModalOpen = editor.modal && editor.modal.style.display === 'flex';
    /* Раньше требовали только открытую модалку редактора; превью часто рендерится при уже
       скрытом #contentEditorModal — merge не выполнялся, а при выполнении «живой» null затирал узор из JSON. */
    if (!previewModalOpen && !editorModalOpen) {
        logPreviewBg('mergeLiveCanvasBackground:skip', {
            reason: 'no preview or editor shell',
            previewDisplay: editor.cardPreviewModal ? editor.cardPreviewModal.style.display : null,
            modalDisplay: editor.modal ? editor.modal.style.display : null,
        });
        return payload;
    }

    let merge = false;
    let mergeReason = '';
    if (editor.editorOpenedFromContentCardView && editor.previewEditFrameId != null) {
        merge =
            ref.frameId === editor.previewEditFrameId &&
            editor._contentCardEditFrameIndex != null &&
            editor._contentCardEditFrameIndex === editor.cardPreviewIndex;
        if (merge) mergeReason = 'contentCardView';
    }
    if (!merge && editor.editorOpenedFromPreview && !editor.editorOpenedFromContentCardView && editor.previewEditFrameId != null) {
        const slot = ref.saveSlotIndex != null ? ref.saveSlotIndex : 0;
        const editSlot =
            editor.previewEditSaveSlotIndex != null ? editor.previewEditSaveSlotIndex : 0;
        merge = ref.frameId === editor.previewEditFrameId && slot === editSlot;
        if (merge) mergeReason = 'openedFromPreview';
    }
    if (
        !merge &&
        typeof window !== 'undefined' &&
        window.__CONTENT_CARD_VIEW_ONLY__ !== true &&
        typeof editor.getFrameIdForSave === 'function'
    ) {
        const curId = editor.getFrameIdForSave();
        if (
            curId &&
            !String(curId).startsWith('editor_') &&
            ref.frameId === curId &&
            isLatestSavedSlotForFrame(ref, allRefs)
        ) {
            merge = true;
            mergeReason = 'frameIdMatchesLatestSlot';
        }
    }
    /* Пока открыт редактор и смотрим превью того же кадра, что на странице hint viewer,
       подмешиваем живой фон/узор даже если слоты/флаги edit-сессии выше не совпали. */
    if (
        !merge &&
        ref &&
        typeof window !== 'undefined' &&
        window.__CONTENT_CARD_VIEW_ONLY__ !== true &&
        typeof window.getHintViewerBoardSnapshot === 'function'
    ) {
        const snap = window.getHintViewerBoardSnapshot();
        const hintFid = snap && snap.frameId != null ? String(snap.frameId) : '';
        if (
            hintFid &&
            String(ref.frameId) === hintFid &&
            isLatestSavedSlotForFrame(ref, allRefs)
        ) {
            merge = true;
            mergeReason = 'hintViewerFrameMatch';
        }
    }

    if (!merge) {
        logPreviewBg('mergeLiveCanvasBackground:no-merge', {
            refFrameId: ref && ref.frameId,
            refSlot: ref && ref.saveSlotIndex,
            cardPreviewIndex: editor.cardPreviewIndex,
            editorOpenedFromContentCardView: editor.editorOpenedFromContentCardView,
            previewEditFrameId: editor.previewEditFrameId,
            getFrameIdForSave:
                typeof editor.getFrameIdForSave === 'function' ? editor.getFrameIdForSave() : undefined,
        });
        return payload;
    }

    let clone;
    try {
        clone = JSON.parse(JSON.stringify(payload));
    } catch (e) {
        logPreviewBg('mergeLiveCanvasBackground:clone-failed', { err: String(e && e.message) });
        return payload;
    }
    if (!clone.editor || typeof clone.editor !== 'object') clone.editor = {};
    /* После «Сохранить кадр» редактор сбрасывает узор в DOM, но payload уже содержит паттерн в JSON.
       Если подмешать «живое» состояние (null), превью затрёт только что сохранённый узор. */
    if (editor._previewMergePreferStoredCanvasBg) {
        logPreviewBg('mergeLiveCanvasBackground:merged-stored-only', {
            reason: mergeReason,
            canvasBackground: clone.editor.canvasBackground,
            canvasBackgroundPattern: previewBgPatternSummary(clone.editor.canvasBackgroundPattern),
        });
        return clone;
    }
    const editorModalFlex = editor.modal && editor.modal.style.display === 'flex';
    let livePatternForBg = null;
    if (typeof editor.getCanvasBackgroundPatternForSave === 'function') {
        livePatternForBg = editor.getCanvasBackgroundPatternForSave();
        if (livePatternForBg != null) {
            clone.editor.canvasBackgroundPattern = livePatternForBg;
        } else if (editorModalFlex) {
            clone.editor.canvasBackgroundPattern = null;
        }
    }
    if (typeof editor.getCanvasBackgroundForSave === 'function') {
        if (editorModalFlex || livePatternForBg != null) {
            clone.editor.canvasBackground = editor.getCanvasBackgroundForSave();
        }
    }
    logPreviewBg('mergeLiveCanvasBackground:merged', {
        reason: mergeReason,
        editorModalFlex,
        canvasBackground: clone.editor.canvasBackground,
        canvasBackgroundPattern: previewBgPatternSummary(clone.editor.canvasBackgroundPattern),
    });
    return clone;
}

function applyPreviewCanvasBackground(editor, payload, targets) {
    if (!targets || !targets.length) return;
    const bgColor = editor.resolveSavedCanvasBackground(payload);
    const pattern = typeof editor.resolveSavedCanvasBackgroundPattern === 'function'
        ? editor.resolveSavedCanvasBackgroundPattern(payload)
        : null;
    let patternCssUrl = '';
    let tileW = 0;
    let tileH = 0;
    if (pattern && pattern.imageDataUrl && typeof editor.buildCanvasTilePatternCssUrl === 'function') {
        patternCssUrl = editor.buildCanvasTilePatternCssUrl(pattern);
        const clamp = typeof editor.clampNumericValue === 'function'
            ? (v, min, max, d) => editor.clampNumericValue(v, min, max, d)
            : (v, min, max, d) => {
                const n = Number(v);
                if (!Number.isFinite(n)) return d;
                return Math.max(min, Math.min(max, n));
            };
        const interval = clamp(pattern.interval, 20, 200, 100);
        const imageWidth = clamp(pattern.imageWidth, 8, 4096, 64);
        const imageHeight = clamp(pattern.imageHeight, 8, 4096, 64);
        const scale = interval / 100;
        tileW = Math.max(1, Math.round(imageWidth * scale));
        tileH = Math.max(1, Math.round(imageHeight * scale));
    }
    logPreviewBg('applyPreviewCanvasBackground', {
        targetCount: targets.length,
        bgColor,
        patternFromPayload: previewBgPatternSummary(pattern),
        tilePx: patternCssUrl ? `${tileW}x${tileH}` : null,
        patternCssApplied: !!patternCssUrl,
    });
    targets.forEach((node) => {
        if (!node || !node.style) return;
        node.style.backgroundColor = bgColor;
        if (patternCssUrl) {
            node.style.backgroundImage = patternCssUrl;
            node.style.backgroundRepeat = 'repeat';
            node.style.backgroundSize = `${tileW}px ${tileH}px`;
            node.style.backgroundPosition = 'left top';
        } else {
            node.style.backgroundImage = 'none';
            node.style.backgroundRepeat = '';
            node.style.backgroundSize = '';
            node.style.backgroundPosition = '';
        }
    });
}

export function shouldShowBoardInCardPreviewImpl(_editor, payload) {
    if (!payload) return false;
    if (payload.editor && payload.editor.boardCanvasToggle) return true;
    if (payload.editor && payload.editor.boardCanvasToggle === false) return false;
    const b = payload.board;
    if (b == null || typeof b !== 'object') return false;
    if (b.error === 'no_game_data') return false;
    return true;
}

export function loadBoardPreviewImagesImpl(editor) {
    if (editor._boardPreviewAssetsPromise) return editor._boardPreviewAssetsPromise;
    const bust = () => `?t=${Date.now()}`;
    const loadOne = (src) => new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => reject(new Error(src));
        img.src = src + bust();
    });
    const paths = {
        board: '/static/board.png',
        black: '/static/black_checker.png',
        white: '/static/white_checker.png',
        double2: '/static/Double2.png',
        double4: '/static/Double4.png',
        double8: '/static/Double8.png',
        double16: '/static/Double16.png',
        double32: '/static/Double32.png',
        double64: '/static/Double64.png'
    };
    for (let i = 1; i <= 6; i++) {
        paths[`d${i}w`] = `/static/${i}w.png`;
        paths[`d${i}b`] = `/static/${i}b.png`;
    }
    editor._boardPreviewAssetsPromise = Promise.all(
        Object.entries(paths).map(([key, url]) => loadOne(url).then((img) => [key, img]))
    ).then((pairs) => Object.fromEntries(pairs));
    return editor._boardPreviewAssetsPromise;
}

export function getBoardPreviewPointXImpl(_editor, point) {
    if (point >= 13 && point <= 18) {
        const baseX = 50 + (point - 13) * 60;
        return baseX - (point === 13 ? 8 : 0);
    }
    if (point >= 19 && point <= 24) {
        return 450 + (point - 19) * 60;
    }
    if (point >= 7 && point <= 12) {
        const baseX = 50 + (12 - point) * 60;
        return baseX - (point === 12 ? 4 : 0);
    }
    if (point >= 1 && point <= 6) {
        return 450 + (6 - point) * 60;
    }
    return 0;
}

export function getBoardPreviewBaseYImpl(_editor, point) {
    return (point > 12) ? 70 : 690;
}

export function getBoardPreviewDyImpl(_editor, point) {
    return (point > 12) ? 55 : -55;
}

export function drawBoardPreviewCheckersImpl(editor, ctx, player, img, positions, currentPlayer, invertColors) {
    ctx.font = 'bold 30px Arial';
    ctx.fillStyle = '#ffffff';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    if (player === currentPlayer) {
        for (let point = 1; point <= 24; point++) {
            const x = editor.getBoardPreviewPointX(point);
            let y = editor.getBoardPreviewBaseY(point);
            const dy = editor.getBoardPreviewDy(point);
            let displayPoint = point;
            if (invertColors) {
                if (player === 'red') {
                    displayPoint = 25 - point;
                }
            } else if (player === 'black') {
                displayPoint = 25 - point;
            }
            let numberY;
            if (point > 12) {
                numberY = y - 50;
            } else {
                numberY = y + 60;
            }
            ctx.fillText(String(displayPoint), x, numberY);
        }
    }

    for (const pointStr in positions) {
        if (pointStr === 'bar' || pointStr === 'off') continue;
        const point = parseInt(pointStr, 10);
        const count = positions[pointStr];
        const x = editor.getBoardPreviewPointX(point);
        const y = editor.getBoardPreviewBaseY(point);
        const dy = editor.getBoardPreviewDy(point);
        for (let i = 0; i < Math.min(count, 6); i++) {
            ctx.drawImage(img, x - 31.25, y + (i * dy) - 31.25, 62.5, 62.5);
        }
        if (count > 6) {
            const lastCheckerY = y + (5 * dy);
            ctx.fillText(`${count}`, x + 40, lastCheckerY + 5);
        }
    }

    const barX = 400;
    let barY = (player === 'black') ? 220 : 520;
    if (invertColors) {
        barY = (player === 'black') ? 520 : 220;
    }
    if (positions.bar && positions.bar !== 0) {
        let y = barY;
        const dyBar = (player === 'black') ? 55 : -55;
        for (let i = 0; i < Math.min(Math.abs(positions.bar), 6); i++) {
            ctx.drawImage(img, barX - 31.25, y + (i * dyBar) - 31.25, 62.5, 62.5);
        }
        if (Math.abs(positions.bar) > 6) {
            const lastCheckerY = y + (5 * dyBar);
            ctx.fillText(`(${Math.abs(positions.bar)})`, barX + 30, lastCheckerY + 5);
        }
    }

    let offX = 783;
    let offY;
    if (invertColors) {
        offY = (player === 'black') ? 440 : 340;
    } else {
        offY = (player === 'black') ? 340 : 440;
    }
    if (positions.off && positions.off !== 0) {
        const originalFont = ctx.font;
        ctx.font = 'bold 32px Arial';
        ctx.fillText(`${positions.off}`, offX, offY);
        ctx.font = originalFont;
    }
}

export function drawDoublingCubePreviewImpl(_editor, ctx, cubeVisual, invertColors, imgs) {
    if (!cubeVisual || !cubeVisual.mode || !ctx) return;
    const v = Number(cubeVisual.value) || 64;
    const cubeKey = `double${v}`;
    let img = imgs[cubeKey];
    if (!img || !img.complete) img = imgs.double64;
    if (!img || !img.complete) return;
    const pl = cubeVisual.player ? String(cubeVisual.player).toLowerCase() : '';
    const isRed = pl === 'red';

    if (cubeVisual.mode === 'center') {
        ctx.drawImage(img, 375, 350, 50, 50);
        return;
    }
    if (cubeVisual.mode === 'side') {
        let cubeX;
        if (invertColors) {
            cubeX = isRed ? 175 : 575;
        } else {
            cubeX = isRed ? 575 : 175;
        }
        ctx.drawImage(img, cubeX, 350, 50, 50);
        return;
    }
    if (cubeVisual.mode === 'bar') {
        let cubeY = 350;
        if (invertColors) {
            if (isRed) cubeY = 600;
            else if (pl === 'black') cubeY = 100;
        } else if (pl === 'black') {
            cubeY = 600;
        } else if (isRed) {
            cubeY = 100;
        }
        ctx.drawImage(img, 375, cubeY, 50, 50);
    }
}

export function resolveBoardPositionsFromSnapshotImpl(_editor, snapshot) {
    if (!snapshot || typeof snapshot !== 'object') return null;
    if (snapshot.error === 'no_game_data') return null;
    const inv = !!snapshot.invertColors;
    const pos = snapshot.positions;
    if (pos && typeof pos === 'object' && pos.red && pos.black) {
        return { redPositions: pos.red, blackPositions: pos.black };
    }
    const fi = snapshot.frameIndex;
    if (fi === 0 || fi === null || fi === undefined) {
        if (inv) {
            return {
                redPositions: { '1': 2, '12': 5, '17': 3, '19': 5, 'bar': 0, 'off': 0 },
                blackPositions: { '6': 5, '8': 3, '13': 5, '24': 2, 'bar': 0, 'off': 0 }
            };
        }
        return {
            redPositions: { '24': 2, '6': 5, '8': 3, '13': 5, 'bar': 0, 'off': 0 },
            blackPositions: { '1': 2, '19': 5, '17': 3, '12': 5, 'bar': 0, 'off': 0 }
        };
    }
    return null;
}

export function paintBoardPreviewCanvasImpl(editor, canvas, snapshot, imgs) {
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    if (!imgs.board || !imgs.board.complete) return;
    ctx.drawImage(imgs.board, 0, 0, w, h);

    const invertColors = !!snapshot.invertColors;
    const resolved = editor.resolveBoardPositionsFromSnapshot(snapshot);
    const turnRow = snapshot.turn;
    const currentPlayer = (turnRow && turnRow.player) ? String(turnRow.player).toLowerCase() : 'red';

    if (resolved) {
        editor.drawBoardPreviewCheckers(ctx, 'red', imgs.white, resolved.redPositions, currentPlayer, invertColors);
        editor.drawBoardPreviewCheckers(ctx, 'black', imgs.black, resolved.blackPositions, currentPlayer, invertColors);
    }

    const diceImagesWhite = {
        1: imgs.d1w, 2: imgs.d2w, 3: imgs.d3w, 4: imgs.d4w, 5: imgs.d5w, 6: imgs.d6w
    };
    const diceImagesBlack = {
        1: imgs.d1b, 2: imgs.d2b, 3: imgs.d3b, 4: imgs.d4b, 5: imgs.d5b, 6: imgs.d6b
    };

    if (turnRow && turnRow.dice && turnRow.dice.length >= 2 && !['double', 'take', 'win'].includes(turnRow.action)) {
        const [d1, d2] = turnRow.dice;
        const diceY = 350;
        let diceX1;
        let diceX2;
        let diceSet;
        const isRedPlayer = String(turnRow.player || '').toLowerCase() === 'red';
        if (invertColors) {
            if (isRedPlayer) {
                diceX1 = 130;
                diceX2 = 220;
                diceSet = diceImagesWhite;
            } else {
                diceX1 = 530;
                diceX2 = 620;
                diceSet = diceImagesBlack;
            }
        } else if (isRedPlayer) {
            diceX1 = 530;
            diceX2 = 620;
            diceSet = diceImagesWhite;
        } else {
            diceX1 = 130;
            diceX2 = 220;
            diceSet = diceImagesBlack;
        }
        if (diceSet[d1]) ctx.drawImage(diceSet[d1], diceX1, diceY, 60, 60);
        if (diceSet[d2]) ctx.drawImage(diceSet[d2], diceX2, diceY, 60, 60);
    }

    if (snapshot.cubeVisual) {
        editor.drawDoublingCubePreview(ctx, snapshot.cubeVisual, invertColors, imgs);
    } else if (turnRow && turnRow.action === 'win' && imgs.double64) {
        ctx.drawImage(imgs.double64, 375, 350, 50, 50);
    }
}

export function formatBoardMatchBannerTextImpl(_editor, snapshot) {
    const s = snapshot && snapshot.scores;
    if (!s || typeof s !== 'object' || s.matchLength == null) {
        return '';
    }
    const ml = Number(s.matchLength);
    if (!Number.isFinite(ml) || ml <= 0) {
        return 'Манигейм';
    }
    const r = s.gameRedScore != null && s.gameRedScore !== '' ? s.gameRedScore : '—';
    const b = s.gameBlackScore != null && s.gameBlackScore !== '' ? s.gameBlackScore : '—';
    return `Матч до ${ml} · Счёт: ${r} — ${b}`;
}

export function setupCardPreviewTableCollapseImpl(editor, tableEl) {
    if (!tableEl || !tableEl.classList.contains('card-preview-canvas-clone')) return;
    if (tableEl.querySelector(':scope > .card-preview-table-toggle')) return;
    const kids = Array.from(tableEl.children);
    if (!kids.length) return;

    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'card-preview-table-toggle';
    toggle.setAttribute('aria-expanded', 'true');
    toggle.setAttribute('aria-label', 'Свернуть или развернуть таблицу');
    toggle.title = 'Свернуть или развернуть таблицу';
    toggle.innerHTML = `
            <span class="card-preview-table-toggle-icon" aria-hidden="true">
                <svg class="card-preview-table-caret-svg" viewBox="0 0 48 22" xmlns="http://www.w3.org/2000/svg" focusable="false">
                    <path fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round" d="M7 17 L24 5 L41 17"/>
                </svg>
            </span>`;

    const body = document.createElement('div');
    body.className = 'card-preview-table-collapse-body';
    kids.forEach((k) => body.appendChild(k));
    tableEl.appendChild(toggle);
    tableEl.appendChild(body);

    const syncA11y = () => {
        const collapsed = tableEl.classList.contains('card-preview-table--collapsed');
        toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    };
    const onToggle = (e) => {
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        tableEl.classList.toggle('card-preview-table--collapsed');
        syncA11y();
        requestAnimationFrame(() => editor.refreshCardPreviewScale());
    };
    toggle.addEventListener('click', onToggle);
    toggle.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            onToggle(e);
        }
    });
    syncA11y();
}

export function appendCardPreviewBoardOverlayImpl(editor, wrap, payload) {
    const snapshot = payload.board && typeof payload.board === 'object' ? payload.board : {};
    const showMatchBanner = !!(payload && payload.editor && payload.editor.showBoardMatchBanner);
    let bannerText = showMatchBanner ? editor.formatBoardMatchBannerText(snapshot) : '';
    if (showMatchBanner && !bannerText) {
        bannerText = 'Данные матча недоступны';
    }
    const overlay = document.createElement('div');
    overlay.className = 'card-preview-board-overlay';
    overlay.innerHTML = `
            <div class="card-preview-board-body">
                <div class="card-preview-board-collapsible">
                    <div class="card-preview-board-match-banner" ${showMatchBanner ? '' : 'hidden'}>${editor.escapeHtml(bannerText)}</div>
                    <div class="card-preview-board-canvas-wrap">
                        <canvas class="card-preview-board-canvas" width="800" height="800" aria-hidden="true"></canvas>
                    </div>
                </div>
                <div class="card-preview-board-toggle-row">
                    <button type="button" class="card-preview-board-toggle" aria-expanded="true" aria-label="Свернуть или развернуть доску" title="Свернуть или развернуть доску">
                        <span class="card-preview-board-toggle-icon" aria-hidden="true">
                            <svg class="card-preview-board-caret-svg" viewBox="0 0 48 22" xmlns="http://www.w3.org/2000/svg" focusable="false">
                                <path fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round" d="M7 17 L24 5 L41 17"/>
                            </svg>
                        </span>
                    </button>
                </div>
            </div>
        `;

    wrap.appendChild(overlay);
    setupCardPreviewBoardCollapseImpl(editor, overlay);

    const canvas = overlay.querySelector('.card-preview-board-canvas');
    editor.loadBoardPreviewImages()
        .then((imgs) => {
            if (!canvas.isConnected) return;
            editor.paintBoardPreviewCanvas(canvas, snapshot, imgs);
            requestAnimationFrame(() => editor.refreshCardPreviewScale());
        })
        .catch((err) => {
            console.error('appendCardPreviewBoardOverlay:', err);
        });
}

export function setupCardPreviewBoardCollapseImpl(editor, overlay) {
    if (!overlay) return;
    const toggle = overlay.querySelector('.card-preview-board-toggle');
    const body = overlay.querySelector('.card-preview-board-body');
    if (!toggle || !body) return;
    const collapsedInitial = !!editor._cardPreviewBoardCollapsed;
    overlay.classList.toggle('card-preview-board-overlay--collapsed', collapsedInitial);
    toggle.setAttribute('aria-expanded', collapsedInitial ? 'false' : 'true');
    const onToggle = (e) => {
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        const collapsedNow = !overlay.classList.contains('card-preview-board-overlay--collapsed');
        overlay.classList.toggle('card-preview-board-overlay--collapsed', collapsedNow);
        editor._cardPreviewBoardCollapsed = collapsedNow;
        toggle.setAttribute('aria-expanded', collapsedNow ? 'false' : 'true');
        requestAnimationFrame(() => editor.refreshCardPreviewScale());
    };
    toggle.addEventListener('click', onToggle);
    toggle.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            onToggle(e);
        }
    });
}

export function renderCardPreviewSurfaceImpl(editor, payload) {
    const host = document.getElementById('cardPreviewFrameHost');
    if (!host) return;
    host.innerHTML = '';
    host.style.backgroundColor = '';
    host.style.backgroundImage = 'none';
    host.style.backgroundRepeat = '';
    host.style.backgroundSize = '';
    host.style.backgroundPosition = '';
    if (!payload) {
        return;
    }

    const effectivePayload = editor.getPayloadForCardPreviewRender(payload);
    const list = Array.isArray(effectivePayload.elements) ? effectivePayload.elements : [];

    const wrap = document.createElement('div');
    wrap.className = 'card-preview-surface-wrap';
    const inner = document.createElement('div');
    inner.className = 'card-preview-surface-inner card-preview-surface-inner--flex-stack';
    inner.style.width = '100%';
    inner.style.position = 'relative';
    inner.style.boxSizing = 'border-box';
    applyPreviewCanvasBackground(editor, effectivePayload, [host, wrap, inner]);

    let maxNum = 0;
    list.forEach(item => {
        const m = /^element_(\d+)$/.exec(item.id || '');
        if (m) maxNum = Math.max(maxNum, parseInt(m[1], 10) + 1);
    });
    const savedCounter = editor.elementIdCounter;
    editor.elementIdCounter = maxNum;
    list.forEach(item => {
        const el = editor.deserializeCanvasElement(item, { previewMode: true });
        if (el) {
            el.style.width = '100%';
            el.style.left = '0px';
            el.style.boxSizing = 'border-box';
            inner.appendChild(el);
        }
    });
    editor.elementIdCounter = savedCounter;

    editor.reorderCardPreviewElementsBySavedTop(inner);
    const rawTops = Array.from(inner.querySelectorAll('.canvas-element')).map((el) => {
        const t = parseInt(el.style.top, 10);
        return Number.isNaN(t) ? 0 : t;
    });
    const minTop = rawTops.length ? Math.min(...rawTops) : 0;
    inner.style.paddingTop = minTop > 0 ? `${minTop}px` : '';
    inner.querySelectorAll('.canvas-element').forEach((el) => {
        el.style.top = '';
        el.style.left = '';
    });
    editor.refreshPreviewTableElementsFromCardData(inner, effectivePayload);
    inner
        .querySelectorAll('.canvas-element.table-element.card-preview-canvas-clone')
        .forEach((el) => editor.setupCardPreviewTableCollapse(el));
    normalizePreviewTextBlockHeights(inner);
    normalizePreviewImageBlockHeights(editor, inner);

    if (editor.shouldShowBoardInCardPreview(effectivePayload)) {
        editor.appendCardPreviewBoardOverlay(wrap, effectivePayload);
    }
    wrap.appendChild(inner);
    host.appendChild(wrap);

    inner.querySelectorAll('img').forEach((img) => {
        img.addEventListener('load', () => editor.refreshCardPreviewScale());
    });

    requestAnimationFrame(() => {
        editor.refreshCardPreviewScale();
    });
    setTimeout(() => {
        editor.refreshCardPreviewScale();
    }, 120);
}

export function updateCardPreviewInnerMinHeightImpl(_editor, inner) {
    if (!inner) return;
    if (inner.classList.contains('card-preview-surface-inner--flex-stack')) {
        inner.style.minHeight = '';
        return;
    }
    const nodes = inner.querySelectorAll('.canvas-element');
    if (!nodes.length) {
        inner.style.minHeight = '';
        return;
    }
    let maxBottom = 0;
    nodes.forEach((el) => {
        const top = parseInt(el.style.top, 10);
        const t = Number.isNaN(top) ? 0 : top;
        const bottom = t + (el.offsetHeight || 0);
        maxBottom = Math.max(maxBottom, bottom);
    });
    const pad = 8;
    inner.style.minHeight = maxBottom > 0 ? `${Math.ceil(maxBottom + pad)}px` : '';
}

export function refreshCardPreviewScaleImpl(editor) {
    const host = document.getElementById('cardPreviewFrameHost');
    if (!host) return;
    const inner = host.querySelector('.card-preview-surface-inner');
    const wrap = host.querySelector('.card-preview-surface-wrap');
    if (!inner || !wrap) return;

    inner.style.transform = 'none';
    if (inner.classList.contains('card-preview-surface-inner--flex-stack')) {
        inner.querySelectorAll('.canvas-element').forEach((el) => {
            el.style.marginBottom = '';
        });
        normalizePreviewTextBlockHeights(inner);
        normalizePreviewImageBlockHeights(editor, inner);
    }
    editor.updateCardPreviewInnerMinHeight(inner);
    const boardEl = wrap.querySelector('.card-preview-board-overlay');
    const boardH = boardEl ? Math.ceil(boardEl.offsetHeight) : 0;
    const innerH = Math.ceil(inner.offsetHeight);
    wrap.style.minHeight = `${boardH + innerH}px`;
}

export function cardPreviewPrevImpl(editor) {
    if (editor.cardPreviewIndex > 0) {
        editor.cardPreviewIndex--;
        editor.refreshCardPreviewUI();
    }
}

export function cardPreviewNextImpl(editor) {
    if (editor.cardPreviewIndex < editor.cardPreviewRefs.length - 1) {
        editor.cardPreviewIndex++;
        editor.refreshCardPreviewUI();
    }
}

export function deleteCurrentPreviewFrameImpl(editor) {
    if (typeof window !== 'undefined' && window.__CONTENT_CARD_VIEW_ONLY__ === true) return;
    const total = editor.cardPreviewRefs.length;
    if (total <= 0) {
        editor.showNotification('Нет кадров для удаления', 'warning');
        return;
    }
    const ref = editor.cardPreviewRefs[editor.cardPreviewIndex];
    if (!ref) return;

    if (!confirm('Удалить текущий кадр из предпросмотра?')) return;

    if (ref.storageKey) {
        try {
            localStorage.removeItem(ref.storageKey);
        } catch (e) {
            console.warn('deleteCurrentPreviewFrame removeItem:', e);
        }
    }
    editor.cardPreviewRefs.splice(editor.cardPreviewIndex, 1);
    if (editor.cardPreviewIndex >= editor.cardPreviewRefs.length) {
        editor.cardPreviewIndex = Math.max(editor.cardPreviewRefs.length - 1, 0);
    }
    editor.showNotification('Кадр удалён', 'success');
    editor.refreshCardPreviewUI();
}

export function cardPreviewApproveImpl(editor) {
    if (!editor.cardPreviewRefs.length) {
        editor.showNotification('Нет сохранённых кадров для этой игры', 'warning');
        return;
    }
    let labels = editor.loadCardLabelsFromStorage();
    if (!labels.length && editor._contentCardTopLabels && editor._contentCardTopLabels.length) {
        labels = editor._contentCardTopLabels.filter((x) => typeof x === 'string' && x.trim()).map((x) => x.trim());
    }
    if (!labels.length) {
        const withKeys = editor.cardPreviewRefs.filter((r) => r.storageKey);
        if (withKeys.length) {
            labels = editor.collectUnifiedLabelsFromFrameRefs(withKeys);
            if (labels.length) {
                try {
                    editor.saveCardLabelsToStorage(labels);
                } catch (e) {
                    console.warn('cardPreviewApprove migrate labels:', e);
                }
            }
        }
    }
    editor.cardLabelsDraft = labels.slice();
    editor.openCardLabelsModal();
}
