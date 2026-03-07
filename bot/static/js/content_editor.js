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
        // Определяем доступные инструменты (элементы контента со страницы)
        const tools = [
            {
                id: 'match-info',
                name: 'Информация о матче',
                type: 'info',
                description: 'Данные о текущем матче/игре',
                available: true
            },
            {
                id: 'players-info',
                name: 'Информация об игроках',
                type: 'info',
                description: 'Имена и статистика игроков',
                available: true
            },
            {
                id: 'boardCanvas',
                name: 'Игровая доска',
                type: 'canvas',
                description: 'Визуализация игрового поля',
                available: true
            },
            {
                id: 'move-info',
                name: 'Информация о ходе',
                type: 'info',
                description: 'Детали текущего хода',
                available: true
            },
            {
                id: 'red-pips',
                name: 'Пипсы красных',
                type: 'counter',
                description: 'Количество пипсов красного игрока',
                available: true
            },
            {
                id: 'black-pips',
                name: 'Пипсы черных',
                type: 'counter',
                description: 'Количество пипсов черного игрока',
                available: true
            },
            {
                id: 'controls',
                name: 'Панель управления',
                type: 'controls',
                description: 'Кнопки управления игрой',
                available: true
            },
            {
                id: 'moveHintsTable',
                name: 'Таблица подсказок ходов',
                type: 'table',
                description: 'Подсказки по возможным ходам',
                available: true
            },
            {
                id: 'cubeHintsTable',
                name: 'Таблица подсказок куба',
                type: 'table',
                description: 'Подсказки по удвоению',
                available: true
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
        // Получаем оригинальный элемент со страницы (если есть)
        const originalElement = document.getElementById(toolId);
        
        if (originalElement) {
            // Клонируем контент
            const clonedContent = originalElement.cloneNode(true);
            element.appendChild(clonedContent);
        } else {
            // Если оригинала нет, создаем заглушку
            element.innerHTML = `
                <div style="padding: 10px; text-align: center; color: #666;">
                    <strong>${toolId}</strong><br>
                    <small>Элемент не найден на странице</small>
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
