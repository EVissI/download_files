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

        this.init();
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
        this.createModal();
        this.loadTools();
        this.setupEventListeners();
        this.setupCanvasEvents();
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

        if (!document.getElementById('saveCardConfirmModal')) {
            document.body.insertAdjacentHTML('beforeend', `
                <div id="saveCardConfirmModal" class="save-frame-confirm-modal" style="display: none;" aria-hidden="true">
                    <div class="save-frame-confirm-overlay" onclick="contentEditor.cancelSaveCard()"></div>
                    <div class="save-frame-confirm-box" role="dialog" aria-modal="true">
                        <h3 class="save-frame-confirm-title">Сохранить карточку</h3>
                        <div class="save-frame-confirm-actions">
                            <button type="button" class="save-frame-cancel-btn" onclick="contentEditor.cancelSaveCard()">Отмена</button>
                            <button type="button" class="save-frame-ok-btn save-card-ok-btn" onclick="contentEditor.confirmSaveCard()">Сохранить</button>
                        </div>
                    </div>
                </div>
            `);
        }
        this.saveCardConfirmModal = document.getElementById('saveCardConfirmModal');

        if (!document.getElementById('cardPreviewModal')) {
            document.body.insertAdjacentHTML('beforeend', `
                <div id="cardPreviewModal" class="card-preview-modal card-preview-modal--fullscreen" style="display: none;" aria-hidden="true">
                    <div class="card-preview-overlay" onclick="contentEditor.closeCardPreviewModal()"></div>
                    <div class="card-preview-box" role="dialog" aria-modal="true">
                        <div class="card-preview-header">
                            <h3 class="card-preview-title">Предпросмотр карточки</h3>
                            <button type="button" class="card-preview-close" onclick="contentEditor.closeCardPreviewModal()" aria-label="Закрыть">&times;</button>
                        </div>
                        <div class="card-preview-nav">
                            <button type="button" class="card-preview-nav-btn" id="cardPreviewPrevBtn" onclick="contentEditor.cardPreviewPrev()">←</button>
                            <span class="card-preview-counter" id="cardPreviewCounter">0 / 0</span>
                            <button type="button" class="card-preview-nav-btn" id="cardPreviewNextBtn" onclick="contentEditor.cardPreviewNext()">→</button>
                            <button type="button" class="card-preview-approve" id="cardPreviewApproveBtn" onclick="contentEditor.cardPreviewApprove()">Апрув</button>
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
        
        this.canvas = document.getElementById('canvas');
        this.toolsList = document.getElementById('toolsList');
        this.propertiesContent = document.getElementById('propertiesContent');

        // Дополнительные ссылки на панели для ресайза
        this.toolbarPanel = this.modal.querySelector('.toolbar');
        this.workspacePanel = this.modal.querySelector('.workspace');
        this.propertiesPanel = this.modal.querySelector('.properties-panel');
    }

    openModal() {
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
    }

    openModalWithData(cardData) {
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

    setupElementInteractions(element) {
        // Добавляем обработчики для выделения элемента
        element.addEventListener('click', (e) => {
            e.stopPropagation();
            this.selectElement(element);
        });

        // Добавляем обработчики для перемещения (drag and drop)
        element.addEventListener('mousedown', (e) => {
            if (e.target.classList.contains('control-btn')) return;
            
            const startX = e.clientX - element.offsetLeft;
            const startY = e.clientY - element.offsetTop;

            const handleMouseMove = (e) => {
                const newX = e.clientX - startX;
                const newY = e.clientY - startY;
                
                // Ограничиваем перемещение в пределах canvas
                const canvasRect = this.canvas.getBoundingClientRect();
                const elementRect = element.getBoundingClientRect();
                
                const maxX = canvasRect.width - elementRect.width;
                const maxY = canvasRect.height - elementRect.height;
                
                element.style.left = Math.max(0, Math.min(newX, maxX)) + 'px';
                element.style.top = Math.max(0, Math.min(newY, maxY)) + 'px';
            };

            const handleMouseUp = () => {
                document.removeEventListener('mousemove', handleMouseMove);
                document.removeEventListener('mouseup', handleMouseUp);
            };

            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
        });
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
        
        switch(toolId) {
            case 'boardCanvas':
                // Доска с параметрами - временно отключена
                element.innerHTML = `
                    <div style="padding: 20px; text-align: center; color: #666;">
                        <strong>Доска с параметрами</strong><br>
                        <small>Функционал временно отключен</small>
                    </div>
                `;
                break;
                
            case 'question-text':
                // Текст вопроса в стиле Photoshop
                element.innerHTML = `
                    <div class="text-content" contenteditable="true" placeholder="Введите текст вопроса...">Текст вопроса</div>
                `;
                element.classList.add('text-element');
                this.setupTextEditing(element);
                break;
                
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
                
            case 'answer-text':
                // Текст ответа в стиле Photoshop
                element.innerHTML = `
                    <div class="text-content" contenteditable="true" placeholder="Введите текст ответа...">Текст ответа</div>
                `;
                element.classList.add('text-element');
                this.setupTextEditing(element);
                break;
                
            case 'support-link':
                // Ссылка с текстовым контентом
                element.innerHTML = `
                    <div class="link-content">
                        <div class="link-text" contenteditable="true" placeholder="Введите текст ссылки...">Ссылка</div>
                        <input type="hidden" class="link-url" value="">
                    </div>
                `;
                element.classList.add('link-element');
                this.setupLinkEditing(element);
                break;
                
            default:
                element.innerHTML = `
                    <div style=" text-align: center; color: #666;">
                        <strong>${toolId}</strong><br>
                        <small>Неизвестный тип элемента</small>
                    </div>
                `;
        }
    }

    setupLinkEditing(element) {
        const linkText = element.querySelector('.link-text');
        const linkUrl = element.querySelector('.link-url');
        if (!linkText || !linkUrl) return;

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
            this.saveSelectionForEditable(linkText);
            if (linkText.textContent.trim() === '') {
                linkText.textContent = 'Ссылка';
            }
        });

        // Обработка клика по ссылке для перехода (только если не в режиме редактирования)
        element.addEventListener('click', (e) => {
            // Если не в режиме редактирования текста и клик не по текстовому полю
            if (!linkText.contains(e.target) || document.activeElement !== linkText) {
                const url = linkUrl.value;
                if (url && url.trim() !== '') {
                    // Открываем ссылку в новой вкладке
                    window.open(url, '_blank');
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
        // Remove mini menu - no controls added
        // Elements will be managed through other means
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
                <button type="button" class="action-btn save-frame-inline-btn" onclick="contentEditor.openSaveFrameConfirm()">Сохранить кадр</button>
                <button type="button" class="action-btn save-card-inline-btn" onclick="contentEditor.openSaveCardConfirm()">Сохранить карточку</button>
            </div>
        `;
    }

    updateElementProperty(property, value) {
        if (!this.selectedElement) return;
        
        switch(property) {
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
                this.propertiesContent.innerHTML = '<p>Выберите элемент для редактирования</p>';
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
            if (this.saveCardConfirmModal && this.saveCardConfirmModal.style.display === 'flex') {
                this.cancelSaveCard();
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

    confirmSaveFrame() {
        try {
            const frameId = this.getFrameIdForSave();
            const saveSlotIndex = this.allocateNextSaveSlotIndex(frameId);
            const payload = this.buildFrameSavePayload(frameId, saveSlotIndex);
            const key = this.frameStorageKey(frameId, saveSlotIndex);
            localStorage.setItem(key, JSON.stringify(payload));
            this.showNotification(`Кадр сохранён №${saveSlotIndex + 1}`, 'success');
        } catch (err) {
            console.error('confirmSaveFrame:', err);
            this.showNotification('Не удалось сохранить: ' + (err.message || err), 'error');
            return;
        }
        this.cancelSaveFrame();
        this.closeModal();
        this.resetEditorAfterSave();
    }

    buildFrameSavePayload(frameId, saveSlotIndex) {
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

        const bg = this.canvas.style.backgroundColor || window.getComputedStyle(this.canvas).backgroundColor;
        return {
            version: 1,
            frameId,
            saveSlotIndex,
            savedAt: new Date().toISOString(),
            board,
            cardData: cardDataCopy,
            editor: {
                boardCanvasToggle: !!this.toggleStates['boardCanvas'],
                canvasBackground: bg
            },
            elements: this.serializeCanvasElements()
        };
    }

    serializeCanvasElements() {
        const out = [];
        this.canvas.querySelectorAll('.canvas-element').forEach(el => {
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
                    item.tableHtml = tbl ? tbl.outerHTML : el.innerHTML;
                    break;
                }
                case 'upload-image': {
                    item.imageUrl = el.dataset.imageUrl || '';
                    break;
                }
                case 'audio-file': {
                    item.audioUrl = el.dataset.audioUrl || '';
                    item.audioName = el.dataset.audioName || '';
                    break;
                }
                case 'board-illustration': {
                    const img = el.querySelector('img');
                    item.imageDataUrl = img ? img.src : '';
                    break;
                }
                default:
                    item.innerHtml = el.innerHTML;
            }
            out.push(item);
        });
        return out;
    }

    resetEditorAfterSave() {
        this.elements = [];
        if (this.canvas) {
            this.canvas.innerHTML = '';
            this.canvas.style.backgroundColor = '#ffffff';
        }
        this.selectedElement = null;
        if (this.propertiesContent) {
            this.propertiesContent.innerHTML = '<p>Выберите элемент для редактирования</p>';
        }
        this.toggleStates = {};
        this.cardData = null;
        this.elementIdCounter = 0;
        this.loadTools();
        this.forceRefreshContent();
    }

    openSaveCardConfirm() {
        if (!this.saveCardConfirmModal) return;
        this.saveCardConfirmModal.style.display = 'flex';
        this.saveCardConfirmModal.setAttribute('aria-hidden', 'false');
    }

    cancelSaveCard() {
        if (!this.saveCardConfirmModal) return;
        this.saveCardConfirmModal.style.display = 'none';
        this.saveCardConfirmModal.setAttribute('aria-hidden', 'true');
    }

    getGameContextForCard() {
        const b = typeof window.getHintViewerBoardSnapshot === 'function'
            ? window.getHintViewerBoardSnapshot()
            : null;
        const gameId = (b && b.gameId) ? b.gameId : 'default';
        const gameNum = b && b.currentGameNum != null ? b.currentGameNum : null;
        return { gameId, gameNum, board: b };
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

    cardManifestStorageKey(gameId, gameNum) {
        const safe = this.sanitizeFrameIdForStorageKey(`${gameId}_g${gameNum != null ? gameNum : 'na'}`);
        return `contentEditor_card_${safe}`;
    }

    confirmSaveCard() {
        try {
            const frameId = this.getFrameIdForSave();
            const saveSlotIndex = this.allocateNextSaveSlotIndex(frameId);
            const currentPayload = this.buildFrameSavePayload(frameId, saveSlotIndex);
            localStorage.setItem(this.frameStorageKey(frameId, saveSlotIndex), JSON.stringify(currentPayload));

            const refs = this.collectSavedFrameRefsForCurrentGame();
            const { gameId, gameNum } = this.getGameContextForCard();
            const manifest = {
                version: 1,
                savedAt: new Date().toISOString(),
                gameId,
                currentGameNum: gameNum,
                frameRefs: refs.map(r => ({
                    storageKey: r.storageKey,
                    frameId: r.frameId,
                    saveSlotIndex: r.saveSlotIndex
                }))
            };
            localStorage.setItem(this.cardManifestStorageKey(gameId, gameNum), JSON.stringify(manifest));
            this.showNotification('Карточка и текущий кадр сохранены', 'success');
        } catch (err) {
            console.error('confirmSaveCard:', err);
            this.showNotification('Не удалось сохранить карточку: ' + (err.message || err), 'error');
            return;
        }
        this.cancelSaveCard();
        this.closeModal();
        this.resetEditorAfterSave();
        this.openCardPreviewModal();
    }

    openCardPreviewModal() {
        if (!this.cardPreviewModal) return;
        this.cardPreviewRefs = this.collectSavedFrameRefsForCurrentGame();
        this.cardPreviewIndex = 0;
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
        document.body.style.overflow = 'auto';
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
        let extra = '';
        try {
            const raw = localStorage.getItem(ref.storageKey);
            payload = raw ? JSON.parse(raw) : null;
            if (payload && payload.savedAt) {
                extra = `<span class="card-preview-saved-at">${this.escapeHtml(payload.savedAt)}</span>`;
            }
        } catch (e) {
            payload = null;
        }

        meta.innerHTML = `
            <div class="card-preview-meta-line"><strong>ID</strong> ${this.escapeHtml(ref.frameId)} · сохранение ${ref.saveSlotIndex + 1}</div>
            ${extra}
        `;
        this.renderCardPreviewSurface(payload);
    }

    renderCardPreviewSurface(payload) {
        const host = document.getElementById('cardPreviewFrameHost');
        if (!host) return;
        host.innerHTML = '';
        if (!payload) {
            return;
        }

        const list = Array.isArray(payload.elements) ? payload.elements : [];

        const designW = this.getMaxCanvasWidth();
        const wrap = document.createElement('div');
        wrap.className = 'card-preview-surface-wrap';
        const inner = document.createElement('div');
        inner.className = 'card-preview-surface-inner';
        inner.dataset.designWidth = String(designW);
        inner.style.width = designW + 'px';
        inner.style.position = 'relative';
        inner.style.boxSizing = 'border-box';
        inner.style.background = (payload.editor && payload.editor.canvasBackground) ? payload.editor.canvasBackground : '#ffffff';

        let maxNum = 0;
        list.forEach(item => {
            const m = /^element_(\d+)$/.exec(item.id || '');
            if (m) maxNum = Math.max(maxNum, parseInt(m[1], 10) + 1);
        });
        const savedCounter = this.elementIdCounter;
        this.elementIdCounter = maxNum;
        list.forEach(item => {
            const el = this.deserializeCanvasElement(item, { previewMode: true });
            if (el) inner.appendChild(el);
        });
        this.elementIdCounter = savedCounter;

        wrap.appendChild(inner);
        host.appendChild(wrap);

        inner.querySelectorAll('img').forEach((img) => {
            img.addEventListener('load', () => this.refreshCardPreviewScale());
        });

        requestAnimationFrame(() => {
            this.refreshCardPreviewScale();
        });
    }

    refreshCardPreviewScale() {
        const host = document.getElementById('cardPreviewFrameHost');
        if (!host) return;
        const inner = host.querySelector('.card-preview-surface-inner');
        const wrap = host.querySelector('.card-preview-surface-wrap');
        if (!inner || !wrap) return;

        const designW = parseFloat(inner.dataset.designWidth) || this.getMaxCanvasWidth();
        const avail = Math.max(120, host.clientWidth - 16);
        const scale = Math.min(1, avail / designW);
        inner.style.transform = `scale(${scale})`;
        inner.style.transformOrigin = 'top center';

        const h = inner.offsetHeight * scale;
        wrap.style.minHeight = `${Math.ceil(h + 8)}px`;
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
        const ref = this.cardPreviewRefs[this.cardPreviewIndex];
        if (!ref) {
            this.showNotification('Нет выбранного кадра', 'warning');
            return;
        }
        this.showNotification(`Апрув (заглушка): ${ref.frameId}`, 'info');
    }

    openEditorFromSelectedPreview() {
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
        this.openModalWithData(payload.cardData || null);
        this.restoreCanvasFromPayload(payload);
    }

    restoreCanvasFromPayload(payload) {
        if (!this.canvas) return;

        this.elements = [];
        this.canvas.innerHTML = '';
        this.selectedElement = null;
        this.toggleStates = {};

        if (payload.editor && payload.editor.boardCanvasToggle) {
            this.toggleStates['boardCanvas'] = true;
        }
        if (payload.editor && payload.editor.canvasBackground) {
            this.canvas.style.backgroundColor = payload.editor.canvasBackground;
        } else {
            this.canvas.style.backgroundColor = '#ffffff';
        }

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

        if (this.propertiesContent) {
            this.propertiesContent.innerHTML = '<p>Выберите элемент для редактирования</p>';
        }

        this.loadTools();
        this.syncBoardToolToggleFromState();
        this.forceRefreshContent();
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
                if (!previewMode) this.setupLinkEditing(element);
                break;
            }
            case 'moveHintsTable':
                element.classList.add('table-element');
                element.dataset.tableType = item.tableType || 'hints';
                element.innerHTML = item.tableHtml || '';
                break;
            case 'upload-image':
                element.classList.add('image-element');
                if (item.imageUrl) element.dataset.imageUrl = item.imageUrl;
                element.innerHTML = `<img src="${item.imageUrl || ''}" style="width: 100%; height: 100%; object-fit: contain;" alt="" />`;
                break;
            case 'audio-file':
                element.classList.add('audio-element');
                if (item.audioUrl) element.dataset.audioUrl = item.audioUrl;
                if (item.audioName) element.dataset.audioName = item.audioName;
                element.innerHTML = `
                    <div class="audio-message" style="display: flex; align-items: center; padding: 12px; height: 100%; background: #f0f0f0; border-radius: 8px;">
                        <div class="audio-icon" style="font-size: 24px; margin-right: 12px; color: #667eea;">🎵</div>
                        <div class="audio-info" style="flex: 1;">
                            <div class="audio-name" style="font-size: 14px; font-weight: 500; color: #333; margin-bottom: 4px;">${this.escapeHtml(item.audioName || 'Аудио')}</div>
                            <div class="audio-duration" style="font-size: 12px; color: #666;">—</div>
                        </div>
                        <div class="audio-play-btn" style="width: 32px; height: 32px; border-radius: 50%; background: #667eea; color: white; border: none; cursor: ${previewMode ? 'default' : 'pointer'}; display: flex; align-items: center; justify-content: center; font-size: 16px; opacity: ${previewMode ? '0.5' : '1'};">▶</div>
                    </div>`;
                if (item.audioUrl && !previewMode) {
                    this.setupAudioElement(element, item.audioUrl, null);
                }
                break;
            case 'board-illustration': {
                const img = document.createElement('img');
                img.src = item.imageDataUrl || '';
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
        // Клик по элементу для выделения и открытия свойств
        this.canvas.addEventListener('mousedown', (e) => {
            // Ищем ближайший родительский элемент canvas-element
            const canvasElement = e.target.closest('.canvas-element');
            
            if (canvasElement && 
                !e.target.classList.contains('control-btn')) {
                this.selectElement(canvasElement);
            }
        });

    }


    deselectAll() {
        document.querySelectorAll('.canvas-element').forEach(el => {
            el.classList.remove('selected');
        });
        this.selectedElement = null;
        this.propertiesContent.innerHTML = '<p>Выберите элемент для редактирования</p>';
    }

    openCanvasSettingsModal() {
        // Создаем модальное окно настроек фона канваса
        const modalHTML = `
            <div id="canvasSettingsModal" class="canvas-settings-modal" style="display: flex;">
                <div class="canvas-settings-overlay" onclick="contentEditor.closeCanvasSettingsModal()"></div>
                <div class="canvas-settings-container">
                    <div class="canvas-settings-header">
                        <h3>Настройки фона канваса</h3>
                        <button class="close-btn" onclick="contentEditor.closeCanvasSettingsModal()">&times;</button>
                    </div>
                    <div class="canvas-settings-body">
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
                                <button class="add-preset-btn" onclick="contentEditor.addPresetColor()">
                                    <i class="fa fa-plus"></i> Добавить цвет
                                </button>
                            </div>
                        </div>
                    </div>
                    <div class="canvas-settings-footer">
                        <button class="cancel-btn" onclick="contentEditor.closeCanvasSettingsModal()">Отмена</button>
                        <button class="apply-btn" onclick="contentEditor.applyCanvasBackground()">Применить</button>
                    </div>
                </div>
            </div>
        `;
        
        // Добавляем модальное окно в DOM
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        
        // Устанавливаем текущий цвет фона
        const currentBg = window.getComputedStyle(this.canvas).backgroundColor;
        const hexColor = this.rgbToHex(currentBg);
        document.getElementById('canvasBackgroundColor').value = hexColor;
        document.getElementById('canvasBackgroundText').value = hexColor;
        
        // Добавляем обработчики для предустановленных цветов
        this.setupPresetColorHandlers();
        
        // Синхронизация color picker и текстового поля
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
        // Clear all elements
        this.elements = [];
        if (this.canvas) {
            this.canvas.innerHTML = '';
        }
        
        // Reset properties
        this.selectedElement = null;
        if (this.propertiesContent) {
            this.propertiesContent.innerHTML = '<p>Выберите элемент для редактирования</p>';
        }
        
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

clearContentEditorLocalStorage();

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    contentEditor = new ContentEditor();
});
