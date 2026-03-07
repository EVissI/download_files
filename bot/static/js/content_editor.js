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
        this.isDragging = false;
        this.isResizing = false;
        this.dragStartX = 0;
        this.dragStartY = 0;
        this.elementStartX = 0;
        this.elementStartY = 0;
        this.currentResizeHandle = null;
        
        this.init();
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
        this.modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        this.loadTools(); // Обновляем инструменты при открытии
    }

    closeModal() {
        this.modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }

    loadTools() {
        // Определяем доступные инструменты согласно требованиям
        const tools = [
            {
                id: 'boardCanvas',
                name: 'Доска с параметрами',
                type: 'canvas',
                description: 'Игровая доска с параметрами (манигейм/матч)',
                available: true
            },
            {
                id: 'question-text',
                name: 'Текст вопроса',
                type: 'text',
                description: 'Текст вопроса для анализа',
                available: false // Будем создавать программно
            },
            {
                id: 'moveHintsTable',
                name: 'Таблица',
                type: 'table',
                description: 'Таблица подсказок или данных',
                available: true
            },
            {
                id: 'answer-text',
                name: 'Текст ответа',
                type: 'text',
                description: 'Текст ответа или решения',
                available: false // Будем создавать программно
            },
            {
                id: 'board-illustration',
                name: 'Иллюстрация',
                type: 'image',
                description: 'Изображение доски как иллюстрация',
                available: true
            },
            {
                id: 'audio-file',
                name: 'Аудио-файл',
                type: 'audio',
                description: 'Аудиофайл для воспроизведения',
                available: false // Будем создавать программно
            },
            {
                id: 'support-link',
                name: 'Ссылка',
                type: 'link',
                description: 'Ссылка на дополнительные материалы',
                available: false // Будем создавать программно
            }
        ];

        this.renderTools(tools);
    }

    renderTools(tools) {
        this.toolsList.innerHTML = tools.map(tool => `
            <div class="tool-item ${tool.available ? 'available' : 'unavailable'}" 
                 data-tool-id="${tool.id}"
                 onclick="contentEditor.selectTool('${tool.id}')">
                <div class="tool-item-header">
                    <span class="tool-name">${tool.name}</span>
                    <span class="tool-type">${tool.type}</span>
                </div>
                <div class="tool-description">${tool.description}</div>
                <div class="tool-status ${tool.available ? 'available' : 'unavailable'}">
                    ${tool.available ? '✓ Доступно' : '✗ Недоступно'}
                </div>
            </div>
        `).join('');
    }

    selectTool(toolId) {
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

    addElementToCanvas(toolId) {
        const elementId = `element_${this.elementIdCounter++}`;
        const element = document.createElement('div');
        element.id = elementId;
        element.className = 'canvas-element';
        element.dataset.toolId = toolId;
        
        // Позиционируем элемент в центре холста со смещением
        const canvasRect = this.canvas.getBoundingClientRect();
        const x = Math.random() * (canvasRect.width - 200) + 50;
        const y = Math.random() * (canvasRect.height - 150) + 50;
        
        element.style.left = x + 'px';
        element.style.top = y + 'px';
        element.style.width = '200px';
        element.style.height = '150px';
        
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
        // Очищаем элемент
        element.innerHTML = '';
        
        switch(toolId) {
            case 'boardCanvas':
                // Доска с параметрами
                const originalCanvas = document.getElementById('boardCanvas');
                if (originalCanvas) {
                    const clonedCanvas = originalCanvas.cloneNode(true);
                    clonedCanvas.style.width = '100%';
                    clonedCanvas.style.height = '100%';
                    element.appendChild(clonedCanvas);
                } else {
                    element.innerHTML = `
                        <div style="padding: 20px; text-align: center; color: #666;">
                            <strong>Доска не найдена</strong><br>
                            <small>Игровая доска не доступна на странице</small>
                        </div>
                    `;
                }
                break;
                
            case 'question-text':
                // Текст вопроса
                element.innerHTML = `
                    <div style="padding: 15px; height: 100%; display: flex; flex-direction: column; justify-content: center;">
                        <textarea placeholder="Введите текст вопроса..." 
                                  style="width: 100%; height: 80%; border: 1px solid #ddd; border-radius: 4px; padding: 10px; resize: none; font-family: inherit;"
                                  onchange="this.parentElement.querySelector('.text-preview').innerHTML = this.value.replace(/\\n/g, '<br>')"></textarea>
                        <div class="text-preview" style="margin-top: 10px; padding: 10px; background: #f5f5f5; border-radius: 4px; min-height: 40px;"></div>
                    </div>
                `;
                break;
                
            case 'moveHintsTable':
                // Таблица
                const originalTable = document.getElementById('moveHintsTable');
                if (originalTable) {
                    const clonedTable = originalTable.cloneNode(true);
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
                    // Создаем изображение из canvas
                    const img = document.createElement('img');
                    img.src = canvasForImage.toDataURL();
                    img.style.width = '100%';
                    img.style.height = '100%';
                    img.style.objectFit = 'contain';
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
                
            case 'support-link':
                // Ссылка
                element.innerHTML = `
                    <div style="padding: 20px; height: 100%; display: flex; flex-direction: column; justify-content: center;">
                        <label style="display: block; margin-bottom: 10px; font-weight: bold;">URL ссылки:</label>
                        <input type="url" placeholder="https://example.com" 
                               style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 10px;"
                               oninput="this.parentElement.querySelector('.link-preview').href = this.value; this.parentElement.querySelector('.link-preview').textContent = this.value || 'Ссылка'">
                        <a href="#" class="link-preview" target="_blank" 
                           style="display: inline-block; padding: 8px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 4px;">Ссылка</a>
                    </div>
                `;
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
        
        this.propertiesContent.innerHTML = `
            <div class="property-group">
                <h4>Основные</h4>
                <div class="property-item">
                    <label>ID:</label>
                    <input type="text" value="${element.id}" readonly style="background: #2a2a2a;">
                </div>
                <div class="property-item">
                    <label>Тип:</label>
                    <input type="text" value="${element.dataset.toolId}" readonly style="background: #2a2a2a;">
                </div>
            </div>
            
            <div class="property-group">
                <h4>Позиция</h4>
                <div class="property-item">
                    <label>X:</label>
                    <input type="range" id="propX" min="0" max="${this.canvas.offsetWidth - 100}" 
                           value="${parseInt(element.style.left)}" 
                           oninput="contentEditor.updateElementProperty('left', this.value + 'px')">
                    <div class="property-value">${parseInt(element.style.left)}px</div>
                </div>
                <div class="property-item">
                    <label>Y:</label>
                    <input type="range" id="propY" min="0" max="${this.canvas.offsetHeight - 100}" 
                           value="${parseInt(element.style.top)}" 
                           oninput="contentEditor.updateElementProperty('top', this.value + 'px')">
                    <div class="property-value">${parseInt(element.style.top)}px</div>
                </div>
                <div class="property-item">
                    <label>Z-Index:</label>
                    <input type="number" id="propZ" min="1" max="9999" value="${element.style.zIndex || 1}" 
                           oninput="contentEditor.updateElementProperty('zIndex', this.value)">
                </div>
            </div>
            
            <div class="property-group">
                <h4>Размер</h4>
                <div class="property-item">
                    <label>Ширина:</label>
                    <input type="range" id="propWidth" min="50" max="800" 
                           value="${parseInt(element.style.width)}" 
                           oninput="contentEditor.updateElementProperty('width', this.value + 'px')">
                    <div class="property-value">${parseInt(element.style.width)}px</div>
                </div>
                <div class="property-item">
                    <label>Высота:</label>
                    <input type="range" id="propHeight" min="50" max="600" 
                           value="${parseInt(element.style.height)}" 
                           oninput="contentEditor.updateElementProperty('height', this.value + 'px')">
                    <div class="property-value">${parseInt(element.style.height)}px</div>
                </div>
            </div>
            
            <div class="property-group">
                <h4>Стиль</h4>
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
        }
    }

    duplicateElement(elementId) {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        const newElement = element.cloneNode(true);
        const newId = `element_${this.elementIdCounter++}`;
        newElement.id = newId;
        
        // Смещаем дубликат
        const currentLeft = parseInt(element.style.left);
        const currentTop = parseInt(element.style.top);
        newElement.style.left = (currentLeft + 20) + 'px';
        newElement.style.top = (currentTop + 20) + 'px';
        
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
    }

    setupCanvasEvents() {
        // Перетаскивание элементов
        this.canvas.addEventListener('mousedown', (e) => {
            if (e.target.classList.contains('canvas-element') && 
                !e.target.classList.contains('resize-handle') &&
                !e.target.classList.contains('control-btn')) {
                this.startDragging(e, e.target);
            } else if (e.target.classList.contains('resize-handle')) {
                this.startResizing(e, e.target);
            }
        });

        document.addEventListener('mousemove', (e) => {
            if (this.isDragging) {
                this.drag(e);
            } else if (this.isResizing) {
                this.resize(e);
            }
        });

        document.addEventListener('mouseup', () => {
            this.stopDragging();
            this.stopResizing();
        });
    }

    startDragging(e, element) {
        this.isDragging = true;
        this.dragElement = element;
        this.dragStartX = e.clientX;
        this.dragStartY = e.clientY;
        this.elementStartX = parseInt(element.style.left);
        this.elementStartY = parseInt(element.style.top);
        
        element.classList.add('dragging');
        this.selectElement(element);
    }

    drag(e) {
        if (!this.isDragging || !this.dragElement) return;
        
        const deltaX = e.clientX - this.dragStartX;
        const deltaY = e.clientY - this.dragStartY;
        
        const newX = Math.max(0, Math.min(this.canvas.offsetWidth - this.dragElement.offsetWidth, 
                                         this.elementStartX + deltaX));
        const newY = Math.max(0, Math.min(this.canvas.offsetHeight - this.dragElement.offsetHeight, 
                                         this.elementStartY + deltaY));
        
        this.dragElement.style.left = newX + 'px';
        this.dragElement.style.top = newY + 'px';
        
        // Обновляем свойства
        this.updatePropertyDisplay('propX', newX);
        this.updatePropertyDisplay('propY', newY);
    }

    stopDragging() {
        if (this.dragElement) {
            this.dragElement.classList.remove('dragging');
        }
        this.isDragging = false;
        this.dragElement = null;
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
        
        let newWidth = this.resizeStartWidth;
        let newHeight = this.resizeStartHeight;
        let newLeft = this.resizeStartLeft;
        let newTop = this.resizeStartTop;
        
        switch(this.resizePosition) {
            case 'se':
                newWidth = Math.max(50, this.resizeStartWidth + deltaX);
                newHeight = Math.max(50, this.resizeStartHeight + deltaY);
                break;
            case 'sw':
                newWidth = Math.max(50, this.resizeStartWidth - deltaX);
                newHeight = Math.max(50, this.resizeStartHeight + deltaY);
                newLeft = this.resizeStartLeft + deltaX;
                if (newWidth === 50) newLeft = this.resizeStartLeft + this.resizeStartWidth - 50;
                break;
            case 'ne':
                newWidth = Math.max(50, this.resizeStartWidth + deltaX);
                newHeight = Math.max(50, this.resizeStartHeight - deltaY);
                newTop = this.resizeStartTop + deltaY;
                if (newHeight === 50) newTop = this.resizeStartTop + this.resizeStartHeight - 50;
                break;
            case 'nw':
                newWidth = Math.max(50, this.resizeStartWidth - deltaX);
                newHeight = Math.max(50, this.resizeStartHeight - deltaY);
                newLeft = this.resizeStartLeft + deltaX;
                newTop = this.resizeStartTop + deltaY;
                if (newWidth === 50) newLeft = this.resizeStartLeft + this.resizeStartWidth - 50;
                if (newHeight === 50) newTop = this.resizeStartTop + this.resizeStartHeight - 50;
                break;
        }
        
        this.resizeElement.style.width = newWidth + 'px';
        this.resizeElement.style.height = newHeight + 'px';
        this.resizeElement.style.left = newLeft + 'px';
        this.resizeElement.style.top = newTop + 'px';
        
        // Обновляем свойства
        this.updatePropertyDisplay('propWidth', newWidth);
        this.updatePropertyDisplay('propHeight', newHeight);
        this.updatePropertyDisplay('propX', newLeft);
        this.updatePropertyDisplay('propY', newTop);
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
}

// Создаем глобальный экземпляр редактора
let contentEditor;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    contentEditor = new ContentEditor();
});
