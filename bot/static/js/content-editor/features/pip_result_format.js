/** Эмодзи для верного / неверного ответа в блоке результата pip-интерактивов. */
export const PIP_RESULT_MARK_OK = '✅';
export const PIP_RESULT_MARK_BAD = '❌';

function mark(ok) {
    return ok ? PIP_RESULT_MARK_OK : PIP_RESULT_MARK_BAD;
}

function formatUserValue(v) {
    return v != null ? String(v) : '—';
}

/**
 * Результат блока «Подсчёт пипсов».
 * @param {string} elapsed
 * @param {{ upperPips: number, lowerPips: number } | null} ref
 * @param {number | null} userUpper
 * @param {number | null} userLower
 */
export function buildPipCountResultText(elapsed, ref, userUpper, userLower) {
    const lines = ['Время: ' + elapsed, '', 'Подсчет пипсов:'];
    if (!ref) {
        lines.push('Нет данных доски для проверки.');
        return lines.join('\n');
    }
    const upperOk = userUpper === ref.upperPips;
    const lowerOk = userLower === ref.lowerPips;
    lines.push(
        'Игрок сверху: ваш ' +
            formatUserValue(userUpper) +
            ', правильно ' +
            ref.upperPips +
            ' ' +
            mark(upperOk)
    );
    lines.push(
        'Игрок снизу: ваш ' +
            formatUserValue(userLower) +
            ', правильно ' +
            ref.lowerPips +
            ' ' +
            mark(lowerOk)
    );
    return lines.join('\n');
}

/**
 * Результат блока «Дабл».
 * @param {string} elapsed
 * @param {string} chosenLabel
 * @param {string} correctLabel
 * @param {boolean} doubleCorrect
 */
export function buildDoubleResultText(elapsed, chosenLabel, correctLabel, doubleCorrect) {
    return [
        'Время: ' + elapsed,
        '',
        'Решение по кубу:',
        'Ваше решение: ' + chosenLabel,
        'Правильно: ' + correctLabel + ' ' + mark(doubleCorrect),
    ].join('\n');
}

/**
 * Результат комбо «Пипсы + дабл».
 */
export function buildComboResultText(
    elapsed,
    ref,
    userUpper,
    userLower,
    chosenLabel,
    correctLabel,
    doubleCorrect
) {
    const lines = ['Время: ' + elapsed, '', 'Подсчет пипсов:'];
    if (!ref) {
        lines.push('Нет данных доски для проверки.');
    } else {
        const upperOk = userUpper === ref.upperPips;
        const lowerOk = userLower === ref.lowerPips;
        lines.push(
            'Игрок сверху: ваш ' +
                formatUserValue(userUpper) +
                ', правильно ' +
                ref.upperPips +
                ' ' +
                mark(upperOk)
        );
        lines.push(
            'Игрок снизу: ваш ' +
                formatUserValue(userLower) +
                ', правильно ' +
                ref.lowerPips +
                ' ' +
                mark(lowerOk)
        );
    }
    lines.push(
        '',
        'Решение по кубу:',
        'Ваше решение: ' + chosenLabel,
        'Правильно: ' + correctLabel + ' ' + mark(doubleCorrect)
    );
    return lines.join('\n');
}
