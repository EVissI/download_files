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
    'Переменные: {time}, {no_board}, {upper_row}, {lower_row}, {upper_user}, {upper_correct}, {upper_mark}, {lower_user}, {lower_correct}, {lower_mark}, {choice_user}, {choice_correct}, {choice_mark}. Цвет: выделите текст и нажмите «Цвет» или тег <span style="color:#RRGGBB">...</span>. Пустое поле — шаблон по умолчанию.';

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

function escapeHtml(text) {
    return String(text ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function normalizeColorForStyle(raw) {
    const c = String(raw || '').trim();
    if (/^#[0-9a-fA-F]{3}$/.test(c) || /^#[0-9a-fA-F]{6}$/.test(c)) {
        return c.toLowerCase();
    }
    const rgbMatch = c.match(/^rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$/i);
    if (rgbMatch) {
        const parts = rgbMatch.slice(1, 4).map((n) => Number(n));
        if (parts.every((n) => n >= 0 && n <= 255)) {
            return `rgb(${parts[0]}, ${parts[1]}, ${parts[2]})`;
        }
    }
    return null;
}

function colorFromSpanStyle(style) {
    const raw = String(style || '').trim();
    const colorOnly = raw.match(/^\s*color\s*:\s*(.+?)\s*;?\s*$/i);
    if (colorOnly) {
        return normalizeColorForStyle(colorOnly[1]);
    }
    const inline = raw.match(/(?:^|;)\s*color\s*:\s*([^;]+)/i);
    if (inline) {
        return normalizeColorForStyle(inline[1].trim());
    }
    return null;
}

/** Разрешён только span с color; остальные теги снимаются, текст сохраняется. */
export function sanitizePipResultHtml(html) {
    const str = String(html ?? '');
    if (!str.includes('<')) {
        return escapeHtml(str);
    }
    if (typeof DOMParser === 'undefined') {
        return escapeHtml(str.replace(/<[^>]+>/g, ''));
    }
    const doc = new DOMParser().parseFromString('<div>' + str + '</div>', 'text/html');
    const root = doc.body && doc.body.firstElementChild;
    if (!root) {
        return escapeHtml(str);
    }

    function serializeNode(node) {
        if (node.nodeType === Node.TEXT_NODE) {
            return escapeHtml(node.textContent || '');
        }
        if (node.nodeType !== Node.ELEMENT_NODE) {
            return '';
        }
        const tag = node.tagName ? node.tagName.toUpperCase() : '';
        if (tag === 'SPAN') {
            const color = colorFromSpanStyle(node.getAttribute('style') || '');
            if (color) {
                const inner = Array.from(node.childNodes).map(serializeNode).join('');
                return `<span style="color:${escapeHtml(color)}">${inner}</span>`;
            }
        }
        return Array.from(node.childNodes).map(serializeNode).join('');
    }

    return Array.from(root.childNodes).map(serializeNode).join('');
}

/** Вывод результата pip-интерактива (поддержка цветных span). */
export function setPipInteractiveResultContent(el, rawHtml) {
    if (!el) return;
    el.innerHTML = sanitizePipResultHtml(rawHtml);
}

export function wrapPipResultTemplateSelection(text, color) {
    const selected = String(text ?? '');
    if (!selected) return null;
    const normalized = normalizeColorForStyle(color);
    if (!normalized) return null;
    return `<span style="color:${normalized}">${selected}</span>`;
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
        const value = vars[key] != null ? escapeHtml(String(vars[key])) : '';
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
