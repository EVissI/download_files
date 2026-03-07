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
        this.currentResizeHandle = null;
        this.toggleStates = {}; // Для отслеживания состояния toggle-кнопок
        
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
                                <h3>Инструменты</h3>
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

    forceRefreshContent() {
        // Force refresh all cached content
        if (this.canvas) {
            // Clear canvas and force reflow
            const elements = this.canvas.querySelectorAll('.canvas-element');
            elements.forEach(el => {
                el.style.display = 'none';
                el.offsetHeight; // Force reflow
                el.style.display = '';
            });
        }
        
        // Refresh tools list
        if (this.toolsList) {
            this.toolsList.style.display = 'none';
            this.toolsList.offsetHeight; // Force reflow
            this.toolsList.style.display = '';
        }
        
        // Refresh properties panel
        if (this.propertiesContent) {
            const currentContent = this.propertiesContent.innerHTML;
            this.propertiesContent.innerHTML = '';
            this.propertiesContent.offsetHeight; // Force reflow
            this.propertiesContent.innerHTML = currentContent;
        }
    }

    loadTools() {
        // Определяем доступные инструменты согласно требованиям
        const tools = [
            {
                id: 'boardCanvas',
                name: 'Доска с параметрами',
                type: 'canvas',
                description: 'Игровая доска с параметрами (манигейм/матч)'
            },
            {
                id: 'question-text',
                name: 'Текст вопроса',
                type: 'text',
                description: 'Текст вопроса для анализа'
            },
            {
                id: 'moveHintsTable',
                name: 'Таблица',
                type: 'table',
                description: 'Таблица подсказок или данных'
            },
            {
                id: 'answer-text',
                name: 'Текст ответа',
                type: 'text',
                description: 'Текст ответа или решения'
            },
            {
                id: 'board-illustration',
                name: 'Иллюстрация',
                type: 'image',
                description: 'Изображение доски как иллюстрация'
            },
            {
                id: 'audio-file',
                name: 'Аудио-файл',
                type: 'audio',
                description: 'Аудиофайл для воспроизведения'
            },
            {
                id: 'support-link',
                name: 'Ссылка',
                type: 'link',
                description: 'Ссылка на дополнительные материалы'
            }
        ];

        this.renderTools(tools);
    }

    renderTools(tools) {
        this.toolsList.innerHTML = tools.map(tool => `
            <div class="tool-item ${tool.id === 'boardCanvas' ? 'toggle-button' : ''}" 
                 data-tool-id="${tool.id}"
                 onclick="contentEditor.selectTool('${tool.id}')">
                <div class="tool-item-header">
                    <span class="tool-name">${tool.name}</span>
                    ${tool.id === 'boardCanvas' ? '<span class="toggle-indicator">⚡</span>' : ''}
                </div>
                <div class="tool-description">${tool.description}</div>
            </div>
        `).join('');
    }

    selectTool(toolId) {
        // Особое поведение для boardCanvas - toggle режим
        if (toolId === 'boardCanvas') {
            this.toggleBoardCanvas(toolId);
            return;
        }

        // Убираем выделение с предыдущего инструмента
        document.querySelectorAll('.tool-item').forEach(item => {
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
        
        // Calculate center X position
        const centerX = (Math.min(canvasRect.width, maxCanvasWidth) - elementWidth) / 2;
        
        // Calculate vertical spacing and position
        const verticalSpacing = 20; // Расстояние между элементами
        const startY = 20; // Начальный отступ сверху
        
        let nextY = startY;
        
        // Find the next available vertical position
        for (const existingEl of existingElements) {
            const existingTop = parseInt(existingEl.style.top);
            const existingHeight = parseInt(existingEl.style.height);
            
            // Check if the current element fits before this existing element
            if (nextY + elementHeight + verticalSpacing <= existingTop) {
                break; // Found a gap
            }
            
            // Move to the next position after this element
            nextY = existingTop + existingHeight + verticalSpacing;
        }
        
        // Ensure the element doesn't go beyond canvas bounds
        const maxY = Math.min(canvasRect.height, maxCanvasHeight) - elementHeight - 20;
        if (nextY > maxY) {
            // If we run out of space, start from the top with a smaller spacing
            nextY = startY + (this.elements.length % 5) * (elementHeight + 10);
        }
        
        return {
            x: Math.max(10, centerX),
            y: Math.max(startY, nextY)
        };
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
        
        // Adjust element size for mobile cards
        const defaultWidth = this.isMobile() ? Math.min(120, maxCanvasWidth - 40) : 200;
        const defaultHeight = this.isMobile() ? Math.min(80, maxCanvasHeight - 40) : 150;
        
        // Position elements in vertical blocks with center alignment
        const position = this.calculateVerticalPosition(defaultWidth, defaultHeight);
        
        element.style.left = position.x + 'px';
        element.style.top = position.y + 'px';
        element.style.width = defaultWidth + 'px';
        element.style.height = defaultHeight + 'px';
        
        // Добавляем контент в элемент
        this.populateElementContent(element, toolId);
        
        // Добавляем контролы
        this.addElementControls(element);
        
        // Добавляем resize handles
        this.addResizeHandles(element);
        
        // Добавляем на холст
        this.canvas.appendChild(element);
        
        // Сохраняем в массив элементов
        this.elements.push({
            id: elementId,
            toolId: toolId,
            element: element
        });
        
        // Выделяем элемент
        this.selectElement(element);
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
                // Таблица
                const originalTable = document.getElementById('moveHintsTable');
                if (originalTable) {
                    const clonedTable = originalTable.cloneNode(true);
                    // Add cache-busting to table
                    clonedTable.setAttribute('data-table-timestamp', timestamp);
                    element.appendChild(clonedTable);
                } else {
                    // Создаем пример таблицы
                    element.innerHTML = `
                        <div style="padding: 10px; height: 100%; overflow: auto;">
                            <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
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
                        </div>
                    `;
                }
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
                
            case 'audio-file':
                // Аудио-файл
                element.innerHTML = `
                    <div style="padding: 20px; text-align: center; height: 100%; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                        <div style="font-size: 48px; margin-bottom: 10px;">🎵</div>
                        <input type="file" accept="audio/*" style="margin-bottom: 10px;">
                        <audio controls style="width: 100%;">
                            <source src="" type="audio/mpeg">
                            Ваш браузер не поддерживает аудио.
                        </audio>
                    </div>
                `;
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
                    <div style="padding: 10px; text-align: center; color: #666;">
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

        // Делаем текст нефокусируемым при перетаскивании
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

        // Обработка окончания редактирования
        linkText.addEventListener('blur', () => {
            // Если текст пустой, возвращаем placeholder
            if (linkText.textContent.trim() === '') {
                linkText.textContent = 'Ссылка';
            }
        });

        // Обработка клика по ссылке для перехода
        element.addEventListener('click', (e) => {
            // Если не в режиме редактирования текста
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

        // Делаем текст нефокусируемым при перетаскивании
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
        const controls = document.createElement('div');
        controls.className = 'element-controls';
        controls.innerHTML = `
            <button class="control-btn" onclick="contentEditor.duplicateElement('${element.id}')" title="Дублировать">📋</button>
            <button class="control-btn delete" onclick="contentEditor.deleteElement('${element.id}')" title="Удалить">🗑️</button>
        `;
        element.appendChild(controls);
    }

    addResizeHandles(element) {
        const handles = ['nw', 'ne', 'sw', 'se'];
        handles.forEach(position => {
            const handle = document.createElement('div');
            handle.className = `resize-handle ${position}`;
            handle.dataset.position = position;
            element.appendChild(handle);
        });
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
        
        this.propertiesContent.innerHTML = `
            <div class="property-group">
                <h4>Размер</h4>
                <div class="property-item">
                    <label>Ширина:</label>
                    <input type="range" id="propWidth" min="50" max="${maxElementWidth}" 
                           value="${parseInt(element.style.width)}" 
                           oninput="contentEditor.updateElementProperty('width', this.value + 'px')">
                    <div class="property-value">${parseInt(element.style.width)}px</div>
                </div>
                <div class="property-item">
                    <label>Высота:</label>
                    <input type="range" id="propHeight" min="50" max="${maxElementHeight}" 
                           value="${parseInt(element.style.height)}" 
                           oninput="contentEditor.updateElementProperty('height', this.value + 'px')">
                    <div class="property-value">${parseInt(element.style.height)}px</div>
                </div>
            </div>
            
            <div class="property-group">
                <h4>Стиль</h4>
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
                <button class="action-btn" onclick="contentEditor.bringToFront()">На передний план</button>
                <button class="action-btn" onclick="contentEditor.sendToBack()">На задний план</button>
                <button class="action-btn danger" onclick="contentEditor.deleteElement('${element.id}')">Удалить</button>
            </div>
        `;
    }

    updateElementProperty(property, value) {
        if (!this.selectedElement) return;
        
        switch(property) {
            case 'left':
            case 'top':
            case 'width':
            case 'height':
            case 'zIndex':
                this.selectedElement.style[property] = value;
                break;
            case 'fontSize':
                if (element.classList.contains('text-element')) {
                    const textContent = this.selectedElement.querySelector('.text-content');
                    if (textContent) {
                        textContent.style.fontSize = value;
                    }
                } else if (element.classList.contains('link-element')) {
                    const linkText = this.selectedElement.querySelector('.link-text');
                    if (linkText) {
                        linkText.style.fontSize = value;
                    }
                }
                break;
            case 'textColor':
                if (element.classList.contains('text-element')) {
                    const textContent = this.selectedElement.querySelector('.text-content');
                    if (textContent) {
                        textContent.style.color = value;
                    }
                } else if (element.classList.contains('link-element')) {
                    const linkText = this.selectedElement.querySelector('.link-text');
                    if (linkText) {
                        linkText.style.color = value;
                    }
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
                break;
            case 'opacity':
                this.selectedElement.style.opacity = value;
                break;
            case 'shadow':
                this.selectedElement.style.boxShadow = value ? '0 4px 16px rgba(0,0,0,0.3)' : 'none';
                break;
        }
        
        // Обновляем отображение значений
        if (property === 'left' || property === 'top' || property === 'width' || property === 'height') {
            const valueDisplay = this.selectedElement.querySelector(`.property-value`);
            if (valueDisplay) {
                valueDisplay.textContent = value;
            }
        } else if (property === 'fontSize') {
            const fontSizeInput = document.getElementById('propFontSize');
            if (fontSizeInput) {
                const fontSizeDisplay = fontSizeInput.parentElement.querySelector('.property-value');
                if (fontSizeDisplay) {
                    fontSizeDisplay.textContent = value;
                }
            }
        }
        
        // Автоматическое изменение высоты отключено
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
        
        // Используем новую логику позиционирования для дубликата
        const elementWidth = parseInt(element.style.width) || 200;
        const elementHeight = parseInt(element.style.height) || 150;
        const position = this.calculateVerticalPosition(elementWidth, elementHeight);
        
        newElement.style.left = position.x + 'px';
        newElement.style.top = position.y + 'px';
        
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
            
            if (this.selectedElement && this.selectedElement.id === elementId) {
                this.selectedElement = null;
                this.propertiesContent.innerHTML = '<p>Выберите элемент для редактирования</p>';
            }
        }
    }

    bringToFront() {
        if (!this.selectedElement) return;
        
        const maxZ = Math.max(...this.elements.map(el => 
            parseInt(el.element.style.zIndex || 1)
        ));
        this.selectedElement.style.zIndex = maxZ + 1;
    }

    sendToBack() {
        if (!this.selectedElement) return;
        
        const minZ = Math.min(...this.elements.map(el => 
            parseInt(el.element.style.zIndex || 1)
        ));
        this.selectedElement.style.zIndex = Math.max(1, minZ - 1);
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
        // Update all canvas elements on window resize
        const canvasElements = this.canvas.querySelectorAll('.canvas-element');
        canvasElements.forEach(element => {
            const toolId = element.dataset.toolId;
            if (toolId === 'boardCanvas' || toolId === 'board-illustration') {
                // Update canvas/image dimensions for mobile
                const canvasOrImg = element.querySelector('canvas, img');
                if (canvasOrImg) {
                    const maxWidth = this.getMaxCanvasWidth();
                    canvasOrImg.style.maxWidth = maxWidth + 'px';
                    canvasOrImg.style.width = '100%';
                    canvasOrImg.style.height = 'auto';
                }
            }
        });
    }

    setupCanvasEvents() {
        // Изменение размера элементов
        this.canvas.addEventListener('mousedown', (e) => {
            if (e.target.classList.contains('resize-handle')) {
                this.startResizing(e, e.target);
            }
        });

        document.addEventListener('mousemove', (e) => {
            if (this.isResizing) {
                this.resize(e);
            }
        });

        document.addEventListener('mouseup', () => {
            this.stopResizing();
        });
    }

    startResizing(e, handle) {
        this.isResizing = true;
        this.resizeHandle = handle;
        this.resizeElement = handle.parentElement;
        this.resizeStartX = e.clientX;
        this.resizeStartY = e.clientY;
        this.resizeStartWidth = parseInt(this.resizeElement.style.width);
        this.resizeStartHeight = parseInt(this.resizeElement.style.height);
        this.resizeStartLeft = parseInt(this.resizeElement.style.left);
        this.resizeStartTop = parseInt(this.resizeElement.style.top);
        this.resizePosition = handle.dataset.position;
        
        e.stopPropagation();
    }

    resize(e) {
        if (!this.isResizing || !this.resizeElement) return;
        
        const deltaX = e.clientX - this.resizeStartX;
        const deltaY = e.clientY - this.resizeStartY;
        
        // Get mobile constraints
        const maxCanvasWidth = this.getMaxCanvasWidth();
        const maxCanvasHeight = this.getMaxCanvasHeight();
        const maxElementWidth = maxCanvasWidth - 40;
        const maxElementHeight = maxCanvasHeight - 40;
        
        let newWidth = this.resizeStartWidth;
        let newHeight = this.resizeStartHeight;
        let newLeft = this.resizeStartLeft;
        let newTop = this.resizeStartTop;
        
        switch(this.resizePosition) {
            case 'se':
                newWidth = Math.max(50, Math.min(maxElementWidth, this.resizeStartWidth + deltaX));
                newHeight = Math.max(50, Math.min(maxElementHeight, this.resizeStartHeight + deltaY));
                break;
            case 'sw':
                newWidth = Math.max(50, Math.min(maxElementWidth, this.resizeStartWidth - deltaX));
                newHeight = Math.max(50, Math.min(maxElementHeight, this.resizeStartHeight + deltaY));
                newLeft = this.resizeStartLeft + deltaX;
                if (newWidth === 50) newLeft = this.resizeStartLeft + this.resizeStartWidth - 50;
                break;
            case 'ne':
                newWidth = Math.max(50, Math.min(maxElementWidth, this.resizeStartWidth + deltaX));
                newHeight = Math.max(50, Math.min(maxElementHeight, this.resizeStartHeight - deltaY));
                newTop = this.resizeStartTop + deltaY;
                if (newHeight === 50) newTop = this.resizeStartTop + this.resizeStartHeight - 50;
                break;
            case 'nw':
                newWidth = Math.max(50, Math.min(maxElementWidth, this.resizeStartWidth - deltaX));
                newHeight = Math.max(50, Math.min(maxElementHeight, this.resizeStartHeight - deltaY));
                newLeft = this.resizeStartLeft + deltaX;
                newTop = this.resizeStartTop + deltaY;
                if (newWidth === 50) newLeft = this.resizeStartLeft + this.resizeStartWidth - 50;
                if (newHeight === 50) newTop = this.resizeStartTop + this.resizeStartHeight - 50;
                break;
        }
        
        this.resizeElement.style.width = newWidth + 'px';
        this.resizeElement.style.height = newHeight + 'px';
        
        // Обновляем свойства
        this.updatePropertyDisplay('propWidth', newWidth);
        this.updatePropertyDisplay('propHeight', newHeight);
    }

    stopResizing() {
        this.isResizing = false;
        this.resizeHandle = null;
        this.resizeElement = null;
    }

    updatePropertyDisplay(propId, value) {
        const propElement = document.getElementById(propId);
        if (propElement) {
            propElement.value = value;
            const valueDisplay = propElement.parentElement.querySelector('.property-value');
            if (valueDisplay) {
                valueDisplay.textContent = value + 'px';
            }
        }
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
