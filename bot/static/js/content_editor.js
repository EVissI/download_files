/**
 * Content Editor Module
 * Редактор контента в стиле Photoshop
 */

class ContentEditor {
    constructor() {
        this.modal = null;
        this.canvas = null;
        this.toolsList = null;
        this.propertiesContent = null;
        this.selectedElement = null;
        this.elements = [];
        this.elementIdCounter = 0;
        this.toggleStates = {}; // Для отслеживания состояния toggle-кнопок
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
        this._onCardPreviewResize = () => this.refreshCardPreviewScale();

        /** Редактор открыт из предпросмотра карточки — одна кнопка «Сохранить», перезапись того же кадра */
        this.editorOpenedFromPreview = false;
        this.previewEditStorageKey = null;
        this.previewEditFrameId = null;
        this.previewEditSaveSlotIndex = null;
        /** После сохранения из предпросмотра-редактора — открыть предпросмотр на этом кадре */
        this._resumePreviewStorageKey = null;

        /** Кэш загрузки PNG для оверлея доски в предпросмотре */
        this._boardPreviewAssetsPromise = null;

        /** Модалка меток карточки (целиком, не на отдельный кадр) */
        this.cardLabelsModal = null;
        this.cardLabelsDraft = [];

        /** Кэш открытой IndexedDB для больших аудио (вне квоты localStorage JSON) */
        this._contentEditorMediaDbPromise = null;

        /** Глобальный стиль текста: новые блоки + значения вкладки «Текст» в настройках */
        this.globalTextStyleDefaults = { ...ContentEditor.DEFAULT_GLOBAL_TEXT_STYLE };

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
        if (typeof window !== 'undefined' && window.__CONTENT_CARD_VIEW_ONLY__) {
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
        this._contentCardTopLabels = [];
        this._contentCardViewFileName = '';
        if (!document.getElementById('contentCardViewRoot')) {
            document.body.insertAdjacentHTML('beforeend', `
                <div id="contentCardViewRoot" class="card-preview-modal card-preview-modal--fullscreen" style="display: none; min-height: 100vh;" aria-hidden="true">
                    <div class="card-preview-box" style="width: 100%; max-width: 100%; box-sizing: border-box;">
                        <div class="card-preview-header">
                            <h3 class="card-preview-title" id="contentCardViewTitle">Карточка</h3>
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
            `);
        }
        this.cardPreviewModal = document.getElementById('contentCardViewRoot');
        this.cardLabelsModal = null;
        this.modal = null;
        this.canvas = null;
        this.toolsList = null;
        this.propertiesContent = null;
    }

    async bootstrapContentCardViewPage() {
        const params = new URLSearchParams(window.location.search);
        const cardId = params.get('content_card_id');
        const metaHost = document.getElementById('cardPreviewMeta');
        const showErr = (msg) => {
            const t = this.escapeHtml(msg);
            if (metaHost) {
                metaHost.innerHTML = `<span class="card-preview-meta-empty">${t}</span>`;
            }
            if (this.cardPreviewModal) {
                this.cardPreviewModal.style.display = 'flex';
                this.cardPreviewModal.setAttribute('aria-hidden', 'false');
            }
        };
        if (!cardId) {
            showErr('Не указан content_card_id в адресе страницы');
            return;
        }
        const initData = (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || '';
        if (!initData) {
            showErr('Откройте страницу из Telegram (нужен initData)');
            return;
        }
        try {
            const r = await fetch('/api/content_cards/fetch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    init_data: initData,
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
            if (titleEl && data.file_name) {
                titleEl.textContent = data.file_name;
            }
            this._contentCardViewFileName = data.file_name || '';
            this._contentCardTopLabels = Array.isArray(data.labels) ? data.labels : [];
            const fw = data.frames || {};
            const framesArr = Array.isArray(fw.frames) ? fw.frames.slice() : [];
            framesArr.sort((a, b) => (a.order != null ? a.order : 0) - (b.order != null ? b.order : 0));
            this.cardPreviewRefs = framesArr.map((f) => ({
                frameId: f.frameId,
                saveSlotIndex: f.saveSlotIndex != null ? f.saveSlotIndex : 0,
                payload: f.payload,
                storageKey: null,
            }));
            this.cardPreviewIndex = 0;
            if (this.cardPreviewModal) {
                this.cardPreviewModal.style.display = 'flex';
                this.cardPreviewModal.setAttribute('aria-hidden', 'false');
            }
            document.body.style.overflow = 'hidden';
            window.addEventListener('resize', this._onCardPreviewResize);
            this.refreshCardPreviewUI();
        } catch (e) {
            console.error('bootstrapContentCardViewPage:', e);
            showErr(e.message || String(e));
        }
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
                            </div>
                            <div class="editor-resizer editor-resizer-vertical" data-resize-target="toolbar"></div>
                            <div class="workspace">
                                <div class="canvas" id="canvas">
                                    <!-- Здесь будут размещаться элементы -->
                                </div>
                            </div>
                            <div class="editor-resizer editor-resizer-vertical" data-resize-target="properties"></div>
                            <div class="properties-panel toolbar-properties">
                                <h3>Свойства</h3>
                                <div id="propertiesContent">
                                    <p>Выберите элемент для редактирования</p>
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

        if (!document.getElementById('cardPreviewModal')) {
            document.body.insertAdjacentHTML('beforeend', `
                <div id="cardPreviewModal" class="card-preview-modal card-preview-modal--fullscreen" style="display: none;" aria-hidden="true">
                    <div class="card-preview-overlay" onclick="contentEditor.closeCardPreviewModal()"></div>
                    <div class="card-preview-box" role="dialog" aria-modal="true">
                        <div class="card-preview-header">
                            <h3 class="card-preview-title">Предпросмотр карточки</h3>
                            <div class="card-preview-header-right">
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
                        <h3 id="cardLabelsModalTitle" class="card-labels-title">Метки карточки</h3>
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
            `);
        }
        this.cardLabelsModal = document.getElementById('cardLabelsModal');
        const labelsInput = document.getElementById('cardLabelsInput');
        if (labelsInput) {
            labelsInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.addCardLabelFromInput();
                }
            });
        }

        this.canvas = document.getElementById('canvas');
        this.toolsList = document.getElementById('toolsList');
        this.propertiesContent = document.getElementById('propertiesContent');

        // Дополнительные ссылки на панели для ресайза
        this.toolbarPanel = this.modal.querySelector('.toolbar');
        this.workspacePanel = this.modal.querySelector('.workspace');
        this.propertiesPanel = this.modal.querySelector('.properties-panel');
        this.applyPropertiesEmptyState();
    }

    /** Кнопки «Сохранить кадр» / «Предпросмотр» или «Сохранить» из режима предпросмотра (без обёртки). */
    getPropertiesFrameActionsInnerHtml() {
        if (this.editorOpenedFromPreview) {
            return `<button type="button" class="action-btn save-from-preview-btn" onclick="contentEditor.confirmSaveFromPreviewEditor()">Сохранить</button>`;
        }
        return `<button type="button" class="action-btn save-frame-inline-btn" onclick="contentEditor.openSaveFrameConfirm()">Сохранить кадр</button>
                <button type="button" class="action-btn save-card-inline-btn" onclick="contentEditor.openCardPreviewModal()">Предпросмотр</button>`;
    }

    getPropertiesEmptyStateHtml() {
        return `<p>Выберите элемент для редактирования</p>
            <div class="action-buttons action-buttons-col">${this.getPropertiesFrameActionsInnerHtml()}</div>`;
    }

    applyPropertiesEmptyState() {
        if (this.propertiesContent) {
            this.propertiesContent.innerHTML = this.getPropertiesEmptyStateHtml();
        }
    }

    clearPreviewEditSession() {
        this.editorOpenedFromPreview = false;
        this.previewEditStorageKey = null;
        this.previewEditFrameId = null;
        this.previewEditSaveSlotIndex = null;
    }

    openModal() {
        this.clearPreviewEditSession();
        // Force cache-busting by adding timestamp to modal
        const timestamp = Date.now();
        if (this.modal) {
            this.modal.setAttribute('data-cache-timestamp', timestamp);
        }

        this.modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        this.loadTools(); // Обновляем инструменты при открытии

        // Force refresh of all dynamic content
        this.forceRefreshContent();
    }

    closeModal() {
        this.modal.style.display = 'none';
        document.body.style.overflow = 'auto';
        this.clearPreviewEditSession();
    }

    /**
     * @param {object|null} cardData
     * @param {{ fromPreviewRestore?: boolean }} [options] — если true, не сбрасываем сессию «из предпросмотра»
     */
    openModalWithData(cardData, options = {}) {
        if (!options.fromPreviewRestore) {
            this.clearPreviewEditSession();
        }
        // Force cache-busting by adding timestamp to modal
        const timestamp = Date.now();
        if (this.modal) {
            this.modal.setAttribute('data-cache-timestamp', timestamp);
        }

        this.modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        this.loadTools(); // Обновляем инструменты при открытии

        // Сохраняем данные карточки для использования при выборе инструмента таблицы
        this.cardData = cardData;

        // Force refresh of all dynamic content
        this.forceRefreshContent();
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
                <table style="width: 100%; border-collapse: collapse; font-size: 12px; table-layout: fixed; margin: 0; padding: 0; border-spacing: 0;">
                    <thead>
                        <tr style="background: #f0f0f0;">
                            <th style="border: 1px solid #ddd; padding: 4px;">Ход</th>
                            <th style="border: 1px solid #ddd; padding: 4px;">Вероятность</th>
                            <th style="border: 1px solid #ddd; padding: 4px;">Результат</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td style="border: 1px solid #ddd; padding: 4px;">8/6</td>
                            <td style="border: 1px solid #ddd; padding: 4px;">0.654</td>
                            <td style="border: 1px solid #ddd; padding: 4px;">+0.123</td>
                        </tr>
                        <tr>
                            <td style="border: 1px solid #ddd; padding: 4px;">13/9</td>
                            <td style="border: 1px solid #ddd; padding: 4px;">0.598</td>
                            <td style="border: 1px solid #ddd; padding: 4px;">-0.045</td>
                        </tr>
                    </tbody>
                </table>
            `;
        }

        element.classList.add('table-element');

        // Debug: Log position preservation
        console.log('Table position after createTableElement:', {
            top: element.style.top,
            left: element.style.left,
            width: element.style.width,
            height: element.style.height
        });
    }

    updateTableContent(element, tableType) {
        // Debug: Log position before update
        console.log('updateTableContent - before:', {
            top: element.style.top,
            left: element.style.left,
            width: element.style.width,
            height: element.style.height
        });

        element.dataset.tableType = tableType;
        element.innerHTML = '';

        if (!this.cardData) {
            // Если нет данных, показываем заглушку
            element.innerHTML = `
                <div style="padding: 20px; text-align: center; color: #666;">
                    <strong>Нет данных для таблицы</strong>
                </div>
            `;
        } else {
            if (tableType === 'hints' && this.cardData.hints) {
                const table = this.createHintsTable(this.cardData.hints);
                element.appendChild(table);
            } else if (tableType === 'cube' && this.cardData.cube_hints) {
                const table = this.createCubeTable(this.cardData.cube_hints);
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

        // Debug: Log position after update
        console.log('updateTableContent - after:', {
            top: element.style.top,
            left: element.style.left,
            width: element.style.width,
            height: element.style.height
        });
    }

    createHintsTable(hints) {
        const table = document.createElement('table');
        table.style.cssText = `
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
            table-layout: fixed;
            margin: 0;
            padding: 0;
            border-spacing: 0;
        `;

        // Заголовок таблицы
        const header = table.createTHead();
        const headerRow = header.insertRow();
        const headers = ['Ход', '%', '%', 'Эквити'];

        headers.forEach(text => {
            const th = document.createElement('th');
            th.textContent = text;
            th.style.cssText = `
                background: #4CAF50;
                color: white;
                text-align: left;
                border: 1px solid #ddd;
                font-weight: bold;
            `;
            headerRow.appendChild(th);
        });

        // Тело таблицы
        const tbody = table.createTBody();
        hints.forEach((hint, index) => {
            const row = tbody.insertRow();

            // Ход
            const moveCell = row.insertCell();
            moveCell.textContent = hint.move || 'N/A';
            moveCell.style.cssText = 'padding: 6px; border: 1px solid #ddd; font-weight: bold;';

            // Win%
            const winCell = row.insertCell();
            winCell.textContent = hint.probs && hint.probs[0] ? (hint.probs[0] * 100).toFixed(1) : 'N/A';
            winCell.style.cssText = 'padding: 6px; border: 1px solid #ddd; text-align: center;';

            // Wg%
            const wgCell = row.insertCell();
            wgCell.textContent = hint.probs && hint.probs[1] ? (hint.probs[1] * 100).toFixed(1) : 'N/A';
            wgCell.style.cssText = 'padding: 6px; border: 1px solid #ddd; text-align: center;';

            // Эквити
            const eqCell = row.insertCell();
            eqCell.textContent = hint.eq ? hint.eq.toFixed(3) : 'N/A';
            eqCell.style.cssText = 'padding: 6px; border: 1px solid #ddd; text-align: center; font-weight: bold;';
        });

        return table;
    }

    createCubeTable(cubeHints) {
        const table = document.createElement('table');
        table.style.cssText = `
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
            table-layout: fixed;
            margin: 0;
            padding: 0;
            border-spacing: 0;
        `;

        // Заголовок таблицы
        const header = table.createTHead();
        const headerRow = header.insertRow();
        const headers = ['Действие', 'Эквити'];

        headers.forEach(text => {
            const th = document.createElement('th');
            th.textContent = text;
            th.style.cssText = `
                background: #FF9800;
                color: white;
                text-align: left;
                border: 1px solid #ddd;
                font-weight: bold;
            `;
            headerRow.appendChild(th);
        });

        // Тело таблицы
        const tbody = table.createTBody();
        if (cubeHints[0] && cubeHints[0].cubeful_equities) {
            cubeHints[0].cubeful_equities.forEach(eq => {
                const row = tbody.insertRow();

                // Действие
                const actionCell = row.insertCell();
                const action = eq.action_1 || '';
                if (eq.action_2) {
                    actionCell.textContent = `${action} / ${eq.action_2}`;
                } else {
                    actionCell.textContent = action;
                }
                actionCell.style.cssText = 'padding: 6px; border: 1px solid #ddd; font-weight: bold;';

                // Эквити
                const eqCell = row.insertCell();
                eqCell.textContent = eq.eq ? eq.eq.toFixed(3) : 'N/A';
                eqCell.style.cssText = 'padding: 6px; border: 1px solid #ddd; text-align: center; font-weight: bold;';
            });
        }

        return table;
    }

    /** Высота блока при пересчёте вертикального стека (как в recalculateAllElementPositions). */
    getElementStackHeight(element) {
        if (element.classList.contains('table-element')) {
            let h = element.offsetHeight;
            if (h < 50) h = 100;
            return h;
        }
        if (element.dataset.toolId === 'upload-image') {
            return parseInt(element.style.height, 10) || element.offsetHeight || 200;
        }
        return parseInt(element.style.height, 10) || element.offsetHeight || 150;
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
                name: 'Загрузить изображение',
                type: 'image',
                description: 'Загрузить изображение с локального хранилища',
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

        // Особое поведение для upload-image - прямая загрузка файла
        if (toolId === 'upload-image') {
            this.handleDirectImageUpload();
            return;
        }

        // Особое поведение для audio-file - прямая загрузка файла
        if (toolId === 'audio-file') {
            this.handleDirectAudioUpload();
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

    handleDirectImageUpload() {
        // Создаем временный input для выбора файла
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = 'image/*';
        fileInput.style.display = 'none';

        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file && file.type.startsWith('image/')) {
                this.uploadImageDirectly(file);
            }
            // Удаляем временный input
            document.body.removeChild(fileInput);
        });

        // Добавляем input в DOM и вызываем клик
        document.body.appendChild(fileInput);
        fileInput.click();
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

    addAudioElementToCanvas(audioUrl, fileName, file) {
        const elementId = `element_${this.elementIdCounter++}`;
        const element = document.createElement('div');
        element.id = elementId;
        element.className = 'canvas-element audio-element';
        element.dataset.toolId = 'audio-file';
        element.dataset.audioUrl = audioUrl;
        element.dataset.audioName = fileName;

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
                    <div class="audio-name" style="font-size: 14px; font-weight: 500; color: #333; margin-bottom: 4px;">${fileName}</div>
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
        this.canvas.appendChild(element);

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

        // Get audio duration
        audio.addEventListener('loadedmetadata', () => {
            const duration = audio.duration;
            const minutes = Math.floor(duration / 60);
            const seconds = Math.floor(duration % 60);
            durationEl.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
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
            // Calculate smart height based on aspect ratio
            const aspectRatio = img.naturalHeight / img.naturalWidth;
            const smartHeight = Math.max(100, Math.min(600, canvasWidth * aspectRatio));

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
            this.canvas.appendChild(element);

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
        const changedHeight = changedElement.offsetHeight;
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
                elementHeight = element.offsetHeight;
                if (elementHeight < 50) {
                    elementHeight = 100; // Default for empty tables
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
            this.canvas.appendChild(element);

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
                const atc = element.querySelector('.text-content');
                if (atc) this.applyGlobalTextStyleDefaultsToTextNode(atc);
                this.setupTextEditing(element);
                break;
            }

            case 'support-link': {
                element.innerHTML = `
                    <div class="link-content">
                        <div class="link-text" contenteditable="true" placeholder="Введите текст ссылки...">Ссылка</div>
                        <input type="hidden" class="link-url" value="">
                    </div>
                `;
                element.classList.add('link-element');
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
            this.saveSelectionForEditable(linkText);
            if (linkText.textContent.trim() === '') {
                linkText.textContent = 'Ссылка';
            }
        });

        linkText.addEventListener('input', scheduleLinkify);
        linkText.addEventListener('paste', () => {
            requestAnimationFrame(() => this.linkifyPlainUrlsUnderLinkElement(element));
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
                return;
            }
            if (!linkText.contains(e.target) || document.activeElement !== linkText) {
                const url = linkUrl.value;
                if (url && url.trim() !== '') {
                    window.open(url, '_blank', 'noopener,noreferrer');
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
        const textContent = element.querySelector('.text-content');
        if (!textContent) return;

        // Предотвращаем всплытие события клика, чтобы не выделять элемент при редактировании текста
        textContent.addEventListener('mousedown', (e) => {
            e.stopPropagation();
            if (e.target === textContent) {
                textContent.focus();
            }
        });

        // Добавляем обработчик фокуса для открытия свойств
        textContent.addEventListener('focus', () => {
            this.selectElement(element);
        });

        // Обработка окончания редактирования и сохранение выделения для форматирования
        textContent.addEventListener('blur', () => {
            this.saveSelectionForEditable(textContent);
            // Если текст пустой, возвращаем placeholder
            if (textContent.textContent.trim() === '') {
                if (element.dataset.toolId === 'question-text') {
                    textContent.textContent = 'Текст вопроса';
                } else if (element.dataset.toolId === 'answer-text') {
                    textContent.textContent = 'Текст ответа';
                }
            }
        });

        // Обработка ввода текста - только перенос строк
        textContent.addEventListener('input', () => {
            // Перенос строк работает через CSS, без автоматического изменения высоты
        });

        // Обработка клавиш для переноса строк
        textContent.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                textContent.blur();
            } else if (e.key === 'Enter') {
                // Разрешаем перенос по Shift+Enter или всегда для текстовых элементов
                if (e.shiftKey) {
                    // Shift+Enter - разрешаем перенос
                    return;
                } else {
                    // Обычный Enter - разрешаем перенос в текстовых элементах
                    e.preventDefault();
                    // Вставляем перенос строки
                    document.execCommand('insertLineBreak');
                    // Автоматическое изменение высоты отключено
                }
            }
        });
    }

    addElementControls(element) {
        const tid = element.dataset.toolId;
        if (!['question-text', 'answer-text', 'support-link'].includes(tid)) return;
        if (element.querySelector('.text-block-resize-handle')) return;
        const h = document.createElement('div');
        h.className = 'text-block-resize-handle';
        h.title = 'Потяните, чтобы изменить высоту';
        h.setAttribute('aria-hidden', 'true');
        element.appendChild(h);
    }

    beginTextBlockHeightDrag(element, startClientY) {
        const startH = element.getBoundingClientRect().height;
        const minH = 36;
        const maxH = this.canvas
            ? Math.max(this.canvas.scrollHeight, this.canvas.clientHeight) + 400
            : 2400;
        const prevUserSelect = document.body.style.userSelect;
        document.body.style.userSelect = 'none';

        element.classList.add('is-text-height-resizing');
        if (this.canvas) this.canvas.classList.add('ce-text-resize-active');

        let rafId = 0;
        let latestClientY = startClientY;

        const applyFrame = () => {
            rafId = 0;
            let nh = startH + (latestClientY - startClientY);
            nh = Math.max(minH, Math.min(maxH, nh));
            element.style.height = `${nh}px`;
            if (element.id) this.repositionElementsBelow(element.id);
        };

        const scheduleFrame = (clientY) => {
            latestClientY = clientY;
            if (!rafId) {
                rafId = requestAnimationFrame(applyFrame);
            }
        };

        const onMouseMove = (ev) => scheduleFrame(ev.clientY);
        const onMouseUp = () => cleanup();

        const onTouchMove = (ev) => {
            if (ev.cancelable) ev.preventDefault();
            if (ev.touches.length) scheduleFrame(ev.touches[0].clientY);
        };
        const onTouchEnd = () => cleanup();

        const cleanup = () => {
            if (rafId) {
                cancelAnimationFrame(rafId);
                rafId = 0;
            }
            applyFrame();
            element.style.height = `${Math.round(parseFloat(element.style.height) || element.offsetHeight)}px`;
            if (element.id) this.repositionElementsBelow(element.id);

            element.classList.remove('is-text-height-resizing');
            if (this.canvas) this.canvas.classList.remove('ce-text-resize-active');

            document.body.style.userSelect = prevUserSelect;
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            document.removeEventListener('touchmove', onTouchMove);
            document.removeEventListener('touchend', onTouchEnd);
            document.removeEventListener('touchcancel', onTouchEnd);
        };

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
        document.addEventListener('touchmove', onTouchMove, { passive: false });
        document.addEventListener('touchend', onTouchEnd);
        document.addEventListener('touchcancel', onTouchEnd);
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
            ? this.rgbToHex(window.getComputedStyle(linkTextEl).color || '#007bff')
            : '#007bff';

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
                    <input type="range" id="propFontSize" min="10" max="72" value="${parseInt(window.getComputedStyle(element.querySelector('.text-content')).fontSize) || 16}" 
                           oninput="contentEditor.updateElementProperty('fontSize', this.value + 'px')">
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
                    <input type="range" id="propLineHeight" min="10" max="30" value="${Math.round(parseFloat(window.getComputedStyle(element.querySelector('.text-content')).lineHeight) || 20)}"
                           oninput="contentEditor.updateElementProperty('lineHeight', this.value + 'px')">
                </div>
                <div class="property-item">
                    <label>Отступ внутри блока:</label>
                    <input type="range" id="propPadding" min="0" max="40" value="${parseInt(window.getComputedStyle(element).padding) || 8}"
                           oninput="contentEditor.updateElementProperty('padding', this.value + 'px')">
                </div>
                <div class="property-item">
                    <label>Цвет фона блока:</label>
                    <input type="color" id="propBgColor" value="${window.getComputedStyle(element).backgroundColor || '#ffffff'}"
                           oninput="contentEditor.updateElementProperty('backgroundColor', this.value)">
                </div>
                <div class="property-item">
                    <label>Форматирование:</label>
                    <div style="display:flex;gap:6px;">
                        <button class="action-btn" type="button" onclick="contentEditor.updateElementProperty('toggleBold')"><b>B</b></button>
                        <button class="action-btn" type="button" onclick="contentEditor.updateElementProperty('toggleItalic')"><i>I</i></button>
                        <button class="action-btn" type="button" onclick="contentEditor.updateElementProperty('toggleUnderline')"><u>U</u></button>
                    </div>
                </div>
                ` : ''}
                ${element.classList.contains('link-element') ? `
                <div class="property-item">
                    <label>Размер шрифта:</label>
                    <input type="range" id="propFontSize" min="10" max="72" value="${parseInt(window.getComputedStyle(element.querySelector('.link-text')).fontSize) || 16}" 
                           oninput="contentEditor.updateElementProperty('fontSize', this.value + 'px')">
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
                    <input type="url" id="propLinkUrl" value="${element.querySelector('.link-url').value}" 
                           placeholder="https://example.com"
                           oninput="contentEditor.updateElementProperty('linkUrl', this.value)">
                </div>
                ` : ''}
                ${element.classList.contains('audio-element') ? `
                <div class="property-item">
                    <label>Имя файла:</label>
                    <input type="text" id="propAudioName" value="${element.dataset.audioName || 'Аудио файл'}" 
                           oninput="contentEditor.updateElementProperty('audioName', this.value)">
                </div>
                <div class="property-item">
                    <label>Управление воспроизведением:</label>
                    <div style="display: flex; gap: 10px; margin-top: 5px;">
                        <button class="action-btn" onclick="contentEditor.playAudioElement('${element.id}')">▶ Воспроизвести</button>
                        <button class="action-btn" onclick="contentEditor.pauseAudioElement('${element.id}')">⏸ Пауза</button>
                    </div>
                </div>
                <div class="property-item">
                    <label>Громкость:</label>
                    <input type="range" id="propAudioVolume" min="0" max="100" value="100" 
                           oninput="contentEditor.updateElementProperty('audioVolume', this.value / 100)">
                    <div class="property-value">100%</div>
                </div>
                ` : ''}
            </div>
            
            <div class="action-buttons action-buttons-col">
                <button class="action-btn danger" onclick="contentEditor.deleteElement('${element.id}')">Удалить</button>
                ${this.getPropertiesFrameActionsInnerHtml()}
            </div>
        `;
    }

    updateElementProperty(property, value) {
        if (!this.selectedElement) return;

        switch (property) {
            case 'audioName':
                this.selectedElement.dataset.audioName = value;
                const audioNameEl = this.selectedElement.querySelector('.audio-name');
                if (audioNameEl) {
                    audioNameEl.textContent = value;
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
                const fontSizeDisplay = document.querySelector('#propFontSize + .property-value');
                if (fontSizeDisplay) fontSizeDisplay.textContent = value;
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
                const linkUrl = this.selectedElement.querySelector('.link-url');
                if (linkUrl) {
                    linkUrl.value = value;
                }
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
                }
                break;
            }
            case 'padding': {
                this.selectedElement.style.padding = value;
                break;
            }
            case 'backgroundColor': {
                this.selectedElement.style.backgroundColor = value;
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
                const aspectRatio = img.naturalHeight / img.naturalWidth;
                elementHeight = Math.max(100, Math.min(600, canvasRect.width * aspectRatio));
            } else {
                elementHeight = parseInt(element.style.height) || 200;
            }
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

        this.canvas.appendChild(newElement);
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
            if (this.cardLabelsModal && this.cardLabelsModal.style.display === 'flex') {
                this.cancelCardLabelsStep();
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
        const board = typeof window.getHintViewerBoardSnapshot === 'function'
            ? window.getHintViewerBoardSnapshot()
            : null;

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
                canvasBackground: this.getCanvasBackgroundForSave()
            },
            elements: await this.serializeCanvasElementsForSave()
        };
    }

    /** Надёжное чтение фона канваса (inline или computed), чтобы корректно восстанавливать после сохранения */
    getCanvasBackgroundForSave() {
        if (!this.canvas) return '#ffffff';
        const inline = (this.canvas.style.backgroundColor || '').trim();
        if (inline && inline !== 'transparent') {
            return this.canvas.style.backgroundColor;
        }
        const cs = window.getComputedStyle(this.canvas);
        const c = (cs.backgroundColor || '').trim();
        if (c && c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent') {
            return c;
        }
        return '#ffffff';
    }

    /** Фон канваса из сохранённого payload (предпросмотр / восстановление) */
    resolveSavedCanvasBackground(payload) {
        const raw = payload && payload.editor && payload.editor.canvasBackground;
        if (raw != null && String(raw).trim() !== '') {
            return String(raw).trim();
        }
        return '#ffffff';
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
        return {
            color: pick('color'),
            fontSize: pick('fontSize'),
            lineHeight: pick('lineHeight'),
            textAlign: pick('textAlign'),
            fontWeight: pick('fontWeight'),
            fontStyle: pick('fontStyle'),
            textDecoration: td && String(td).trim() ? td : cs.textDecoration,
            fontFamily: pick('fontFamily')
        };
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
                    item.textHtml = tc ? tc.innerHTML : '';
                    break;
                }
                case 'support-link': {
                    const lt = el.querySelector('.link-text');
                    const lu = el.querySelector('.link-url');
                    item.linkTextHtml = lt ? lt.innerHTML : '';
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
                    const s3a = el.dataset.audioS3Key || '';
                    if (s3a) {
                        item.audioS3Key = s3a;
                        item.audioName = el.dataset.audioName || '';
                        item.audioUrl = '';
                        item.audioStorageId = '';
                        item.dataset.audioS3Key = s3a;
                        delete item.dataset.audioUrl;
                        delete item.dataset.audioStorageId;
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
                    delete item.dataset.audioUrl;
                    if (item.audioStorageId) item.dataset.audioStorageId = item.audioStorageId;
                    else delete item.dataset.audioStorageId;
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
            this.canvas.innerHTML = '';
            this.canvas.style.backgroundColor = '#ffffff';
        }
        this.selectedElement = null;
        this.applyPropertiesEmptyState();
        this.toggleStates = {};
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
        const mat = rawMat.replace(/[\\/]/g, '_').trim() || 'card';
        const { gameId, gameNum } = this.getGameContextForCard();
        const g = gameNum != null ? `_g${gameNum}` : '';
        let base = `${mat}_${gameId}${g}`;
        if (base.length > 255) {
            base = base.slice(0, 255);
        }
        return base;
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
     */
    async uploadPayloadMediaToS3(payload) {
        if (!payload || !Array.isArray(payload.elements)) {
            return;
        }
        if (!window.Telegram || !window.Telegram.WebApp || !window.Telegram.WebApp.initData) {
            return;
        }
        for (const item of payload.elements) {
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
        } catch (e) {
            this.showNotification(e.message || String(e), 'error');
            return false;
        }
        const labels = this.loadCardLabelsFromStorage();
        const file_name = this.buildContentCardFileNameForCloud();
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
            const hint = data.updated ? ' (обновлено)' : '';
            this.showNotification('Карточка сохранена на сервере' + hint, 'success');
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
        if (!this.cardPreviewModal) return;
        this.cardPreviewRefs = this.collectSavedFrameRefsForCurrentGame();
        if (this._resumePreviewStorageKey) {
            const i = this.cardPreviewRefs.findIndex((r) => r.storageKey === this._resumePreviewStorageKey);
            this.cardPreviewIndex = i >= 0 ? i : 0;
            this._resumePreviewStorageKey = null;
        } else {
            this.cardPreviewIndex = 0;
        }
        this.cardPreviewModal.classList.add('card-preview-modal--fullscreen');
        this.cardPreviewModal.style.display = 'flex';
        this.cardPreviewModal.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
        window.addEventListener('resize', this._onCardPreviewResize);
        this.refreshCardPreviewUI();
    }

    closeCardPreviewModal() {
        if (!this.cardPreviewModal) return;
        window.removeEventListener('resize', this._onCardPreviewResize);
        this.cardPreviewModal.style.display = 'none';
        this.cardPreviewModal.setAttribute('aria-hidden', 'true');
        const editorStillOpen = this.modal && this.modal.style.display === 'flex';
        document.body.style.overflow = editorStillOpen ? 'hidden' : 'auto';
        const host = document.getElementById('cardPreviewFrameHost');
        if (host) host.innerHTML = '';
    }

    refreshCardPreviewUI() {
        const total = this.cardPreviewRefs.length;
        const counter = document.getElementById('cardPreviewCounter');
        const meta = document.getElementById('cardPreviewMeta');
        const prevBtn = document.getElementById('cardPreviewPrevBtn');
        const nextBtn = document.getElementById('cardPreviewNextBtn');
        const approveBtn = document.getElementById('cardPreviewApproveBtn');

        if (counter) {
            counter.textContent = total === 0 ? '0 / 0' : `${this.cardPreviewIndex + 1} / ${total}`;
        }
        if (prevBtn) prevBtn.disabled = total === 0 || this.cardPreviewIndex <= 0;
        if (nextBtn) nextBtn.disabled = total === 0 || this.cardPreviewIndex >= total - 1;
        if (approveBtn) approveBtn.disabled = total === 0;

        if (!meta) return;

        if (total === 0) {
            meta.innerHTML = '<span class="card-preview-meta-empty">Нет сохранённых кадров для этой игры</span>';
            this.renderCardPreviewSurface(null);
            return;
        }

        const ref = this.cardPreviewRefs[this.cardPreviewIndex];
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
        const labelsKey = this.getCardLabelsStorageKey();
        const hasStoredLabelsKey = localStorage.getItem(labelsKey) !== null;
        const storedLabels = hasStoredLabelsKey ? this.loadCardLabelsFromStorage() : null;
        const fallbackLabels = this._contentCardTopLabels && this._contentCardTopLabels.length
            ? this._contentCardTopLabels
            : [];
        const labelsToShow = hasStoredLabelsKey ? storedLabels : fallbackLabels;
        if (labelsToShow.length) {
            const topParts = labelsToShow
                .filter((t) => typeof t === 'string' && t.trim())
                .map((t) => `<span class="card-preview-label-chip">${this.escapeHtml(t.trim())}</span>`)
                .join(' ');
            if (topParts) {
                meta.insertAdjacentHTML(
                    'beforeend',
                    `<div class="card-preview-meta-line card-preview-meta-labels">Метки карточки: ${topParts}</div>`
                );
            }
        }
        this.renderCardPreviewSurface(payload);
    }

    /** В предпросмотре убираем пустой верх: сдвигаем все блоки так, чтобы верхний был у top: 0 */
    normalizePreviewStackTops(inner) {
        const children = Array.from(inner.querySelectorAll('.canvas-element'));
        if (!children.length) return;
        let minTop = Infinity;
        children.forEach((el) => {
            const t = parseInt(el.style.top, 10);
            if (!Number.isNaN(t)) minTop = Math.min(minTop, t);
        });
        if (!Number.isFinite(minTop) || minTop <= 0) return;
        children.forEach((el) => {
            const t = parseInt(el.style.top, 10);
            if (!Number.isNaN(t)) el.style.top = `${t - minTop}px`;
        });
    }

    shouldShowBoardInCardPreview(payload) {
        return !!(payload && payload.editor && payload.editor.boardCanvasToggle);
    }

    loadBoardPreviewImages() {
        if (this._boardPreviewAssetsPromise) return this._boardPreviewAssetsPromise;
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
            double64: '/static/Double64.png'
        };
        for (let i = 1; i <= 6; i++) {
            paths[`d${i}w`] = `/static/${i}w.png`;
            paths[`d${i}b`] = `/static/${i}b.png`;
        }
        this._boardPreviewAssetsPromise = Promise.all(
            Object.entries(paths).map(([key, url]) => loadOne(url).then((img) => [key, img]))
        ).then((pairs) => Object.fromEntries(pairs));
        return this._boardPreviewAssetsPromise;
    }

    getBoardPreviewPointX(point) {
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

    getBoardPreviewBaseY(point) {
        return (point > 12) ? 70 : 690;
    }

    getBoardPreviewDy(point) {
        return (point > 12) ? 55 : -55;
    }

    drawBoardPreviewCheckers(ctx, player, img, positions, currentPlayer, invertColors) {
        ctx.font = 'bold 30px Arial';
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        if (player === currentPlayer) {
            for (let point = 1; point <= 24; point++) {
                const x = this.getBoardPreviewPointX(point);
                let y = this.getBoardPreviewBaseY(point);
                const dy = this.getBoardPreviewDy(point);
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
            const x = this.getBoardPreviewPointX(point);
            const y = this.getBoardPreviewBaseY(point);
            const dy = this.getBoardPreviewDy(point);
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

    resolveBoardPositionsFromSnapshot(snapshot) {
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

    paintBoardPreviewCanvas(canvas, snapshot, imgs) {
        const ctx = canvas.getContext('2d');
        const w = canvas.width;
        const h = canvas.height;
        ctx.clearRect(0, 0, w, h);
        if (!imgs.board || !imgs.board.complete) return;
        ctx.drawImage(imgs.board, 0, 0, w, h);

        const invertColors = !!snapshot.invertColors;
        const resolved = this.resolveBoardPositionsFromSnapshot(snapshot);
        const turnRow = snapshot.turn;
        const currentPlayer = (turnRow && turnRow.player) ? String(turnRow.player).toLowerCase() : 'red';

        if (resolved) {
            this.drawBoardPreviewCheckers(ctx, 'red', imgs.white, resolved.redPositions, currentPlayer, invertColors);
            this.drawBoardPreviewCheckers(ctx, 'black', imgs.black, resolved.blackPositions, currentPlayer, invertColors);
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

        if (turnRow && turnRow.action === 'win' && imgs.double64) {
            ctx.drawImage(imgs.double64, 375, 350, 50, 50);
        }
    }

    appendCardPreviewBoardOverlay(wrap, payload) {
        const snapshot = payload.board && typeof payload.board === 'object' ? payload.board : {};
        const overlay = document.createElement('div');
        overlay.className = 'card-preview-board-overlay';
        overlay.innerHTML = `
            <div class="card-preview-board-body">
                <div class="card-preview-board-canvas-wrap">
                    <canvas class="card-preview-board-canvas" width="800" height="800" aria-hidden="true"></canvas>
                </div>
            </div>
            <button type="button" class="card-preview-board-handle" aria-expanded="true" aria-label="Свернуть или развернуть доску" title="Свернуть или развернуть доску">
                <span class="card-preview-board-handle-icon" aria-hidden="true">
                    <svg class="card-preview-board-caret-svg" viewBox="0 0 48 22" xmlns="http://www.w3.org/2000/svg" focusable="false">
                        <path fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round" d="M7 17 L24 5 L41 17"/>
                    </svg>
                </span>
            </button>
        `;
        const handleBtn = overlay.querySelector('.card-preview-board-handle');
        const toggleBoardCollapsed = () => {
            overlay.classList.toggle('card-preview-board-overlay--collapsed');
            const collapsed = overlay.classList.contains('card-preview-board-overlay--collapsed');
            handleBtn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
            requestAnimationFrame(() => this.refreshCardPreviewScale());
        };
        handleBtn.addEventListener('click', toggleBoardCollapsed);
        handleBtn.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleBoardCollapsed();
            }
        });

        wrap.appendChild(overlay);

        const canvas = overlay.querySelector('.card-preview-board-canvas');
        this.loadBoardPreviewImages()
            .then((imgs) => {
                if (!canvas.isConnected) return;
                this.paintBoardPreviewCanvas(canvas, snapshot, imgs);
                requestAnimationFrame(() => this.refreshCardPreviewScale());
            })
            .catch((err) => {
                console.error('appendCardPreviewBoardOverlay:', err);
            });
    }

    renderCardPreviewSurface(payload) {
        const host = document.getElementById('cardPreviewFrameHost');
        if (!host) return;
        host.innerHTML = '';
        host.style.backgroundColor = '';
        if (!payload) {
            return;
        }

        const list = Array.isArray(payload.elements) ? payload.elements : [];
        const canvasBg = this.resolveSavedCanvasBackground(payload);
        host.style.backgroundColor = canvasBg;

        const wrap = document.createElement('div');
        wrap.className = 'card-preview-surface-wrap';
        wrap.style.backgroundColor = canvasBg;
        const inner = document.createElement('div');
        inner.className = 'card-preview-surface-inner';
        inner.style.width = '100%';
        inner.style.position = 'relative';
        inner.style.boxSizing = 'border-box';
        inner.style.backgroundColor = canvasBg;

        let maxNum = 0;
        list.forEach(item => {
            const m = /^element_(\d+)$/.exec(item.id || '');
            if (m) maxNum = Math.max(maxNum, parseInt(m[1], 10) + 1);
        });
        const savedCounter = this.elementIdCounter;
        this.elementIdCounter = maxNum;
        list.forEach(item => {
            const el = this.deserializeCanvasElement(item, { previewMode: true });
            if (el) {
                el.style.width = '100%';
                el.style.left = '0px';
                el.style.boxSizing = 'border-box';
                inner.appendChild(el);
            }
        });
        this.elementIdCounter = savedCounter;

        this.normalizePreviewStackTops(inner);

        if (this.shouldShowBoardInCardPreview(payload)) {
            this.appendCardPreviewBoardOverlay(wrap, payload);
        }
        wrap.appendChild(inner);
        host.appendChild(wrap);

        inner.querySelectorAll('img').forEach((img) => {
            img.addEventListener('load', () => this.refreshCardPreviewScale());
        });

        requestAnimationFrame(() => {
            this.refreshCardPreviewScale();
        });
    }

    /**
     * Дети предпросмотра — position:absolute; без min-height у inner в потоке height≈0 и ломается высота скролла.
     * Высота обёртки предпросмотра учитывает доску в потоке (см. refreshCardPreviewScale).
     */
    updateCardPreviewInnerMinHeight(inner) {
        if (!inner) return;
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

    refreshCardPreviewScale() {
        const host = document.getElementById('cardPreviewFrameHost');
        if (!host) return;
        const inner = host.querySelector('.card-preview-surface-inner');
        const wrap = host.querySelector('.card-preview-surface-wrap');
        if (!inner || !wrap) return;

        inner.style.transform = 'none';
        this.updateCardPreviewInnerMinHeight(inner);
        const boardEl = wrap.querySelector('.card-preview-board-overlay');
        const boardH = boardEl ? Math.ceil(boardEl.offsetHeight) : 0;
        const innerH = Math.ceil(inner.offsetHeight);
        wrap.style.minHeight = `${boardH + innerH}px`;
    }

    escapeHtml(s) {
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    cardPreviewPrev() {
        if (this.cardPreviewIndex > 0) {
            this.cardPreviewIndex--;
            this.refreshCardPreviewUI();
        }
    }

    cardPreviewNext() {
        if (this.cardPreviewIndex < this.cardPreviewRefs.length - 1) {
            this.cardPreviewIndex++;
            this.refreshCardPreviewUI();
        }
    }

    cardPreviewApprove() {
        if (!this.cardPreviewRefs.length) {
            this.showNotification('Нет сохранённых кадров для этой игры', 'warning');
            return;
        }
        let labels = this.loadCardLabelsFromStorage();
        if (!labels.length && this._contentCardTopLabels && this._contentCardTopLabels.length) {
            labels = this._contentCardTopLabels.filter((x) => typeof x === 'string' && x.trim()).map((x) => x.trim());
        }
        if (!labels.length) {
            const withKeys = this.cardPreviewRefs.filter((r) => r.storageKey);
            if (withKeys.length) {
                labels = this.collectUnifiedLabelsFromFrameRefs(withKeys);
                if (labels.length) {
                    try {
                        this.saveCardLabelsToStorage(labels);
                    } catch (e) {
                        console.warn('cardPreviewApprove migrate labels:', e);
                    }
                }
            }
        }
        this.cardLabelsDraft = labels.slice();
        this.openCardLabelsModal();
    }

    openCardLabelsModal() {
        if (!this.cardLabelsModal) return;
        this.renderCardLabelsList();
        const input = document.getElementById('cardLabelsInput');
        if (input) input.value = '';
        this.cardLabelsModal.style.display = 'flex';
        this.cardLabelsModal.setAttribute('aria-hidden', 'false');
        requestAnimationFrame(() => {
            if (input) input.focus();
        });
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
        this.canvas.innerHTML = '';
        this.selectedElement = null;
        this.toggleStates = {};

        if (payload.editor && payload.editor.boardCanvasToggle) {
            this.toggleStates['boardCanvas'] = true;
        }
        this.cardData = null;
        if (payload.cardData && typeof payload.cardData === 'object') {
            try {
                this.cardData = JSON.parse(JSON.stringify(payload.cardData));
            } catch (e) {
                this.cardData = null;
            }
        }
        this.canvas.style.backgroundColor = this.resolveSavedCanvasBackground(payload);

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
                this.canvas.appendChild(el);
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
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                if (this.canvas && this.canvas.getBoundingClientRect().width > 0) {
                    this.handleWindowResize();
                }
                this.forceRefreshContent();
            });
        });
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
            if (item.style.height) element.style.height = item.style.height;
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
                element.innerHTML = `
                    <div class="link-content">
                        <div class="link-text" contenteditable="${ce}" placeholder="Введите текст ссылки...">${item.linkTextHtml || ''}</div>
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
            case 'audio-file':
                element.classList.add('audio-element');
                if (item.audioS3Key) {
                    element.dataset.audioS3Key = item.audioS3Key;
                }
                if (item.audioStorageId) element.dataset.audioStorageId = item.audioStorageId;
                if (item.audioName) element.dataset.audioName = item.audioName;
                if (item.audioUrl) element.dataset.audioUrl = item.audioUrl;
                element.innerHTML = `
                    <div class="audio-message" style="display: flex; align-items: center; padding: 12px; height: 100%; background: #f0f0f0; border-radius: 8px;">
                        <div class="audio-icon" style="font-size: 24px; margin-right: 12px; color: #667eea;">🎵</div>
                        <div class="audio-info" style="flex: 1;">
                            <div class="audio-name" style="font-size: 14px; font-weight: 500; color: #333; margin-bottom: 4px;">${this.escapeHtml(item.audioName || 'Аудио')}</div>
                            <div class="audio-duration" style="font-size: 12px; color: #666;">—</div>
                        </div>
                        <div class="audio-play-btn" style="width: 32px; height: 32px; border-radius: 50%; background: #667eea; color: white; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 16px;">▶</div>
                    </div>`;
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
                        let newHeight = startToolbarHeight + dy;
                        newHeight = Math.max(minPanelSize, Math.min(maxPanelSize, newHeight));
                        this.toolbarPanel.style.height = newHeight + 'px';
                    } else if (target === 'properties' && this.propertiesPanel) {
                        let newHeight = startPropsHeight - dy;
                        newHeight = Math.max(minPanelSize, Math.min(maxPanelSize, newHeight));
                        this.propertiesPanel.style.height = newHeight + 'px';
                    }
                }
            };

            const onMouseMove = (moveEvent) => {
                handleMove(moveEvent.clientX, moveEvent.clientY);
            };

            const onMouseUp = () => {
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
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
                const img = element.querySelector('img');
                if (img && img.naturalWidth && img.naturalHeight) {
                    const oldHeight = parseInt(element.style.height);

                    // Recalculate smart height based on new canvas width
                    const aspectRatio = img.naturalHeight / img.naturalWidth;
                    const smartHeight = Math.max(100, Math.min(600, fullWidth * aspectRatio));

                    element.style.height = smartHeight + 'px';
                    img.style.width = '100%';
                    img.style.height = '100%';
                    img.style.objectFit = 'contain';

                    // If height changed, reposition elements below
                    if (oldHeight !== smartHeight) {
                        this.repositionElementsBelow(element.id);
                    }
                }
            }

            // Special handling for tables
            if (element.classList.contains('table-element') || toolId === 'moveHintsTable') {
                const table = element.querySelector('table');
                if (table) {
                    table.style.width = '100%';
                }
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
                elementHeight = element.offsetHeight;
                if (elementHeight < 50) {
                    elementHeight = 100; // Default for empty tables
                }
            } else if (element.dataset.toolId === 'upload-image') {
                // For images, use the current styled height
                elementHeight = parseInt(element.style.height) || 200;
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
        // Клик по элементу для выделения и открытия свойств; ресайз высоты текстовых блоков
        this.canvas.addEventListener('mousedown', (e) => {
            const resizeHandle = e.target.closest('.text-block-resize-handle');
            if (resizeHandle) {
                const canvasElement = resizeHandle.closest('.canvas-element');
                if (canvasElement) {
                    e.preventDefault();
                    e.stopPropagation();
                    this.selectElement(canvasElement);
                    this.beginTextBlockHeightDrag(canvasElement, e.clientY);
                }
                return;
            }

            const canvasElement = e.target.closest('.canvas-element');
            if (canvasElement && !e.target.classList.contains('control-btn')) {
                this.selectElement(canvasElement);
            }
        });

        this.canvas.addEventListener(
            'touchstart',
            (e) => {
                const resizeHandle = e.target.closest('.text-block-resize-handle');
                if (!resizeHandle) return;
                const canvasElement = resizeHandle.closest('.canvas-element');
                if (!canvasElement) return;
                e.preventDefault();
                this.selectElement(canvasElement);
                this.beginTextBlockHeightDrag(canvasElement, e.touches[0].clientY);
            },
            { passive: false }
        );
    }


    deselectAll() {
        document.querySelectorAll('.canvas-element').forEach(el => {
            el.classList.remove('selected');
        });
        this.selectedElement = null;
        this.applyPropertiesEmptyState();
    }

    openCanvasSettingsModal() {
        this.closeCanvasSettingsModal();
        const d = this.globalTextStyleDefaults || ContentEditor.DEFAULT_GLOBAL_TEXT_STYLE;
        const textSize = parseInt(String(d.fontSize).replace(/px\s*$/i, ''), 10) || 16;
        let textColorHex = d.color || '#333333';
        if (textColorHex && !/^#[0-9A-F]{6}$/i.test(textColorHex)) {
            textColorHex = this.rgbToHex(textColorHex) || '#333333';
        }
        const textAlign = d.textAlign || 'left';
        let lineH = parseInt(String(d.lineHeight).replace(/px\s*$/i, ''), 10);
        if (Number.isNaN(lineH)) lineH = 20;
        const fontBold = d.fontWeight === 'bold' || parseInt(d.fontWeight, 10) >= 600;
        const fontItalic = d.fontStyle === 'italic';
        const fontUnderline = String(d.textDecoration || '').includes('underline');
        const firstFam = d.fontFamily ? d.fontFamily.split(',')[0].trim().replace(/^["']|["']$/g, '') : '';
        const fontFamilyOptions = [
            { value: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif', label: 'Системный' },
            { value: 'Arial, Helvetica, sans-serif', label: 'Arial' },
            { value: 'Georgia, "Times New Roman", serif', label: 'Georgia' },
            { value: '"Times New Roman", Times, serif', label: 'Times New Roman' },
            { value: 'Verdana, Geneva, sans-serif', label: 'Verdana' },
            { value: '"Courier New", Courier, monospace', label: 'Courier New' },
            { value: 'Tahoma, Geneva, sans-serif', label: 'Tahoma' }
        ];
        const fontSelectHtml = fontFamilyOptions.map((o) => {
            const v = String(o.value).replace(/&/g, '&amp;').replace(/"/g, '&quot;');
            return `<option value="${v}">${this.escapeHtml(o.label)}</option>`;
        }).join('');

        const modalHTML = `
            <div id="canvasSettingsModal" class="canvas-settings-modal" style="display: flex;">
                <div class="canvas-settings-overlay" onclick="contentEditor.closeCanvasSettingsModal()"></div>
                <div class="canvas-settings-container">
                    <div class="canvas-settings-header">
                        <h3>Настройки канваса</h3>
                        <button type="button" class="close-btn" onclick="contentEditor.closeCanvasSettingsModal()">&times;</button>
                    </div>
                    <div class="canvas-settings-tabs">
                        <button type="button" class="canvas-settings-tab-btn active" data-tab="background"
                            onclick="contentEditor.switchCanvasSettingsTab('background')">Фон</button>
                        <button type="button" class="canvas-settings-tab-btn" data-tab="text"
                            onclick="contentEditor.switchCanvasSettingsTab('text')">Текст</button>
                    </div>
                    <div class="canvas-settings-body-scroll">
                    <div class="canvas-settings-body">
                        <div id="canvasSettingsPanelBg" class="canvas-settings-tab-panel">
                            <div class="setting-group">
                                <label for="canvasBackgroundColor">Цвет фона:</label>
                                <div class="color-input-group">
                                    <input type="color" id="canvasBackgroundColor" value="#ffffff">
                                    <input type="text" id="canvasBackgroundText" value="#ffffff" placeholder="#ffffff">
                                </div>
                            </div>
                            <div class="setting-group">
                                <label>Предустановленные цвета:</label>
                                <div class="preset-colors" id="presetColorsContainer">
                                    ${this.renderPresetColors()}
                                </div>
                                <div class="preset-controls">
                                    <div class="preset-mode-toggle">
                                        <label class="checkbox-label">
                                            <input type="checkbox" id="deleteModeCheckbox">
                                            <span class="checkbox-custom"></span>
                                            <span class="checkbox-text">Режим удаления</span>
                                        </label>
                                    </div>
                                    <button type="button" class="add-preset-btn" onclick="contentEditor.addPresetColor()">
                                        <i class="fa fa-plus"></i> Добавить цвет
                                    </button>
                                </div>
                            </div>
                        </div>
                        <div id="canvasSettingsPanelText" class="canvas-settings-tab-panel" style="display: none;">
                            <p class="canvas-settings-tab-hint">Применяется ко всем текстовым блокам и подписям ссылок на кадре; после «Применить» те же настройки получают и новые блоки.</p>
                            <div class="setting-group">
                                <label for="globalTextFontSize">Размер шрифта: <span id="globalTextFontSizeLabel">${textSize}</span>px</label>
                                <input type="range" id="globalTextFontSize" min="10" max="72" value="${textSize}">
                            </div>
                            <div class="setting-group">
                                <label for="globalTextColor">Цвет текста:</label>
                                <div class="color-input-group">
                                    <input type="color" id="globalTextColor" value="${textColorHex}">
                                    <input type="text" id="globalTextColorText" value="${textColorHex}" placeholder="#333333">
                                </div>
                            </div>
                            <div class="setting-group">
                                <label for="globalTextAlign">Выравнивание:</label>
                                <select id="globalTextAlign">
                                    <option value="left" ${(textAlign === 'left' || textAlign === 'start') ? 'selected' : ''}>Слева</option>
                                    <option value="center" ${textAlign === 'center' ? 'selected' : ''}>По центру</option>
                                    <option value="right" ${(textAlign === 'right' || textAlign === 'end') ? 'selected' : ''}>Справа</option>
                                    <option value="justify" ${textAlign === 'justify' ? 'selected' : ''}>По ширине</option>
                                </select>
                            </div>
                            <div class="setting-group">
                                <label for="globalTextLineHeight">Межстрочный интервал: <span id="globalTextLineHeightLabel">${lineH}</span>px</label>
                                <input type="range" id="globalTextLineHeight" min="10" max="36" value="${lineH}">
                            </div>
                            <div class="setting-group">
                                <label for="globalTextFontFamily">Шрифт:</label>
                                <select id="globalTextFontFamily">${fontSelectHtml}</select>
                            </div>
                            <div class="setting-group canvas-settings-text-toggles">
                                <label class="checkbox-label">
                                    <input type="checkbox" id="globalTextBold" ${fontBold ? 'checked' : ''}>
                                    <span class="checkbox-custom"></span>
                                    <span class="checkbox-text"><strong>Жирный</strong></span>
                                </label>
                                <label class="checkbox-label">
                                    <input type="checkbox" id="globalTextItalic" ${fontItalic ? 'checked' : ''}>
                                    <span class="checkbox-custom"></span>
                                    <span class="checkbox-text"><em>Курсив</em></span>
                                </label>
                                <label class="checkbox-label">
                                    <input type="checkbox" id="globalTextUnderline" ${fontUnderline ? 'checked' : ''}>
                                    <span class="checkbox-custom"></span>
                                    <span class="checkbox-text"><u>Подчёркивание</u></span>
                                </label>
                            </div>
                        </div>
                    </div>
                    </div>
                    <div class="canvas-settings-footer">
                        <button type="button" class="cancel-btn" onclick="contentEditor.closeCanvasSettingsModal()">Отмена</button>
                        <button type="button" class="apply-btn" onclick="contentEditor.applyCanvasSettingsActiveTab()">Применить</button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);

        const currentBg = window.getComputedStyle(this.canvas).backgroundColor;
        const hexBg = this.rgbToHex(currentBg);
        document.getElementById('canvasBackgroundColor').value = hexBg;
        document.getElementById('canvasBackgroundText').value = hexBg;

        const ffSel = document.getElementById('globalTextFontFamily');
        if (ffSel && firstFam) {
            let matched = false;
            for (let i = 0; i < ffSel.options.length; i++) {
                const v = ffSel.options[i].value;
                if (firstFam.toLowerCase().includes(v.split(',')[0].trim().toLowerCase().replace(/["']/g, ''))
                    || v.toLowerCase().includes(firstFam.toLowerCase())) {
                    ffSel.selectedIndex = i;
                    matched = true;
                    break;
                }
            }
            if (!matched && d.fontFamily) {
                const opt = document.createElement('option');
                opt.value = d.fontFamily;
                opt.textContent = `Текущий (${firstFam})`;
                opt.selected = true;
                ffSel.insertBefore(opt, ffSel.firstChild);
            }
        }

        this.setupPresetColorHandlers();

        const colorPicker = document.getElementById('canvasBackgroundColor');
        const colorText = document.getElementById('canvasBackgroundText');
        colorPicker.addEventListener('input', (e) => {
            colorText.value = e.target.value;
        });
        colorText.addEventListener('input', (e) => {
            if (/^#[0-9A-F]{6}$/i.test(e.target.value)) {
                colorPicker.value = e.target.value;
            }
        });

        const gSize = document.getElementById('globalTextFontSize');
        const gSizeLabel = document.getElementById('globalTextFontSizeLabel');
        if (gSize && gSizeLabel) {
            gSize.addEventListener('input', () => { gSizeLabel.textContent = gSize.value; });
        }
        const gLh = document.getElementById('globalTextLineHeight');
        const gLhLabel = document.getElementById('globalTextLineHeightLabel');
        if (gLh && gLhLabel) {
            gLh.addEventListener('input', () => { gLhLabel.textContent = gLh.value; });
        }
        const gCol = document.getElementById('globalTextColor');
        const gColTxt = document.getElementById('globalTextColorText');
        if (gCol && gColTxt) {
            gCol.addEventListener('input', () => { gColTxt.value = gCol.value; });
            gColTxt.addEventListener('input', (e) => {
                if (/^#[0-9A-F]{6}$/i.test(e.target.value)) gCol.value = e.target.value;
            });
        }
    }

    switchCanvasSettingsTab(tab) {
        const modal = document.getElementById('canvasSettingsModal');
        if (!modal) return;
        modal.querySelectorAll('.canvas-settings-tab-btn').forEach((btn) => {
            btn.classList.toggle('active', btn.dataset.tab === tab);
        });
        const bg = document.getElementById('canvasSettingsPanelBg');
        const tx = document.getElementById('canvasSettingsPanelText');
        if (bg) bg.style.display = tab === 'background' ? 'block' : 'none';
        if (tx) tx.style.display = tab === 'text' ? 'block' : 'none';
    }

    applyCanvasSettingsActiveTab() {
        const modal = document.getElementById('canvasSettingsModal');
        const active = modal && modal.querySelector('.canvas-settings-tab-btn.active');
        const tab = active ? active.dataset.tab : 'background';
        if (tab === 'text') {
            this.applyGlobalCanvasTextSettings();
        } else {
            this.applyCanvasBackground();
        }
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
        return this.presetColors.map((color, index) => `
            <div class="preset-color" style="background: ${color};" data-color="${color}" data-index="${index}">
            </div>
        `).join('');
    }

    setupPresetColorHandlers() {
        const deleteModeCheckbox = document.getElementById('deleteModeCheckbox');

        document.querySelectorAll('.preset-color').forEach(preset => {
            preset.addEventListener('click', (e) => {
                if (deleteModeCheckbox.checked) {
                    // Режим удаления - удаляем цвет
                    const index = parseInt(e.currentTarget.dataset.index);
                    this.deletePresetColor(index);
                } else {
                    // Обычный режим - выбираем цвет
                    const color = e.currentTarget.dataset.color;
                    document.getElementById('canvasBackgroundColor').value = color;
                    document.getElementById('canvasBackgroundText').value = color;
                }
            });
        });

        // Добавляем обработчик для чекбокса режима удаления
        deleteModeCheckbox.addEventListener('change', (e) => {
            // Обновляем стиль цветов в зависимости от режима
            document.querySelectorAll('.preset-color').forEach(color => {
                if (e.target.checked) {
                    color.classList.add('delete-mode');
                } else {
                    color.classList.remove('delete-mode');
                }
            });
        });
    }

    addPresetColor() {
        const color = document.getElementById('canvasBackgroundColor').value;

        // Проверяем, что цвет еще не добавлен
        if (!this.presetColors.includes(color)) {
            this.presetColors.push(color);

            // Обновляем контейнер с предустановленными цветами
            const container = document.getElementById('presetColorsContainer');
            container.innerHTML = this.renderPresetColors();

            // Обновляем обработчики
            this.setupPresetColorHandlers();

            // Показать уведомление
            this.showNotification('Цвет добавлен в предустановленные', 'success');
        } else {
            this.showNotification('Этот цвет уже есть в списке', 'warning');
        }
    }

    deletePresetColor(index) {
        const color = this.presetColors[index];
        this.presetColors.splice(index, 1);

        // Обновляем контейнер с предустановленными цветами
        const container = document.getElementById('presetColorsContainer');
        container.innerHTML = this.renderPresetColors();

        // Обновляем обработчики
        this.setupPresetColorHandlers();

        // Показать уведомление
        this.showNotification(`Цвет ${color} удален`, 'info');
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

    closeCanvasSettingsModal() {
        const modal = document.getElementById('canvasSettingsModal');
        if (modal) {
            modal.remove();
        }
    }

    applyCanvasBackground() {
        const color = document.getElementById('canvasBackgroundColor').value;
        this.canvas.style.backgroundColor = color;
        this.closeCanvasSettingsModal();
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

    // Method to force complete reload of the editor
    forceReload() {
        this.clearPreviewEditSession();
        // Clear all elements
        this.elements = [];
        if (this.canvas) {
            this.canvas.innerHTML = '';
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

// Создаем глобальный экземпляр редактора
let contentEditor;

/**
 * При каждой загрузке страницы удаляем из localStorage только данные редактора
 * (кадры, карточки, счётчики слотов). Настройки страницы (eqThreshold, чекбоксы и т.д.) не трогаем.
 */
function clearContentEditorLocalStorage() {
    if (typeof localStorage === 'undefined') return;
    const toRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && k.startsWith('contentEditor_')) {
            toRemove.push(k);
        }
    }
    toRemove.forEach((k) => localStorage.removeItem(k));
}

/** Большие аудио лежат в IndexedDB под тем же именем, что и в ContentEditor.CONTENT_EDITOR_MEDIA_DB */
function clearContentEditorIndexedDB() {
    try {
        if (typeof indexedDB !== 'undefined') {
            indexedDB.deleteDatabase('contentEditorMedia');
        }
    } catch (e) {
        /* ignore */
    }
}

if (typeof window === 'undefined' || !window.__CONTENT_CARD_VIEW_ONLY__) {
    clearContentEditorLocalStorage();
    clearContentEditorIndexedDB();
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function () {
    if (window.__CONTENT_CARD_VIEW_ONLY__) {
        contentEditor = new ContentEditor();
        contentEditor.bootstrapContentCardViewPage().catch((e) => {
            console.error('content card view bootstrap:', e);
        });
        return;
    }
    contentEditor = new ContentEditor();
});
