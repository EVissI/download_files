/** Эмодзи для верного / неверного ответа в блоке результата pip-интерактивов. */
export const PIP_RESULT_MARK_OK = '✅';
export const PIP_RESULT_MARK_BAD = '❌';

export const PIP_RESULT_TEMPLATE_KIND_COUNT = 'pip_count';
export const PIP_RESULT_TEMPLATE_KIND_DOUBLE = 'pip_double';
export const PIP_RESULT_TEMPLATE_KIND_COMBO = 'pip_combo';

export const DEFAULT_PIP_COUNT_RESULT_TEMPLATE = `Время: {time}

Подсчет пипсов:
{no_board}{upper_row}{lower_row}`;

export const DEFAULT_PIP_DOUBLE_RESULT_TEMPLATE = `Время: {time}

Решение по кубу:
Ваше решение: {choice_user}
Правильно: {choice_correct} {choice_mark}`;

export const DEFAULT_PIP_COMBO_RESULT_TEMPLATE = `Время: {time}

Подсчет пипсов:
{no_board}{upper_row}{lower_row}
Решение по кубу:
Ваше решение: {choice_user}
Правильно: {choice_correct} {choice_mark}`;

export const PIP_RESULT_TEMPLATE_PLACEHOLDER_HINT =
    'Переменные: {time}, {no_board}, {upper_row}, {lower_row}, {upper_user}, {upper_correct}, {upper_mark}, {lower_user}, {lower_correct}, {lower_mark}, {choice_user}, {choice_correct}, {choice_mark}. Пустое поле — шаблон по умолчанию.';

const DEFAULT_TEMPLATE_BY_KIND = {
    [PIP_RESULT_TEMPLATE_KIND_COUNT]: DEFAULT_PIP_COUNT_RESULT_TEMPLATE,
    [PIP_RESULT_TEMPLATE_KIND_DOUBLE]: DEFAULT_PIP_DOUBLE_RESULT_TEMPLATE,
    [PIP_RESULT_TEMPLATE_KIND_COMBO]: DEFAULT_PIP_COMBO_RESULT_TEMPLATE,
};

function mark(ok) {
    return ok ? PIP_RESULT_MARK_OK : PIP_RESULT_MARK_BAD;
}

function formatUserValue(v) {
    return v != null ? String(v) : '—';
}

export function getDefaultPipResultTemplate(kind) {
    return DEFAULT_TEMPLATE_BY_KIND[kind] || DEFAULT_PIP_COUNT_RESULT_TEMPLATE;
}

export function pipResultTemplateKindFromToolId(toolId) {
    if (toolId === 'interactive-pip-count') return PIP_RESULT_TEMPLATE_KIND_COUNT;
    if (toolId === 'interactive-pip-double') return PIP_RESULT_TEMPLATE_KIND_DOUBLE;
    if (toolId === 'interactive-pip-combo') return PIP_RESULT_TEMPLATE_KIND_COMBO;
    return null;
}

export function resolvePipResultTemplate(block, kind) {
    const stored =
        block && block.dataset && block.dataset.cePipResultTemplate != null
            ? String(block.dataset.cePipResultTemplate)
            : '';
    const trimmed = stored.trim();
    if (trimmed) return trimmed;
    return getDefaultPipResultTemplate(kind);
}

export function applyPipResultTemplate(template, vars) {
    let out = String(template || '');
    Object.keys(vars).forEach((key) => {
        const value = vars[key] != null ? String(vars[key]) : '';
        out = out.split('{' + key + '}').join(value);
    });
    return out.replace(/\n{3,}/g, '\n\n').trimEnd();
}

function buildPipRowVars(ref, userUpper, userLower) {
    if (!ref) {
        return {
            no_board: 'Нет данных доски для проверки.\n',
            upper_row: '',
            lower_row: '',
            upper_user: '',
            upper_correct: '',
            upper_mark: '',
            lower_user: '',
            lower_correct: '',
            lower_mark: '',
        };
    }
    const upperOk = userUpper === ref.upperPips;
    const lowerOk = userLower === ref.lowerPips;
    return {
        no_board: '',
        upper_row:
            'Игрок сверху: ваш ' +
            formatUserValue(userUpper) +
            ', правильно ' +
            ref.upperPips +
            ' ' +
            mark(upperOk) +
            '\n',
        lower_row:
            'Игрок снизу: ваш ' +
            formatUserValue(userLower) +
            ', правильно ' +
            ref.lowerPips +
            ' ' +
            mark(lowerOk) +
            '\n',
        upper_user: formatUserValue(userUpper),
        upper_correct: String(ref.upperPips),
        upper_mark: mark(upperOk),
        lower_user: formatUserValue(userLower),
        lower_correct: String(ref.lowerPips),
        lower_mark: mark(lowerOk),
    };
}

function buildCubeVars(chosenLabel, correctLabel, doubleCorrect) {
    return {
        choice_user: chosenLabel != null ? String(chosenLabel) : '—',
        choice_correct: correctLabel != null ? String(correctLabel) : '—',
        choice_mark: mark(!!doubleCorrect),
    };
}

function renderFromTemplate(block, kind, vars) {
    const template = resolvePipResultTemplate(block, kind);
    return applyPipResultTemplate(template, vars);
}

/**
 * Результат блока «Подсчёт пипсов».
 */
export function buildPipCountResultText(elapsed, ref, userUpper, userLower, block) {
    const vars = {
        time: elapsed,
        ...buildPipRowVars(ref, userUpper, userLower),
    };
    return renderFromTemplate(block, PIP_RESULT_TEMPLATE_KIND_COUNT, vars);
}

/**
 * Результат блока «Решение по кубу».
 */
export function buildDoubleResultText(elapsed, chosenLabel, correctLabel, doubleCorrect, block) {
    const vars = {
        time: elapsed,
        ...buildCubeVars(chosenLabel, correctLabel, doubleCorrect),
    };
    return renderFromTemplate(block, PIP_RESULT_TEMPLATE_KIND_DOUBLE, vars);
}

/**
 * Результат комбо «Пипсы+Решение по кубу».
 */
export function buildComboResultText(
    elapsed,
    ref,
    userUpper,
    userLower,
    chosenLabel,
    correctLabel,
    doubleCorrect,
    block
) {
    const vars = {
        time: elapsed,
        ...buildPipRowVars(ref, userUpper, userLower),
        ...buildCubeVars(chosenLabel, correctLabel, doubleCorrect),
    };
    return renderFromTemplate(block, PIP_RESULT_TEMPLATE_KIND_COMBO, vars);
}

/** Пример результата для превью в панели свойств. */
export function buildPipResultPreview(kind, template) {
    const tpl = String(template || '').trim() || getDefaultPipResultTemplate(kind);
    const ref = { upperPips: 5, lowerPips: 7 };
    const base = { time: '01:23', ...buildPipRowVars(ref, 5, 3) };
    const cube = buildCubeVars('Double/take', 'No double', false);
    if (kind === PIP_RESULT_TEMPLATE_KIND_COUNT) {
        return applyPipResultTemplate(tpl, base);
    }
    if (kind === PIP_RESULT_TEMPLATE_KIND_DOUBLE) {
        return applyPipResultTemplate(tpl, { time: '01:23', ...cube });
    }
    return applyPipResultTemplate(tpl, { ...base, ...cube });
}
