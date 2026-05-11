/** Краткое описание узора для консоли (без полного data URL). */
function canvasBgPatternSummary(p) {
    if (!p || typeof p !== 'object') return null;
    const u = String(p.imageDataUrl || '');
    const key = String(p.imageS3Key || '').trim();
    return {
        mode: p.mode || 'tile',
        hasDataUrl: u.length > 0,
        dataUrlChars: u.length,
        imageS3Key: key || null,
        interval: p.interval,
        imageWidth: p.imageWidth,
        imageHeight: p.imageHeight,
        fileName: p.fileName || null,
    };
}

function logCanvasBg(stage, detail) {
    if (typeof console === 'undefined' || typeof console.debug !== 'function') return;
    console.debug('[canvas-bg]', stage, detail);
}

export function getCanvasBackgroundForSaveImpl(editor) {
    if (!editor.canvas) return '#ffffff';
    const inline = (editor.canvas.style.backgroundColor || '').trim();
    if (inline && inline !== 'transparent') {
        return editor.canvas.style.backgroundColor;
    }
    const cs = window.getComputedStyle(editor.canvas);
    const c = (cs.backgroundColor || '').trim();
    if (c && c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent') {
        return c;
    }
    return '#ffffff';
}

export function resolveSavedCanvasBackgroundImpl(_editor, payload) {
    const raw = payload && payload.editor && payload.editor.canvasBackground;
    if (raw != null && String(raw).trim() !== '') {
        return String(raw).trim();
    }
    return '#ffffff';
}

export function getCanvasBackgroundPatternForSaveImpl(editor) {
    if (!editor.canvasBackgroundPattern) {
        logCanvasBg('getCanvasBackgroundPatternForSave', { result: null });
        return null;
    }
    const imageDataUrl = String(editor.canvasBackgroundPattern.imageDataUrl || '').trim();
    const imageS3Key = String(editor.canvasBackgroundPattern.imageS3Key || '').trim();
    if (!imageDataUrl && !imageS3Key) {
        logCanvasBg('getCanvasBackgroundPatternForSave', { result: null, reason: 'empty url and s3 key' });
        return null;
    }
    const interval = editor.clampNumericValue(
        editor.canvasBackgroundPattern.interval,
        20,
        200,
        100
    );
    const imageWidth = editor.clampNumericValue(editor.canvasBackgroundPattern.imageWidth, 8, 4096, 64);
    const imageHeight = editor.clampNumericValue(editor.canvasBackgroundPattern.imageHeight, 8, 4096, 64);
    const modeRaw = String(editor.canvasBackgroundPattern.mode || 'tile').toLowerCase();
    const mode = modeRaw === 'cover' ? 'cover' : 'tile';
    const out = {
        mode,
        imageDataUrl,
        imageS3Key,
        imageWidth,
        imageHeight,
        interval,
        fileName: String(editor.canvasBackgroundPattern.fileName || ''),
    };
    logCanvasBg('getCanvasBackgroundPatternForSave', { pattern: canvasBgPatternSummary(out) });
    return out;
}

export function resolveSavedCanvasBackgroundPatternImpl(editor, payload) {
    const raw = payload && payload.editor && payload.editor.canvasBackgroundPattern;
    if (!raw || typeof raw !== 'object') {
        logCanvasBg('resolveSavedCanvasBackgroundPattern', { result: null, reason: 'no raw' });
        return null;
    }
    let mode = String(raw.mode || 'tile').toLowerCase();
    if (mode !== 'cover' && mode !== 'tile') mode = 'tile';
    let imageDataUrl = String(raw.imageDataUrl || '').trim();
    const imageS3Key = String(raw.imageS3Key || '').trim();
    if (!imageDataUrl && imageS3Key && typeof editor.buildContentCardMediaUrl === 'function') {
        imageDataUrl = editor.buildContentCardMediaUrl(imageS3Key);
    }
    if (!imageDataUrl) {
        logCanvasBg('resolveSavedCanvasBackgroundPattern', {
            result: null,
            reason: 'no imageDataUrl after resolve',
            hadS3Key: !!imageS3Key,
        });
        return null;
    }
    const fallbackInterval = raw.interval != null
        ? raw.interval
        : 100;
    const resolved = {
        mode,
        imageDataUrl,
        imageS3Key,
        imageWidth: editor.clampNumericValue(raw.imageWidth, 8, 4096, 64),
        imageHeight: editor.clampNumericValue(raw.imageHeight, 8, 4096, 64),
        interval: editor.clampNumericValue(fallbackInterval, 20, 200, 100),
        fileName: String(raw.fileName || ''),
    };
    logCanvasBg('resolveSavedCanvasBackgroundPattern', { pattern: canvasBgPatternSummary(resolved) });
    return resolved;
}

export function buildCanvasTilePatternCssUrlImpl(editor, pattern) {
    if (!pattern || !pattern.imageDataUrl) return '';
    const src = String(pattern.imageDataUrl || '').trim().replace(/"/g, '\\"');
    if (!src) return '';
    return `url("${src}")`;
}

export function applyCanvasPatternConfigImpl(editor, pattern) {
    if (!editor.canvas) return;
    if (!pattern || !pattern.imageDataUrl) {
        logCanvasBg('applyCanvasPatternConfig', { action: 'clear' });
        editor.canvasBackgroundPattern = null;
        editor.canvas.style.backgroundImage = 'none';
        editor.canvas.style.backgroundRepeat = '';
        editor.canvas.style.backgroundSize = '';
        editor.canvas.style.backgroundPosition = '';
        return;
    }
    const mode = String(pattern.mode || 'tile').toLowerCase() === 'cover' ? 'cover' : 'tile';
    const normalized = {
        mode,
        imageDataUrl: String(pattern.imageDataUrl || ''),
        imageS3Key: String(pattern.imageS3Key || ''),
        imageWidth: editor.clampNumericValue(pattern.imageWidth, 8, 4096, 64),
        imageHeight: editor.clampNumericValue(pattern.imageHeight, 8, 4096, 64),
        interval: editor.clampNumericValue(pattern.interval, 20, 200, 100),
        fileName: String(pattern.fileName || ''),
    };
    editor.canvasBackgroundPattern = normalized;
    editor.canvas.style.backgroundImage = buildCanvasTilePatternCssUrlImpl(editor, normalized);
    if (mode === 'cover') {
        editor.canvas.style.backgroundRepeat = 'no-repeat';
        editor.canvas.style.backgroundSize = 'cover';
        editor.canvas.style.backgroundPosition = 'center center';
        logCanvasBg('applyCanvasPatternConfig', {
            action: 'apply',
            mode: 'cover',
            pattern: canvasBgPatternSummary(normalized),
        });
        return;
    }
    const scale = normalized.interval / 100;
    const tileW = Math.max(1, Math.round(normalized.imageWidth * scale));
    const tileH = Math.max(1, Math.round(normalized.imageHeight * scale));
    editor.canvas.style.backgroundRepeat = 'repeat';
    editor.canvas.style.backgroundSize = `${tileW}px ${tileH}px`;
    editor.canvas.style.backgroundPosition = 'left top';
    logCanvasBg('applyCanvasPatternConfig', {
        action: 'apply',
        mode: 'tile',
        tilePx: `${tileW}x${tileH}`,
        pattern: canvasBgPatternSummary(normalized),
    });
}

export function openCanvasSettingsModalImpl(editor) {
    editor.closeCanvasSettingsModal();
    const d = editor.globalTextStyleDefaults || editor.constructor.DEFAULT_GLOBAL_TEXT_STYLE;
    const textSize = parseInt(String(d.fontSize).replace(/px\s*$/i, ''), 10) || 16;
    let textColorHex = d.color || '#333333';
    if (textColorHex && !/^#[0-9A-F]{6}$/i.test(textColorHex)) {
        textColorHex = editor.rgbToHex(textColorHex) || '#333333';
    }
    const textAlign = d.textAlign || 'left';
    let lineH = parseInt(String(d.lineHeight).replace(/px\s*$/i, ''), 10);
    if (Number.isNaN(lineH)) lineH = 20;
    const fontBold = d.fontWeight === 'bold' || parseInt(d.fontWeight, 10) >= 600;
    const fontItalic = d.fontStyle === 'italic';
    const fontUnderline = String(d.textDecoration || '').includes('underline');
    const firstFam = d.fontFamily ? d.fontFamily.split(',')[0].trim().replace(/^["']|["']$/g, '') : '';
    const fontFamilyOptions = [
        { value: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif', label: 'Системный' },
        { value: 'Arial, Helvetica, sans-serif', label: 'Arial' },
        { value: 'Georgia, "Times New Roman", serif', label: 'Georgia' },
        { value: '"Times New Roman", Times, serif', label: 'Times New Roman' },
        { value: 'Verdana, Geneva, sans-serif', label: 'Verdana' },
        { value: '"Courier New", Courier, monospace', label: 'Courier New' },
        { value: 'Tahoma, Geneva, sans-serif', label: 'Tahoma' }
    ];
    const fontSelectHtml = fontFamilyOptions.map((o) => {
        const v = String(o.value).replace(/&/g, '&amp;').replace(/"/g, '&quot;');
        return `<option value="${v}">${editor.escapeHtml(o.label)}</option>`;
    }).join('');
    const activePattern = resolveSavedCanvasBackgroundPatternImpl(editor, {
        editor: { canvasBackgroundPattern: editor.canvasBackgroundPattern },
    });
    editor._canvasPatternDraft = activePattern ? { ...activePattern } : null;
    logCanvasBg('openCanvasSettingsModal', {
        draftFromEditor: canvasBgPatternSummary(editor._canvasPatternDraft),
    });
    const patternEnabled = !!(editor._canvasPatternDraft && editor._canvasPatternDraft.imageDataUrl);
    const patternInterval = editor._canvasPatternDraft
        ? editor.clampNumericValue(editor._canvasPatternDraft.interval, 20, 200, 100)
        : 100;
    const patternMode =
        editor._canvasPatternDraft && String(editor._canvasPatternDraft.mode || '').toLowerCase() === 'cover'
            ? 'cover'
            : 'tile';
    const patternFileLabel = editor._canvasPatternDraft && editor._canvasPatternDraft.fileName
        ? editor._canvasPatternDraft.fileName
        : (patternEnabled ? 'Изображение выбрано' : 'Картинка не выбрана');

    const modalHTML = `
        <div id="canvasSettingsModal" class="canvas-settings-modal" style="display: flex;">
            <div class="canvas-settings-overlay" onclick="contentEditor.closeCanvasSettingsModal()"></div>
            <div class="canvas-settings-container">
                <div class="canvas-settings-header">
                    <h3>Настройки канваса</h3>
                    <button type="button" class="close-btn" onclick="contentEditor.closeCanvasSettingsModal()">&times;</button>
                </div>
                <div class="canvas-settings-tabs">
                    <button type="button" class="canvas-settings-tab-btn active" data-tab="background"
                        onclick="contentEditor.switchCanvasSettingsTab('background')">Фон</button>
                    <button type="button" class="canvas-settings-tab-btn" data-tab="text"
                        onclick="contentEditor.switchCanvasSettingsTab('text')">Текст</button>
                </div>
                <div class="canvas-settings-body-scroll">
                <div class="canvas-settings-body">
                    <div id="canvasSettingsPanelBg" class="canvas-settings-tab-panel">
                        <div class="setting-group">
                            <label for="canvasBackgroundColor">Цвет фона:</label>
                            <div class="color-input-group">
                                <input type="color" id="canvasBackgroundColor" value="#ffffff">
                                <input type="text" id="canvasBackgroundText" value="#ffffff" placeholder="#ffffff">
                            </div>
                        </div>
                        <div class="setting-group">
                            <label>Предустановленные цвета:</label>
                            <div class="preset-colors" id="presetColorsContainer">
                                ${editor.renderPresetColors()}
                            </div>
                            <div class="preset-controls">
                                <div class="preset-mode-toggle">
                                    <label class="checkbox-label">
                                        <input type="checkbox" id="deleteModeCheckbox">
                                        <span class="checkbox-custom"></span>
                                        <span class="checkbox-text">Режим удаления</span>
                                    </label>
                                </div>
                                <button type="button" class="add-preset-btn" onclick="contentEditor.addPresetColor()">
                                    <i class="fa fa-plus"></i> Добавить цвет
                                </button>
                            </div>
                        </div>
                        <div class="setting-group canvas-settings-pattern-row">
                            <label class="checkbox-label">
                                <input type="checkbox" id="canvasPatternEnabled" ${patternEnabled ? 'checked' : ''}>
                                <span class="checkbox-custom"></span>
                                <span class="checkbox-text">Фон картинкой</span>
                            </label>
                        </div>
                        <div id="canvasPatternControls" class="setting-group" style="${patternEnabled ? '' : 'display:none;'}">
                            <label>Изображение узора:</label>
                            <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                                <button type="button" class="add-preset-btn" onclick="contentEditor.openCanvasPatternImagePicker()">
                                    <i class="fa fa-image"></i> Загрузить картинку
                                </button>
                                <span id="canvasPatternFileName" style="font-size:12px; color:#666;">${editor.escapeHtml(patternFileLabel)}</span>
                            </div>
                            <input type="file" id="canvasPatternFileInput" accept="image/*" style="display:none">
                            <div id="canvasPatternPreview" style="margin-top:8px; width:100%; height:84px; border:1px solid #ddd; border-radius:8px; background-color:#fff; background-image:${patternEnabled ? editor.buildCanvasTilePatternCssUrl(editor._canvasPatternDraft) : 'none'}; background-repeat:repeat; background-size:${patternEnabled ? `${Math.max(1, Math.round(editor._canvasPatternDraft.imageWidth * (patternInterval / 100)))}px ${Math.max(1, Math.round(editor._canvasPatternDraft.imageHeight * (patternInterval / 100)))}px` : 'auto'};"></div>
                        </div>
                        <div id="canvasPatternModeWrap" class="setting-group" style="${patternEnabled ? '' : 'display:none;'}">
                            <label>Вид фона картинкой</label>
                            <div class="canvas-pattern-mode-row" style="display:flex; flex-direction:column; gap:8px; margin-top:6px;">
                                <label class="checkbox-label" style="cursor:pointer;">
                                    <input type="radio" name="canvasPatternMode" value="tile" ${patternMode === 'tile' ? 'checked' : ''}>
                                    <span class="checkbox-text">Повторять (плитка / узор)</span>
                                </label>
                                <label class="checkbox-label" style="cursor:pointer;">
                                    <input type="radio" name="canvasPatternMode" value="cover" ${patternMode === 'cover' ? 'checked' : ''}>
                                    <span class="checkbox-text">На весь канвас (одна картинка, без шва)</span>
                                </label>
                            </div>
                        </div>
                        <div id="canvasPatternGapWrap" class="setting-group" style="${patternEnabled && patternMode === 'tile' ? '' : 'display:none;'}">
                            <label for="canvasPatternGapRange">Интервал узора (меньше = мельче): <span id="canvasPatternGapValue">${patternInterval}%</span></label>
                            <div style="display:flex; gap:8px; align-items:center;">
                                <input type="range" id="canvasPatternGapRange" min="20" max="200" step="1" value="${patternInterval}" style="flex:1;">
                                <input type="number" id="canvasPatternGapNumber" min="20" max="200" step="1" value="${patternInterval}" style="width:82px;">
                            </div>
                        </div>
                    </div>
                    <div id="canvasSettingsPanelText" class="canvas-settings-tab-panel" style="display: none;">
                        <p class="canvas-settings-tab-hint">Применяется ко всем текстовым блокам и подписям ссылок на кадре; после «Применить» те же настройки получают и новые блоки.</p>
                        <div class="setting-group">
                            <label for="globalTextFontSize">Размер шрифта:</label>
                            <select id="globalTextFontSize">
                                ${editor.renderNumericSelectOptions(10, 72, textSize, 1, 'px')}
                            </select>
                        </div>
                        <div class="setting-group">
                            <label for="globalTextColor">Цвет текста:</label>
                            <div class="color-input-group">
                                <input type="color" id="globalTextColor" value="${textColorHex}">
                                <input type="text" id="globalTextColorText" value="${textColorHex}" placeholder="#333333">
                            </div>
                        </div>
                        <div class="setting-group">
                            <label for="globalTextAlign">Выравнивание:</label>
                            <select id="globalTextAlign">
                                <option value="left" ${(textAlign === 'left' || textAlign === 'start') ? 'selected' : ''}>Слева</option>
                                <option value="center" ${textAlign === 'center' ? 'selected' : ''}>По центру</option>
                                <option value="right" ${(textAlign === 'right' || textAlign === 'end') ? 'selected' : ''}>Справа</option>
                                <option value="justify" ${textAlign === 'justify' ? 'selected' : ''}>По ширине</option>
                            </select>
                        </div>
                        <div class="setting-group">
                            <label for="globalTextLineHeight">Межстрочный интервал:</label>
                            <select id="globalTextLineHeight">
                                ${editor.renderNumericSelectOptions(10, 36, lineH, 1, 'px')}
                            </select>
                        </div>
                        <div class="setting-group">
                            <label for="globalTextFontFamily">Шрифт:</label>
                            <select id="globalTextFontFamily">${fontSelectHtml}</select>
                        </div>
                        <div class="setting-group canvas-settings-text-toggles">
                            <label class="checkbox-label">
                                <input type="checkbox" id="globalTextBold" ${fontBold ? 'checked' : ''}>
                                <span class="checkbox-custom"></span>
                                <span class="checkbox-text"><strong>Жирный</strong></span>
                            </label>
                            <label class="checkbox-label">
                                <input type="checkbox" id="globalTextItalic" ${fontItalic ? 'checked' : ''}>
                                <span class="checkbox-custom"></span>
                                <span class="checkbox-text"><em>Курсив</em></span>
                            </label>
                            <label class="checkbox-label">
                                <input type="checkbox" id="globalTextUnderline" ${fontUnderline ? 'checked' : ''}>
                                <span class="checkbox-custom"></span>
                                <span class="checkbox-text"><u>Подчёркивание</u></span>
                            </label>
                        </div>
                    </div>
                </div>
                </div>
                <div class="canvas-settings-footer">
                    <button type="button" class="cancel-btn" onclick="contentEditor.closeCanvasSettingsModal()">Отмена</button>
                    <button type="button" class="apply-btn" onclick="contentEditor.applyCanvasSettingsActiveTab()">Применить</button>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);

    const currentBg = window.getComputedStyle(editor.canvas).backgroundColor;
    const hexBg = editor.rgbToHex(currentBg);
    document.getElementById('canvasBackgroundColor').value = hexBg;
    document.getElementById('canvasBackgroundText').value = hexBg;

    const ffSel = document.getElementById('globalTextFontFamily');
    if (ffSel && firstFam) {
        let matched = false;
        for (let i = 0; i < ffSel.options.length; i++) {
            const v = ffSel.options[i].value;
            if (firstFam.toLowerCase().includes(v.split(',')[0].trim().toLowerCase().replace(/["']/g, ''))
                || v.toLowerCase().includes(firstFam.toLowerCase())) {
                ffSel.selectedIndex = i;
                matched = true;
                break;
            }
        }
        if (!matched && d.fontFamily) {
            const opt = document.createElement('option');
            opt.value = d.fontFamily;
            opt.textContent = `Текущий (${firstFam})`;
            opt.selected = true;
            ffSel.insertBefore(opt, ffSel.firstChild);
        }
    }

    editor.setupPresetColorHandlers();

    const colorPicker = document.getElementById('canvasBackgroundColor');
    const colorText = document.getElementById('canvasBackgroundText');
    colorPicker.addEventListener('input', (e) => {
        colorText.value = e.target.value;
    });
    colorText.addEventListener('input', (e) => {
        if (/^#[0-9A-F]{6}$/i.test(e.target.value)) {
            colorPicker.value = e.target.value;
        }
    });

    const patternEnableCb = document.getElementById('canvasPatternEnabled');
    const patternControls = document.getElementById('canvasPatternControls');
    const patternModeWrap = document.getElementById('canvasPatternModeWrap');
    const patternGapWrap = document.getElementById('canvasPatternGapWrap');
    const patternFileInput = document.getElementById('canvasPatternFileInput');
    const patternGapRange = document.getElementById('canvasPatternGapRange');
    const patternGapNumber = document.getElementById('canvasPatternGapNumber');
    const patternGapValue = document.getElementById('canvasPatternGapValue');

    const syncPatternGapUi = (raw) => {
        const val = editor.clampNumericValue(raw, 20, 200, 100);
        if (patternGapRange) patternGapRange.value = String(val);
        if (patternGapNumber) patternGapNumber.value = String(val);
        if (patternGapValue) patternGapValue.textContent = `${val}%`;
        if (editor._canvasPatternDraft && editor._canvasPatternDraft.imageDataUrl) {
            editor._canvasPatternDraft.interval = val;
            editor.refreshCanvasPatternPreviewInModal();
        }
    };

    const syncPatternModeAndGapVisibility = () => {
        const enabled = !!(patternEnableCb && patternEnableCb.checked);
        if (patternModeWrap) patternModeWrap.style.display = enabled ? 'block' : 'none';
        const modeRadio = document.querySelector('input[name="canvasPatternMode"]:checked');
        const mode = modeRadio && modeRadio.value === 'cover' ? 'cover' : 'tile';
        if (patternGapWrap) patternGapWrap.style.display = enabled && mode === 'tile' ? 'block' : 'none';
    };

    if (patternEnableCb) {
        patternEnableCb.addEventListener('change', () => {
            const enabled = !!patternEnableCb.checked;
            if (patternControls) patternControls.style.display = enabled ? 'block' : 'none';
            syncPatternModeAndGapVisibility();
        });
    }
    document.querySelectorAll('input[name="canvasPatternMode"]').forEach((radio) => {
        radio.addEventListener('change', () => {
            if (editor._canvasPatternDraft) {
                const v = document.querySelector('input[name="canvasPatternMode"]:checked');
                editor._canvasPatternDraft.mode = v && v.value === 'cover' ? 'cover' : 'tile';
            }
            syncPatternModeAndGapVisibility();
            editor.refreshCanvasPatternPreviewInModal();
        });
    });
    if (patternFileInput) {
        patternFileInput.addEventListener('change', () => {
            editor.handleCanvasPatternFileInput(patternFileInput);
        });
    }
    if (patternGapRange) {
        patternGapRange.addEventListener('input', (e) => syncPatternGapUi(e.target.value));
    }
    if (patternGapNumber) {
        patternGapNumber.addEventListener('input', (e) => syncPatternGapUi(e.target.value));
    }
    syncPatternGapUi(patternInterval);
    syncPatternModeAndGapVisibility();

    const gCol = document.getElementById('globalTextColor');
    const gColTxt = document.getElementById('globalTextColorText');
    if (gCol && gColTxt) {
        gCol.addEventListener('input', () => { gColTxt.value = gCol.value; });
        gColTxt.addEventListener('input', (e) => {
            if (/^#[0-9A-F]{6}$/i.test(e.target.value)) gCol.value = e.target.value;
        });
    }
}

export function switchCanvasSettingsTabImpl(_editor, tab) {
    const modal = document.getElementById('canvasSettingsModal');
    if (!modal) return;
    modal.querySelectorAll('.canvas-settings-tab-btn').forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });
    const bg = document.getElementById('canvasSettingsPanelBg');
    const tx = document.getElementById('canvasSettingsPanelText');
    if (bg) bg.style.display = tab === 'background' ? 'block' : 'none';
    if (tx) tx.style.display = tab === 'text' ? 'block' : 'none';
}

export function applyCanvasSettingsActiveTabImpl(editor) {
    const modal = document.getElementById('canvasSettingsModal');
    const active = modal && modal.querySelector('.canvas-settings-tab-btn.active');
    const tab = active ? active.dataset.tab : 'background';
    if (tab === 'text') {
        editor.applyGlobalCanvasTextSettings();
    } else {
        editor.applyCanvasBackground();
    }
}

export function renderPresetColorsImpl(editor) {
    return editor.presetColors.map((color, index) => `
        <div class="preset-color" style="background: ${color};" data-color="${color}" data-index="${index}">
        </div>
    `).join('');
}

export function setupPresetColorHandlersImpl(editor) {
    const deleteModeCheckbox = document.getElementById('deleteModeCheckbox');

    document.querySelectorAll('.preset-color').forEach(preset => {
        preset.addEventListener('click', (e) => {
            if (deleteModeCheckbox.checked) {
                const index = parseInt(e.currentTarget.dataset.index, 10);
                editor.deletePresetColor(index);
            } else {
                const color = e.currentTarget.dataset.color;
                document.getElementById('canvasBackgroundColor').value = color;
                document.getElementById('canvasBackgroundText').value = color;
            }
        });
    });

    deleteModeCheckbox.addEventListener('change', (e) => {
        document.querySelectorAll('.preset-color').forEach(color => {
            if (e.target.checked) {
                color.classList.add('delete-mode');
            } else {
                color.classList.remove('delete-mode');
            }
        });
    });
}

export function addPresetColorImpl(editor) {
    const color = document.getElementById('canvasBackgroundColor').value;
    if (!editor.presetColors.includes(color)) {
        editor.presetColors.push(color);
        const container = document.getElementById('presetColorsContainer');
        container.innerHTML = editor.renderPresetColors();
        editor.setupPresetColorHandlers();
        editor.showNotification('Цвет добавлен в предустановленные', 'success');
    } else {
        editor.showNotification('Этот цвет уже есть в списке', 'warning');
    }
}

export function deletePresetColorImpl(editor, index) {
    const color = editor.presetColors[index];
    editor.presetColors.splice(index, 1);
    const container = document.getElementById('presetColorsContainer');
    container.innerHTML = editor.renderPresetColors();
    editor.setupPresetColorHandlers();
    editor.showNotification(`Цвет ${color} удален`, 'info');
}

export function openCanvasPatternImagePickerImpl(_editor) {
    const input = document.getElementById('canvasPatternFileInput');
    if (input) input.click();
}

export function handleCanvasPatternFileInputImpl(editor, inputEl) {
    if (!inputEl || !inputEl.files || !inputEl.files[0]) return;
    const file = inputEl.files[0];
    if (!file.type || !file.type.startsWith('image/')) {
        editor.showNotification('Нужно выбрать файл изображения', 'warning');
        inputEl.value = '';
        return;
    }
    const reader = new FileReader();
    reader.onload = () => {
        const dataUrl = String(reader.result || '');
        if (!dataUrl) {
            editor.showNotification('Не удалось прочитать изображение', 'error');
            return;
        }
        const img = new Image();
        img.onload = () => {
            const fallbackInterval = editor._canvasPatternDraft
                ? editor.clampNumericValue(editor._canvasPatternDraft.interval, 20, 200, 100)
                : 100;
            const fromRadio = document.querySelector('input[name="canvasPatternMode"]:checked');
            const radioMode = fromRadio && fromRadio.value === 'cover' ? 'cover' : 'tile';
            const prevMode =
                editor._canvasPatternDraft && String(editor._canvasPatternDraft.mode || '').toLowerCase() === 'cover'
                    ? 'cover'
                    : 'tile';
            const mode = editor._canvasPatternDraft ? prevMode : radioMode;
            editor._canvasPatternDraft = {
                mode,
                imageDataUrl: dataUrl,
                imageS3Key: '',
                imageWidth: editor.clampNumericValue(img.naturalWidth, 8, 4096, 64),
                imageHeight: editor.clampNumericValue(img.naturalHeight, 8, 4096, 64),
                interval: fallbackInterval,
                fileName: String(file.name || 'pattern-image'),
            };
            logCanvasBg('handleCanvasPatternFileInput', {
                fileName: editor._canvasPatternDraft.fileName,
                naturalSize: `${img.naturalWidth}x${img.naturalHeight}`,
                draft: canvasBgPatternSummary(editor._canvasPatternDraft),
            });
            const nameEl = document.getElementById('canvasPatternFileName');
            if (nameEl) {
                nameEl.textContent = editor._canvasPatternDraft.fileName || 'Изображение выбрано';
            }
            editor.refreshCanvasPatternPreviewInModal();
            editor.showNotification('Картинка узора загружена', 'success');
        };
        img.onerror = () => {
            editor.showNotification('Не удалось загрузить изображение', 'error');
        };
        img.src = dataUrl;
    };
    reader.onerror = () => {
        editor.showNotification('Ошибка чтения файла', 'error');
    };
    reader.readAsDataURL(file);
}

export function refreshCanvasPatternPreviewInModalImpl(editor) {
    const preview = document.getElementById('canvasPatternPreview');
    if (!preview) return;
    if (!editor._canvasPatternDraft || !editor._canvasPatternDraft.imageDataUrl) {
        preview.style.backgroundImage = 'none';
        preview.style.backgroundSize = 'auto';
        preview.style.backgroundRepeat = '';
        preview.style.backgroundPosition = '';
        return;
    }
    const mode =
        String(editor._canvasPatternDraft.mode || 'tile').toLowerCase() === 'cover' ? 'cover' : 'tile';
    preview.style.backgroundImage = editor.buildCanvasTilePatternCssUrl(editor._canvasPatternDraft);
    if (mode === 'cover') {
        preview.style.backgroundRepeat = 'no-repeat';
        preview.style.backgroundSize = 'cover';
        preview.style.backgroundPosition = 'center center';
        return;
    }
    const interval = editor.clampNumericValue(editor._canvasPatternDraft.interval, 20, 200, 100);
    const scale = interval / 100;
    preview.style.backgroundRepeat = 'repeat';
    preview.style.backgroundSize = `${Math.max(1, Math.round(editor._canvasPatternDraft.imageWidth * scale))}px ${Math.max(1, Math.round(editor._canvasPatternDraft.imageHeight * scale))}px`;
    preview.style.backgroundPosition = 'left top';
}

export function closeCanvasSettingsModalImpl(editor) {
    const modal = document.getElementById('canvasSettingsModal');
    if (modal) {
        modal.remove();
    }
    editor._canvasPatternDraft = null;
}

export function applyCanvasBackgroundImpl(editor) {
    const color = document.getElementById('canvasBackgroundColor').value;
    editor.canvas.style.backgroundColor = color;
    const patternEnabled = !!(document.getElementById('canvasPatternEnabled') && document.getElementById('canvasPatternEnabled').checked);
    logCanvasBg('applyCanvasBackground', {
        backgroundColor: color,
        patternEnabled,
        draftBefore: canvasBgPatternSummary(editor._canvasPatternDraft),
    });
    if (patternEnabled) {
        if (!editor._canvasPatternDraft || !editor._canvasPatternDraft.imageDataUrl) {
            logCanvasBg('applyCanvasBackground', { aborted: true, reason: 'no pattern draft image' });
            editor.showNotification('Сначала загрузите картинку для узора', 'warning');
            return;
        }
        const modeRadio = document.querySelector('input[name="canvasPatternMode"]:checked');
        editor._canvasPatternDraft.mode = modeRadio && modeRadio.value === 'cover' ? 'cover' : 'tile';
        const gapRaw = document.getElementById('canvasPatternGapNumber')
            ? document.getElementById('canvasPatternGapNumber').value
            : editor._canvasPatternDraft.interval;
        editor._canvasPatternDraft.interval = editor.clampNumericValue(gapRaw, 20, 200, 100);
        editor.applyCanvasPatternConfig(editor._canvasPatternDraft);
    } else {
        editor.applyCanvasPatternConfig(null);
    }
    if (typeof editor._previewMergePreferStoredCanvasBg !== 'undefined') {
        editor._previewMergePreferStoredCanvasBg = false;
    }
    logCanvasBg('applyCanvasBackground', {
        done: true,
        storedPattern: canvasBgPatternSummary(editor.canvasBackgroundPattern),
    });
    editor.closeCanvasSettingsModal();
}
