export function setupTextEditingImpl(editor, element) {
    const textContent = element.querySelector('.text-content');
    if (!textContent) return;
    editor.autoGrowTextElementContainer(element);

    // Предотвращаем всплытие события клика, чтобы не выделять элемент при редактировании текста
    textContent.addEventListener('mousedown', (e) => {
        e.stopPropagation();
        if (e.target === textContent) {
            textContent.focus();
        }
    });

    // Добавляем обработчик фокуса для открытия свойств
    textContent.addEventListener('focus', () => {
        editor.selectElement(element);
    });

    // Обработка окончания редактирования и сохранение выделения для форматирования
    textContent.addEventListener('blur', () => {
        editor.saveSelectionForEditable(textContent);
        // Если текст пустой, возвращаем placeholder
        if (textContent.textContent.trim() === '') {
            if (element.dataset.toolId === 'question-text') {
                textContent.textContent = 'Текст вопроса';
            } else if (element.dataset.toolId === 'answer-text') {
                textContent.textContent = 'Текст ответа';
            }
        }
        editor.autoGrowTextElementContainer(element);
        requestAnimationFrame(() => editor.autoGrowTextElementContainer(element));
    });

    // Обработка ввода текста - только перенос строк
    textContent.addEventListener('input', () => {
        editor.autoGrowTextElementContainer(element);
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
                editor.autoGrowTextElementContainer(element);
            }
        } else if (e.key === 'Backspace' || e.key === 'Delete') {
            // После массового удаления (например Ctrl+A + Delete) схлопываем высоту блока.
            requestAnimationFrame(() => editor.autoGrowTextElementContainer(element));
        }
    });
}

export function autoGrowTextElementContainerImpl(editor, element, options = {}) {
    if (!element || !editor.canvas || !element.classList.contains('canvas-element')) return;
    const tid = element.dataset.toolId;
    if (!['question-text', 'answer-text', 'support-link'].includes(tid)) return;

    const contentNode = element.querySelector('.text-content, .link-text');
    if (!contentNode) return;
    const skipReposition = !!(options && options.skipReposition);

    // Ограничиваем ширину текстового блока доступной шириной канваса
    // (важно при ресайзе панелей/экрана, когда меняется рабочая область).
    const canvasWidth = editor.canvas.clientWidth || editor.canvas.getBoundingClientRect().width || 0;
    if (canvasWidth > 0) {
        const left = parseFloat(element.style.left) || 0;
        const maxAllowedWidth = Math.max(80, Math.floor(canvasWidth - left));
        const currentWidth = parseFloat(element.style.width) || 0;
        if (!currentWidth || currentWidth > maxAllowedWidth || currentWidth < 80) {
            element.style.width = `${maxAllowedWidth}px`;
        }
    }

    const cs = window.getComputedStyle(contentNode);
    const lineHeight = parseFloat(cs.lineHeight) || 20;
    const minElementHeight = 36;
    const innerPadding = parseFloat(element.style.padding) || 0;
    const currentHeight = parseFloat(element.style.height) || element.getBoundingClientRect().height || 0;
    const linkContentNode = tid === 'support-link' ? element.querySelector('.link-content') : null;
    let extraVerticalPadding = 0;
    if (linkContentNode) {
        const lcs = window.getComputedStyle(linkContentNode);
        extraVerticalPadding =
            (parseFloat(lcs.paddingTop) || 0) +
            (parseFloat(lcs.paddingBottom) || 0);
    }

    // Временно снимаем фиксированную высоту, чтобы корректно считать shrink после удаления текста.
    const prevHeight = element.style.height;
    const prevContentHeight = contentNode.style.height;
    element.style.height = 'auto';
    if (tid === 'support-link') {
        // Для link-блока scrollHeight корректно считается при авто-высоте.
        contentNode.style.height = 'auto';
    }
    const contentHeight = Math.max(contentNode.scrollHeight, lineHeight + 8);
    const targetHeight = Math.max(
        minElementHeight,
        Math.ceil(contentHeight + innerPadding * 2 + extraVerticalPadding)
    );

    if (Math.abs(targetHeight - currentHeight) < 1) {
        contentNode.style.height = prevContentHeight;
        element.style.height = prevHeight;
        return;
    }
    element.style.height = `${targetHeight}px`;
    contentNode.style.height = prevContentHeight;
    if (!skipReposition && element.id) editor.repositionElementsBelow(element.id);
}

export function beginTextBlockHeightDragImpl(editor, element, startClientY) {
    const startH = element.getBoundingClientRect().height;
    const minH = 36;
    const maxH = editor.canvas
        ? Math.max(editor.canvas.scrollHeight, editor.canvas.clientHeight) + 400
        : 2400;
    const prevUserSelect = document.body.style.userSelect;
    document.body.style.userSelect = 'none';

    element.classList.add('is-text-height-resizing');
    if (editor.canvas) editor.canvas.classList.add('ce-text-resize-active');

    let rafId = 0;
    let latestClientY = startClientY;

    const applyFrame = () => {
        rafId = 0;
        let nh = startH + (latestClientY - startClientY);
        nh = Math.max(minH, Math.min(maxH, nh));
        element.style.height = `${nh}px`;
        if (element.id) editor.repositionElementsBelow(element.id);
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
        if (element.id) editor.repositionElementsBelow(element.id);

        element.classList.remove('is-text-height-resizing');
        if (editor.canvas) editor.canvas.classList.remove('ce-text-resize-active');

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
