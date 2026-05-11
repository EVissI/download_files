import {
    applyContentCardFetchPayloadImpl,
    applyContentCardSharedToEditorPayloadImpl,
    assignContentCardSharedContextFromWrapperImpl,
    bootstrapContentCardViewPageImpl,
    deriveContentCardSharedContextFromFramesImpl,
    ensureContentCardAddFrameUiImpl,
    getPayloadForCardPreviewRenderImpl,
    initContentCardViewOnlyImpl,
    mergeSharedUnderFrameCardDataImpl,
    wrapContentCardFramesWithSharedImpl,
} from '/static/js/content-editor/features/content_card_view_bootstrap.js';
import {
    buildEmptyContentCardFramePayloadImpl,
    closeContentCardAddFrameModalImpl,
    closeContentCardAdminInfoModalImpl,
    confirmContentCardAddFrameImpl,
    deleteCurrentContentCardFrameImpl,
    ensureViewOnlyEditorMountedImpl,
    openContentCardAddFrameModalImpl,
    openContentCardAdminInfoModalImpl,
    openEditorFromContentCardViewImpl,
} from '/static/js/content-editor/features/content_card_view_admin.js';
import {
    autoGrowTextElementContainerImpl,
    beginTextBlockHeightDragImpl,
    setupTextEditingImpl,
} from '/static/js/content-editor/features/text_resize.js';

/* Фича-модули со статическим import не наследуют ?t= от content_editor.js — кешируются отдельно.
   Пробрасываем тот же query, что у динамического import content_editor.js из bootstrap/core. */
const _featureModuleCacheQs = (() => {
    try {
        return new URL(import.meta.url).search || '';
    } catch (_e) {
        return '';
    }
})();
const {
    appendCardPreviewBoardOverlayImpl,
    cardPreviewApproveImpl,
    cardPreviewNextImpl,
    cardPreviewPrevImpl,
    closeCardPreviewModalImpl,
    deleteCurrentPreviewFrameImpl,
    drawBoardPreviewCheckersImpl,
    drawDoublingCubePreviewImpl,
    formatBoardMatchBannerTextImpl,
    getBoardPreviewBaseYImpl,
    getBoardPreviewDyImpl,
    getBoardPreviewPointXImpl,
    loadBoardPreviewImagesImpl,
    openCardPreviewModalImpl,
    paintBoardPreviewCanvasImpl,
    refreshCardPreviewScaleImpl,
    refreshCardPreviewUIImpl,
    renderCardPreviewSurfaceImpl,
    reorderCardPreviewElementsBySavedTopImpl,
    resolveBoardPositionsFromSnapshotImpl,
    setupCardPreviewTableCollapseImpl,
    shouldShowBoardInCardPreviewImpl,
    updateCardPreviewInnerMinHeightImpl,
} = await import(
    new URL('./content-editor/features/content_preview.js', import.meta.url).href + _featureModuleCacheQs
);
const {
    addPresetColorImpl,
    applyCanvasBackgroundImpl,
    applyCanvasPatternConfigImpl,
    applyCanvasSettingsActiveTabImpl,
    buildCanvasTilePatternCssUrlImpl,
    closeCanvasSettingsModalImpl,
    deletePresetColorImpl,
    getCanvasBackgroundForSaveImpl,
    getCanvasBackgroundPatternForSaveImpl,
    handleCanvasPatternFileInputImpl,
    openCanvasPatternImagePickerImpl,
    openCanvasSettingsModalImpl,
    refreshCanvasPatternPreviewInModalImpl,
    renderPresetColorsImpl,
    resolveSavedCanvasBackgroundImpl,
    resolveSavedCanvasBackgroundPatternImpl,
    setupPresetColorHandlersImpl,
    switchCanvasSettingsTabImpl,
} = await import(
    new URL('./content-editor/features/canvas_background.js', import.meta.url).href + _featureModuleCacheQs
);

/**
 * Content Editor Module
 * Редактор контента в стиле Photoshop
 */

export class ContentEditor {
    constructor() {
        this.modal = null;
        this.canvas = null;
        this.toolsList = null;
        this.propertiesContent = null;
        this.propertiesToolsDock = null;
        this.toolsListOriginalParent = null;
        this.propertiesContentOriginalParent = null;
        this.selectedElement = null;
        this.elements = [];
        this.elementIdCounter = 0;
        this.toggleStates = {}; // Для отслеживания состояния toggle-кнопок
        /** Показывать строку «матч / манигейм» над доской в предпросмотре (сохраняется в payload.editor.showBoardMatchBanner). */
        this.boardMatchBannerEnabled = false;
        this.cardData = null; // Сохраняем данные карточки для таблиц
        this.presetColors = [ // Сохраняем предустановленные цвета
            '#ffffff', '#f8f9fa', '#e9ecef', '#dee2e6',
            '#ced4da', '#f8f8f8', '#333333', '#1a1a1a'
        ];
        // Сохранённое выделение в contenteditable для Word-like форматирования
        this.savedSelection = null;
        this.savedSelectionEditable = null;

        /** Предпросмотр сохранённой карточки: список ссылок на кадры и текущий индекс */
        this.cardPreviewRefs = [];
        this.cardPreviewIndex = 0;
        this._cardPreviewBoardCollapsed = false;
        this._editorBoardCollapsed = false;
        this._onCardPreviewResize = () => this.refreshCardPreviewScale();

        /** Редактор открыт из предпросмотра карточки — одна кнопка «Сохранить», перезапись того же кадра */
        this.editorOpenedFromPreview = false;
        this.previewEditStorageKey = null;
        this.previewEditFrameId = null;
        this.previewEditSaveSlotIndex = null;
        /** После сохранения из предпросмотра-редактора — открыть предпросмотр на этом кадре */
        this._resumePreviewStorageKey = null;

        /** Редактор открыт со страницы /content-card-view (root-админ): сохранение кадра на сервер */
        this.editorOpenedFromContentCardView = false;
        this._contentCardEditFrameIndex = null;
        this._contentCardViewCardId = null;
        this._viewOnlyEditorMounted = false;

        /** Кэш загрузки PNG для оверлея доски в предпросмотре */
        this._boardPreviewAssetsPromise = null;

        /** Снимок доски из открытого payload (content-card-view / предпросмотр), если нет hint_viewer */
        this._editorSessionBoardSnapshot = null;

        /** Сохранённый style у #boardCanvas до «плавающего» показа поверх модалки редактора */
        this._liveBoardCanvasStyleBackup = null;
        /** Хост отображения доски внутри редактора (только визуализация). */
        this.editorBoardDisplayHost = null;

        /** Модалка меток карточки (целиком, не на отдельный кадр) */
        this.cardLabelsModal = null;
        this.cardLabelsDraft = [];
        /** Пресеты меток с сервера (root-админ): { id, value }[] */
        this._labelPresetsList = [];
        this.labelPresetsModal = null;
        this._labelPresetsTarget = 'card';
        this._adminLabelsDraft = [];
        this._duplicateSourceConfirmAction = null;
        /** Пресеты стилей текста (общие для админов). */
        this._textStylePresetsList = [];
        this._textStylePresetsLoaded = false;
        this.textStylePresetSaveModal = null;
        this.textStylePresetManageModal = null;

        /** Кэш открытой IndexedDB для больших аудио (вне квоты localStorage JSON) */
        this._contentEditorMediaDbPromise = null;

        /** Запись голосового (MediaRecorder) */
        this._voiceRecordStream = null;
        this._voiceRecordRecorder = null;
        this._voiceRecordChunks = [];
        this._voiceRecordTimerId = null;
        this._voiceRecordStartedAt = 0;
        this._voiceRecordDiscardOnStop = false;
        this._audioModalKeepOpenAfterDiscard = false;

        /** Глобальный стиль текста: новые блоки + значения вкладки «Текст» в настройках */
        this.globalTextStyleDefaults = { ...ContentEditor.DEFAULT_GLOBAL_TEXT_STYLE };
        /** Фон канваса-картинка: пока режим узора (tile). */
        this.canvasBackgroundPattern = null;
        /** Черновик паттерна внутри модалки настроек канваса. */
        this._canvasPatternDraft = null;

        this.init();
    }

    static get DEFAULT_GLOBAL_TEXT_STYLE() {
        return {
            fontSize: '16px',
            color: '#333333',
            textAlign: 'left',
            lineHeight: '20px',
            fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            fontWeight: 'normal',
            fontStyle: 'normal',
            textDecoration: 'none'
        };
    }

    /** Лимит размера вложения (как CC_MEDIA_MAX_BYTES на сервере). */
    static get ATTACH_FILE_MAX_BYTES() {
        return 30 * 1024 * 1024;
    }

    /** Применить сохранённые глобальные стили к узлу .text-content / .link-text */
    applyGlobalTextStyleDefaultsToTextNode(node) {
        if (!node || !this.globalTextStyleDefaults) return;
        const s = this.globalTextStyleDefaults;
        node.style.fontSize = s.fontSize;
        node.style.color = s.color;
        node.style.textAlign = s.textAlign;
        node.style.lineHeight = s.lineHeight;
        node.style.fontFamily = s.fontFamily;
        node.style.fontWeight = s.fontWeight;
        node.style.fontStyle = s.fontStyle;
        node.style.textDecoration = s.textDecoration;
    }

    /** Обновить объект дефолтов из полей модалки и раздать по всем текстовым узлам на канвасе */
    syncGlobalTextStyleDefaultsFromFormAndApplyAll() {
        const sizeEl = document.getElementById('globalTextFontSize');
        const colorEl = document.getElementById('globalTextColor');
        const alignEl = document.getElementById('globalTextAlign');
        const lhEl = document.getElementById('globalTextLineHeight');
        const famEl = document.getElementById('globalTextFontFamily');
        const boldEl = document.getElementById('globalTextBold');
        const italicEl = document.getElementById('globalTextItalic');
        const underEl = document.getElementById('globalTextUnderline');
        if (!sizeEl || !colorEl || !alignEl || !lhEl || !famEl) return false;
        this.globalTextStyleDefaults = {
            fontSize: `${sizeEl.value}px`,
            color: colorEl.value,
            textAlign: alignEl.value,
            lineHeight: `${lhEl.value}px`,
            fontFamily: famEl.value,
            fontWeight: boldEl && boldEl.checked ? 'bold' : 'normal',
            fontStyle: italicEl && italicEl.checked ? 'italic' : 'normal',
            textDecoration: underEl && underEl.checked ? 'underline' : 'none'
        };
        if (this.canvas) {
            this.canvas.querySelectorAll('.text-content, .link-text').forEach((n) => {
                this.applyGlobalTextStyleDefaultsToTextNode(n);
                const parent = n.closest('.canvas-element');
                if (parent) this.autoGrowTextElementContainer(parent);
            });
        }
        return true;
    }

    // Check if mobile device and get max canvas width
    isMobile() {
        return window.innerWidth <= 768;
    }
    getMaxCanvasWidth() {
        if (this.isMobile()) {
            // For mobile, return standard mobile card width
            return 360;
        }
        return 800; // Desktop default
    }

    getMaxCanvasHeight() {
        if (this.isMobile()) {
            // Для мобильных устройств учитываем высоту вьюпорта и панели
            // Оставляем место под заголовок и оба тулбара
            const viewportHeight = window.innerHeight || 600;
            const reserved = 260; // header + toolbars + отступы
            const dynamicMax = viewportHeight - reserved;
            // Не даём канвасу быть слишком маленьким
            return Math.max(400, dynamicMax);
        }
        return 600; // Desktop default
    }

    init() {
        if (typeof window !== 'undefined' && window.__CONTENT_CARD_VIEW_ONLY__ === true) {
            this.initContentCardViewOnly();
            return;
        }
        this.createModal();
        this.loadTools();
        this.setupEventListeners();
        this.setupCanvasEvents();
    }

    /** Только просмотр сохранённой карточки (страница /content-card-view), без редактора. */
    initContentCardViewOnly() {
        return initContentCardViewOnlyImpl(this);
    }

    /** Кнопка «Добавить кадр» и модалка (для старых встраиваний DOM без них). */
    _ensureContentCardAddFrameUi() {
        return ensureContentCardAddFrameUiImpl(this);
    }

    async bootstrapContentCardViewPage() {
        return bootstrapContentCardViewPageImpl(this);
    }

    /** Обновляет метаданные админа и cardPreviewRefs из ответа /api/content_cards/fetch. */
    _applyContentCardFetchPayload(data) {
        return applyContentCardFetchPayloadImpl(this, data);
    }

    /**
     * Общий контекст карточки: явный `sharedContext` в JSON или первый кадр с board / cardData (hints).
     * Не показывается в предпросмотре пустого кадра — подмешивается только при открытии редактора.
     */
    _assignContentCardSharedContextFromWrapper(fw) {
        return assignContentCardSharedContextFromWrapperImpl(this, fw);
    }

    _deriveContentCardSharedContextFromFrames(framesArr) {
        return deriveContentCardSharedContextFromFramesImpl(this, framesArr);
    }

    /** Слой кадра поверх общего контекста: непустые поля кадра перекрывают shared. */
    mergeSharedUnderFrameCardData(sharedCd, frameCd) {
        return mergeSharedUnderFrameCardDataImpl(this, sharedCd, frameCd);
    }

    /**
     * Payload кадра для предпросмотра / просмотра сохранённой карточки: board и cardData из sharedContext,
     * если в самом кадре их нет (как в JSON после сохранения с общим контекстом).
     */
    getPayloadForCardPreviewRender(payload) {
        return getPayloadForCardPreviewRenderImpl(this, payload);
    }

    /** Подставить shared board/cardData в клон payload перед restore (пустой новый кадр). */
    applyContentCardSharedToEditorPayload(payload) {
        return applyContentCardSharedToEditorPayloadImpl(this, payload);
    }

    /** Обёртка кадров для POST /api/content_cards/update — сохраняет sharedContext карточки. */
    wrapContentCardFramesWithShared(framesArray) {
        return wrapContentCardFramesWithSharedImpl(this, framesArray);
    }

    /** Удаление текущего кадра (только ROOT-админ, только если кадров больше одного). */
    async deleteCurrentContentCardFrame() {
        return deleteCurrentContentCardFrameImpl(this);
    }

    /** Пустой payload кадра для новой записи в карточке (content-card-view). */
    buildEmptyContentCardFramePayload() {
        return buildEmptyContentCardFramePayloadImpl(this);
    }

    openContentCardAddFrameModal() {
        return openContentCardAddFrameModalImpl(this);
    }

    closeContentCardAddFrameModal() {
        return closeContentCardAddFrameModalImpl(this);
    }

    async confirmContentCardAddFrame() {
        return confirmContentCardAddFrameImpl(this);
    }

    openContentCardAdminInfoModal() {
        return openContentCardAdminInfoModalImpl(this);
    }

    ensureContentCardAdminLabelsEditModal() {
        let modal = document.getElementById('contentCardAdminLabelsEditModal');
        if (modal) return modal;
        document.body.insertAdjacentHTML(
            'beforeend',
            `
            <div id="contentCardAdminLabelsEditModal" class="card-labels-modal" style="display: none; z-index: 100003;" aria-hidden="true">
                <div class="card-labels-overlay" id="contentCardAdminLabelsOverlay"></div>
                <div class="card-labels-box" role="dialog" aria-modal="true" aria-labelledby="contentCardAdminLabelsTitle">
                    <div class="card-labels-modal-header-row">
                        <h3 id="contentCardAdminLabelsTitle" class="card-labels-title">Метки карточки</h3>
                        <button type="button" id="contentCardAdminLabelsOpenPresetsBtn" class="card-labels-presets-open-btn" style="display: none;" onclick="contentEditor.openLabelPresetsModal()" title="Пресеты меток">Пресеты</button>
                    </div>
                    <div class="card-labels-input-row">
                        <input type="text" id="contentCardAdminLabelsInput" class="card-labels-input" maxlength="500" placeholder="Введите метку и нажмите Enter или «Добавить»" autocomplete="off" />
                        <button type="button" class="card-labels-add-btn" id="contentCardAdminLabelsAddBtn">Добавить</button>
                    </div>
                    <div id="contentCardAdminLabelsList" class="card-labels-list" aria-live="polite"></div>
                    <div class="card-labels-actions">
                        <button type="button" class="card-labels-back-btn" id="contentCardAdminLabelsCancelBtn">Отмена</button>
                        <button type="button" class="card-labels-save-btn" id="contentCardAdminLabelsSaveBtn">Сохранить</button>
                    </div>
                </div>
            </div>
            `
        );
        modal = document.getElementById('contentCardAdminLabelsEditModal');
        const input = document.getElementById('contentCardAdminLabelsInput');
        const addBtn = document.getElementById('contentCardAdminLabelsAddBtn');
        const saveBtn = document.getElementById('contentCardAdminLabelsSaveBtn');
        const cancelBtn = document.getElementById('contentCardAdminLabelsCancelBtn');
        const overlay = document.getElementById('contentCardAdminLabelsOverlay');
        if (input) {
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.addContentCardAdminLabelFromInput();
                }
            });
        }
        if (addBtn) addBtn.addEventListener('click', () => this.addContentCardAdminLabelFromInput());
        if (saveBtn) saveBtn.addEventListener('click', () => this.saveContentCardAdminLabels());
        if (cancelBtn) cancelBtn.addEventListener('click', () => this.closeContentCardAdminLabelsEditModal());
        if (overlay) overlay.addEventListener('click', () => this.closeContentCardAdminLabelsEditModal());
        return modal;
    }

    openContentCardAdminLabelsEditModal() {
        if (!this._contentCardAdminMeta) return;
        const modal = this.ensureContentCardAdminLabelsEditModal();
        this._labelPresetsTarget = 'admin';
        this._adminLabelsDraft = Array.isArray(this._contentCardAdminMeta.labels)
            ? this._contentCardAdminMeta.labels
                .map((x) => (typeof x === 'string' ? x.trim() : String(x)))
                .filter(Boolean)
            : [];
        this.renderContentCardAdminLabelsList();
        const input = document.getElementById('contentCardAdminLabelsInput');
        if (input) input.value = '';
        modal.style.display = 'flex';
        modal.setAttribute('aria-hidden', 'false');
        void this.refreshLabelPresetsAccessButton('contentCardAdminLabelsOpenPresetsBtn');
        requestAnimationFrame(() => {
            if (input) input.focus();
        });
    }

    closeContentCardAdminLabelsEditModal() {
        const modal = document.getElementById('contentCardAdminLabelsEditModal');
        if (!modal) return;
        modal.style.display = 'none';
        modal.setAttribute('aria-hidden', 'true');
    }

    addContentCardAdminLabelFromInput() {
        const input = document.getElementById('contentCardAdminLabelsInput');
        if (!input) return;
        const text = String(input.value || '').trim();
        if (!text) return;
        this._adminLabelsDraft.push(text);
        input.value = '';
        this.renderContentCardAdminLabelsList();
        input.focus();
    }

    removeContentCardAdminLabelAt(index) {
        if (index < 0 || index >= this._adminLabelsDraft.length) return;
        this._adminLabelsDraft.splice(index, 1);
        this.renderContentCardAdminLabelsList();
    }

    renderContentCardAdminLabelsList() {
        const list = document.getElementById('contentCardAdminLabelsList');
        if (!list) return;
        if (!this._adminLabelsDraft.length) {
            list.innerHTML = '<span class="card-labels-empty">Пока нет меток</span>';
            return;
        }
        list.innerHTML = this._adminLabelsDraft
            .map(
                (label, i) =>
                    `<span class="card-labels-chip">${this.escapeHtml(label)}` +
                    `<button type="button" class="ce-card-label-remove-btn" onclick="contentEditor.removeContentCardAdminLabelAt(${i})" aria-label="Удалить метку">&times;</button></span>`
            )
            .join('');
    }

    ensureContentCardAdminNotesEditModal() {
        let modal = document.getElementById('contentCardAdminNotesEditModal');
        if (modal) return modal;
        document.body.insertAdjacentHTML(
            'beforeend',
            `
            <div id="contentCardAdminNotesEditModal" class="card-labels-modal" style="display: none; z-index: 100003;" aria-hidden="true">
                <div class="card-labels-overlay" id="contentCardAdminNotesOverlay"></div>
                <div class="card-labels-box" role="dialog" aria-modal="true" aria-labelledby="contentCardAdminNotesTitle">
                    <h3 id="contentCardAdminNotesTitle" class="card-labels-title">Примечания карточки</h3>
                    <textarea id="contentCardAdminNotesTextarea" class="card-labels-input" rows="5" maxlength="4000" placeholder="Введите примечания"></textarea>
                    <div class="card-labels-actions">
                        <button type="button" class="card-labels-back-btn" id="contentCardAdminNotesCancelBtn">Отмена</button>
                        <button type="button" class="card-labels-save-btn" id="contentCardAdminNotesSaveBtn">Сохранить</button>
                    </div>
                </div>
            </div>
            `
        );
        modal = document.getElementById('contentCardAdminNotesEditModal');
        const saveBtn = document.getElementById('contentCardAdminNotesSaveBtn');
        const cancelBtn = document.getElementById('contentCardAdminNotesCancelBtn');
        const overlay = document.getElementById('contentCardAdminNotesOverlay');
        if (saveBtn) saveBtn.addEventListener('click', () => this.saveContentCardAdminNotes());
        if (cancelBtn) cancelBtn.addEventListener('click', () => this.closeContentCardAdminNotesEditModal());
        if (overlay) overlay.addEventListener('click', () => this.closeContentCardAdminNotesEditModal());
        return modal;
    }

    openContentCardAdminNotesEditModal() {
        if (!this._contentCardAdminMeta) return;
        const modal = this.ensureContentCardAdminNotesEditModal();
        const textarea = document.getElementById('contentCardAdminNotesTextarea');
        if (textarea) textarea.value = String(this._contentCardAdminMeta.notes || '');
        modal.style.display = 'flex';
        modal.setAttribute('aria-hidden', 'false');
        requestAnimationFrame(() => {
            if (textarea) textarea.focus();
        });
    }

    closeContentCardAdminNotesEditModal() {
        const modal = document.getElementById('contentCardAdminNotesEditModal');
        if (!modal) return;
        modal.style.display = 'none';
        modal.setAttribute('aria-hidden', 'true');
    }

    async _saveContentCardAdminMeta(labels, notes) {
        const initData = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData;
        const params = new URLSearchParams(window.location.search || '');
        const fabToken = String(params.get('fab_token') || '');
        if (!initData && !fabToken) {
            this.showNotification('Сохранение доступно в Telegram WebApp', 'warning');
            return false;
        }
        if (this._contentCardViewCardId == null) {
            this.showNotification('Не удалось определить карточку', 'error');
            return false;
        }
        try {
            const res = await fetch('/api/content_cards/update_meta', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ...(initData ? { init_data: initData } : { fab_token: fabToken }),
                    content_card_id: Number(this._contentCardViewCardId),
                    labels: labels,
                    notes: notes,
                }),
            });
            if (!res.ok) {
                let detail = 'Ошибка сохранения метаданных карточки';
                try {
                    const j = await res.json();
                    if (j && j.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
                } catch (_e) {}
                throw new Error(detail);
            }
            return true;
        } catch (e) {
            this.showNotification(e.message || String(e), 'error');
            return false;
        }
    }

    async saveContentCardAdminLabels() {
        if (!this._contentCardAdminMeta) return;
        const normalized = this._adminLabelsDraft.map((s) => String(s).trim()).filter(Boolean);
        const ok = await this._saveContentCardAdminMeta(normalized, this._contentCardAdminMeta.notes || '');
        if (!ok) return;
        this._contentCardAdminMeta.labels = normalized;
        this.closeContentCardAdminLabelsEditModal();
        this.openContentCardAdminInfoModal();
        this.showNotification('Метки обновлены', 'success');
    }

    async saveContentCardAdminNotes() {
        if (!this._contentCardAdminMeta) return;
        const textarea = document.getElementById('contentCardAdminNotesTextarea');
        const notes = textarea ? String(textarea.value || '').trim() : '';
        const ok = await this._saveContentCardAdminMeta(this._contentCardAdminMeta.labels || [], notes);
        if (!ok) return;
        this._contentCardAdminMeta.notes = notes;
        this.closeContentCardAdminNotesEditModal();
        this.openContentCardAdminInfoModal();
        this.showNotification('Примечания обновлены', 'success');
    }

    /**
     * Скачивание исходного .mat из S3 (hints/{game_id}.mat) по имени файла карточки; только WebApp + админ.
     */
    async downloadContentCardHintMat() {
        const initData = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData;
        const params = new URLSearchParams(window.location.search || '');
        const fabToken = String(params.get('fab_token') || '');
        if (!initData && !fabToken) {
            this.showNotification('Скачивание доступно в Telegram WebApp', 'warning');
            return;
        }
        const cid = this._contentCardViewCardId;
        if (cid == null || Number.isNaN(Number(cid))) {
            this.showNotification('Не удалось определить карточку', 'error');
            return;
        }
        try {
            const res = await fetch('/api/content_cards/hint_mat_download_link', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ...(initData ? { init_data: initData } : { fab_token: fabToken }),
                    content_card_id: Number(cid),
                }),
            });
            if (!res.ok) {
                let detail = 'Ошибка скачивания';
                try {
                    const j = await res.json();
                    if (j.detail) {
                        detail =
                            typeof j.detail === 'string'
                                ? j.detail
                                : Array.isArray(j.detail)
                                  ? j.detail.map((x) => x.msg || JSON.stringify(x)).join('; ')
                                  : JSON.stringify(j.detail);
                    }
                } catch (e) {
                    /* ignore */
                }
                throw new Error(detail);
            }
            const data = await res.json().catch(() => ({}));
            const downloadPath = data && data.url ? String(data.url) : '';
            const fn = data && data.file_name
                ? String(data.file_name)
                : (
                    (this._contentCardAdminMeta &&
                        String(this._contentCardAdminMeta.file_name || '')
                            .replace(/[\\/]/g, '_')
                            .trim()) ||
                    'source.mat'
                );
            if (!downloadPath) {
                throw new Error('Сервер не вернул ссылку для скачивания');
            }
            this.requestDownloadByPath(downloadPath, fn);
        } catch (e) {
            console.error('downloadContentCardHintMat:', e);
            this.showNotification(e.message || String(e), 'error');
        }
    }

    closeContentCardAdminInfoModal() {
        return closeContentCardAdminInfoModalImpl(this);
    }

    ensureViewOnlyEditorMounted() {
        return ensureViewOnlyEditorMountedImpl(this);
    }

    async openEditorFromContentCardView() {
        return openEditorFromContentCardViewImpl(this);
    }

    createModal() {
        // Проверяем, существует ли уже модальное окно
        this.modal = document.getElementById('contentEditorModal');
        if (!this.modal) {
            // Если нет, создаем его
            const modalHTML = `
                <div id="contentEditorModal" class="content-editor-modal" style="display: none;">
                    <div class="content-editor-overlay" onclick="contentEditor.closeModal()"></div>
                    <div class="content-editor-container">
                        <div class="content-editor-header">
                            <h2>Редактор контента</h2>
                            <button class="close-btn" onclick="contentEditor.closeModal()">&times;</button>
                        </div>
                        <div class="content-editor-body">
                            <div class="toolbar toolbar-tools">
                                <div class="tools-list" id="toolsList">
                                    <!-- Динамический список инструментов -->
                                </div>
                                <div class="toolbar-board-extra" id="toolbarBoardMatchBannerRow" hidden>
                                    <label class="toolbar-board-match-label">
                                        <input type="checkbox" id="boardMatchBannerCheckbox" />
                                        <span>Инфо о матче над доской</span>
                                    </label>
                                </div>
                            </div>
                            <div class="editor-resizer editor-resizer-vertical" data-resize-target="toolbar"></div>
                            <div class="workspace">
                                <div class="canvas" id="canvas">
                                    <!-- Здесь будут размещаться элементы -->
                                </div>
                            </div>
                            <div class="editor-resizer editor-resizer-vertical" data-resize-target="properties"></div>
                            <div class="properties-panel toolbar-properties">
                                <div id="propertiesToolsDock" class="properties-tools-dock" hidden>
                                    <h3 class="properties-tools-title">Инструменты</h3>
                                </div>
                                <div id="propertiesContent">
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            document.body.insertAdjacentHTML('beforeend', modalHTML);
            this.modal = document.getElementById('contentEditorModal');
        }

        if (!document.getElementById('saveFrameConfirmModal')) {
            document.body.insertAdjacentHTML('beforeend', `
                <div id="saveFrameConfirmModal" class="save-frame-confirm-modal" style="display: none;" aria-hidden="true">
                    <div class="save-frame-confirm-overlay" onclick="contentEditor.cancelSaveFrame()"></div>
                    <div class="save-frame-confirm-box" role="dialog" aria-modal="true">
                        <h3 class="save-frame-confirm-title">Сохранить кадр</h3>
                        <div class="save-frame-confirm-actions">
                            <button type="button" class="save-frame-cancel-btn" onclick="contentEditor.cancelSaveFrame()">Отмена</button>
                            <button type="button" class="save-frame-ok-btn" onclick="contentEditor.confirmSaveFrame()">Сохранить</button>
                        </div>
                    </div>
                </div>
            `);
        }
        this.saveFrameConfirmModal = document.getElementById('saveFrameConfirmModal');

        if (!document.getElementById('audioSourceModal')) {
            document.body.insertAdjacentHTML(
                'beforeend',
                `
                <div id="audioSourceModal" class="ce-audio-source-modal" style="display: none;" aria-hidden="true">
                    <div class="ce-audio-source-overlay" onclick="contentEditor.closeAudioSourceModal()"></div>
                    <div class="ce-audio-source-box" role="dialog" aria-modal="true" aria-labelledby="audioSourceModalTitle">
                        <h3 id="audioSourceModalTitle" class="ce-audio-source-title">Аудио</h3>
                        <div id="audioSourceStepPick" class="ce-audio-source-step ce-audio-source-step--pick">
                            <button type="button" class="ce-audio-source-btn ce-audio-source-btn--primary" onclick="contentEditor.audioModalPickFile()">
                                Прикрепить аудио
                            </button>
                            <button type="button" class="ce-audio-source-btn ce-audio-source-btn--primary" onclick="contentEditor.audioModalStartRecord()">
                                Записать аудио
                            </button>
                            <button type="button" class="ce-audio-source-btn ce-audio-source-btn--ghost" onclick="contentEditor.closeAudioSourceModal()">
                                Отмена
                            </button>
                        </div>
                        <div id="audioSourceStepRecord" class="ce-audio-source-step ce-audio-source-step--record" style="display: none;">
                            <div class="ce-audio-record-row">
                                <span class="ce-audio-record-dot" aria-hidden="true"></span>
                                <span class="ce-audio-record-label">Идёт запись…</span>
                            </div>
                            <div id="audioRecordTimer" class="ce-audio-record-timer">0:00</div>
                            <p class="ce-audio-record-hint">Говорите в микрофон. Нажмите «Стоп», когда закончите.</p>
                            <div class="ce-audio-source-actions-row">
                                <button type="button" class="ce-audio-source-btn ce-audio-source-btn--stop" onclick="contentEditor.audioModalStopRecord()">
                                    Стоп
                                </button>
                                <button type="button" class="ce-audio-source-btn ce-audio-source-btn--ghost" onclick="contentEditor.audioModalCancelRecord()">
                                    Отмена
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `
            );
        }

        if (!document.getElementById('imageSourceModal')) {
            document.body.insertAdjacentHTML(
                'beforeend',
                `
                <div id="imageSourceModal" class="ce-image-source-modal" style="display: none;" aria-hidden="true">
                    <div class="ce-image-source-overlay" onclick="contentEditor.closeImageSourceModal()"></div>
                    <div class="ce-image-source-box" role="dialog" aria-modal="true" aria-labelledby="imageSourceModalTitle">
                        <h3 id="imageSourceModalTitle" class="ce-image-source-title">Изображение</h3>
                        <p class="ce-image-source-lead">Выберите источник файла для блока на кадре.</p>
                        <div class="ce-image-source-step">
                            <button type="button" class="ce-image-source-btn ce-image-source-btn--primary" onclick="contentEditor.imageModalPickFromDevice()">
                                Файл с устройства
                            </button>
                            <button type="button" class="ce-image-source-btn ce-image-source-btn--primary" onclick="contentEditor.imageModalOpenLibrary()">
                                Медиатека карточек
                            </button>
                            <button type="button" class="ce-image-source-btn ce-image-source-btn--primary" onclick="contentEditor.imageModalPasteFromClipboard()">
                                Буфер обмена
                            </button>
                            <button type="button" class="ce-image-source-btn ce-image-source-btn--ghost" onclick="contentEditor.closeImageSourceModal()">
                                Отмена
                            </button>
                        </div>
                    </div>
                </div>
                <div id="imageLibraryModal" class="ce-image-library-modal" style="display: none;" aria-hidden="true">
                    <div class="ce-image-library-overlay" onclick="contentEditor.closeImageLibraryModal()"></div>
                    <div class="ce-image-library-box" role="dialog" aria-modal="true" aria-labelledby="imageLibraryModalTitle">
                        <h3 id="imageLibraryModalTitle" class="ce-image-library-title">Медиатека изображений</h3>
                        <p class="ce-image-library-hint">Файлы из вашего каталога медиа карточек. Нажмите миниатюру, чтобы вставить на кадр (повторная загрузка не нужна).</p>
                        <div id="imageLibraryStatus" class="ce-image-library-status" aria-live="polite"></div>
                        <div id="imageLibraryGrid" class="ce-image-library-grid"></div>
                        <div class="ce-image-library-actions">
                            <button type="button" id="imageLibraryLoadMore" class="ce-image-source-btn ce-image-source-btn--ghost" style="display: none;" onclick="contentEditor.imageLibraryLoadMore()">
                                Показать ещё
                            </button>
                            <button type="button" class="ce-image-source-btn ce-image-source-btn--ghost" onclick="contentEditor.closeImageLibraryModal()">
                                Назад
                            </button>
                        </div>
                    </div>
                </div>
            `
            );
        }

        if (window.__CONTENT_CARD_VIEW_ONLY__ !== true) {
            if (!document.getElementById('cardPreviewModal')) {
                document.body.insertAdjacentHTML('beforeend', `
                <div id="cardPreviewModal" class="card-preview-modal card-preview-modal--fullscreen" style="display: none;" aria-hidden="true">
                    <div class="card-preview-overlay" onclick="contentEditor.closeCardPreviewModal()"></div>
                    <div class="card-preview-box" role="dialog" aria-modal="true">
                        <div class="card-preview-header">
                            <h3 class="card-preview-title">Предпросмотр карточки</h3>
                            <div class="card-preview-header-right">
                                <button type="button" id="cardPreviewDeleteBtn" class="card-preview-open-editor" onclick="contentEditor.deleteCurrentPreviewFrame()" title="Удалить текущий кадр" aria-label="Удалить текущий кадр">
                                    <i class="fa fa-trash" aria-hidden="true" style="font-size: 14px; width: 14px;"></i>
                                    <span style="margin-left: 6px;">Удалить кадр</span>
                                </button>
                                <button type="button" class="card-preview-close" onclick="contentEditor.closeCardPreviewModal()" aria-label="Закрыть">&times;</button>
                            </div>
                        </div>
                        <div class="card-preview-nav">
                            <button type="button" class="card-preview-nav-btn" id="cardPreviewPrevBtn" onclick="contentEditor.cardPreviewPrev()">←</button>
                            <span class="card-preview-counter" id="cardPreviewCounter">0 / 0</span>
                            <button type="button" class="card-preview-nav-btn" id="cardPreviewNextBtn" onclick="contentEditor.cardPreviewNext()">→</button>
                            <button type="button" class="card-preview-approve" id="cardPreviewApproveBtn" onclick="contentEditor.cardPreviewApprove()">Далее</button>
                        </div>
                        <div class="card-preview-meta" id="cardPreviewMeta"></div>
                        <div class="card-preview-frame-host" id="cardPreviewFrameHost"></div>
                        <div class="card-preview-footer">
                            <button type="button" class="card-preview-open-editor" onclick="contentEditor.openEditorFromSelectedPreview()">Открыть редактор</button>
                        </div>
                    </div>
                </div>
            `);
            }
            this.cardPreviewModal = document.getElementById('cardPreviewModal');

            if (!document.getElementById('cardLabelsModal')) {
                document.body.insertAdjacentHTML('beforeend', `
                <div id="cardLabelsModal" class="card-labels-modal" style="display: none;" aria-hidden="true">
                    <div class="card-labels-overlay" onclick="contentEditor.cancelCardLabelsStep()"></div>
                    <div class="card-labels-box" role="dialog" aria-modal="true" aria-labelledby="cardLabelsModalTitle">
                        <div class="card-labels-modal-header-row">
                            <h3 id="cardLabelsModalTitle" class="card-labels-title">Метки карточки</h3>
                            <button type="button" id="cardLabelsOpenPresetsBtn" class="card-labels-presets-open-btn" style="display: none;" onclick="contentEditor.openLabelPresetsModal()" title="Пресеты меток">Пресеты</button>
                        </div>
                        <div class="card-labels-input-row">
                            <input type="text" id="cardLabelsInput" class="card-labels-input" maxlength="500" placeholder="Введите метку и нажмите Enter или «Добавить»" autocomplete="off" />
                            <button type="button" class="card-labels-add-btn" onclick="contentEditor.addCardLabelFromInput()">Добавить</button>
                        </div>
                        <div id="cardLabelsList" class="card-labels-list" aria-live="polite"></div>
                        <div class="card-labels-actions">
                            <button type="button" class="card-labels-back-btn" onclick="contentEditor.cancelCardLabelsStep()">К предпросмотру</button>
                            <button type="button" class="card-labels-save-btn" onclick="contentEditor.confirmCardLabels()">Сохранить</button>
                        </div>
                    </div>
                </div>
                <div id="labelPresetsModal" class="label-presets-modal" style="display: none;" aria-hidden="true">
                    <div class="card-labels-overlay" onclick="contentEditor.closeLabelPresetsModal()"></div>
                    <div class="card-labels-box label-presets-modal-box" role="dialog" aria-modal="true" aria-labelledby="labelPresetsModalTitle">
                        <div class="label-presets-modal-header">
                            <h3 id="labelPresetsModalTitle" class="card-labels-title">Пресеты меток</h3>
                            <button type="button" class="label-presets-modal-close" onclick="contentEditor.closeLabelPresetsModal()" aria-label="Закрыть">&times;</button>
                        </div>
                        <p class="card-labels-presets-hint">Нажмите текст пресета — он добавится в список меток карточки (в окне ниже после возврата).</p>
                        <div id="labelPresetsList" class="card-labels-presets-list" aria-live="polite"></div>
                        <div class="card-labels-preset-admin-row">
                            <input type="text" id="labelPresetNewInput" class="card-labels-input" maxlength="255" placeholder="Новый пресет для всех" autocomplete="off" />
                            <button type="button" class="card-labels-add-btn" onclick="contentEditor.createLabelPresetFromInput()">Сохранить в пресеты</button>
                        </div>
                        <div class="card-labels-actions card-labels-actions--preset-footer">
                            <button type="button" class="card-labels-save-btn" onclick="contentEditor.closeLabelPresetsModal()">Готово</button>
                        </div>
                    </div>
                </div>
            `);
            }
            if (!document.getElementById('contentCardDuplicateSourceModal')) {
                document.body.insertAdjacentHTML(
                    'beforeend',
                    `
                <div id="contentCardDuplicateSourceModal" class="card-labels-modal" style="display: none;" aria-hidden="true">
                    <div class="card-labels-overlay" onclick="contentEditor.closeContentCardDuplicateSourceModal()"></div>
                    <div class="card-labels-box" role="dialog" aria-modal="true" aria-labelledby="contentCardDuplicateSourceTitle">
                        <h3 id="contentCardDuplicateSourceTitle" class="card-labels-title">Карточка с таким исходником уже есть</h3>
                        <p id="contentCardDuplicateSourceMessage" class="content-card-duplicate-source-msg"></p>
                        <div class="card-labels-actions">
                            <button type="button" class="card-labels-back-btn" onclick="contentEditor.closeContentCardDuplicateSourceModal()">Отмена</button>
                            <button type="button" class="card-labels-save-btn" onclick="contentEditor.confirmSaveDespiteDuplicateSource()">Всё равно сохранить</button>
                        </div>
                    </div>
                </div>
            `
                );
            }
            if (!document.getElementById('textStylePresetSaveModal')) {
                document.body.insertAdjacentHTML(
                    'beforeend',
                    `
                <div id="textStylePresetSaveModal" class="text-style-preset-modal" style="display: none;" aria-hidden="true">
                    <div class="card-labels-overlay" onclick="contentEditor.closeTextStylePresetSaveModal()"></div>
                    <div class="card-labels-box text-style-preset-modal-box" role="dialog" aria-modal="true" aria-labelledby="textStylePresetSaveTitle">
                        <h3 id="textStylePresetSaveTitle" class="card-labels-title">Сохранить пресет текста</h3>
                        <div class="card-labels-input-row">
                            <input type="text" id="textStylePresetNameInput" class="card-labels-input" maxlength="80" placeholder="Название пресета" autocomplete="off" />
                        </div>
                        <div class="card-labels-actions">
                            <button type="button" class="card-labels-back-btn" onclick="contentEditor.closeTextStylePresetSaveModal()">Отмена</button>
                            <button type="button" class="card-labels-save-btn" onclick="contentEditor.createTextStylePresetFromModal()">Сохранить</button>
                        </div>
                    </div>
                </div>
                <div id="textStylePresetManageModal" class="text-style-preset-modal" style="display: none;" aria-hidden="true">
                    <div class="card-labels-overlay" onclick="contentEditor.closeTextStylePresetManageModal()"></div>
                    <div class="card-labels-box text-style-preset-modal-box" role="dialog" aria-modal="true" aria-labelledby="textStylePresetManageTitle">
                        <div class="label-presets-modal-header">
                            <h3 id="textStylePresetManageTitle" class="card-labels-title">Пресеты текста</h3>
                            <button type="button" class="label-presets-modal-close" onclick="contentEditor.closeTextStylePresetManageModal()" aria-label="Закрыть">&times;</button>
                        </div>
                        <div id="textStylePresetManageList" class="text-style-presets-list" aria-live="polite"></div>
                        <div class="card-labels-actions card-labels-actions--preset-footer">
                            <button type="button" class="card-labels-save-btn" onclick="contentEditor.closeTextStylePresetManageModal()">Готово</button>
                        </div>
                    </div>
                </div>
            `
                );
            }
            this.cardLabelsModal = document.getElementById('cardLabelsModal');
            this.labelPresetsModal = document.getElementById('labelPresetsModal');
            this.textStylePresetSaveModal = document.getElementById('textStylePresetSaveModal');
            this.textStylePresetManageModal = document.getElementById('textStylePresetManageModal');
            const labelsInput = document.getElementById('cardLabelsInput');
            if (labelsInput) {
                labelsInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        this.addCardLabelFromInput();
                    }
                });
            }
            const labelPresetNewInput = document.getElementById('labelPresetNewInput');
            if (labelPresetNewInput) {
                labelPresetNewInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        this.createLabelPresetFromInput();
                    }
                });
            }
            const textStylePresetNameInput = document.getElementById('textStylePresetNameInput');
            if (textStylePresetNameInput) {
                textStylePresetNameInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        this.createTextStylePresetFromModal();
                    }
                });
            }
        } else {
            this.cardPreviewModal = document.getElementById('contentCardViewRoot');
            this.cardLabelsModal = null;
            this.labelPresetsModal = null;
        }

        if (!document.getElementById('textStylePresetSaveModal')) {
            document.body.insertAdjacentHTML(
                'beforeend',
                `
                <div id="textStylePresetSaveModal" class="text-style-preset-modal" style="display: none;" aria-hidden="true">
                    <div class="card-labels-overlay" onclick="contentEditor.closeTextStylePresetSaveModal()"></div>
                    <div class="card-labels-box text-style-preset-modal-box" role="dialog" aria-modal="true" aria-labelledby="textStylePresetSaveTitle">
                        <h3 id="textStylePresetSaveTitle" class="card-labels-title">Сохранить пресет текста</h3>
                        <div class="card-labels-input-row">
                            <input type="text" id="textStylePresetNameInput" class="card-labels-input" maxlength="80" placeholder="Название пресета" autocomplete="off" />
                        </div>
                        <div class="card-labels-actions">
                            <button type="button" class="card-labels-back-btn" onclick="contentEditor.closeTextStylePresetSaveModal()">Отмена</button>
                            <button type="button" class="card-labels-save-btn" onclick="contentEditor.createTextStylePresetFromModal()">Сохранить</button>
                        </div>
                    </div>
                </div>
                <div id="textStylePresetManageModal" class="text-style-preset-modal" style="display: none;" aria-hidden="true">
                    <div class="card-labels-overlay" onclick="contentEditor.closeTextStylePresetManageModal()"></div>
                    <div class="card-labels-box text-style-preset-modal-box" role="dialog" aria-modal="true" aria-labelledby="textStylePresetManageTitle">
                        <div class="label-presets-modal-header">
                            <h3 id="textStylePresetManageTitle" class="card-labels-title">Пресеты текста</h3>
                            <button type="button" class="label-presets-modal-close" onclick="contentEditor.closeTextStylePresetManageModal()" aria-label="Закрыть">&times;</button>
                        </div>
                        <div id="textStylePresetManageList" class="text-style-presets-list" aria-live="polite"></div>
                        <div class="card-labels-actions card-labels-actions--preset-footer">
                            <button type="button" class="card-labels-save-btn" onclick="contentEditor.closeTextStylePresetManageModal()">Готово</button>
                        </div>
                    </div>
                </div>
            `
            );
        }
        this.textStylePresetSaveModal = document.getElementById('textStylePresetSaveModal');
        this.textStylePresetManageModal = document.getElementById('textStylePresetManageModal');
        const textStylePresetNameInput = document.getElementById('textStylePresetNameInput');
        if (textStylePresetNameInput && !textStylePresetNameInput.dataset.cePresetBound) {
            textStylePresetNameInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.createTextStylePresetFromModal();
                }
            });
            textStylePresetNameInput.dataset.cePresetBound = '1';
        }

        this.canvas = document.getElementById('canvas');
        this.editorBoardDisplayHost = null;
        this.ensureEditorBoardDisplayHost();
        this.toolsList = document.getElementById('toolsList');
        this.propertiesContent = document.getElementById('propertiesContent');
        this.propertiesToolsDock = document.getElementById('propertiesToolsDock');
        if (!this.toolsListOriginalParent && this.toolsList) {
            this.toolsListOriginalParent = this.toolsList.parentElement;
        }
        if (!this.propertiesContentOriginalParent && this.propertiesContent) {
            this.propertiesContentOriginalParent = this.propertiesContent.parentElement;
        }

        // Дополнительные ссылки на панели для ресайза
        this.toolbarPanel = this.modal.querySelector('.toolbar');
        this.workspacePanel = this.modal.querySelector('.workspace');
        this.propertiesPanel = this.modal.querySelector('.properties-panel');
        this.ensurePreviewUiParity();
        this.applyPropertiesEmptyState();
        this.wireBoardMatchBannerToolbar();
        this.syncDesktopPanelLayout();
    }

    syncDesktopPanelLayout() {
        if (!this.modal || !this.toolsList) return;
        const body = this.modal.querySelector('.content-editor-body');
        const dock = this.propertiesToolsDock || document.getElementById('propertiesToolsDock');
        const toolsToolbar = this.modal.querySelector('.toolbar.toolbar-tools');
        const boardExtraRow = document.getElementById('toolbarBoardMatchBannerRow');
        if (!body || !dock) return;
        const mobile = this.isMobile();
        if (mobile) {
            body.classList.remove('desktop-merged-tools');
            body.classList.add('mobile-merged-properties');
            dock.hidden = true;
            if (toolsToolbar) {
                if (this.propertiesContent && this.propertiesContent.parentElement !== toolsToolbar) {
                    const mobileToolsAnchor = (this.toolsList && this.toolsList.parentElement === toolsToolbar)
                        ? this.toolsList
                        : null;
                    toolsToolbar.insertBefore(this.propertiesContent, mobileToolsAnchor);
                }
                if (this.toolsList.parentElement !== toolsToolbar) {
                    toolsToolbar.appendChild(this.toolsList);
                }
                if (boardExtraRow && boardExtraRow.parentElement !== toolsToolbar) {
                    toolsToolbar.appendChild(boardExtraRow);
                }
            } else if (this.toolsListOriginalParent && this.toolsList.parentElement !== this.toolsListOriginalParent) {
                this.toolsListOriginalParent.appendChild(this.toolsList);
            }
            return;
        }
        body.classList.remove('mobile-merged-properties');
        if (this.propertiesContentOriginalParent && this.propertiesContent && this.propertiesContent.parentElement !== this.propertiesContentOriginalParent) {
            this.propertiesContentOriginalParent.appendChild(this.propertiesContent);
        }
        body.classList.add('desktop-merged-tools');
        dock.hidden = false;
        if (this.toolsList.parentElement !== dock) {
            dock.appendChild(this.toolsList);
        }
        if (boardExtraRow && boardExtraRow.parentElement !== dock) {
            dock.appendChild(boardExtraRow);
        }
    }

    /** Кнопки «Сохранить кадр» / «Предпросмотр» или «Сохранить» из режима предпросмотра (без обёртки). */
    getPropertiesFrameActionsInnerHtml() {
        if (this.editorOpenedFromPreview || this.editorOpenedFromContentCardView) {
            return `<div class="properties-frame-actions-row">
                        <button type="button" class="action-btn save-from-preview-btn" onclick="contentEditor.confirmSaveFromPreviewEditor()"
                                title="Сохранить" aria-label="Сохранить">
                            <i class="fa fa-save" aria-hidden="true" style="font-size: 14px; width: 14px;"></i>
                        </button>
                    </div>`;
        }
        return `<div class="properties-frame-actions-row">
                    <button type="button" class="action-btn save-frame-inline-btn" onclick="contentEditor.openSaveFrameConfirm()"
                            title="Сохранить кадр" aria-label="Сохранить кадр">
                        <i class="fa fa-save" aria-hidden="true" style="font-size: 14px; width: 14px;"></i>
                    </button>
                    <button type="button" class="action-btn save-card-inline-btn" onclick="contentEditor.openCardPreviewModal()"
                            title="Предпросмотр" aria-label="Предпросмотр">
                        <i class="fa fa-eye" aria-hidden="true" style="font-size: 14px; width: 14px;"></i>
                    </button>
                </div>`;
    }

    getPropertiesEmptyStateHtml() {
        return `<div class="action-buttons action-buttons-col">${this.getPropertiesFrameActionsInnerHtml()}</div>`;
    }

    applyPropertiesEmptyState() {
        if (this.propertiesContent) {
            this.propertiesContent.innerHTML = this.getPropertiesEmptyStateHtml();
        }
    }

    clearPreviewEditSession() {
        this.editorOpenedFromPreview = false;
        this.editorOpenedFromContentCardView = false;
        this.previewEditStorageKey = null;
        this.previewEditFrameId = null;
        this.previewEditSaveSlotIndex = null;
        this._contentCardEditFrameIndex = null;
        this._editorSessionBoardSnapshot = null;
    }

    /**
     * Объединение cardData при сохранении кадра с content-card-view: новые поля из редактора,
     * hints / cube_hints и прочее из оригинала, если в сессии не пришли.
     */
    mergeCardDataForContentCardSave(fresh, orig) {
        if (!orig || typeof orig !== 'object') {
            return fresh && typeof fresh === 'object' ? JSON.parse(JSON.stringify(fresh)) : null;
        }
        const o = JSON.parse(JSON.stringify(orig));
        if (!fresh || typeof fresh !== 'object') {
            return Object.keys(o).length ? o : null;
        }
        const f = JSON.parse(JSON.stringify(fresh));
        for (const [k, v] of Object.entries(f)) {
            if (v !== undefined && v !== null) {
                o[k] = v;
            }
        }
        return Object.keys(o).length ? o : null;
    }

    /** Пересобрать таблицы хода/куба из payload.cardData (если в JSON есть hints / cube_hints). */
    refreshTableElementsFromCardData() {
        if (!this.canvas || !this.cardData) return;
        this.canvas.querySelectorAll('.canvas-element.table-element').forEach((el) => {
            const t = el.dataset.tableType === 'cube' ? 'cube' : 'hints';
            if (t === 'hints' && this.cardData.hints) {
                this.updateTableContent(el, 'hints');
            } else if (t === 'cube' && this.cardData.cube_hints) {
                this.updateTableContent(el, 'cube');
            }
        });
    }

    /** Предпросмотр карточки: как в редакторе, пересобрать таблицы из payload.cardData поверх разметки из elements. */
    refreshPreviewTableElementsFromCardData(inner, payload) {
        if (!inner || !payload || !payload.cardData || typeof payload.cardData !== 'object') return;
        let cd;
        try {
            cd = JSON.parse(JSON.stringify(payload.cardData));
        } catch (e) {
            return;
        }
        if (!cd.hints && !cd.cube_hints) return;
        inner.querySelectorAll('.canvas-element.table-element').forEach((el) => {
            const t = el.dataset.tableType === 'cube' ? 'cube' : 'hints';
            if (t === 'hints' && cd.hints) {
                this.updateTableContent(el, 'hints', cd);
                this.applyContentTableMarkupClasses(el);
            } else if (t === 'cube' && cd.cube_hints) {
                this.updateTableContent(el, 'cube', cd);
                this.applyContentTableMarkupClasses(el);
            }
        });
    }

    /**
     * Единые дефолты сессии редактора, чтобы поведение предпросмотра
     * не зависело от предыдущего открытия страницы/редактора.
     */
    resetEditorSessionDefaults() {
        this.toggleStates = {};
        this.boardMatchBannerEnabled = false;
    }

    /**
     * При каждом открытии редактора начинаем с одинакового состояния панели свойств,
     * чтобы кнопки «Сохранить кадр / Предпросмотр» (и далее удаление/пресеты)
     * были доступны одинаково из всех страниц.
     */
    resetSelectionForFreshOpen() {
        this.selectedElement = null;
        if (this.canvas) {
            this.canvas.querySelectorAll('.canvas-element.selected').forEach((el) => {
                el.classList.remove('selected');
            });
        }
        this.applyPropertiesEmptyState();
    }

    ensurePreviewUiParity() {
        if (typeof window === 'undefined' || window.__CONTENT_CARD_VIEW_ONLY__ === true) return;

        const previewModal = document.getElementById('cardPreviewModal');
        if (previewModal) {
            const headerRight = previewModal.querySelector('.card-preview-header-right');
            if (headerRight && !document.getElementById('cardPreviewDeleteBtn')) {
                const deleteBtn = document.createElement('button');
                deleteBtn.type = 'button';
                deleteBtn.id = 'cardPreviewDeleteBtn';
                deleteBtn.className = 'card-preview-open-editor';
                deleteBtn.title = 'Удалить текущий кадр';
                deleteBtn.setAttribute('aria-label', 'Удалить текущий кадр');
                deleteBtn.innerHTML =
                    '<i class="fa fa-trash" aria-hidden="true" style="font-size: 14px; width: 14px;"></i>' +
                    '<span style="margin-left: 6px;">Удалить кадр</span>';
                deleteBtn.onclick = () => this.deleteCurrentPreviewFrame();
                headerRight.prepend(deleteBtn);
            }

            const nav = previewModal.querySelector('.card-preview-nav');
            if (nav && !document.getElementById('cardPreviewApproveBtn')) {
                const approveBtn = document.createElement('button');
                approveBtn.type = 'button';
                approveBtn.id = 'cardPreviewApproveBtn';
                approveBtn.className = 'card-preview-approve';
                approveBtn.textContent = 'Далее';
                approveBtn.onclick = () => this.cardPreviewApprove();
                nav.appendChild(approveBtn);
            }
        }

        const labelsModal = document.getElementById('cardLabelsModal');
        if (labelsModal && !document.getElementById('cardLabelsOpenPresetsBtn')) {
            const headerRow = labelsModal.querySelector('.card-labels-modal-header-row');
            if (headerRow) {
                const presetsBtn = document.createElement('button');
                presetsBtn.type = 'button';
                presetsBtn.id = 'cardLabelsOpenPresetsBtn';
                presetsBtn.className = 'card-labels-presets-open-btn';
                presetsBtn.style.display = 'none';
                presetsBtn.title = 'Пресеты меток';
                presetsBtn.textContent = 'Пресеты';
                presetsBtn.onclick = () => this.openLabelPresetsModal();
                headerRow.appendChild(presetsBtn);
            }
        }
    }

    openModal() {
        this.clearPreviewEditSession();
        this.resetEditorSessionDefaults();
        // Force cache-busting by adding timestamp to modal
        const timestamp = Date.now();
        if (this.modal) {
            this.modal.setAttribute('data-cache-timestamp', timestamp);
        }

        this.modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        this.loadTools(); // Обновляем инструменты при открытии
        this.syncBoardToolToggleFromState();
        this.syncBoardMatchBannerToolbarVisibility();
        this.renderEditorBoardDisplay();
        this.resetSelectionForFreshOpen();

        // Force refresh of all dynamic content
        this.forceRefreshContent();
    }

    closeModal() {
        if (!this.modal) return;
        this._restoreLiveHintBoardCanvasIfNeeded();
        const fromContentCardView = this.editorOpenedFromContentCardView;
        this.modal.style.display = 'none';
        if (fromContentCardView) {
            this.clearPreviewEditSession();
            document.body.style.overflow = 'hidden';
            if (this.cardPreviewModal) {
                this.cardPreviewModal.style.display = 'flex';
                this.cardPreviewModal.setAttribute('aria-hidden', 'false');
                window.addEventListener('resize', this._onCardPreviewResize);
                this.refreshCardPreviewUI();
            }
        } else {
            document.body.style.overflow = 'auto';
            this.clearPreviewEditSession();
        }
        this.renderEditorBoardDisplay();
    }

    /**
     * @param {object|null} cardData
     * @param {{ fromPreviewRestore?: boolean }} [options] — если true, не сбрасываем сессию «из предпросмотра»
     */
    openModalWithData(cardData, options = {}) {
        if (!options.fromPreviewRestore) {
            this.clearPreviewEditSession();
            this.resetEditorSessionDefaults();
        }
        // Force cache-busting by adding timestamp to modal
        const timestamp = Date.now();
        if (this.modal) {
            this.modal.setAttribute('data-cache-timestamp', timestamp);
        }

        this.modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        this.loadTools(); // Обновляем инструменты при открытии
        this.syncBoardToolToggleFromState();
        this.syncBoardMatchBannerToolbarVisibility();
        this.renderEditorBoardDisplay();
        this.resetSelectionForFreshOpen();

        // Сохраняем данные карточки для использования при выборе инструмента таблицы
        this.cardData = cardData;

        // Force refresh of all dynamic content
        this.forceRefreshContent();
    }

    async openModalWithDuplicateSourceCheck(cardData) {
        if (!window || !window.Telegram || !window.Telegram.WebApp) {
            this.openModalWithData(cardData);
            return;
        }
        try {
            const dup = await this.checkDuplicateSourceFileOnServer();
            if (dup && dup.exists) {
                this.openContentCardDuplicateSourceModal(
                    dup.file_name,
                    dup.content_card_id,
                    () => this.openModalWithData(cardData),
                    'Всё равно открыть редактор'
                );
                return;
            }
        } catch (e) {
            console.error('openModalWithDuplicateSourceCheck:', e);
            this.showNotification(
                e.message || 'Не удалось проверить, нет ли карточки с таким файлом',
                'error'
            );
            return;
        }
        this.openModalWithData(cardData);
    }

    createTableElement(element) {
        // Add cache-busting timestamp
        const timestamp = Date.now();
        element.setAttribute('data-content-timestamp', timestamp);

        // Устанавливаем стандартный тип таблицы - "ход"
        element.dataset.tableType = 'hints';

        // Preserve existing positioning styles and only update content-related styles
        const existingTop = element.style.top;
        const existingLeft = element.style.left;
        const existingWidth = element.style.width;
        const existingHeight = element.style.height;

        // Update only content-related styles without affecting positioning
        element.style.margin = '0';
        element.style.padding = '0';
        element.style.border = 'none';
        element.style.boxSizing = 'border-box';
        element.style.minHeight = '100px';

        if (this.cardData) {
            // Создаем таблицу на основе данных карточки
            this.updateTableContent(element, 'hints');
        } else {
            // Создаем пример таблицу если нет данных
            element.innerHTML = `
                <table class="ce-content-table">
                    <thead>
                        <tr>
                            <th>Ход</th>
                            <th>%</th>
                            <th>%</th>
                            <th>Эквити</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>8/6</td>
                            <td>65.4</td>
                            <td>34.6</td>
                            <td>0.123</td>
                        </tr>
                        <tr>
                            <td>13/9</td>
                            <td>59.8</td>
                            <td>40.2</td>
                            <td>-0.045</td>
                        </tr>
                    </tbody>
                </table>
            `;
        }

        element.classList.add('table-element');
        this.setupEditorTableCollapse(element);

        // Debug: Log position preservation
        console.log('Table position after createTableElement:', {
            top: element.style.top,
            left: element.style.left,
            width: element.style.width,
            height: element.style.height
        });
    }

    updateTableContent(element, tableType, cardDataOverride) {
        const cardData = cardDataOverride !== undefined ? cardDataOverride : this.cardData;
        const wasCollapsed = element.classList.contains('editor-table--collapsed');
        // Debug: Log position before update
        console.log('updateTableContent - before:', {
            top: element.style.top,
            left: element.style.left,
            width: element.style.width,
            height: element.style.height
        });

        element.dataset.tableType = tableType;
        element.innerHTML = '';
        element.classList.remove('editor-table--collapsed');

        if (!cardData) {
            // Если нет данных, показываем заглушку
            element.innerHTML = `
                <div style="padding: 20px; text-align: center; color: #666;">
                    <strong>Нет данных для таблицы</strong>
                </div>
            `;
        } else {
            if (tableType === 'hints' && cardData.hints) {
                const table = this.createHintsTable(cardData.hints, cardData);
                element.appendChild(table);
            } else if (tableType === 'cube' && cardData.cube_hints) {
                const table = this.createCubeTable(cardData.cube_hints, cardData);
                element.appendChild(table);
            } else {
                // Если для выбранного типа нет данных
                element.innerHTML = `
                    <div style="padding: 20px; text-align: center; color: #666;">
                        <strong>Нет данных для типа таблицы: ${tableType === 'hints' ? 'Ход' : 'Куб'}</strong>
                    </div>
                `;
            }
        }

        this.applyContentTableMarkupClasses(element);
        this.setupEditorTableCollapse(element);
        if (wasCollapsed) {
            element.classList.add('editor-table--collapsed');
        }

        // Debug: Log position after update
        console.log('updateTableContent - after:', {
            top: element.style.top,
            left: element.style.left,
            width: element.style.width,
            height: element.style.height
        });
    }

    /**
     * Таблица ходов (как moveTableHtml в hint_viewer.html, без цветовой подсветки строк).
     * @param {Array} hints
     * @param {object|null} item — строка кадра (gnu_move, action, player_name, points …)
     */
    createHintsTable(hints, item) {
        const table = document.createElement('table');
        table.className = 'ce-content-table';

        const header = table.createTHead();
        const headerRow = header.insertRow();
        ['Ход', '%', '%', 'Эквити'].forEach((text) => {
            const th = document.createElement('th');
            th.textContent = text;
            headerRow.appendChild(th);
        });

        const tbody = table.createTBody();
        if (!hints || !Array.isArray(hints)) {
            return table;
        }

        if (item && item.action === 'win') {
            const row = tbody.insertRow();
            const name = item.player_name != null ? item.player_name : (item.player || '');
            const pts = item.points != null ? item.points : '';
            [`Победа ${name} (${pts} очков)`, '-', '-', '-'].forEach((txt) => {
                const c = row.insertCell();
                c.textContent = txt;
            });
            this.highlightBestTableRow(row);
            return table;
        }

        const firstEq = hints.length > 0 && hints[0].eq != null ? hints[0].eq : null;

        hints.forEach((hint, index) => {
            if (!hint.probs || hint.probs.length < 2) return;
            const row = tbody.insertRow();
            const prob1 = hint.probs[0] != null ? (hint.probs[0] * 100).toFixed(1) : '-';
            const prob2 = hint.probs[1] != null ? (hint.probs[1] * 100).toFixed(1) : '-';
            const eq = hint.eq != null ? hint.eq.toFixed(3) : '-';
            const displayEq =
                firstEq !== null && hint.eq !== undefined && index > 0 && typeof hint.eq === 'number'
                    ? `(${(hint.eq - firstEq).toFixed(3)})`
                    : eq;
            const move = hint.move || '-';

            [move, prob1, prob2, displayEq].forEach((txt) => {
                const c = row.insertCell();
                c.textContent = txt;
            });
            if (index === 0) {
                this.highlightBestTableRow(row);
            }
        });

        return table;
    }

    /**
     * Таблица куба (как cubeTableHtml в hint_viewer.html, без цветовой подсветки строк).
     * @param {Array} cubeHints
     * @param {object|null} _item — строка кадра (оставлен для совместимости вызовов)
     */
    createCubeTable(cubeHints, _item) {
        const table = document.createElement('table');
        table.className = 'ce-content-table ce-content-table--cube';

        const header = table.createTHead();
        const headerRow = header.insertRow();
        ['Действие', 'Эквити'].forEach((text) => {
            const th = document.createElement('th');
            th.textContent = text;
            headerRow.appendChild(th);
        });

        const tbody = table.createTBody();
        const ch0 = cubeHints && cubeHints[0];
        if (!ch0 || !ch0.cubeful_equities) {
            return table;
        }

        ch0.cubeful_equities.forEach((hint) => {
            const row = tbody.insertRow();
            const eqVal = hint.eq != null ? hint.eq.toFixed(3) : '-';
            const displayEq = eqVal;
            let displayAction = hint.action_1 || '';
            if (hint.action_2) {
                displayAction += `, ${hint.action_2}`;
            }

            const a = row.insertCell();
            a.textContent = displayAction;
            const e = row.insertCell();
            e.textContent = displayEq;
            if (tbody.rows.length === 1) {
                this.highlightBestTableRow(row);
            }
        });

        return table;
    }

    highlightBestTableRow(row) {
        if (!row) return;
        const bestRowColor = '#2e7d32'; // как .hint-best в hint_viewer.html
        Array.from(row.cells || []).forEach((cell) => {
            cell.style.setProperty('background-color', bestRowColor, 'important');
        });
    }

    /** Классы `ce-content-table` — единые стили в редакторе и в предпросмотре/content-card-view (см. content_editor.css). */
    applyContentTableMarkupClasses(wrapperEl) {
        const first = wrapperEl.firstElementChild;
        const tbl = first && first.tagName === 'TABLE' ? first : wrapperEl.querySelector('table');
        if (!tbl) return;
        tbl.classList.add('ce-content-table');
        if (wrapperEl.dataset.tableType === 'cube') {
            tbl.classList.add('ce-content-table--cube');
        } else {
            tbl.classList.remove('ce-content-table--cube');
        }
    }

    /**
     * Редактор: кнопка сворачивания блока таблицы (аналогично предпросмотру/карточке).
     */
    setupEditorTableCollapse(tableEl) {
        if (!tableEl || !tableEl.classList.contains('table-element')) return;
        if (tableEl.classList.contains('card-preview-canvas-clone')) return;
        if (tableEl.querySelector(':scope > .card-preview-table-toggle')) return;
        if (tableEl.querySelector(':scope > .editor-table-toggle')) return;
        const kids = Array.from(tableEl.children);
        if (!kids.length) return;

        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'editor-table-toggle';
        toggle.setAttribute('aria-expanded', 'true');
        toggle.setAttribute('aria-label', 'Свернуть или развернуть таблицу');
        toggle.title = 'Свернуть или развернуть таблицу';
        toggle.innerHTML = `
            <span class="editor-table-toggle-icon" aria-hidden="true">
                <svg class="editor-table-caret-svg" viewBox="0 0 48 22" xmlns="http://www.w3.org/2000/svg" focusable="false">
                    <path fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round" d="M7 17 L24 5 L41 17"/>
                </svg>
            </span>`;

        const body = document.createElement('div');
        body.className = 'editor-table-collapse-body';
        kids.forEach((k) => body.appendChild(k));
        tableEl.appendChild(toggle);
        tableEl.appendChild(body);

        const syncA11y = () => {
            const collapsed = tableEl.classList.contains('editor-table--collapsed');
            toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        };
        const runRelayoutAnimation = () => {
            if (tableEl.__ceTableRelayoutRaf) {
                cancelAnimationFrame(tableEl.__ceTableRelayoutRaf);
                tableEl.__ceTableRelayoutRaf = 0;
            }
            const startedAt = performance.now();
            const durationMs = 280;
            const tick = () => {
                this.recalculateAllElementPositions();
                if (performance.now() - startedAt < durationMs) {
                    tableEl.__ceTableRelayoutRaf = requestAnimationFrame(tick);
                } else {
                    tableEl.__ceTableRelayoutRaf = 0;
                    this.recalculateAllElementPositions();
                }
            };
            tick();
        };
        const onToggle = (e) => {
            if (e) {
                e.preventDefault();
                e.stopPropagation();
            }
            tableEl.classList.toggle('editor-table--collapsed');
            syncA11y();
            runRelayoutAnimation();
        };

        toggle.addEventListener('click', onToggle);
        toggle.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                onToggle(e);
            }
        });
        syncA11y();
    }

    /** Высота блока при пересчёте вертикального стека (как в recalculateAllElementPositions). */
    getElementStackHeight(element) {
        if (element.classList.contains('table-element')) {
            if (element.classList.contains('editor-table--collapsed')) {
                return 28;
            }
            let h = element.offsetHeight;
            if (h < 50) h = 100;
            return h;
        }
        if (element.dataset.toolId === 'upload-image') {
            return parseInt(element.style.height, 10) || element.offsetHeight || 200;
        }
        if (element.dataset.toolId === 'attach-file') {
            return parseInt(element.style.height, 10) || element.offsetHeight || 72;
        }
        return parseInt(element.style.height, 10) || element.offsetHeight || 150;
    }

    getResponsiveUploadImageHeight(width, naturalWidth, naturalHeight, options = {}) {
        const w = Math.max(0, Math.ceil(Number(width) || 0));
        const nw = Math.max(0, Number(naturalWidth) || 0);
        const nh = Math.max(0, Number(naturalHeight) || 0);
        if (!w || !nw || !nh) return null;
        const minHeight = Math.max(1, Math.ceil(Number(options.minHeight) || 100));
        const maxHeight = Math.max(minHeight, Math.ceil(Number(options.maxHeight) || 600));
        const ratio = nh / nw;
        return Math.max(minHeight, Math.min(maxHeight, Math.ceil(w * ratio)));
    }

    applyResponsiveUploadImageLayout(element, options = {}) {
        if (!element || element.dataset.toolId !== 'upload-image') return null;
        const img = element.querySelector('img');
        if (!img || !img.naturalWidth || !img.naturalHeight) return null;
        const widthFromOption = Number(options.targetWidth) || 0;
        const widthRaw =
            widthFromOption ||
            Math.ceil(element.getBoundingClientRect().width || element.clientWidth || parseFloat(element.style.width) || 0);
        const maxWidth = Math.max(0, Math.ceil(Number(options.maxWidth) || 0));
        const width = maxWidth > 0 ? Math.min(widthRaw, maxWidth) : widthRaw;
        const h = this.getResponsiveUploadImageHeight(width, img.naturalWidth, img.naturalHeight, options);
        if (!h) return null;
        element.style.height = `${h}px`;
        img.style.width = '100%';
        img.style.height = '100%';
        img.style.objectFit = 'contain';
        return h;
    }

    getStackedCanvasElements() {
        if (!this.canvas) return [];
        return Array.from(this.canvas.querySelectorAll('.canvas-element'))
            .filter((el) => !el.id.includes('boardLabel'))
            .sort((a, b) => (parseInt(a.style.top, 10) || 0) - (parseInt(b.style.top, 10) || 0));
    }

    clientYToCanvasScrollY(clientY) {
        if (!this.canvas) return 0;
        const rect = this.canvas.getBoundingClientRect();
        return clientY - rect.top + this.canvas.scrollTop;
    }

    /**
     * Новый порядок блоков после отпускания: вставка по вертикали относительно центров остальных.
     */
    computeStackOrderAfterDrop(dragEl, canvasY) {
        const sorted = this.getStackedCanvasElements();
        const from = sorted.indexOf(dragEl);
        if (from < 0) return sorted;
        sorted.splice(from, 1);
        let insert = 0;
        for (let i = 0; i < sorted.length; i++) {
            const el = sorted[i];
            const t = parseInt(el.style.top, 10) || 0;
            const mid = t + el.offsetHeight / 2;
            if (canvasY < mid) {
                insert = i;
                break;
            }
            insert = i + 1;
        }
        sorted.splice(insert, 0, dragEl);
        return sorted;
    }

    /** Применить порядок: стопка сверху вниз, left=0, ширина канваса, порядок узлов в DOM. */
    applyVerticalStackFromOrder(ordered) {
        if (!this.canvas || !ordered || !ordered.length) return;
        const canvas = this.canvas;
        const w = canvas.getBoundingClientRect().width;
        let nextY = 0;
        ordered.forEach((el) => {
            const h = this.getElementStackHeight(el);
            el.style.left = '0px';
            el.style.top = `${nextY}px`;
            el.style.width = `${w}px`;
            el.style.transform = '';
            canvas.appendChild(el);
            nextY += h;
        });
        this.expandCanvasIfNeeded(nextY);
    }

    ensureBlockDragHandle(element) {
        if (!element || element.querySelector(':scope > .ce-block-drag-handle')) return;
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'ce-block-drag-handle';
        btn.title = 'Перетащить блок (порядок в стопке)';
        btn.setAttribute('aria-label', 'Перетащить блок');
        element.insertBefore(btn, element.firstChild);
    }

    stripBlockDragHandlesFromClone(clone) {
        clone.querySelectorAll('.ce-block-drag-handle').forEach((n) => n.remove());
    }

    elementInnerHtmlForSave(el) {
        const clone = el.cloneNode(true);
        this.stripBlockDragHandlesFromClone(clone);
        return clone.innerHTML;
    }

    /**
     * Нормализует HTML из contenteditable перед сохранением:
     * Telegram/WebView может вставлять эмодзи как <img alt="🙂">.
     * Преобразуем такие узлы обратно в Unicode-текст, чтобы эмодзи
     * стабильно сохранялись в JSON и корректно восстанавливались.
     */
    editableInnerHtmlForSave(editableNode) {
        if (!editableNode) return '';
        const clone = editableNode.cloneNode(true);
        clone.querySelectorAll('img').forEach((img) => {
            const alt = String(img.getAttribute('alt') || img.getAttribute('aria-label') || '').trim();
            if (alt) {
                img.replaceWith(document.createTextNode(alt));
            } else {
                img.remove();
            }
        });
        return clone.innerHTML;
    }

    /**
     * Перестановка блоков только по вертикали: тянуть за ручку слева, отпустить — новая позиция в стопке.
     */
    attachBlockReorderInteractions(element) {
        if (!this.canvas || !element) return;
        if (element.dataset.ceBlockReorderBound === '1') return;
        if (element.id && element.id.includes('boardLabel')) return;

        this.ensureBlockDragHandle(element);
        const handle = element.querySelector(':scope > .ce-block-drag-handle');
        if (!handle) return;

        const DRAG_THRESHOLD_PX = 8;

        const onDown = (ev) => {
            const clientY = ev.touches ? ev.touches[0].clientY : ev.clientY;
            if (ev.type === 'mousedown' && ev.button !== 0) return;
            ev.preventDefault();
            ev.stopPropagation();
            this.selectElement(element);

            const startY = clientY;
            let dragging = false;
            const prevTransition = element.style.transition;
            const prevZ = element.style.zIndex;
            const prevTransform = element.style.transform;

            const onMove = (moveEv) => {
                const cy = moveEv.touches ? moveEv.touches[0].clientY : moveEv.clientY;
                const dy = cy - startY;
                if (!dragging) {
                    if (Math.abs(dy) < DRAG_THRESHOLD_PX) return;
                    dragging = true;
                    element.classList.add('ce-block-dragging');
                    this.canvas.classList.add('ce-stack-drag-active');
                    document.body.style.userSelect = 'none';
                    element.style.transition = 'none';
                    element.style.zIndex = '1000';
                }
                element.style.transform = `translateY(${dy}px)`;
            };

            const cleanupListeners = () => {
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
                document.removeEventListener('touchmove', onTouchMove);
                document.removeEventListener('touchend', onUp);
                document.removeEventListener('touchcancel', onUp);
            };

            const onUp = (upEv) => {
                const cy = upEv.changedTouches ? upEv.changedTouches[0].clientY : upEv.clientY;
                cleanupListeners();
                document.body.style.userSelect = '';
                element.style.transition = prevTransition;
                element.style.zIndex = prevZ;
                element.style.transform = prevTransform || '';
                element.classList.remove('ce-block-dragging');
                this.canvas.classList.remove('ce-stack-drag-active');

                if (!dragging) return;
                const canvasY = this.clientYToCanvasScrollY(cy);
                const newOrder = this.computeStackOrderAfterDrop(element, canvasY);
                this.applyVerticalStackFromOrder(newOrder);
            };

            const onTouchMove = (te) => {
                if (te.cancelable) te.preventDefault();
                onMove(te);
            };

            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
            document.addEventListener('touchmove', onTouchMove, { passive: false });
            document.addEventListener('touchend', onUp);
            document.addEventListener('touchcancel', onUp);
        };

        handle.addEventListener('mousedown', onDown);
        handle.addEventListener('touchstart', onDown, { passive: false });
        element.dataset.ceBlockReorderBound = '1';
    }

    forceRefreshContent() {
        // Force refresh all cached content without affecting positioning
        if (this.canvas) {
            // Just trigger a gentle reflow without hiding/showing elements
            const elements = this.canvas.querySelectorAll('.canvas-element');
            elements.forEach(el => {
                // Gentle reflow that doesn't affect positioning
                el.style.transform = 'translateZ(0)';
                el.offsetHeight; // Force reflow
                el.style.transform = '';
            });
        }

        // Refresh tools list
        if (this.toolsList) {
            this.toolsList.style.transform = 'translateZ(0)';
            this.toolsList.offsetHeight; // Force reflow
            this.toolsList.style.transform = '';
        }

        // Refresh properties panel
        if (this.propertiesContent) {
            const currentContent = this.propertiesContent.innerHTML;
            this.propertiesContent.style.transform = 'translateZ(0)';
            this.propertiesContent.offsetHeight; // Force reflow
            this.propertiesContent.style.transform = '';
        }
    }

    loadTools() {
        // Определяем доступные инструменты согласно требованиям
        const tools = [
            {
                id: 'boardCanvas',
                name: 'Доска с параметрами',
                type: 'canvas',
                description: 'Игровая доска с параметрами (манигейм/матч)',
                icon: 'fa fa-bolt'
            },
            {
                id: 'question-text',
                name: 'Текст вопроса',
                type: 'text',
                description: 'Текст вопроса для анализа',
                icon: 'fa fa-question-circle'
            },
            {
                id: 'moveHintsTable',
                name: 'Таблица',
                type: 'table',
                description: 'Таблица подсказок или данных',
                icon: 'fa fa-table'
            },
            {
                id: 'answer-text',
                name: 'Текст ответа',
                type: 'text',
                description: 'Текст ответа или решения',
                icon: 'fa fa-comment'
            },
            {
                id: 'upload-image',
                name: 'Изображение',
                type: 'image',
                description: 'Файл с устройства или медиатека загрузок карточек',
                icon: 'fa fa-image'
            },
            {
                id: 'audio-file',
                name: 'Аудио-файл',
                type: 'audio',
                description: 'Аудиофайл для воспроизведения',
                icon: 'fa fa-volume-up'
            },
            {
                id: 'attach-file',
                name: 'Файл',
                type: 'file',
                description: 'Прикрепить файл до 30 МБ (S3), скачивание для пользователя',
                icon: 'fa fa-paperclip'
            },
            {
                id: 'support-link',
                name: 'Ссылка',
                type: 'link',
                description: 'Ссылка на дополнительные материалы',
                icon: 'fa fa-link'
            },
            {
                id: 'canvas-settings',
                name: 'Настройки',
                type: 'settings',
                description: 'Настройки фона канваса',
                icon: 'fa fa-cog'
            }
        ];

        this.renderTools(tools);
    }

    renderTools(tools) {
        this.toolsList.innerHTML = `
            <div class="tools-grid">
                ${tools.map(tool => `
                    <div class="tool-item-icon ${tool.id === 'boardCanvas' ? 'toggle-button' : ''}" 
                         data-tool-id="${tool.id}"
                         onclick="contentEditor.selectTool('${tool.id}')"
                         title="${tool.name}">
                        <i class="${tool.icon}"></i>
                    </div>
                `).join('')}
            </div>
        `;
    }

    selectTool(toolId) {
        // Особое поведение для boardCanvas - toggle режим
        if (toolId === 'boardCanvas') {
            this.toggleBoardCanvas(toolId);
            return;
        }

        // Особое поведение для upload-image — модалка: устройство или медиатека S3
        if (toolId === 'upload-image') {
            this.openImageSourceModal();
            return;
        }

        // Особое поведение для audio-file — модалка: файл или запись
        if (toolId === 'audio-file') {
            this.openAudioSourceModal();
            return;
        }

        if (toolId === 'attach-file') {
            this.handleDirectAttachFileUpload();
            return;
        }

        // Особое поведение для canvas-settings - открытие модального окна настроек
        if (toolId === 'canvas-settings') {
            this.openCanvasSettingsModal();
            return;
        }

        // Убираем выделение с предыдущего инструмента
        document.querySelectorAll('.tool-item-icon').forEach(item => {
            item.classList.remove('selected');
        });

        // Выделяем выбранный инструмент
        const selectedTool = document.querySelector(`[data-tool-id="${toolId}"]`);
        if (selectedTool) {
            selectedTool.classList.add('selected');
        }

        // Добавляем элемент на холст
        this.addElementToCanvas(toolId);
    }

    openImageSourceModal() {
        const modal = document.getElementById('imageSourceModal');
        if (!modal) {
            this._triggerLocalImageFilePicker();
            return;
        }
        modal.style.display = 'flex';
        modal.setAttribute('aria-hidden', 'false');
    }

    closeImageSourceModal() {
        const modal = document.getElementById('imageSourceModal');
        if (modal) {
            modal.style.display = 'none';
            modal.setAttribute('aria-hidden', 'true');
        }
    }

    imageModalPickFromDevice() {
        this.closeImageSourceModal();
        setTimeout(() => this._triggerLocalImageFilePicker(), 0);
    }

    /** Выбор файла с диска (прежнее поведение без модалки выбора источника). */
    _triggerLocalImageFilePicker() {
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = 'image/*';
        fileInput.style.display = 'none';

        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file && file.type.startsWith('image/')) {
                this.uploadImageDirectly(file);
            }
            document.body.removeChild(fileInput);
        });

        document.body.appendChild(fileInput);
        fileInput.click();
    }

    /** Вставка картинки из системного буфера обмена (Clipboard API). */
    async imageModalPasteFromClipboard() {
        try {
            if (!navigator.clipboard || typeof navigator.clipboard.read !== 'function') {
                this.showNotification(
                    'В этом окружении нельзя прочитать буфер обмена. Скопируйте изображение и используйте «Файл с устройства», сохранив скриншот.',
                    'warning'
                );
                return;
            }
            const items = await navigator.clipboard.read();
            for (const clipItem of items) {
                const types = clipItem.types || [];
                for (const type of types) {
                    if (!type || !type.startsWith('image/')) continue;
                    const blob = await clipItem.getType(type);
                    if (blob && blob.size > 0) {
                        let ext = (type.split('/')[1] || 'png').toLowerCase();
                        if (ext === 'jpeg') ext = 'jpg';
                        const mime = blob.type && blob.type.startsWith('image/') ? blob.type : type;
                        const file = new File([blob], `clipboard.${ext}`, { type: mime });
                        this.closeImageSourceModal();
                        this.uploadImageDirectly(file);
                        return;
                    }
                }
            }
            this.showNotification('В буфере обмена нет изображения. Скопируйте картинку (например, скриншот) и нажмите снова.', 'warning');
        } catch (e) {
            console.warn('imageModalPasteFromClipboard:', e);
            this.showNotification(
                'Не удалось прочитать буфер: разрешите доступ в браузере или вставьте через «Файл с устройства».',
                'warning'
            );
        }
    }

    imageModalOpenLibrary() {
        const initData = (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || '';
        if (!initData) {
            this.showNotification('Медиатека доступна в Telegram WebApp (нужен init_data)', 'warning');
            return;
        }
        const src = document.getElementById('imageSourceModal');
        const lib = document.getElementById('imageLibraryModal');
        if (!lib) {
            this.showNotification('Окно медиатеки не найдено', 'error');
            return;
        }
        if (src) {
            src.style.display = 'none';
            src.setAttribute('aria-hidden', 'true');
        }
        lib.style.display = 'flex';
        lib.setAttribute('aria-hidden', 'false');
        this._imageLibraryNextToken = null;
        const grid = document.getElementById('imageLibraryGrid');
        const st = document.getElementById('imageLibraryStatus');
        const more = document.getElementById('imageLibraryLoadMore');
        if (grid) grid.innerHTML = '';
        if (st) st.textContent = '';
        if (more) more.style.display = 'none';
        this._fetchImageLibraryPage(null);
    }

    closeImageLibraryModal() {
        const lib = document.getElementById('imageLibraryModal');
        const src = document.getElementById('imageSourceModal');
        if (lib) {
            lib.style.display = 'none';
            lib.setAttribute('aria-hidden', 'true');
        }
        if (src) {
            src.style.display = 'flex';
            src.setAttribute('aria-hidden', 'false');
        }
    }

    _closeAllImageModals() {
        const lib = document.getElementById('imageLibraryModal');
        const src = document.getElementById('imageSourceModal');
        if (lib) {
            lib.style.display = 'none';
            lib.setAttribute('aria-hidden', 'true');
        }
        if (src) {
            src.style.display = 'none';
            src.setAttribute('aria-hidden', 'true');
        }
    }

    imageLibraryLoadMore() {
        if (this._imageLibraryNextToken) {
            this._fetchImageLibraryPage(this._imageLibraryNextToken);
        }
    }

    async _fetchImageLibraryPage(continuationToken) {
        const grid = document.getElementById('imageLibraryGrid');
        const st = document.getElementById('imageLibraryStatus');
        const more = document.getElementById('imageLibraryLoadMore');
        if (!grid) return;
        const initData = (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || '';
        if (!initData) {
            if (st) st.textContent = 'Нет доступа: откройте редактор из Telegram.';
            return;
        }
        if (st && !continuationToken) st.textContent = 'Загрузка…';
        if (more) more.disabled = true;
        try {
            const r = await fetch('/api/content_cards/media/list', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    init_data: initData,
                    continuation_token: continuationToken || null,
                    limit: 48,
                }),
            });
            const data = await r.json().catch(() => ({}));
            if (!r.ok) {
                const d = data.detail;
                const msg =
                    typeof d === 'string'
                        ? d
                        : Array.isArray(d)
                          ? d.map((x) => x.msg || JSON.stringify(x)).join('; ')
                          : `Ошибка ${r.status}`;
                if (st) st.textContent = msg;
                return;
            }
            let items = Array.isArray(data.items) ? data.items.slice() : [];
            items.sort((a, b) => {
                const ta = a && a.last_modified ? Date.parse(a.last_modified) : 0;
                const tb = b && b.last_modified ? Date.parse(b.last_modified) : 0;
                return tb - ta;
            });
            this._imageLibraryNextToken = data.continuation_token || null;
            if (!continuationToken && items.length === 0) {
                if (st) st.textContent = 'Пока нет изображений в медиатеке. Сначала загрузите файл с устройства.';
            } else if (st) {
                st.textContent = '';
            }
            items.forEach((it) => {
                if (!it || !it.key) return;
                const cell = document.createElement('button');
                cell.type = 'button';
                cell.className = 'ce-image-library-cell';
                cell.title = it.filename || it.key;
                const url = this.buildContentCardMediaUrl(it.key);
                const thumb = document.createElement('img');
                thumb.alt = '';
                thumb.loading = 'lazy';
                thumb.src = url;
                thumb.className = 'ce-image-library-thumb';
                const cap = document.createElement('span');
                cap.className = 'ce-image-library-caption';
                cap.textContent = this._shortenImageLibraryFilename(it.filename || it.key);
                cell.appendChild(thumb);
                cell.appendChild(cap);
                cell.addEventListener('click', () => {
                    this._selectImageFromLibrary(it.key, it.filename || '');
                });
                grid.appendChild(cell);
            });
            if (more) {
                more.style.display = this._imageLibraryNextToken ? 'block' : 'none';
                more.disabled = false;
            }
        } catch (e) {
            console.error('_fetchImageLibraryPage:', e);
            if (st) st.textContent = 'Не удалось загрузить список файлов.';
        }
        if (more) more.disabled = false;
    }

    _shortenImageLibraryFilename(name, maxLen = 22) {
        const s = String(name || '').trim() || '—';
        if (s.length <= maxLen) return s;
        const ext = s.includes('.') ? s.slice(s.lastIndexOf('.')) : '';
        const base = ext ? s.slice(0, s.length - ext.length) : s;
        const keep = maxLen - ext.length - 1;
        if (keep < 4) return s.slice(0, maxLen - 1) + '…';
        return `${base.slice(0, Math.ceil(keep / 2))}…${base.slice(-Math.floor(keep / 2))}${ext}`;
    }

    _selectImageFromLibrary(s3Key, filename) {
        this._closeAllImageModals();
        this.addImageElementFromS3Key(s3Key, filename);
    }

    /** Вставка картинки по уже существующему ключу S3 (без повторной загрузки при сохранении кадра). */
    addImageElementFromS3Key(s3Key, displayName) {
        const imageUrl = this.buildContentCardMediaUrl(s3Key);
        if (!imageUrl) {
            this.showNotification('Некорректный ключ файла', 'error');
            return;
        }
        const elementId = `element_${this.elementIdCounter++}`;
        const element = document.createElement('div');
        element.id = elementId;
        element.className = 'canvas-element image-element';
        element.dataset.toolId = 'upload-image';
        element.dataset.imageS3Key = s3Key;
        if (displayName) {
            element.dataset.imageSourceName = String(displayName).slice(0, 240);
        }

        const canvasRect = this.canvas.getBoundingClientRect();
        const canvasWidth = canvasRect.width;

        const img = new Image();
        img.onload = () => {
            const smartHeight = this.getResponsiveUploadImageHeight(canvasWidth, img.naturalWidth, img.naturalHeight) || 200;
            const position = this.calculateVerticalPosition(canvasWidth, smartHeight);

            element.style.left = position.x + 'px';
            element.style.top = position.y + 'px';
            element.style.width = position.width + 'px';
            element.style.height = smartHeight + 'px';

            const imEl = document.createElement('img');
            imEl.src = imageUrl;
            imEl.alt = '';
            imEl.style.width = '100%';
            imEl.style.height = '100%';
            imEl.style.objectFit = 'contain';
            element.appendChild(imEl);

            this.addElementControls(element);
            this.attachBlockReorderInteractions(element);
            this.getCanvasElementsRoot().appendChild(element);

            setTimeout(() => {
                const elementBottom = parseInt(element.style.top, 10) + element.offsetHeight;
                this.expandCanvasIfNeeded(elementBottom);
            }, 100);

            this.elements.push({
                id: elementId,
                toolId: 'upload-image',
                element,
            });

            this.repositionElementsBelow(elementId);
            this.selectElement(element);
        };

        img.onerror = () => {
            console.error('Ошибка загрузки изображения из медиатеки');
            this.showNotification('Не удалось открыть файл из медиатеки', 'error');
        };

        img.src = imageUrl;
    }

    uploadImageDirectly(file) {
        const reader = new FileReader();

        reader.onload = (e) => {
            const imageUrl = e.target.result;

            // Создаем элемент на канвасе с изображением
            this.addImageElementToCanvas(imageUrl, file.name);
        };

        reader.onerror = () => {
            console.error('Ошибка при чтении файла изображения');
            alert('Не удалось прочитать файл изображения');
        };

        reader.readAsDataURL(file);
    }

    openAudioSourceModal() {
        const modal = document.getElementById('audioSourceModal');
        if (!modal) {
            this.showNotification('Модальное окно аудио не найдено', 'error');
            return;
        }
        this._resetAudioSourceModalToPick();
        this._voiceRecordDiscardOnStop = false;
        this._audioModalKeepOpenAfterDiscard = false;
        modal.style.display = 'flex';
        modal.setAttribute('aria-hidden', 'false');
    }

    closeAudioSourceModal() {
        if (this._voiceRecordRecorder && this._voiceRecordRecorder.state === 'recording') {
            this._voiceRecordDiscardOnStop = true;
            this._audioModalKeepOpenAfterDiscard = false;
            try {
                this._voiceRecordRecorder.stop();
            } catch (e) {
                this._syncCleanupVoiceRecording();
                this._finishAudioSourceModalHidden();
                this._resetAudioSourceModalToPick();
            }
            return;
        }
        this._syncCleanupVoiceRecording();
        this._finishAudioSourceModalHidden();
        this._resetAudioSourceModalToPick();
    }

    _finishAudioSourceModalHidden() {
        const modal = document.getElementById('audioSourceModal');
        if (modal) {
            modal.style.display = 'none';
            modal.setAttribute('aria-hidden', 'true');
        }
    }

    _resetAudioSourceModalToPick() {
        const pick = document.getElementById('audioSourceStepPick');
        const rec = document.getElementById('audioSourceStepRecord');
        const timerEl = document.getElementById('audioRecordTimer');
        if (timerEl) timerEl.textContent = '0:00';
        if (pick) pick.style.display = 'flex';
        if (rec) rec.style.display = 'none';
    }

    _syncCleanupVoiceRecording() {
        clearInterval(this._voiceRecordTimerId);
        this._voiceRecordTimerId = null;
        this._voiceRecordStartedAt = 0;
        this._voiceRecordChunks = [];
        this._voiceRecordRecorder = null;
        if (this._voiceRecordStream) {
            this._voiceRecordStream.getTracks().forEach((t) => t.stop());
            this._voiceRecordStream = null;
        }
    }

    /** Длительность для подписи под аудио (целые секунды). */
    _formatAudioDurationLabel(totalSec) {
        if (!Number.isFinite(totalSec) || totalSec < 0) return '';
        const s = Math.floor(totalSec);
        const m = Math.floor(s / 60);
        const sec = s % 60;
        return `${m}:${String(sec).padStart(2, '0')}`;
    }

    /** Текст заголовка аудио на холсте: подпись или имя файла. */
    _audioElementDisplayTitle(el) {
        const t = (el.dataset && el.dataset.audioTitle) || '';
        const n = (el.dataset && el.dataset.audioName) || '';
        return (t && String(t).trim()) || n || 'Аудио';
    }

    audioModalPickFile() {
        this.closeAudioSourceModal();
        this.handleDirectAudioUpload();
    }

    _preferredAudioRecorderMime() {
        if (typeof MediaRecorder === 'undefined' || !MediaRecorder.isTypeSupported) {
            return '';
        }
        const types = [
            'audio/webm;codecs=opus',
            'audio/webm',
            'audio/ogg;codecs=opus',
            'audio/mp4',
        ];
        for (const t of types) {
            if (MediaRecorder.isTypeSupported(t)) return t;
        }
        return '';
    }

    async audioModalStartRecord() {
        if (typeof MediaRecorder === 'undefined') {
            this.showNotification('Запись аудио не поддерживается в этом браузере', 'error');
            return;
        }
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.showNotification('Доступ к микрофону недоступен', 'error');
            return;
        }
        const pick = document.getElementById('audioSourceStepPick');
        const rec = document.getElementById('audioSourceStepRecord');
        const timerEl = document.getElementById('audioRecordTimer');
        if (!pick || !rec) return;

        const mime = this._preferredAudioRecorderMime();
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                },
            });
            this._voiceRecordStream = stream;
            const opts = mime ? { mimeType: mime } : {};
            const mr = new MediaRecorder(stream, opts);
            this._voiceRecordChunks = [];
            mr.ondataavailable = (e) => {
                if (e.data && e.data.size > 0) this._voiceRecordChunks.push(e.data);
            };
            mr.onstop = () => this._onVoiceMediaRecorderStop(mr);
            this._voiceRecordRecorder = mr;
            this._voiceRecordDiscardOnStop = false;
            this._audioModalKeepOpenAfterDiscard = false;
            mr.start(200);
            this._voiceRecordStartedAt = Date.now();

            pick.style.display = 'none';
            rec.style.display = 'flex';
            if (timerEl) timerEl.textContent = '0:00';
            const startMs = this._voiceRecordStartedAt;
            this._voiceRecordTimerId = setInterval(() => {
                const s = Math.floor((Date.now() - startMs) / 1000);
                const m = Math.floor(s / 60);
                const sec = s % 60;
                if (timerEl) {
                    timerEl.textContent = `${m}:${String(sec).padStart(2, '0')}`;
                }
            }, 400);
        } catch (err) {
            console.error('audioModalStartRecord:', err);
            this.showNotification(
                err && err.name === 'NotAllowedError'
                    ? 'Разрешите доступ к микрофону'
                    : 'Не удалось начать запись',
                'error'
            );
            this._syncCleanupVoiceRecording();
        }
    }

    _onVoiceMediaRecorderStop(mr) {
        clearInterval(this._voiceRecordTimerId);
        this._voiceRecordTimerId = null;
        const recordedSec =
            this._voiceRecordStartedAt > 0
                ? Math.max(0, Math.round((Date.now() - this._voiceRecordStartedAt) / 1000))
                : null;
        this._voiceRecordStartedAt = 0;
        const discard = this._voiceRecordDiscardOnStop;
        const keepOpen = this._audioModalKeepOpenAfterDiscard;
        this._voiceRecordDiscardOnStop = false;
        this._audioModalKeepOpenAfterDiscard = false;

        const mimeType = (mr && mr.mimeType) || 'audio/webm';
        const chunks = this._voiceRecordChunks.slice();
        this._voiceRecordChunks = [];
        this._voiceRecordRecorder = null;
        if (this._voiceRecordStream) {
            this._voiceRecordStream.getTracks().forEach((t) => t.stop());
            this._voiceRecordStream = null;
        }

        if (discard) {
            if (keepOpen) {
                this._resetAudioSourceModalToPick();
            } else {
                this._finishAudioSourceModalHidden();
                this._resetAudioSourceModalToPick();
            }
            return;
        }

        const blob = new Blob(chunks, { type: mimeType });
        if (blob.size < 64) {
            this.showNotification('Слишком короткая запись', 'warning');
            this._finishAudioSourceModalHidden();
            this._resetAudioSourceModalToPick();
            return;
        }

        let ext = 'webm';
        if (mimeType.includes('mp4') || mimeType.includes('mpeg') || mimeType.includes('m4a')) ext = 'm4a';
        else if (mimeType.includes('ogg')) ext = 'ogg';
        else if (mimeType.includes('webm')) ext = 'webm';

        const name = `voice_${Date.now()}.${ext}`;
        const file = new File([blob], name, { type: mimeType });
        const url = URL.createObjectURL(blob);
        this._finishAudioSourceModalHidden();
        this._resetAudioSourceModalToPick();
        this.addAudioElementToCanvas(url, name, file, {
            audioTitle: 'Голосовое сообщение',
            knownDurationSec: recordedSec,
        });
    }

    audioModalStopRecord() {
        this._voiceRecordDiscardOnStop = false;
        this._audioModalKeepOpenAfterDiscard = false;
        if (this._voiceRecordRecorder && this._voiceRecordRecorder.state === 'recording') {
            try {
                this._voiceRecordRecorder.stop();
            } catch (e) {
                console.error('audioModalStopRecord:', e);
                this.showNotification('Не удалось завершить запись', 'error');
                this.closeAudioSourceModal();
            }
        }
    }

    audioModalCancelRecord() {
        if (this._voiceRecordRecorder && this._voiceRecordRecorder.state === 'recording') {
            this._voiceRecordDiscardOnStop = true;
            this._audioModalKeepOpenAfterDiscard = true;
            try {
                this._voiceRecordRecorder.stop();
            } catch (e) {
                this._syncCleanupVoiceRecording();
                this._resetAudioSourceModalToPick();
            }
        } else {
            this._resetAudioSourceModalToPick();
        }
    }

    handleDirectAudioUpload() {
        // Создаем временный input для выбора файла
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = 'audio/*';
        fileInput.style.display = 'none';

        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file && file.type.startsWith('audio/')) {
                this.uploadAudioDirectly(file);
            }
            // Удаляем временный input
            document.body.removeChild(fileInput);
        });

        // Добавляем input в DOM и вызываем клик
        document.body.appendChild(fileInput);
        fileInput.click();
    }

    uploadAudioDirectly(file) {
        const reader = new FileReader();

        reader.onload = (e) => {
            const audioUrl = e.target.result;

            // Создаем элемент на канвасе с аудио
            this.addAudioElementToCanvas(audioUrl, file.name, file);
        };

        reader.onerror = () => {
            console.error('Ошибка при чтении файла аудио');
            alert('Не удалось прочитать файл аудио');
        };

        reader.readAsDataURL(file);
    }

    handleDirectAttachFileUpload() {
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.style.display = 'none';

        fileInput.addEventListener('change', async (e) => {
            const file = e.target.files && e.target.files[0];
            if (file) {
                await this.importAttachFileFromFile(file);
            }
            if (fileInput.parentNode) {
                document.body.removeChild(fileInput);
            }
        });

        document.body.appendChild(fileInput);
        fileInput.click();
    }

    async importAttachFileFromFile(file) {
        if (!file) return;
        if (file.size > ContentEditor.ATTACH_FILE_MAX_BYTES) {
            this.showNotification('Файл больше 30 МБ', 'error');
            return;
        }
        const initData = (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || '';
        if (!initData) {
            this.showNotification('Загрузка доступна из Telegram WebApp (нужен init_data)', 'warning');
            return;
        }
        try {
            this.showNotification('Загрузка файла…', 'info');
            const up = await this.uploadBinaryToContentCardMedia(
                file,
                file.name,
                file.type || 'application/octet-stream'
            );
            this.addAttachFileElementToCanvas(up.s3_key, file.name, up.content_type || file.type || '');
            this.showNotification('Файл прикреплён', 'success');
        } catch (err) {
            console.error('importAttachFileFromFile:', err);
            this.showNotification('Не удалось загрузить: ' + (err.message || err), 'error');
        }
    }

    addAttachFileElementToCanvas(s3Key, fileName, contentType) {
        const elementId = `element_${this.elementIdCounter++}`;
        const element = document.createElement('div');
        element.id = elementId;
        element.className = 'canvas-element ce-attach-file-element';
        element.dataset.toolId = 'attach-file';
        element.dataset.attachmentS3Key = s3Key;
        element.dataset.attachmentFileName = fileName || 'file';
        element.dataset.attachmentContentType = contentType || '';

        const canvasRect = this.canvas.getBoundingClientRect();
        const position = this.calculateVerticalPosition(canvasRect.width, 72);
        element.style.left = position.x + 'px';
        element.style.top = position.y + 'px';
        element.style.width = position.width + 'px';
        element.style.height = '72px';

        this.buildAttachFileElementInner(element, false);
        this.getCanvasElementsRoot().appendChild(element);
        this.addElementControls(element);
        this.attachBlockReorderInteractions(element);
        this.elements.push({
            id: elementId,
            toolId: 'attach-file',
            element,
        });
        this.selectElement(element);
    }

    buildAttachFileElementInner(element, previewMode) {
        const name = element.dataset.attachmentFileName || 'Файл';
        const s3Key = element.dataset.attachmentS3Key || '';
        element.innerHTML = '';
        const wrap = document.createElement('div');
        wrap.className = previewMode ? 'ce-attach-file-inner' : 'ce-attach-file-inner ce-attach-file-inner--editor';
        const icon = document.createElement('span');
        icon.className = 'ce-attach-file-icon';
        icon.setAttribute('aria-hidden', 'true');
        icon.textContent = '📎';
        const label = document.createElement('span');
        label.className = 'ce-attach-file-name';
        label.textContent = name;
        wrap.appendChild(icon);
        wrap.appendChild(label);
        if (previewMode) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'ce-attach-file-download-btn';
            btn.textContent = 'Скачать';
            btn.setAttribute('aria-label', `Скачать ${name}`);
            wrap.appendChild(btn);
            element.appendChild(wrap);
            this.wireAttachFileDownloadButton(btn, s3Key, name);
        } else {
            element.appendChild(wrap);
        }
    }

    wireAttachFileDownloadButton(btn, s3Key, fileName) {
        if (!btn) return;
        if (!s3Key) {
            btn.disabled = true;
            btn.textContent = 'Файл недоступен';
            return;
        }
        const handler = (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.requestAttachmentDownload(s3Key, fileName);
        };
        btn.addEventListener('click', handler);
    }

    /**
     * Скачивание: Telegram.WebApp.downloadFile при наличии, иначе открытие URL с attachment.
     */
    requestAttachmentDownload(s3Key, fileName) {
        if (!s3Key) return;
        const safeName = (fileName && String(fileName).replace(/[\\/]/g, '_').trim()) || 'file';
        const path = this.buildContentCardMediaDownloadUrl(s3Key, safeName);
        this.requestDownloadByPath(path, safeName);
    }

    requestDownloadByPath(path, fileName) {
        if (!path) return;
        let absUrl;
        try {
            absUrl = new URL(path, window.location.href).href;
        } catch (e) {
            absUrl = path;
        }
        this.requestDownloadByUrl(absUrl, fileName);
    }

    requestDownloadByUrl(absUrl, fileName) {
        const safeName = (fileName && String(fileName).replace(/[\\/]/g, '_').trim()) || 'file';
        const tw = window.Telegram && window.Telegram.WebApp;
        if (tw && typeof tw.downloadFile === 'function') {
            try {
                tw.downloadFile({ url: absUrl, file_name: safeName }, (accepted) => {
                    if (accepted === false) {
                        this.showNotification('Скачивание отменено', 'info');
                    }
                });
                return;
            } catch (err) {
                console.warn('Telegram.WebApp.downloadFile:', err);
            }
        }
        const a = document.createElement('a');
        a.href = absUrl;
        a.setAttribute('download', safeName);
        a.rel = 'noopener noreferrer';
        a.target = '_blank';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    buildContentCardMediaDownloadUrl(s3Key, displayFileName) {
        if (!s3Key) return '';
        const params = new URLSearchParams({ key: s3Key, download: '1' });
        if (displayFileName) {
            params.set('filename', String(displayFileName).slice(0, 240));
        }
        return `/api/content_cards/media?${params.toString()}`;
    }

    addAudioElementToCanvas(audioUrl, fileName, file, opts = {}) {
        const elementId = `element_${this.elementIdCounter++}`;
        const element = document.createElement('div');
        element.id = elementId;
        element.className = 'canvas-element audio-element';
        element.dataset.toolId = 'audio-file';
        element.dataset.audioUrl = audioUrl;
        element.dataset.audioName = fileName;
        if (opts.audioTitle) {
            element.dataset.audioTitle = String(opts.audioTitle);
        }
        if (opts.knownDurationSec != null && Number.isFinite(Number(opts.knownDurationSec))) {
            element.dataset.audioKnownDurationSec = String(Math.max(0, Number(opts.knownDurationSec)));
        }

        const displayTitle = opts.audioTitle ? String(opts.audioTitle) : fileName;

        // Get canvas dimensions
        const canvasRect = this.canvas.getBoundingClientRect();
        const maxCanvasWidth = this.getMaxCanvasWidth();
        const maxCanvasHeight = this.getMaxCanvasHeight();

        // Calculate position for audio element
        const position = this.calculateVerticalPosition(canvasRect.width, 80); // Default height 80px

        element.style.left = position.x + 'px';
        element.style.top = position.y + 'px';
        element.style.width = position.width + 'px';
        element.style.height = '80px'; // Default height

        // Add messenger-style audio content
        element.innerHTML = `
            <div class="audio-message" style="display: flex; align-items: center; padding: 12px; height: 100%; background: #f0f0f0; border-radius: 8px;">
                <div class="audio-icon" style="font-size: 24px; margin-right: 12px; color: #667eea;">🎵</div>
                <div class="audio-info" style="flex: 1;">
                    <div class="audio-name" style="font-size: 14px; font-weight: 500; color: #333; margin-bottom: 4px;">${this.escapeHtml(displayTitle)}</div>
                    <div class="audio-duration" style="font-size: 12px; color: #666;">Загрузка...</div>
                </div>
                <div class="audio-play-btn" style="width: 32px; height: 32px; border-radius: 50%; background: #667eea; color: white; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 16px;">
                    ▶
                </div>
            </div>
        `;

        // Add controls
        this.addElementControls(element);
        this.attachBlockReorderInteractions(element);

        // Add to canvas
        this.getCanvasElementsRoot().appendChild(element);

        // Expand canvas if needed for the audio element
        setTimeout(() => {
            const elementBottom = parseInt(element.style.top) + element.offsetHeight;
            this.expandCanvasIfNeeded(elementBottom);
        }, 100);

        // Setup audio functionality
        this.setupAudioElement(element, audioUrl, file);

        // Save to elements array
        this.elements.push({
            id: elementId,
            toolId: 'audio-file',
            element: element
        });

        // Select element
        this.selectElement(element);
    }

    setupAudioElement(element, audioUrl, file) {
        const playBtn = element.querySelector('.audio-play-btn');
        const durationEl = element.querySelector('.audio-duration');

        // Create audio element (hidden)
        const audio = document.createElement('audio');
        audio.src = audioUrl;
        audio.preload = 'metadata';
        element.appendChild(audio);

        const knownRaw = element.dataset.audioKnownDurationSec;
        if (knownRaw !== undefined && knownRaw !== '') {
            const ks = Number(knownRaw);
            if (Number.isFinite(ks)) {
                const lbl = this._formatAudioDurationLabel(ks);
                if (lbl) durationEl.textContent = lbl;
            }
            delete element.dataset.audioKnownDurationSec;
        }

        // Get audio duration (blob/WebM часто даёт Infinity до полной загрузки — не показываем)
        audio.addEventListener('loadedmetadata', () => {
            const duration = audio.duration;
            if (Number.isFinite(duration) && duration > 0 && duration < 86400) {
                durationEl.textContent = this._formatAudioDurationLabel(duration);
                durationEl.style.display = '';
                return;
            }
            const cur = (durationEl.textContent || '').trim();
            if (cur && cur !== 'Загрузка...') {
                return;
            }
            durationEl.textContent = '';
            durationEl.style.display = 'none';
        });

        // Play/pause functionality
        let isPlaying = false;
        playBtn.addEventListener('click', (e) => {
            e.stopPropagation();

            if (isPlaying) {
                audio.pause();
                playBtn.textContent = '▶';
                isPlaying = false;
            } else {
                audio.play();
                playBtn.textContent = '⏸';
                isPlaying = true;
            }
        });

        // Reset play button when audio ends
        audio.addEventListener('ended', () => {
            playBtn.textContent = '▶';
            isPlaying = false;
        });
    }

    addImageElementToCanvas(imageUrl, fileName) {
        const elementId = `element_${this.elementIdCounter++}`;
        const element = document.createElement('div');
        element.id = elementId;
        element.className = 'canvas-element image-element';
        element.dataset.toolId = 'upload-image';
        element.dataset.imageUrl = imageUrl;

        // Get canvas dimensions
        const canvasRect = this.canvas.getBoundingClientRect();
        const canvasWidth = canvasRect.width;

        // Create image to get natural dimensions
        const img = new Image();
        img.onload = () => {
            const smartHeight = this.getResponsiveUploadImageHeight(canvasWidth, img.naturalWidth, img.naturalHeight) || 200;

            // Calculate position for image element
            const position = this.calculateVerticalPosition(canvasWidth, smartHeight);

            element.style.left = position.x + 'px';
            element.style.top = position.y + 'px';
            element.style.width = position.width + 'px';
            element.style.height = smartHeight + 'px';

            // Add image content with proper styling
            element.innerHTML = `
                <img src="${imageUrl}" style="width: 100%; height: 100%; object-fit: contain;" />
            `;

            // Add controls
            this.addElementControls(element);
            this.attachBlockReorderInteractions(element);

            // Add to canvas
            this.getCanvasElementsRoot().appendChild(element);

            // Expand canvas if needed for the image
            setTimeout(() => {
                const elementBottom = parseInt(element.style.top) + element.offsetHeight;
                this.expandCanvasIfNeeded(elementBottom);
            }, 100);

            // Save to elements array
            this.elements.push({
                id: elementId,
                toolId: 'upload-image',
                element: element
            });

            // Reposition elements below the new image
            this.repositionElementsBelow(elementId);

            // Select element
            this.selectElement(element);
        };

        img.onerror = () => {
            console.error('Ошибка загрузки изображения');
            alert('Не удалось загрузить изображение');
        };

        // Start loading the image
        img.src = imageUrl;
    }

    toggleBoardCanvas(toolId) {
        // Инициализируем состояние если нужно
        if (this.toggleStates[toolId] === undefined) {
            this.toggleStates[toolId] = false;
        }

        // Переключаем состояние
        this.toggleStates[toolId] = !this.toggleStates[toolId];

        // Находим элемент кнопки
        const toolElement = document.querySelector(`[data-tool-id="${toolId}"]`);
        if (toolElement) {
            if (this.toggleStates[toolId]) {
                // Включаем "горит" состояние
                toolElement.classList.add('toggle-active');
                toolElement.classList.remove('selected');

                // Показываем уведомление или выполняем действие
                this.showToggleNotification(toolId, true);
            } else {
                // Выключаем "горит" состояние
                toolElement.classList.remove('toggle-active');

                // Скрываем уведомление
                this.showToggleNotification(toolId, false);
            }
        }

        this.syncLiveHintBoardCanvasOverlay();
        this.syncBoardMatchBannerToolbarVisibility();
    }

    /**
     * Раньше при открытой модалке и включённом тумблере «Доска» страничный #boardCanvas поднимался поверх редактора.
     * Теперь в редакторе используется отдельный read-only рендер доски; этот метод
     * снимает legacy-оверлей и синхронизирует встроенное отображение.
     */
    syncLiveHintBoardCanvasOverlay() {
        this._restoreLiveHintBoardCanvasIfNeeded();
        this.renderEditorBoardDisplay();
    }

    _restoreLiveHintBoardCanvasIfNeeded() {
        const el = document.getElementById('boardCanvas');
        if (el) {
            el.classList.remove('content-editor-live-board-overlay');
            if (this._liveBoardCanvasStyleBackup !== null) {
                el.setAttribute('style', this._liveBoardCanvasStyleBackup);
                this._liveBoardCanvasStyleBackup = null;
            }
        } else {
            this._liveBoardCanvasStyleBackup = null;
        }
    }

    ensureEditorBoardDisplayHost() {
        if (!this.canvas) return null;
        const existingById = document.getElementById('editorBoardDisplayHost');
        if (existingById && !this.canvas.contains(existingById)) {
            existingById.remove();
        }
        let host = this.canvas.querySelector(':scope > #editorBoardDisplayHost');
        if (!host) {
            const layer = this.ensureCanvasContentLayer();
            if (layer) {
                layer.insertAdjacentHTML(
                    'beforebegin',
                    `<div id="editorBoardDisplayHost" class="editor-board-display-host" hidden aria-hidden="true"></div>`
                );
            } else {
                this.canvas.insertAdjacentHTML(
                    'afterbegin',
                    `<div id="editorBoardDisplayHost" class="editor-board-display-host" hidden aria-hidden="true"></div>`
                );
            }
            host = this.canvas.querySelector(':scope > #editorBoardDisplayHost');
        }
        this.editorBoardDisplayHost = host;
        return host;
    }

    ensureCanvasContentLayer() {
        if (!this.canvas) return null;
        let layer = this.canvas.querySelector(':scope > #editorCanvasContentLayer');
        if (!layer) {
            this.canvas.insertAdjacentHTML(
                'beforeend',
                `<div id="editorCanvasContentLayer" class="editor-canvas-content-layer"></div>`
            );
            layer = this.canvas.querySelector(':scope > #editorCanvasContentLayer');
        }
        return layer;
    }

    getCanvasElementsRoot() {
        return this.ensureCanvasContentLayer() || this.canvas;
    }

    resetCanvasDomStructure() {
        if (!this.canvas) return;
        this.canvas.innerHTML = '';
        this.editorBoardDisplayHost = null;
        this.ensureCanvasContentLayer();
        this.ensureEditorBoardDisplayHost();
    }

    getEditorBoardSnapshotForDisplay() {
        let snapshot = null;
        if (typeof window !== 'undefined' && typeof window.getHintViewerBoardSnapshot === 'function') {
            try {
                snapshot = window.getHintViewerBoardSnapshot();
            } catch (e) {
                console.warn('getEditorBoardSnapshotForDisplay:', e);
                snapshot = null;
            }
        }
        if ((snapshot == null || typeof snapshot !== 'object') && this._editorSessionBoardSnapshot != null) {
            snapshot = this._editorSessionBoardSnapshot;
        }
        if (snapshot == null || typeof snapshot !== 'object') return null;
        try {
            return JSON.parse(JSON.stringify(snapshot));
        } catch (e) {
            return snapshot;
        }
    }

    clearEditorBoardDisplay() {
        const host = this.ensureEditorBoardDisplayHost();
        if (!host) return;
        host.innerHTML = '';
        host.classList.remove('is-visible');
        host.hidden = true;
        host.setAttribute('aria-hidden', 'true');
    }

    renderEditorBoardDisplay() {
        const host = this.ensureEditorBoardDisplayHost();
        if (!host) return;
        const boardEnabled = !!this.toggleStates['boardCanvas'];
        if (!boardEnabled) {
            this.clearEditorBoardDisplay();
            return;
        }
        const snapshot = this.getEditorBoardSnapshotForDisplay();
        if (!snapshot || snapshot.error === 'no_game_data') {
            host.innerHTML = `<div class="editor-board-display-empty">Нет данных доски для отображения</div>`;
            host.classList.add('is-visible');
            host.hidden = false;
            host.setAttribute('aria-hidden', 'false');
            return;
        }
        const showMatchBanner = !!this.boardMatchBannerEnabled;
        let bannerText = showMatchBanner ? this.formatBoardMatchBannerText(snapshot) : '';
        if (showMatchBanner && !bannerText) {
            bannerText = 'Данные матча недоступны';
        }
        host.innerHTML = `
            <div class="editor-board-display">
                <div class="editor-board-display-body">
                    <div class="editor-board-match-banner" ${showMatchBanner ? '' : 'hidden'}>${this.escapeHtml(bannerText)}</div>
                    <div class="editor-board-canvas-wrap">
                        <canvas class="editor-board-canvas" width="800" height="800" aria-hidden="true"></canvas>
                    </div>
                </div>
                <button type="button" class="editor-board-toggle" aria-expanded="true" aria-label="Свернуть или развернуть доску" title="Свернуть или развернуть доску">
                    <span class="editor-board-toggle-icon" aria-hidden="true">
                        <svg class="editor-board-caret-svg" viewBox="0 0 48 22" xmlns="http://www.w3.org/2000/svg" focusable="false">
                            <path fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round" d="M7 17 L24 5 L41 17"/>
                        </svg>
                    </span>
                </button>
            </div>
        `;
        host.classList.add('is-visible');
        host.hidden = false;
        host.setAttribute('aria-hidden', 'false');
        this.setupEditorBoardCollapse(host);
        const canvas = host.querySelector('.editor-board-canvas');
        if (!canvas) return;
        this.loadBoardPreviewImages()
            .then((imgs) => {
                if (!canvas.isConnected) return;
                this.paintBoardPreviewCanvas(canvas, snapshot, imgs);
            })
            .catch((err) => {
                console.error('renderEditorBoardDisplay:', err);
            });
    }

    setupEditorBoardCollapse(host) {
        if (!host) return;
        const display = host.querySelector('.editor-board-display');
        const toggle = host.querySelector('.editor-board-toggle');
        if (!display || !toggle) return;
        const collapsedInitial = !!this._editorBoardCollapsed;
        display.classList.toggle('editor-board-display--collapsed', collapsedInitial);
        toggle.setAttribute('aria-expanded', collapsedInitial ? 'false' : 'true');
        const onToggle = (e) => {
            if (e) {
                e.preventDefault();
                e.stopPropagation();
            }
            const collapsedNow = !display.classList.contains('editor-board-display--collapsed');
            display.classList.toggle('editor-board-display--collapsed', collapsedNow);
            this._editorBoardCollapsed = collapsedNow;
            toggle.setAttribute('aria-expanded', collapsedNow ? 'false' : 'true');
        };
        toggle.addEventListener('click', onToggle);
        toggle.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                onToggle(e);
            }
        });
    }

    showToggleNotification(toolId, isActive) {
        console.log(`${toolId} is now ${isActive ? 'ACTIVE' : 'INACTIVE'}`);
    }

    expandCanvasIfNeeded(elementBottom) {
        // Канвас больше не управляет размером контейнера, он всегда занимает
        // фиксированную область и скроллится внутри. Здесь оставляем только лог при отладке.
        // const requiredHeight = elementBottom + 40;
        // console.log(`Canvas content bottom at ${requiredHeight}px`);
    }

    calculateVerticalPosition(elementWidth, elementHeight) {
        const canvasRect = this.canvas.getBoundingClientRect();
        const maxCanvasWidth = this.getMaxCanvasWidth();
        const maxCanvasHeight = this.getMaxCanvasHeight();

        // Get existing elements sorted by their top position
        const existingElements = Array.from(this.canvas.querySelectorAll('.canvas-element'))
            .filter(el => !el.id.includes('boardLabel')) // Исключаем boardLabel
            .sort((a, b) => parseInt(a.style.top) - parseInt(b.style.top));

        // All elements now occupy actual canvas width without margins
        const centerX = 0;
        // Use actual canvas width for proper scaling on mobile
        const fullWidth = canvasRect.width;

        // Calculate vertical position with no spacing
        const startY = 0; // No top margin for first element
        const elementSpacing = 0; // No spacing between elements

        let nextY = startY;

        // Find the next available vertical position
        for (const existingEl of existingElements) {
            const existingTop = parseInt(existingEl.style.top);
            let existingHeight;

            // Get actual height of existing element
            if (existingEl.classList.contains('table-element')) {
                if (existingEl.classList.contains('editor-table--collapsed')) {
                    existingHeight = 28;
                } else {
                    // For table elements, get the actual rendered height
                    existingHeight = existingEl.offsetHeight;

                    // Force a reflow to ensure we have the correct height
                    if (existingHeight < 50) {
                        // Force reflow to get accurate table height
                        existingEl.style.display = 'block';
                        existingEl.offsetHeight; // Force reflow
                        existingHeight = existingEl.offsetHeight;
                        existingEl.style.display = '';
                    }

                    // If table still has very small height, estimate based on content
                    if (existingHeight < 50) {
                        const table = existingEl.querySelector('table');
                        if (table) {
                            const rowCount = table.querySelectorAll('tr').length;
                            existingHeight = Math.max(80, rowCount * 35); // Estimate 35px per row + minimum 80px
                        } else {
                            // Check if table has content but no table element yet
                            if (existingEl.innerHTML.trim() !== '') {
                                existingHeight = 150; // Content present but no table structure
                            } else {
                                existingHeight = 100; // Empty table
                            }
                        }
                    }
                }

                // Debug: Log table height calculation
                console.log(`Table height calculation for element at top=${existingTop}: final height=${existingHeight}`);
            } else {
                // For other elements, use the styled height or default
                const styledHeight = parseInt(existingEl.style.height);
                existingHeight = styledHeight || existingEl.offsetHeight || 150;
            }

            // Check if the current element fits before this existing element
            let currentElementHeight;
            if (elementHeight === 'auto') {
                // For auto height elements (like tables), estimate height based on typical content
                currentElementHeight = 120; // Reasonable estimate for new table
            } else {
                currentElementHeight = elementHeight;
            }

            if (nextY + currentElementHeight + elementSpacing <= existingTop) {
                break; // Found a gap
            }

            // Move to the next position after this element with no spacing
            nextY = existingTop + existingHeight + elementSpacing;
        }

        // Ensure the element doesn't go beyond canvas bounds - expand canvas instead
        let currentElementHeight;
        if (elementHeight === 'auto') {
            currentElementHeight = 120; // Default estimate for auto elements
        } else {
            currentElementHeight = elementHeight;
        }

        // Calculate where the element would end
        const elementBottom = nextY + currentElementHeight;

        // Expand canvas if needed instead of restricting element placement
        this.expandCanvasIfNeeded(elementBottom);

        // Debug: Log final calculation
        console.log(`Final position calculation: y=${nextY}, elementHeight=${currentElementHeight}, elementBottom=${elementBottom}`);

        return {
            x: centerX,
            y: Math.max(startY, nextY),
            width: fullWidth
        };
    }

    repositionElementsBelow(elementId) {
        const changedElement = document.getElementById(elementId);
        if (!changedElement) return;

        const changedTop = parseInt(changedElement.style.top);
        const changedHeight = this.getElementStackHeight(changedElement);
        const changedBottom = changedTop + changedHeight;

        // Get all elements sorted by their top position
        const allElements = Array.from(this.canvas.querySelectorAll('.canvas-element'))
            .filter(el => el.id !== elementId && !el.id.includes('boardLabel'))
            .sort((a, b) => parseInt(a.style.top) - parseInt(b.style.top));

        // Find elements that need to be repositioned (those below the changed element)
        const elementsBelow = allElements.filter(el => {
            const elementTop = parseInt(el.style.top);
            return elementTop >= changedTop;
        });

        // Reposition elements below
        let nextY = changedBottom;
        const elementSpacing = 0; // No spacing between elements

        elementsBelow.forEach(element => {
            const currentTop = parseInt(element.style.top);
            let elementHeight;

            // Get actual height of element
            if (element.classList.contains('table-element')) {
                if (element.classList.contains('editor-table--collapsed')) {
                    elementHeight = 28;
                } else {
                    elementHeight = element.offsetHeight;
                    if (elementHeight < 50) {
                        elementHeight = 100; // Default for empty tables
                    }
                }
            } else {
                elementHeight = parseInt(element.style.height) || element.offsetHeight || 150;
            }

            // Only reposition if this element was actually below
            if (currentTop >= changedTop) {
                element.style.top = nextY + 'px';
                nextY += elementHeight + elementSpacing;
            }
        });

        // Expand canvas if needed after repositioning
        this.expandCanvasIfNeeded(nextY);
    }

    addElementToCanvas(toolId) {
        const elementId = `element_${this.elementIdCounter++}`;
        const element = document.createElement('div');
        element.id = elementId;
        element.className = 'canvas-element';
        element.dataset.toolId = toolId;

        // Get canvas dimensions
        const canvasRect = this.canvas.getBoundingClientRect();
        const maxCanvasWidth = this.getMaxCanvasWidth();
        const maxCanvasHeight = this.getMaxCanvasHeight();

        // All elements now occupy actual canvas width without margins
        let defaultHeight;
        if (toolId === 'moveHintsTable') {
            // Table elements have auto height
            defaultHeight = 'auto';
        } else {
            // Other elements have fixed height based on mobile/desktop
            defaultHeight = this.isMobile() ? Math.min(80, maxCanvasHeight - 40) : 150;
        }

        // For non-table elements, add a small delay to ensure any existing tables have rendered
        const calculatePosition = () => {
            // Debug: Log existing elements before positioning
            if (toolId !== 'moveHintsTable') {
                console.log('=== ELEMENT POSITIONING DEBUG ===');
                const existingElements = this.canvas.querySelectorAll('.canvas-element');
                console.log('Existing elements count:', existingElements.length);
                existingElements.forEach((el, index) => {
                    console.log(`Element ${index}: top=${el.style.top}, height=${el.offsetHeight}, class=${el.className}`);
                });
            }

            // Position elements in vertical blocks with actual canvas width
            const position = this.calculateVerticalPosition(canvasRect.width, defaultHeight);

            // Debug: Log calculated position
            if (toolId !== 'moveHintsTable') {
                console.log(`Calculated position for ${toolId}:`, position);
            }

            element.style.left = position.x + 'px';
            element.style.top = position.y + 'px';

            // Set width to actual canvas width without margins and height
            element.style.width = position.width + 'px';

            if (defaultHeight === 'auto') {
                element.style.height = 'auto';
            } else {
                element.style.height = defaultHeight + 'px';
            }

            // Добавляем контент в элемент
            this.populateElementContent(element, toolId);

            // Добавляем контролы
            this.addElementControls(element);
            this.attachBlockReorderInteractions(element);

            // Добавляем на холст
            this.getCanvasElementsRoot().appendChild(element);

            // Expand canvas if needed for the new element
            setTimeout(() => {
                const elementBottom = parseInt(element.style.top) + element.offsetHeight;
                this.expandCanvasIfNeeded(elementBottom);
            }, 100);

            // Debug: Log final position for non-table elements
            if (toolId !== 'moveHintsTable') {
                setTimeout(() => {
                    console.log(`Final ${toolId} position:`, {
                        top: element.style.top,
                        height: element.offsetHeight,
                        offsetTop: element.offsetTop
                    });
                }, 100);
            }

            // Сохраняем в массив элементов
            this.elements.push({
                id: elementId,
                toolId: toolId,
                element: element
            });

            // Выделяем элемент
            this.selectElement(element);
        };

        if (toolId === 'moveHintsTable') {
            // For tables, calculate position immediately
            calculatePosition();
        } else {
            // For other elements, add a small delay to ensure tables are rendered
            setTimeout(calculatePosition, 50);
        }
    }

    populateElementContent(element, toolId) {
        // Очищаем элемент и убираем все кешированные данные
        element.innerHTML = '';
        element.removeAttribute('data-cached');

        // Add cache-busting timestamp
        const timestamp = Date.now();
        element.setAttribute('data-content-timestamp', timestamp);

        switch (toolId) {
            case 'boardCanvas':
                // Доска с параметрами - временно отключена
                element.innerHTML = `
                    <div style="padding: 20px; text-align: center; color: #666;">
                        <strong>Доска с параметрами</strong><br>
                        <small>Функционал временно отключен</small>
                    </div>
                `;
                break;

            case 'question-text': {
                element.innerHTML = `
                    <div class="text-content" contenteditable="true" placeholder="Введите текст вопроса...">Текст вопроса</div>
                `;
                element.classList.add('text-element');
                element.style.backgroundColor = 'transparent';
                const qtc = element.querySelector('.text-content');
                if (qtc) this.applyGlobalTextStyleDefaultsToTextNode(qtc);
                this.setupTextEditing(element);
                break;
            }

            case 'moveHintsTable':
                // Таблица - создаем на основе сохраненных данных
                this.createTableElement(element);
                break;

            case 'board-illustration':
                // Иллюстрация (изображение доски)
                const canvasForImage = document.getElementById('boardCanvas');
                if (canvasForImage) {
                    // Создаем изображение из canvas с cache-busting
                    const img = document.createElement('img');
                    img.src = canvasForImage.toDataURL() + '?t=' + timestamp;

                    // Apply mobile width constraints
                    const maxWidth = this.getMaxCanvasWidth();
                    img.style.maxWidth = maxWidth + 'px';
                    img.style.width = '100%';
                    img.style.height = 'auto';
                    img.style.objectFit = 'contain';
                    img.setAttribute('data-image-timestamp', timestamp);
                    element.appendChild(img);
                } else {
                    element.innerHTML = `
                        <div style="padding: 20px; text-align: center; color: #666;">
                            <strong>Изображение недоступно</strong><br>
                            <small>Доска не найдена для создания иллюстрации</small>
                        </div>
                    `;
                }
                break;

            case 'answer-text': {
                element.innerHTML = `
                    <div class="text-content" contenteditable="true" placeholder="Введите текст ответа...">Текст ответа</div>
                `;
                element.classList.add('text-element');
                element.style.backgroundColor = 'transparent';
                const atc = element.querySelector('.text-content');
                if (atc) this.applyGlobalTextStyleDefaultsToTextNode(atc);
                this.setupTextEditing(element);
                break;
            }

            case 'support-link': {
                element.innerHTML = `
                    <div class="link-content">
                        <div class="link-text" contenteditable="true" placeholder="Текст и выделенная ссылка…">Текст: ссылка</div>
                        <input type="hidden" class="link-url" value="">
                    </div>
                `;
                element.classList.add('link-element');
                element.style.backgroundColor = 'transparent';
                const ltx = element.querySelector('.link-text');
                if (ltx) this.applyGlobalTextStyleDefaultsToTextNode(ltx);
                this.setupLinkEditing(element);
                break;
            }

            default:
                element.innerHTML = `
                    <div style=" text-align: center; color: #666;">
                        <strong>${toolId}</strong><br>
                        <small>Неизвестный тип элемента</small>
                    </div>
                `;
        }
    }

    /** Обрезка хвостовой пунктуации у распознанного URL для корректного href. */
    normalizeHrefFromRecognizedUrl(raw) {
        let u = String(raw || '').trim().replace(/[.,;:!?)]+$/g, '');
        if (/^www\./i.test(u)) u = `https://${u}`;
        return u;
    }

    _linkifySingleTextNodeIfUrl(textNode) {
        const text = textNode.textContent;
        if (!text) return;
        const re = /(https?:\/\/[^\s<>"']+|tg:\/\/[^\s<>"']+|www\.[^\s<>"']+)/gi;
        const parts = [];
        let last = 0;
        let m;
        re.lastIndex = 0;
        while ((m = re.exec(text)) !== null) {
            if (m.index > last) parts.push({ t: 'text', v: text.slice(last, m.index) });
            parts.push({ t: 'link', v: m[0] });
            last = m.index + m[0].length;
        }
        if (!parts.some((p) => p.t === 'link')) return;
        if (last < text.length) parts.push({ t: 'text', v: text.slice(last) });

        const parent = textNode.parentNode;
        if (!parent) return;
        const frag = document.createDocumentFragment();
        for (const p of parts) {
            if (p.t === 'text') frag.appendChild(document.createTextNode(p.v));
            else {
                const href = this.normalizeHrefFromRecognizedUrl(p.v);
                if (!href) continue;
                const a = document.createElement('a');
                a.href = href;
                a.textContent = p.v;
                a.target = '_blank';
                a.rel = 'noopener noreferrer';
                frag.appendChild(a);
            }
        }
        while (frag.firstChild) parent.insertBefore(frag.firstChild, textNode);
        parent.removeChild(textNode);
    }

    /**
     * В contenteditable .link-text оборачивает «голые» URL (http(s), tg://, www…) в <a>.
     * Не трогает текст уже внутри существующих <a>.
     */
    linkifyPlainUrlsInLinkTextRoot(root) {
        if (!root) return;
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
        const textNodes = [];
        let n;
        while ((n = walker.nextNode())) {
            if (!n.textContent) continue;
            let el = n.parentElement;
            let underAnchor = false;
            while (el && el !== root) {
                if (el.tagName === 'A') {
                    underAnchor = true;
                    break;
                }
                el = el.parentElement;
            }
            if (!underAnchor) textNodes.push(n);
        }
        for (let i = textNodes.length - 1; i >= 0; i--) {
            this._linkifySingleTextNodeIfUrl(textNodes[i]);
        }
    }

    linkifyPlainUrlsUnderLinkElement(element) {
        const linkText = element.querySelector('.link-text');
        const linkUrl = element.querySelector('.link-url');
        if (!linkText || !linkUrl) return;
        this.linkifyPlainUrlsInLinkTextRoot(linkText);
        this._normalizeAnchorsInLinkTextRoot(linkText);
        const first = linkText.querySelector('a[href]');
        if (first) {
            const href = first.getAttribute('href');
            if (href && !String(linkUrl.value || '').trim()) {
                linkUrl.value = href;
                const prop = document.getElementById('propLinkUrl');
                if (prop && this.selectedElement === element) prop.value = href;
            }
        }
    }

    setupLinkEditing(element) {
        const linkText = element.querySelector('.link-text');
        const linkUrl = element.querySelector('.link-url');
        if (!linkText || !linkUrl) return;
        this.autoGrowTextElementContainer(element);

        let linkifyDebounce = null;
        const scheduleLinkify = () => {
            clearTimeout(linkifyDebounce);
            linkifyDebounce = setTimeout(() => {
                linkifyDebounce = null;
                this.linkifyPlainUrlsUnderLinkElement(element);
            }, 180);
        };

        // Предотвращаем всплытие события клика, чтобы не выделять элемент при редактировании ссылки
        linkText.addEventListener('mousedown', (e) => {
            e.stopPropagation();
            if (e.target === linkText) {
                linkText.focus();
            }
        });

        // Добавляем обработчик фокуса для открытия свойств
        linkText.addEventListener('focus', () => {
            this.selectElement(element);
        });

        // Обработка окончания редактирования и сохранение выделения
        linkText.addEventListener('blur', () => {
            clearTimeout(linkifyDebounce);
            this.linkifyPlainUrlsUnderLinkElement(element);
            this._normalizeAnchorsInLinkTextRoot(linkText);
            this.saveSelectionForEditable(linkText);
            if (linkText.textContent.trim() === '') {
                linkText.textContent = 'Текст и ссылка';
            }
            this.autoGrowTextElementContainer(element);
        });

        linkText.addEventListener('input', () => {
            scheduleLinkify();
            this.autoGrowTextElementContainer(element);
        });
        linkText.addEventListener('paste', () => {
            requestAnimationFrame(() => {
                this.linkifyPlainUrlsUnderLinkElement(element);
                this.autoGrowTextElementContainer(element);
            });
        });

        // Обработка клика по ссылке для перехода (только если не в режиме редактирования)
        element.addEventListener('click', (e) => {
            const anchor = e.target.closest('a[href]');
            if (anchor && linkText.contains(anchor)) {
                if (document.activeElement === linkText) return;
                let href = anchor.getAttribute('href');
                if (href) {
                    href = href.trim();
                    if (href && !/^\s*javascript:/i.test(href)) {
                        e.preventDefault();
                        e.stopPropagation();
                        window.open(href, '_blank', 'noopener,noreferrer');
                    }
                }
            }
        });

        // Обработка клавиш
        linkText.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                linkText.blur();
            } else if (e.key === 'Enter') {
                if (e.shiftKey) {
                    // Shift+Enter - разрешаем перенос
                    return;
                } else {
                    // Обычный Enter - завершаем редактирование
                    e.preventDefault();
                    linkText.blur();
                }
            }
        });
    }

    /**
     * Предпросмотр карточки: открытие URL из поля ссылки и диплинков внутри HTML текста (tg:// и т.д.).
     * В режиме предпросмотра setupLinkEditing не вызывается — события до блока не доходили из‑за pointer-events.
     */
    attachPreviewLinkNavigation(element) {
        const linkUrl = element.querySelector('.link-url');
        const linkText = element.querySelector('.link-text');
        if (!linkUrl) return;
        element.addEventListener('click', (e) => {
            const anchor = e.target.closest('a[href]');
            if (anchor && linkText && linkText.contains(anchor)) {
                let href = anchor.getAttribute('href');
                if (href) {
                    href = href.trim();
                    if (href && !/^\s*javascript:/i.test(href)) {
                        e.preventDefault();
                        e.stopPropagation();
                        try {
                            window.open(href, '_blank', 'noopener,noreferrer');
                        } catch (err) {
                            window.location.assign(href);
                        }
                    }
                }
                return;
            }
            const hasInline = linkText && linkText.querySelector('a[href]');
            if (hasInline) {
                return;
            }
            const url = (linkUrl.value || '').trim();
            if (!url) return;
            e.preventDefault();
            e.stopPropagation();
            try {
                window.open(url, '_blank', 'noopener,noreferrer');
            } catch (err) {
                window.location.assign(url);
            }
        });
    }

    setupTextEditing(element) {
        return setupTextEditingImpl(this, element);
    }

    autoGrowTextElementContainer(element, options = {}) {
        return autoGrowTextElementContainerImpl(this, element, options);
    }

    addElementControls(element) {
        // Ручной ресайз текстовых блоков отключён: высота управляется авто-ростом по контенту.
        return;
    }

    beginTextBlockHeightDrag(element, startClientY) {
        return beginTextBlockHeightDragImpl(this, element, startClientY);
    }

    // --- Word-like: сохранение/восстановление выделения и форматирование по выделению ---

    getCharacterOffset(container, targetNode, targetOffset) {
        let offset = 0;
        const walk = (node) => {
            if (node.nodeType === Node.TEXT_NODE) {
                if (node === targetNode) {
                    offset += targetOffset;
                    return true;
                }
                offset += node.length;
                return false;
            }
            for (let i = 0; i < node.childNodes.length; i++) {
                if (walk(node.childNodes[i])) return true;
            }
            return false;
        };
        walk(container);
        return offset;
    }

    setSelectionByCharacterOffset(editable, start, end) {
        let cur = 0;
        let startNode = null, startOffset = 0, endNode = null, endOffset = 0;
        const walk = (node) => {
            if (node.nodeType === Node.TEXT_NODE) {
                const len = node.length;
                if (cur <= start && start < cur + len) {
                    startNode = node;
                    startOffset = start - cur;
                }
                if (cur <= end && end <= cur + len) {
                    endNode = node;
                    endOffset = end - cur;
                }
                cur += len;
                return;
            }
            for (let i = 0; i < node.childNodes.length; i++) {
                walk(node.childNodes[i]);
                if (endNode) return;
            }
        };
        walk(editable);
        if (!startNode) startNode = editable.firstChild || editable, startOffset = 0;
        if (!endNode) endNode = editable.firstChild || editable, endOffset = endNode.nodeType === Node.TEXT_NODE ? endNode.length : 0;
        const sel = window.getSelection();
        const range = document.createRange();
        range.setStart(startNode, startOffset);
        range.setEnd(endNode, endOffset);
        sel.removeAllRanges();
        sel.addRange(range);
    }

    saveSelectionForEditable(editableEl) {
        const sel = window.getSelection();
        if (!sel.rangeCount || !editableEl.contains(sel.anchorNode)) return;
        const range = sel.getRangeAt(0);
        if (!editableEl.contains(range.commonAncestorContainer)) return;
        const start = this.getCharacterOffset(editableEl, range.startContainer, range.startOffset);
        const end = this.getCharacterOffset(editableEl, range.endContainer, range.endOffset);
        this.savedSelection = { start, end };
        this.savedSelectionEditable = editableEl;
    }

    restoreSelectionForEditable(editableEl) {
        editableEl.focus();
        if (this.savedSelectionEditable === editableEl && this.savedSelection) {
            const { start, end } = this.savedSelection;
            this.setSelectionByCharacterOffset(editableEl, start, end);
        }
    }

    hasValidSelectionForFormat(editableEl) {
        if (this.savedSelectionEditable === editableEl && this.savedSelection) {
            const { start, end } = this.savedSelection;
            if (start !== end) return true;
        }
        const sel = window.getSelection();
        return sel.rangeCount && editableEl.contains(sel.anchorNode) && !sel.isCollapsed;
    }

    applyFormatToSelection(editableEl, execCommandName, value) {
        this.restoreSelectionForEditable(editableEl);
        const sel = window.getSelection();
        if (sel.isCollapsed) return;
        if (value !== undefined) {
            document.execCommand(execCommandName, false, value);
        } else {
            document.execCommand(execCommandName, false, null);
        }
    }

    /**
     * Блок «Ссылка»: скрытое поле link-url синхронизируется с полем свойств;
     * при applyToDom — createLink на выделение или обновление единственного <a>.
     */
    updateLinkBlockUrlFromProperties(value, applyToDom) {
        if (!this.selectedElement || !this.selectedElement.classList.contains('link-element')) {
            return;
        }
        const linkText = this.selectedElement.querySelector('.link-text');
        const linkUrlHidden = this.selectedElement.querySelector('.link-url');
        if (!linkText || !linkUrlHidden) return;
        const v = String(value != null ? value : '').trim();
        linkUrlHidden.value = v;
        if (!applyToDom || !v) {
            return;
        }
        linkText.focus();
        if (this.hasValidSelectionForFormat(linkText)) {
            this.restoreSelectionForEditable(linkText);
            document.execCommand('createLink', false, v);
        } else {
            const anchors = linkText.querySelectorAll('a[href]');
            if (anchors.length === 1) {
                anchors[0].setAttribute('href', v);
            }
        }
        this._normalizeAnchorsInLinkTextRoot(linkText);
        const prop = document.getElementById('propLinkUrl');
        if (prop && this.selectedElement) {
            prop.value = this._getLinkBlockUrlRaw(this.selectedElement);
        }
    }

    _normalizeAnchorsInLinkTextRoot(root) {
        if (!root) return;
        root.querySelectorAll('a[href]').forEach((a) => {
            a.target = '_blank';
            a.rel = 'noopener noreferrer';
        });
    }

    /** Сырой URL для поля свойств / синхронизации (первый <a> или скрытое поле). */
    _getLinkBlockUrlRaw(element) {
        const lt = element && element.querySelector('.link-text');
        const lu = element && element.querySelector('.link-url');
        const first = lt && lt.querySelector('a[href]');
        const fromA = first && first.getAttribute('href');
        return fromA ? String(fromA) : lu ? String(lu.value || '') : '';
    }

    /** URL для подстановки в HTML шаблон панели свойств. */
    _getLinkBlockUrlForProperties(element) {
        return this.escapeHtml(this._getLinkBlockUrlRaw(element));
    }

    applyStyleToSelection(editableEl, styleObj) {
        this.restoreSelectionForEditable(editableEl);
        const sel = window.getSelection();
        if (sel.isCollapsed || !sel.rangeCount) return;
        const range = sel.getRangeAt(0);
        const span = document.createElement('span');
        Object.assign(span.style, styleObj);
        try {
            range.surroundContents(span);
        } catch (e) {
            const fragment = range.extractContents();
            span.appendChild(fragment);
            range.insertNode(span);
        }
    }

    selectElement(element) {
        // Убираем выделение с предыдущего элемента
        document.querySelectorAll('.canvas-element').forEach(el => {
            el.classList.remove('selected');
        });

        // Выделяем новый элемент
        element.classList.add('selected');
        this.selectedElement = element;

        // Показываем свойства элемента
        this.showElementProperties(element);
    }

    clampNumericValue(value, min, max, fallback) {
        const n = parseInt(value, 10);
        if (Number.isNaN(n)) return fallback;
        return Math.max(min, Math.min(max, n));
    }

    renderNumericSelectOptions(min, max, current, step = 1, suffix = '') {
        const safeStep = Math.max(1, parseInt(step, 10) || 1);
        const safeCurrent = this.clampNumericValue(current, min, max, min);
        const opts = [];
        for (let v = min; v <= max; v += safeStep) {
            opts.push(
                `<option value="${v}" ${v === safeCurrent ? 'selected' : ''}>${v}${suffix}</option>`
            );
        }
        return opts.join('');
    }

    showElementProperties(element) {
        const computedStyle = window.getComputedStyle(element);

        // Get mobile-aware card dimensions
        const maxCanvasWidth = this.getMaxCanvasWidth();
        const maxCanvasHeight = this.getMaxCanvasHeight();
        const maxElementWidth = this.isMobile() ? maxCanvasWidth - 40 : 750;
        const maxElementHeight = this.isMobile() ? maxCanvasHeight - 40 : 600;

        // Check if this is a table element
        const isTableElement = element.classList.contains('table-element') || element.dataset.toolId === 'moveHintsTable';

        const textContentEl = element.querySelector('.text-content');
        const linkTextEl = element.querySelector('.link-text');
        const currentTextNode = textContentEl || linkTextEl;

        // Безопасно конвертируем вычисленные цвета в HEX, чтобы color input работал корректно
        const textColorValue = textContentEl
            ? this.rgbToHex(window.getComputedStyle(textContentEl).color || '#333333')
            : '#333333';
        const linkColorValue = linkTextEl
            ? this.rgbToHex(window.getComputedStyle(linkTextEl).color || '#333333')
            : '#333333';

        this.propertiesContent.innerHTML = `
            <div class="property-group">
                <h4>Стиль</h4>
                ${isTableElement ? `
                <div class="property-item">
                    <label>Тип таблицы:</label>
                    <select id="propTableType" onchange="contentEditor.updateElementProperty('tableType', this.value)">
                        <option value="hints" ${(element.dataset.tableType === 'hints' || !element.dataset.tableType) ? 'selected' : ''}>Таблица хода</option>
                        <option value="cube" ${element.dataset.tableType === 'cube' ? 'selected' : ''}>Таблица по кубу</option>
                    </select>
                </div>
                ` : ''}
                ${element.classList.contains('text-element') ? `
                <div class="property-item">
                    <label>Размер шрифта:</label>
                    <select id="propFontSize" onchange="contentEditor.updateElementProperty('fontSize', this.value + 'px')">
                        ${this.renderNumericSelectOptions(
                            10,
                            72,
                            parseInt(window.getComputedStyle(element.querySelector('.text-content')).fontSize) || 16,
                            1,
                            'px'
                        )}
                    </select>
                    <div class="property-value">${parseInt(window.getComputedStyle(element.querySelector('.text-content')).fontSize) || 16}px</div>
                </div>
                <div class="property-item">
                    <label>Цвет текста:</label>
                    <input type="color" id="propTextColor" value="${textColorValue}"
                           onchange="contentEditor.updateElementProperty('textColor', this.value)">
                </div>
                <div class="property-item">
                    <label>Выравнивание:</label>
                    <select id="propTextAlign" onchange="contentEditor.updateElementProperty('textAlign', this.value)">
                        <option value="left" ${window.getComputedStyle(element.querySelector('.text-content')).textAlign === 'left' ? 'selected' : ''}>Слева</option>
                        <option value="center" ${window.getComputedStyle(element.querySelector('.text-content')).textAlign === 'center' ? 'selected' : ''}>По центру</option>
                        <option value="right" ${window.getComputedStyle(element.querySelector('.text-content')).textAlign === 'right' ? 'selected' : ''}>Справа</option>
                        <option value="justify" ${window.getComputedStyle(element.querySelector('.text-content')).textAlign === 'justify' ? 'selected' : ''}>По ширине</option>
                    </select>
                </div>
                <div class="property-item">
                    <label>Межстрочный интервал:</label>
                    <select id="propLineHeight" onchange="contentEditor.updateElementProperty('lineHeight', this.value + 'px')">
                        ${this.renderNumericSelectOptions(
                            10,
                            30,
                            Math.round(parseFloat(window.getComputedStyle(element.querySelector('.text-content')).lineHeight) || 20),
                            1,
                            'px'
                        )}
                    </select>
                </div>
                <div class="property-item">
                    <label>Отступ внутри блока:</label>
                    <select id="propPadding" onchange="contentEditor.updateElementProperty('padding', this.value + 'px')">
                        ${this.renderNumericSelectOptions(
                            0,
                            40,
                            parseInt(window.getComputedStyle(element).padding) || 8,
                            1,
                            'px'
                        )}
                    </select>
                </div>
                <div class="property-item">
                    <label>Цвет фона блока:</label>
                    <div class="property-bg-color-row" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                        <input type="color" id="propBgColor" value="${this.getBlockBackgroundColorForInput(element)}"
                               oninput="contentEditor.updateElementProperty('backgroundColor', this.value)"
                               aria-label="Цвет фона блока">
                        <button type="button" class="action-btn" title="Убрать заливку, прозрачный фон"
                                onclick="contentEditor.updateElementProperty('clearBlockBackground')">Сбросить</button>
                    </div>
                </div>
                <div class="property-item">
                    <label>Форматирование:</label>
                    <div style="display:flex;gap:6px;">
                        <button class="action-btn" type="button" onclick="contentEditor.updateElementProperty('toggleBold')"><b>B</b></button>
                        <button class="action-btn" type="button" onclick="contentEditor.updateElementProperty('toggleItalic')"><i>I</i></button>
                        <button class="action-btn" type="button" onclick="contentEditor.updateElementProperty('toggleUnderline')"><u>U</u></button>
                    </div>
                </div>
                <div class="property-item property-item-text-presets">
                    <div class="text-style-presets-controls-row">
                        <select id="propTextStylePresetSelect" class="text-style-preset-select" title="Применить пресет текста"
                                onchange="contentEditor.applyTextStylePresetFromSelect(this.value)">
                            ${this.renderTextStylePresetSelectOptions()}
                        </select>
                        <button type="button" class="action-btn text-style-preset-save-btn" title="Сохранить текущий стиль как пресет"
                                onclick="contentEditor.openTextStylePresetSaveModal()">Сохранить</button>
                        <button type="button" class="action-btn text-style-preset-manage-btn" title="Просмотр и удаление пресетов"
                                onclick="contentEditor.openTextStylePresetManageModal()">Просмотр</button>
                    </div>
                </div>
                ` : ''}
                ${element.classList.contains('link-element') ? `
                <div class="property-item">
                    <label>Размер шрифта:</label>
                    <select id="propFontSize" onchange="contentEditor.updateElementProperty('fontSize', this.value + 'px')">
                        ${this.renderNumericSelectOptions(
                            10,
                            72,
                            parseInt(window.getComputedStyle(element.querySelector('.link-text')).fontSize) || 16,
                            1,
                            'px'
                        )}
                    </select>
                    <div class="property-value">${parseInt(window.getComputedStyle(element.querySelector('.link-text')).fontSize) || 16}px</div>
                </div>
                <div class="property-item">
                    <label>Цвет текста:</label>
                    <input type="color" id="propTextColor" value="${linkColorValue}"
                           onchange="contentEditor.updateElementProperty('textColor', this.value)">
                </div>
                <div class="property-item">
                    <label>Выравнивание:</label>
                    <select id="propTextAlign" onchange="contentEditor.updateElementProperty('textAlign', this.value)">
                        <option value="left" ${window.getComputedStyle(element.querySelector('.link-text')).textAlign === 'left' ? 'selected' : ''}>Слева</option>
                        <option value="center" ${window.getComputedStyle(element.querySelector('.link-text')).textAlign === 'center' ? 'selected' : ''}>По центру</option>
                        <option value="right" ${window.getComputedStyle(element.querySelector('.link-text')).textAlign === 'right' ? 'selected' : ''}>Справа</option>
                    </select>
                </div>
                <div class="property-item">
                    <label>URL ссылки:</label>
                    <input type="url" id="propLinkUrl" value="${this._getLinkBlockUrlForProperties(element)}" 
                           placeholder="https://example.com"
                           oninput="contentEditor.updateLinkBlockUrlFromProperties(this.value, false)"
                           onchange="contentEditor.updateLinkBlockUrlFromProperties(this.value, true)"
                           onkeydown="if(event.key==='Enter'){ event.preventDefault(); this.blur(); }">
                    <p class="property-hint ce-link-url-hint">Выделите в блоке слова или фразу, введите адрес и нажмите Enter или уйдите с поля — ссылка появится только на выделении. Если в блоке одна ссылка, URL обновит её.</p>
                </div>
                ` : ''}
                ${element.classList.contains('audio-element') ? `
                <div class="property-item">
                    <label>Заголовок:</label>
                    <input type="text" id="propAudioName" value="${this.escapeHtml(this._audioElementDisplayTitle(element))}" 
                           oninput="contentEditor.updateElementProperty('audioTitle', this.value)">
                </div>
                <div class="property-item property-item-audio-controls">
                    <div class="audio-controls-compact-row">
                        <button type="button" class="action-btn audio-compact-btn" aria-label="Воспроизвести" title="Воспроизвести"
                                onclick="contentEditor.playAudioElement('${element.id}')">▶</button>
                        <button type="button" class="action-btn audio-compact-btn" aria-label="Пауза" title="Пауза"
                                onclick="contentEditor.pauseAudioElement('${element.id}')">⏸</button>
                        <select id="propAudioVolume" class="audio-volume-compact-select" aria-label="Громкость"
                                title="Громкость" onchange="contentEditor.updateElementProperty('audioVolume', this.value / 100)">
                        ${this.renderNumericSelectOptions(0, 100, 100, 5, '%')}
                        </select>
                    </div>
                </div>
                ` : ''}
                ${element.dataset.toolId === 'attach-file' ? `
                <div class="property-item">
                    <label>Имя для отображения:</label>
                    <input type="text" id="propAttachFileName" value="${this.escapeHtml(element.dataset.attachmentFileName || '')}" 
                           placeholder="Имя файла"
                           oninput="contentEditor.updateElementProperty('attachFileDisplayName', this.value)">
                </div>
                ` : ''}
            </div>
            
            <div class="action-buttons">
                <button class="action-btn danger" onclick="contentEditor.deleteElement('${element.id}')" title="Удалить элемент" aria-label="Удалить элемент">
                    <i class="fa fa-trash" aria-hidden="true" style="font-size: 14px; width: 14px;"></i>
                </button>
                ${this.getPropertiesFrameActionsInnerHtml()}
            </div>
        `;
        if (element.classList.contains('text-element')) {
            this.syncTextStylePresetDropdown();
            void this.refreshTextStylePresetsList();
        }
    }

    updateElementProperty(property, value) {
        if (!this.selectedElement) return;

        switch (property) {
            case 'attachFileDisplayName':
                this.selectedElement.dataset.attachmentFileName = value;
                {
                    const nm = this.selectedElement.querySelector('.ce-attach-file-name');
                    if (nm) nm.textContent = value.trim() ? value : 'Файл';
                }
                break;
            case 'audioTitle':
                this.selectedElement.dataset.audioTitle = value;
                {
                    const audioNameEl = this.selectedElement.querySelector('.audio-name');
                    if (audioNameEl) {
                        audioNameEl.textContent = this._audioElementDisplayTitle(this.selectedElement);
                    }
                }
                break;
            case 'audioVolume':
                const audio = this.selectedElement.querySelector('audio');
                if (audio) {
                    audio.volume = value;
                }
                break;
            case 'fontSize': {
                const textEl = this.selectedElement.querySelector('.text-content, .link-text');
                if (!textEl) break;
                if (this.hasValidSelectionForFormat(textEl)) {
                    this.applyStyleToSelection(textEl, { fontSize: value });
                } else {
                    textEl.style.fontSize = value;
                }
                const fontSizeSelect = document.getElementById('propFontSize');
                if (fontSizeSelect) {
                    const n = parseInt(String(value), 10);
                    if (Number.isFinite(n)) {
                        fontSizeSelect.value = String(n);
                    }
                }
                const fontSizeDisplay = document.querySelector('#propFontSize + .property-value');
                if (fontSizeDisplay) fontSizeDisplay.textContent = value;
                this.autoGrowTextElementContainer(this.selectedElement);
                break;
            }
            case 'textColor': {
                const textEl = this.selectedElement.querySelector('.text-content, .link-text');
                if (!textEl) break;
                if (this.hasValidSelectionForFormat(textEl)) {
                    this.applyFormatToSelection(textEl, 'foreColor', value);
                } else {
                    textEl.style.color = value;
                }
                break;
            }
            case 'linkUrl':
                this.updateLinkBlockUrlFromProperties(value, false);
                break;
            case 'tableType':
                this.selectedElement.dataset.tableType = value;
                this.updateTableContent(this.selectedElement, value);
                break;
            case 'textAlign': {
                const el = this.selectedElement.querySelector('.text-content, .link-text');
                if (el) {
                    el.style.textAlign = value;
                }
                break;
            }
            case 'lineHeight': {
                const el = this.selectedElement.querySelector('.text-content, .link-text');
                if (el) {
                    el.style.lineHeight = value;
                    this.autoGrowTextElementContainer(this.selectedElement);
                }
                break;
            }
            case 'padding': {
                this.selectedElement.style.padding = value;
                this.autoGrowTextElementContainer(this.selectedElement);
                break;
            }
            case 'backgroundColor': {
                this.selectedElement.style.backgroundColor = value;
                const bgColorInput = document.getElementById('propBgColor');
                if (bgColorInput) {
                    bgColorInput.value = this.getBlockBackgroundColorForInput(this.selectedElement);
                }
                break;
            }
            case 'clearBlockBackground': {
                this.selectedElement.style.backgroundColor = 'transparent';
                const bgColorInputClear = document.getElementById('propBgColor');
                if (bgColorInputClear) {
                    bgColorInputClear.value = this.getBlockBackgroundColorForInput(this.selectedElement);
                }
                break;
            }
            case 'toggleBold': {
                const el = this.selectedElement.querySelector('.text-content, .link-text');
                if (el) {
                    if (this.hasValidSelectionForFormat(el)) {
                        this.applyFormatToSelection(el, 'bold');
                    } else {
                        el.style.fontWeight = el.style.fontWeight === 'bold' ? 'normal' : 'bold';
                    }
                }
                break;
            }
            case 'toggleItalic': {
                const el = this.selectedElement.querySelector('.text-content, .link-text');
                if (el) {
                    if (this.hasValidSelectionForFormat(el)) {
                        this.applyFormatToSelection(el, 'italic');
                    } else {
                        el.style.fontStyle = el.style.fontStyle === 'italic' ? 'normal' : 'italic';
                    }
                }
                break;
            }
            case 'toggleUnderline': {
                const el = this.selectedElement.querySelector('.text-content, .link-text');
                if (el) {
                    if (this.hasValidSelectionForFormat(el)) {
                        this.applyFormatToSelection(el, 'underline');
                    } else {
                        const dec = el.style.textDecorationLine || el.style.textDecoration;
                        const hasUnderline = dec && dec.includes('underline');
                        el.style.textDecoration = hasUnderline ? 'none' : 'underline';
                    }
                }
                break;
            }
        }
    }

    playAudioElement(elementId) {
        const element = document.getElementById(elementId);
        if (element && element.classList.contains('audio-element')) {
            const audio = element.querySelector('audio');
            const playBtn = element.querySelector('.audio-play-btn');

            if (audio) {
                audio.play();
                if (playBtn) {
                    playBtn.textContent = '⏸';
                }
            }
        }
    }

    pauseAudioElement(elementId) {
        const element = document.getElementById(elementId);
        if (element && element.classList.contains('audio-element')) {
            const audio = element.querySelector('audio');
            const playBtn = element.querySelector('.audio-play-btn');

            if (audio) {
                audio.pause();
                if (playBtn) {
                    playBtn.textContent = '▶';
                }
            }
        }
    }

    // Умный перенос текста (без автоматического изменения высоты)
    applySmartTextWrapping(element) {
        const textContent = element.querySelector('.text-content');
        if (!textContent) return;

        // Проверяем, является ли элемент текстовым
        if (!element.classList.contains('text-element')) return;

        // Только обеспечиваем правильный перенос текста
        // Высота элемента управляется вручную через панель свойств

        // Ничего не делаем - перенос уже работает через CSS
        // Автоматическое изменение высоты отключено
    }

    duplicateElement(elementId) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const newElement = element.cloneNode(true);
        const newId = `element_${this.elementIdCounter++}`;
        newElement.id = newId;
        delete newElement.dataset.ceBlockReorderBound;

        // Get appropriate dimensions for positioning - all elements now use actual canvas width
        let elementHeight;
        if (element.classList.contains('table-element')) {
            // For table elements, use actual dimensions
            elementHeight = element.offsetHeight;
        } else if (element.dataset.toolId === 'upload-image') {
            // For uploaded images, recalculate smart height based on current canvas width
            const img = element.querySelector('img');
            if (img && img.naturalWidth && img.naturalHeight) {
                const canvasRect = this.canvas.getBoundingClientRect();
                elementHeight = this.getResponsiveUploadImageHeight(canvasRect.width, img.naturalWidth, img.naturalHeight) || 200;
            } else {
                elementHeight = parseInt(element.style.height) || 200;
            }
        } else if (element.dataset.toolId === 'attach-file') {
            elementHeight = parseInt(element.style.height, 10) || 72;
        } else {
            // For other elements, use styled height or default
            elementHeight = parseInt(element.style.height) || 150;
        }

        // Get actual canvas width for proper mobile scaling
        const canvasRect = this.canvas.getBoundingClientRect();

        // Use new logic for positioning with actual canvas width
        const position = this.calculateVerticalPosition(canvasRect.width, elementHeight);

        newElement.style.left = position.x + 'px';
        newElement.style.top = position.y + 'px';
        newElement.style.width = position.width + 'px';

        // Обновляем контролы
        const controls = newElement.querySelector('.element-controls');
        if (controls) {
            controls.innerHTML = `
                <button class="control-btn" onclick="contentEditor.duplicateElement('${newId}')" title="Дублировать">📋</button>
                <button class="control-btn delete" onclick="contentEditor.deleteElement('${newId}')" title="Удалить">🗑️</button>
            `;
        }

        this.getCanvasElementsRoot().appendChild(newElement);
        this.addElementControls(newElement);
        this.attachBlockReorderInteractions(newElement);
        this.elements.push({
            id: newId,
            toolId: element.dataset.toolId,
            element: newElement
        });

        this.selectElement(newElement);
    }

    deleteElement(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            // Get position of deleted element before removing
            const deletedTop = parseInt(element.style.top);
            const deletedHeight = element.offsetHeight;

            // Remove the element
            element.remove();
            this.elements = this.elements.filter(el => el.id !== elementId);

            // Clear selection if deleted element was selected
            if (this.selectedElement && this.selectedElement.id === elementId) {
                this.selectedElement = null;
                this.applyPropertiesEmptyState();
            }

            // Move elements below the deleted element up
            this.moveElementsUpAfterDeletion(deletedTop, deletedHeight);

            // Adjust canvas height if needed
            this.adjustCanvasHeightAfterDeletion();
        }
    }

    moveElementsUpAfterDeletion(deletedTop, deletedHeight) {
        // Get all elements sorted by their top position
        const allElements = Array.from(this.canvas.querySelectorAll('.canvas-element'))
            .filter(el => !el.id.includes('boardLabel'))
            .sort((a, b) => parseInt(a.style.top) - parseInt(b.style.top));

        // Find elements that were below the deleted element and move them up
        allElements.forEach(element => {
            const elementTop = parseInt(element.style.top);

            // If this element was below the deleted element, move it up
            if (elementTop > deletedTop) {
                const newTop = elementTop - deletedHeight;
                element.style.top = Math.max(0, newTop) + 'px';
            }
        });
    }

    adjustCanvasHeightAfterDeletion() {
        // Высота канваса больше не подстраивается под элементы —
        // они скроллятся внутри фиксированной области.
    }


    setupEventListeners() {
        // Клик по холсту для снятия выделения
        this.canvas.addEventListener('click', (e) => {
            if (e.target === this.canvas) {
                this.deselectAll();
            }
        });

        // Handle window resize for mobile responsiveness
        window.addEventListener('resize', () => {
            this.handleWindowResize();
        });

        document.addEventListener('keydown', (e) => {
            if (e.key !== 'Escape') return;
            if (this.saveFrameConfirmModal && this.saveFrameConfirmModal.style.display === 'flex') {
                this.cancelSaveFrame();
                return;
            }
            const dupModal = document.getElementById('contentCardDuplicateSourceModal');
            if (dupModal && dupModal.style.display === 'flex') {
                this.closeContentCardDuplicateSourceModal();
                return;
            }
            if (this.textStylePresetManageModal && this.textStylePresetManageModal.style.display === 'flex') {
                this.closeTextStylePresetManageModal();
                return;
            }
            if (this.textStylePresetSaveModal && this.textStylePresetSaveModal.style.display === 'flex') {
                this.closeTextStylePresetSaveModal();
                return;
            }
            if (this.labelPresetsModal && this.labelPresetsModal.style.display === 'flex') {
                this.closeLabelPresetsModal();
                return;
            }
            if (this.cardLabelsModal && this.cardLabelsModal.style.display === 'flex') {
                this.cancelCardLabelsStep();
                return;
            }
            const imgLib = document.getElementById('imageLibraryModal');
            if (imgLib && imgLib.style.display === 'flex') {
                this.closeImageLibraryModal();
                return;
            }
            const imgSrc = document.getElementById('imageSourceModal');
            if (imgSrc && imgSrc.style.display === 'flex') {
                this.closeImageSourceModal();
                return;
            }
            if (this.cardPreviewModal && this.cardPreviewModal.style.display === 'flex') {
                this.closeCardPreviewModal();
            }
        });

        // Ресайз тулбаров и панели свойств / канваса
        this.initPanelResizers();
    }

    openSaveFrameConfirm() {
        if (!this.saveFrameConfirmModal) return;
        this.saveFrameConfirmModal.style.display = 'flex';
        this.saveFrameConfirmModal.setAttribute('aria-hidden', 'false');
    }

    cancelSaveFrame() {
        if (!this.saveFrameConfirmModal) return;
        this.saveFrameConfirmModal.style.display = 'none';
        this.saveFrameConfirmModal.setAttribute('aria-hidden', 'true');
    }

    sanitizeFrameIdForStorageKey(frameId) {
        return String(frameId).replace(/[^a-zA-Z0-9_-]/g, '_');
    }

    /** Следующий свободный индекс сохранения для данного кадра (0, 1, 2, …). */
    allocateNextSaveSlotIndex(frameId) {
        const safe = this.sanitizeFrameIdForStorageKey(frameId);
        const counterKey = `contentEditor_saveSlotNext_${safe}`;
        const next = parseInt(localStorage.getItem(counterKey) || '0', 10);
        localStorage.setItem(counterKey, String(next + 1));
        return next;
    }

    frameStorageKey(frameId, slotIndex) {
        return `contentEditor_frame_${this.sanitizeFrameIdForStorageKey(frameId)}_${slotIndex}`;
    }

    getFrameIdForSave() {
        const board = typeof window.getHintViewerBoardSnapshot === 'function'
            ? window.getHintViewerBoardSnapshot()
            : null;
        return (board && board.frameId) ? board.frameId : `editor_${Date.now()}`;
    }

    async confirmSaveFrame() {
        try {
            const frameId = this.getFrameIdForSave();
            const saveSlotIndex = this.allocateNextSaveSlotIndex(frameId);
            const payload = await this.buildFrameSavePayload(frameId, saveSlotIndex);
            await this.uploadPayloadMediaToS3(payload);
            const key = this.frameStorageKey(frameId, saveSlotIndex);
            localStorage.setItem(key, JSON.stringify(payload));
            this.showNotification(`Кадр сохранён №${saveSlotIndex + 1}`, 'success');
        } catch (err) {
            console.error('confirmSaveFrame:', err);
            this.showNotification('Не удалось сохранить: ' + (err.message || err), 'error');
            return;
        }
        this.cancelSaveFrame();
        this.resetEditorAfterSave();
    }

    async buildFrameSavePayload(frameId, saveSlotIndex) {
        if (
            !this.editorOpenedFromContentCardView &&
            !this.editorOpenedFromPreview &&
            typeof window.getHintViewerCurrentCardData === 'function'
        ) {
            this.syncCardDataFromHintViewerPage();
        }

        let board =
            typeof window.getHintViewerBoardSnapshot === 'function'
                ? window.getHintViewerBoardSnapshot()
                : null;
        if (board == null && this._editorSessionBoardSnapshot != null) {
            try {
                board = JSON.parse(JSON.stringify(this._editorSessionBoardSnapshot));
            } catch (e) {
                board = this._editorSessionBoardSnapshot;
            }
        }

        if (!this.toggleStates['boardCanvas']) {
            board = null;
        }

        let cardDataCopy = null;
        if (this.cardData) {
            try {
                cardDataCopy = JSON.parse(JSON.stringify(this.cardData));
            } catch (e) {
                cardDataCopy = null;
            }
        }

        return {
            version: 1,
            frameId,
            saveSlotIndex,
            savedAt: new Date().toISOString(),
            board,
            cardData: cardDataCopy,
            editor: {
                boardCanvasToggle: !!this.toggleStates['boardCanvas'],
                canvasBackground: this.getCanvasBackgroundForSave(),
                canvasBackgroundPattern: this.getCanvasBackgroundPatternForSave(),
                showBoardMatchBanner: !!this.boardMatchBannerEnabled,
            },
            elements: await this.serializeCanvasElementsForSave()
        };
    }

    /** Надёжное чтение фона канваса (inline или computed), чтобы корректно восстанавливать после сохранения */
    getCanvasBackgroundForSave() {
        return getCanvasBackgroundForSaveImpl(this);
    }

    /** Фон канваса из сохранённого payload (предпросмотр / восстановление) */
    resolveSavedCanvasBackground(payload) {
        return resolveSavedCanvasBackgroundImpl(this, payload);
    }

    getCanvasBackgroundPatternForSave() {
        return getCanvasBackgroundPatternForSaveImpl(this);
    }

    resolveSavedCanvasBackgroundPattern(payload) {
        return resolveSavedCanvasBackgroundPatternImpl(this, payload);
    }

    buildCanvasTilePatternCssUrl(pattern) {
        return buildCanvasTilePatternCssUrlImpl(this, pattern);
    }

    applyCanvasPatternConfig(pattern) {
        return applyCanvasPatternConfigImpl(this, pattern);
    }

    /** Стили обёртки .canvas-element (фон блока; padding — только если задан в панели свойств, не из computed) */
    collectBlockStyle(el) {
        const cs = window.getComputedStyle(el);
        const out = {};
        const bgInline = el.style.backgroundColor;
        if (bgInline && String(bgInline).trim()) {
            out.backgroundColor = bgInline;
        } else {
            const c = cs.backgroundColor;
            if (c && c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent') {
                out.backgroundColor = c;
            }
        }
        if (el.style.padding && String(el.style.padding).trim()) {
            out.padding = el.style.padding;
        }
        return Object.keys(out).length ? out : undefined;
    }

    /** Стили .text-content / .link-text (цвет текста, шрифт, выравнивание) */
    collectTextStyle(node) {
        const cs = window.getComputedStyle(node);
        const pick = (prop) => {
            const i = node.style[prop];
            return (i && String(i).trim()) ? i : cs[prop];
        };
        const td = pick('textDecoration');
        const out = {
            fontSize: pick('fontSize'),
            lineHeight: pick('lineHeight'),
            textAlign: pick('textAlign'),
            fontWeight: pick('fontWeight'),
            fontStyle: pick('fontStyle'),
            textDecoration: td && String(td).trim() ? td : cs.textDecoration,
            fontFamily: pick('fontFamily')
        };
        /* Цвет только если задан inline (панель свойств / глобальные стили текста).
           Иначе getComputedStyle мог унаследовать «чужой» цвет (например белый с родителя),
           и после сохранения текст переставал совпадать с видом в редакторе. */
        const inlineColor = node.style.color && String(node.style.color).trim();
        if (inlineColor) {
            out.color = inlineColor;
        }
        return out;
    }

    applyStyleSnapshot(domEl, snap) {
        if (!domEl || !snap || typeof snap !== 'object') return;
        Object.keys(snap).forEach((key) => {
            const v = snap[key];
            if (v != null && String(v).trim() !== '') {
                try {
                    domEl.style[key] = v;
                } catch (e) { /* ignore */ }
            }
        });
    }

    /** Имя БД совпадает с очисткой в clearContentEditorIndexedDB */
    static get CONTENT_EDITOR_MEDIA_DB() {
        return 'contentEditorMedia';
    }

    static get CONTENT_EDITOR_AUDIO_STORE() {
        return 'audio';
    }

    openContentEditorMediaDB() {
        if (this._contentEditorMediaDbPromise) return this._contentEditorMediaDbPromise;
        const dbName = ContentEditor.CONTENT_EDITOR_MEDIA_DB;
        this._contentEditorMediaDbPromise = new Promise((resolve, reject) => {
            if (typeof indexedDB === 'undefined') {
                this._contentEditorMediaDbPromise = null;
                reject(new Error('IndexedDB недоступен'));
                return;
            }
            const req = indexedDB.open(dbName, 1);
            req.onerror = () => {
                this._contentEditorMediaDbPromise = null;
                reject(req.error || new Error('IDB open failed'));
            };
            req.onsuccess = () => resolve(req.result);
            req.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains(ContentEditor.CONTENT_EDITOR_AUDIO_STORE)) {
                    db.createObjectStore(ContentEditor.CONTENT_EDITOR_AUDIO_STORE, { keyPath: 'id' });
                }
            };
        });
        return this._contentEditorMediaDbPromise;
    }

    generateAudioStorageId() {
        return `ceaud_${Date.now()}_${Math.random().toString(36).slice(2, 12)}`;
    }

    async putAudioBlobToIDB(id, blob) {
        const db = await this.openContentEditorMediaDB();
        const storeName = ContentEditor.CONTENT_EDITOR_AUDIO_STORE;
        return new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readwrite');
            tx.onerror = () => reject(tx.error || new Error('IDB write'));
            tx.oncomplete = () => resolve();
            tx.objectStore(storeName).put({ id, blob });
        });
    }

    async getAudioBlobFromIDB(id) {
        if (!id) return null;
        try {
            const db = await this.openContentEditorMediaDB();
            const storeName = ContentEditor.CONTENT_EDITOR_AUDIO_STORE;
            return new Promise((resolve, reject) => {
                const tx = db.transaction(storeName, 'readonly');
                const r = tx.objectStore(storeName).get(id);
                r.onerror = () => reject(r.error);
                r.onsuccess = () => {
                    const row = r.result;
                    resolve(row && row.blob instanceof Blob ? row.blob : null);
                };
            });
        } catch (e) {
            console.warn('getAudioBlobFromIDB:', e);
            return null;
        }
    }

    /**
     * Подставляет blob из IndexedDB и вешает плеер (data: URL не кладём в localStorage — квота).
     */
    async hydrateAudioElementFromIDB(element) {
        const id = element.dataset.audioStorageId;
        if (!id) return;
        const blob = await this.getAudioBlobFromIDB(id);
        if (!blob || !element.isConnected) return;
        const url = URL.createObjectURL(blob);
        element.dataset.audioUrl = url;
        this.setupAudioElement(element, url, null);
    }

    async serializeCanvasElementsForSave() {
        if (!this.canvas) return [];
        const out = [];
        const nodes = this.canvas.querySelectorAll('.canvas-element');
        for (const el of nodes) {
            const toolId = el.dataset.toolId || '';
            const item = {
                id: el.id,
                toolId,
                style: {
                    top: el.style.top,
                    left: el.style.left,
                    width: el.style.width,
                    height: el.style.height
                },
                dataset: { ...el.dataset }
            };
            delete item.dataset.ceBlockReorderBound;

            switch (toolId) {
                case 'question-text':
                case 'answer-text': {
                    const tc = el.querySelector('.text-content');
                    item.textHtml = tc ? this.editableInnerHtmlForSave(tc) : '';
                    break;
                }
                case 'support-link': {
                    const lt = el.querySelector('.link-text');
                    const lu = el.querySelector('.link-url');
                    item.linkTextHtml = lt ? this.editableInnerHtmlForSave(lt) : '';
                    item.linkUrl = lu ? lu.value : '';
                    break;
                }
                case 'moveHintsTable': {
                    const tbl = el.querySelector('table');
                    item.tableType = el.dataset.tableType || 'hints';
                    item.tableHtml = tbl ? tbl.outerHTML : this.elementInnerHtmlForSave(el);
                    break;
                }
                case 'upload-image': {
                    const s3k = el.dataset.imageS3Key || '';
                    if (s3k) {
                        item.imageS3Key = s3k;
                        if (el.dataset.imageContentType) {
                            item.imageContentType = el.dataset.imageContentType;
                        }
                        item.imageUrl = '';
                        delete item.dataset.imageUrl;
                    } else {
                        item.imageUrl = el.dataset.imageUrl || '';
                    }
                    break;
                }
                case 'audio-file': {
                    const applySerializedAudioTitle = () => {
                        const tit = (el.dataset.audioTitle && String(el.dataset.audioTitle).trim()) || '';
                        if (tit) item.audioTitle = tit;
                        else delete item.audioTitle;
                    };
                    const s3a = el.dataset.audioS3Key || '';
                    if (s3a) {
                        item.audioS3Key = s3a;
                        item.audioName = el.dataset.audioName || '';
                        item.audioUrl = '';
                        item.audioStorageId = '';
                        item.dataset.audioS3Key = s3a;
                        delete item.dataset.audioUrl;
                        delete item.dataset.audioStorageId;
                        applySerializedAudioTitle();
                        break;
                    }
                    const url = el.dataset.audioUrl || '';
                    let sid = el.dataset.audioStorageId || '';
                    if (url.startsWith('data:')) {
                        sid = sid || this.generateAudioStorageId();
                        const blob = await (await fetch(url)).blob();
                        await this.putAudioBlobToIDB(sid, blob);
                        el.dataset.audioStorageId = sid;
                        item.audioStorageId = sid;
                        item.audioName = el.dataset.audioName || '';
                        item.audioUrl = '';
                    } else if (url.startsWith('blob:')) {
                        if (!sid) {
                            try {
                                const blob = await (await fetch(url)).blob();
                                sid = this.generateAudioStorageId();
                                await this.putAudioBlobToIDB(sid, blob);
                                el.dataset.audioStorageId = sid;
                            } catch (err) {
                                console.warn('serializeCanvasElementsForSave audio blob:', err);
                            }
                        }
                        item.audioStorageId = sid || '';
                        item.audioName = el.dataset.audioName || '';
                        item.audioUrl = '';
                    } else if (/^https?:\/\//i.test(url)) {
                        item.audioUrl = url;
                        item.audioName = el.dataset.audioName || '';
                        item.audioStorageId = '';
                    } else {
                        item.audioStorageId = sid;
                        item.audioName = el.dataset.audioName || '';
                        item.audioUrl = url || '';
                    }
                    applySerializedAudioTitle();
                    delete item.dataset.audioUrl;
                    if (item.audioStorageId) item.dataset.audioStorageId = item.audioStorageId;
                    else delete item.dataset.audioStorageId;
                    break;
                }
                case 'attach-file': {
                    const ask = el.dataset.attachmentS3Key || '';
                    if (ask) {
                        item.attachmentS3Key = ask;
                        item.attachmentFileName = el.dataset.attachmentFileName || '';
                        item.attachmentContentType = el.dataset.attachmentContentType || '';
                    }
                    break;
                }
                case 'board-illustration': {
                    const s3b = el.dataset.boardImageS3Key || '';
                    const img = el.querySelector('img');
                    if (s3b) {
                        item.boardImageS3Key = s3b;
                        item.imageDataUrl = '';
                    } else {
                        item.imageDataUrl = img ? img.src : '';
                    }
                    break;
                }
                default:
                    item.innerHtml = this.elementInnerHtmlForSave(el);
            }

            const bs = this.collectBlockStyle(el);
            if (bs) item.blockStyle = bs;
            const textInner = el.querySelector('.text-content, .link-text');
            if (textInner) {
                item.textStyle = this.collectTextStyle(textInner);
            }

            out.push(item);
        }
        return out;
    }

    resetEditorAfterSave() {
        this.elements = [];
        if (this.canvas) {
            this.resetCanvasDomStructure();
            this.canvas.style.backgroundColor = '#ffffff';
            this.applyCanvasPatternConfig(null);
        }
        /* См. mergeLiveCanvasBackgroundIntoPreviewPayload: не затирать паттерн в превью пустым «живым» состоянием. */
        this._previewMergePreferStoredCanvasBg = true;
        this.selectedElement = null;
        this.applyPropertiesEmptyState();
        this.toggleStates = {};
        this._editorSessionBoardSnapshot = null;
        this._canvasPatternDraft = null;
        this.syncCardDataFromHintViewerPage();
        this.elementIdCounter = 0;
        this.loadTools();
        this.forceRefreshContent();
    }

    /**
     * Те же данные таблицы/кадра, что при входе из hint_viewer (data[current]).
     * Доска не хранится в редакторе — снимается через getHintViewerBoardSnapshot() при каждом сохранении.
     */
    syncCardDataFromHintViewerPage() {
        if (typeof window.getHintViewerCurrentCardData !== 'function') {
            this.cardData = null;
            return;
        }
        try {
            this.cardData = window.getHintViewerCurrentCardData();
        } catch (e) {
            console.warn('syncCardDataFromHintViewerPage:', e);
            this.cardData = null;
        }
    }

    getGameContextForCard() {
        const b = typeof window.getHintViewerBoardSnapshot === 'function'
            ? window.getHintViewerBoardSnapshot()
            : null;
        const gameId = (b && b.gameId) ? b.gameId : 'default';
        const gameNum = b && b.currentGameNum != null ? b.currentGameNum : null;
        return { gameId, gameNum, board: b };
    }

    getCardLabelsStorageKey() {
        const { gameId, gameNum } = this.getGameContextForCard();
        const g = gameNum != null ? `_g${gameNum}` : '';
        return `contentEditor_card_labels_${gameId}${g}`;
    }

    loadCardLabelsFromStorage() {
        try {
            const raw = localStorage.getItem(this.getCardLabelsStorageKey());
            if (!raw) return [];
            const arr = JSON.parse(raw);
            if (!Array.isArray(arr)) return [];
            const seen = new Set();
            const out = [];
            for (const x of arr) {
                if (typeof x !== 'string') continue;
                const t = x.trim().slice(0, 255);
                if (t && !seen.has(t)) {
                    seen.add(t);
                    out.push(t);
                }
            }
            return out;
        } catch (e) {
            console.warn('loadCardLabelsFromStorage:', e);
            return [];
        }
    }

    saveCardLabelsToStorage(labels) {
        const seen = new Set();
        const out = [];
        for (const x of Array.isArray(labels) ? labels : []) {
            if (typeof x !== 'string') continue;
            const t = x.trim().slice(0, 255);
            if (t && !seen.has(t)) {
                seen.add(t);
                out.push(t);
            }
        }
        localStorage.setItem(this.getCardLabelsStorageKey(), JSON.stringify(out));
    }

    /**
     * chat_id для API (глобальный chatId из hint_viewer или query-параметр).
     */
    getHintViewerChatIdForApi() {
        try {
            const w = typeof window !== 'undefined' ? window : undefined;
            const cid = w && (w.hintViewerChatId != null ? w.hintViewerChatId : w.chatId);
            if (cid != null && String(cid).length) {
                return String(cid);
            }
        } catch (e) {
            /* ignore */
        }
        try {
            return new URLSearchParams(window.location.search).get('chat_id') || '';
        } catch (e) {
            return '';
        }
    }

    buildContentCardFileNameForCloud() {
        const rawMat =
            typeof window !== 'undefined' && window.hintViewerMatFileName
                ? String(window.hintViewerMatFileName)
                : '';
        const normalized = rawMat.replace(/[\\/]/g, '_').trim();
        const { gameId: rawGid } = this.getGameContextForCard();
        const gameId = String(rawGid != null ? rawGid : 'default')
            .replace(/[\\/]/g, '_')
            .trim() || 'default';

        // Имена вроде source.mat с бэка — не уникальны; для карточки нужен стем gameId и реальное расширение (.mat)
        const PLACEHOLDER_STEMS = new Set(['source', 'file', 'game', 'card', 'default']);
        let stem = '';
        let ext = '.mat';
        if (normalized) {
            const dot = normalized.lastIndexOf('.');
            if (dot > 0 && dot < normalized.length - 1) {
                ext = normalized.slice(dot);
                if (ext.length > 16) {
                    ext = ext.slice(0, 16);
                }
                stem = normalized.slice(0, dot);
            } else {
                stem = normalized;
            }
        }
        if (!stem || PLACEHOLDER_STEMS.has(stem.toLowerCase())) {
            stem = gameId;
        }

        // Имя файла карточки в облаке: только стем + расширение (без _gN — совпадает с id матча/анализа)
        let base = `${stem}${ext}`;
        if (base.length > 255) {
            base = base.slice(0, 255);
        }
        return base;
    }

    async checkDuplicateSourceFileOnServer() {
        let initData = '';
        if (window.Telegram && window.Telegram.WebApp) {
            initData = window.Telegram.WebApp.initData || '';
        }
        if (!initData) {
            return { exists: false, content_card_id: null, file_name: '' };
        }
        const file_name = this.buildContentCardFileNameForCloud();
        const checkRes = await fetch('/api/content_cards/check_file_name', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ init_data: initData, file_name }),
        });
        let checkData = {};
        try {
            checkData = await checkRes.json();
        } catch (e) {
            checkData = {};
        }
        if (!checkRes.ok) {
            let msg = checkData.detail;
            if (Array.isArray(msg)) {
                msg = msg.map((x) => (x.msg || JSON.stringify(x))).join('; ');
            } else if (msg && typeof msg === 'object') {
                msg = JSON.stringify(msg);
            }
            throw new Error(msg || `Ошибка ${checkRes.status}`);
        }
        return {
            exists: !!checkData.exists,
            content_card_id: checkData.content_card_id != null ? checkData.content_card_id : null,
            file_name: file_name,
        };
    }

    async checkDuplicateBoardXgidOnServer(boardXgid) {
        let initData = '';
        if (window.Telegram && window.Telegram.WebApp) {
            initData = window.Telegram.WebApp.initData || '';
        }
        if (!initData) {
            return { exists: false, content_card_id: null };
        }
        const s = String(boardXgid || '').trim();
        if (!s) {
            return { exists: false, content_card_id: null };
        }
        const checkRes = await fetch('/api/content_cards/check_board_xgid', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ init_data: initData, board_xgid: s }),
        });
        let checkData = {};
        try {
            checkData = await checkRes.json();
        } catch (e) {
            checkData = {};
        }
        if (!checkRes.ok) {
            let msg = checkData.detail;
            if (Array.isArray(msg)) {
                msg = msg.map((x) => (x.msg || JSON.stringify(x))).join('; ');
            } else if (msg && typeof msg === 'object') {
                msg = JSON.stringify(msg);
            }
            throw new Error(msg || `Ошибка ${checkRes.status}`);
        }
        return {
            exists: !!checkData.exists,
            content_card_id: checkData.content_card_id != null ? checkData.content_card_id : null,
        };
    }

    /**
     * Проверка дубликата по строке позиции (XGID), как в колонке content_cards.board_xgid.
     * Для конструктора позиций (pokaz), где нет исходного .mat-файла.
     */
    async openModalWithDuplicateBoardXgidCheck(cardData) {
        if (!window || !window.Telegram || !window.Telegram.WebApp) {
            this.openModalWithData(cardData);
            return;
        }
        let boardXgid = '';
        try {
            if (typeof window.getHintViewerBoardSnapshot === 'function') {
                const snap = window.getHintViewerBoardSnapshot();
                if (snap && typeof snap.xgid === 'string') {
                    boardXgid = snap.xgid.trim();
                }
            }
        } catch (e) {
            console.warn('openModalWithDuplicateBoardXgidCheck:', e);
        }
        if (!boardXgid) {
            this.openModalWithData(cardData);
            return;
        }
        try {
            const dup = await this.checkDuplicateBoardXgidOnServer(boardXgid);
            if (dup && dup.exists) {
                this.openContentCardDuplicateSourceModal(
                    boardXgid,
                    dup.content_card_id,
                    () => this.openModalWithData(cardData),
                    'Всё равно открыть редактор',
                    'board_xgid'
                );
                return;
            }
        } catch (e) {
            console.error('openModalWithDuplicateBoardXgidCheck:', e);
            this.showNotification(
                e.message || 'Не удалось проверить, нет ли карточки с такой позицией',
                'error'
            );
            return;
        }
        this.openModalWithData(cardData);
    }

    /**
     * Единая точка входа для открытия редактора из страниц hint_viewer/pokaz.
     * duplicateMode:
     * - 'source'     -> проверка дубликата по исходному файлу (hint_viewer)
     * - 'board_xgid' -> проверка дубликата по позиции доски (pokaz)
     * - 'auto'       -> выбрать доступный метод автоматически
     */
    async openModalWithBestDuplicateCheck(cardData, options = {}) {
        const duplicateMode = (options && options.duplicateMode) ? options.duplicateMode : 'auto';
        if (options && options.forceBoardMatchBanner === true) {
            this.boardMatchBannerEnabled = true;
        }
        if (duplicateMode === 'source') {
            if (typeof this.openModalWithDuplicateSourceCheck !== 'function') {
                throw new Error('Режим duplicateMode=source недоступен: нет openModalWithDuplicateSourceCheck');
            }
            await this.openModalWithDuplicateSourceCheck(cardData);
            return;
        }
        if (duplicateMode === 'board_xgid') {
            if (typeof this.openModalWithDuplicateBoardXgidCheck !== 'function') {
                throw new Error('Режим duplicateMode=board_xgid недоступен: нет openModalWithDuplicateBoardXgidCheck');
            }
            await this.openModalWithDuplicateBoardXgidCheck(cardData);
            return;
        }
        if (typeof this.openModalWithDuplicateSourceCheck === 'function') {
            await this.openModalWithDuplicateSourceCheck(cardData);
            return;
        }
        if (typeof this.openModalWithDuplicateBoardXgidCheck === 'function') {
            await this.openModalWithDuplicateBoardXgidCheck(cardData);
            return;
        }
        if (typeof this.openModalWithData === 'function') {
            this.openModalWithData(cardData);
            return;
        }
        throw new Error('ContentEditor не содержит методов открытия модального окна');
    }

    collectUnifiedLabelsFromFrameRefs(refs) {
        const seen = new Set();
        const out = [];
        for (const ref of refs) {
            try {
                const raw = localStorage.getItem(ref.storageKey);
                const p = raw ? JSON.parse(raw) : null;
                if (p && Array.isArray(p.labels)) {
                    for (const x of p.labels) {
                        if (typeof x !== 'string') continue;
                        const t = x.trim().slice(0, 255);
                        if (t && !seen.has(t)) {
                            seen.add(t);
                            out.push(t);
                        }
                    }
                }
            } catch (e) {
                console.warn('collectUnifiedLabelsFromFrameRefs:', ref.storageKey, e);
            }
        }
        return out;
    }

    buildFramesPayloadForCloudSave(refs) {
        const frames = refs.map((ref, order) => {
            const raw = localStorage.getItem(ref.storageKey);
            let payload = null;
            try {
                payload = raw ? JSON.parse(raw) : null;
            } catch (e) {
                throw new Error('Некорректный JSON кадра: ' + ref.storageKey);
            }
            if (!payload || !payload.frameId) {
                throw new Error('Повреждённый кадр: ' + ref.storageKey);
            }
            return {
                frameId: ref.frameId,
                saveSlotIndex: ref.saveSlotIndex != null ? ref.saveSlotIndex : 0,
                order,
                payload,
            };
        });
        return { version: 1, frames };
    }

    /**
     * URL медиа карточки: GET без привязки к владельцу (доступ по знанию s3_key из JSON карточки).
     */
    buildContentCardMediaUrl(s3Key) {
        if (!s3Key) {
            return '';
        }
        return `/api/content_cards/media?${new URLSearchParams({ key: s3Key }).toString()}`;
    }

    _guessExtFromMime(mime, fallbackName) {
        const m = (mime || '').split(';')[0].trim().toLowerCase();
        const map = {
            'image/png': 'png',
            'image/jpeg': 'jpg',
            'image/webp': 'webp',
            'image/gif': 'gif',
            'audio/mpeg': 'mp3',
            'audio/mp4': 'm4a',
            'audio/webm': 'webm',
            'audio/ogg': 'ogg',
            'audio/wav': 'wav',
            'audio/x-wav': 'wav',
        };
        if (map[m]) return map[m];
        if (fallbackName && fallbackName.includes('.')) {
            return fallbackName.split('.').pop().slice(0, 8) || 'bin';
        }
        return 'bin';
    }

    async uploadBinaryToContentCardMedia(blob, filenameHint, contentType) {
        const initData = (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || '';
        if (!initData) {
            throw new Error('Нет init_data для загрузки файла');
        }
        const ext = this._guessExtFromMime(blob.type || contentType, filenameHint);
        const fname = (filenameHint && filenameHint.replace(/[\\/]/g, '_')) || `file.${ext}`;
        const fd = new FormData();
        fd.append('init_data', initData);
        fd.append('file', blob, fname.includes('.') ? fname : `${fname}.${ext}`);
        const r = await fetch('/api/content_cards/media/upload', { method: 'POST', body: fd });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) {
            const d = data.detail;
            throw new Error(typeof d === 'string' ? d : `upload ${r.status}`);
        }
        if (!data.s3_key) {
            throw new Error('Нет s3_key в ответе');
        }
        return { s3_key: data.s3_key, content_type: data.content_type || blob.type || '' };
    }

    /**
     * Перед сохранением кадра/карточки: заливает тяжёлые медиа в S3, в JSON остаются s3_key.
     * Требуется Telegram WebApp init_data и права контент-админа — иначе upload не вызывается,
     * в JSON остаются data/blob URL (см. uploadBinaryToContentCardMedia).
     */
    async uploadPayloadMediaToS3(payload) {
        if (!payload || typeof payload !== 'object') {
            return;
        }
        const initData =
            (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || '';
        if (!initData) {
            return;
        }
        const bgPattern = payload.editor && payload.editor.canvasBackgroundPattern;
        if (bgPattern && typeof bgPattern === 'object') {
            const dataUrl = String(bgPattern.imageDataUrl || '');
            if (!bgPattern.imageS3Key && dataUrl.startsWith('data:image')) {
                try {
                    const blob = await (await fetch(dataUrl)).blob();
                    const hintName = (bgPattern.fileName && String(bgPattern.fileName).trim())
                        ? String(bgPattern.fileName).trim()
                        : 'canvas-pattern.png';
                    const up = await this.uploadBinaryToContentCardMedia(blob, hintName, blob.type);
                    bgPattern.imageS3Key = up.s3_key;
                    delete bgPattern.imageDataUrl;
                } catch (e) {
                    console.warn('uploadPayloadMediaToS3 canvas pattern:', e && e.message ? e.message : e);
                }
            }
        }
        const elements = Array.isArray(payload.elements) ? payload.elements : [];
        for (const item of elements) {
            const toolId = item.toolId || '';
            if (toolId === 'upload-image' && !item.imageS3Key) {
                const url = item.imageUrl || '';
                if (url.startsWith('data:') || url.startsWith('blob:')) {
                    const blob = await (await fetch(url)).blob();
                    const up = await this.uploadBinaryToContentCardMedia(blob, 'frame.png', blob.type);
                    item.imageS3Key = up.s3_key;
                    item.imageContentType = up.content_type || blob.type || '';
                    delete item.imageUrl;
                }
            } else if (toolId === 'board-illustration' && !item.boardImageS3Key) {
                const d = item.imageDataUrl || '';
                if (d.startsWith('data:image')) {
                    const blob = await (await fetch(d)).blob();
                    const up = await this.uploadBinaryToContentCardMedia(blob, 'board.png', blob.type);
                    item.boardImageS3Key = up.s3_key;
                    delete item.imageDataUrl;
                }
            } else if (toolId === 'audio-file' && !item.audioS3Key) {
                let blob = null;
                if (item.audioStorageId) {
                    blob = await this.getAudioBlobFromIDB(item.audioStorageId);
                } else {
                    const au = item.audioUrl || '';
                    if (au.startsWith('blob:') || au.startsWith('data:')) {
                        blob = await (await fetch(au)).blob();
                    }
                }
                if (blob) {
                    const name = (item.audioName && String(item.audioName).replace(/[\\/]/g, '_')) || 'audio.webm';
                    const up = await this.uploadBinaryToContentCardMedia(blob, name, blob.type);
                    item.audioS3Key = up.s3_key;
                    item.audioUrl = '';
                    item.audioStorageId = '';
                }
            }
        }
    }

    openContentCardDuplicateSourceModal(
        fileNameOrXgid,
        existingCardId,
        onConfirm,
        confirmButtonText,
        duplicateKind = 'file'
    ) {
        const modal = document.getElementById('contentCardDuplicateSourceModal');
        const msgEl = document.getElementById('contentCardDuplicateSourceMessage');
        const titleEl = document.getElementById('contentCardDuplicateSourceTitle');
        if (!modal || !msgEl) {
            this.showNotification('Не удалось показать диалог подтверждения', 'error');
            return;
        }
        this._duplicateSourceConfirmAction =
            typeof onConfirm === 'function' ? onConfirm : null;
        const confirmBtn = modal.querySelector('.card-labels-save-btn');
        if (confirmBtn) {
            confirmBtn.textContent = confirmButtonText || 'Всё равно сохранить';
        }
        const idPart =
            existingCardId != null && !Number.isNaN(Number(existingCardId))
                ? ` (карточка №${this.escapeHtml(String(existingCardId))})`
                : '';
        if (duplicateKind === 'board_xgid') {
            if (titleEl) {
                titleEl.textContent = 'Карточка с такой позицией уже есть';
            }
            const raw = String(fileNameOrXgid || '');
            const preview =
                raw.length > 140 ? `${this.escapeHtml(raw.slice(0, 140))}…` : this.escapeHtml(raw);
            msgEl.innerHTML =
                `Такая строка позиции (XGID) уже сохранена для другой карточки${idPart}.` +
                (preview
                    ? `<br/><span style="display:block;margin-top:8px;font-size:12px;opacity:0.85;word-break:break-all;">${preview}</span>`
                    : '') +
                '<br/><span style="display:block;margin-top:10px;">Открыть редактор всё равно?</span>';
        } else {
            if (titleEl) {
                titleEl.textContent = 'Карточка с таким исходником уже есть';
            }
            const fnEsc = this.escapeHtml(String(fileNameOrXgid || ''));
            msgEl.innerHTML =
                `Исходный файл «${fnEsc}» уже используется${idPart}. ` +
                'Создать ещё одну карточку с тем же исходником?';
        }
        modal.style.display = 'flex';
        modal.setAttribute('aria-hidden', 'false');
    }

    closeContentCardDuplicateSourceModal() {
        const modal = document.getElementById('contentCardDuplicateSourceModal');
        if (!modal) return;
        this._duplicateSourceConfirmAction = null;
        const confirmBtn = modal.querySelector('.card-labels-save-btn');
        if (confirmBtn) {
            confirmBtn.textContent = 'Всё равно сохранить';
        }
        const titleEl = document.getElementById('contentCardDuplicateSourceTitle');
        if (titleEl) {
            titleEl.textContent = 'Карточка с таким исходником уже есть';
        }
        modal.style.display = 'none';
        modal.setAttribute('aria-hidden', 'true');
    }

    async confirmSaveDespiteDuplicateSource() {
        const confirmAction = this._duplicateSourceConfirmAction;
        this.closeContentCardDuplicateSourceModal();
        if (typeof confirmAction === 'function') {
            await Promise.resolve(confirmAction());
            return;
        }
        const ok = await this.saveCardToCloud();
        if (ok) {
            this.closeCardPreviewModal();
        }
    }

    async saveCardToCloud() {
        const refs = this.collectSavedFrameRefsForCurrentGame();
        if (!refs.length) {
            this.showNotification('Нет сохранённых кадров для этой игры', 'warning');
            return false;
        }
        let initData = '';
        if (window.Telegram && window.Telegram.WebApp) {
            initData = window.Telegram.WebApp.initData || '';
        }
        if (!initData) {
            this.showNotification('Откройте страницу из Telegram, чтобы сохранить на сервер', 'warning');
            return false;
        }
        const chatIdStr = this.getHintViewerChatIdForApi();
        if (!chatIdStr) {
            this.showNotification('Не найден идентификатор пользователя (chat_id)', 'warning');
            return false;
        }
        const file_name = this.buildContentCardFileNameForCloud();
        let framesWrapper;
        try {
            const frames = [];
            for (let order = 0; order < refs.length; order++) {
                const ref = refs[order];
                const raw = localStorage.getItem(ref.storageKey);
                let payload = null;
                try {
                    payload = raw ? JSON.parse(raw) : null;
                } catch (e) {
                    throw new Error('Некорректный JSON кадра: ' + ref.storageKey);
                }
                if (!payload || !payload.frameId) {
                    throw new Error('Повреждённый кадр: ' + ref.storageKey);
                }
                await this.uploadPayloadMediaToS3(payload);
                delete payload.labels;
                localStorage.setItem(ref.storageKey, JSON.stringify(payload));
                frames.push({
                    frameId: ref.frameId,
                    saveSlotIndex: ref.saveSlotIndex != null ? ref.saveSlotIndex : 0,
                    order,
                    payload,
                });
            }
            framesWrapper = { version: 1, frames };
            let shBoard = null;
            let shCardData = null;
            if (typeof window.getHintViewerBoardSnapshot === 'function') {
                try {
                    shBoard = window.getHintViewerBoardSnapshot();
                    if (shBoard != null) shBoard = JSON.parse(JSON.stringify(shBoard));
                } catch (e) {
                    shBoard = null;
                }
            }
            if (typeof window.getHintViewerCurrentCardData === 'function') {
                try {
                    shCardData = window.getHintViewerCurrentCardData();
                    if (shCardData != null) shCardData = JSON.parse(JSON.stringify(shCardData));
                } catch (e) {
                    shCardData = null;
                }
            }
            if (shBoard != null || shCardData != null) {
                framesWrapper.sharedContext = {
                    board: shBoard,
                    cardData: shCardData,
                };
            }
        } catch (e) {
            this.showNotification(e.message || String(e), 'error');
            return false;
        }
        const labels = this.loadCardLabelsFromStorage();
        const chat_id = parseInt(chatIdStr, 10);
        if (Number.isNaN(chat_id)) {
            this.showNotification('Некорректный chat_id', 'error');
            return false;
        }
        try {
            const response = await fetch('/api/content_cards/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    init_data: initData,
                    file_name,
                    frames: framesWrapper,
                    labels: labels.length ? labels : null,
                    chat_id,
                }),
            });
            let data = {};
            try {
                data = await response.json();
            } catch (e) {
                data = {};
            }
            if (!response.ok) {
                let msg = data.detail;
                if (Array.isArray(msg)) {
                    msg = msg.map((x) => (x.msg || JSON.stringify(x))).join('; ');
                } else if (msg && typeof msg === 'object') {
                    msg = JSON.stringify(msg);
                }
                throw new Error(msg || `Ошибка ${response.status}`);
            }
            this.showNotification('Карточка сохранена на сервере', 'success');
            return true;
        } catch (e) {
            console.error('saveCardToCloud:', e);
            this.showNotification(e.message || String(e), 'error');
            return false;
        }
    }

    /**
     * Все сохранённые кадры из localStorage, относящиеся к текущей игре (gameId + номер игры).
     */
    collectSavedFrameRefsForCurrentGame() {
        const { gameId, gameNum } = this.getGameContextForCard();
        const refs = [];
        const prefix = 'contentEditor_frame_';

        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (!key || !key.startsWith(prefix)) continue;
            try {
                const raw = localStorage.getItem(key);
                const payload = JSON.parse(raw);
                if (!payload || !payload.frameId) continue;

                let match = false;
                if (gameNum != null) {
                    const idPrefix = `${gameId}_g${gameNum}_`;
                    match = String(payload.frameId).startsWith(idPrefix);
                } else {
                    match = String(payload.frameId).startsWith(`${gameId}_`) ||
                        (payload.board && payload.board.gameId === gameId);
                }
                if (!match) continue;

                refs.push({
                    storageKey: key,
                    frameId: payload.frameId,
                    saveSlotIndex: payload.saveSlotIndex != null ? payload.saveSlotIndex : 0,
                    savedAt: payload.savedAt || ''
                });
            } catch (err) {
                console.warn('collectSavedFrameRefsForCurrentGame:', key, err);
            }
        }

        refs.sort((a, b) => {
            const fa = this.parseFrameIndexFromFrameId(a.frameId);
            const fb = this.parseFrameIndexFromFrameId(b.frameId);
            if (fa !== fb) return fa - fb;
            if (a.saveSlotIndex !== b.saveSlotIndex) return a.saveSlotIndex - b.saveSlotIndex;
            return String(a.savedAt).localeCompare(String(b.savedAt));
        });

        return refs;
    }

    parseFrameIndexFromFrameId(frameId) {
        const m = String(frameId).match(/_f(\d+)$/);
        return m ? parseInt(m[1], 10) : 0;
    }

    openCardPreviewModal() {
        return openCardPreviewModalImpl(this);
    }

    closeCardPreviewModal() {
        return closeCardPreviewModalImpl(this);
    }

    refreshCardPreviewUI() {
        return refreshCardPreviewUIImpl(this);
    }

    /**
     * Порядок блоков в предпросмотре по сохранённому top с холста (перед flex-колонкой top сбрасывается).
     */
    reorderCardPreviewElementsBySavedTop(inner) {
        return reorderCardPreviewElementsBySavedTopImpl(this, inner);
    }

    shouldShowBoardInCardPreview(payload) {
        return shouldShowBoardInCardPreviewImpl(this, payload);
    }

    loadBoardPreviewImages() {
        return loadBoardPreviewImagesImpl(this);
    }

    getBoardPreviewPointX(point) {
        return getBoardPreviewPointXImpl(this, point);
    }

    getBoardPreviewBaseY(point) {
        return getBoardPreviewBaseYImpl(this, point);
    }

    getBoardPreviewDy(point) {
        return getBoardPreviewDyImpl(this, point);
    }

    drawBoardPreviewCheckers(ctx, player, img, positions, currentPlayer, invertColors) {
        return drawBoardPreviewCheckersImpl(this, ctx, player, img, positions, currentPlayer, invertColors);
    }

    /** Соответствует геометрии куба в hint_viewer (cubeVisual из getHintViewerBoardSnapshot). */
    drawDoublingCubePreview(ctx, cubeVisual, invertColors, imgs) {
        return drawDoublingCubePreviewImpl(this, ctx, cubeVisual, invertColors, imgs);
    }

    resolveBoardPositionsFromSnapshot(snapshot) {
        return resolveBoardPositionsFromSnapshotImpl(this, snapshot);
    }

    paintBoardPreviewCanvas(canvas, snapshot, imgs) {
        return paintBoardPreviewCanvasImpl(this, canvas, snapshot, imgs);
    }

    /** Текст строки над доской (как в hint_viewer: матч до n и счёт, либо манигейм). */
    formatBoardMatchBannerText(snapshot) {
        return formatBoardMatchBannerTextImpl(this, snapshot);
    }

    /**
     * Предпросмотр карточки: кнопка сворачивания блока таблицы (ход/куб).
     */
    setupCardPreviewTableCollapse(tableEl) {
        return setupCardPreviewTableCollapseImpl(this, tableEl);
    }

    appendCardPreviewBoardOverlay(wrap, payload) {
        return appendCardPreviewBoardOverlayImpl(this, wrap, payload);
    }

    renderCardPreviewSurface(payload) {
        const out = renderCardPreviewSurfaceImpl(this, payload);
        this.ensureCardPreviewBoardCollapseUi();
        return out;
    }

    ensureCardPreviewBoardCollapseUi() {
        const host = document.getElementById('cardPreviewFrameHost');
        if (!host) return;
        const overlay = host.querySelector('.card-preview-board-overlay');
        if (!overlay) return;

        const body = overlay.querySelector('.card-preview-board-body');
        if (!body) return;

        let collapsible = body.querySelector(':scope > .card-preview-board-collapsible');
        if (!collapsible) {
            collapsible = document.createElement('div');
            collapsible.className = 'card-preview-board-collapsible';
            const movingNodes = Array.from(
                body.querySelectorAll(':scope > .card-preview-board-match-banner, :scope > .card-preview-board-canvas-wrap')
            );
            movingNodes.forEach((n) => collapsible.appendChild(n));
            body.insertBefore(collapsible, body.firstChild || null);
        }

        let toggleRow = body.querySelector(':scope > .card-preview-board-toggle-row');
        if (!toggleRow) {
            toggleRow = document.createElement('div');
            toggleRow.className = 'card-preview-board-toggle-row';
            toggleRow.innerHTML = `
                <button type="button" class="card-preview-board-toggle" aria-expanded="true" aria-label="Свернуть или развернуть доску" title="Свернуть или развернуть доску">
                    <span class="card-preview-board-toggle-icon" aria-hidden="true">
                        <svg class="card-preview-board-caret-svg" viewBox="0 0 48 22" xmlns="http://www.w3.org/2000/svg" focusable="false">
                            <path fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round" d="M7 17 L24 5 L41 17"/>
                        </svg>
                    </span>
                </button>
            `;
            body.appendChild(toggleRow);
        }

        let toggle = toggleRow.querySelector('.card-preview-board-toggle');
        if (!toggle) return;

        const collapsedInitial = !!this._cardPreviewBoardCollapsed;
        overlay.classList.toggle('card-preview-board-overlay--collapsed', collapsedInitial);
        toggle.setAttribute('aria-expanded', collapsedInitial ? 'false' : 'true');
        if (toggle.dataset.ceBoardCollapseBound !== '1') {
            // Удаляем внешние/дублирующие обработчики (в т.ч. из legacy feature-слоя),
            // чтобы состояние не переключалось дважды за один клик.
            const cleanToggle = toggle.cloneNode(true);
            toggle.replaceWith(cleanToggle);
            toggle = cleanToggle;
        }
        if (toggle.dataset.ceBoardCollapseBound === '1') return;
        toggle.dataset.ceBoardCollapseBound = '1';
        const onToggle = (e) => {
            if (e) {
                e.preventDefault();
                e.stopPropagation();
            }
            const collapsedNow = !overlay.classList.contains('card-preview-board-overlay--collapsed');
            overlay.classList.toggle('card-preview-board-overlay--collapsed', collapsedNow);
            this._cardPreviewBoardCollapsed = collapsedNow;
            toggle.setAttribute('aria-expanded', collapsedNow ? 'false' : 'true');
            requestAnimationFrame(() => this.refreshCardPreviewScale());
        };
        toggle.addEventListener('click', onToggle);
        toggle.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                onToggle(e);
            }
        });
    }

    /**
     * Для предпросмотра с flex-колонкой высота inner считается из потока; иначе — из absolute top + height.
     */
    updateCardPreviewInnerMinHeight(inner) {
        return updateCardPreviewInnerMinHeightImpl(this, inner);
    }

    refreshCardPreviewScale() {
        return refreshCardPreviewScaleImpl(this);
    }

    escapeHtml(s) {
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    cardPreviewPrev() {
        return cardPreviewPrevImpl(this);
    }

    cardPreviewNext() {
        return cardPreviewNextImpl(this);
    }

    deleteCurrentPreviewFrame() {
        return deleteCurrentPreviewFrameImpl(this);
    }

    cardPreviewApprove() {
        return cardPreviewApproveImpl(this);
    }

    openCardLabelsModal() {
        if (!this.cardLabelsModal) return;
        this._labelPresetsTarget = 'card';
        this.renderCardLabelsList();
        const input = document.getElementById('cardLabelsInput');
        if (input) input.value = '';
        this.cardLabelsModal.style.display = 'flex';
        this.cardLabelsModal.setAttribute('aria-hidden', 'false');
        void this.refreshLabelPresetsAccessButton();
        requestAnimationFrame(() => {
            if (input) input.focus();
        });
    }

    /**
     * Показать кнопку «Пресеты» только если есть доступ к API (root-админ).
     */
    async refreshLabelPresetsAccessButton(buttonId = 'cardLabelsOpenPresetsBtn') {
        const btn = document.getElementById(buttonId);
        if (!btn) return;
        const ok = await this.fetchLabelPresetsFromServer();
        btn.style.display = ok ? 'inline-flex' : 'none';
    }

    async fetchLabelPresetsFromServer() {
        const auth = this.getContentCardApiAuthPayload();
        if (!auth) {
            this._labelPresetsList = [];
            return false;
        }
        try {
            const r = await fetch('/api/content_cards/label_presets', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(auth),
            });
            if (!r.ok) {
                this._labelPresetsList = [];
                return false;
            }
            const data = await r.json();
            this._labelPresetsList = Array.isArray(data.presets) ? data.presets.slice() : [];
            return true;
        } catch (e) {
            console.warn('fetchLabelPresetsFromServer:', e);
            this._labelPresetsList = [];
            return false;
        }
    }

    openLabelPresetsModal() {
        this.ensureLabelPresetsModal();
        if (!this.labelPresetsModal) return;
        void this._openLabelPresetsModalAsync();
    }

    ensureLabelPresetsModal() {
        let modal = document.getElementById('labelPresetsModal');
        if (!modal) {
            document.body.insertAdjacentHTML(
                'beforeend',
                `
                <div id="labelPresetsModal" class="label-presets-modal" style="display: none;" aria-hidden="true">
                    <div class="card-labels-overlay" onclick="contentEditor.closeLabelPresetsModal()"></div>
                    <div class="card-labels-box label-presets-modal-box" role="dialog" aria-modal="true" aria-labelledby="labelPresetsModalTitle">
                        <div class="label-presets-modal-header">
                            <h3 id="labelPresetsModalTitle" class="card-labels-title">Пресеты меток</h3>
                            <button type="button" class="label-presets-modal-close" onclick="contentEditor.closeLabelPresetsModal()" aria-label="Закрыть">&times;</button>
                        </div>
                        <p class="card-labels-presets-hint">Нажмите текст пресета — он добавится в список меток карточки (в окне ниже после возврата).</p>
                        <div id="labelPresetsList" class="card-labels-presets-list" aria-live="polite"></div>
                        <div class="card-labels-preset-admin-row">
                            <input type="text" id="labelPresetNewInput" class="card-labels-input" maxlength="255" placeholder="Новый пресет для всех" autocomplete="off" />
                            <button type="button" class="card-labels-add-btn" onclick="contentEditor.createLabelPresetFromInput()">Сохранить в пресеты</button>
                        </div>
                        <div class="card-labels-actions card-labels-actions--preset-footer">
                            <button type="button" class="card-labels-save-btn" onclick="contentEditor.closeLabelPresetsModal()">Готово</button>
                        </div>
                    </div>
                </div>
                `
            );
            modal = document.getElementById('labelPresetsModal');
        }
        this.labelPresetsModal = modal;
        const labelPresetNewInput = document.getElementById('labelPresetNewInput');
        if (labelPresetNewInput && !labelPresetNewInput.dataset.presetsEnterBound) {
            labelPresetNewInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.createLabelPresetFromInput();
                }
            });
            labelPresetNewInput.dataset.presetsEnterBound = '1';
        }
        return modal;
    }

    async _openLabelPresetsModalAsync() {
        const ok = await this.fetchLabelPresetsFromServer();
        if (!ok) {
            this.showNotification('Пресеты доступны только администраторам', 'warning');
            return;
        }
        this.labelPresetsModal.style.display = 'flex';
        this.labelPresetsModal.setAttribute('aria-hidden', 'false');
        this.renderLabelPresetsPanel();
        const inp = document.getElementById('labelPresetNewInput');
        requestAnimationFrame(() => {
            if (inp) inp.focus();
        });
    }

    closeLabelPresetsModal() {
        if (!this.labelPresetsModal) return;
        this.labelPresetsModal.style.display = 'none';
        this.labelPresetsModal.setAttribute('aria-hidden', 'true');
    }

    getContentCardApiAuthPayload() {
        const initData = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData;
        if (initData) return { init_data: initData };
        const params = new URLSearchParams(window.location.search || '');
        const fabToken = String(params.get('fab_token') || '');
        if (fabToken) return { fab_token: fabToken };
        return null;
    }

    renderTextStylePresetSelectOptions() {
        const opts = ['<option value="">Пресет стиля…</option>'];
        for (const preset of this._textStylePresetsList) {
            opts.push(
                `<option value="${preset.id}">${this.escapeHtml(String(preset.name || 'Без имени'))}</option>`
            );
        }
        return opts.join('');
    }

    syncTextStylePresetDropdown() {
        const select = document.getElementById('propTextStylePresetSelect');
        if (!select) return;
        select.innerHTML = this.renderTextStylePresetSelectOptions();
        select.value = '';
    }

    _normalizeTextStylePresetPayload(raw) {
        if (!raw || typeof raw !== 'object') return null;
        const p = raw;
        const fontSizePx = this.clampNumericValue(p.fontSizePx, 8, 200, 16);
        const lineHeightPx = this.clampNumericValue(p.lineHeightPx, 8, 120, 20);
        const paddingPx = this.clampNumericValue(p.paddingPx, 0, 100, 8);
        const textAlign = ['left', 'center', 'right', 'justify'].includes(String(p.textAlign))
            ? String(p.textAlign)
            : 'left';
        const textColor = this.rgbToHex(String(p.textColor || '#333333'));
        let backgroundColor = 'transparent';
        if (p.backgroundColor != null && String(p.backgroundColor).trim() !== '') {
            const rawBg = String(p.backgroundColor).trim();
            if (/^transparent$/i.test(rawBg)) {
                backgroundColor = 'transparent';
            } else if (/^rgba?\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\s*\)$/i.test(rawBg.replace(/\s/g, ''))) {
                backgroundColor = 'transparent';
            } else {
                backgroundColor = this.rgbToHex(rawBg);
            }
        }
        return {
            fontSize: `${fontSizePx}px`,
            lineHeight: `${lineHeightPx}px`,
            padding: `${paddingPx}px`,
            textAlign,
            textColor,
            backgroundColor,
            fontWeight: p.fontWeight === 'bold' ? 'bold' : 'normal',
            fontStyle: p.fontStyle === 'italic' ? 'italic' : 'normal',
            textDecoration: p.textDecoration === 'underline' ? 'underline' : 'none',
        };
    }

    getCurrentTextStylePresetPayload() {
        if (!this.selectedElement || !this.selectedElement.classList.contains('text-element')) return null;
        const textEl = this.selectedElement.querySelector('.text-content');
        if (!textEl) return null;
        const textStyle = window.getComputedStyle(textEl);
        const blockStyle = window.getComputedStyle(this.selectedElement);
        const fontSizeSelect = document.getElementById('propFontSize');
        const textColorInput = document.getElementById('propTextColor');
        const textAlignSelect = document.getElementById('propTextAlign');
        const lineHeightSelect = document.getElementById('propLineHeight');
        const paddingSelect = document.getElementById('propPadding');
        const bgColorInput = document.getElementById('propBgColor');

        const hasSelection = this.hasValidSelectionForFormat(textEl);
        let isBold = false;
        let isItalic = false;
        let isUnderline = false;
        if (hasSelection) {
            this.restoreSelectionForEditable(textEl);
            try {
                isBold = !!document.queryCommandState('bold');
            } catch (e) {}
            try {
                isItalic = !!document.queryCommandState('italic');
            } catch (e) {}
            try {
                isUnderline = !!document.queryCommandState('underline');
            } catch (e) {}
        } else {
            const weightRaw = String(textStyle.fontWeight || '').trim();
            isBold = weightRaw === 'bold' || (!Number.isNaN(parseInt(weightRaw, 10)) && parseInt(weightRaw, 10) >= 600);
            isItalic = textStyle.fontStyle === 'italic';
            const textDecorationLine = String(textStyle.textDecorationLine || textStyle.textDecoration || '');
            isUnderline = textDecorationLine.includes('underline');
        }

        return {
            fontSizePx: this.clampNumericValue(
                parseInt(fontSizeSelect && fontSizeSelect.value ? fontSizeSelect.value : textStyle.fontSize, 10),
                8,
                200,
                16
            ),
            textColor: this.rgbToHex(
                textColorInput && textColorInput.value ? textColorInput.value : (textStyle.color || '#333333')
            ),
            textAlign: String(
                textAlignSelect && textAlignSelect.value ? textAlignSelect.value : (textStyle.textAlign || 'left')
            ),
            lineHeightPx: this.clampNumericValue(
                parseInt(lineHeightSelect && lineHeightSelect.value ? lineHeightSelect.value : Math.round(parseFloat(textStyle.lineHeight) || 20), 10),
                8,
                120,
                20
            ),
            paddingPx: this.clampNumericValue(
                parseInt(paddingSelect && paddingSelect.value ? paddingSelect.value : blockStyle.padding, 10),
                0,
                100,
                8
            ),
            backgroundColor: this.isCanvasElementBackgroundTransparent(this.selectedElement)
                ? 'transparent'
                : this.normalizeBackgroundColorForInput(
                      bgColorInput && bgColorInput.value
                          ? bgColorInput.value
                          : this.getBlockBackgroundColorForInput(this.selectedElement)
                  ),
            fontWeight: isBold ? 'bold' : 'normal',
            fontStyle: isItalic ? 'italic' : 'normal',
            textDecoration: isUnderline ? 'underline' : 'none',
        };
    }

    applyTextStylePresetPayload(payload) {
        if (!this.selectedElement || !this.selectedElement.classList.contains('text-element')) return false;
        const normalized = this._normalizeTextStylePresetPayload(payload);
        if (!normalized) return false;
        const textEl = this.selectedElement.querySelector('.text-content');
        if (!textEl) return false;

        const hasSelection = this.hasValidSelectionForFormat(textEl);
        if (hasSelection) {
            this.applyStyleToSelection(textEl, {
                fontSize: normalized.fontSize,
                color: normalized.textColor,
                lineHeight: normalized.lineHeight,
                fontWeight: normalized.fontWeight,
                fontStyle: normalized.fontStyle,
                textDecoration: normalized.textDecoration,
            });
        } else {
            textEl.style.fontSize = normalized.fontSize;
            textEl.style.color = normalized.textColor;
            textEl.style.lineHeight = normalized.lineHeight;
            textEl.style.fontWeight = normalized.fontWeight;
            textEl.style.fontStyle = normalized.fontStyle;
            textEl.style.textDecoration = normalized.textDecoration;
        }

        textEl.style.textAlign = normalized.textAlign;
        this.selectedElement.style.padding = normalized.padding;
        this.selectedElement.style.backgroundColor = normalized.backgroundColor;
        this.autoGrowTextElementContainer(this.selectedElement);
        const fontSizeSelect = document.getElementById('propFontSize');
        const textColorInput = document.getElementById('propTextColor');
        const textAlignSelect = document.getElementById('propTextAlign');
        const lineHeightSelect = document.getElementById('propLineHeight');
        const paddingSelect = document.getElementById('propPadding');
        const bgColorInput = document.getElementById('propBgColor');
        const fontSizeDisplay = document.querySelector('#propFontSize + .property-value');
        if (fontSizeSelect) {
            fontSizeSelect.value = String(parseInt(normalized.fontSize, 10) || 16);
        }
        if (fontSizeDisplay) {
            fontSizeDisplay.textContent = normalized.fontSize;
        }
        if (textColorInput) {
            textColorInput.value = normalized.textColor;
        }
        if (textAlignSelect) {
            textAlignSelect.value = normalized.textAlign;
        }
        if (lineHeightSelect) {
            lineHeightSelect.value = String(parseInt(normalized.lineHeight, 10) || 20);
        }
        if (paddingSelect) {
            paddingSelect.value = String(parseInt(normalized.padding, 10) || 8);
        }
        if (bgColorInput) {
            bgColorInput.value = this.normalizeBackgroundColorForInput(normalized.backgroundColor);
        }
        return true;
    }

    syncTextPropertiesFromActiveSelection(element = this.selectedElement) {
        if (!element || !element.classList || !element.classList.contains('text-element')) return;
        const textEl = element.querySelector('.text-content');
        if (!textEl) return;

        const fontSizeSelect = document.getElementById('propFontSize');
        const textColorInput = document.getElementById('propTextColor');
        const textAlignSelect = document.getElementById('propTextAlign');
        const lineHeightSelect = document.getElementById('propLineHeight');
        const paddingSelect = document.getElementById('propPadding');
        const bgColorInput = document.getElementById('propBgColor');
        const fontSizeDisplay = document.querySelector('#propFontSize + .property-value');
        if (!fontSizeSelect && !textColorInput && !textAlignSelect && !lineHeightSelect && !paddingSelect && !bgColorInput) {
            return;
        }

        let styleNode = textEl;
        const sel = window.getSelection();
        if (sel && sel.rangeCount) {
            const range = sel.getRangeAt(0);
            const anchorNode = range.startContainer;
            if (anchorNode && textEl.contains(anchorNode)) {
                if (anchorNode.nodeType === Node.ELEMENT_NODE) {
                    styleNode = anchorNode;
                } else if (anchorNode.parentElement) {
                    styleNode = anchorNode.parentElement;
                }
            }
        }
        if (!(styleNode instanceof Element) || !textEl.contains(styleNode)) {
            styleNode = textEl;
        }

        const textStyle = window.getComputedStyle(styleNode);
        const blockStyle = window.getComputedStyle(element);
        const fontSizePx = this.clampNumericValue(parseInt(textStyle.fontSize, 10), 8, 200, 16);
        const lineHeightPx = this.clampNumericValue(
            parseInt(String(Math.round(parseFloat(textStyle.lineHeight) || 20)), 10),
            8,
            120,
            20
        );
        const paddingPx = this.clampNumericValue(parseInt(blockStyle.padding, 10), 0, 100, 8);
        const textColor = this.rgbToHex(textStyle.color || '#333333');
        const textAlign = String(textStyle.textAlign || 'left');
        const bgColor = this.getBlockBackgroundColorForInput(element);

        if (fontSizeSelect) fontSizeSelect.value = String(fontSizePx);
        if (fontSizeDisplay) fontSizeDisplay.textContent = `${fontSizePx}px`;
        if (textColorInput) textColorInput.value = textColor;
        if (textAlignSelect) {
            const allowed = ['left', 'center', 'right', 'justify'];
            textAlignSelect.value = allowed.includes(textAlign) ? textAlign : 'left';
        }
        if (lineHeightSelect) lineHeightSelect.value = String(lineHeightPx);
        if (paddingSelect) paddingSelect.value = String(paddingPx);
        if (bgColorInput) bgColorInput.value = bgColor;
    }

    async applyTextStylePresetFromSelect(value) {
        const presetId = Number(value);
        const select = document.getElementById('propTextStylePresetSelect');
        if (!Number.isFinite(presetId) || presetId < 1) {
            if (select) select.value = '';
            return;
        }
        const preset = this._textStylePresetsList.find((x) => Number(x.id) === presetId);
        if (!preset || !preset.payload) {
            this.showNotification('Пресет не найден', 'warning');
            if (select) select.value = '';
            return;
        }
        const ok = this.applyTextStylePresetPayload(preset.payload);
        if (ok) {
            this.showNotification('Пресет применён', 'success');
        }
        if (select) select.value = '';
    }

    openTextStylePresetSaveModal() {
        if (!this.textStylePresetSaveModal) return;
        if (!this.selectedElement || !this.selectedElement.classList.contains('text-element')) {
            this.showNotification('Выберите текстовый блок', 'warning');
            return;
        }
        const inp = document.getElementById('textStylePresetNameInput');
        if (inp) inp.value = '';
        this.textStylePresetSaveModal.style.display = 'flex';
        this.textStylePresetSaveModal.setAttribute('aria-hidden', 'false');
        requestAnimationFrame(() => {
            if (inp) inp.focus();
        });
    }

    closeTextStylePresetSaveModal() {
        if (!this.textStylePresetSaveModal) return;
        this.textStylePresetSaveModal.style.display = 'none';
        this.textStylePresetSaveModal.setAttribute('aria-hidden', 'true');
    }

    async openTextStylePresetManageModal() {
        if (!this.textStylePresetManageModal) return;
        await this.refreshTextStylePresetsList(true);
        this.renderTextStylePresetManageList();
        this.textStylePresetManageModal.style.display = 'flex';
        this.textStylePresetManageModal.setAttribute('aria-hidden', 'false');
    }

    closeTextStylePresetManageModal() {
        if (!this.textStylePresetManageModal) return;
        this.textStylePresetManageModal.style.display = 'none';
        this.textStylePresetManageModal.setAttribute('aria-hidden', 'true');
    }

    renderTextStylePresetManageList() {
        const list = document.getElementById('textStylePresetManageList');
        if (!list) return;
        if (!this._textStylePresetsList.length) {
            list.innerHTML = '<span class="card-labels-presets-empty">Пока нет пресетов.</span>';
            return;
        }
        list.innerHTML = this._textStylePresetsList
            .map((p) => (
                `<div class="text-style-preset-row">` +
                `<span class="text-style-preset-name">${this.escapeHtml(String(p.name || 'Без имени'))}</span>` +
                `<button type="button" class="card-labels-preset-remove" onclick="contentEditor.deleteTextStylePresetById(${p.id})" aria-label="Удалить пресет">&times;</button>` +
                `</div>`
            ))
            .join('');
    }

    async refreshTextStylePresetsList(force = false) {
        if (this._textStylePresetsLoaded && !force) {
            this.syncTextStylePresetDropdown();
            this.renderTextStylePresetManageList();
            return this._textStylePresetsList;
        }
        const auth = this.getContentCardApiAuthPayload();
        if (!auth) return [];
        try {
            const r = await fetch('/api/content_cards/text_style_presets', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(auth),
            });
            let j = {};
            try {
                j = await r.json();
            } catch (e) {}
            if (!r.ok) {
                let detail = '';
                if (typeof j.detail === 'string') detail = j.detail;
                else if (Array.isArray(j.detail)) {
                    detail = j.detail.map((x) => x.msg || JSON.stringify(x)).join('; ');
                }
                this.showNotification(detail || 'Не удалось загрузить пресеты текста', 'error');
                return [];
            }
            this._textStylePresetsList = (Array.isArray(j.presets) ? j.presets : [])
                .map((p) => {
                    let payload = p.payload || null;
                    if (!payload && p.payload_json && typeof p.payload_json === 'object') {
                        payload = p.payload_json;
                    }
                    return {
                        id: Number(p.id),
                        name: String(p.name || ''),
                        payload: payload && typeof payload === 'object' ? payload : null,
                    };
                })
                .filter((p) => Number.isFinite(p.id) && p.id > 0 && p.name && p.payload);
            this._textStylePresetsList.sort((a, b) =>
                String(a.name).localeCompare(String(b.name), undefined, { sensitivity: 'base' })
            );
            this._textStylePresetsLoaded = true;
            this.syncTextStylePresetDropdown();
            this.renderTextStylePresetManageList();
            return this._textStylePresetsList;
        } catch (e) {
            console.error('refreshTextStylePresetsList:', e);
            this.showNotification(e.message || String(e), 'error');
            return [];
        }
    }

    async createTextStylePresetFromModal() {
        const inp = document.getElementById('textStylePresetNameInput');
        const auth = this.getContentCardApiAuthPayload();
        const payload = this.getCurrentTextStylePresetPayload();
        if (!inp || !auth || !payload) return;
        const name = String(inp.value || '').trim();
        if (!name) {
            this.showNotification('Введите название пресета', 'warning');
            return;
        }
        try {
            const r = await fetch('/api/content_cards/text_style_presets/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...auth, name, payload }),
            });
            let j = {};
            try {
                j = await r.json();
            } catch (e) {}
            if (!r.ok) {
                let detail = '';
                if (typeof j.detail === 'string') detail = j.detail;
                else if (Array.isArray(j.detail)) {
                    detail = j.detail.map((x) => x.msg || JSON.stringify(x)).join('; ');
                }
                this.showNotification(detail || 'Не удалось сохранить пресет', 'error');
                return;
            }
            const created = {
                id: Number(j.id),
                name: String(j.name || ''),
                payload: j.payload && typeof j.payload === 'object' ? j.payload : payload,
            };
            if (!Number.isFinite(created.id) || created.id < 1 || !created.name) {
                this.showNotification('Сервер вернул некорректный пресет', 'error');
                return;
            }
            this._textStylePresetsList = this._textStylePresetsList.filter((x) => Number(x.id) !== created.id);
            this._textStylePresetsList.push(created);
            this._textStylePresetsList.sort((a, b) =>
                String(a.name).localeCompare(String(b.name), undefined, { sensitivity: 'base' })
            );
            this._textStylePresetsLoaded = true;
            this.syncTextStylePresetDropdown();
            this.renderTextStylePresetManageList();
            this.closeTextStylePresetSaveModal();
            this.showNotification('Пресет текста сохранён', 'success');
        } catch (e) {
            console.error('createTextStylePresetFromModal:', e);
            this.showNotification(e.message || String(e), 'error');
        }
    }

    async deleteTextStylePresetById(id) {
        const presetId = Number(id);
        if (!Number.isFinite(presetId) || presetId < 1) return;
        const ok = await this.confirmPresetDanger('Удалить этот текстовый пресет?');
        if (!ok) return;
        const auth = this.getContentCardApiAuthPayload();
        if (!auth) return;
        try {
            const r = await fetch('/api/content_cards/text_style_presets/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...auth, preset_id: presetId }),
            });
            let j = {};
            try {
                j = await r.json();
            } catch (e) {}
            if (!r.ok) {
                let detail = '';
                if (typeof j.detail === 'string') detail = j.detail;
                else if (Array.isArray(j.detail)) {
                    detail = j.detail.map((x) => x.msg || JSON.stringify(x)).join('; ');
                }
                this.showNotification(detail || 'Не удалось удалить пресет', 'error');
                return;
            }
            this._textStylePresetsList = this._textStylePresetsList.filter((x) => Number(x.id) !== presetId);
            this.syncTextStylePresetDropdown();
            this.renderTextStylePresetManageList();
            this.showNotification('Пресет удалён', 'success');
        } catch (e) {
            console.error('deleteTextStylePresetById:', e);
            this.showNotification(e.message || String(e), 'error');
        }
    }

    renderLabelPresetsPanel() {
        const listEl = document.getElementById('labelPresetsList');
        if (!listEl) return;
        if (!this._labelPresetsList.length) {
            listEl.innerHTML =
                '<span class="card-labels-presets-empty">Пока нет пресетов — задайте строку ниже и нажмите «В пресеты».</span>';
            return;
        }
        listEl.innerHTML = this._labelPresetsList
            .map(
                (p) =>
                    `<span class="card-labels-preset-chip">` +
                    `<button type="button" class="card-labels-preset-insert" onclick="event.stopPropagation(); contentEditor.addCardLabelFromPresetById(${p.id})">${this.escapeHtml(p.value)}</button>` +
                    `<button type="button" class="card-labels-preset-remove" onclick="event.preventDefault(); event.stopPropagation(); contentEditor.deleteLabelPresetById(${p.id})" aria-label="Удалить пресет">&times;</button>` +
                    `</span>`
            )
            .join('');
    }

    addCardLabelFromPresetById(id) {
        const p = this._labelPresetsList.find((x) => x.id === id);
        if (!p || p.value == null) return;
        const v = String(p.value).trim();
        if (!v) return;
        const draft = this._labelPresetsTarget === 'admin' ? this._adminLabelsDraft : this.cardLabelsDraft;
        if (draft.some((x) => String(x).trim() === v)) {
            this.showNotification('Эта метка уже в списке', 'warning');
            return;
        }
        draft.push(v);
        if (this._labelPresetsTarget === 'admin') {
            this.renderContentCardAdminLabelsList();
        } else {
            this.renderCardLabelsList();
        }
        this.closeLabelPresetsModal();
    }

    async createLabelPresetFromInput() {
        const inp = document.getElementById('labelPresetNewInput');
        const auth = this.getContentCardApiAuthPayload();
        if (!inp || !auth) return;
        const text = String(inp.value || '').trim();
        if (!text) {
            this.showNotification('Введите текст пресета', 'warning');
            return;
        }
        try {
            const r = await fetch('/api/content_cards/label_presets/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...auth, value: text }),
            });
            let j = {};
            try {
                j = await r.json();
            } catch (e) {}
            if (!r.ok) {
                let detail = '';
                if (typeof j.detail === 'string') detail = j.detail;
                else if (Array.isArray(j.detail))
                    detail = j.detail.map((x) => x.msg || JSON.stringify(x)).join('; ');
                else if (j.detail) detail = JSON.stringify(j.detail);
                this.showNotification(detail || 'Не удалось сохранить пресет', 'error');
                return;
            }
            if (j.id != null && j.value != null) {
                this._labelPresetsList.push({ id: j.id, value: j.value });
                this._labelPresetsList.sort((a, b) =>
                    String(a.value).localeCompare(String(b.value), undefined, { sensitivity: 'base' })
                );
                inp.value = '';
                this.renderLabelPresetsPanel();
                this.showNotification('Пресет сохранён', 'success');
            }
        } catch (e) {
            console.error('createLabelPresetFromInput:', e);
            this.showNotification(e.message || String(e), 'error');
        }
    }

    /**
     * В Telegram WebApp часто блокируют множественные window.confirm — используем showConfirm.
     */
    confirmPresetDanger(message) {
        return new Promise((resolve) => {
            const tg = typeof window !== 'undefined' && window.Telegram && window.Telegram.WebApp;
            if (tg && typeof tg.showConfirm === 'function') {
                tg.showConfirm(message, (ok) => resolve(!!ok));
                return;
            }
            resolve(window.confirm(message));
        });
    }

    async deleteLabelPresetById(id) {
        const presetId = Number(id);
        if (!Number.isFinite(presetId) || presetId < 1) return;
        const ok = await this.confirmPresetDanger('Удалить этот пресет?');
        if (!ok) return;
        const auth = this.getContentCardApiAuthPayload();
        if (!auth) return;
        try {
            const r = await fetch('/api/content_cards/label_presets/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...auth, preset_id: presetId }),
            });
            let j = {};
            try {
                j = await r.json();
            } catch (e) {}
            if (!r.ok) {
                let detail = '';
                if (typeof j.detail === 'string') detail = j.detail;
                else if (j.detail) detail = JSON.stringify(j.detail);
                this.showNotification(detail || 'Не удалось удалить пресет', 'error');
                return;
            }
            this._labelPresetsList = this._labelPresetsList.filter((x) => Number(x.id) !== presetId);
            this.renderLabelPresetsPanel();
            this.showNotification('Пресет удалён', 'success');
        } catch (e) {
            console.error('deleteLabelPresetById:', e);
            this.showNotification(e.message || String(e), 'error');
        }
    }

    closeCardLabelsModal() {
        if (!this.cardLabelsModal) return;
        this.cardLabelsModal.style.display = 'none';
        this.cardLabelsModal.setAttribute('aria-hidden', 'true');
    }

    cancelCardLabelsStep() {
        this.cardLabelsDraft = [];
        this.closeCardLabelsModal();
    }

    addCardLabelFromInput() {
        const input = document.getElementById('cardLabelsInput');
        if (!input) return;
        const text = String(input.value || '').trim();
        if (!text) return;
        this.cardLabelsDraft.push(text);
        input.value = '';
        this.renderCardLabelsList();
        input.focus();
    }

    removeCardLabelAt(index) {
        if (index < 0 || index >= this.cardLabelsDraft.length) return;
        this.cardLabelsDraft.splice(index, 1);
        this.renderCardLabelsList();
    }

    renderCardLabelsList() {
        const list = document.getElementById('cardLabelsList');
        if (!list) return;
        if (!this.cardLabelsDraft.length) {
            list.innerHTML = '<span class="card-labels-empty">Пока нет меток</span>';
            return;
        }
        list.innerHTML = this.cardLabelsDraft
            .map(
                (label, i) =>
                    `<span class="card-labels-chip">${this.escapeHtml(label)}` +
                    `<button type="button" class="ce-card-label-remove-btn" onclick="contentEditor.removeCardLabelAt(${i})" aria-label="Удалить метку">&times;</button></span>`
            )
            .join('');
    }

    async confirmCardLabels() {
        const normalized = this.cardLabelsDraft.map((s) => String(s).trim()).filter(Boolean);
        try {
            this.saveCardLabelsToStorage(normalized);
        } catch (err) {
            console.error('confirmCardLabels:', err);
            this.showNotification('Не удалось сохранить метки', 'error');
            return;
        }
        this.cardLabelsDraft = [];
        this.closeCardLabelsModal();
        const ok = await this.saveCardToCloud();
        if (ok) {
            this.closeCardPreviewModal();
        }
    }

    async openEditorFromSelectedPreview() {
        const ref = this.cardPreviewRefs[this.cardPreviewIndex];
        if (!ref) {
            this.showNotification('Нет кадра для редактора', 'warning');
            return;
        }
        let payload;
        try {
            const raw = localStorage.getItem(ref.storageKey);
            payload = raw ? JSON.parse(raw) : null;
        } catch (e) {
            this.showNotification('Не удалось прочитать кадр', 'error');
            return;
        }
        if (!payload) {
            this.showNotification('Пустые данные кадра', 'error');
            return;
        }
        this.closeCardPreviewModal();
        this.editorOpenedFromPreview = true;
        this.previewEditStorageKey = ref.storageKey;
        this.previewEditFrameId = ref.frameId;
        this.previewEditSaveSlotIndex = ref.saveSlotIndex;
        this.openModalWithData(payload.cardData || null, { fromPreviewRestore: true });
        await this.restoreCanvasFromPayload(payload);
    }

    /**
     * Сохранение из редактора, открытого из предпросмотра: перезапись кадра в localStorage.
     * Редактор остаётся открытым под модалкой, очищается и переходит в обычный режим.
     * Предпросмотр сразу открывается на том же кадре; после закрытия предпросмотра снова виден редактор.
     */
    async confirmSaveFromPreviewEditor() {
        if (this.editorOpenedFromContentCardView && this._contentCardViewCardId != null) {
            const idx = this._contentCardEditFrameIndex;
            if (idx == null || idx < 0 || idx >= this.cardPreviewRefs.length) {
                this.showNotification('Нет привязки к кадру', 'warning');
                return;
            }
            const initData = (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || '';
            if (!initData) {
                this.showNotification('Нет init_data для сохранения', 'warning');
                return;
            }
            try {
                const slot = this.previewEditSaveSlotIndex != null ? this.previewEditSaveSlotIndex : 0;
                let payload = await this.buildFrameSavePayload(this.previewEditFrameId, slot);
                await this.uploadPayloadMediaToS3(payload);
                const orig = this.cardPreviewRefs[idx].payload;
                payload.cardData = this.mergeCardDataForContentCardSave(payload.cardData, orig && orig.cardData);
                if (
                    this.toggleStates['boardCanvas'] &&
                    payload.board == null &&
                    orig &&
                    orig.board != null
                ) {
                    try {
                        payload.board = JSON.parse(JSON.stringify(orig.board));
                    } catch (e) {
                        payload.board = orig.board;
                    }
                }
                delete payload.labels;
                const frames = this.cardPreviewRefs.map((r, order) => ({
                    frameId: r.frameId,
                    saveSlotIndex: r.saveSlotIndex != null ? r.saveSlotIndex : 0,
                    order,
                    payload:
                        order === idx
                            ? payload
                            : r.payload
                              ? JSON.parse(JSON.stringify(r.payload))
                              : null,
                }));
                const framesWrapper = this.wrapContentCardFramesWithShared(frames);
                const response = await fetch('/api/content_cards/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        init_data: initData,
                        content_card_id: this._contentCardViewCardId,
                        frames: framesWrapper,
                    }),
                });
                let data = {};
                try {
                    data = await response.json();
                } catch (e) {
                    data = {};
                }
                if (!response.ok) {
                    let msg = data.detail;
                    if (Array.isArray(msg)) {
                        msg = msg.map((x) => (x.msg || JSON.stringify(x))).join('; ');
                    } else if (msg && typeof msg === 'object') {
                        msg = JSON.stringify(msg);
                    }
                    throw new Error(msg || `Ошибка ${response.status}`);
                }
                this.cardPreviewRefs[idx].payload = JSON.parse(JSON.stringify(payload));
                this.showNotification('Кадр сохранён на сервере', 'success');
            } catch (err) {
                console.error('confirmSaveFromPreviewEditor (content card):', err);
                this.showNotification('Не удалось сохранить: ' + (err.message || err), 'error');
                return;
            }
            this.clearPreviewEditSession();
            this.resetEditorAfterSave();
            if (this.modal) {
                this.modal.style.display = 'none';
            }
            document.body.style.overflow = 'hidden';
            if (this.cardPreviewModal) {
                this.cardPreviewModal.style.display = 'flex';
                this.cardPreviewModal.setAttribute('aria-hidden', 'false');
                window.addEventListener('resize', this._onCardPreviewResize);
                this.refreshCardPreviewUI();
            }
            return;
        }

        if (!this.editorOpenedFromPreview || !this.previewEditStorageKey || this.previewEditFrameId == null) {
            this.showNotification('Нет привязки к кадру предпросмотра', 'warning');
            return;
        }
        const resumeKey = this.previewEditStorageKey;
        try {
            const slot = this.previewEditSaveSlotIndex != null ? this.previewEditSaveSlotIndex : 0;
            const payload = await this.buildFrameSavePayload(this.previewEditFrameId, slot);
            await this.uploadPayloadMediaToS3(payload);
            localStorage.setItem(resumeKey, JSON.stringify(payload));
            this.showNotification('Кадр обновлён', 'success');
        } catch (err) {
            console.error('confirmSaveFromPreviewEditor:', err);
            this.showNotification('Не удалось сохранить: ' + (err.message || err), 'error');
            return;
        }
        this.clearPreviewEditSession();
        this.resetEditorAfterSave();
        this._resumePreviewStorageKey = resumeKey;
        this.openCardPreviewModal();
    }

    async restoreCanvasFromPayload(payload) {
        if (!this.canvas) return;

        this.elements = [];
        this.resetCanvasDomStructure();
        this.selectedElement = null;
        this.toggleStates = {};

        if (payload.editor && payload.editor.boardCanvasToggle) {
            this.toggleStates['boardCanvas'] = true;
        }
        this.boardMatchBannerEnabled = !!(payload.editor && payload.editor.showBoardMatchBanner);
        this.cardData = null;
        if (payload.cardData && typeof payload.cardData === 'object') {
            try {
                this.cardData = JSON.parse(JSON.stringify(payload.cardData));
            } catch (e) {
                this.cardData = null;
            }
        }

        this._editorSessionBoardSnapshot = null;
        if (payload.board != null && typeof payload.board === 'object') {
            try {
                this._editorSessionBoardSnapshot = JSON.parse(JSON.stringify(payload.board));
            } catch (e) {
                this._editorSessionBoardSnapshot = payload.board;
            }
        }

        this.canvas.style.backgroundColor = this.resolveSavedCanvasBackground(payload);
        this.applyCanvasPatternConfig(this.resolveSavedCanvasBackgroundPattern(payload));

        const items = payload.elements || [];
        let maxNum = 0;
        items.forEach(item => {
            const m = /^element_(\d+)$/.exec(item.id || '');
            if (m) maxNum = Math.max(maxNum, parseInt(m[1], 10) + 1);
        });
        this.elementIdCounter = maxNum;

        items.forEach(item => {
            const el = this.deserializeCanvasElement(item);
            if (el) {
                this.getCanvasElementsRoot().appendChild(el);
                this.elements.push({
                    id: el.id,
                    toolId: el.dataset.toolId,
                    element: el
                });
            }
        });

        this.canvas.querySelectorAll('.canvas-element').forEach((el) => {
            this.addElementControls(el);
            this.attachBlockReorderInteractions(el);
        });

        this.applyPropertiesEmptyState();

        this.loadTools();
        this.syncBoardToolToggleFromState();
        this.syncBoardMatchBannerToolbarVisibility();
        this.syncLiveHintBoardCanvasOverlay();
        this.refreshTableElementsFromCardData();

        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                if (this.canvas && this.canvas.getBoundingClientRect().width > 0) {
                    this.handleWindowResize();
                }
                this.forceRefreshContent();
            });
        });
    }

    wireBoardMatchBannerToolbar() {
        const cb = document.getElementById('boardMatchBannerCheckbox');
        if (!cb || cb.dataset.ceWired === '1') return;
        cb.dataset.ceWired = '1';
        cb.addEventListener('change', () => {
            this.boardMatchBannerEnabled = cb.checked;
            this.renderEditorBoardDisplay();
        });
    }

    syncBoardMatchBannerToolbarVisibility() {
        const row = document.getElementById('toolbarBoardMatchBannerRow');
        const cb = document.getElementById('boardMatchBannerCheckbox');
        if (!row || !cb) return;
        const boardOn = !!this.toggleStates['boardCanvas'];
        row.hidden = !boardOn;
        row.style.display = boardOn ? 'block' : 'none';
        cb.checked = !!this.boardMatchBannerEnabled;
    }

    syncBoardToolToggleFromState() {
        const toolElement = document.querySelector('[data-tool-id="boardCanvas"]');
        if (!toolElement) return;
        if (this.toggleStates['boardCanvas']) {
            toolElement.classList.add('toggle-active');
        } else {
            toolElement.classList.remove('toggle-active');
        }
    }

    deserializeCanvasElement(item, options = {}) {
        const previewMode = options.previewMode === true;
        const toolId = item.toolId || '';
        const elementId = item.id || `element_${this.elementIdCounter++}`;
        const element = document.createElement('div');
        element.id = elementId;
        element.className = 'canvas-element';
        if (previewMode) {
            element.classList.add('card-preview-canvas-clone');
        }
        element.dataset.toolId = toolId;
        if (item.dataset) {
            Object.keys(item.dataset).forEach(k => {
                element.dataset[k] = item.dataset[k];
            });
        }
        if (item.style) {
            if (item.style.top) element.style.top = item.style.top;
            if (item.style.left) element.style.left = item.style.left;
            if (item.style.width) element.style.width = item.style.width;
            const isTextual = toolId === 'question-text' || toolId === 'answer-text' || toolId === 'support-link';
            const isPreviewImage = previewMode && toolId === 'upload-image';
            // В preview высота текстовых блоков должна считаться от текущей ширины экрана.
            if (item.style.height && !(previewMode && isTextual) && !isPreviewImage) {
                element.style.height = item.style.height;
            }
        }

        const ce = previewMode ? 'false' : 'true';

        switch (toolId) {
            case 'question-text':
                element.classList.add('text-element');
                element.innerHTML = `<div class="text-content" contenteditable="${ce}" placeholder="Введите текст вопроса...">${item.textHtml || ''}</div>`;
                if (!previewMode) this.setupTextEditing(element);
                break;
            case 'answer-text':
                element.classList.add('text-element');
                element.innerHTML = `<div class="text-content" contenteditable="${ce}" placeholder="Введите текст ответа...">${item.textHtml || ''}</div>`;
                if (!previewMode) this.setupTextEditing(element);
                break;
            case 'support-link': {
                element.classList.add('link-element');
                const rawUrl = item.linkUrl != null ? String(item.linkUrl) : '';
                const urlAttr = rawUrl.replace(/&/g, '&amp;').replace(/"/g, '&quot;');
                let linkInner = item.linkTextHtml || '';
                const hasAnchor = /<a\s/i.test(String(linkInner));
                if (rawUrl.trim() && !hasAnchor) {
                    const inner = String(linkInner).trim() || 'Ссылка';
                    linkInner = `<a href="${urlAttr}" target="_blank" rel="noopener noreferrer">${inner}</a>`;
                }
                element.innerHTML = `
                    <div class="link-content">
                        <div class="link-text" contenteditable="${ce}" placeholder="Текст и выделенная ссылка…">${linkInner}</div>
                        <input type="hidden" class="link-url" value="${urlAttr}">
                    </div>`;
                if (!previewMode) {
                    this.setupLinkEditing(element);
                } else {
                    this.attachPreviewLinkNavigation(element);
                }
                break;
            }
            case 'moveHintsTable':
                element.classList.add('table-element');
                element.dataset.tableType = item.tableType || 'hints';
                element.innerHTML = item.tableHtml || '';
                this.applyContentTableMarkupClasses(element);
                if (!previewMode) {
                    this.setupEditorTableCollapse(element);
                }
                break;
            case 'upload-image': {
                element.classList.add('image-element');
                const s3img = item.imageS3Key || '';
                if (s3img) {
                    element.dataset.imageS3Key = s3img;
                    if (item.imageContentType) element.dataset.imageContentType = item.imageContentType;
                } else if (item.imageUrl) {
                    element.dataset.imageUrl = item.imageUrl;
                }
                const imgUp = document.createElement('img');
                imgUp.src = s3img ? this.buildContentCardMediaUrl(s3img) : (item.imageUrl || '');
                imgUp.style.width = '100%';
                imgUp.style.height = '100%';
                imgUp.style.objectFit = 'contain';
                imgUp.alt = '';
                element.appendChild(imgUp);
                break;
            }
            case 'attach-file': {
                element.classList.add('ce-attach-file-element');
                if (item.attachmentS3Key) {
                    element.dataset.attachmentS3Key = item.attachmentS3Key;
                    element.dataset.attachmentFileName = item.attachmentFileName || 'file';
                    element.dataset.attachmentContentType = item.attachmentContentType || '';
                }
                this.buildAttachFileElementInner(element, previewMode);
                break;
            }
            case 'audio-file':
                element.classList.add('audio-element');
                if (item.audioS3Key) {
                    element.dataset.audioS3Key = item.audioS3Key;
                }
                if (item.audioStorageId) element.dataset.audioStorageId = item.audioStorageId;
                if (item.audioName) element.dataset.audioName = item.audioName;
                if (item.audioTitle) element.dataset.audioTitle = item.audioTitle;
                if (item.audioUrl) element.dataset.audioUrl = item.audioUrl;
                {
                    const audioHead = this.escapeHtml(
                        (item.audioTitle && String(item.audioTitle).trim()) || item.audioName || 'Аудио'
                    );
                    element.innerHTML = `
                    <div class="audio-message" style="display: flex; align-items: center; padding: 12px; height: 100%; background: #f0f0f0; border-radius: 8px;">
                        <div class="audio-icon" style="font-size: 24px; margin-right: 12px; color: #667eea;">🎵</div>
                        <div class="audio-info" style="flex: 1;">
                            <div class="audio-name" style="font-size: 14px; font-weight: 500; color: #333; margin-bottom: 4px;">${audioHead}</div>
                            <div class="audio-duration" style="font-size: 12px; color: #666;">—</div>
                        </div>
                        <div class="audio-play-btn" style="width: 32px; height: 32px; border-radius: 50%; background: #667eea; color: white; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 16px;">▶</div>
                    </div>`;
                }
                if (item.audioS3Key) {
                    const mediaUrl = this.buildContentCardMediaUrl(item.audioS3Key);
                    element.dataset.audioUrl = mediaUrl;
                    this.setupAudioElement(element, mediaUrl, null);
                } else if (item.audioStorageId) {
                    this.hydrateAudioElementFromIDB(element).catch((e) => console.error('hydrateAudioElementFromIDB:', e));
                } else if (item.audioUrl) {
                    this.setupAudioElement(element, item.audioUrl, null);
                }
                break;
            case 'board-illustration': {
                const img = document.createElement('img');
                const s3b = item.boardImageS3Key || '';
                if (s3b) {
                    element.dataset.boardImageS3Key = s3b;
                    img.src = this.buildContentCardMediaUrl(s3b);
                } else {
                    img.src = item.imageDataUrl || '';
                }
                img.style.maxWidth = this.getMaxCanvasWidth() + 'px';
                img.style.width = '100%';
                img.style.height = 'auto';
                img.style.objectFit = 'contain';
                element.appendChild(img);
                break;
            }
            case 'boardCanvas':
                element.innerHTML = `
                    <div style="padding: 20px; text-align: center; color: #666;">
                        <strong>Доска с параметрами</strong><br>
                        <small>Функционал временно отключен</small>
                    </div>`;
                break;
            default:
                element.innerHTML = item.innerHtml || '';
        }

        if (item.blockStyle) {
            this.applyStyleSnapshot(element, item.blockStyle);
        }
        const textInner = element.querySelector('.text-content, .link-text');
        if (textInner && item.textStyle) {
            this.applyStyleSnapshot(textInner, item.textStyle);
        }

        return element;
    }

    initPanelResizers() {
        const resizers = this.modal.querySelectorAll('.editor-resizer');
        if (!resizers.length) return;
        let resizeSyncRaf = 0;
        const scheduleResizeSync = () => {
            if (resizeSyncRaf) return;
            resizeSyncRaf = requestAnimationFrame(() => {
                resizeSyncRaf = 0;
                this.handleWindowResize();
            });
        };

        const startResize = (startX, startY, target, isMobile, startToolbarWidth, startPropsWidth, startToolbarHeight, startPropsHeight) => {
            // Разрешаем практически полностью "задвигать" панели
            const minPanelSize = 0;
            const maxPanelSize = 400;

            const handleMove = (clientX, clientY) => {
                const dx = clientX - startX;
                const dy = clientY - startY;

                if (!isMobile) {
                    // Desktop: ресайз по горизонтали (ширина панелей)
                    if (target === 'toolbar' && this.toolbarPanel) {
                        let newWidth = startToolbarWidth + dx;
                        newWidth = Math.max(minPanelSize, Math.min(maxPanelSize, newWidth));
                        this.toolbarPanel.style.width = newWidth + 'px';
                    } else if (target === 'properties' && this.propertiesPanel) {
                        let newWidth = startPropsWidth - dx;
                        newWidth = Math.max(minPanelSize, Math.min(maxPanelSize, newWidth));
                        this.propertiesPanel.style.width = newWidth + 'px';
                    }
                } else {
                    // Mobile: ресайз по вертикали (высота панелей)
                    if (target === 'toolbar' && this.toolbarPanel) {
                        // После перестановки панелей toolbar находится внизу:
                        // тянем разделитель вниз -> toolbar должен уменьшаться.
                        let newHeight = startToolbarHeight - dy;
                        newHeight = Math.max(minPanelSize, Math.min(maxPanelSize, newHeight));
                        this.toolbarPanel.style.height = newHeight + 'px';
                    } else if (target === 'properties' && this.propertiesPanel) {
                        // Панель properties сверху:
                        // тянем разделитель вниз -> панель должна увеличиваться.
                        let newHeight = startPropsHeight + dy;
                        newHeight = Math.max(minPanelSize, Math.min(maxPanelSize, newHeight));
                        this.propertiesPanel.style.height = newHeight + 'px';
                    }
                }
                scheduleResizeSync();
            };

            const onMouseMove = (moveEvent) => {
                handleMove(moveEvent.clientX, moveEvent.clientY);
            };

            const onMouseUp = () => {
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
                this.handleWindowResize();
            };

            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);

            // Возвращаем функции, чтобы можно было переиспользовать для touch
            return { handleMove, onMouseUp };
        };

        resizers.forEach(resizer => {
            // Desktop / мышь
            resizer.addEventListener('mousedown', (e) => {
                e.preventDefault();

                const target = resizer.dataset.resizeTarget;
                const isMobile = this.isMobile();

                const startX = e.clientX;
                const startY = e.clientY;

                const startToolbarWidth = this.toolbarPanel ? this.toolbarPanel.offsetWidth : 0;
                const startPropsWidth = this.propertiesPanel ? this.propertiesPanel.offsetWidth : 0;
                const startToolbarHeight = this.toolbarPanel ? this.toolbarPanel.offsetHeight : 0;
                const startPropsHeight = this.propertiesPanel ? this.propertiesPanel.offsetHeight : 0;

                startResize(startX, startY, target, isMobile, startToolbarWidth, startPropsWidth, startToolbarHeight, startPropsHeight);
            });

            // Mobile / touch
            resizer.addEventListener('touchstart', (e) => {
                if (!e.touches || !e.touches.length) return;
                e.preventDefault();

                const touch = e.touches[0];
                const target = resizer.dataset.resizeTarget;
                const isMobile = true; // при touch считаем, что мобильный сценарий

                const startX = touch.clientX;
                const startY = touch.clientY;

                const startToolbarWidth = this.toolbarPanel ? this.toolbarPanel.offsetWidth : 0;
                const startPropsWidth = this.propertiesPanel ? this.propertiesPanel.offsetWidth : 0;
                const startToolbarHeight = this.toolbarPanel ? this.toolbarPanel.offsetHeight : 0;
                const startPropsHeight = this.propertiesPanel ? this.propertiesPanel.offsetHeight : 0;

                const { handleMove, onMouseUp } = startResize(
                    startX,
                    startY,
                    target,
                    isMobile,
                    startToolbarWidth,
                    startPropsWidth,
                    startToolbarHeight,
                    startPropsHeight
                );

                const onTouchMove = (moveEvent) => {
                    if (!moveEvent.touches || !moveEvent.touches.length) return;
                    const t = moveEvent.touches[0];
                    handleMove(t.clientX, t.clientY);
                };

                const onTouchEnd = () => {
                    document.removeEventListener('touchmove', onTouchMove);
                    document.removeEventListener('touchend', onTouchEnd);
                    onMouseUp();
                };

                document.addEventListener('touchmove', onTouchMove, { passive: false });
                document.addEventListener('touchend', onTouchEnd);
            }, { passive: false });
        });
    }

    handleWindowResize() {
        this.syncDesktopPanelLayout();
        // Get current canvas dimensions
        const canvasRect = this.canvas.getBoundingClientRect();
        const maxCanvasWidth = this.getMaxCanvasWidth();
        // Use actual canvas width for proper mobile scaling
        const fullWidth = canvasRect.width;

        // Update all canvas elements to match new canvas width
        const canvasElements = this.canvas.querySelectorAll('.canvas-element');
        canvasElements.forEach(element => {
            // Update width for all elements to actual canvas width
            element.style.width = fullWidth + 'px';

            const toolId = element.dataset.toolId;

            // Special handling for canvas/image elements
            if (toolId === 'boardCanvas' || toolId === 'board-illustration') {
                const canvasOrImg = element.querySelector('canvas, img');
                if (canvasOrImg) {
                    canvasOrImg.style.maxWidth = fullWidth + 'px';
                    canvasOrImg.style.width = '100%';
                    canvasOrImg.style.height = 'auto';
                }
            }

            // Special handling for uploaded images - recalculate smart height
            if (toolId === 'upload-image') {
                const oldHeight = parseInt(element.style.height, 10);
                const smartHeight = this.applyResponsiveUploadImageLayout(element, { targetWidth: fullWidth });
                // If height changed, reposition elements below
                if (smartHeight != null && oldHeight !== smartHeight) {
                    this.repositionElementsBelow(element.id);
                }
            }

            if (toolId === 'attach-file') {
                element.style.height = '72px';
            }

            // Special handling for tables
            if (element.classList.contains('table-element') || toolId === 'moveHintsTable') {
                const table = element.querySelector('table');
                if (table) {
                    table.style.width = '100%';
                    this.applyContentTableMarkupClasses(element);
                }
            }

            if (toolId === 'question-text' || toolId === 'answer-text' || toolId === 'support-link') {
                this.autoGrowTextElementContainer(element, { skipReposition: true });
            }
        });

        // After updating all element sizes, recalculate positions for all elements
        this.recalculateAllElementPositions();

        // Ensure canvas height is appropriate after resize
        const allElements = this.canvas.querySelectorAll('.canvas-element');
        if (allElements.length > 0) {
            const lastElement = Array.from(allElements).reduce((last, current) => {
                const lastBottom = parseInt(last.style.top) + last.offsetHeight;
                const currentBottom = parseInt(current.style.top) + current.offsetHeight;
                return currentBottom > lastBottom ? current : last;
            });

            const maxBottom = parseInt(lastElement.style.top) + lastElement.offsetHeight;
            this.expandCanvasIfNeeded(maxBottom);
        }
    }

    recalculateAllElementPositions() {
        // Get all elements sorted by their current top position
        const allElements = Array.from(this.canvas.querySelectorAll('.canvas-element'))
            .filter(el => !el.id.includes('boardLabel'))
            .sort((a, b) => parseInt(a.style.top) - parseInt(b.style.top));

        const canvasRect = this.canvas.getBoundingClientRect();
        const elementSpacing = 0; // No spacing between elements
        let nextY = 0; // Start from top

        // Recalculate positions for all elements
        allElements.forEach(element => {
            let elementHeight;

            // Get actual height of element
            if (element.classList.contains('table-element')) {
                if (element.classList.contains('editor-table--collapsed')) {
                    elementHeight = 28;
                } else {
                    elementHeight = element.offsetHeight;
                    if (elementHeight < 50) {
                        elementHeight = 100; // Default for empty tables
                    }
                }
            } else if (element.dataset.toolId === 'upload-image') {
                // For images, use the current styled height
                elementHeight = parseInt(element.style.height) || 200;
            } else if (element.dataset.toolId === 'attach-file') {
                elementHeight = parseInt(element.style.height, 10) || 72;
            } else {
                elementHeight = parseInt(element.style.height) || element.offsetHeight || 150;
            }

            // Update position
            element.style.top = nextY + 'px';
            element.style.left = '0px'; // Always align to left
            element.style.width = canvasRect.width + 'px'; // Full canvas width

            // Move to next position
            nextY += elementHeight + elementSpacing;
        });

        // Expand canvas if needed after recalculating all positions
        this.expandCanvasIfNeeded(nextY);
    }

    setupCanvasEvents() {
        // Клик по элементу для выделения и открытия свойств
        this.canvas.addEventListener('mousedown', (e) => {
            const canvasElement = e.target.closest('.canvas-element');
            if (canvasElement && !e.target.classList.contains('control-btn')) {
                this.selectElement(canvasElement);
            }
        });
    }


    deselectAll() {
        document.querySelectorAll('.canvas-element').forEach(el => {
            el.classList.remove('selected');
        });
        this.selectedElement = null;
        this.applyPropertiesEmptyState();
    }

    openCanvasSettingsModal() {
        return openCanvasSettingsModalImpl(this);
    }

    switchCanvasSettingsTab(tab) {
        return switchCanvasSettingsTabImpl(this, tab);
    }

    applyCanvasSettingsActiveTab() {
        return applyCanvasSettingsActiveTabImpl(this);
    }

    applyGlobalCanvasTextSettings() {
        if (!this.syncGlobalTextStyleDefaultsFromFormAndApplyAll()) {
            this.closeCanvasSettingsModal();
            return;
        }
        const n = this.canvas ? this.canvas.querySelectorAll('.text-content, .link-text').length : 0;
        if (n > 0) {
            this.showNotification('Стиль текста применён ко всем текстовым блокам', 'success');
        } else {
            this.showNotification('Настройки сохранены — такой текст получат новые блоки', 'success');
        }
        this.closeCanvasSettingsModal();
    }

    renderPresetColors() {
        return renderPresetColorsImpl(this);
    }

    setupPresetColorHandlers() {
        return setupPresetColorHandlersImpl(this);
    }

    addPresetColor() {
        return addPresetColorImpl(this);
    }

    deletePresetColor(index) {
        return deletePresetColorImpl(this, index);
    }

    showNotification(message, type = 'info') {
        // Создаем уведомление
        const notification = document.createElement('div');
        notification.className = `canvas-notification canvas-notification-${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <i class="fa fa-${this.getNotificationIcon(type)}"></i>
                <span>${message}</span>
            </div>
        `;

        // Добавляем в DOM
        document.body.appendChild(notification);

        // Показываем уведомление
        setTimeout(() => notification.classList.add('show'), 10);

        // Автоматически скрываем через 3 секунды
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    getNotificationIcon(type) {
        const icons = {
            'success': 'check-circle',
            'warning': 'exclamation-triangle',
            'info': 'info-circle',
            'error': 'times-circle'
        };
        return icons[type] || 'info-circle';
    }

    openCanvasPatternImagePicker() {
        return openCanvasPatternImagePickerImpl(this);
    }

    handleCanvasPatternFileInput(inputEl) {
        return handleCanvasPatternFileInputImpl(this, inputEl);
    }

    refreshCanvasPatternPreviewInModal() {
        return refreshCanvasPatternPreviewInModalImpl(this);
    }

    closeCanvasSettingsModal() {
        return closeCanvasSettingsModalImpl(this);
    }

    applyCanvasBackground() {
        return applyCanvasBackgroundImpl(this);
    }

    rgbToHex(rgb) {
        // Конвертация RGB в HEX
        if (rgb.startsWith('#')) {
            return rgb;
        }

        const result = rgb.match(/\d+/g);
        if (!result || result.length < 3) {
            return '#ffffff';
        }

        const r = parseInt(result[0]);
        const g = parseInt(result[1]);
        const b = parseInt(result[2]);

        return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
    }

    normalizeBackgroundColorForInput(value) {
        const raw = String(value || '').trim();
        if (!raw || /^transparent$/i.test(raw)) return '#ffffff';
        const rgba = raw.match(/rgba?\(([^)]+)\)/i);
        if (rgba) {
            const parts = rgba[1].split(',').map((x) => x.trim());
            if (parts.length >= 4) {
                const alpha = parseFloat(parts[3]);
                if (!Number.isNaN(alpha) && alpha <= 0) {
                    return '#ffffff';
                }
            }
        }
        return this.rgbToHex(raw || '#ffffff');
    }

    /** Фон обёртки canvas-element: прозрачный дефолт или без заливки. */
    isCanvasElementBackgroundTransparent(element) {
        if (!element) return true;
        const inline = String(element.style.backgroundColor || '').trim();
        if (/^transparent$/i.test(inline)) return true;
        const inlineCompact = inline.replace(/\s/g, '');
        if (/^rgba?\(0,0,0,0\)$/i.test(inlineCompact)) return true;
        if (inline) return false;
        const n = String(window.getComputedStyle(element).backgroundColor || '').trim().toLowerCase();
        return !n || n === 'transparent' || n === 'rgba(0, 0, 0, 0)' || n === 'rgba(0,0,0,0)';
    }

    getBlockBackgroundColorForInput(element) {
        if (!element) return '#ffffff';
        const inline = String(element.style.backgroundColor || '').trim();
        if (inline) {
            return this.normalizeBackgroundColorForInput(inline);
        }
        const computed = window.getComputedStyle(element).backgroundColor || '';
        const normalizedComputed = String(computed).trim().toLowerCase();
        if (
            normalizedComputed &&
            normalizedComputed !== 'transparent' &&
            normalizedComputed !== 'rgba(0, 0, 0, 0)' &&
            normalizedComputed !== 'rgba(0,0,0,0)'
        ) {
            return this.normalizeBackgroundColorForInput(computed);
        }
        return '#ffffff';
    }

    // Method to force complete reload of the editor
    forceReload() {
        this.clearPreviewEditSession();
        // Clear all elements
        this.elements = [];
        if (this.canvas) {
            this.resetCanvasDomStructure();
        }

        // Reset properties
        this.selectedElement = null;
        this.applyPropertiesEmptyState();

        // Reset toggle states
        this.toggleStates = {};

        // Reload tools
        this.loadTools();

        // Force refresh
        this.forceRefreshContent();
    }
}

export default ContentEditor;
