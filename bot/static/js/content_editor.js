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
            // For mobile, return standard mobile card height
            return 640;
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
                            <div class="toolbar">
                                <div class="tools-list" id="toolsList">
                                    <!-- Динамический список инструментов -->
                                </div>
                            </div>

                            <div class="workspace">
                                <div class="canvas" id="canvas">
                                    <!-- Здесь будут размещаться элементы -->
                                </div>
                            </div>

                            <div class="properties-panel">
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
        
        this.canvas = document.getElementById('canvas');
        this.toolsList = document.getElementById('toolsList');
        this.propertiesContent = document.getElementById('propertiesContent');
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
        
        // Setup audio functionality
        this.setupAudioElement(element, audioUrl, file);
        
        // Save to elements array
        this.elements.push({
            id: elementId,
            toolId: 'audio-file',
            element: element
        });
        
        // Update canvas height
        this.updateCanvasHeight();
        
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
        // Можно добавить логику для показа уведомлений
        console.log(`${toolId} is now ${isActive ? 'ACTIVE' : 'INACTIVE'}`);
        
        // При необходимости можно добавить визуальное уведомление в интерфейсе
        if (isActive) {
            // Активировано - можно показать сообщение или выполнить действие
            this.performToggleAction(toolId, true);
        } else {
            // Деактивировано
            this.performToggleAction(toolId, false);
        }
    }

    performToggleAction(toolId, isActive) {
        // Здесь можно добавить конкретные действия при toggle
        switch(toolId) {
            case 'boardCanvas':
                if (isActive) {
                    console.log('BoardCanvas активирован');
                    this.showBoardLabel();
                } else {
                    console.log('BoardCanvas деактивирован');
                    this.hideBoardLabel();
                }
                break;
        }
    }

    showBoardLabel() {
        // Проверяем, есть ли уже надпись
        if (document.getElementById('boardLabel')) {
            return; // Уже существует
        }

        // Создаем элемент надписи
        const boardLabel = document.createElement('div');
        boardLabel.id = 'boardLabel';
        boardLabel.className = 'board-label';
        boardLabel.textContent = 'доска';
        
        // Добавляем на холст
        this.canvas.appendChild(boardLabel);
        
        // Запускаем анимацию появления в следующем кадре
        requestAnimationFrame(() => {
            boardLabel.classList.add('show');
        });
    }

    hideBoardLabel() {
        // Находим и удаляем надпись
        const boardLabel = document.getElementById('boardLabel');
        if (boardLabel) {
            boardLabel.classList.remove('show');
            boardLabel.classList.add('hide');
            
            // Удаляем элемент после завершения анимации
            setTimeout(() => {
                if (boardLabel.parentNode) {
                    boardLabel.remove();
                }
            }, 300);
        }
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
        
        // Ensure the element doesn't go beyond canvas bounds
        let currentElementHeight;
        if (elementHeight === 'auto') {
            currentElementHeight = 120; // Default estimate for auto elements
        } else {
            currentElementHeight = elementHeight;
        }
        
        const maxY = Math.min(canvasRect.height, maxCanvasHeight) - currentElementHeight - 20;
        if (nextY > maxY) {
            // If we run out of space, start from the top with offset
            nextY = startY + (this.elements.length % 3) * (currentElementHeight + elementSpacing);
        }
        
        // Debug: Log final calculation
        console.log(`Final position calculation: y=${nextY}, elementHeight=${currentElementHeight}`);
        
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
        
        // Update canvas height after repositioning
        this.updateCanvasHeight();
    }

    updateCanvasHeight() {
        if (!this.canvas) return;
        
        const allElements = Array.from(this.canvas.querySelectorAll('.canvas-element'))
            .filter(el => !el.id.includes('boardLabel'));
        
        if (allElements.length === 0) {
            // No elements - set minimum height
            this.canvas.style.height = '0px';
            return;
        }
        
        // Find the bottom-most element
        let maxBottom = 0;
        allElements.forEach(element => {
            const top = parseInt(element.style.top) || 0;
            const height = element.offsetHeight;
            const bottom = top + height;
            maxBottom = Math.max(maxBottom, bottom);
        });
        
        // Add some padding at the bottom
        const canvasHeight = maxBottom + 20;
        this.canvas.style.height = canvasHeight + 'px';
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
            
            // Update canvas height
            this.updateCanvasHeight();
            
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
                // Начинаем редактирование при клике на текст
                linkText.focus();
                
                // Выделяем весь текст при первом клике
                if (linkText.textContent === 'Ссылка') {
                    // Выделяем весь текст
                    const selection = window.getSelection();
                    const range = document.createRange();
                    range.selectNodeContents(linkText);
                    selection.removeAllRanges();
                    selection.addRange(range);
                }
            }
        });

        // Добавляем обработчик фокуса для открытия свойств
        linkText.addEventListener('focus', () => {
            this.selectElement(element);
        });

        // Обработка окончания редактирования
        linkText.addEventListener('blur', () => {
            // Если текст пустой, возвращаем placeholder
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
                // Начинаем редактирование при клике на текст
                textContent.focus();
                
                // Выделяем весь текст при первом клике
                if (textContent.textContent === 'Текст вопроса' || textContent.textContent === 'Текст ответа') {
                    // Выделяем весь текст
                    const selection = window.getSelection();
                    const range = document.createRange();
                    range.selectNodeContents(textContent);
                    selection.removeAllRanges();
                    selection.addRange(range);
                }
            }
        });

        // Добавляем обработчик фокуса для открытия свойств
        textContent.addEventListener('focus', () => {
            this.selectElement(element);
        });

        // Обработка окончания редактирования
        textContent.addEventListener('blur', () => {
            // Если текст пустой, возвращаем placeholder
            if (textContent.textContent.trim() === '') {
                if (element.dataset.toolId === 'question-text') {
                    textContent.textContent = 'Текст вопроса';
                } else if (element.dataset.toolId === 'answer-text') {
                    textContent.textContent = 'Текст ответа';
                }
            }
            // Автоматическое изменение высоты отключено
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
                    <input type="color" id="propTextColor" value="${window.getComputedStyle(element.querySelector('.text-content')).color || '#333333'}" 
                           oninput="contentEditor.updateElementProperty('textColor', this.value)">
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
                    <input type="color" id="propTextColor" value="${window.getComputedStyle(element.querySelector('.link-text')).color || '#007bff'}" 
                           oninput="contentEditor.updateElementProperty('textColor', this.value)">
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
                <div class="property-item">
                    <label>Цвет обводки:</label>
                    <input type="color" id="propBorderColor" value="#667eea" 
                           oninput="contentEditor.updateElementProperty('borderColor', this.value)">
                </div>
                <div class="property-item">
                    <label>Толщина обводки:</label>
                    <input type="range" id="propBorderWidth" min="0" max="10" value="2" 
                           oninput="contentEditor.updateElementProperty('borderWidth', this.value + 'px')">
                    <div class="property-value">2px</div>
                </div>
                <div class="property-item">
                    <label>Прозрачность:</label>
                    <input type="range" id="propOpacity" min="0" max="100" value="100" 
                           oninput="contentEditor.updateElementProperty('opacity', this.value / 100)">
                    <div class="property-value">100%</div>
                </div>
                <div class="property-item">
                    <label>
                        <input type="checkbox" id="propShadow" 
                               onchange="contentEditor.updateElementProperty('shadow', this.checked)">
                        Тень
                    </label>
                </div>
            </div>
            
            <div class="action-buttons">
                <button class="action-btn danger" onclick="contentEditor.deleteElement('${element.id}')">Удалить</button>
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
            case 'fontSize':
                const textElement = this.selectedElement.querySelector('.text-content, .link-text');
                if (textElement) {
                    textElement.style.fontSize = value;
                    // Update display value
                    const valueDisplay = document.querySelector(`#prop${property.charAt(0).toUpperCase() + property.slice(1)} + .property-value`);
                    if (valueDisplay) {
                        valueDisplay.textContent = value;
                    }
                }
                break;
            case 'textColor':
                const textContent = this.selectedElement.querySelector('.text-content, .link-text');
                if (textContent) {
                    textContent.style.color = value;
                }
                break;
            case 'linkUrl':
                const linkUrl = this.selectedElement.querySelector('.link-url');
                if (linkUrl) {
                    linkUrl.value = value;
                }
                break;
            case 'borderColor':
                this.selectedElement.style.borderColor = value;
                break;
            case 'borderWidth':
                this.selectedElement.style.borderWidth = value;
                // Update display value
                const borderWidthDisplay = document.querySelector('#propBorderWidth + .property-value');
                if (borderWidthDisplay) {
                    borderWidthDisplay.textContent = value;
                }
                break;
            case 'opacity':
                this.selectedElement.style.opacity = value;
                // Update display value
                const opacityDisplay = document.querySelector('#propOpacity + .property-value');
                if (opacityDisplay) {
                    opacityDisplay.textContent = Math.round(value * 100) + '%';
                }
                break;
            case 'shadow':
                if (value) {
                    this.selectedElement.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.3)';
                } else {
                    this.selectedElement.style.boxShadow = 'none';
                }
                break;
            case 'tableType':
                this.selectedElement.dataset.tableType = value;
                this.updateTableContent(this.selectedElement, value);
                break;
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
            element.remove();
            this.elements = this.elements.filter(el => el.id !== elementId);
            
            // Update canvas height after deletion
            this.updateCanvasHeight();
            
            if (this.selectedElement && this.selectedElement.id === elementId) {
                this.selectedElement = null;
                this.propertiesContent.innerHTML = '<p>Выберите элемент для редактирования</p>';
            }
        }
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
        // Note: updateCanvasHeight is already called inside recalculateAllElementPositions
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
        
        // Update canvas height after recalculation
        this.updateCanvasHeight();
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

    // Method to force complete reload of the editor
    forceReload() {
        // Clear board label if exists
        this.hideBoardLabel();
        
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

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    contentEditor = new ContentEditor();
});
