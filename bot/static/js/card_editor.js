/**
 * Card Editor Module
 * Редактор для выбора и настройки контента со страницы
 */

class CardEditor {
    constructor() {
        this.modal = null;
        this.selectedElements = [];
        this.init();
    }

    init() {
        this.createModal();
        this.detectAvailableContent();
    }

    createModal() {
        // Создаем модальное окно редактора
        const modalHTML = `
            <div id="cardEditorModal" class="card-editor-modal" style="display: none;">
                <div class="card-editor-overlay" onclick="cardEditor.closeModal()"></div>
                <div class="card-editor-container">
                    <div class="card-editor-header">
                        <h2>Редактор контента страницы</h2>
                        <button class="close-btn" onclick="cardEditor.closeModal()">&times;</button>
                    </div>
                    <div class="card-editor-body">
                        <div class="content-selector">
                            <h3>Доступный контент на странице:</h3>
                            <div class="content-list" id="contentList">
                                <!-- Динамический список доступного контента -->
                            </div>
                        </div>
                        <div class="selected-content" id="selectedContent" style="display: none;">
                            <h3>Выбранный контент:</h3>
                            <div class="content-preview" id="contentPreview">
                                <!-- Предпросмотр выбранного контента -->
                            </div>
                            <div class="content-controls">
                                <div class="control-group">
                                    <h4>Размеры:</h4>
                                    <div class="size-controls">
                                        <div class="control-item">
                                            <label>Ширина:</label>
                                            <input type="range" id="widthSlider" min="100" max="1200" value="400">
                                            <span id="widthValue">400px</span>
                                        </div>
                                        <div class="control-item">
                                            <label>Высота:</label>
                                            <input type="range" id="heightSlider" min="100" max="800" value="300">
                                            <span id="heightValue">300px</span>
                                        </div>
                                        <div class="control-item">
                                            <label>
                                                <input type="checkbox" id="autoSize"> Автоматический размер
                                            </label>
                                        </div>
                                    </div>
                                </div>
                                <div class="control-group">
                                    <h4>Позиционирование:</h4>
                                    <div class="position-controls">
                                        <div class="control-item">
                                            <label>Позиция X:</label>
                                            <input type="range" id="positionX" min="0" max="100" value="50">
                                            <span id="positionXValue">50%</span>
                                        </div>
                                        <div class="control-item">
                                            <label>Позиция Y:</label>
                                            <input type="range" id="positionY" min="0" max="100" value="50">
                                            <span id="positionYValue">50%</span>
                                        </div>
                                        <div class="control-item">
                                            <label>Z-индекс:</label>
                                            <input type="number" id="zIndex" min="1" max="9999" value="100">
                                        </div>
                                    </div>
                                </div>
                                <div class="control-group">
                                    <h4>Стиль:</h4>
                                    <div class="style-controls">
                                        <div class="control-item">
                                            <label>Обводка:</label>
                                            <input type="color" id="borderColor" value="#007bff">
                                            <input type="range" id="borderWidth" min="0" max="10" value="2">
                                            <span id="borderWidthValue">2px</span>
                                        </div>
                                        <div class="control-item">
                                            <label>Прозрачность:</label>
                                            <input type="range" id="opacity" min="0" max="100" value="100">
                                            <span id="opacityValue">100%</span>
                                        </div>
                                        <div class="control-item">
                                            <label>
                                                <input type="checkbox" id="shadow"> Тень
                                            </label>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="card-editor-footer">
                        <button class="btn btn-secondary" onclick="cardEditor.closeModal()">Закрыть</button>
                    </div>
                </div>
            </div>
        `;

        // Добавляем модальное окно в body
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.modal = document.getElementById('cardEditorModal');
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Слушатели для слайдеров
        const widthSlider = document.getElementById('widthSlider');
        const heightSlider = document.getElementById('heightSlider');
        const positionX = document.getElementById('positionX');
        const positionY = document.getElementById('positionY');
        const borderWidth = document.getElementById('borderWidth');
        const opacity = document.getElementById('opacity');

        if (widthSlider) {
            widthSlider.addEventListener('input', (e) => {
                document.getElementById('widthValue').textContent = e.target.value + 'px';
                this.updatePreview();
            });
        }

        if (heightSlider) {
            heightSlider.addEventListener('input', (e) => {
                document.getElementById('heightValue').textContent = e.target.value + 'px';
                this.updatePreview();
            });
        }

        if (positionX) {
            positionX.addEventListener('input', (e) => {
                document.getElementById('positionXValue').textContent = e.target.value + '%';
                this.updatePreview();
            });
        }

        if (positionY) {
            positionY.addEventListener('input', (e) => {
                document.getElementById('positionYValue').textContent = e.target.value + '%';
                this.updatePreview();
            });
        }

        if (borderWidth) {
            borderWidth.addEventListener('input', (e) => {
                document.getElementById('borderWidthValue').textContent = e.target.value + 'px';
                this.updatePreview();
            });
        }

        if (opacity) {
            opacity.addEventListener('input', (e) => {
                document.getElementById('opacityValue').textContent = e.target.value + '%';
                this.updatePreview();
            });
        }

        // Слушатели для чекбоксов
        ['autoSize', 'shadow'].forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener('change', () => this.updatePreview());
            }
        });

        // Слушатели для цвета и других полей
        ['borderColor', 'zIndex'].forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener('input', () => this.updatePreview());
            }
        });
    }

    detectAvailableContent() {
        const availableContent = [
            {
                id: 'match-info',
                name: 'Информация о матче',
                type: 'text',
                description: 'Информация о текущем матче/игре'
            },
            {
                id: 'players-info',
                name: 'Информация об игроках',
                type: 'text',
                description: 'Имена и статистика игроков'
            },
            {
                id: 'boardCanvas',
                name: 'Игровая доска',
                type: 'canvas',
                description: 'Визуализация игрового поля'
            },
            {
                id: 'move-info',
                name: 'Информация о ходе',
                type: 'text',
                description: 'Детали текущего хода'
            },
            {
                id: 'red-pips',
                name: 'Пипсы красных',
                type: 'text',
                description: 'Количество пипсов красного игрока'
            },
            {
                id: 'black-pips',
                name: 'Пипсы черных',
                type: 'text',
                description: 'Количество пипсов черного игрока'
            },
            {
                id: 'controls',
                name: 'Панель управления',
                type: 'controls',
                description: 'Кнопки управления игрой'
            },
            {
                id: 'hints-table',
                name: 'Таблица подсказок',
                type: 'table',
                description: 'Подсказки по ходам и кубу'
            },
            {
                id: 'moveHintsTable',
                name: 'Подсказки по ходам',
                type: 'table',
                description: 'Детальные подсказки по возможным ходам'
            },
            {
                id: 'cubeHintsTable',
                name: 'Подсказки по кубу',
                type: 'table',
                description: 'Рекомендации по удвоению'
            }
        ];

        this.renderContentList(availableContent);
    }

    renderContentList(contentList) {
        const container = document.getElementById('contentList');
        if (!container) return;

        let html = '';
        contentList.forEach(item => {
            const element = document.getElementById(item.id);
            const exists = element ? 'available' : 'unavailable';
            
            html += `
                <div class="content-item ${exists}" data-id="${item.id}" data-type="${item.type}" onclick="cardEditor.selectContent('${item.id}')">
                    <div class="content-item-header">
                        <div class="content-item-name">${item.name}</div>
                        <div class="content-item-type">${this.getTypeIcon(item.type)} ${item.type}</div>
                    </div>
                    <div class="content-item-description">${item.description}</div>
                    <div class="content-item-status">${exists === 'available' ? '✓ Доступно' : '✗ Не найдено'}</div>
                </div>
            `;
        });

        container.innerHTML = html;
    }

    getTypeIcon(type) {
        const icons = {
            'text': '📝',
            'canvas': '🎨',
            'controls': '🎮',
            'table': '📊'
        };
        return icons[type] || '📄';
    }

    selectContent(elementId) {
        const element = document.getElementById(elementId);
        if (!element) {
            if (typeof showMessageModal === 'function') {
                showMessageModal('Элемент не найден на странице', 'error');
            }
            return;
        }

        this.selectedElements = [elementId];
        this.showContentEditor(elementId, element);
        
        // Подсвечиваем выбранный элемент
        document.querySelectorAll('.content-item').forEach(item => {
            item.classList.remove('selected');
        });
        document.querySelector(`[data-id="${elementId}"]`).classList.add('selected');
    }

    showContentEditor(elementId, element) {
        const selectedContent = document.getElementById('selectedContent');
        
        selectedContent.style.display = 'block';

        // Показываем предпросмотр
        this.updatePreview(element);
    }

    updatePreview(element) {
        const preview = document.getElementById('contentPreview');
        if (!preview) return;

        if (!element && this.selectedElements.length > 0) {
            element = document.getElementById(this.selectedElements[0]);
        }

        if (!element) return;

        // Получаем настройки
        const width = document.getElementById('autoSize').checked ? 'auto' : document.getElementById('widthSlider').value + 'px';
        const height = document.getElementById('autoSize').checked ? 'auto' : document.getElementById('heightSlider').value + 'px';
        const posX = document.getElementById('positionX').value + '%';
        const posY = document.getElementById('positionY').value + '%';
        const zIndex = document.getElementById('zIndex').value;
        const borderColor = document.getElementById('borderColor').value;
        const borderWidth = document.getElementById('borderWidth').value + 'px';
        const opacity = document.getElementById('opacity').value / 100;
        const shadow = document.getElementById('shadow').checked;

        // Создаем клон элемента для предпросмотра
        const clone = element.cloneNode(true);
        clone.id = 'preview-clone';

        // Применяем стили
        const previewStyles = {
            width: width,
            height: height,
            position: 'relative',
            left: posX,
            top: posY,
            zIndex: zIndex,
            border: `${borderWidth} solid ${borderColor}`,
            opacity: opacity,
            boxShadow: shadow ? '0 4px 8px rgba(0,0,0,0.2)' : 'none',
            transform: 'translate(-50%, -50%)',
            maxWidth: '90%',
            maxHeight: '300px',
            overflow: 'auto'
        };

        // Применяем стили к клону
        Object.assign(clone.style, previewStyles);

        // Очищаем и добавляем предпросмотр
        preview.innerHTML = '';
        preview.appendChild(clone);
    }

    openModal() {
        this.modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
        this.detectAvailableContent(); // Обновляем список при открытии
    }

    closeModal() {
        this.modal.style.display = 'none';
        document.body.style.overflow = 'auto';
        this.resetEditor();
    }

    resetEditor() {
        this.selectedElements = [];
        document.querySelectorAll('.content-item').forEach(item => {
            item.classList.remove('selected');
        });
        document.getElementById('selectedContent').style.display = 'none';
    }
}

// Создаем глобальный экземпляр редактора
let cardEditor;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    cardEditor = new CardEditor();
});

// Глобальная функция для открытия редактора
function openCardEditor() {
    if (cardEditor) {
        cardEditor.openModal();
    }
}
