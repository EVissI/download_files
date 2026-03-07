/**
 * Card Editor Module
 * Модуль для редактирования карточек с различными типами контента
 */

class CardEditor {
    constructor() {
        this.modal = null;
        this.currentContentType = null;
        this.init();
    }

    init() {
        this.createModal();
    }

    createModal() {
        // Создаем модальное окно редактора
        const modalHTML = `
            <div id="cardEditorModal" class="card-editor-modal" style="display: none;">
                <div class="card-editor-overlay" onclick="cardEditor.closeModal()"></div>
                <div class="card-editor-container">
                    <div class="card-editor-header">
                        <h2>Редактор карточек</h2>
                        <button class="close-btn" onclick="cardEditor.closeModal()">&times;</button>
                    </div>
                    <div class="card-editor-body">
                        <div class="content-type-selector">
                            <h3>Выберите тип контента:</h3>
                            <div class="content-type-grid">
                                <div class="content-type-item" data-type="board" onclick="cardEditor.selectContentType('board')">
                                    <div class="content-type-icon">📋</div>
                                    <div class="content-type-title">Доска с параметрами</div>
                                    <div class="content-type-desc">Манигейм / матч</div>
                                </div>
                                <div class="content-type-item" data-type="question" onclick="cardEditor.selectContentType('question')">
                                    <div class="content-type-icon">❓</div>
                                    <div class="content-type-title">Текст вопроса</div>
                                    <div class="content-type-desc">Вопрос для карточки</div>
                                </div>
                                <div class="content-type-item" data-type="table" onclick="cardEditor.selectContentType('table')">
                                    <div class="content-type-icon">📊</div>
                                    <div class="content-type-title">Таблица</div>
                                    <div class="content-type-desc">Табличные данные</div>
                                </div>
                                <div class="content-type-item" data-type="answer" onclick="cardEditor.selectContentType('answer')">
                                    <div class="content-type-icon">💬</div>
                                    <div class="content-type-title">Текст ответа</div>
                                    <div class="content-type-desc">Ответ на вопрос</div>
                                </div>
                                <div class="content-type-item" data-type="image" onclick="cardEditor.selectContentType('image')">
                                    <div class="content-type-icon">🖼️</div>
                                    <div class="content-type-title">Иллюстрация</div>
                                    <div class="content-type-desc">Изображение</div>
                                </div>
                                <div class="content-type-item" data-type="audio" onclick="cardEditor.selectContentType('audio')">
                                    <div class="content-type-icon">🎵</div>
                                    <div class="content-type-title">Аудио-файл</div>
                                    <div class="content-type-desc">Звуковой файл</div>
                                </div>
                                <div class="content-type-item" data-type="link" onclick="cardEditor.selectContentType('link')">
                                    <div class="content-type-icon">🔗</div>
                                    <div class="content-type-title">Ссылка</div>
                                    <div class="content-type-desc">Веб-ссылка</div>
                                </div>
                            </div>
                        </div>
                        <div class="content-editor" id="contentEditor" style="display: none;">
                            <!-- Динамический контент редактора -->
                        </div>
                    </div>
                    <div class="card-editor-footer">
                        <button class="btn btn-secondary" onclick="cardEditor.closeModal()">Отмена</button>
                        <button class="btn btn-primary" id="saveContentBtn" onclick="cardEditor.saveContent()" style="display: none;">Сохранить</button>
                    </div>
                </div>
            </div>
        `;

        // Добавляем модальное окно в body
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.modal = document.getElementById('cardEditorModal');
    }

    openModal() {
        this.modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
    }

    closeModal() {
        this.modal.style.display = 'none';
        document.body.style.overflow = 'auto';
        this.resetEditor();
    }

    selectContentType(type) {
        this.currentContentType = type;
        
        // Подсвечиваем выбранный тип
        document.querySelectorAll('.content-type-item').forEach(item => {
            item.classList.remove('selected');
        });
        document.querySelector(`[data-type="${type}"]`).classList.add('selected');

        // Показываем редактор для выбранного типа
        this.showContentEditor(type);
    }

    showContentEditor(type) {
        const editorContainer = document.getElementById('contentEditor');
        const saveBtn = document.getElementById('saveContentBtn');
        
        let editorHTML = '';

        switch (type) {
            case 'board':
                editorHTML = this.getBoardEditorHTML();
                break;
            case 'question':
                editorHTML = this.getQuestionEditorHTML();
                break;
            case 'table':
                editorHTML = this.getTableEditorHTML();
                break;
            case 'answer':
                editorHTML = this.getAnswerEditorHTML();
                break;
            case 'image':
                editorHTML = this.getImageEditorHTML();
                break;
            case 'audio':
                editorHTML = this.getAudioEditorHTML();
                break;
            case 'link':
                editorHTML = this.getLinkEditorHTML();
                break;
        }

        editorContainer.innerHTML = editorHTML;
        editorContainer.style.display = 'block';
        saveBtn.style.display = 'inline-block';
    }

    getBoardEditorHTML() {
        return `
            <div class="editor-form">
                <h3>Параметры доски</h3>
                <div class="form-group">
                    <label for="boardType">Тип доски:</label>
                    <select id="boardType" class="form-control">
                        <option value="manigame">Манигейм</option>
                        <option value="match">Матч</option>
                        <option value="tournament">Турнир</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="boardTitle">Название:</label>
                    <input type="text" id="boardTitle" class="form-control" placeholder="Введите название доски">
                </div>
                <div class="form-group">
                    <label for="boardDescription">Описание:</label>
                    <textarea id="boardDescription" class="form-control" placeholder="Введите описание доски"></textarea>
                </div>
                <div class="form-group">
                    <label for="boardPlayers">Количество игроков:</label>
                    <input type="number" id="boardPlayers" class="form-control" min="2" max="10" value="2">
                </div>
            </div>
        `;
    }

    getQuestionEditorHTML() {
        return `
            <div class="editor-form">
                <h3>Текст вопроса</h3>
                <div class="form-group">
                    <label for="questionText">Вопрос:</label>
                    <textarea id="questionText" class="form-control" rows="4" placeholder="Введите текст вопроса"></textarea>
                </div>
                <div class="form-group">
                    <label for="questionCategory">Категория:</label>
                    <input type="text" id="questionCategory" class="form-control" placeholder="Введите категорию вопроса">
                </div>
                <div class="form-group">
                    <label for="questionDifficulty">Сложность:</label>
                    <select id="questionDifficulty" class="form-control">
                        <option value="easy">Легкий</option>
                        <option value="medium">Средний</option>
                        <option value="hard">Сложный</option>
                    </select>
                </div>
            </div>
        `;
    }

    getTableEditorHTML() {
        return `
            <div class="editor-form">
                <h3>Таблица</h3>
                <div class="form-group">
                    <label for="tableTitle">Заголовок таблицы:</label>
                    <input type="text" id="tableTitle" class="form-control" placeholder="Введите заголовок">
                </div>
                <div class="form-group">
                    <label for="tableRows">Количество строк:</label>
                    <input type="number" id="tableRows" class="form-control" min="1" max="20" value="3">
                </div>
                <div class="form-group">
                    <label for="tableColumns">Количество колонок:</label>
                    <input type="number" id="tableColumns" class="form-control" min="1" max="10" value="3">
                </div>
                <div class="form-group">
                    <button type="button" class="btn btn-secondary" onclick="cardEditor.generateTable()">Сгенерировать таблицу</button>
                </div>
                <div id="tableContainer"></div>
            </div>
        `;
    }

    getAnswerEditorHTML() {
        return `
            <div class="editor-form">
                <h3>Текст ответа</h3>
                <div class="form-group">
                    <label for="answerText">Ответ:</label>
                    <textarea id="answerText" class="form-control" rows="4" placeholder="Введите текст ответа"></textarea>
                </div>
                <div class="form-group">
                    <label for="answerType">Тип ответа:</label>
                    <select id="answerType" class="form-control">
                        <option value="text">Текст</option>
                        <option value="number">Число</option>
                        <option value="boolean">Да/Нет</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="answerExplanation">Пояснение:</label>
                    <textarea id="answerExplanation" class="form-control" rows="2" placeholder="Введите пояснение к ответу"></textarea>
                </div>
            </div>
        `;
    }

    getImageEditorHTML() {
        return `
            <div class="editor-form">
                <h3>Иллюстрация</h3>
                <div class="form-group">
                    <label for="imageFile">Выберите файл:</label>
                    <input type="file" id="imageFile" class="form-control" accept="image/*">
                </div>
                <div class="form-group">
                    <label for="imageUrl">Или URL изображения:</label>
                    <input type="url" id="imageUrl" class="form-control" placeholder="https://example.com/image.jpg">
                </div>
                <div class="form-group">
                    <label for="imageAlt">Альтернативный текст:</label>
                    <input type="text" id="imageAlt" class="form-control" placeholder="Описание изображения">
                </div>
                <div class="form-group">
                    <label for="imageCaption">Подпись:</label>
                    <input type="text" id="imageCaption" class="form-control" placeholder="Подпись к изображению">
                </div>
                <div id="imagePreview"></div>
            </div>
        `;
    }

    getAudioEditorHTML() {
        return `
            <div class="editor-form">
                <h3>Аудио-файл</h3>
                <div class="form-group">
                    <label for="audioFile">Выберите файл:</label>
                    <input type="file" id="audioFile" class="form-control" accept="audio/*">
                </div>
                <div class="form-group">
                    <label for="audioUrl">Или URL аудио:</label>
                    <input type="url" id="audioUrl" class="form-control" placeholder="https://example.com/audio.mp3">
                </div>
                <div class="form-group">
                    <label for="audioTitle">Название:</label>
                    <input type="text" id="audioTitle" class="form-control" placeholder="Название аудио">
                </div>
                <div class="form-group">
                    <label for="audioDescription">Описание:</label>
                    <textarea id="audioDescription" class="form-control" rows="2" placeholder="Описание аудио"></textarea>
                </div>
                <div id="audioPreview"></div>
            </div>
        `;
    }

    getLinkEditorHTML() {
        return `
            <div class="editor-form">
                <h3>Ссылка</h3>
                <div class="form-group">
                    <label for="linkUrl">URL:</label>
                    <input type="url" id="linkUrl" class="form-control" placeholder="https://example.com">
                </div>
                <div class="form-group">
                    <label for="linkTitle">Заголовок:</label>
                    <input type="text" id="linkTitle" class="form-control" placeholder="Заголовок ссылки">
                </div>
                <div class="form-group">
                    <label for="linkDescription">Описание:</label>
                    <textarea id="linkDescription" class="form-control" rows="2" placeholder="Описание ссылки"></textarea>
                </div>
                <div class="form-group">
                    <label for="linkTarget">Открытие:</label>
                    <select id="linkTarget" class="form-control">
                        <option value="_blank">В новой вкладке</option>
                        <option value="_self">В той же вкладке</option>
                    </select>
                </div>
            </div>
        `;
    }

    generateTable() {
        const rows = parseInt(document.getElementById('tableRows').value);
        const columns = parseInt(document.getElementById('tableColumns').value);
        const container = document.getElementById('tableContainer');
        
        let tableHTML = `
            <div class="table-editor">
                <table class="table table-bordered">
                    <thead>
                        <tr>
        `;
        
        for (let i = 0; i < columns; i++) {
            tableHTML += `<th><input type="text" class="form-control" placeholder="Колонка ${i + 1}"></th>`;
        }
        
        tableHTML += `
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        for (let i = 0; i < rows; i++) {
            tableHTML += '<tr>';
            for (let j = 0; j < columns; j++) {
                tableHTML += `<td><input type="text" class="form-control" placeholder="Ячейка ${i + 1}-${j + 1}"></td>`;
            }
            tableHTML += '</tr>';
        }
        
        tableHTML += `
                    </tbody>
                </table>
            </div>
        `;
        
        container.innerHTML = tableHTML;
    }

    saveContent() {
        const content = this.collectContent();
        
        // Здесь можно добавить логику сохранения контента
        console.log('Сохранение контента:', content);
        
        // Показываем сообщение об успешном сохранении
        if (typeof showMessageModal === 'function') {
            showMessageModal('Контент успешно сохранен!', 'success');
        } else {
            alert('Контент успешно сохранен!');
        }
        
        this.closeModal();
    }

    collectContent() {
        const content = {
            type: this.currentContentType,
            data: {}
        };

        switch (this.currentContentType) {
            case 'board':
                content.data = {
                    type: document.getElementById('boardType').value,
                    title: document.getElementById('boardTitle').value,
                    description: document.getElementById('boardDescription').value,
                    players: document.getElementById('boardPlayers').value
                };
                break;
            case 'question':
                content.data = {
                    text: document.getElementById('questionText').value,
                    category: document.getElementById('questionCategory').value,
                    difficulty: document.getElementById('questionDifficulty').value
                };
                break;
            case 'answer':
                content.data = {
                    text: document.getElementById('answerText').value,
                    type: document.getElementById('answerType').value,
                    explanation: document.getElementById('answerExplanation').value
                };
                break;
            case 'link':
                content.data = {
                    url: document.getElementById('linkUrl').value,
                    title: document.getElementById('linkTitle').value,
                    description: document.getElementById('linkDescription').value,
                    target: document.getElementById('linkTarget').value
                };
                break;
        }

        return content;
    }

    resetEditor() {
        this.currentContentType = null;
        document.querySelectorAll('.content-type-item').forEach(item => {
            item.classList.remove('selected');
        });
        document.getElementById('contentEditor').style.display = 'none';
        document.getElementById('saveContentBtn').style.display = 'none';
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
