function staticAsset(path) {
    var v = window.__STATIC_ASSET_V || '';
    if (!v) return path;
    return path + (path.indexOf('?') >= 0 ? '&' : '?') + 't=' + encodeURIComponent(v);
}

function screenshotImageFileName() {
    const d = new Date();
    const p = (n) => String(n).padStart(2, '0');
    return `image_${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}.png`;
}

function isHintViewerAdminFromMeta() {
    const meta = document.querySelector('meta[name="hint-viewer-is-admin"]');
    return !!(meta && meta.getAttribute('content') === '1');
}

function applyHintViewerAdminUi() {
    if (typeof applyMatchAnalysisAdminFlag === 'function') {
        applyMatchAnalysisAdminFlag(true);
    } else {
        window.hintViewerIsAdmin = true;
    }
    if (!window.hintViewerIsAdmin) return;
    const adminBox = document.getElementById('adminButtonContainer');
    if (adminBox) adminBox.style.display = 'block';
    const fontScaleSelect = document.getElementById('screenshotFontScaleSelect');
    if (fontScaleSelect && typeof hintViewerScreenshotFontScale !== 'undefined') {
        fontScaleSelect.value = String(hintViewerScreenshotFontScale);
    }
    if (window.matchAnalysisMode) {
        const pipBtn = document.getElementById('openPipCountCardEditorBtn');
        const cardBtn = document.getElementById('openCardEditorBtn');
        if (pipBtn) pipBtn.style.display = 'none';
        if (cardBtn) cardBtn.style.display = 'none';
    }
    if (typeof updateMatchAnalysisChromeUi === 'function') {
        updateMatchAnalysisChromeUi();
    }
}

function ensureHtml2Canvas() {
    if (typeof window.html2canvas === 'function') {
        return Promise.resolve(window.html2canvas);
    }
    if (window.__html2canvasLoading) return window.__html2canvasLoading;
    window.__html2canvasLoading = new Promise(function (resolve, reject) {
        const s = document.createElement('script');
        s.src = staticAsset('/static/js/vendor/html2canvas.min.js');
        s.async = true;
        s.onload = function () {
            if (typeof window.html2canvas === 'function') resolve(window.html2canvas);
            else reject(new Error('html2canvas missing'));
        };
        s.onerror = function () { reject(new Error('html2canvas load failed')); };
        document.head.appendChild(s);
    });
    return window.__html2canvasLoading;
}

function ensureContentEditorCss() {
    if (document.querySelector('link[data-content-editor-css]')) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = staticAsset('/static/css/content_editor.css');
    link.setAttribute('data-content-editor-css', '1');
    document.head.appendChild(link);
}

async function ensureContentEditor() {
    if (window.contentEditor) return window.contentEditor;
    if (window.__contentEditorPromise) return window.__contentEditorPromise;
    window.__contentEditorPromise = (async function () {
        ensureContentEditorCss();
        const q = (window.__STATIC_ASSET_V || '')
            ? ('?t=' + encodeURIComponent(window.__STATIC_ASSET_V))
            : '';
        const [storageBridge, core] = await Promise.all([
            import('/static/js/content-editor/infra/storage_telegram_bridge.js' + q),
            import('/static/js/content-editor/core/content_editor_core.js' + q),
        ]);
        if (storageBridge.shouldClearEditorStorageOnBoot && storageBridge.shouldClearEditorStorageOnBoot()) {
            storageBridge.clearContentEditorLocalStorage();
            storageBridge.clearContentEditorIndexedDB();
        }
        const editor = await core.createContentEditorCore();
        window.contentEditor = editor;
        return editor;
    })();
    try {
        return await window.__contentEditorPromise;
    } catch (e) {
        window.__contentEditorPromise = null;
        throw e;
    }
}

        const urlParams = new URLSearchParams(window.location.search);
        const gameId = urlParams.get('game_id') || 'default';
        const error = urlParams.get('error') || '0';
        const matchAnalysisIdParam = urlParams.get('id') || urlParams.get('match_analysis_id');
        let matchAnalysisId = matchAnalysisIdParam ? parseInt(matchAnalysisIdParam, 10) : null;
        if (matchAnalysisId != null && Number.isNaN(matchAnalysisId)) matchAnalysisId = null;
        const matchAnalysisModeFromServer = (function () {
            const meta = document.querySelector('meta[name="match-analysis-mode"]');
            return (meta && meta.getAttribute('content') === '1');
        })();
        const matchAnalysisMode = matchAnalysisModeFromServer || !!matchAnalysisId;
        const matchAnalysisAsUserPreview =
            urlParams.get('as_user') === '1' ||
            urlParams.get('as_user') === 'true' ||
            urlParams.get('user_preview') === '1';
        const matchAnalysisAudioOnly =
            matchAnalysisMode &&
            (urlParams.get('audio_only') === '1' ||
                urlParams.get('audio_only') === 'true' ||
                urlParams.get('only_audio') === '1');
        const deepLinkGameParam = urlParams.get('game') || urlParams.get('game_number');
        const deepLinkMoveParam = urlParams.get('move') || urlParams.get('move_index');
        let pendingDeepLinkGame = deepLinkGameParam ? parseInt(deepLinkGameParam, 10) : null;
        if (pendingDeepLinkGame != null && Number.isNaN(pendingDeepLinkGame)) pendingDeepLinkGame = null;
        let pendingDeepLinkMoveIndex = deepLinkMoveParam != null && deepLinkMoveParam !== ''
            ? parseInt(deepLinkMoveParam, 10)
            : null;
        if (pendingDeepLinkMoveIndex != null && Number.isNaN(pendingDeepLinkMoveIndex)) {
            pendingDeepLinkMoveIndex = null;
        }
        let matchAnalysisDoc = null;
        let matchAnalysisTitle = '';
        window.hintViewerIsAdmin = false;
        window.matchAnalysisMode = matchAnalysisMode;
        window.matchAnalysisId = matchAnalysisId;

        function applyMatchAnalysisAdminFlag(isAdmin) {
            window.hintViewerIsAdmin = matchAnalysisAsUserPreview ? false : !!isAdmin;
        }
        let hintViewerScreenshotFontScale = (function () {
            const meta = document.querySelector('meta[name="hint-screenshot-font-scale"]');
            const parsed = parseInt(meta?.getAttribute('content') || '100', 10);
            return Number.isNaN(parsed) ? 100 : parsed;
        })();
        let screenshotFontScaleBackup = [];

        function isScreenshotFontScaleSkipped(el) {
            if (!el || el.nodeType !== 1) return true;
            if (el.id === 'boardCanvas') return true;
            if (el.closest('#boardCanvas')) return true;
            if (el.closest('#adminButtonContainer')) return true;
            if (el.id === 'matchAnalysisStatusBtn' || el.closest('#matchAnalysisStatusBtn')) return true;
            if (el.id === 'matchAnalysisCabinetBackBtn' || el.closest('#matchAnalysisCabinetBackBtn')) return true;
            if (el.closest('.ma-header-actions')) return true;
            if (el.tagName === 'CANVAS') return true;
            return false;
        }

        function applyScreenshotFontScale() {
            const scale = hintViewerScreenshotFontScale / 100;
            screenshotFontScaleBackup = [];
            if (scale === 1) return;

            const container = document.querySelector('.container');
            if (!container) return;

            const elements = container.querySelectorAll('*');
            const updates = [];
            elements.forEach((el) => {
                if (isScreenshotFontScaleSkipped(el)) return;
                const px = parseFloat(window.getComputedStyle(el).fontSize);
                if (!px || Number.isNaN(px)) return;
                updates.push({
                    el,
                    fontSize: el.style.fontSize,
                    nextFontSize: `${Math.round(px * scale * 10) / 10}px`,
                });
            });
            updates.forEach(({ el, fontSize, nextFontSize }) => {
                screenshotFontScaleBackup.push({ el, fontSize });
                el.style.fontSize = nextFontSize;
            });
        }

        function removeScreenshotFontScale() {
            screenshotFontScaleBackup.forEach(({ el, fontSize }) => {
                el.style.fontSize = fontSize;
            });
            screenshotFontScaleBackup = [];
        }

        function restoreAdminButtonContainerAfterScreenshot(adminButtonContainer, originalDisplay) {
            if (!adminButtonContainer) return;
            if (window.hintViewerIsAdmin && originalDisplay !== null) {
                adminButtonContainer.style.display = originalDisplay;
            } else {
                adminButtonContainer.style.display = 'none';
            }
        }

        // Add cache-busting to CSS background images
        function isWebStandaloneHintViewer() {
            const meta = document.querySelector('meta[name="web-standalone-mode"]');
            return !!(meta && meta.getAttribute('content') === '1');
        }

        document.addEventListener('DOMContentLoaded', function () {
            const screenSaveBtn = document.getElementById('screenSaveBtn');
            const screenUploadBtn = document.getElementById('screenUploadBtn');
            if (isWebStandaloneHintViewer()) {
                if (screenSaveBtn) screenSaveBtn.title = 'Добавить скриншот в архив';
                if (screenUploadBtn) screenUploadBtn.title = 'Скачать архив со скриншотами';
            }
        });
    
        if (window.Telegram && window.Telegram.WebApp) {
            const tg = window.Telegram.WebApp;
            const allowFullscreen = (document.querySelector('meta[name="webapp-fullscreen-enabled"]') || {}).content === '1';
            tg.ready();
            tg.expand();
            try {
                const canFullscreen =
                    allowFullscreen &&
                    typeof tg.requestFullscreen === 'function' &&
                    (typeof tg.isVersionAtLeast !== 'function' || tg.isVersionAtLeast('8.0'));
                if (canFullscreen && !tg.isFullscreen) {
                    tg.requestFullscreen();
                }
            } catch (e) {
                console.warn('requestFullscreen(hint_viewer) failed:', e);
            }
        }

        let data = [];
        let dataLoaded = false;
        let redPlayer = 'Unknown';
        let blackPlayer = 'Unknown';
        let invertColors = false;
        let availableGames = [];
        let currentGameNum = null;
        let matchLength = 0;
        let gameRedScore = 0;
        let gameBlackScore = 0;
        let enable_crawford_game_number = null;
        let matFileName = '';
        let animating = false;
        let skipAnimation = false;
        let animationSpeed = 1.0;
        let skipAnimationEnabled = false;
        let pendingPrevGame = false;
        let hidePipsCheckbox = null;
        let hasErrorsInMatch = false;
        let eqThreshold = 0.030;
        // Load eqThreshold from localStorage if available
        const savedEqThreshold = localStorage.getItem('eqThreshold');
        if (savedEqThreshold !== null) {
            eqThreshold = parseFloat(savedEqThreshold);
        }
        const infoDiv = document.getElementById('move-info');
        const matchInfoDiv = document.getElementById('match-info');
        const playersInfoDiv = document.getElementById('players-info');
        const topBar = document.getElementById('top-bar');
        infoDiv.innerHTML = '<div class="loading">Loading game data...</div>';

        function getTelegramInitData() {
            try {
                return (window.Telegram && Telegram.WebApp && Telegram.WebApp.initData) || '';
            } catch (e) {
                return '';
            }
        }

        function isWebStandaloneMode() {
            try {
                const meta = document.querySelector('meta[name="web-standalone-mode"]');
                return !!(meta && meta.getAttribute('content') === '1');
            } catch (e) {
                return false;
            }
        }

        function getMatchAnalysisAuthFields() {
            const initData = getTelegramInitData();
            if (initData) return { init_data: initData };
            if (isWebStandaloneMode()) return {};
            return null;
        }

        function appendMatchAnalysisAuthToFormData(fd) {
            const auth = getMatchAnalysisAuthFields();
            if (auth && auth.init_data) fd.append('init_data', auth.init_data);
            return auth !== null;
        }

        function resolveHintViewerChatId(fallback) {
            try {
                const tgUser =
                    window.Telegram &&
                    Telegram.WebApp &&
                    Telegram.WebApp.initDataUnsafe &&
                    Telegram.WebApp.initDataUnsafe.user;
                if (tgUser && tgUser.id != null && tgUser.id !== '') {
                    return String(tgUser.id);
                }
            } catch (e) {}
            const fromUrl = urlParams.get('chat_id');
            if (fromUrl) return String(fromUrl);
            if (fallback != null && fallback !== '') return String(fallback);
            return null;
        }

        // Текущий пользователь WebApp/URL — не владелец сохранённого анализа.
        let chatId = resolveHintViewerChatId(null);
        try {
            window.hintViewerChatId = chatId;
        } catch (e) {}

        function getActiveHintViewerChatId() {
            chatId = resolveHintViewerChatId(chatId);
            try {
                window.hintViewerChatId = chatId;
            } catch (e) {}
            return chatId;
        }

        function fetchGameJson(gameNum) {
            if (matchAnalysisDoc) {
                const g = (matchAnalysisDoc.games || []).find(
                    (x) => String(x.game_number) === String(gameNum)
                );
                if (!g) {
                    return Promise.reject(new Error('Game not found in match analysis'));
                }
                return Promise.resolve({
                    game_info: g.game_info || {},
                    moves: g.moves || [],
                });
            }
            return fetch(`/api/analysis/${gameId}?game_num=${gameNum}`).then((response) => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            });
        }

        function processLoadedMoves(json) {
            const gameInfo = json.game_info || {};

            data = (json.moves || [])
                .map((item, idx) => {
                    const copy = Object.assign({}, item);
                    copy._moveIndex = idx;
                    return copy;
                })
                .filter((item) => item.turn !== undefined || item.action === 'win');
            data = data.filter(
                (it) =>
                    (Array.isArray(it.moves) ||
                        it.action === 'win' ||
                        it.action === 'double' ||
                        it.action === 'take') &&
                    it.action !== 'pass'
            );

            current = 0;
            dataLoaded = true;

            data.forEach((item) => {
                if (item.hints && item.hints.length > 0) {
                    const firstEq = item.hints[0].eq;
                    const madeHint = item.hints.find(
                        (h) =>
                            h.move &&
                            h.move.replace(/\*/g, '') ===
                                (item.gnu_move || '').trim().replace(/\*/g, '')
                    );
                    if (madeHint) {
                        const diff = firstEq - madeHint.eq;
                        item.is_error = diff >= eqThreshold;
                    } else {
                        item.is_error = false;
                    }
                } else {
                    item.is_error = false;
                }
                item.is_visible = computeMoveIsVisible(item);
            });

            return gameInfo;
        }

        function bootstrapAnalysisSummary(json) {
            const gameInfo = json.game_info || {};
            availableGames = json.games || [];
            if (matchAnalysisDoc) {
                availableGames = (matchAnalysisDoc.games || []).map((g) => ({
                    game_number: g.game_number,
                }));
            }
            redPlayer = gameInfo.red_player || 'Unknown';
            blackPlayer = gameInfo.black_player || 'Unknown';
            invertColors = gameInfo.invert_colors || false;
            matchLength = gameInfo.match_length || 0;
            enable_crawford_game_number = parseInt(gameInfo.enable_crawford_game) || null;
            const scores = gameInfo.scores || {};
            // Не подменяем chat_id текущего зрителя на chat_id из JSON анализа
            // (иначе скриншоты уходят создателю карточки из кабинета).
            chatId = resolveHintViewerChatId(chatId || gameInfo.chat_id || null);
            try {
                window.hintViewerChatId = chatId;
            } catch (e) {}
            matFileName = gameInfo.mat_file_name || matchAnalysisTitle || '';
            try {
                window.hintViewerMatFileName = matFileName;
            } catch (e) {}
            hasErrorsInMatch = false;
            return scores;
        }

        function moveHasAudioComment(item) {
            return !!(item && (item.audioS3Key || item.audio_s3_key));
        }

        function computeMoveIsVisible(item) {
            const hasCubeError =
                (item.action === 'double' ||
                    item.action === 'take' ||
                    item.action === 'drop') &&
                item.is_best_move_cube === false;
            const hasMoveError =
                Array.isArray(item.moves) &&
                item.moves.length > 0 &&
                item.is_best_move === false &&
                item.is_error;
            let visible =
                error === '0' ||
                (error === '1' &&
                    (hasMoveError ||
                        hasCubeError ||
                        (item.action === 'win' && item.is_error))) ||
                (error === '2' &&
                    ((item.player_name === redPlayer &&
                        (hasMoveError || hasCubeError)) ||
                        (item.action === 'win' && item.is_error))) ||
                (error === '3' &&
                    ((item.player_name === blackPlayer &&
                        (hasMoveError || hasCubeError)) ||
                        (item.action === 'win' && item.is_error)));
            if (visible && matchAnalysisAudioOnly) {
                visible = moveHasAudioComment(item);
            }
            return visible;
        }

        function buildGameSelectHtml(selectedValue) {
            let selectHtml = '<select id="gameSelect" class="game-select" onchange="loadGame(this.value)">';
            selectHtml += '<option value="">Выберите игру</option>';
            (availableGames || []).forEach((game) => {
                const num = game.game_number;
                const selected = String(num) === String(selectedValue) ? ' selected' : '';
                selectHtml += `<option value="${num}"${selected}>Игра ${num}</option>`;
            });
            selectHtml += '</select>';
            return selectHtml;
        }

        function renderMatchInfoRow() {
            if (!matchInfoDiv || !(matchLength > 0)) return;
            const prevHide = document.getElementById('hideInfoCheckbox');
            const hideChecked = !!(prevHide && prevHide.checked);
            const pipsEl = document.getElementById('black-pips');
            const pipsText = pipsEl ? pipsEl.innerText : '0';
            const pipsClass = pipsEl && pipsEl.className
                ? pipsEl.className
                : 'pips-above-board';
            const pipsDisplay = pipsEl ? pipsEl.style.display : '';

            matchInfoDiv.innerHTML =
                '<div class="match-info-row">' +
                `<span class="match-length">Матч до ${matchLength}</span>` +
                buildGameSelectHtml(currentGameNum) +
                '<div class="match-info-trailing">' +
                `<span class="match-score">Счет: ${gameRedScore} - ${gameBlackScore}</span>` +
                '<div class="right-group">' +
                `<input type="checkbox" id="hideInfoCheckbox"${hideChecked ? ' checked' : ''}>` +
                `<div id="black-pips" class="${pipsClass}"` +
                (pipsDisplay ? ` style="display: ${pipsDisplay}"` : '') +
                `>${pipsText}</div>` +
                '</div>' +
                '</div>' +
                '</div>';

            const hideInfoCheckbox = document.getElementById('hideInfoCheckbox');
            if (hideInfoCheckbox) {
                const savedState = localStorage.getItem('hideInfoCheckbox');
                if (!hideChecked && savedState === 'true') {
                    hideInfoCheckbox.checked = true;
                }
                hideInfoCheckbox.addEventListener('change', () => {
                    localStorage.setItem('hideInfoCheckbox', hideInfoCheckbox.checked);
                });
            }
        }

        function renderMatchTopBar(crawfordVisibility) {
            if (!topBar) return;
            topBar.innerHTML =
                '<span id="crawfordLabel" style="visibility: ' +
                crawfordVisibility +
                ';">Кроуфорд</span>';
        }

        function startAnalysisBootstrap(json) {
            const scores = bootstrapAnalysisSummary(json);
            const redScore = scores.Red || 0;
            const blackScore = scores.Black || 0;

            if (availableGames.length > 0 && matchLength > 0) {
                currentGameNum = parseInt(availableGames[0].game_number);
                gameRedScore = scores.Red || 0;
                gameBlackScore = scores.Black || 0;
                playersInfoDiv.innerHTML = `Белые: ${redPlayer} – Черные: ${blackPlayer}`;
                let crawfordVisibility =
                    enable_crawford_game_number &&
                    currentGameNum === enable_crawford_game_number
                        ? 'visible'
                        : 'hidden';
                renderMatchInfoRow();
                renderMatchTopBar(crawfordVisibility);

                if (availableGames.length > 0) {
                    let startGameNum = availableGames[0].game_number;
                    if (pendingDeepLinkGame != null) {
                        const deepGame = availableGames.find(
                            (g) => String(g.game_number) === String(pendingDeepLinkGame)
                        );
                        if (deepGame) startGameNum = deepGame.game_number;
                        pendingDeepLinkGame = null;
                    }
                    currentGameNum = parseInt(startGameNum);
                    loadGame(startGameNum);
                }
            } else if (availableGames.length > 0) {
                let startGameNum = availableGames[0].game_number;
                if (pendingDeepLinkGame != null) {
                    const deepGame = availableGames.find(
                        (g) => String(g.game_number) === String(pendingDeepLinkGame)
                    );
                    if (deepGame) startGameNum = deepGame.game_number;
                    pendingDeepLinkGame = null;
                }
                currentGameNum = parseInt(startGameNum);
                gameRedScore = redScore;
                gameBlackScore = blackScore;
                matchInfoDiv.innerHTML = 'Манигейм';
                playersInfoDiv.innerHTML = `Белые: ${redPlayer} <br>Черные: ${blackPlayer}<br>`;
                topBar.innerHTML =
                    '<span id="crawfordLabel" style="visibility: hidden;"></span>' +
                    '<input type="checkbox" id="hideInfoCheckbox">' +
                    '<div id="black-pips" class="pips-above-board">0</div>';
                const hideInfoCheckbox = document.getElementById('hideInfoCheckbox');
                if (hideInfoCheckbox) {
                    const savedState = localStorage.getItem('hideInfoCheckbox');
                    if (savedState === 'true') {
                        hideInfoCheckbox.checked = true;
                    }
                    hideInfoCheckbox.addEventListener('change', () => {
                        localStorage.setItem('hideInfoCheckbox', hideInfoCheckbox.checked);
                    });
                }
                loadGame(startGameNum);
            } else {
                matchInfoDiv.innerHTML = '';
                playersInfoDiv.innerHTML = `Белые: ${redPlayer} <br>Черные: ${blackPlayer}<br>`;
                topBar.innerHTML =
                    '<span id="crawfordLabel" style="visibility: hidden;"></span>' +
                    '<input type="checkbox" id="hideInfoCheckbox">' +
                    '<div id="black-pips" class="pips-above-board">0</div>';
                infoDiv.innerHTML = '<div class="loading">Нет игр в анализе</div>';
            }
            updateMatchAnalysisChromeUi();
        }

        // Загружаем список доступных игр (S3 hints или сохранённый MatchAnalysis)
        const analysisBootstrapPromise = matchAnalysisMode && matchAnalysisId
            ? fetch('/api/match_analysis/fetch', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify(Object.assign(
                      { id: matchAnalysisId },
                      getMatchAnalysisAuthFields() || { init_data: getTelegramInitData() }
                  )),
              }).then(async (response) => {
                  if (!response.ok) {
                      const err = await response.json().catch(() => ({}));
                      throw new Error(err.detail || `HTTP ${response.status}`);
                  }
                  return response.json();
              }).then((payload) => {
                  matchAnalysisDoc = payload.analysis || {};
                  matchAnalysisTitle = payload.title || '';
                  window.matchAnalysisId = matchAnalysisId;
                  if (typeof payload.is_root_admin === 'boolean') {
                      applyMatchAnalysisAdminFlag(payload.is_root_admin);
                  }
                  if (payload.user_card_status && typeof window.__setMatchAnalysisCachedUserStatus === 'function') {
                      window.__setMatchAnalysisCachedUserStatus(payload.user_card_status);
                  }
                  return {
                      game_info: matchAnalysisDoc.game_info || {},
                      games: (matchAnalysisDoc.games || []).map((g) => ({
                          game_number: g.game_number,
                      })),
                  };
              })
            : fetch(`/api/analysis/${gameId}`).then((response) => {
                  if (!response.ok) {
                      throw new Error(`HTTP error! status: ${response.status}`);
                  }
                  return response.json();
              });

        analysisBootstrapPromise
            .then((json) => {
                startAnalysisBootstrap(json);
            })
            .catch((err) => {
                console.error('Error loading analysis:', err);
                infoDiv.innerHTML =
                    '<div class="loading">Ошибка загрузки анализа: ' +
                    (err.message || err) +
                    '</div>';
            });

        function loadGame(gameNum) {
            return new Promise((resolve, reject) => {
                if (!gameNum) {
                    data = [];
                    dataLoaded = false;
                    infoDiv.innerHTML = '<div class="loading">Select a game to view</div>';
                    document.getElementById('moveHintsTable').innerHTML = '';
                    document.getElementById('cubeHintsTable').innerHTML = '';
                    resolve();
                    return;
                }

                currentGameNum = parseInt(gameNum);
                // Update the select dropdown
                const gameSelect = document.getElementById('gameSelect');
                if (gameSelect) {
                    gameSelect.value = gameNum;
                }
                infoDiv.innerHTML = '<div class="loading">Loading game data...</div>';

                fetchGameJson(gameNum)
                    .then(json => {
                        const gameInfo = processLoadedMoves(json);

                        const hasNonWinVisible = data.some(item => item.is_visible && item.action !== 'win');
                        if (hasNonWinVisible) {
                            hasErrorsInMatch = true;
                        } else if (error !== '0' || matchAnalysisAudioOnly) {
                            const nextGame = availableGames.find(g => g.game_number > currentGameNum);
                            if (nextGame) {
                                loadGame(nextGame.game_number);
                            } else {
                                if (!hasErrorsInMatch) {
                                    showMessageModal(
                                        matchAnalysisAudioOnly
                                            ? 'В матче нет аудиокомментариев'
                                            : 'В матче нет ошибок',
                                        'info'
                                    );
                                }
                            }
                        }

                        const gameScores = gameInfo.scores || {};
                        gameRedScore = gameScores.Red || 0;
                        gameBlackScore = gameScores.Black || 0;
                        if (matchLength === 0) {
                            playersInfoDiv.innerHTML = "Белые: " + redPlayer + " <br>Черные: " + blackPlayer + "<br>";
                            if (!document.getElementById('black-pips') && topBar) {
                                const prevHide = document.getElementById('hideInfoCheckbox');
                                const hideChecked = !!(prevHide && prevHide.checked);
                                topBar.innerHTML =
                                    '<span id="crawfordLabel" style="visibility: hidden;"></span>' +
                                    `<input type="checkbox" id="hideInfoCheckbox"${hideChecked ? ' checked' : ''}>` +
                                    '<div id="black-pips" class="pips-above-board">0</div>';
                                const hideInfoCheckbox = document.getElementById('hideInfoCheckbox');
                                if (hideInfoCheckbox) {
                                    const savedState = localStorage.getItem('hideInfoCheckbox');
                                    if (!hideChecked && savedState === 'true') {
                                        hideInfoCheckbox.checked = true;
                                    }
                                    hideInfoCheckbox.addEventListener('change', () => {
                                        localStorage.setItem('hideInfoCheckbox', hideInfoCheckbox.checked);
                                    });
                                }
                            }
                        } else {
                            playersInfoDiv.innerHTML = `Белые: ${redPlayer} – Черные: ${blackPlayer}`;
                            renderMatchInfoRow();
                            let crawfordVisibility = (enable_crawford_game_number && currentGameNum === enable_crawford_game_number) ? 'visible' : 'hidden';
                            renderMatchTopBar(crawfordVisibility);
                        }

                        hidePipsCheckbox = document.getElementById('hidePipsCheckbox');
                        if (hidePipsCheckbox) {
                            const savedState = localStorage.getItem('hidePipsCheckbox');
                            if (savedState === 'true') {
                                hidePipsCheckbox.checked = true;
                            }
                            hidePipsCheckbox.addEventListener('change', () => {
                                localStorage.setItem('hidePipsCheckbox', hidePipsCheckbox.checked);
                                render(current, invertColors);
                            });
                        }

                        const initSettingsFromLocalStorage = () => {
                            const skipAnimState = localStorage.getItem('skipAnimationCheckbox');
                            const skipAnimCheckbox = document.getElementById('skipAnimationCheckbox');
                            if (skipAnimCheckbox && skipAnimState === 'true') {
                                skipAnimCheckbox.checked = true;
                            }

                            const hidePipsState = localStorage.getItem('hidePipsCheckbox');
                            if (hidePipsCheckbox && hidePipsState === 'true') {
                                hidePipsCheckbox.checked = true;
                            }

                            const animSpeedState = localStorage.getItem('animationSpeedSlider');
                            const animSpeedSlider = document.getElementById('animationSpeedSlider');
                            if (animSpeedSlider && animSpeedState) {
                                animSpeedSlider.value = animSpeedState;
                            }

                            const eqState = localStorage.getItem('eqThreshold');
                            const eqInput = document.getElementById('eqThreshold');
                            if (eqState) {
                                eqThreshold = parseFloat(eqState);
                            } else {
                                localStorage.setItem('eqThreshold', eqThreshold);
                            }
                            if (eqInput) {
                                eqInput.value = eqThreshold;
                            }

                            const eqSelect = document.getElementById('eqThresholdSelect');
                            if (eqSelect) {
                                eqSelect.value = eqThreshold.toString();
                            }

                            // Hide animation controls in error mode
                            if (error !== '0') {
                                const skipLabel = document.getElementById('skipAnimationLabel');
                                if (skipLabel) skipLabel.style.display = 'none';
                                const speedLabel = document.getElementById('animationSpeedLabel');
                                if (speedLabel) speedLabel.style.display = 'none';
                            }
                        };

                        // Инициализируем настройки при загрузке игры
                        initSettingsFromLocalStorage();
                        updateVisibility();

                        // Обработчики изменения для порогов EQ
                        const eqInput = document.getElementById('eqThreshold');
                        if (eqInput) {
                            eqInput.addEventListener('input', (e) => {
                                eqThreshold = parseFloat(e.target.value) || 0.060;
                                localStorage.setItem('eqThreshold', eqThreshold);
                                const eqSelect = document.getElementById('eqThresholdSelect');
                                if (eqSelect) {
                                    eqSelect.value = eqThreshold.toString();
                                }
                                updateVisibility();
                            });
                        }

                        const eqSelect = document.getElementById('eqThresholdSelect');
                        if (eqSelect) {
                            eqSelect.addEventListener('change', (e) => {
                                const value = parseFloat(e.target.value);
                                eqThreshold = value;
                                localStorage.setItem('eqThreshold', eqThreshold);
                                const eqInput = document.getElementById('eqThreshold');
                                if (eqInput) {
                                    eqInput.value = value;
                                }
                                updateVisibility();
                            });
                        }

                        const skipAnimationCheckbox = document.getElementById('skipAnimationCheckbox');
                        if (skipAnimationCheckbox) {
                            skipAnimationCheckbox.addEventListener('change', (e) => {
                                skipAnimationEnabled = e.target.checked;
                                localStorage.setItem('skipAnimationCheckbox', e.target.checked);
                            });
                        }

                        // Force skip animation if error != '0'
                        if (error !== '0') {
                            skipAnimationEnabled = true;
                        }

                        const animationSpeedSlider = document.getElementById('animationSpeedSlider');
                        if (animationSpeedSlider) {
                            animationSpeedSlider.addEventListener('change', (e) => {
                                animationSpeed = parseFloat(e.target.value);
                                localStorage.setItem('animationSpeedSlider', e.target.value);
                            });
                        }

                        // Найти все индексы ходов с удвоением
                        doubleTurns = data.map((item, index) => item.action === 'double' ? index : -1).filter(idx => idx !== -1);
                        firstDoubleIndex = doubleTurns.length > 0 ? doubleTurns[0] : -1;

                        if (data.length > 0) {
                            dataLoaded = true;
                            console.log('Data loaded:', data);
                            console.log('First turn data:', data[0]);
                            console.log('First turn moves:', data[0]?.moves);
                            current = 0;
                            if (data[0]?.action === 'skip') {
                                current = 1;
                            }
                            // Найти первый видимый ход
                            while (current < data.length && !data[current].is_visible) {
                                current++;
                            }
                            if (current >= data.length) {
                                current = 0; // fallback
                            }
                            if (pendingDeepLinkMoveIndex != null) {
                                const deepIdx = data.findIndex(
                                    (row) => row && row._moveIndex === pendingDeepLinkMoveIndex
                                );
                                if (deepIdx >= 0) {
                                    current = deepIdx;
                                }
                                pendingDeepLinkMoveIndex = null;
                            }
                            // Reset hints display
                            moveHintsTable.classList.remove('active');
                            cubeHintsTable.classList.remove('active');
                            moveHintsBtn.classList.remove('active');
                            cubeHintsBtn.classList.remove('active');
                            if (imagesLoaded === 27) {
                                render(current, invertColors);
                                updateButtons();
                                updateMatchAnalysisAudioUi();
                                infoDiv.innerHTML = '';
                                // Auto-select move hints
                                moveHintsTable.classList.add('active');
                                moveHintsBtn.classList.add('active');
                            } else {
                                console.log('Waiting for images to load before rendering');
                            }
                        } else {
                            infoDiv.innerHTML = '<div class="error">No game data found for this game.</div>';
                        }
                        updateMatchAnalysisAudioUi();
                        resolve();
                    })
                    .catch(error => {
                        console.error('Error loading game:', error);
                        infoDiv.innerHTML = '<div class="error">Error loading game data. Please try again.</div>';
                        reject(error);
                    });
            });
        }

        let current = 0;
        let doubleTurns = [];
        let firstDoubleIndex = -1;
        let currentCube = null;
        let currentCubePlayer = null;

        function updateVisibility() {
            if (!dataLoaded || !data || data.length === 0) return;
            data.forEach(item => {
                if (item.hints && item.hints.length > 0) {
                    const firstEq = item.hints[0].eq;
                    const madeHint = item.hints.find(h => h.move && h.move.replace(/\*/g, '') === item.gnu_move.trim().replace(/\*/g, ''));
                    if (madeHint) {
                        const diff = firstEq - madeHint.eq;
                        item.is_error = diff >= eqThreshold;
                    } else {
                        item.is_error = false;
                    }
                } else {
                    item.is_error = false;
                }
                item.is_visible = computeMoveIsVisible(item);
            });
            // Проверить границы перед обращением к data[current]
            if (current < 0 || current >= data.length) {
                current = 0;
            }
            // Найти новый current, если текущий не видим
            if (data[current] && !data[current].is_visible) {
                let newCurrent = current;
                while (newCurrent >= 0 && newCurrent < data.length && !data[newCurrent].is_visible) newCurrent--;
                if (newCurrent < 0) {
                    newCurrent = current;
                    while (newCurrent < data.length && !data[newCurrent].is_visible) newCurrent++;
                }
                if (newCurrent >= data.length) newCurrent = data.length - 1;
                if (newCurrent < 0) newCurrent = 0;
                current = newCurrent;
            }
            render(current, invertColors);
            updateButtons();
        }

        function updateCurrentCube(turn) {
            let lastDoubleIndex = -1;
            for (let i = 0; i < doubleTurns.length; i++) {
                if (doubleTurns[i] <= turn) {
                    lastDoubleIndex = doubleTurns[i];
                } else {
                    break;
                }
            }
            if (lastDoubleIndex !== -1) {
                const cubeValue = data[lastDoubleIndex].cube;
                const doubleImages = {
                    2: Double2,
                    4: Double4,
                    8: Double8,
                    16: Double16,
                    32: Double32,
                    64: Double64
                };
                currentCube = doubleImages[cubeValue];
                currentCubePlayer = data[lastDoubleIndex].player;
            } else {
                currentCube = null;
                currentCubePlayer = null;
            }
        }
        const canvas = document.getElementById('boardCanvas');
        const ctx = canvas.getContext('2d');

        const moveHintsBtn = document.getElementById('moveHintsBtn');
        const cubeHintsBtn = document.getElementById('cubeHintsBtn');
        const moveHintsTable = document.getElementById('moveHintsTable');
        const cubeHintsTable = document.getElementById('cubeHintsTable');

        // Default to move hints active
        moveHintsBtn.classList.add('active');
        moveHintsTable.classList.add('active');

        moveHintsBtn.addEventListener('click', () => {
            moveHintsTable.classList.add('active');
            cubeHintsTable.classList.remove('active');
            moveHintsBtn.classList.add('active');
            cubeHintsBtn.classList.remove('active');
        });

        cubeHintsBtn.addEventListener('click', () => {
            cubeHintsTable.classList.add('active');
            moveHintsTable.classList.remove('active');
            cubeHintsBtn.classList.add('active');
            moveHintsBtn.classList.remove('active');
        });

        const boardImg = new Image();
        boardImg.src = staticAsset('/static/board.webp');

        const blackImg = new Image();
        blackImg.src = staticAsset('/static/black_checker.webp');

        const whiteImg = new Image();
        whiteImg.src = staticAsset('/static/white_checker.webp');

        const Dice1w = new Image();
        Dice1w.src = staticAsset('/static/1w.webp');
        const Dice2w = new Image();
        Dice2w.src = staticAsset('/static/2w.webp');
        const Dice3w = new Image();
        Dice3w.src = staticAsset('/static/3w.webp');
        const Dice4w = new Image();
        Dice4w.src = staticAsset('/static/4w.webp');
        const Dice5w = new Image();
        Dice5w.src = staticAsset('/static/5w.webp');
        const Dice6w = new Image();
        Dice6w.src = staticAsset('/static/6w.webp');

        const Dice1b = new Image();
        Dice1b.src = staticAsset('/static/1b.webp');
        const Dice2b = new Image();
        Dice2b.src = staticAsset('/static/2b.webp');
        const Dice3b = new Image();
        Dice3b.src = staticAsset('/static/3b.webp');
        const Dice4b = new Image();
        Dice4b.src = staticAsset('/static/4b.webp');
        const Dice5b = new Image();
        Dice5b.src = staticAsset('/static/5b.webp');
        const Dice6b = new Image();
        Dice6b.src = staticAsset('/static/6b.webp');

        const Double2 = new Image();
        Double2.src = staticAsset('/static/Double2.webp');
        const Double4 = new Image();
        Double4.src = staticAsset('/static/Double4.webp');
        const Double8 = new Image();
        Double8.src = staticAsset('/static/Double8.webp');
        const Double16 = new Image();
        Double16.src = staticAsset('/static/Double16.webp');
        const Double32 = new Image();
        Double32.src = staticAsset('/static/Double32.webp');
        const Double64 = new Image();
        Double64.src = staticAsset('/static/Double64.webp');

        const LeftArrow = new Image();
        LeftArrow.src = staticAsset('/static/left.webp');
        const RightArrow = new Image();
        RightArrow.src = staticAsset('/static/right.webp');

        const ScreenShot = new Image();
        ScreenShot.src = staticAsset('/static/Screen.webp');
        const ScreenSave = new Image();
        ScreenSave.src = staticAsset('/static/ScreenSave.webp');
        const ScreenUpload = new Image();
        ScreenUpload.src = staticAsset('/static/ScreenUpload.webp');

        const ChangeColor = new Image();
        ChangeColor.src = staticAsset('/static/change_color.webp');

        let imagesLoaded = 0;
        const checkImagesLoaded = () => {
            imagesLoaded++;
            console.log('Images loaded:', imagesLoaded);
            if (imagesLoaded === 27 && dataLoaded) {
                console.log('All images and data loaded, rendering turn', current);
                render(current, invertColors);
                updateButtons();
                infoDiv.innerHTML = '';
            }
        };

        boardImg.onload = checkImagesLoaded;
        blackImg.onload = checkImagesLoaded;
        whiteImg.onload = checkImagesLoaded;
        Dice1w.onload = checkImagesLoaded;
        Dice2w.onload = checkImagesLoaded;
        Dice3w.onload = checkImagesLoaded;
        Dice4w.onload = checkImagesLoaded;
        Dice5w.onload = checkImagesLoaded;
        Dice6w.onload = checkImagesLoaded;
        Dice1b.onload = checkImagesLoaded;
        Dice2b.onload = checkImagesLoaded;
        Dice3b.onload = checkImagesLoaded;
        Dice4b.onload = checkImagesLoaded;
        Dice5b.onload = checkImagesLoaded;
        Dice6b.onload = checkImagesLoaded;
        Double2.onload = checkImagesLoaded;
        Double4.onload = checkImagesLoaded;
        Double8.onload = checkImagesLoaded;
        Double16.onload = checkImagesLoaded;
        Double32.onload = checkImagesLoaded;
        Double64.onload = checkImagesLoaded;
        LeftArrow.onload = checkImagesLoaded;
        RightArrow.onload = checkImagesLoaded;
        ScreenShot.onload = checkImagesLoaded;
        ScreenSave.onload = checkImagesLoaded;
        ScreenUpload.onload = checkImagesLoaded;
        ChangeColor.onload = checkImagesLoaded;

        // Обработка ошибок загрузки изображений
        [boardImg, blackImg, whiteImg, Dice1w, Dice2w, Dice3w, Dice4w, Dice5w, Dice6w, Dice1b, Dice2b, Dice3b, Dice4b, Dice5b, Dice6b, Double2, Double4, Double8, Double16, Double32, Double64, LeftArrow, RightArrow, ScreenShot, ChangeColor, ScreenSave, ScreenUpload,].forEach(img => {
            img.onerror = () => {
                console.error(`Failed to load image: ${img.src}`);
                infoDiv.innerHTML = '<div class="error">Error loading game assets. Please try again later.</div>';
            };
        });

        const diceImages = {
            white: {
                1: Dice1w,
                2: Dice2w,
                3: Dice3w,
                4: Dice4w,
                5: Dice5w,
                6: Dice6w
            },
            black: {
                1: Dice1b,
                2: Dice2b,
                3: Dice3b,
                4: Dice4b,
                5: Dice5b,
                6: Dice6b
            }
        };

        const cubeImages = {
            2: Double2,
            4: Double4,
            8: Double8,
            16: Double16,
            32: Double32,
            64: Double64
        };

        function getX(point) {
            if (point >= 13 && point <= 18) {
                const baseX = 50 + (point - 13) * 60;
                return baseX - (point === 13 ? 8 : 0);
            } else if (point >= 19 && point <= 24) {
                return 450 + (point - 19) * 60;
            } else if (point >= 7 && point <= 12) {
                const baseX = 50 + (12 - point) * 60;
                return baseX - (point === 12 ? 4 : 0);
            } else if (point >= 1 && point <= 6) {
                return 450 + (6 - point) * 60;
            }
            return 0;
        }

        function getBaseY(point) {
            return (point > 12) ? 70 : 690;
        }

        function getDy(point) {
            return (point > 12) ? 55 : -55;
        }

        function calculatePips(positions, player, invertColors = false) {
            let totalPips = 0;
            for (let pointStr in positions) {
                if (pointStr === 'bar') {
                    totalPips += Math.abs(positions[pointStr]) * 25;
                } else if (pointStr === 'off') {
                } else {
                    const point = parseInt(pointStr);
                    const count = positions[pointStr];
                    let effectivePoint = point;
                    if (invertColors) {
                        if (player === 'red') {
                            effectivePoint = 25 - point;
                        } else if (player === 'black') {
                            effectivePoint = point;
                        }
                    } else {
                        if (player === 'black') {
                            effectivePoint = 25 - point;
                        } else {
                            effectivePoint = point;
                        }
                    }
                    totalPips += count * effectivePoint;
                }
            }
            return totalPips;
        }

        function currentPlayerType(positions, currentPlayerType) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(boardImg, 0, 0, canvas.width, canvas.height);

            drawCheckers('red', whiteImg, positions.red, currentPlayerType);
            drawCheckers('black', blackImg, positions.black, currentPlayerType);

            const turnData = data[current];
            if (turnData && turnData.dice && turnData.dice.length >= 2 && !['double', 'take', 'win'].includes(turnData.action)) {
                const [d1, d2] = turnData.dice;
                const diceY = 350;
                let diceX1, diceX2;
                let diceSet;
                if (invertColors) {
                    if (currentPlayer === 'red') {
                        diceX1 = 130;
                        diceX2 = 220;
                        diceSet = diceImages.white;
                    } else {
                        diceX1 = 530;
                        diceX2 = 620;
                        diceSet = diceImages.black;
                    }
                } else {
                    if (currentPlayer === 'red') {
                        diceX1 = 530;
                        diceX2 = 620;
                        diceSet = diceImages.white;
                    } else {
                        diceX1 = 130;
                        diceX2 = 220;
                        diceSet = diceImages.black;
                    }
                }
                if (diceSet[d1]) ctx.drawImage(diceSet[d1], diceX1, diceY, 60, 60);
                if (diceSet[d2]) ctx.drawImage(diceSet[d2], diceX2, diceY, 60, 60);
            }

            // Draw cube during animation
            const item = turnData;
            if (current < firstDoubleIndex) {
                ctx.drawImage(Double64, 375, 350, 50, 50);
            }

            for (let i = 0; i < doubleTurns.length; i++) {
                const doubleIndex = doubleTurns[i];
                if (current === doubleIndex) {
                    const cubeValue = data[doubleIndex].cube;
                    const doubleImages = {
                        2: Double2,
                        4: Double4,
                        8: Double8,
                        16: Double16,
                        32: Double32,
                        64: Double64
                    };
                    const img = doubleImages[cubeValue];
                    if (img) {
                        let cubeX;
                        if (invertColors) {
                            if (data[doubleIndex].player === 'Red') {
                                cubeX = 175; // куб справа для красных при инверсии
                            } else {
                                cubeX = 575; // куб слева для черных при инверсии
                            }
                        } else {
                            if (data[doubleIndex].player === 'Red') {
                                cubeX = 575; // куб слева для красных
                            } else {
                                cubeX = 175; // куб справа для черных
                            }
                        }
                        ctx.drawImage(img, cubeX, 350, 50, 50);
                    }
                    break;
                }
            }

            if (currentCube && current > firstDoubleIndex && !doubleTurns.includes(current) && item.action !== 'win') {
                let cubeY = 350;
                if (invertColors) {
                    if (currentCubePlayer === 'Red') {
                        cubeY = 600;
                    } else if (currentCubePlayer === 'Black') {
                        cubeY = 100;
                    }
                } else {
                    if (currentCubePlayer === 'Black') {
                        cubeY = 600;
                    } else if (currentCubePlayer === 'Red') {
                        cubeY = 100;
                    }
                }
                ctx.drawImage(currentCube, 375, cubeY, 50, 50);
            }

            if (item.action === 'win') {
                ctx.drawImage(Double64, 375, 350, 50, 50);
            }
        }

        function animateSingleMove(move, playerType, temp_positions, callback) {
            const img = playerType === 'red' ? whiteImg : blackImg;
            const player_pos = temp_positions[playerType];
            const opp_pos = temp_positions[playerType === 'red' ? 'black' : 'red'];
            const fromStr = move.from.toString();
            const toStr = move.to.toString()
            let fromX, fromY;
            const rawFrom = move.from;
            const fromIsBar = (rawFrom === 'bar' || rawFrom === 25 || rawFrom === '25');
            const rawTo = move.to;
            const isOff = (rawTo === 'off' || rawTo === 0 || rawTo === '0');
            const isBar = (rawTo === 'bar' || rawTo === 25 || rawTo === '25');
            if (fromIsBar) {
                fromX = 400;
                let barY = (playerType === 'black') ? 220 : 520;
                let barDy = (playerType === 'black') ? 55 : -55;
                if (invertColors) {
                    barY = (playerType === 'black') ? 520 : 220;
                    barDy = (playerType === 'black') ? -55 : 55;
                }
                const barCount = player_pos['bar'] || 0;
                fromY = barY + (barCount - 1) * barDy;
            } else {
                const fromPoint = parseInt(fromStr);
                fromX = getX(fromPoint);
                const fromBaseY = getBaseY(fromPoint);
                const fromDy = getDy(fromPoint);
                const fromCount = player_pos[fromStr] || 0;
                fromY = fromBaseY + (fromCount - 1) * fromDy;
            }

            if (fromIsBar) {
                player_pos['bar'] = (player_pos['bar'] || 1) - 1;
                if (player_pos['bar'] === 0) delete player_pos['bar'];
            } else {
                player_pos[fromStr] = (player_pos[fromStr] || 1) - 1;
                if (player_pos[fromStr] === 0) delete player_pos[fromStr];
            }

            let toX, toY;
            if (isOff) {
                toX = 820;
                toY = playerType === 'black'
                    ? (invertColors ? 440 : 340)
                    : (invertColors ? 340 : 440);
            } else {
                const toPoint = parseInt(toStr);
                toX = getX(toPoint);
                const toBaseY = getBaseY(toPoint);
                const toDy = getDy(toPoint);
                let toCount = player_pos[toStr] || 0;
                if (move.hit) {
                    toCount = 0; // After hit, place on empty point
                }
                toY = toBaseY + toCount * toDy;
            }

            let progress = 0;
            const duration = 200 / animationSpeed; // Duration for smooth animation
            const startTime = Date.now();

            const animate = () => {
                const elapsed = Date.now() - startTime;
                progress = Math.min(elapsed / duration, 1);
                // Ease-in-out for smoother movement
                const easedProgress = progress < 0.5 ? 2 * progress * progress : 1 - Math.pow(-2 * progress + 2, 2) / 2;
                const currentX = fromX + (toX - fromX) * easedProgress;
                const currentY = fromY + (toY - fromY) * easedProgress;

                drawBoardForAnimation(temp_positions);
                ctx.drawImage(img, currentX - 31.25, currentY - 31.25, 62.5, 62.5);

                if (progress < 1) {
                    requestAnimationFrame(animate);
                } else {
                    // Add checker to to position
                    if (toStr === 'off') {
                        player_pos['off'] = (player_pos['off'] || 0) + 1;
                    } else {
                        player_pos[toStr] = (player_pos[toStr] || 0) + 1;
                    }
                    callback(move.hit, move, playerType, temp_positions);
                }
            };
            animate();
        }

        function animateHit(move, playerType, temp_positions, finalCallback) {
            const hitPlayerType = playerType === 'red' ? 'black' : 'red';
            const img = hitPlayerType === 'red' ? whiteImg : blackImg;
            const opp_pos = temp_positions[hitPlayerType];

            const toStr = move.to.toString();
            // Temporarily remove hit checker from to position
            opp_pos[toStr] = (opp_pos[toStr] || 1) - 1;
            if (opp_pos[toStr] === 0) delete opp_pos[toStr];

            const hitPoint = parseInt(toStr);
            const fromX = getX(hitPoint);
            const fromBaseY = getBaseY(hitPoint);
            const fromDy = getDy(hitPoint);
            const hitCount = opp_pos[toStr] || 0; // Now 0
            let fromY = fromBaseY + (hitCount - 1) * fromDy;

            const barX = 400;
            let barY = (hitPlayerType === 'black') ? 220 : 520;
            let barDy = (hitPlayerType === 'black') ? 55 : -55;
            if (invertColors) {
                barY = (hitPlayerType === 'black') ? 520 : 220;
                barDy = (hitPlayerType === 'black') ? -55 : 55;
            }
            const barCount = opp_pos['bar'] || 0;
            const toX = 820; // Fly to the right
            const toY = barY + barCount * barDy; // Position for the hit checker on bar

            let progress = 0;
            const duration = 200 / animationSpeed;
            const startTime = Date.now();

            const animate = () => {
                const elapsed = Date.now() - startTime;
                progress = Math.min(elapsed / duration, 1);
                // Ease-in-out for smoother movement
                const easedProgress = progress < 0.5 ? 2 * progress * progress : 1 - Math.pow(-2 * progress + 2, 2) / 2;
                const currentX = fromX + (barX - fromX) * easedProgress;
                const currentY = fromY + (toY - fromY) * easedProgress;

                drawBoardForAnimation(temp_positions);
                ctx.drawImage(img, currentX - 31.25, currentY - 31.25, 62.5, 62.5);

                if (progress < 1) {
                    requestAnimationFrame(animate);
                } else {
                    // Add hit checker to bar
                    opp_pos['bar'] = (opp_pos['bar'] || 0) + 1;
                    finalCallback();
                }
            };
            animate();
        }

        function updateTempPositionsAfterMove(move, playerType, temp_positions) {
            const player_pos = temp_positions[playerType];
            const opp_pos = temp_positions[playerType === 'red' ? 'black' : 'red'];
            const fromStr = move.from.toString();
            const toStr = move.to.toString();
            const isOffMove = (move.to === 0 || move.to === '0' || move.to === 'off');
            const isBarFrom = (move.from === 25 || move.from === '25' || move.from === 'bar');
            if (move.hit) {
                opp_pos[toStr] = (opp_pos[toStr] || 1) - 1;
                if (opp_pos[toStr] === 0) delete opp_pos[toStr];
                opp_pos['bar'] = (opp_pos['bar'] || 0) + 1;
            }

            if (isBarFrom) {
                player_pos['bar'] = (player_pos['bar'] || 1) - 1;
                if (player_pos['bar'] <= 0) delete player_pos['bar'];
            } else {
                player_pos[fromStr] = (player_pos[fromStr] || 1) - 1;
                if (player_pos[fromStr] === 0) delete player_pos[fromStr];
            }
            if (isOffMove) {
                player_pos['off'] = (player_pos['off'] || 0) + 1;
            } else {
                player_pos[toStr] = (player_pos[toStr] || 0) + 1;
            }
        }

        function drawCheckers(player, img, positions, currentPlayer) {
            ctx.font = 'bold 30px Arial';
            ctx.fillStyle = '#ffffff';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';

            if (player === currentPlayer) {
                for (let point = 1; point <= 24; point++) {
                    const x = getX(point);
                    let y = getBaseY(point);
                    const dy = getDy(point);

                    let displayPoint = point;
                    if (invertColors) {
                        if (player === 'red') {
                            displayPoint = 25 - point; // Red sees points inverted when colors are inverted
                        } else if (player === 'black') {
                            displayPoint = point; // Black sees points normally when colors are inverted
                        }
                    } else {
                        if (player === 'black') {
                            displayPoint = 25 - point; // Black sees points inverted (24 at top-right, 1 at bottom-left)
                        } else if (player === 'red') {
                            displayPoint = point; // Red sees points starting from bottom-left (1 at bottom-left, 24 at top-right)
                        }
                    }
                    let numberY;
                    if (point > 12) {
                        numberY = y - 50; // Above for upper half
                    } else {
                        numberY = y + 60; // Below for lower half
                    }
                    ctx.fillText(displayPoint, x, numberY);
                }
            }

            for (let pointStr in positions) {
                if (pointStr === 'bar' || pointStr === 'off') continue;
                const point = parseInt(pointStr);
                let count = positions[pointStr];
                const x = getX(point);
                let y = getBaseY(point);
                const dy = getDy(point);

                for (let i = 0; i < Math.min(count, 6); i++) {
                    ctx.drawImage(img, x - 31.25, y + (i * dy) - 31.25, 62.5, 62.5);
                }

                if (count > 6) {
                    const lastCheckerY = y + (5 * dy);
                    ctx.fillText(`${count}`, x + 40, lastCheckerY + 5);
                }
            }

            const barX = 400;
            let barY = (player === 'black') ? 220 : 520;
            if (invertColors) {
                barY = (player === 'black') ? 520 : 220;
            }
            if (positions.bar && positions.bar !== 0) {
                let y = barY;
                const dy = (player === 'black') ? 55 : -55;
                for (let i = 0; i < Math.min(Math.abs(positions.bar), 6); i++) {
                    ctx.drawImage(img, barX - 31.25, y + (i * dy) - 31.25, 62.5, 62.5);
                }
                if (Math.abs(positions.bar) > 6) {
                    const lastCheckerY = y + (5 * dy);
                    ctx.fillText(`(${Math.abs(positions.bar)})`, barX + 30, lastCheckerY + 5);
                }
            }

            let offX = 783;
            // объявляем offY вне блоков, затем назначаем значение в зависимости от invertColors и player
            let offY;
            if (invertColors) {
                offY = (player === 'black') ? 440 : 340;
            } else {
                offY = (player === 'black') ? 340 : 440;
            }
            if (positions.off && positions.off !== 0) {
                const originalFont = ctx.font;
                ctx.font = 'bold 32px Arial';
                ctx.fillText(`${positions.off}`, offX, offY);
                ctx.font = originalFont;
            }
        }

        function render(turn, invertColors = false) {
            if (!data || !data[turn]) {
                console.error('No data for turn:', turn);
                document.getElementById('move-info').innerHTML = '<div class="error">No data available for this turn.</div>';
                return;
            }

            const hidePips = hidePipsCheckbox && hidePipsCheckbox.checked;

            current = turn;
            updateCurrentCube(turn);
            document.getElementById('turnLabel').innerText = `${data[turn].turn || 'End'}`;
            console.log('Rendering turn:', turn, 'Data:', data[turn]);

            ctx.clearRect(0, 0, 800, 800);
            ctx.drawImage(boardImg, 0, 0, 800, 800);

            let redPositions, blackPositions;
            if (turn === 0) {
                if (invertColors) {
                    redPositions = { '1': 2, '12': 5, '17': 3, '19': 5, 'bar': 0, 'off': 0 };
                    blackPositions = { '6': 5, '8': 3, '13': 5, '24': 2, 'bar': 0, 'off': 0 };
                } else {
                    redPositions = { '24': 2, '6': 5, '8': 3, '13': 5, 'bar': 0, 'off': 0 };
                    blackPositions = { '1': 2, '19': 5, '17': 3, '12': 5, 'bar': 0, 'off': 0 };
                }
            } else {
                const prevTurn = turn - 1;
                if (invertColors) {
                    redPositions = data[prevTurn].inverted_positions['red'];
                    blackPositions = data[prevTurn].inverted_positions['black'];
                } else {
                    redPositions = data[prevTurn].positions['red'];
                    blackPositions = data[prevTurn].positions['black'];
                }
            }
            const currentPlayer = data[turn].player.toLowerCase();
            drawCheckers('red', whiteImg, redPositions, currentPlayer);
            drawCheckers('black', blackImg, blackPositions, currentPlayer);

            const redPips = calculatePips(redPositions, 'red', invertColors);
            const blackPips = calculatePips(blackPositions, 'black', invertColors);

            if (!hidePips) {
                const blackPipsEl = document.getElementById('black-pips');
                const redPipsEl = document.getElementById('red-pips');
                if (invertColors) {
                    if (blackPipsEl) {
                        blackPipsEl.innerText = `${redPips}`;
                        blackPipsEl.className = 'pips-above-board-inverted';
                        blackPipsEl.style.display = 'block';
                    }
                    if (redPipsEl) {
                        redPipsEl.innerText = `${blackPips}`;
                        redPipsEl.className = 'pips-below-board-inverted';
                        redPipsEl.style.display = 'block';
                    }
                    ctx.fillStyle = '#000000';
                    ctx.fillRect(650, 800, 150, 50);
                    ctx.fillStyle = '#ffffff';
                    ctx.font = 'bold 20px Arial';
                    ctx.textAlign = 'center';
                    ctx.fillText(`${redPips}`, 725, -20);

                    ctx.fillStyle = '#ffffff';
                    ctx.fillRect(650, -50, 150, 50);
                    ctx.fillStyle = '#000000';
                    ctx.fillText(`${blackPips}`, 725, 830);
                } else {
                    if (blackPipsEl) {
                        blackPipsEl.innerText = `${blackPips}`;
                        blackPipsEl.className = 'pips-above-board';
                        blackPipsEl.style.display = 'block';
                    }
                    if (redPipsEl) {
                        redPipsEl.innerText = `${redPips}`;
                        redPipsEl.className = 'pips-below-board';
                        redPipsEl.style.display = 'block';
                    }
                    ctx.fillStyle = '#000000';
                    ctx.fillRect(650, -50, 150, 50);
                    ctx.fillStyle = '#ffffff';
                    ctx.font = 'bold 20px Arial';
                    ctx.textAlign = 'center';
                    ctx.fillText(`${blackPips}`, 725, -20);

                    ctx.fillStyle = '#ffffff';
                    ctx.fillRect(650, 800, 150, 50);
                    ctx.fillStyle = '#000000';
                    ctx.fillText(`${redPips}`, 725, 830);
                }
            } else {
                const blackPipsEl = document.getElementById('black-pips');
                const redPipsEl = document.getElementById('red-pips');
                if (blackPipsEl) blackPipsEl.style.display = 'none';
                if (redPipsEl) redPipsEl.style.display = 'none';
            }


            const item = data[turn];
            if (item.dice && item.dice.length >= 2 && !['double', 'take', 'win'].includes(item.action)) {
                const [d1, d2] = item.dice;
                const diceY = 350;

                let diceX1, diceX2;
                let diceSet;
                if (invertColors) {
                    if (item.player === 'Red') {
                        diceX1 = 130; // кубики слева для красных при инверсии
                        diceX2 = 220;
                        diceSet = diceImages.white;
                    } else {
                        diceX1 = 530; // кубики справа для черных при инверсии
                        diceX2 = 620;
                        diceSet = diceImages.black;
                    }
                } else {
                    if (item.player === 'Red') {
                        diceX1 = 530; // кубики справа для красных
                        diceX2 = 620;
                        diceSet = diceImages.white;
                    } else {
                        diceX1 = 130; // кубики слева для черных
                        diceX2 = 220;
                        diceSet = diceImages.black;
                    }
                }

                if (diceSet[d1]) ctx.drawImage(diceSet[d1], diceX1, diceY, 60, 60);
                if (diceSet[d2]) ctx.drawImage(diceSet[d2], diceX2, diceY, 60, 60);
            }


            if (turn < firstDoubleIndex) {
                ctx.drawImage(Double64, 375, 350, 50, 50);
            }

            for (let i = 0; i < doubleTurns.length; i++) {
                const doubleIndex = doubleTurns[i];
                if (turn === doubleIndex) {
                    const cubeValue = data[doubleIndex].cube;
                    const doubleImages = {
                        2: Double2,
                        4: Double4,
                        8: Double8,
                        16: Double16,
                        32: Double32,
                        64: Double64
                    };
                    const img = doubleImages[cubeValue];
                    if (img) {
                        let cubeX;
                        if (invertColors) {
                            if (data[doubleIndex].player === 'Red') {
                                cubeX = 175; // куб справа для красных при инверсии
                            } else {
                                cubeX = 575; // куб слева для черных при инверсии
                            }
                        } else {
                            if (data[doubleIndex].player === 'Red') {
                                cubeX = 575; // куб слева для красных
                            } else {
                                cubeX = 175; // куб справа для черных
                            }
                        }
                        ctx.drawImage(img, cubeX, 350, 50, 50);
                    }
                    break;
                }
            }

            if (currentCube && turn > firstDoubleIndex && !doubleTurns.includes(turn) && item.action !== 'win') {
                let cubeY = 350;
                if (invertColors) {
                    if (currentCubePlayer === 'Red') {
                        cubeY = 600;
                    } else if (currentCubePlayer === 'Black') {
                        cubeY = 100;
                    }
                } else {
                    if (currentCubePlayer === 'Black') {
                        cubeY = 600;
                    } else if (currentCubePlayer === 'Red') {
                        cubeY = 100;
                    }
                }
                ctx.drawImage(currentCube, 375, cubeY, 50, 50);
            }

            if (item.action === 'win') {
                ctx.drawImage(Double64, 375, 350, 50, 50);
            }
            let info = '';
            let prefix = (turn > 0 && data[turn - 1].action === 'double') ? '<strong>Take</strong>  <br>' : '';
            if (item.action === 'double') {
                info = `Double (${item.cube})`;
            } else if (item.action === 'take') {
                info = `Take`;
            } else if (item.action === 'win') {
                // Найти следующую игру для счета
                const nextGame = availableGames.find(g => g.game_number > currentGameNum);
                let finalRedScore, finalBlackScore;
                if (nextGame) {
                    // Загрузить scores из файла следующей игры
                    fetchGameJson(nextGame.game_number)
                        .then(json => {
                            const nextScores = json.game_info.scores || {};
                            finalRedScore = nextScores.Red || 0;
                            finalBlackScore = nextScores.Black || 0;
                            const larger = Math.max(finalRedScore, finalBlackScore);
                            const smaller = Math.min(finalRedScore, finalBlackScore);
                            const winInfo = `${item.player_name} победил. Счёт ${larger} - ${smaller}`;
                            document.getElementById('move-info').innerHTML = winInfo;
                        })
                        .catch(error => {
                            console.error('Error loading next game scores:', error);
                            // Fallback to current logic
                            finalRedScore = gameRedScore;
                            finalBlackScore = gameBlackScore;
                            if (item.player_name === redPlayer) {
                                finalRedScore += item.points;
                            } else if (item.player_name === blackPlayer) {
                                finalBlackScore += item.points;
                            }
                            const larger = Math.max(finalRedScore, finalBlackScore);
                            const smaller = Math.min(finalRedScore, finalBlackScore);
                            info = `${item.player_name} победил. Счёт ${larger} - ${smaller}`;
                        });
                    return; // Exit early, info will be set asynchronously
                } else {
                    // Если следующей игры нет, используем текущую логику
                    finalRedScore = gameRedScore;
                    finalBlackScore = gameBlackScore;
                    if (item.player_name === redPlayer) {
                        finalRedScore += item.points;
                    } else if (item.player_name === blackPlayer) {
                        finalBlackScore += item.points;
                    }
                }
                const larger = Math.max(finalRedScore, finalBlackScore);
                const smaller = Math.min(finalRedScore, finalBlackScore);
                info = `${item.player_name} победил. Счёт ${larger} - ${smaller}`;
            } else if (item.moves && item.moves.length > 0) {
                info = prefix + `${item.gnu_move ? item.gnu_move.trim() : ''}`;
            } else if (item.moves && item.moves.length === 0) {
                info = prefix + `Пропуск хода`;
            } else {
                info = prefix + '<div class="info-text">No moves available for this turn.</div>';
                console.warn('No moves for turn:', turn, item);
            }
            setTimeout(() => {
                document.getElementById('move-info').innerHTML = info;
                console.log('Info set to:', info);
                console.log('Actual move-info div content:', document.getElementById('move-info').innerHTML);
            }, 0);

            // Generate cube hints table
            let cubeTableHtml = '<table><tr><th>Действие</th><th>Эквити</th></tr>';
            if (item.cube_hints && item.cube_hints.length > 0) {
                let nextGnuMove = (data[turn + 1] && data[turn + 1].gnu_move) ? data[turn + 1].gnu_move.trim() : 'pass';
                const noDoubleHint = (item.cube_hints[0].cubeful_equities || []).find(h => h.action_1 === 'No double');
                const PassHint = (item.cube_hints[0].cubeful_equities || []).find(h => h.action_1 === 'Double' && h.action_2 === 'pass');
                const noDoubleEq = noDoubleHint && noDoubleHint.eq ? noDoubleHint.eq : null;
                const PassHintEq = PassHint && PassHint.eq ? PassHint.eq : null;
                (item.cube_hints[0].cubeful_equities || []).forEach((hint, index) => {
                    const eq = hint.eq ? hint.eq.toFixed(3) : '-';
                    const displayEq = eq;
                    let displayAction = hint.action_1;
                    if (hint.action_2) {
                        displayAction += `, ${hint.action_2}`;
                    }
                    let rowClass = '';
                    if (item.gnu_move && item.gnu_move.trim() === 'Double' && hint.action_1 === 'Double' && hint.action_2 === nextGnuMove) {
                        if (noDoubleEq !== null && hint.eq !== undefined) {
                            if (hint.eq > noDoubleEq) {
                                rowClass = 'hint-best';
                            } else {
                                rowClass = 'hint-good';
                            }
                        }
                    } else if (item.gnu_move && item.gnu_move.trim() === 'take' && hint.action_2 === 'take') {
                        if (PassHintEq !== null && hint.eq !== undefined) {
                            if (hint.eq > PassHintEq) {
                                rowClass = 'hint-best';
                            } else {
                                rowClass = 'hint-good';
                            }
                        }
                    } else if (item.gnu_move && item.gnu_move.trim() !== 'take' && item.gnu_move.trim() !== 'Double' && hint.action_1 === 'No double') {
                        if (index === 0) {
                            rowClass = 'hint-best';
                        } else if (index === 1) {
                            rowClass = 'hint-good';
                        } else if (index === 2) {
                            rowClass = 'hint-poor';
                        }
                    }
                    cubeTableHtml += `<tr class="${rowClass}"><td>${displayAction}</td><td>${displayEq}</td></tr>`;
                });
            }
            cubeTableHtml += '</table>';
            if (item.action !== 'win') {
                document.getElementById('cubeHintsTable').innerHTML = cubeTableHtml;
            }

            // Generate move hints table
            let moveTableHtml = '<table><tr><th>Ход</th><th>%</th><th>%</th><th>Эквити</th></tr>';
            if (item.action === 'win') {
                moveTableHtml += `<tr class="hint-best"><td>Победа ${item.player_name} (${item.points} очков)</td><td>-</td><td>-</td><td>-</td></tr>`;
            } else {
                const firstEq = item.hints && item.hints.length > 0 ? item.hints[0].eq : null;
                (item.hints || []).forEach((hint, index) => {
                    if (hint.probs && hint.probs.length >= 2) {
                        const prob1 = hint.probs[0] ? (hint.probs[0] * 100).toFixed(1) : '-';
                        const prob2 = hint.probs[1] ? (hint.probs[1] * 100).toFixed(1) : '-';
                        const eq = hint.eq ? hint.eq.toFixed(3) : '-';
                        const displayEq = (firstEq !== null && hint.eq !== undefined && index > 0)
                            ? '(' + (hint.eq - firstEq).toFixed(3) + ')'
                            : eq;
                        let move = hint.move || '-';
                        let rowClass = '';
                        const moveNorm = (hint.move || '').replace(/\*/g, '');
                        const gnuNorm = item.gnu_move ? item.gnu_move.trim().replace(/\*/g, '') : '';
                        if (gnuNorm && moveNorm === gnuNorm) {
                            const diff = firstEq - hint.eq;
                            if (diff < eqThreshold) {
                                rowClass = 'hint-best';
                            } else if (index >= 1 && index <= 4) {
                                rowClass = 'hint-good';
                            } else {
                                rowClass = 'hint-poor';
                            }
                        }
                        moveTableHtml += `<tr class="${rowClass}"><td>${move}</td><td>${prob1}</td><td>${prob2}</td><td>${displayEq}</td></tr>`;
                    }
                });
            }
            moveTableHtml += '</table>';
            if (item.action === 'win') {
                document.getElementById('moveHintsTable').innerHTML = '';
                document.getElementById('cubeHintsTable').innerHTML = '';
            } else {
                document.getElementById('moveHintsTable').innerHTML = moveTableHtml;
            }
            
            // Автоматическое открытие таблицы при error != 0
            if (error !== '0' && item.is_visible) {
                const moveHintsBtn = document.getElementById('moveHintsBtn');
                const cubeHintsBtn = document.getElementById('cubeHintsBtn');
                const moveHintsTable = document.getElementById('moveHintsTable');
                const cubeHintsTable = document.getElementById('cubeHintsTable');
                
                // Определяем, есть ли ошибки (проверяем явно false, чтобы не учитывать undefined)
                const hasMoveError = (Array.isArray(item.moves) && item.moves.length > 0) && 
                                   item.is_best_move === false;
                const hasCubeError = (item.action === 'double' || item.action === 'take' || item.action === 'drop') && 
                                    item.is_best_move_cube === false;
                
                // Если оба параметра False - открываем таблицу по ходу
                if (hasMoveError && hasCubeError) {
                    moveHintsTable.classList.add('active');
                    moveHintsBtn.classList.add('active');
                    cubeHintsTable.classList.remove('active');
                    cubeHintsBtn.classList.remove('active');
                }
                // Если только ошибка по кубу - открываем таблицу куба
                else if (hasCubeError && !hasMoveError) {
                    cubeHintsTable.classList.add('active');
                    cubeHintsBtn.classList.add('active');
                    moveHintsTable.classList.remove('active');
                    moveHintsBtn.classList.remove('active');
                }
                // Если только ошибка по ходу - открываем таблицу ходов
                else if (hasMoveError && !hasCubeError) {
                    moveHintsTable.classList.add('active');
                    moveHintsBtn.classList.add('active');
                    cubeHintsTable.classList.remove('active');
                    cubeHintsBtn.classList.remove('active');
                }
            }
        }

        function findNextVisibleIndex(fromIndex) {
            let i = fromIndex;
            while (i < data.length && !(data[i] && data[i].is_visible)) i++;
            return i;
        }

        function findPrevVisibleIndex(fromIndex) {
            let i = fromIndex;
            while (i >= 0 && !(data[i] && data[i].is_visible)) i--;
            return i;
        }

        function goToNextVisibleMoveOrGame() {
            if (!dataLoaded || !data || !data.length) return false;
            let nextIdx = findNextVisibleIndex(current + 1);
            if (nextIdx < data.length) {
                current = nextIdx;
                render(current, invertColors);
                updateButtons();
                updateInfo();
                return true;
            }
            if (availableGames.length > 1) {
                const currentIndex = availableGames.findIndex(
                    (game) => game.game_number == currentGameNum
                );
                if (currentIndex !== -1 && currentIndex < availableGames.length - 1) {
                    loadGame(availableGames[currentIndex + 1].game_number);
                    return true;
                }
            }
            return false;
        }

        function goToPrevVisibleMoveOrGame() {
            if (!dataLoaded || !data || !data.length) return Promise.resolve(false);
            let prevIdx = findPrevVisibleIndex(current - 1);
            if (prevIdx >= 0) {
                current = prevIdx;
                render(current, invertColors);
                updateButtons();
                updateInfo();
                return Promise.resolve(true);
            }
            if (availableGames.length > 1) {
                const currentIndex = availableGames.findIndex(
                    (game) => game.game_number == currentGameNum
                );
                if (currentIndex > 0) {
                    const prevGameNum = availableGames[currentIndex - 1].game_number;
                    return loadGame(prevGameNum).then(function () {
                        current = findPrevVisibleIndex(data.length - 1);
                        if (current < 0) current = 0;
                        render(current, invertColors);
                        updateButtons();
                        updateInfo();
                        return true;
                    });
                }
            }
            return Promise.resolve(false);
        }

        async function prevTurn() {
            if (animating) {
                skipAnimation = true;
                pendingPrevGame = true;
                setTimeout(() => {
                    if (pendingPrevGame) {
                        pendingPrevGame = false;
                        goToPrevVisibleMoveOrGame();
                    }
                }, 50);
                return;
            }

            if (dataLoaded) {
                await goToPrevVisibleMoveOrGame();
            }
        }

        function drawBoardForAnimation(positions) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(boardImg, 0, 0, canvas.width, canvas.height);

            updateCurrentCube(current);

            const currentPlayer = data[current].player.toLowerCase();
            drawCheckers('red', whiteImg, positions.red, currentPlayer);
            drawCheckers('black', blackImg, positions.black, currentPlayer);

            const turnData = data[current];
            if (turnData && turnData.dice && turnData.dice.length >= 2 && !['double', 'take', 'win'].includes(turnData.action)) {
                const [d1, d2] = turnData.dice;
                const diceY = 350;
                let diceX1, diceX2;
                let diceSet;
                if (invertColors) {
                    if (currentPlayer === 'red') {
                        diceX1 = 130;
                        diceX2 = 220;
                        diceSet = diceImages.white;
                    } else {
                        diceX1 = 530;
                        diceX2 = 620;
                        diceSet = diceImages.black;
                    }
                } else {
                    if (currentPlayer === 'red') {
                        diceX1 = 530;
                        diceX2 = 620;
                        diceSet = diceImages.white;
                    } else {
                        diceX1 = 130;
                        diceX2 = 220;
                        diceSet = diceImages.black;
                    }
                }
                if (diceSet[d1]) ctx.drawImage(diceSet[d1], diceX1, diceY, 60, 60);
                if (diceSet[d2]) ctx.drawImage(diceSet[d2], diceX2, diceY, 60, 60);
            }

            // Draw cube
            if (current < firstDoubleIndex) {
                ctx.drawImage(Double64, 375, 350, 50, 50);
            }

            for (let i = 0; i < doubleTurns.length; i++) {
                const doubleIndex = doubleTurns[i];
                if (current === doubleIndex) {
                    const cubeValue = data[doubleIndex].cube;
                    const doubleImages = {
                        2: Double2,
                        4: Double4,
                        8: Double8,
                        16: Double16,
                        32: Double32,
                        64: Double64
                    };
                    const img = doubleImages[cubeValue];
                    if (img) {
                        let cubeX;
                        if (invertColors) {
                            if (data[doubleIndex].player === 'Red') {
                                cubeX = 175; // куб справа для красных при инверсии
                            } else {
                                cubeX = 575; // куб слева для черных при инверсии
                            }
                        } else {
                            if (data[doubleIndex].player === 'Red') {
                                cubeX = 575; // куб слева для красных
                            } else {
                                cubeX = 175; // куб справа для черных
                            }
                        }
                        ctx.drawImage(img, cubeX, 350, 50, 50);
                    }
                    break;
                }
            }

            if (currentCube && current > firstDoubleIndex && !doubleTurns.includes(current) && turnData.action !== 'win') {
                let cubeY = 350;
                if (invertColors) {
                    if (currentCubePlayer === 'Red') {
                        cubeY = 600;
                    } else if (currentCubePlayer === 'Black') {
                        cubeY = 100;
                    }
                } else {
                    if (currentCubePlayer === 'Black') {
                        cubeY = 600;
                    } else if (currentCubePlayer === 'Red') {
                        cubeY = 100;
                    }
                }
                ctx.drawImage(currentCube, 375, cubeY, 50, 50);
            }

            if (turnData.action === 'win') {
                ctx.drawImage(Double64, 375, 350, 50, 50);
            }
        }

        function animateSingleMove(move, playerType, temp_positions, callback) {
            const img = playerType === 'red' ? whiteImg : blackImg;
            const player_pos = temp_positions[playerType];
            const opp_pos = temp_positions[playerType === 'red' ? 'black' : 'red'];
            const fromStr = move.from.toString();
            const toStr = move.to.toString()
            let fromX, fromY;
            const rawFrom = move.from;
            const fromIsBar = (rawFrom === 'bar' || rawFrom === 25 || rawFrom === '25');
            const rawTo = move.to;
            const isOff = (rawTo === 'off' || rawTo === 0 || rawTo === '0');
            const isBar = (rawTo === 'bar' || rawTo === 25 || rawTo === '25');
            if (fromIsBar) {
                fromX = 400;
                const barY = (playerType === 'black') ? 220 : 520;
                const barDy = (playerType === 'black') ? 55 : -55;
                const barCount = player_pos['bar'] || 0;
                fromY = barY + (barCount - 1) * barDy;
            } else {
                const fromPoint = parseInt(fromStr);
                fromX = getX(fromPoint);
                const fromBaseY = getBaseY(fromPoint);
                const fromDy = getDy(fromPoint);
                const fromCount = player_pos[fromStr] || 0;
                fromY = fromBaseY + (fromCount - 1) * fromDy;
            }

            if (fromIsBar) {
                player_pos['bar'] = (player_pos['bar'] || 1) - 1;
                if (player_pos['bar'] === 0) delete player_pos['bar'];
            } else {
                player_pos[fromStr] = (player_pos[fromStr] || 1) - 1;
                if (player_pos[fromStr] === 0) delete player_pos[fromStr];
            }

            let toX, toY;
            if (isOff) {
                toX = 820;
                toY = playerType === 'black'
                    ? (invertColors ? 440 : 340)
                    : (invertColors ? 340 : 440);
            } else {
                const toPoint = parseInt(toStr);
                toX = getX(toPoint);
                const toBaseY = getBaseY(toPoint);
                const toDy = getDy(toPoint);
                let toCount = player_pos[toStr] || 0;
                if (move.hit) {
                    toCount = 0; // After hit, place on empty point
                }
                toY = toBaseY + toCount * toDy;
            }

            let progress = 0;
            const duration = 200 / animationSpeed; // Duration for smooth animation
            const startTime = Date.now();

            const animate = () => {
                const elapsed = Date.now() - startTime;
                progress = Math.min(elapsed / duration, 1);
                // Ease-in-out for smoother movement
                const easedProgress = progress < 0.5 ? 2 * progress * progress : 1 - Math.pow(-2 * progress + 2, 2) / 2;
                const currentX = fromX + (toX - fromX) * easedProgress;
                const currentY = fromY + (toY - fromY) * easedProgress;

                drawBoardForAnimation(temp_positions);
                ctx.drawImage(img, currentX - 31.25, currentY - 31.25, 62.5, 62.5);

                if (progress < 1) {
                    requestAnimationFrame(animate);
                } else {
                    // Add checker to to position
                    if (toStr === 'off') {
                        player_pos['off'] = (player_pos['off'] || 0) + 1;
                    } else {
                        player_pos[toStr] = (player_pos[toStr] || 0) + 1;
                    }
                    callback(move.hit, move, playerType, temp_positions);
                }
            };
            animate();
        }

        function animateHit(move, playerType, temp_positions, finalCallback) {
            const hitPlayerType = playerType === 'red' ? 'black' : 'red';
            const img = hitPlayerType === 'red' ? whiteImg : blackImg;
            const opp_pos = temp_positions[hitPlayerType];

            const toStr = move.to.toString();
            // Temporarily remove hit checker from to position
            opp_pos[toStr] = (opp_pos[toStr] || 1) - 1;
            if (opp_pos[toStr] === 0) delete opp_pos[toStr];

            const hitPoint = parseInt(toStr);
            const fromX = getX(hitPoint);
            const fromBaseY = getBaseY(hitPoint);
            const fromDy = getDy(hitPoint);
            const hitCount = opp_pos[toStr] || 0; // Now 0
            let fromY = fromBaseY + (hitCount - 1) * fromDy;

            const barX = 400;
            const barY = (hitPlayerType === 'black') ? 220 : 520;
            const barDy = (hitPlayerType === 'black') ? 55 : -55;
            const barCount = opp_pos['bar'] || 0;
            const toX = 820; // Fly to the right
            const toY = barY + barCount * barDy; // Position for the hit checker on bar

            let progress = 0;
            const duration = 200 / animationSpeed;
            const startTime = Date.now();

            const animate = () => {
                const elapsed = Date.now() - startTime;
                progress = Math.min(elapsed / duration, 1);
                // Ease-in-out for smoother movement
                const easedProgress = progress < 0.5 ? 2 * progress * progress : 1 - Math.pow(-2 * progress + 2, 2) / 2;
                const currentX = fromX + (barX - fromX) * easedProgress;
                const currentY = fromY + (toY - fromY) * easedProgress;

                drawBoardForAnimation(temp_positions);
                ctx.drawImage(img, currentX - 31.25, currentY - 31.25, 62.5, 62.5);

                if (progress < 1) {
                    requestAnimationFrame(animate);
                } else {
                    // Add hit checker to bar
                    opp_pos['bar'] = (opp_pos['bar'] || 0) + 1;
                    finalCallback();
                }
            };
            animate();
        }

        function updateTempPositionsAfterMove(move, playerType, temp_positions) {
            const player_pos = temp_positions[playerType];
            const opp_pos = temp_positions[playerType === 'red' ? 'black' : 'red'];
            const fromStr = move.from.toString();
            const toStr = move.to.toString();
            const isOffMove = (move.to === 0 || move.to === '0' || move.to === 'off');
            const isBarFrom = (move.from === 25 || move.from === '25' || move.from === 'bar');
            if (move.hit) {
                opp_pos[toStr] = (opp_pos[toStr] || 1) - 1;
                if (opp_pos[toStr] === 0) delete opp_pos[toStr];
                opp_pos['bar'] = (opp_pos['bar'] || 0) + 1;
            }

            if (isBarFrom) {
                player_pos['bar'] = (player_pos['bar'] || 1) - 1;
                if (player_pos['bar'] <= 0) delete player_pos['bar'];
            } else {
                player_pos[fromStr] = (player_pos[fromStr] || 1) - 1;
                if (player_pos[fromStr] === 0) delete player_pos[fromStr];
            }
            if (isOffMove) {
                player_pos['off'] = (player_pos['off'] || 0) + 1;
            } else {
                player_pos[toStr] = (player_pos[toStr] || 0) + 1;
            }
        }

        function nextTurn() {
            // В режиме «только аудио» (и при выключенной анимации) прыгаем
            // сразу на следующий видимый ход — без промежуточных кадров.
            if (skipAnimationEnabled || matchAnalysisAudioOnly) {
                if (dataLoaded) {
                    goToNextVisibleMoveOrGame();
                }
                return;
            }

            // Если уже идет анимация - устанавливаем флаг пропуска
            if (animating) {
                skipAnimation = true;
                return;
            }

            if (dataLoaded) {
                if (current >= data.length - 1) {
                    // If no next visible in current game, try next game
                    if (availableGames.length > 1) {
                        const currentIndex = availableGames.findIndex(game => game.game_number == currentGameNum);
                        if (currentIndex !== -1 && currentIndex < availableGames.length - 1) {
                            const nextGameNum = availableGames[currentIndex + 1].game_number;
                            loadGame(nextGameNum);
                        }
                    } else {
                        return;
                    }
                } else {

                    animating = true;
                    skipAnimation = false; // Сбрасываем флаг
                    updateButtons();
                    updateInfo(); // Обновляем инфо сразу

                    const nextTurnData = data[current];
                    const playerType = nextTurnData.player.toLowerCase();

                    let prev_positions;
                    if (current === 0) {
                        // Initial positions
                        if (invertColors) {
                            prev_positions = {
                                red: { '1': 2, '12': 5, '17': 3, '19': 5, 'bar': 0, 'off': 0 },
                                black: { '6': 5, '8': 3, '13': 5, '24': 2, 'bar': 0, 'off': 0 }
                            };
                        } else {
                            prev_positions = {
                                red: { '24': 2, '6': 5, '8': 3, '13': 5, 'bar': 0, 'off': 0 },
                                black: { '1': 2, '19': 5, '17': 3, '12': 5, 'bar': 0, 'off': 0 }
                            };
                        }
                    } else {
                        prev_positions = invertColors ? data[current - 1].inverted_positions : data[current - 1].positions;
                    }

                    const temp_positions = JSON.parse(JSON.stringify(prev_positions));

                    let moves = nextTurnData.moves || [];
                    const toScreenPoint = (p) => {
                        if (p === 'off' || p === 0) return 'off';
                        if (p === 'bar' || p === 25) return 'bar';
                        const n = Number(p);
                        if (!Number.isFinite(n) || n < 1 || n > 24) return p;
                        let boardP = (playerType === 'black') ? (25 - n) : n;
                        return invertColors ? (25 - boardP) : boardP;
                    };

                    moves = moves.map(m => ({
                        ...m,
                        from: toScreenPoint(m.from),
                        to: toScreenPoint(m.to),
                    }));

                    const finishAnimatedStep = () => {
                        clearTimeout(timeoutId);
                        animating = false;
                        skipAnimation = false;
                        goToNextVisibleMoveOrGame();
                    };

                    const timeoutId = setTimeout(() => {
                        animating = false;
                        updateButtons();
                    }, 5000);

                    if (moves.length > 0) {
                        let moveIndex = 0;
                        const animateMoves = () => {
                            // Проверяем флаг пропуска
                            if (skipAnimation) {
                                // Применяем все оставшиеся ходы мгновенно
                                while (moveIndex < moves.length) {
                                    const move = moves[moveIndex];
                                    updateTempPositionsAfterMove(move, playerType, temp_positions);
                                    moveIndex++;
                                }
                                finishAnimatedStep();
                                return;
                            }

                            if (moveIndex < moves.length) {
                                const move = moves[moveIndex];
                                animateSingleMove(move, playerType, temp_positions, (hasHit, move, playerType, temp_positions) => {
                                    if (hasHit) {
                                        animateHit(move, playerType, temp_positions, () => {
                                            moveIndex++;
                                            setTimeout(animateMoves, 100 / animationSpeed);
                                        });
                                    } else {
                                        moveIndex++;
                                        setTimeout(animateMoves, 100 / animationSpeed);
                                    }
                                });
                            } else {
                                finishAnimatedStep();
                            }
                        };
                        animateMoves();
                    } else {
                        finishAnimatedStep();
                    }
                }
            }
        }

        function toggleInvert() {
            invertColors = !invertColors;
            render(current, invertColors);
        }

        function updateInfo() {
            if (!dataLoaded) return;

            const turnLabel = document.getElementById('turnLabel');
            turnLabel.textContent = data[current].turn || 'End';

            const moveInfo = document.getElementById('move-info');
            const item = data[current];
            let info = '';
            let prefix = (current > 0 && data[current - 1].action === 'double') ? '<strong>Take</strong>  <br>' : '';
            if (item.action === 'double') {
                info = `Double (${item.cube})`;
            } else if (item.action === 'take') {
                info = `Take`;
            } else if (item.action === 'win') {
                // Найти следующую игру для счета
                const nextGame = availableGames.find(g => g.game_number > currentGameNum);
                let finalRedScore, finalBlackScore;
                if (nextGame) {
                    // Загрузить scores из файла следующей игры
                    fetchGameJson(nextGame.game_number)
                        .then(json => {
                            const nextScores = json.game_info.scores || {};
                            finalRedScore = nextScores.Red || 0;
                            finalBlackScore = nextScores.Black || 0;
                            const larger = Math.max(finalRedScore, finalBlackScore);
                            const smaller = Math.min(finalRedScore, finalBlackScore);
                            const winInfo = `${item.player_name} победил. Счёт ${larger} - ${smaller}`;
                            document.getElementById('move-info').innerHTML = winInfo;
                        })
                        .catch(error => {
                            console.error('Error loading next game scores:', error);
                            // Fallback to current logic
                            finalRedScore = gameRedScore;
                            finalBlackScore = gameBlackScore;
                            if (item.player_name === redPlayer) {
                                finalRedScore += item.points;
                            } else if (item.player_name === blackPlayer) {
                                finalBlackScore += item.points;
                            }
                            const larger = Math.max(finalRedScore, finalBlackScore);
                            const smaller = Math.min(finalRedScore, finalBlackScore);
                            info = `${item.player_name} победил. Счёт ${larger} - ${smaller}`;
                        });
                    return; // Exit early, info will be set asynchronously
                } else {
                    // Если следующей игры нет, используем текущую логику
                    finalRedScore = gameRedScore;
                    finalBlackScore = gameBlackScore;
                    if (item.player_name === redPlayer) {
                        finalRedScore += item.points;
                    } else if (item.player_name === blackPlayer) {
                        finalBlackScore += item.points;
                    }
                }
                const larger = Math.max(finalRedScore, finalBlackScore);
                const smaller = Math.min(finalRedScore, finalBlackScore);
                info = `${item.player_name} победил. Счёт ${larger} - ${smaller}`;
            } else if (item.moves && item.moves.length > 0) {
                info = prefix + `${item.gnu_move ? item.gnu_move.trim() : ''}`;
            } else if (item.moves && item.moves.length === 0) {
                info = prefix + `Пропуск хода`;
            } else {
                info = prefix + '<div class="info-text">No moves available for this turn.</div>';
                console.warn('No moves for turn:', current, item);
            }
            setTimeout(() => {
                document.getElementById('move-info').innerHTML = info;
                console.log('Info set to:', info);
                console.log('Actual move-info div content:', document.getElementById('move-info').innerHTML);
            }, 0);
        }

        function showFadingMessage(message) {
            const msgDiv = document.createElement('div');
            msgDiv.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(0,0,0,0.8);color:white;padding:12px 24px;border-radius:8px;font-size:16px;z-index:10001;';
            msgDiv.textContent = message;
            document.body.appendChild(msgDiv);
            setTimeout(() => {
                msgDiv.style.transition = 'opacity 0.8s';
                msgDiv.style.opacity = '0';
                setTimeout(() => msgDiv.remove(), 800);
            }, 1200);
        }

        const MSG_MODAL_ICONS = {
            success: 'fa-check-circle',
            error: 'fa-times-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        function showMessageModal(message, type) {
            type = type || 'info';
            const overlay = document.getElementById('msgModalOverlay');
            const iconEl = document.getElementById('msgModalIcon');
            const contentEl = document.getElementById('msgModalContent');
            const okBtn = document.getElementById('msgModalOkBtn');
            if (!overlay || !iconEl || !contentEl || !okBtn) return;

            iconEl.className = 'msg-modal-icon ' + type;
            iconEl.innerHTML = '<i class="fa ' + (MSG_MODAL_ICONS[type] || MSG_MODAL_ICONS.info) + '"></i>';
            contentEl.textContent = message;

            const closeModal = () => {
                overlay.classList.remove('show');
                okBtn.onclick = null;
                overlay.onclick = null;
            };

            okBtn.onclick = closeModal;
            overlay.onclick = (e) => { if (e.target === overlay) closeModal(); };

            overlay.classList.add('show');
        }

        const HINT_VIEWER_SCREENSHOT_SELECTORS = [
            '.board-block',
            '.hints-table',
        ];

        function isHintViewerScreenshotElementVisible(el) {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) {
                return false;
            }
            const rect = el.getBoundingClientRect();
            return rect.width > 0 || rect.height > 0;
        }

        function measureHintViewerScreenshotBounds(extraPadding) {
            extraPadding = extraPadding == null ? 12 : extraPadding;
            const topPadding = 50;
            const scrollX = window.scrollX || document.documentElement.scrollLeft || 0;
            const scrollY = window.scrollY || document.documentElement.scrollTop || 0;
            const elements = [];

            HINT_VIEWER_SCREENSHOT_SELECTORS.forEach((selector) => {
                document.querySelectorAll(selector).forEach((el) => {
                    if (isHintViewerScreenshotElementVisible(el)) {
                        elements.push(el);
                    }
                });
            });

            if (!elements.length) {
                const container = document.querySelector('.container');
                if (container) elements.push(container);
            }

            let top = Infinity;
            let left = Infinity;
            let bottom = -Infinity;
            let right = -Infinity;

            elements.forEach((el) => {
                const rect = el.getBoundingClientRect();
                top = Math.min(top, rect.top);
                left = Math.min(left, rect.left);
                bottom = Math.max(bottom, rect.bottom);
                right = Math.max(right, rect.right);
            });

            if (!Number.isFinite(top)) {
                return {
                    x: 0,
                    y: 0,
                    width: document.documentElement.clientWidth,
                    height: document.documentElement.clientHeight,
                    windowWidth: document.documentElement.clientWidth,
                    windowHeight: document.documentElement.clientHeight,
                };
            }

            const cropTop = Math.max(0, Math.floor(top + scrollY - topPadding));
            const cropLeft = Math.max(0, Math.floor(left + scrollX - extraPadding));
            const cropBottom = Math.ceil(bottom + scrollY + extraPadding);
            const cropRight = Math.ceil(right + scrollX + extraPadding);

            return {
                x: cropLeft,
                y: cropTop,
                width: Math.max(1, cropRight - cropLeft),
                height: Math.max(1, cropBottom - cropTop),
                windowWidth: document.documentElement.clientWidth,
                windowHeight: document.documentElement.clientHeight,
            };
        }

        function getHintViewerHtml2CanvasOptions() {
            const bounds = measureHintViewerScreenshotBounds();
            return {
                useCORS: true,
                allowTaint: true,
                backgroundColor: '#1a1a1a',
                x: bounds.x,
                y: bounds.y,
                width: bounds.width,
                height: bounds.height,
                windowWidth: bounds.windowWidth,
                windowHeight: bounds.windowHeight,
                scrollX: 0,
                scrollY: 0,
                scale: Math.min(window.devicePixelRatio || 1, 2),
                ignoreElements: function (el) {
                    return !!(el && el.classList && el.classList.contains('web-standalone-back'));
                },
            };
        }

        function captureHintViewerScreenshot() {
            window.scrollTo(0, 0);
            document.body.classList.add('screenshot-mode');
            return new Promise((resolve, reject) => {
                requestAnimationFrame(() => {
                    requestAnimationFrame(() => {
                        ensureHtml2Canvas().then(function (html2canvas) { return html2canvas(document.body, getHintViewerHtml2CanvasOptions()); })
                            .then(resolve)
                            .catch(reject)
                            .finally(function () {
                                document.body.classList.remove('screenshot-mode');
                            });
                    });
                });
            });
        }

        function appendMatchAnalysisAudioToFormData(formData) {
            if (!matchAnalysisMode || typeof getCurrentMoveAudioMeta !== 'function') {
                return;
            }
            const meta = getCurrentMoveAudioMeta();
            if (!meta || !meta.audioS3Key) return;
            formData.append('audio_s3_key', meta.audioS3Key);
            if (meta.audioName) {
                formData.append('audio_name', meta.audioName);
            }
        }

        function saveScreenshot() {
            // Hide controls and game selector before taking screenshot
            const controls = document.getElementById('controls');
            const invertBtn = document.getElementById('invertBtn');
            const screenshotBtn = document.getElementById('screenshotBtn');
            const gameSelect = document.getElementById('gameSelect');
            const hintsButtons = document.querySelector('.hints-buttons');
            const hideInfoCheckbox = document.getElementById('hideInfoCheckbox');
            const playersInfo = document.getElementById('players-info');
            const screenSaveBtn = document.getElementById('screenSaveBtn');
            const screenUploadBtn = document.getElementById('screenUploadBtn');
            const animationControls = document.querySelector('.animation-controls');
            const supportContainer = document.querySelector('.support-container');
            const settingsContainer = document.querySelector('.settings-container');
            const openEditorBtn = document.getElementById('openEditorBtn');
            const adminButtonContainer = document.getElementById('adminButtonContainer');
            const topRow = document.getElementById('top-row');
            const pageTitle = document.querySelector('.container > h1');
            const viewerBelowBoard = document.querySelector('.viewer-below-board');
            const originalAdminButtonContainerDisplay = adminButtonContainer ? adminButtonContainer.style.display : null;
            let animationControlsParent = null;
            let animationControlsNextSibling = null;
            if (animationControls) {
                animationControlsParent = animationControls.parentNode;
                animationControlsNextSibling = animationControls.nextSibling;
                animationControlsParent.removeChild(animationControls);
            }
            const originalControlsDisplay = controls ? controls.style.display : null;
            const originalInvertDisplay = invertBtn ? invertBtn.style.display : null;
            const originalScreenshotDisplay = screenshotBtn ? screenshotBtn.style.display : null;
            const originalGameSelectDisplay = gameSelect ? gameSelect.style.display : null;
            const originalHintsButtonsDisplay = hintsButtons ? hintsButtons.style.display : null;
            const originalHideInfoCheckboxDisplay = hideInfoCheckbox ? hideInfoCheckbox.style.display : null;
            const originalPlayersInfoDisplay = playersInfo ? playersInfo.style.display : null;
            const originalScreenSaveBtnDisplay = screenSaveBtn ? screenSaveBtn.style.display : null;
            const originalScreenUploadBtnDisplay = screenUploadBtn ? screenUploadBtn.style.display : null;
            const originalSupportDisplay = supportContainer ? supportContainer.style.display : null;
            const originalSettingsDisplay = settingsContainer ? settingsContainer.style.display : null;
            const originalOpenEditorBtnDisplay = openEditorBtn ? openEditorBtn.style.display : null;
            const originalTopRowDisplay = topRow ? topRow.style.display : null;
            const originalPageTitleDisplay = pageTitle ? pageTitle.style.display : null;
            const originalViewerBelowDisplay = viewerBelowBoard ? viewerBelowBoard.style.display : null;
            const settingsBtn = document.getElementById('settingsBtn');
            const settingsSpan = settingsContainer ? settingsContainer.querySelector('span') : null;
            const originalSettingsBtnDisplay = settingsBtn ? settingsBtn.style.display : null;
            const originalSettingsSpanDisplay = settingsSpan ? settingsSpan.style.display : null;
            const originalPlayersInfoHTML = playersInfo ? playersInfo.innerHTML : '';
            const matchInfo = document.getElementById('match-info');
            const originalMatchInfoHTML = matchInfo ? matchInfo.innerHTML : '';
            const crawfordLabel = document.getElementById('crawfordLabel');
            const originalCrawfordDisplay = crawfordLabel ? crawfordLabel.style.display : 'none';
            const blackPips = document.getElementById('black-pips');
            const redPips = document.getElementById('red-pips');
            const originalBlackPipsDisplay = blackPips ? blackPips.style.display : 'none';
            const originalRedPipsDisplay = redPips ? redPips.style.display : 'none';

            function restoreControls() {
                if (controls && originalControlsDisplay !== null) controls.style.display = originalControlsDisplay;
                if (invertBtn && originalInvertDisplay !== null) invertBtn.style.display = originalInvertDisplay;
                if (screenshotBtn && originalScreenshotDisplay !== null) screenshotBtn.style.display = originalScreenshotDisplay;
                if (gameSelect && originalGameSelectDisplay !== null) gameSelect.style.display = originalGameSelectDisplay;
                if (hintsButtons && originalHintsButtonsDisplay !== null) hintsButtons.style.display = originalHintsButtonsDisplay;
                if (hideInfoCheckbox && originalHideInfoCheckboxDisplay !== null) hideInfoCheckbox.style.display = originalHideInfoCheckboxDisplay;
                if (screenSaveBtn && originalScreenSaveBtnDisplay !== null) screenSaveBtn.style.display = originalScreenSaveBtnDisplay;
                if (screenUploadBtn && originalScreenUploadBtnDisplay !== null) screenUploadBtn.style.display = originalScreenUploadBtnDisplay;
                if (supportContainer && originalSupportDisplay !== null) supportContainer.style.display = originalSupportDisplay;
                if (settingsBtn && originalSettingsBtnDisplay !== null) settingsBtn.style.display = originalSettingsBtnDisplay;
                if (settingsSpan && originalSettingsSpanDisplay !== null) settingsSpan.style.display = originalSettingsSpanDisplay;
                if (settingsContainer && originalSettingsDisplay !== null) settingsContainer.style.display = originalSettingsDisplay;
                if (openEditorBtn && originalOpenEditorBtnDisplay !== null) openEditorBtn.style.display = originalOpenEditorBtnDisplay;
                if (topRow && originalTopRowDisplay !== null) topRow.style.display = originalTopRowDisplay;
                if (pageTitle && originalPageTitleDisplay !== null) pageTitle.style.display = originalPageTitleDisplay;
                if (viewerBelowBoard && originalViewerBelowDisplay !== null) viewerBelowBoard.style.display = originalViewerBelowDisplay;
                if (animationControls && animationControlsParent) {
                    if (animationControlsNextSibling) {
                        animationControlsParent.insertBefore(animationControls, animationControlsNextSibling);
                    } else {
                        animationControlsParent.appendChild(animationControls);
                    }
                }
                if (playersInfo) {
                    if (originalPlayersInfoDisplay !== null) playersInfo.style.display = originalPlayersInfoDisplay;
                    playersInfo.innerHTML = originalPlayersInfoHTML;
                }
                if (matchInfo && originalMatchInfoHTML !== null) {
                    matchInfo.innerHTML = originalMatchInfoHTML;
                }
                if (crawfordLabel && originalCrawfordDisplay !== null) crawfordLabel.style.display = originalCrawfordDisplay;
                if (blackPips && originalBlackPipsDisplay !== null) blackPips.style.display = originalBlackPipsDisplay;
                if (redPips && originalRedPipsDisplay !== null) redPips.style.display = originalRedPipsDisplay;
                if (settingsContainer && originalSettingsDisplay !== null) settingsContainer.style.display = originalSettingsDisplay;
                restoreAdminButtonContainerAfterScreenshot(adminButtonContainer, originalAdminButtonContainerDisplay);
                setMatchAnalysisCabinetBackVisibleForScreenshot(true);
                removeScreenshotFontScale();
            }

            controls.style.display = 'none';
            invertBtn.style.display = 'none';
            screenshotBtn.style.display = 'none';
            if (gameSelect) gameSelect.style.display = 'none';
            if (hintsButtons) hintsButtons.style.display = 'none';
            if (hideInfoCheckbox) hideInfoCheckbox.style.display = 'none';
            if (screenSaveBtn) screenSaveBtn.style.display = 'none';
            if (screenUploadBtn) screenUploadBtn.style.display = 'none';
            if (supportContainer) supportContainer.style.display = 'none';
            if (settingsContainer) settingsContainer.style.display = 'none';
            if (settingsBtn) settingsBtn.style.display = 'none';
            if (settingsSpan) settingsSpan.style.display = 'none';
            if (openEditorBtn) openEditorBtn.style.display = 'none';
            if (adminButtonContainer) adminButtonContainer.style.display = 'none';
            if (topRow) topRow.style.display = 'none';
            if (pageTitle) pageTitle.style.display = 'none';
            if (viewerBelowBoard) viewerBelowBoard.style.display = 'none';
            setMatchAnalysisCabinetBackVisibleForScreenshot(false);
            // Keep crawfordLabel visible for screenshots
            if (hideInfoCheckbox && hideInfoCheckbox.checked) {
                if (playersInfo) {
                    playersInfo.style.display = 'none';
                }
                if (matchInfo && matchLength > 0) {
                    matchInfo.innerHTML = `<div style="position: relative;"><span style="position: absolute; left: 0;">Матч до ${matchLength}</span><span style="position: absolute; left: 50%; transform: translateX(-50%);">Счет: ${gameRedScore} - ${gameBlackScore}</span></div>`;
                }
                if (gameSelect) gameSelect.style.display = 'none';
            }

            if (hidePipsCheckbox && hidePipsCheckbox.checked) {
                if (blackPips) blackPips.style.display = 'none';
                if (redPips) redPips.style.display = 'none';
            }

            applyScreenshotFontScale();
            captureHintViewerScreenshot().then(canvas => {
                canvas.toBlob(blob => {
                    const formData = new FormData();
                    formData.append('photo', blob);
                    appendMatchAnalysisAudioToFormData(formData);
                    const saveUrl = isWebStandaloneHintViewer()
                        ? '/web/hints/api/save_screenshot'
                        : `/api/save_screenshot?chat_id=${getActiveHintViewerChatId()}`;
                    fetch(saveUrl, {
                        method: 'POST',
                        body: formData
                    }).then(response => {
                        if (response.ok) {
                            showMessageModal('Скриншот сохранен в буфер', 'success');
                        } else if (response.status === 401) {
                            showMessageModal('Нужна авторизация', 'error');
                        } else {
                            showMessageModal('Ошибка при сохранении скриншота', 'error');
                        }
                        restoreControls();
                    }).catch(error => {
                        console.error('Error saving screenshot:', error);
                        showMessageModal('Ошибка при сохранении скриншота', 'error');
                        restoreControls();
                    });
                });
            }).catch(error => {
                console.error('Error creating screenshot:', error);
                showMessageModal('Ошибка при создании скриншота', 'error');
                restoreControls();
            });
        }

        function uploadScreenshots() {
            if (isWebStandaloneHintViewer()) {
                fetch('/web/hints/api/download_screenshots', { method: 'POST' }).then(async response => {
                    if (response.status === 401) {
                        showMessageModal('Нужна авторизация', 'error');
                        return;
                    }
                    if (response.status === 404) {
                        showMessageModal('В архиве нет скриншотов', 'warning');
                        return;
                    }
                    if (!response.ok) {
                        showMessageModal('Ошибка при скачивании архива', 'error');
                        return;
                    }
                    const blob = await response.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'screenshots.zip';
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    URL.revokeObjectURL(url);
                    showMessageModal('Архив со скриншотами скачан', 'success');
                }).catch(error => {
                    console.error('Error downloading screenshots:', error);
                    showMessageModal('Ошибка при скачивании архива', 'error');
                });
                return;
            }
            fetch(`/api/upload_screenshots?chat_id=${getActiveHintViewerChatId()}`, { method: 'POST' }).then(async response => {
                if (response.ok) {
                    showMessageModal('Скриншоты отправлены', 'success');
                } else if (response.status === 402) {
                    const data = await response.json();
                    const msg = (data.detail && typeof data.detail === 'string') ? data.detail : 'Недостаточно баланса для отправки скриншотов. Активируйте промокод или приобретите услугу.';
                    showMessageModal(msg, 'warning');
                } else {
                    showMessageModal('Ошибка при отправке скриншотов', 'error');
                }
            }).catch(error => {
                console.error('Error uploading screenshots:', error);
                showMessageModal('Ошибка при отправке скриншотов', 'error');
            });
        }

        function updateButtons() {
            const prevBtn = document.getElementById('prevBtn');
            const nextBtn = document.getElementById('nextBtn');

            if (dataLoaded) {
                // Найти предыдущий видимый ход
                let prevVisible = current - 1;
                while (prevVisible >= 0 && !data[prevVisible].is_visible) {
                    prevVisible--;
                }
                const hasPrev = prevVisible >= 0 || (availableGames.length > 1 && availableGames.findIndex(game => game.game_number == currentGameNum) > 0);
                prevBtn.disabled = !hasPrev;

                // Найти следующий видимый ход
                let nextVisible = current + 1;
                while (nextVisible < data.length && !data[nextVisible].is_visible) {
                    nextVisible++;
                }
                const hasNext = nextVisible < data.length || (availableGames.length > 1 && availableGames.findIndex(game => game.game_number == currentGameNum) < availableGames.length - 1);
                nextBtn.disabled = !hasNext;
            } else {
                prevBtn.disabled = true;
                nextBtn.disabled = true;
            }
            updateMatchAnalysisAudioUi();
        }

        function takeScreenshot() {
            // Hide controls and game selector before taking screenshot
            const controls = document.getElementById('controls');
            const invertBtn = document.getElementById('invertBtn');
            const screenshotBtn = document.getElementById('screenshotBtn');
            const gameSelect = document.getElementById('gameSelect');
            const hintsButtons = document.querySelector('.hints-buttons');
            const hideInfoCheckbox = document.getElementById('hideInfoCheckbox');
            const playersInfo = document.getElementById('players-info');
            const screenSaveBtn = document.getElementById('screenSaveBtn');
            const screenUploadBtn = document.getElementById('screenUploadBtn');
            const animationControls = document.querySelector('.animation-controls');
            const supportContainer = document.querySelector('.support-container');
            const settingsContainer = document.querySelector('.settings-container');
            const openEditorBtn = document.getElementById('openEditorBtn');
            const adminButtonContainer = document.getElementById('adminButtonContainer');
            const topRow = document.getElementById('top-row');
            const pageTitle = document.querySelector('.container > h1');
            const viewerBelowBoard = document.querySelector('.viewer-below-board');
            const originalAdminButtonContainerDisplay = adminButtonContainer ? adminButtonContainer.style.display : null;
            let animationControlsParent = null;
            let animationControlsNextSibling = null;
            if (animationControls) {
                animationControlsParent = animationControls.parentNode;
                animationControlsNextSibling = animationControls.nextSibling;
                animationControlsParent.removeChild(animationControls);
            }
            const originalControlsDisplay = controls ? controls.style.display : null;
            const originalInvertDisplay = invertBtn ? invertBtn.style.display : null;
            const originalScreenshotDisplay = screenshotBtn ? screenshotBtn.style.display : null;
            const originalGameSelectDisplay = gameSelect ? gameSelect.style.display : null;
            const originalHintsButtonsDisplay = hintsButtons ? hintsButtons.style.display : null;
            const originalHideInfoCheckboxDisplay = hideInfoCheckbox ? hideInfoCheckbox.style.display : null;
            const originalPlayersInfoDisplay = playersInfo ? playersInfo.style.display : null;
            const originalScreenSaveBtnDisplay = screenSaveBtn ? screenSaveBtn.style.display : null;
            const originalScreenUploadBtnDisplay = screenUploadBtn ? screenUploadBtn.style.display : null;
            const originalSupportDisplay = supportContainer ? supportContainer.style.display : null;
            const originalSettingsDisplay = settingsContainer ? settingsContainer.style.display : null;
            const originalOpenEditorBtnDisplay = openEditorBtn ? openEditorBtn.style.display : null;
            const originalTopRowDisplay = topRow ? topRow.style.display : null;
            const originalPageTitleDisplay = pageTitle ? pageTitle.style.display : null;
            const originalViewerBelowDisplay = viewerBelowBoard ? viewerBelowBoard.style.display : null;
            const originalPlayersInfoHTML = playersInfo ? playersInfo.innerHTML : '';
            const matchInfo = document.getElementById('match-info');
            const originalMatchInfoHTML = matchInfo ? matchInfo.innerHTML : null;
            const crawfordLabel = document.getElementById('crawfordLabel');
            const originalCrawfordDisplay = crawfordLabel ? crawfordLabel.style.display : null;

            function restoreControls() {
                if (controls && originalControlsDisplay !== null) controls.style.display = originalControlsDisplay;
                if (invertBtn && originalInvertDisplay !== null) invertBtn.style.display = originalInvertDisplay;
                if (screenshotBtn && originalScreenshotDisplay !== null) screenshotBtn.style.display = originalScreenshotDisplay;
                if (gameSelect && originalGameSelectDisplay !== null) gameSelect.style.display = originalGameSelectDisplay;
                if (hintsButtons && originalHintsButtonsDisplay !== null) hintsButtons.style.display = originalHintsButtonsDisplay;
                if (hideInfoCheckbox && originalHideInfoCheckboxDisplay !== null) hideInfoCheckbox.style.display = originalHideInfoCheckboxDisplay;
                if (screenSaveBtn && originalScreenSaveBtnDisplay !== null) screenSaveBtn.style.display = originalScreenSaveBtnDisplay;
                if (screenUploadBtn && originalScreenUploadBtnDisplay !== null) screenUploadBtn.style.display = originalScreenUploadBtnDisplay;
                if (supportContainer && originalSupportDisplay !== null) supportContainer.style.display = originalSupportDisplay;
                if (animationControls && animationControlsParent) {
                    if (animationControlsNextSibling) {
                        animationControlsParent.insertBefore(animationControls, animationControlsNextSibling);
                    } else {
                        animationControlsParent.appendChild(animationControls);
                    }
                }
                if (playersInfo) {
                    if (originalPlayersInfoDisplay !== null) playersInfo.style.display = originalPlayersInfoDisplay;
                    playersInfo.innerHTML = originalPlayersInfoHTML;
                }
                if (matchInfo && originalMatchInfoHTML !== null) {
                    matchInfo.innerHTML = originalMatchInfoHTML;
                }
                if (crawfordLabel && originalCrawfordDisplay !== null) crawfordLabel.style.display = originalCrawfordDisplay;
                if (settingsContainer && originalSettingsDisplay !== null) settingsContainer.style.display = originalSettingsDisplay;
                if (openEditorBtn && originalOpenEditorBtnDisplay !== null) openEditorBtn.style.display = originalOpenEditorBtnDisplay;
                if (topRow && originalTopRowDisplay !== null) topRow.style.display = originalTopRowDisplay;
                if (pageTitle && originalPageTitleDisplay !== null) pageTitle.style.display = originalPageTitleDisplay;
                if (viewerBelowBoard && originalViewerBelowDisplay !== null) viewerBelowBoard.style.display = originalViewerBelowDisplay;
                restoreAdminButtonContainerAfterScreenshot(adminButtonContainer, originalAdminButtonContainerDisplay);
                setMatchAnalysisCabinetBackVisibleForScreenshot(true);
                removeScreenshotFontScale();
            }

            controls.style.display = 'none';
            invertBtn.style.display = 'none';
            screenshotBtn.style.display = 'none';
            if (gameSelect) gameSelect.style.display = 'none';
            if (hintsButtons) hintsButtons.style.display = 'none';
            if (hideInfoCheckbox) hideInfoCheckbox.style.display = 'none';
            if (screenSaveBtn) screenSaveBtn.style.display = 'none';
            if (screenUploadBtn) screenUploadBtn.style.display = 'none';
            if (supportContainer) supportContainer.style.display = 'none';
            if (settingsContainer) settingsContainer.style.display = 'none';
            if (openEditorBtn) openEditorBtn.style.display = 'none';
            if (adminButtonContainer) adminButtonContainer.style.display = 'none';
            if (topRow) topRow.style.display = 'none';
            if (pageTitle) pageTitle.style.display = 'none';
            if (viewerBelowBoard) viewerBelowBoard.style.display = 'none';
            setMatchAnalysisCabinetBackVisibleForScreenshot(false);
            // Keep crawfordLabel visible for screenshots
            if (hideInfoCheckbox && hideInfoCheckbox.checked) {
                if (playersInfo) {
                    playersInfo.style.display = 'none';
                }
                if (matchInfo && matchLength > 0) {
                    matchInfo.innerHTML = `<div style="position: relative;"><span style="position: absolute; left: 0;">Матч до ${matchLength}</span><span style="position: absolute; left: 50%; transform: translateX(-50%);">Счет: ${gameRedScore} - ${gameBlackScore}</span></div>`;
                }
                if (gameSelect) gameSelect.style.display = 'none';
            }

            applyScreenshotFontScale();
            captureHintViewerScreenshot().then(canvas => {
                restoreControls();
                // Convert canvas to blob
                canvas.toBlob(blob => {
                    // Create a file from the blob
                    const file = new File([blob], screenshotImageFileName(), { type: 'image/png' });

                    // Send the file to Telegram
                    if (window.Telegram && window.Telegram.WebApp) {
                        // Use Telegram WebApp API to send the file
                        const formData = new FormData();
                        formData.append('photo', file);
                        appendMatchAnalysisAudioToFormData(formData);

                        // chat_id текущего зрителя (Telegram WebApp), не создателя анализа
                        const currentChatId = getActiveHintViewerChatId();

                        fetch(`/api/send_screenshot?chat_id=${currentChatId}`, {
                            method: 'POST',
                            body: formData
                        }).then(async response => {
                            if (response.ok) {
                                showMessageModal('Скриншот отправлен', 'success');
                            } else if (response.status === 402) {
                                const data = await response.json();
                                const msg = (data.detail && typeof data.detail === 'string') ? data.detail : 'Недостаточно баланса для сохранения скриншота. Активируйте промокод или приобретите услугу.';
                                showMessageModal(msg, 'warning');
                            } else {
                                const text = await response.text();
                                console.error('Server response:', text);
                                try {
                                    const errorData = JSON.parse(text);
                                    showMessageModal('Ошибка при отправке скриншота: ' + (errorData.detail || text), 'error');
                                } catch (e) {
                                    showMessageModal('Ошибка при отправке скриншота', 'error');
                                }
                            }
                        }).catch(error => {
                            console.error('Error sending screenshot:', error);
                            showMessageModal('Ошибка при отправке скриншота', 'error');
                        });
                    } else {
                        const link = document.createElement('a');
                        link.download = screenshotImageFileName();
                        link.href = canvas.toDataURL();
                        link.click();
                    }
                });
            }).catch(error => {
                console.error('Error creating screenshot:', error);
                showMessageModal('Ошибка при создании скриншота: ' + error.message, 'error');
                restoreControls();
            });
        }

        function openSupportModal() {
            document.getElementById('supportModal').style.display = 'block';
            document.getElementById('supportText').value = '';
        }

        function closeSupportModal() {
            document.getElementById('supportModal').style.display = 'none';
        }

        window.onclick = function (event) {
            const modal = document.getElementById('supportModal');
            if (event.target == modal) {
                closeSupportModal();
            }
        }

        function sendToSupport() {
            const text = document.getElementById('supportText').value;
            if (!text.trim()) {
                showMessageModal('Пожалуйста, введите описание проблемы', 'warning');
                return;
            }

            const sendBtn = document.getElementById('sendSupportBtn');
            const originalBtnText = sendBtn.innerText;
            sendBtn.disabled = true;
            sendBtn.innerText = 'Отправка...';

            // Hide screenshot-related UI elements for capture
            const supportContainer = document.querySelector('.support-container');
            const openEditorBtn = document.getElementById('openEditorBtn');
            const adminButtonContainer = document.getElementById('adminButtonContainer');
            const topRow = document.getElementById('top-row');
            const pageTitle = document.querySelector('.container > h1');
            const viewerBelowBoard = document.querySelector('.viewer-below-board');
            const hintsButtons = document.querySelector('.hints-buttons');
            const originalAdminButtonContainerDisplay = adminButtonContainer ? adminButtonContainer.style.display : null;
            const originalSupportDisplay = supportContainer.style.display;
            const originalOpenEditorBtnDisplay = openEditorBtn ? openEditorBtn.style.display : null;
            const originalTopRowDisplay = topRow ? topRow.style.display : null;
            const originalPageTitleDisplay = pageTitle ? pageTitle.style.display : null;
            const originalViewerBelowDisplay = viewerBelowBoard ? viewerBelowBoard.style.display : null;
            const originalHintsButtonsDisplay = hintsButtons ? hintsButtons.style.display : null;
            supportContainer.style.display = 'none';
            if (openEditorBtn) openEditorBtn.style.display = 'none';
            if (adminButtonContainer) adminButtonContainer.style.display = 'none';
            if (topRow) topRow.style.display = 'none';
            if (pageTitle) pageTitle.style.display = 'none';
            if (viewerBelowBoard) viewerBelowBoard.style.display = 'none';
            if (hintsButtons) hintsButtons.style.display = 'none';

            // Still hide modal as requested previously
            const modal = document.getElementById('supportModal');
            const originalModalDisplay = modal.style.display;
            modal.style.display = 'none';

            applyScreenshotFontScale();
            captureHintViewerScreenshot().then(canvas => {
                removeScreenshotFontScale();
                canvas.toBlob(blob => {
                    const formData = new FormData();
                    formData.append('photo', blob);
                    formData.append('text', text);
                    formData.append('chat_id', getActiveHintViewerChatId());

                    // Create AbortController for timeout
                    const controller = new AbortController();
                    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout

                    fetch('/api/send_to_support', {
                        method: 'POST',
                        body: formData,
                        signal: controller.signal
                    }).then(async response => {
                        clearTimeout(timeoutId);
                        if (response.ok) {
                            showMessageModal('Сообщение отправлено в техподдержку', 'success');
                        } else if (response.status === 429) {
                            const data = await response.json();
                            const waitText = (data.detail && data.detail.wait_text) ? data.detail.wait_text : 'некоторое время';
                            showMessageModal(`Слишком много запросов. Пожалуйста, подождите ${waitText} перед следующей отправкой.`, 'warning');
                            modal.style.display = originalModalDisplay;
                        } else {
                            showMessageModal('Ошибка при отправке сообщения', 'error');
                            modal.style.display = originalModalDisplay;
                        }
                    }).catch(error => {
                        clearTimeout(timeoutId);
                        console.error('Error sending to support:', error);
                        if (error.name === 'AbortError') {
                            showMessageModal('Плохое соединение. Таймаут 10 секунд. Попробуйте позже.', 'warning');
                        } else {
                            showMessageModal('Ошибка при отправке сообщения', 'error');
                        }
                        modal.style.display = originalModalDisplay;
                    }).finally(() => {
                        sendBtn.disabled = false;
                        sendBtn.innerText = originalBtnText;
                        supportContainer.style.display = originalSupportDisplay;
                        if (openEditorBtn && originalOpenEditorBtnDisplay !== null) openEditorBtn.style.display = originalOpenEditorBtnDisplay;
                        if (topRow && originalTopRowDisplay !== null) topRow.style.display = originalTopRowDisplay;
                        if (pageTitle && originalPageTitleDisplay !== null) pageTitle.style.display = originalPageTitleDisplay;
                        if (viewerBelowBoard && originalViewerBelowDisplay !== null) viewerBelowBoard.style.display = originalViewerBelowDisplay;
                        if (hintsButtons && originalHintsButtonsDisplay !== null) hintsButtons.style.display = originalHintsButtonsDisplay;
                        restoreAdminButtonContainerAfterScreenshot(adminButtonContainer, originalAdminButtonContainerDisplay);
                        removeScreenshotFontScale();
                    });
                });
            }).catch(error => {
                console.error('Error creating screenshot:', error);
                showMessageModal('Ошибка при создании скриншота', 'error');
                modal.style.display = originalModalDisplay;
                sendBtn.disabled = false;
                sendBtn.innerText = originalBtnText;
                supportContainer.style.display = originalSupportDisplay;
                if (openEditorBtn && originalOpenEditorBtnDisplay !== null) openEditorBtn.style.display = originalOpenEditorBtnDisplay;
                if (topRow && originalTopRowDisplay !== null) topRow.style.display = originalTopRowDisplay;
                if (pageTitle && originalPageTitleDisplay !== null) pageTitle.style.display = originalPageTitleDisplay;
                if (viewerBelowBoard && originalViewerBelowDisplay !== null) viewerBelowBoard.style.display = originalViewerBelowDisplay;
                if (hintsButtons && originalHintsButtonsDisplay !== null) hintsButtons.style.display = originalHintsButtonsDisplay;
                restoreAdminButtonContainerAfterScreenshot(adminButtonContainer, originalAdminButtonContainerDisplay);
                removeScreenshotFontScale();
            });
        }

        // Settings Modal Functions
        function openSettingsModal() {
            document.getElementById('settingsModal').style.display = 'block';
        }

        function closeSettingsModal() {
            document.getElementById('settingsModal').style.display = 'none';
        }

        function switchTab(tabName) {
            event.preventDefault();
            // Hide all tab contents
            const tabContents = document.querySelectorAll('.tab-content');
            tabContents.forEach(tab => {
                tab.classList.remove('active');
            });

            // Remove active class from all tab buttons
            const tabBtns = document.querySelectorAll('.tab-btn');
            tabBtns.forEach(btn => {
                btn.classList.remove('active');
            });

            // Show the selected tab content
            const selectedTab = document.getElementById(tabName);
            if (selectedTab) {
                selectedTab.classList.add('active');
            }

            // Add active class to the clicked button
            event.target.classList.add('active');
        }

        function saveSettings() {
            // Save settings to localStorage if needed
            showFadingMessage('Настройки сохранены');
            closeSettingsModal();
        }

        // Close settings modal when clicking outside of it
        window.addEventListener('click', function (event) {
            const settingsModal = document.getElementById('settingsModal');
            const supportModal = document.getElementById('supportModal');

            if (event.target === settingsModal) {
                closeSettingsModal();
            }
            if (event.target === supportModal) {
                closeSupportModal();
            }
        });

        // Close modal with Escape key
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                const settingsModal = document.getElementById('settingsModal');
                const supportModal = document.getElementById('supportModal');

                if (settingsModal.style.display === 'block') {
                    closeSettingsModal();
                }
                if (supportModal.style.display === 'block') {
                    closeSupportModal();
                }
            }
        });

        function generateXGID() {
            if (!dataLoaded || !data || current === undefined) {
                console.error('Data not loaded');
                return '';
            }

            let xgid = "";
            
            // Get current positions - используем нужные positions в зависимости от инверсии
            let redPositions, blackPositions;
            if (current === 0) {
                // Начальная позиция
                if (invertColors) {
                    redPositions = { '1': 2, '12': 5, '17': 3, '19': 5, 'bar': 0, 'off': 0 };
                    blackPositions = { '6': 5, '8': 3, '13': 5, '24': 2, 'bar': 0, 'off': 0 };
                } else {
                    redPositions = { '24': 2, '6': 5, '8': 3, '13': 5, 'bar': 0, 'off': 0 };
                    blackPositions = { '1': 2, '19': 5, '17': 3, '12': 5, 'bar': 0, 'off': 0 };
                }
            } else {
                const prevTurn = current - 1;
                // Берем нужные positions в зависимости от инверсии
                if (invertColors) {
                    redPositions = data[prevTurn].inverted_positions['red'];
                    blackPositions = data[prevTurn].inverted_positions['black'];
                } else {
                    redPositions = data[prevTurn].positions['red'];
                    blackPositions = data[prevTurn].positions['black'];
                }
            }

            // Determine upper and lower positions for XGID format
            // In XGID: upper = строчные (a-o), lower = заглавные (A-O)
            // Всегда: red = нижний (lower), black = верхний (upper)
            // Потому что мы уже взяли правильные позиции выше с учетом инверсии
            const upperPositions = blackPositions;
            const lowerPositions = redPositions;
            
            // Bar для верхнего игрока (первый символ в XGID)
            const upperBar = upperPositions.bar || 0;
            if (upperBar === 0) {
                xgid += "-";
            } else if (upperBar <= 15) {
                // Верхний игрок = строчные буквы (a-o)
                xgid += String.fromCharCode(96 + upperBar);
            }
            
            // Positions 1-24
            for (let point = 1; point <= 24; point++) {
                const lowerCount = lowerPositions[point.toString()] || 0;
                const upperCount = upperPositions[point.toString()] || 0;

                if (lowerCount > 0) {
                    if (lowerCount <= 15) {
                        // Нижний = заглавные (A-O)
                        xgid += String.fromCharCode(64 + lowerCount);
                    }
                } else if (upperCount > 0) {
                    if (upperCount <= 15) {
                        // Верхний = строчные (a-o)
                        xgid += String.fromCharCode(96 + upperCount);
                    }
                } else {
                    xgid += "-";
                }
            }
            
            // Bar для нижнего игрока (последний символ перед ':' в XGID)
            const lowerBar = lowerPositions.bar || 0;
            if (lowerBar === 0) {
                xgid += "-";
            } else if (lowerBar <= 15) {
                // Нижний игрок = заглавные буквы (A-O)
                xgid += String.fromCharCode(64 + lowerBar);
            }
            
            xgid += ':';
            
            // Cube exponent (part 1)
            let cubeValue = 0;
            let lastDoubleIndex = -1;
            for (let i = 0; i < doubleTurns.length; i++) {
                if (doubleTurns[i] <= current) {
                    lastDoubleIndex = doubleTurns[i];
                } else {
                    break;
                }
            }
            if (lastDoubleIndex !== -1 && data[lastDoubleIndex]) {
                cubeValue = data[lastDoubleIndex].cube || 0;
            }
            let exponent = 0;
            if (cubeValue > 0) {
                exponent = Math.log2(cubeValue);
            }
            xgid += exponent.toString();
            
            xgid += ':';
            
            // Cube position (part 2): 1 = lower, -1 = upper, 0 = no cube
            let cubePosition = 0;
            if (cubeValue !== 0 && currentCubePlayer) {
                // Red всегда lower (1), Black всегда upper (-1) в XGID
                const isLowerPlayer = (currentCubePlayer === 'Red');
                cubePosition = isLowerPlayer ? 1 : -1;
            }
            xgid += cubePosition.toString();
            
            xgid += ':';
            
            // Turn (part 3): 1 = lower, -1 = upper
            const currentItem = data[current];
            const currentPlayer = currentItem.player || '';
            let turnValue = 0;
            if (currentPlayer) {
                // Red всегда lower (1), Black всегда upper (-1) в XGID
                const isLowerPlayerTurn = (currentPlayer === 'Red');
                turnValue = isLowerPlayerTurn ? 1 : -1;
            }
            xgid += turnValue.toString();
            
            xgid += ':';
            
            // Cube part (part 4): dice or 'D' or '00'
            let cubePart = '00';
            if (currentItem.dice && currentItem.dice.length >= 2 && !['double', 'take', 'win'].includes(currentItem.action)) {
                const [d1, d2] = currentItem.dice;
                cubePart = d1.toString() + d2.toString();
            } else if (cubeValue > 0 && currentCubePlayer) {
                // Cube is shown
                cubePart = 'D';
            }
            xgid += cubePart;
            
            xgid += ':';
            
            // Scores (parts 5-6)
            // Red всегда lower score, Black всегда upper score в XGID
            const lowerScore = matchLength > 0 ? gameRedScore : '0';
            const upperScore = matchLength > 0 ? gameBlackScore : '0';
            xgid += lowerScore.toString();
            xgid += ':';
            xgid += upperScore.toString();
            
            xgid += ':';
            
            // Convention (part 7)
            let conventionPart = '0';
            if (matchLength > 0) {
                // Match: 1 if Crawford, 0 otherwise
                const isCrawford = enable_crawford_game_number !== null && currentGameNum >= enable_crawford_game_number;
                conventionPart = isCrawford ? '1' : '0';
            } else {
                // Money game: jacobi + 2*beaver (default 0)
                conventionPart = '0';
            }
            xgid += conventionPart;
            
            xgid += ':';
            
            // Match length (part 8)
            const matchLengthPart = matchLength > 0 ? matchLength.toString() : '0';
            xgid += matchLengthPart;
            
            xgid += ':';
            
            // Max cube (part 9) - default to 3 (8) if not available
            const maxCubePart = '3'; // Default value, can be extracted from gameInfo if available
            xgid += maxCubePart;
            
            return xgid;
        }
        
        function openPokazEditor() {
            try {
                const xgidString = generateXGID();
                if (!xgidString) {
                    showMessageModal('Не удалось сгенерировать XGID строку', 'error');
                    return;
                }
                
                // Get chat_id and lang from URL or use current viewer
                const urlParams = new URLSearchParams(window.location.search);
                const currentChatId = getActiveHintViewerChatId() || urlParams.get('chat_id') || '';
                const lang = urlParams.get('lang') || '';
                
                // Build URL with XGID, chat_id, lang and invert (relative URL for same app navigation)
                const invertParam = invertColors ? '&invert=1' : '';
                const langParam = (lang === 'ru' || lang === 'en') ? '&lang=' + lang : '';
                const pokazUrl = `/pokaz?xgid=${encodeURIComponent(xgidString)}${currentChatId ? '&chat_id=' + encodeURIComponent(currentChatId) : ''}${langParam}${invertParam}`;
                
                // Navigate in same window/app (works in Telegram WebApp and browser)
                window.location.href = pokazUrl;
            } catch (error) {
                console.error('Error opening pokaz editor:', error);
                showMessageModal('Ошибка при открытии редактора: ' + error.message, 'error');
            }
        }

        async function saveHintViewerScreenshotFontScale() {
            const select = document.getElementById('screenshotFontScaleSelect');
            if (!select) return;

            const fontScalePercent = parseInt(select.value, 10);
            hintViewerScreenshotFontScale = fontScalePercent;

            let initData = '';
            if (window.Telegram && window.Telegram.WebApp) {
                initData = window.Telegram.WebApp.initData;
            }
            if (!initData) {
                showMessageModal('Не удалось сохранить: нет данных Telegram', 'error');
                return;
            }

            try {
                const response = await fetch('/api/hint_viewer_screenshot_font_scale', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ initData, fontScalePercent })
                });
                if (response.ok) {
                    const data = await response.json();
                    hintViewerScreenshotFontScale = data.fontScalePercent;
                    select.value = String(hintViewerScreenshotFontScale);
                    showMessageModal('Масштаб шрифта для скриншота сохранён', 'success');
                } else {
                    showMessageModal('Не удалось сохранить масштаб шрифта', 'error');
                }
            } catch (error) {
                console.error('Error saving screenshot font scale:', error);
                showMessageModal('Не удалось сохранить масштаб шрифта', 'error');
            }
        }

        // Check admin status and show/hide admin button
        async function checkAdminStatus() {
            if (isHintViewerAdminFromMeta()) {
                applyHintViewerAdminUi();
                return;
            }
            try {
                // Get Telegram WebApp init data
                let initData = '';
                if (window.Telegram && window.Telegram.WebApp) {
                    initData = window.Telegram.WebApp.initData;
                }
                
                if (!initData) {
                    console.log('No Telegram WebApp init data found');
                    return;
                }
                
                const response = await fetch('/api/check_admin', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        initData: initData
                    })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    if (data.is_admin) {
                        applyMatchAnalysisAdminFlag(true);
                        if (window.hintViewerIsAdmin) {
                            document.getElementById('adminButtonContainer').style.display = 'block';
                            const fontScaleSelect = document.getElementById('screenshotFontScaleSelect');
                            if (fontScaleSelect) {
                                fontScaleSelect.value = String(hintViewerScreenshotFontScale);
                            }
                            if (matchAnalysisMode) {
                                const pipBtn = document.getElementById('openPipCountCardEditorBtn');
                                const cardBtn = document.getElementById('openCardEditorBtn');
                                if (pipBtn) pipBtn.style.display = 'none';
                                if (cardBtn) cardBtn.style.display = 'none';
                            }
                        }
                        updateMatchAnalysisChromeUi();
                        console.log('Admin access granted for user:', data.user_id);
                    }
                } else {
                    console.log('Admin check failed:', response.status);
                }
            } catch (error) {
                console.error('Error checking admin status:', error);
            }
        }

        // Check admin status when page loads
        document.addEventListener('DOMContentLoaded', function() {
            if (matchAnalysisMode) {
                updateMatchAnalysisChromeUi();
            }
            checkAdminStatus();
        });

        /**
         * Снимок состояния доски и кадра для сохранения вместе с редактором (JSON / localStorage).
         * Вызывается из content_editor.js при «Сохранить кадр».
         */
        window.getHintViewerBoardSnapshot = function() {
            try {
                const gid = typeof gameId !== 'undefined' ? gameId : 'default';
                if (typeof dataLoaded === 'undefined' || !dataLoaded || !data || current === undefined) {
                    return {
                        frameId: `${gid}_g_na_f_na`,
                        gameId: gid,
                        currentGameNum: typeof currentGameNum !== 'undefined' ? currentGameNum : null,
                        frameIndex: null,
                        error: 'no_game_data'
                    };
                }
                const gNum = currentGameNum != null ? currentGameNum : 'na';
                const idx = current;
                const frameId = `${gid}_g${gNum}_f${idx}`;
                const xgid = typeof generateXGID === 'function' ? generateXGID() : '';

                let positions = null;
                if (idx > 0 && data[idx - 1]) {
                    const prev = data[idx - 1];
                    if (invertColors && prev.inverted_positions) {
                        positions = JSON.parse(JSON.stringify(prev.inverted_positions));
                    } else if (prev.positions) {
                        positions = JSON.parse(JSON.stringify(prev.positions));
                    }
                }

                const row = data[idx] || null;

                /** Как на доске в render(): куб до первого double, на стороне при double, на баре после take. */
                let cubeVisual = null;
                if (row) {
                    if (row.action === 'win') {
                        cubeVisual = { mode: 'center', value: 64 };
                    } else if (firstDoubleIndex >= 0 && idx < firstDoubleIndex) {
                        cubeVisual = { mode: 'center', value: 64 };
                    } else if (doubleTurns && doubleTurns.indexOf(idx) !== -1) {
                        const v = row.cube;
                        if ([2, 4, 8, 16, 32, 64].indexOf(v) !== -1) {
                            cubeVisual = { mode: 'side', value: v, player: row.player };
                        } else {
                            cubeVisual = { mode: 'center', value: 64 };
                        }
                    } else {
                        let lastDoubleIndex = -1;
                        if (doubleTurns) {
                            for (let i = 0; i < doubleTurns.length; i++) {
                                if (doubleTurns[i] <= idx) {
                                    lastDoubleIndex = doubleTurns[i];
                                }
                            }
                        }
                        if (lastDoubleIndex === -1) {
                            if (firstDoubleIndex < 0) {
                                cubeVisual = { mode: 'center', value: 64 };
                            }
                        } else if (
                            idx > firstDoubleIndex &&
                            (!doubleTurns || doubleTurns.indexOf(idx) === -1) &&
                            row.action !== 'win'
                        ) {
                            const dr = data[lastDoubleIndex];
                            if (dr && dr.cube && dr.player) {
                                cubeVisual = { mode: 'bar', value: dr.cube, player: dr.player };
                            }
                        }
                    }
                }

                return {
                    frameId,
                    gameId: gid,
                    currentGameNum: currentGameNum != null ? currentGameNum : null,
                    frameIndex: idx,
                    invertColors: !!invertColors,
                    xgid,
                    positions,
                    cubeVisual,
                    scores: typeof matchLength !== 'undefined' ? {
                        matchLength,
                        gameRedScore: typeof gameRedScore !== 'undefined' ? gameRedScore : null,
                        gameBlackScore: typeof gameBlackScore !== 'undefined' ? gameBlackScore : null
                    } : null,
                    turn: row ? {
                        turn: row.turn,
                        action: row.action,
                        player: row.player,
                        player_name: row.player_name,
                        dice: row.dice,
                        cube: row.cube,
                        gnu_move: row.gnu_move
                    } : null
                };
            } catch (e) {
                console.error('getHintViewerBoardSnapshot:', e);
                return { error: String(e.message || e) };
            }
        };

        /**
         * Текущая строка кадра (как при openCardEditor): таблица ходов / cube_hints и т.д.
         * После «Сохранить кадр» редактор снова подтягивает это из страницы.
         */
        window.getHintViewerCurrentCardData = function() {
            try {
                if (typeof dataLoaded === 'undefined' || !dataLoaded || !data || current === undefined) {
                    return null;
                }
                return data.length > 0 ? data[current] : null;
            } catch (e) {
                console.error('getHintViewerCurrentCardData:', e);
                return null;
            }
        };

        async function openPipCountCardEditor() {
            let contentEditor;
            try {
                contentEditor = await ensureContentEditor();
            } catch (e) {
                console.error('ensureContentEditor:', e);
                return;
            }
            if (!contentEditor) {
                console.error('ContentEditor не инициализирован');
                return;
            }
            try {
                if (typeof contentEditor.openModalWithBestDuplicateCheck === 'function') {
                    await contentEditor.openModalWithBestDuplicateCheck(null, {
                        duplicateMode: 'board_xgid',
                        pipCountImport: true,
                    });
                } else if (typeof contentEditor.openModalWithData === 'function') {
                    contentEditor.openModalWithData(null, { pipCountImport: true });
                } else {
                    throw new Error('ContentEditor не содержит методов открытия редактора');
                }
                if (typeof contentEditor.setupPipCountImportSession === 'function') {
                    await contentEditor.setupPipCountImportSession({ skipLoadTools: true });
                }
            } catch (e) {
                console.error('openPipCountCardEditor:', e);
            }
        }

        // ---- Анализ матча: сохранение + аудио на ходе ----
        let matchAnalysisAudioEl = null;
        let matchAnalysisMediaRecorder = null;
        let matchAnalysisRecordChunks = [];
        let matchAnalysisAudioUiMoveKey = null;
        let matchAnalysisAudioPlayGen = 0;
        const MATCH_ANALYSIS_AUTOPLAY_LS_KEY = 'matchAnalysisAudioAutoplay';

        function buildMatchAnalysisMediaUrl(s3Key) {
            return '/api/match_analysis/media?key=' + encodeURIComponent(s3Key);
        }

        function getCurrentMoveAudioMeta() {
            if (!dataLoaded || !data || current === undefined || !data[current]) {
                return { moveIndex: null, audioS3Key: null, audioName: null };
            }
            const row = data[current];
            return {
                moveIndex: typeof row._moveIndex === 'number' ? row._moveIndex : null,
                audioS3Key: row.audioS3Key || null,
                audioName: row.audioName || null,
            };
        }

        function getMatchAnalysisAudioMoveKey() {
            const meta = getCurrentMoveAudioMeta();
            return String(currentGameNum) + ':' + String(current) + ':' + String(meta.moveIndex);
        }

        function isMatchAnalysisAutoplayEnabled() {
            const chk = document.getElementById('matchAnalysisAudioAutoplayChk');
            return !!(chk && chk.checked);
        }

        function onMatchAnalysisAutoplayChange() {
            const chk = document.getElementById('matchAnalysisAudioAutoplayChk');
            if (!chk) return;
            try {
                localStorage.setItem(MATCH_ANALYSIS_AUTOPLAY_LS_KEY, chk.checked ? '1' : '0');
            } catch (e) { /* ignore */ }
            if (chk.checked) {
                const meta = getCurrentMoveAudioMeta();
                if (meta.audioS3Key) {
                    playMatchAnalysisAudioForCurrentMove();
                }
            }
        }

        function syncMoveAudioInDoc(gameNumber, moveIndex, audioS3Key, audioName) {
            if (!matchAnalysisDoc || !Array.isArray(matchAnalysisDoc.games)) return;
            const g = matchAnalysisDoc.games.find(
                (x) => String(x.game_number) === String(gameNumber)
            );
            if (!g || !Array.isArray(g.moves) || moveIndex == null) return;
            if (!g.moves[moveIndex]) return;
            g.moves[moveIndex].audioS3Key = audioS3Key;
            g.moves[moveIndex].audioName = audioName;
            if (data && data[current] && data[current]._moveIndex === moveIndex) {
                data[current].audioS3Key = audioS3Key;
                data[current].audioName = audioName;
            }
        }

        function setMatchAnalysisPlayButtonState(isPlaying) {
            const playBtn = document.getElementById('matchAnalysisAudioPlayBtn');
            if (!playBtn) return;
            playBtn.classList.toggle('is-playing', !!isPlaying);
            playBtn.title = isPlaying ? 'Пауза' : 'Слушать';
            playBtn.innerHTML = isPlaying
                ? '<i class="fa fa-pause" aria-hidden="true"></i>'
                : '<i class="fa fa-play" aria-hidden="true"></i>';
        }

        function setMatchAnalysisRecordButtonState(isRecording) {
            const recBtn = document.getElementById('matchAnalysisAudioRecordBtn');
            if (!recBtn) return;
            recBtn.classList.toggle('is-recording', !!isRecording);
            recBtn.title = isRecording ? 'Остановить запись' : 'Записать';
            recBtn.innerHTML = isRecording
                ? '<i class="fa fa-stop" aria-hidden="true"></i>'
                : '<i class="fa fa-microphone" aria-hidden="true"></i>';
        }

        function stopMatchAnalysisAudioPlayback() {
            matchAnalysisAudioPlayGen += 1;
            const el = matchAnalysisAudioEl;
            matchAnalysisAudioEl = null;
            if (el) {
                try {
                    el.onended = null;
                    el.onerror = null;
                    el.pause();
                } catch (e) { /* ignore */ }
                try {
                    el.removeAttribute('src');
                    el.load();
                } catch (e) { /* ignore */ }
            }
            setMatchAnalysisPlayButtonState(false);
        }

        function isBenignAudioPlayError(err) {
            const name = err && err.name ? String(err.name) : '';
            // AbortError: play() interrupted by pause()/new play — ожидаемо при смене хода.
            // NotAllowedError: автоплей без жеста пользователя — не показываем как сбой.
            return name === 'AbortError' || name === 'NotAllowedError';
        }

        function playMatchAnalysisAudioForCurrentMove() {
            const meta = getCurrentMoveAudioMeta();
            if (!meta.audioS3Key) {
                stopMatchAnalysisAudioPlayback();
                return;
            }
            stopMatchAnalysisAudioPlayback();
            const playGen = matchAnalysisAudioPlayGen;
            const el = new Audio(buildMatchAnalysisMediaUrl(meta.audioS3Key));
            matchAnalysisAudioEl = el;
            el.onended = function () {
                if (playGen !== matchAnalysisAudioPlayGen || matchAnalysisAudioEl !== el) return;
                setMatchAnalysisPlayButtonState(false);
            };
            const playPromise = el.play();
            if (!playPromise || typeof playPromise.then !== 'function') {
                if (playGen === matchAnalysisAudioPlayGen && matchAnalysisAudioEl === el) {
                    setMatchAnalysisPlayButtonState(true);
                }
                return;
            }
            playPromise
                .then(function () {
                    if (playGen !== matchAnalysisAudioPlayGen || matchAnalysisAudioEl !== el) return;
                    setMatchAnalysisPlayButtonState(true);
                })
                .catch(function (e) {
                    if (playGen !== matchAnalysisAudioPlayGen || matchAnalysisAudioEl !== el) return;
                    setMatchAnalysisPlayButtonState(false);
                    if (isBenignAudioPlayError(e)) return;
                    console.error(e);
                    showMessageModal('Не удалось воспроизвести аудио', 'error');
                });
        }

        function isMatchAnalysisHeaderActionsVisible() {
            return !!matchAnalysisMode;
        }

        function updateMatchAnalysisChromeUi() {
            const headerEl = document.querySelector('.board-block .header');
            const show = isMatchAnalysisHeaderActionsVisible();
            if (headerEl) {
                headerEl.classList.toggle('has-ma-header-actions', show);
            }
            updateMatchAnalysisAudioUi();
        }

        function setMatchAnalysisCabinetBackVisibleForScreenshot(visible) {
            const headerEl = document.querySelector('.board-block .header');
            if (headerEl && isMatchAnalysisHeaderActionsVisible()) {
                headerEl.classList.toggle('has-ma-header-actions', !!visible);
            }
        }

        (function initMatchAnalysisStatusUi() {
            if (!matchAnalysisMode) return;
            let cachedUserStatus = 'VIEWED';
            let statusBusy = false;

            function isFavoriteStatus(st) {
                return String(st || '').toUpperCase() === 'FAVORITE';
            }

            function applyFavoriteButtonUi(isFavorite) {
                const statusBtn = document.getElementById('matchAnalysisStatusBtn');
                if (!statusBtn) return;
                const on = !!isFavorite;
                statusBtn.classList.toggle('is-favorite', on);
                statusBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
                statusBtn.title = on ? 'Убрать из избранного' : 'В избранное';
                statusBtn.setAttribute(
                    'aria-label',
                    on ? 'Убрать из избранного' : 'Добавить в избранное'
                );
                statusBtn.innerHTML = on
                    ? '<i class="fa fa-star" aria-hidden="true"></i>'
                    : '<i class="fa fa-star-o" aria-hidden="true"></i>';
            }

            function setCachedStatus(st) {
                cachedUserStatus = String(st || 'VIEWED').toUpperCase();
                applyFavoriteButtonUi(isFavoriteStatus(cachedUserStatus));
            }

            function toggleFavorite() {
                if (!matchAnalysisId || statusBusy) return;
                const nextStatus = isFavoriteStatus(cachedUserStatus) ? 'VIEWED' : 'FAVORITE';
                const prevStatus = cachedUserStatus;
                statusBusy = true;
                const statusBtn = document.getElementById('matchAnalysisStatusBtn');
                if (statusBtn) statusBtn.classList.add('is-busy');
                // Optimistic UI
                setCachedStatus(nextStatus);

                fetch('/api/match_analysis/set_status', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(Object.assign(
                        {
                            id: matchAnalysisId,
                            status: nextStatus,
                        },
                        getMatchAnalysisAuthFields() || { init_data: getTelegramInitData() }
                    )),
                }).then(function (r) {
                    if (!r.ok) {
                        return r.json().then(function (j) {
                            throw new Error((j && j.detail) || 'Ошибка сохранения статуса');
                        }).catch(function (err) {
                            if (err && err.message) throw err;
                            throw new Error('Ошибка сохранения статуса');
                        });
                    }
                    return r.json();
                }).then(function (data) {
                    if (data && data.status) setCachedStatus(data.status);
                }).catch(function () {
                    setCachedStatus(prevStatus);
                    if (typeof showMessageModal === 'function') {
                        showMessageModal('Не удалось обновить избранное', 'error');
                    }
                }).finally(function () {
                    statusBusy = false;
                    if (statusBtn) statusBtn.classList.remove('is-busy');
                });
            }

            window.__setMatchAnalysisCachedUserStatus = function (st) {
                setCachedStatus(st);
            };

            applyFavoriteButtonUi(false);
            const statusBtn = document.getElementById('matchAnalysisStatusBtn');
            if (statusBtn) {
                statusBtn.addEventListener('click', toggleFavorite);
            }
        })();

        function updateMatchAnalysisAudioUi() {
            const panel = document.getElementById('matchAnalysisAudioPanel');
            if (!panel) return;
            if (!matchAnalysisMode) {
                panel.style.display = 'none';
                stopMatchAnalysisAudioPlayback();
                matchAnalysisAudioUiMoveKey = null;
                return;
            }
            panel.style.display = 'flex';
            const canEditAudio = !!window.hintViewerIsAdmin;
            const meta = getCurrentMoveAudioMeta();
            const statusEl = document.getElementById('matchAnalysisAudioStatus');
            const playBtn = document.getElementById('matchAnalysisAudioPlayBtn');
            const attachBtn = document.getElementById('matchAnalysisAudioAttachBtn');
            const recordBtn = document.getElementById('matchAnalysisAudioRecordBtn');
            const deleteBtn = document.getElementById('matchAnalysisAudioDeleteBtn');
            const autoplayLabel = document.getElementById('matchAnalysisAudioAutoplayLabel');
            const autoplayChk = document.getElementById('matchAnalysisAudioAutoplayChk');
            const audioLabel = meta.audioS3Key
                ? (meta.audioName || meta.audioS3Key.split('/').pop() || 'аудио')
                : '';

            panel.classList.toggle('has-audio', !!meta.audioS3Key);
            panel.classList.toggle('is-user-mode', !canEditAudio);

            if (canEditAudio) {
                panel.title = meta.audioS3Key ? ('Аудио: ' + audioLabel) : 'Аудио не прикреплено';
                if (statusEl) {
                    statusEl.style.display = '';
                    statusEl.textContent = meta.audioS3Key ? audioLabel : 'нет аудио';
                    statusEl.title = panel.title;
                }
                if (attachBtn) attachBtn.style.display = '';
                if (recordBtn) recordBtn.style.display = '';
                if (deleteBtn) {
                    deleteBtn.style.display = '';
                    deleteBtn.disabled = !meta.audioS3Key;
                }
                if (autoplayLabel) autoplayLabel.style.display = 'none';
            } else {
                panel.title = meta.audioS3Key ? 'Есть аудио на ходе' : 'Аудио не прикреплено';
                if (statusEl) {
                    statusEl.style.display = 'none';
                    statusEl.textContent = '';
                    statusEl.title = '';
                }
                if (attachBtn) attachBtn.style.display = 'none';
                if (recordBtn) recordBtn.style.display = 'none';
                if (deleteBtn) deleteBtn.style.display = 'none';
                if (autoplayLabel) autoplayLabel.style.display = 'inline-flex';
                if (autoplayChk && autoplayChk.dataset.synced !== '1') {
                    try {
                        autoplayChk.checked = localStorage.getItem(MATCH_ANALYSIS_AUTOPLAY_LS_KEY) === '1';
                    } catch (e) {
                        autoplayChk.checked = false;
                    }
                    autoplayChk.dataset.synced = '1';
                }
            }

            if (playBtn) playBtn.disabled = !meta.audioS3Key;

            const moveKey = getMatchAnalysisAudioMoveKey();
            const frameChanged = moveKey !== matchAnalysisAudioUiMoveKey;
            matchAnalysisAudioUiMoveKey = moveKey;

            if (frameChanged) {
                stopMatchAnalysisAudioPlayback();
                if (!canEditAudio && isMatchAnalysisAutoplayEnabled() && meta.audioS3Key) {
                    playMatchAnalysisAudioForCurrentMove();
                }
            }
        }

        function toggleMatchAnalysisAudioPlay() {
            const meta = getCurrentMoveAudioMeta();
            if (!meta.audioS3Key) return;
            if (matchAnalysisAudioEl && !matchAnalysisAudioEl.paused) {
                stopMatchAnalysisAudioPlayback();
                return;
            }
            playMatchAnalysisAudioForCurrentMove();
        }

        function matchAnalysisPickAudioFile() {
            const input = document.getElementById('matchAnalysisAudioFileInput');
            if (input) input.click();
        }

        async function matchAnalysisOnAudioFileSelected(ev) {
            const file = ev.target && ev.target.files && ev.target.files[0];
            if (ev.target) ev.target.value = '';
            if (!file) return;
            await uploadMatchAnalysisAudioBlob(file, file.name || 'audio.webm');
        }

        function withFetchRetry(options) {
            const opts = options || {};
            const retries = opts.retries == null ? 3 : opts.retries;
            const delayMs = opts.delayMs == null ? 700 : opts.delayMs;
            const factor = opts.factor == null ? 2 : opts.factor;
            const shouldRetry = opts.shouldRetry || function (err) {
                if (!err) return false;
                if (err.name === 'TypeError') return true;
                const msg = String(err.message || err).toLowerCase();
                return (
                    msg.includes('failed to fetch') ||
                    msg.includes('networkerror') ||
                    msg.includes('network request failed') ||
                    msg.includes('load failed')
                );
            };

            return function decorate(fn) {
                const wrapped = async function (...args) {
                    let attempt = 0;
                    for (;;) {
                        try {
                            return await fn.apply(this, args);
                        } catch (err) {
                            if (attempt >= retries || !shouldRetry(err)) {
                                throw err;
                            }
                            const wait = Math.round(delayMs * Math.pow(factor, attempt));
                            attempt += 1;
                            console.warn(
                                `[audio upload retry ${attempt}/${retries}] ${err && err.message ? err.message : err}; wait ${wait}ms`
                            );
                            await new Promise((resolve) => setTimeout(resolve, wait));
                        }
                    }
                };
                Object.defineProperty(wrapped, 'name', {
                    value: fn.name ? `withFetchRetry(${fn.name})` : 'withFetchRetry',
                });
                return wrapped;
            };
        }

        const postMatchAnalysisAudioUpload = withFetchRetry({ retries: 3, delayMs: 700, factor: 2 })(
            async function postMatchAnalysisAudioUpload(blob, filename, meta, durationSec) {
                const fd = new FormData();
                if (!appendMatchAnalysisAuthToFormData(fd)) {
                    const err = new Error('Нет данных авторизации');
                    err.status = 401;
                    throw err;
                }
                fd.append('match_analysis_id', String(matchAnalysisId));
                fd.append('game_number', String(currentGameNum));
                fd.append('move_index', String(meta.moveIndex));
                fd.append('file', blob, filename);
                if (durationSec != null && Number.isFinite(durationSec) && durationSec > 0) {
                    fd.append('duration_sec', String(durationSec));
                }
                const resp = await fetch('/api/match_analysis/audio/upload', {
                    method: 'POST',
                    body: fd,
                    credentials: 'same-origin',
                });
                const payload = await resp.json().catch(() => ({}));
                if (!resp.ok) {
                    const detail = payload.detail || ('HTTP ' + resp.status);
                    const err = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
                    err.status = resp.status;
                    throw err;
                }
                return payload;
            }
        );

        function measureMatchAnalysisBlobDurationSec(blob, preferredDurationSec) {
            const preferred = Number(preferredDurationSec);
            if (Number.isFinite(preferred) && preferred > 0) {
                return Promise.resolve(preferred);
            }
            if (!blob) return Promise.resolve(null);

            const decodeAb = (arrayBuffer) => new Promise((resolve) => {
                const Ctx = window.AudioContext || window.webkitAudioContext;
                if (!Ctx || !arrayBuffer) {
                    resolve(null);
                    return;
                }
                let ctx = null;
                const finish = (value) => {
                    try {
                        if (ctx && typeof ctx.close === 'function') ctx.close();
                    } catch (e) { /* ignore */ }
                    resolve(value);
                };
                try {
                    ctx = new Ctx();
                } catch (e) {
                    resolve(null);
                    return;
                }
                const copy = arrayBuffer.slice(0);
                let handled = false;
                const onOk = (buf) => {
                    if (handled) return;
                    handled = true;
                    const d = buf && Number(buf.duration);
                    finish(Number.isFinite(d) && d > 0 ? d : null);
                };
                const onErr = () => {
                    if (handled) return;
                    handled = true;
                    finish(null);
                };
                try {
                    const maybePromise = ctx.decodeAudioData(copy, onOk, onErr);
                    if (maybePromise && typeof maybePromise.then === 'function') {
                        maybePromise.then(onOk).catch(onErr);
                    }
                } catch (e) {
                    onErr();
                }
            });

            return blob.arrayBuffer()
                .then((ab) => decodeAb(ab))
                .then((decoded) => {
                    if (decoded != null) return decoded;
                    return new Promise((resolve) => {
                        let url = '';
                        try {
                            url = URL.createObjectURL(blob);
                        } catch (e) {
                            resolve(null);
                            return;
                        }
                        const audio = new Audio();
                        let done = false;
                        const finish = (value) => {
                            if (done) return;
                            done = true;
                            try { URL.revokeObjectURL(url); } catch (e2) { /* ignore */ }
                            resolve(value);
                        };
                        audio.preload = 'metadata';
                        audio.onloadedmetadata = () => {
                            const d = Number(audio.duration);
                            if (Number.isFinite(d) && d > 0 && d !== Infinity) finish(d);
                            else finish(null);
                        };
                        audio.onerror = () => finish(null);
                        setTimeout(() => finish(null), 8000);
                        audio.src = url;
                    });
                })
                .catch(() => null);
        }

        async function uploadMatchAnalysisAudioBlob(blob, filename, preferredDurationSec) {
            const meta = getCurrentMoveAudioMeta();
            if (!matchAnalysisId || meta.moveIndex == null) {
                showMessageModal('Не выбран ход для аудио', 'error');
                return;
            }
            if (getMatchAnalysisAuthFields() === null) {
                showMessageModal('Нет данных авторизации', 'error');
                return;
            }
            try {
                const durationSec = await measureMatchAnalysisBlobDurationSec(
                    blob,
                    preferredDurationSec
                );
                const payload = await postMatchAnalysisAudioUpload(
                    blob,
                    filename,
                    meta,
                    durationSec
                );
                syncMoveAudioInDoc(
                    currentGameNum,
                    meta.moveIndex,
                    payload.s3_key,
                    payload.audio_name
                );
                if (payload.duration_sec != null && data && data[current]) {
                    data[current].audioDurationSec = payload.duration_sec;
                }
                updateMatchAnalysisAudioUi();
                showMessageModal('Аудио прикреплено', 'info');
            } catch (e) {
                console.error(e);
                showMessageModal('Ошибка загрузки аудио: ' + (e.message || e), 'error');
            }
        }

        async function deleteMatchAnalysisAudio() {
            const meta = getCurrentMoveAudioMeta();
            if (!matchAnalysisId || meta.moveIndex == null || !meta.audioS3Key) return;
            const auth = getMatchAnalysisAuthFields();
            if (auth === null) {
                showMessageModal('Нет данных авторизации', 'error');
                return;
            }
            try {
                const resp = await fetch('/api/match_analysis/audio/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify(Object.assign({
                        id: matchAnalysisId,
                        game_number: currentGameNum,
                        move_index: meta.moveIndex,
                        delete_s3: true,
                    }, auth)),
                });
                const payload = await resp.json().catch(() => ({}));
                if (!resp.ok) {
                    throw new Error(payload.detail || ('HTTP ' + resp.status));
                }
                syncMoveAudioInDoc(currentGameNum, meta.moveIndex, null, null);
                updateMatchAnalysisAudioUi();
            } catch (e) {
                console.error(e);
                showMessageModal('Ошибка удаления аудио: ' + (e.message || e), 'error');
            }
        }

        let matchAnalysisRecordStartedAt = null;

        async function startMatchAnalysisRecording() {
            if (matchAnalysisMediaRecorder && matchAnalysisMediaRecorder.state === 'recording') {
                matchAnalysisMediaRecorder.stop();
                return;
            }
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                matchAnalysisRecordChunks = [];
                matchAnalysisRecordStartedAt = Date.now();
                const mimeCandidates = [
                    'audio/ogg;codecs=opus',
                    'audio/ogg',
                    'audio/webm;codecs=opus',
                    'audio/webm',
                ];
                const mime = mimeCandidates.find((t) => MediaRecorder.isTypeSupported(t)) || '';
                matchAnalysisMediaRecorder = mime
                    ? new MediaRecorder(stream, { mimeType: mime })
                    : new MediaRecorder(stream);
                matchAnalysisMediaRecorder.ondataavailable = (e) => {
                    if (e.data && e.data.size) matchAnalysisRecordChunks.push(e.data);
                };
                matchAnalysisMediaRecorder.onstop = async () => {
                    stream.getTracks().forEach((t) => t.stop());
                    const wallSec = matchAnalysisRecordStartedAt
                        ? (Date.now() - matchAnalysisRecordStartedAt) / 1000
                        : null;
                    matchAnalysisRecordStartedAt = null;
                    const type = matchAnalysisMediaRecorder.mimeType || 'audio/webm';
                    const blob = new Blob(matchAnalysisRecordChunks, { type });
                    const ext = type.includes('ogg') ? 'ogg' : type.includes('mp4') ? 'mp4' : 'webm';
                    setMatchAnalysisRecordButtonState(false);
                    await uploadMatchAnalysisAudioBlob(
                        blob,
                        'voice_' + Date.now() + '.' + ext,
                        wallSec
                    );
                    matchAnalysisMediaRecorder = null;
                };
                matchAnalysisMediaRecorder.start();
                setMatchAnalysisRecordButtonState(true);
            } catch (e) {
                console.error(e);
                matchAnalysisRecordStartedAt = null;
                setMatchAnalysisRecordButtonState(false);
                showMessageModal('Не удалось начать запись: ' + (e.message || e), 'error');
            }
        }

        function openMatchAnalysisCabinet() {
            var meta = document.querySelector('meta[name="web-standalone-mode"]');
            var web = meta && meta.getAttribute('content') === '1';
            window.location.href = web ? '/web/match-analysis' : '/match-analysis-cabinet';
        }

        // Функция открытия редактора контента
        async function openCardEditor() {
            let contentEditor;
            try {
                contentEditor = await ensureContentEditor();
            } catch (e) {
                console.error('ensureContentEditor:', e);
                console.error('ContentEditor не инициализирован');
                return;
            }
            if (!contentEditor) {
                console.error('ContentEditor не инициализирован');
                return;
            }
            {
                const cardData = typeof window.getHintViewerCurrentCardData === 'function'
                    ? window.getHintViewerCurrentCardData()
                    : (data.length > 0 ? data[current] : null);
                if (typeof contentEditor.openModalWithBestDuplicateCheck === 'function') {
                    await contentEditor.openModalWithBestDuplicateCheck(cardData, { duplicateMode: 'source' });
                } else if (typeof contentEditor.openModalWithDuplicateSourceCheck === 'function') {
                    await contentEditor.openModalWithDuplicateSourceCheck(cardData);
                } else if (typeof contentEditor.openModalWithDuplicateBoardXgidCheck === 'function') {
                    await contentEditor.openModalWithDuplicateBoardXgidCheck(cardData);
                } else if (typeof contentEditor.openModalWithData === 'function') {
                    contentEditor.openModalWithData(cardData);
                } else {
                    throw new Error('ContentEditor не содержит методов открытия редактора');
                }
            }
        }

        // Функция для обновления контента кнопки с cache-busting
        function updateButtonContent() {
            const button = document.getElementById('openCardEditorBtn');
            if (button) {
                // Force refresh by adding timestamp to button content
                const timestamp = Date.now();
                button.setAttribute('data-refresh', timestamp);
                // В режиме анализа матча редактор карточек скрыт — не возвращаем кнопку.
                if (matchAnalysisMode) {
                    button.style.display = 'none';
                    return;
                }
                // Trigger a reflow to ensure the update is applied
                button.style.display = 'none';
                button.offsetHeight; // Force reflow
                button.style.display = '';
            }
        }

        // Обновляем контент кнопки при загрузке страницы
        document.addEventListener('DOMContentLoaded', function() {
            updateButtonContent();
            
            // Также обновляем при каждом показе контейнера админа
            const adminContainer = document.getElementById('adminButtonContainer');
            if (adminContainer) {
                const observer = new MutationObserver(function(mutations) {
                    mutations.forEach(function(mutation) {
                        if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
                            if (adminContainer.style.display !== 'none') {
                                updateButtonContent();
                            }
                        }
                    });
                });
                observer.observe(adminContainer, { attributes: true });
            }
        });

    
window.takeScreenshot = takeScreenshot;
window.saveScreenshot = saveScreenshot;
window.uploadScreenshots = uploadScreenshots;
window.prevTurn = prevTurn;
window.nextTurn = nextTurn;
window.toggleInvert = toggleInvert;
window.openSettingsModal = openSettingsModal;
window.closeSettingsModal = closeSettingsModal;
window.switchTab = switchTab;
window.openSupportModal = openSupportModal;
window.closeSupportModal = closeSupportModal;
window.sendToSupport = sendToSupport;
window.openPokazEditor = openPokazEditor;
window.openPipCountCardEditor = openPipCountCardEditor;
window.openCardEditor = openCardEditor;
window.openMatchAnalysisCabinet = openMatchAnalysisCabinet;
window.toggleMatchAnalysisAudioPlay = toggleMatchAnalysisAudioPlay;
window.matchAnalysisPickAudioFile = matchAnalysisPickAudioFile;
window.startMatchAnalysisRecording = startMatchAnalysisRecording;
window.deleteMatchAnalysisAudio = deleteMatchAnalysisAudio;
window.onMatchAnalysisAutoplayChange = onMatchAnalysisAutoplayChange;
