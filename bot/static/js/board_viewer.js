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

function isBoardViewerAdminFromMeta() {
    const meta = document.querySelector('meta[name="board-viewer-is-admin"]');
    return !!(meta && meta.getAttribute('content') === '1');
}

function applyBoardViewerAdminUi() {
    const adminContainer = document.getElementById('adminButtonContainer');
    if (adminContainer) adminContainer.style.display = 'block';
    const fontScaleSelect = document.getElementById('screenshotFontScaleSelect');
    if (fontScaleSelect && typeof boardViewerScreenshotFontScale !== 'undefined') {
        fontScaleSelect.value = String(boardViewerScreenshotFontScale);
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

function boardViewerHtml2Canvas(target, options) {
    return ensureHtml2Canvas().then(function (html2canvas) {
        return html2canvas(target, options);
    });
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

        function isWebStandaloneBoardViewer() {
            const meta = document.querySelector('meta[name="web-standalone-mode"]');
            return !!(meta && meta.getAttribute('content') === '1');
        }

        document.addEventListener('DOMContentLoaded', function () {
            const prevBtn = document.getElementById('prevBtn');
            const nextBtn = document.getElementById('nextBtn');
            const invertBtn = document.getElementById('invertBtn');
            const screenshotBtn = document.getElementById('screenshotBtn');
            const screenSaveBtn = document.getElementById('screenSaveBtn');
            const screenUploadBtn = document.getElementById('screenUploadBtn');
            if (prevBtn) {
                prevBtn.style.backgroundImage = "url('" + staticAsset('/static/left.webp') + "')";
            }
            if (nextBtn) {
                nextBtn.style.backgroundImage = "url('" + staticAsset('/static/right.webp') + "')";
            }
            if (invertBtn) {
                invertBtn.style.backgroundImage = "url('" + staticAsset('/static/change_color.webp') + "')";
            }
            if (screenshotBtn) {
                screenshotBtn.style.backgroundImage = "url('" + staticAsset('/static/Screen.webp') + "')";
            }
            if (screenSaveBtn) {
                screenSaveBtn.style.backgroundImage = "url('" + staticAsset('/static/ScreenSave.webp') + "')";
            }
            if (screenUploadBtn) {
                screenUploadBtn.style.backgroundImage = "url('" + staticAsset('/static/ScreenUpload.webp') + "')";
            }
            if (isWebStandaloneBoardViewer()) {
                if (screenSaveBtn) screenSaveBtn.title = 'Добавить скриншот в архив';
                if (screenUploadBtn) screenUploadBtn.title = 'Скачать архив со скриншотами';
                if (screenshotBtn) screenshotBtn.title = 'Скачать скриншот';
            }
            if (screenshotBtn) screenshotBtn.addEventListener('click', takeScreenshot);
            if (screenSaveBtn) screenSaveBtn.addEventListener('click', saveScreenshot);
            if (screenUploadBtn) screenUploadBtn.addEventListener('click', uploadScreenshots);

            function bindBoardOptionToggle(toggleBtn, checkbox, invertDisplay) {
                if (!toggleBtn || !checkbox) return;
                const sync = () => {
                    const isOn = invertDisplay ? !checkbox.checked : checkbox.checked;
                    toggleBtn.classList.toggle('active', isOn);
                    toggleBtn.setAttribute('aria-pressed', isOn ? 'true' : 'false');
                };
                toggleBtn.addEventListener('click', () => {
                    checkbox.checked = !checkbox.checked;
                    checkbox.dispatchEvent(new Event('change'));
                    sync();
                });
                sync();
            }

            bindBoardOptionToggle(document.getElementById('hideInfoToggle'), document.getElementById('hideInfoCheckbox'), true);
            bindBoardOptionToggle(document.getElementById('skipAnimationToggle'), document.getElementById('skipAnimationCheckbox'), true);
            bindBoardOptionToggle(document.getElementById('hidePipsToggle'), document.getElementById('hidePipsCheckbox'), true);
        });
    
        let data = [];
        let availableGames = [];
        let current = 0;
        let currentGameNum = 1;
        let matchLength = 0;
        let matchPoint = 0;
        let gameRedScore = 0;
        let gameBlackScore = 0;
        let redPlayer = 'Unknown';
        let blackPlayer = 'Unknown';
        let inverted = false;
        let invertColors = false;
        let dataLoaded = false;
        let animating = false;
        let skipAnimation = false;
        let animationSpeed = 1.0;
        let skipAnimationEnabled = false;
        let pendingPrevGame = false;
        let enable_crawford_game_number = null;

        const canvas = document.getElementById('boardCanvas');
        const ctx = canvas.getContext('2d');
        const BOARD_CANVAS_LOGICAL_SIZE = 800;
        const BOARD_POINT_NUMBER_FONT_PX = 30;
        const matchInfoDiv = document.getElementById('match-info');
        const playersInfoDiv = document.getElementById('players-info');

        function updateBoardViewerUiScale() {
            const boardBlock = document.querySelector('.board-block');
            if (!boardBlock || !canvas) return;
            const renderedWidth = canvas.getBoundingClientRect().width;
            if (!renderedWidth) return;
            const scale = renderedWidth / BOARD_CANVAS_LOGICAL_SIZE;
            boardBlock.style.setProperty('--board-ui-scale', scale.toFixed(4));
        }

        if (typeof ResizeObserver !== 'undefined') {
            const boardScaleObserver = new ResizeObserver(() => updateBoardViewerUiScale());
            boardScaleObserver.observe(canvas);
        }
        window.addEventListener('resize', updateBoardViewerUiScale);
        updateBoardViewerUiScale();

        // Load images
        const boardImg = new Image();
        boardImg.src = staticAsset('/static/board.webp');
        const whiteChecker = new Image();
        whiteChecker.src = staticAsset('/static/white_checker.webp');
        const blackChecker = new Image();
        blackChecker.src = staticAsset('/static/black_checker.webp');

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

        const cubeImages = {
            2: Double2,
            4: Double4,
            8: Double8,
            16: Double16,
            32: Double32,
            64: Double64
        };

        // Get game_id from URL
        const urlParams = new URLSearchParams(window.location.search);
        const game_id = urlParams.get('game_id');
        const chat_id = urlParams.get('chat_id')

        if (!game_id) {
            console.error('No game_id provided in URL');
            alert('No game_id provided in URL');
        }

        // Load data
        fetch(`/api/games/${game_id}`)
            .then(response => response.json())
            .then(jsonData => {
                let gamesArray;
                if (Array.isArray(jsonData)) {
                    gamesArray = jsonData;
                } else if (jsonData.games && Array.isArray(jsonData.games)) {
                    gamesArray = jsonData.games;
                } else if (jsonData.detail) {
                    alert('Error: ' + jsonData.detail);
                    return;
                } else {
                    console.error('Unexpected data format:', jsonData);
                    return;
                }
                data = gamesArray[0].turns; // Default to first game
                availableGames = gamesArray.map((game, index) => ({
                    game_number: index + 1,
                    turns: game.turns,
                    first_player: game.first.name,
                    second_player: game.second.name,
                    first_score: game.first.score,
                    second_score: game.second.score,
                    point_match: game.point_match,
                    is_long_game: game.is_long_game,
                    is_crawford: game.is_crawford,
                    winner: game.winner
                }));
                const gameInfo = gamesArray[0]
                redPlayer = gameInfo.first ? gameInfo.first.name : 'Unknown';
                blackPlayer = gameInfo.second ? gameInfo.second.name : 'Unknown';
                gameRedScore = gameInfo.first ? gameInfo.first.score : 0;
                gameBlackScore = gameInfo.second ? gameInfo.second.score : 0;
                matchPoint = gameInfo.point_match ? gameInfo.point_match : 0;
                matchLength = matchPoint;
                enable_crawford_game_number = gamesArray.findIndex(game => game.is_crawford) + 1 || null;
                dataLoaded = true;
                const matchInfoDiv = document.getElementById('match-info');
                const matchText = matchPoint === 0 ? 'Манигейм' : `Матч до ${matchPoint}`;
                const gameSpan = matchPoint === 0 ? '' : `<span>Игра ${currentGameNum}</span>`;
                matchInfoDiv.innerHTML = gameSpan;
                const matchTypeEl = document.getElementById('match-type');
                const matchScoreEl = document.getElementById('match-score');
                if (matchTypeEl) matchTypeEl.textContent = matchText;
                if (matchScoreEl) matchScoreEl.textContent = `Счет: ${gameRedScore} - ${gameBlackScore}`;
                const playersInfoDiv = document.getElementById('players-info');
                playersInfoDiv.innerHTML = `Белые: ${redPlayer} – Черные: ${blackPlayer}<br>`;
                updateGameSelect();
                document.getElementById('gameSelect').value = currentGameNum - 1;
                const gameSelectEl = document.getElementById('gameSelect');
                if (gameSelectEl) gameSelectEl.style.display = matchPoint === 0 ? 'none' : 'block';
                updateButtons();
                drawBoard();
                updateInfo();
                // Update crawford visibility
                let crawfordVisibility = (enable_crawford_game_number && currentGameNum === enable_crawford_game_number) ? 'visible' : 'hidden';
                document.getElementById('crawfordLabel').style.visibility = crawfordVisibility;
                // Force draw board after a short delay to ensure initialization
                setTimeout(() => drawBoard(), 100);
            })
            .catch(error => {
                console.error('Error loading games data:', error);
                alert('Error loading games data: ' + error.message);
            });

        function updateGameSelect() {
            const gameSelect = document.getElementById('gameSelect');
            gameSelect.innerHTML = '';
            availableGames.forEach(game => {
                const option = document.createElement('option');
                option.value = game.game_number - 1;
                option.textContent = `Game ${game.game_number}`;
                gameSelect.appendChild(option);
            });
        }

        function drawCheckers(player, img, positions, currentPlayer) {
            ctx.font = `bold ${BOARD_POINT_NUMBER_FONT_PX}px Arial`;
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
                        if (player === 'second') {
                            displayPoint = point;
                        } else if (player === 'first') {
                            displayPoint = 25 - point;
                        }
                    } else {
                        if (player === 'first') {
                            displayPoint = point;
                        } else if (player === 'second') {
                            displayPoint = 25 - point;
                        }
                    }
                    let numberY;
                    if (point > 12) {
                        numberY = y - 50;
                    } else {
                        numberY = y + 60;
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
            const barY = (player === 'second') ? 220 : 520;
            const barDy = (player === 'second') ? 55 : -55;
            if (positions.bar && positions.bar !== 0) {
                let y = barY;
                for (let i = 0; i < Math.min(Math.abs(positions.bar), 6); i++) {
                    ctx.drawImage(img, barX - 31.25, y + (i * barDy) - 31.25, 62.5, 62.5);
                }
                if (Math.abs(positions.bar) > 6) {
                    const lastCheckerY = y + (5 * barDy);
                    ctx.fillText(`(${Math.abs(positions.bar)})`, barX + 30, lastCheckerY + 5);
                }
            }

            let offX = 783;
            let offY = (player === 'second')
                ? (invertColors ? 440 : 340)
                : (invertColors ? 340 : 440);
            if (positions.off && positions.off !== 0) {
                const originalFont = ctx.font;
                ctx.font = 'bold 32px Arial';
                ctx.fillText(`${positions.off}`, offX, offY);
                ctx.font = originalFont;
            }
        }

        function getX(point, playerType = null) {

            let actualPoint = point;

            if (actualPoint >= 13 && actualPoint <= 18) {
                const baseX = 50 + (actualPoint - 13) * 60;
                return baseX - (actualPoint === 13 ? 8 : 0);
            } else if (actualPoint >= 19 && actualPoint <= 24) {
                return 450 + (actualPoint - 19) * 60;
            } else if (actualPoint >= 7 && actualPoint <= 12) {
                const baseX = 50 + (12 - actualPoint) * 60;
                return baseX - (actualPoint === 12 ? 4 : 0);
            } else if (actualPoint >= 1 && actualPoint <= 6) {
                return 450 + (6 - actualPoint) * 60;
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
                        } else if (player === 'red') {
                            effectivePoint = point;
                        }
                    }
                    totalPips += count * effectivePoint;
                }
            }
            return totalPips;
        }

        function getInitialPositions(inverted, is_long_game) {
            if (is_long_game) {
                if (inverted) {
                    return {
                        first: { '1': 1, '2': 2, '12': 5, '17': 3, '19': 5, 'bar': 0, 'off': 0 },
                        second: { '6': 5, '8': 3, '13': 5, '23': 2, '24': 1, 'bar': 0, 'off': 0 }
                    };
                } else {
                    return {
                        first: { '6': 5, '8': 3, '13': 5, '23': 2, '24': 1, 'bar': 0, 'off': 0 },
                        second: { '1': 1, '2': 2, '12': 5, '17': 3, '19': 5, 'bar': 0, 'off': 0 },
                    };
                }
            } else {
                if (inverted) {
                    return {
                        first: { '1': 2, '12': 5, '17': 3, '19': 5, 'bar': 0, 'off': 0 },
                        second: { '6': 5, '8': 3, '13': 5, '24': 2, 'bar': 0, 'off': 0 }
                    };
                } else {
                    return {
                        first: { '24': 2, '6': 5, '8': 3, '13': 5, 'bar': 0, 'off': 0 },
                        second: { '1': 2, '12': 5, '17': 3, '19': 5, 'bar': 0, 'off': 0 },
                    };
                }
            }
        }

        function drawBoard() {
            if (!dataLoaded) return;

            updateBoardViewerUiScale();

            const hidePips = hidePipsCheckbox && hidePipsCheckbox.checked;

            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Draw board
            ctx.drawImage(boardImg, 0, 0, canvas.width, canvas.height);

            let positions;
            if (current === 0) {
                const game = availableGames.find(g => g.game_number === currentGameNum);
                positions = getInitialPositions(inverted, game.is_long_game);
            } else {
                const prevTurn = current - 1;
                positions = inverted ? data[prevTurn].inverted_positions : data[prevTurn].positions;
            }

            invertColors = inverted;
            const game = availableGames.find(g => g.game_number === currentGameNum);
            const currentPlayerType = data[current] ? data[current].turn : null;
            const currentPlayerName = currentPlayerType ? (currentPlayerType === 'first' ? game.first_player : game.second_player) : null;
            drawCheckers('first', whiteChecker, positions.first, currentPlayerType);
            drawCheckers('second', blackChecker, positions.second, currentPlayerType);

            const redPips = calculatePips(positions.first, 'red', invertColors);
            const blackPips = calculatePips(positions.second, 'black', invertColors);

            if (!hidePips) {
                if (invertColors) {
                    document.getElementById('black-pips').innerText = `${redPips}`;
                    document.getElementById('red-pips').innerText = `${blackPips}`;
                    document.getElementById('black-pips').className = 'pips-above-board-inverted';
                    document.getElementById('red-pips').className = 'pips-below-board-inverted';
                    document.getElementById('black-pips').style.display = 'block';
                    document.getElementById('red-pips').style.display = 'block';
                    ctx.fillStyle = '#000000';
                    ctx.fillRect(650, 800, 150, 50);
                    ctx.fillStyle = '#ffffff';
                    ctx.font = `bold ${BOARD_POINT_NUMBER_FONT_PX}px Arial`;
                    ctx.textAlign = 'center';
                    ctx.fillText(`${redPips}`, 725, -20);

                    ctx.fillStyle = '#ffffff';
                    ctx.fillRect(650, -50, 150, 50);
                    ctx.fillStyle = '#000000';
                    ctx.fillText(`${blackPips}`, 725, 830);
                } else {
                    document.getElementById('black-pips').innerText = `${blackPips}`;
                    document.getElementById('red-pips').innerText = `${redPips}`;
                    document.getElementById('black-pips').className = 'pips-above-board';
                    document.getElementById('red-pips').className = 'pips-below-board';
                    document.getElementById('black-pips').style.display = 'block';
                    document.getElementById('red-pips').style.display = 'block';
                    ctx.fillStyle = '#000000';
                    ctx.fillRect(650, -50, 150, 50);
                    ctx.fillStyle = '#ffffff';
                    ctx.font = `bold ${BOARD_POINT_NUMBER_FONT_PX}px Arial`;
                    ctx.textAlign = 'center';
                    ctx.fillText(`${blackPips}`, 725, -20);

                    ctx.fillStyle = '#ffffff';
                    ctx.fillRect(650, 800, 150, 50);
                    ctx.fillStyle = '#000000';
                    ctx.fillText(`${redPips}`, 725, 830);
                }
            } else {
                document.getElementById('black-pips').style.display = 'none';
                document.getElementById('red-pips').style.display = 'none';
            }

            const item = data[current];
            if (item && item.dice && item.dice.length >= 2 && !['double', 'take', 'win'].includes(item.action)) {
                const [d1, d2] = item.dice;
                const diceY = 350;
                let diceX1, diceX2;
                let diceSet;
                if (invertColors) {
                    if (currentPlayerType === 'first') {
                        diceX1 = 130;
                        diceX2 = 220;
                        diceSet = diceImages.white;
                    } else {
                        diceX1 = 530;
                        diceX2 = 620;
                        diceSet = diceImages.black;
                    }
                } else {
                    if (currentPlayerType === 'first') {
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
            if (item && item.cube_owner === null) {
                // Default position: cube 64 in center
                ctx.drawImage(cubeImages[64], 400 - 25, 400 - 25, 50, 50);
            } else if (item && item.cube_value && item.cube_value > 1) {
                const cubeImg = cubeImages[item.cube_value];
                if (cubeImg) {
                    let cubeX, cubeY;
                    if (item.cube_location === 'center' && item.action != 'drop') {
                        if (item && item.cube_owner === 'first') {
                            cubeX = 200 - 25;
                            cubeY = 380 - 25;
                        } else {
                            cubeX = 600 - 25;
                            cubeY = 380 - 25;
                        }
                    } else {
                        if (item && item.cube_owner === 'first') {
                            cubeX = 400 - 25;
                            cubeY = 625 - 25;
                        } else {
                            cubeX = 400 - 25;
                            cubeY = 150 - 25;
                        }
                    }
                    ctx.drawImage(cubeImg, cubeX, cubeY, 50, 50);
                }
            }
        }

        function drawBoardForAnimation(positions, currentPlayerType) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(boardImg, 0, 0, canvas.width, canvas.height);

            invertColors = inverted;
            drawCheckers('first', whiteChecker, positions.first, currentPlayerType);
            drawCheckers('second', blackChecker, positions.second, currentPlayerType);


            const turnData = data[current];
            if (turnData && turnData.dice && turnData.dice.length === 2 &&
                !['double', 'take', 'win'].includes(turnData.action)) {

                const [d1, d2] = turnData.dice;
                const diceY = 350;
                let diceX1, diceX2;
                let diceSet;

                if (invertColors) {
                    if (currentPlayerType === 'first') {
                        diceX1 = 130; diceX2 = 220; diceSet = diceImages.white;
                    } else {
                        diceX1 = 530; diceX2 = 620; diceSet = diceImages.black;
                    }
                } else {
                    if (currentPlayerType === 'first') {
                        diceX1 = 530; diceX2 = 620; diceSet = diceImages.white;
                    } else {
                        diceX1 = 130; diceX2 = 220; diceSet = diceImages.black;
                    }
                }

                if (diceSet[d1]) ctx.drawImage(diceSet[d1], diceX1, diceY, 60, 60);
                if (diceSet[d2]) ctx.drawImage(diceSet[d2], diceX2, diceY, 60, 60);
            }


            // Draw cube during animation
            if (turnData && turnData.cube_owner === null) {
                // Default position: cube 64 in center
                ctx.drawImage(cubeImages[64], 400 - 25, 400 - 25, 50, 50);
            } else if (turnData && turnData.cube_value && turnData.cube_value > 1) {
                const cubeImg = cubeImages[turnData.cube_value];
                if (cubeImg) {
                    let cubeX, cubeY;
                    if (turnData.cube_location === 'center' && turnData.action != 'drop') {
                        if (turnData && turnData.cube_owner === 'first') {
                            cubeX = 200 - 25;
                            cubeY = 380 - 25;
                        } else {
                            cubeX = 600 - 25;
                            cubeY = 380 - 25;
                        }
                    } else {
                        if (turnData && turnData.cube_owner === 'first') {
                            cubeX = 400 - 25;
                            cubeY = 625 - 25;
                        } else {
                            cubeX = 400 - 25;
                            cubeY = 150 - 25;
                        }
                    }
                    ctx.drawImage(cubeImg, cubeX, cubeY, 50, 50);
                }
            }
        }
        function animateSingleMove(move, playerType, temp_positions, callback) {
            const img = playerType === 'first' ? whiteChecker : blackChecker;
            const player_pos = temp_positions[playerType];
            const opp_pos = temp_positions[playerType === 'first' ? 'second' : 'first'];
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
                const barY = (playerType === 'second') ? 220 : 520;
                const barDy = (playerType === 'second') ? 55 : -55;
                const barCount = player_pos['bar'] || 0;
                fromY = barY + (barCount - 1) * barDy;
            } else {
                const fromPoint = parseInt(fromStr);
                fromX = getX(fromPoint, playerType);
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
                toY = playerType === 'second'
                    ? (invertColors ? 440 : 340)
                    : (invertColors ? 340 : 440);
            } else {
                const toPoint = parseInt(toStr);
                toX = getX(toPoint, playerType);
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

                drawBoardForAnimation(temp_positions, playerType);
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
            const hitPlayerType = playerType === 'first' ? 'second' : 'first';
            const img = hitPlayerType === 'first' ? whiteChecker : blackChecker;
            const opp_pos = temp_positions[hitPlayerType];

            const toStr = move.to.toString();
            // Temporarily remove hit checker from to position
            opp_pos[toStr] = (opp_pos[toStr] || 1) - 1;
            if (opp_pos[toStr] === 0) delete opp_pos[toStr];

            const hitPoint = parseInt(toStr);
            const fromX = getX(hitPoint, hitPlayerType);
            const fromBaseY = getBaseY(hitPoint);
            const fromDy = getDy(hitPoint);
            const hitCount = opp_pos[toStr] || 0; // Now 0
            let fromY = fromBaseY + (hitCount - 1) * fromDy;

            const barX = 400;
            const barY = (hitPlayerType === 'second') ? 220 : 520;
            const barDy = (hitPlayerType === 'second') ? 55 : -55;
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

                drawBoardForAnimation(temp_positions, playerType);
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
            const opp_pos = temp_positions[playerType === 'first' ? 'second' : 'first'];
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
            if (skipAnimationEnabled) {
                if (current >= data.length - 1) {
                    if (currentGameNum < availableGames.length) {
                        currentGameNum++;
                        let crawfordVisibility = (enable_crawford_game_number && currentGameNum === enable_crawford_game_number) ? 'visible' : 'hidden';
                        document.getElementById('crawfordLabel').style.visibility = crawfordVisibility;
                        data = availableGames[currentGameNum - 1].turns;
                        current = 0;
                        updateGameSelect();
                        document.getElementById('gameSelect').value = currentGameNum - 1;
                        updateButtons();
                        drawBoard();
                        updateInfo();
                        const game = availableGames[currentGameNum - 1];
                        const matchText = game.point_match === 0 ? 'Манигейм' : `Матч до ${game.point_match}`;
                        const gameSpan = game.point_match === 0 ? '' : `<span>Игра ${currentGameNum}</span>`;
                        matchInfoDiv.innerHTML = gameSpan;
                        const matchTypeEl = document.getElementById('match-type');
                        const matchScoreEl = document.getElementById('match-score');
                        if (matchTypeEl) matchTypeEl.textContent = matchText;
                        if (matchScoreEl) matchScoreEl.textContent = `Счет: ${game.first_score} - ${game.second_score}`;
                        const gameSelectEl = document.getElementById('gameSelect');
                        if (gameSelectEl) gameSelectEl.style.display = game.point_match === 0 ? 'none' : 'block';
                        redPlayer = game.first_player;
                        blackPlayer = game.second_player;
                        gameRedScore = game.first_score;
                        gameBlackScore = game.second_score;
                        playersInfoDiv.innerHTML = `Белые: ${redPlayer} – Черные: ${blackPlayer}<br>`;
                    } else {
                        return;
                    }
                } else {
                    current++;
                    drawBoard();
                    updateButtons();
                    updateInfo();
                }
                return;
            }

            // Если уже идет анимация - устанавливаем флаг пропуска
            if (animating) {
                skipAnimation = true;
                return;
            }

            if (current >= data.length - 1) {
                if (currentGameNum < availableGames.length) {
                    currentGameNum++;
                    let crawfordVisibility = (enable_crawford_game_number && currentGameNum === enable_crawford_game_number) ? 'visible' : 'hidden';
                    document.getElementById('crawfordLabel').style.visibility = crawfordVisibility;
                    data = availableGames[currentGameNum - 1].turns;
                    current = 0;
                    updateGameSelect();
                    document.getElementById('gameSelect').value = currentGameNum - 1;
                    updateButtons();
                    drawBoard();
                    updateInfo();
                    const game = availableGames[currentGameNum - 1];
                    const matchText = game.point_match === 0 ? 'Манигейм' : `Матч до ${game.point_match}`;
                    const gameSpan = game.point_match === 0 ? '' : `<span>Игра ${currentGameNum}</span>`;
                    matchInfoDiv.innerHTML = gameSpan;
                    const matchTypeEl = document.getElementById('match-type');
                    const matchScoreEl = document.getElementById('match-score');
                    if (matchTypeEl) matchTypeEl.textContent = matchText;
                    if (matchScoreEl) matchScoreEl.textContent = `Счет: ${game.first_score} - ${game.second_score}`;
                    const gameSelectEl = document.getElementById('gameSelect');
                    if (gameSelectEl) gameSelectEl.style.display = game.point_match === 0 ? 'none' : 'block';
                    redPlayer = game.first_player;
                    blackPlayer = game.second_player;
                    gameRedScore = game.first_score;
                    gameBlackScore = game.second_score;
                    playersInfoDiv.innerHTML = `Белые: ${redPlayer} – Черные: ${blackPlayer}<br>`;
                } else {
                    return;
                }
            } else {

                animating = true;
                skipAnimation = false; // Сбрасываем флаг
                updateButtons();
                updateInfo(); // Обновляем инфо сразу

                const nextTurnData = data[current];
                const playerType = nextTurnData.turn === 'first' ? 'first' : 'second';

                let prev_positions;
                if (current === 0) {
                    const game = availableGames.find(g => g.game_number === currentGameNum);
                    prev_positions = getInitialPositions(inverted, game.is_long_game);
                } else {
                    prev_positions = inverted ? data[current - 1].inverted_positions : data[current - 1].positions;
                }

                const temp_positions = JSON.parse(JSON.stringify(prev_positions));

                let moves = nextTurnData.moves || [];
                const toScreenPoint = (p) => {
                    if (p === 'off' || p === 0) return 'off';
                    if (p === 'bar' || p === 25) return 'bar';
                    const n = Number(p);
                    if (!Number.isFinite(n) || n < 1 || n > 24) return p;
                    let boardP = (playerType === 'second') ? (25 - n) : n;
                    return inverted ? (25 - boardP) : boardP;
                };

                moves = moves.map(m => ({
                    ...m,
                    from: toScreenPoint(m.from),
                    to: toScreenPoint(m.to),
                }));

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
                            // Завершаем анимацию
                            clearTimeout(timeoutId);
                            current++;
                            drawBoard();
                            updateButtons();
                            updateInfo();
                            animating = false;
                            skipAnimation = false;
                            if (pendingPrevGame) {
                                pendingPrevGame = false;
                                if (currentGameNum > 1) {
                                    currentGameNum--;
                                    let crawfordVisibility = (enable_crawford_game_number && currentGameNum === enable_crawford_game_number) ? 'visible' : 'hidden';
                                    document.getElementById('crawfordLabel').style.visibility = crawfordVisibility;
                                    data = availableGames[currentGameNum - 1].turns;
                                    current = data.length - 1;
                                    updateGameSelect();
                                    document.getElementById('gameSelect').value = currentGameNum - 1;
                                    drawBoard();
                                    updateButtons();
                                    updateInfo();
                                    const game = availableGames[currentGameNum - 1];
                                    const matchText = game.point_match === 0 ? 'Манигейм' : `Матч до ${game.point_match}`;
                                    const gameSpan = game.point_match === 0 ? '' : `<span>Игра ${currentGameNum}</span>`;
                                    matchInfoDiv.innerHTML = gameSpan;
                                    const matchTypeEl = document.getElementById('match-type');
                                    const matchScoreEl = document.getElementById('match-score');
                                    if (matchTypeEl) matchTypeEl.textContent = matchText;
                                    if (matchScoreEl) matchScoreEl.textContent = `Счет: ${game.first_score} - ${game.second_score}`;
                                    const gameSelectEl = document.getElementById('gameSelect');
                                    if (gameSelectEl) gameSelectEl.style.display = game.point_match === 0 ? 'none' : 'block';
                                    redPlayer = game.first_player;
                                    blackPlayer = game.second_player;
                                    gameRedScore = game.first_score;
                                    gameBlackScore = game.second_score;
                                    playersInfoDiv.innerHTML = `Белые: ${redPlayer} – Черные: ${blackPlayer}<br>`;
                                }
                            }
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
                            clearTimeout(timeoutId);
                            current++;
                            drawBoard();
                            updateButtons();
                            updateInfo();
                            animating = false;
                        }
                    };
                    animateMoves();
                } else {
                    clearTimeout(timeoutId);
                    current++;
                    drawBoard();
                    updateButtons();
                    updateInfo();
                    animating = false;
                }
            }
        }

        function prevTurn() {
            if (animating) {
                skipAnimation = true;
                pendingPrevGame = true;
                setTimeout(() => {
                    if (pendingPrevGame) {
                        pendingPrevGame = false;
                        if (current > 0) {
                            current--;
                            drawBoard();
                            updateButtons();
                            updateInfo();
                        }
                    }
                }, 50);
                return;
            }

            if (current === 0) {
                if (currentGameNum > 1) {
                    currentGameNum--;
                    let crawfordVisibility = (enable_crawford_game_number && currentGameNum === enable_crawford_game_number) ? 'visible' : 'hidden';
                    document.getElementById('crawfordLabel').style.visibility = crawfordVisibility;
                    data = availableGames[currentGameNum - 1].turns;
                    current = data.length - 1;
                    updateGameSelect();
                    document.getElementById('gameSelect').value = currentGameNum - 1;
                    drawBoard();
                    updateButtons();
                    updateInfo();
                    const game = availableGames[currentGameNum - 1];
                    const matchText = game.point_match === 0 ? 'Манигейм' : `Матч до ${game.point_match}`;
                    const gameSpan = game.point_match === 0 ? '' : `<span>Игра ${currentGameNum}</span>`;
                    matchInfoDiv.innerHTML = gameSpan;
                    const matchTypeEl = document.getElementById('match-type');
                    const matchScoreEl = document.getElementById('match-score');
                    if (matchTypeEl) matchTypeEl.textContent = matchText;
                    if (matchScoreEl) matchScoreEl.textContent = `Счет: ${game.first_score} - ${game.second_score}`;
                    const gameSelectEl = document.getElementById('gameSelect');
                    if (gameSelectEl) gameSelectEl.style.display = game.point_match === 0 ? 'none' : 'block';
                    redPlayer = game.first_player;
                    blackPlayer = game.second_player;
                    gameRedScore = game.first_score;
                    gameBlackScore = game.second_score;
                    playersInfoDiv.innerHTML = `Белые: ${redPlayer} – Черные: ${blackPlayer}<br>`;
                }
                return;
            }

            current--;
            drawBoard();
            updateButtons();
            updateInfo();
        }

        function toggleInvert() {
            inverted = !inverted;
            drawBoard();
        }

        function updateButtons() {
            const prevBtn = document.getElementById('prevBtn');
            const nextBtn = document.getElementById('nextBtn');

            if (dataLoaded) {
                prevBtn.disabled = current === 0 && currentGameNum === 1;
                nextBtn.disabled = current === data.length - 1 && currentGameNum >= availableGames.length;
            } else {
                prevBtn.disabled = true;
                nextBtn.disabled = true;
            }
        }

        function updateInfo() {
            if (!dataLoaded) return;

            const turnLabel = document.getElementById('turnLabel');
            turnLabel.textContent = data[current].turn_view;

            const moveInfo = document.getElementById('moveInfo');
            const turn = data[current];
            const game = availableGames.find(g => g.game_number === currentGameNum);

            let moveText = '';
            if (turn && turn.moves && turn.moves.length > 0) {
                const movesStr = turn.moves.map(m => `${m.from}/${m.to}${m.hit ? '*' : ''}`).join(' ');
                moveText = movesStr;
            } else if (turn && turn.action) {
                moveText = turn.action;
            } else {
                moveText = 'Пропуск хода';
            }

            // Check if last turn and winner
            if (current === data.length - 1 && game.winner) {
                const winner = game.winner;
                const nickname = winner.player === 'first' ? game.first_player : game.second_player;
                let first_score = game.first_score;
                let second_score = game.second_score;
                if (winner.player === 'first') {
                    first_score += winner.points;
                } else {
                    second_score += winner.points;
                }
                const winner_score = winner.player === 'first' ? first_score : second_score;
                const loser_score = winner.player === 'first' ? second_score : first_score;
                moveInfo.innerHTML = `${moveText}<br>${nickname} победил. Счет ${winner_score}:${loser_score}`;
            } else {
                moveInfo.textContent = moveText;
            }
        }

        // Screenshot logic from hint_viewer
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

        function showFadingMessage(message) {
            const msgDiv = document.createElement('div');
            msgDiv.style.position = 'fixed';
            msgDiv.style.top = '50%';
            msgDiv.style.left = '50%';
            msgDiv.style.transform = 'translate(-50%, -50%)';
            msgDiv.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
            msgDiv.style.color = 'white';
            msgDiv.style.padding = '10px 20px';
            msgDiv.style.borderRadius = '5px';
            msgDiv.style.fontSize = '16px';
            msgDiv.style.zIndex = '10000';
            msgDiv.innerHTML = message;
            document.body.appendChild(msgDiv);
            setTimeout(() => {
                msgDiv.style.transition = 'opacity 1s';
                msgDiv.style.opacity = '0';
                setTimeout(() => msgDiv.remove(), 1000);
            }, 1000);
        }

        function restoreAdminButtonContainerAfterScreenshot(adminButtonContainer, originalDisplay) {
            if (!adminButtonContainer) return;
            if (originalDisplay !== null && originalDisplay !== '') {
                adminButtonContainer.style.display = originalDisplay;
            } else {
                adminButtonContainer.style.display = 'none';
            }
        }

        let boardViewerScreenshotFontScale = (function () {
            const meta = document.querySelector('meta[name="board-screenshot-font-scale"]');
            const parsed = parseInt(meta?.getAttribute('content') || '100', 10);
            return Number.isNaN(parsed) ? 100 : parsed;
        })();
        let screenshotFontScaleBackup = [];

        function isScreenshotFontScaleSkipped(el) {
            if (!el || el.nodeType !== 1) return true;
            if (el.id === 'boardCanvas') return true;
            if (el.closest('#boardCanvas')) return true;
            if (el.closest('#adminButtonContainer')) return true;
            if (el.closest('#boardToolbar')) return true;
            if (el.closest('#controls')) return true;
            if (el.tagName === 'CANVAS') return true;
            return false;
        }

        function applyScreenshotFontScale() {
            const scale = boardViewerScreenshotFontScale / 100;
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

        async function saveBoardViewerScreenshotFontScale() {
            const select = document.getElementById('screenshotFontScaleSelect');
            if (!select) return;

            const fontScalePercent = parseInt(select.value, 10);
            boardViewerScreenshotFontScale = fontScalePercent;

            let initData = '';
            if (window.Telegram && window.Telegram.WebApp) {
                initData = window.Telegram.WebApp.initData;
            }
            if (!initData) {
                showMessageModal('Не удалось сохранить: нет данных Telegram', 'error');
                return;
            }

            try {
                const response = await fetch('/api/board_viewer_screenshot_font_scale', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ initData, fontScalePercent })
                });
                if (response.ok) {
                    const data = await response.json();
                    boardViewerScreenshotFontScale = data.fontScalePercent;
                    select.value = String(boardViewerScreenshotFontScale);
                    showMessageModal('Масштаб шрифта для скриншота сохранён', 'success');
                } else {
                    showMessageModal('Не удалось сохранить масштаб шрифта', 'error');
                }
            } catch (error) {
                console.error('Error saving screenshot font scale:', error);
                showMessageModal('Не удалось сохранить масштаб шрифта', 'error');
            }
        }

        const BOARD_VIEWER_SCREENSHOT_SELECTORS = [
            '.board-block',
        ];

        function isBoardViewerScreenshotElementVisible(el) {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) {
                return false;
            }
            const rect = el.getBoundingClientRect();
            return rect.width > 0 || rect.height > 0;
        }

        function measureBoardViewerScreenshotBounds(extraPadding) {
            extraPadding = extraPadding == null ? 12 : extraPadding;
            const scrollX = window.scrollX || document.documentElement.scrollLeft || 0;
            const scrollY = window.scrollY || document.documentElement.scrollTop || 0;
            const elements = [];

            BOARD_VIEWER_SCREENSHOT_SELECTORS.forEach((selector) => {
                document.querySelectorAll(selector).forEach((el) => {
                    if (isBoardViewerScreenshotElementVisible(el)) {
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

            return {
                x: Math.max(0, Math.floor(left + scrollX - extraPadding)),
                y: Math.max(0, Math.floor(top + scrollY - extraPadding)),
                width: Math.max(1, Math.ceil(right - left + extraPadding * 2)),
                height: Math.max(1, Math.ceil(bottom - top + extraPadding * 2)),
                windowWidth: document.documentElement.clientWidth,
                windowHeight: document.documentElement.clientHeight,
            };
        }

        function getBoardViewerHtml2CanvasOptions() {
            const bounds = measureBoardViewerScreenshotBounds();
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

        function captureBoardViewerScreenshot() {
            window.scrollTo(0, 0);
            applyScreenshotFontScale();
            document.body.classList.add('screenshot-mode');
            const boardBlock = document.querySelector('.board-block');
            return new Promise((resolve, reject) => {
                requestAnimationFrame(() => {
                    requestAnimationFrame(() => {
                        const target = boardBlock || document.body;
                        const options = boardBlock ? {
                            useCORS: true,
                            allowTaint: true,
                            backgroundColor: '#1a1a1a',
                            scale: Math.min(window.devicePixelRatio || 1, 2),
                            ignoreElements: function (el) {
                                return !!(el && el.classList && el.classList.contains('web-standalone-back'));
                            },
                        } : getBoardViewerHtml2CanvasOptions();
                        boardViewerHtml2Canvas(target, options)
                            .then((canvas) => {
                                document.body.classList.remove('screenshot-mode');
                                removeScreenshotFontScale();
                                resolve(canvas);
                            })
                            .catch((err) => {
                                document.body.classList.remove('screenshot-mode');
                                removeScreenshotFontScale();
                                reject(err);
                            });
                    });
                });
            });
        }

        function saveScreenshot() {
            const controls = document.getElementById('controls');
            const gameSelect = document.getElementById('gameSelect');
            const screenSaveBtn = document.getElementById('screenSaveBtn');
            const screenUploadBtn = document.getElementById('screenUploadBtn');
            const screenshotBtn = document.getElementById('screenshotBtn');
            const invertBtn = document.getElementById('invertBtn');
            const boardToolbar = document.getElementById('boardToolbar');
            const blackPips = document.getElementById('black-pips');
            const redPips = document.getElementById('red-pips');
            const adminButtonContainer = document.getElementById('adminButtonContainer');
            const matchTypeEl = document.getElementById('match-type');
            const matchScoreEl = document.getElementById('match-score');
            const crawfordLabel = document.getElementById('crawfordLabel');
            const originalControlsDisplay = controls ? controls.style.display : '';
            const originalGameSelectDisplay = gameSelect ? gameSelect.style.display : '';
            const originalScreenSaveBtnDisplay = screenSaveBtn ? screenSaveBtn.style.display : '';
            const originalScreenUploadBtnDisplay = screenUploadBtn ? screenUploadBtn.style.display : '';
            const originalScreenshotDisplay = screenshotBtn ? screenshotBtn.style.display : '';
            const originalInvertDisplay = invertBtn ? invertBtn.style.display : '';
            const originalBoardToolbarDisplay = boardToolbar ? boardToolbar.style.display : '';
            const originalAdminButtonContainerDisplay = adminButtonContainer
                ? adminButtonContainer.style.display
                : null;
            const originalBlackPipsDisplay = blackPips ? blackPips.style.display : '';
            const originalRedPipsDisplay = redPips ? redPips.style.display : '';
            const originalPlayersInfoDisplay = playersInfoDiv ? playersInfoDiv.style.display : '';
            const originalPlayersInfoHTML = playersInfoDiv ? playersInfoDiv.innerHTML : '';
            const originalMatchInfoHTML = matchInfoDiv ? matchInfoDiv.innerHTML : '';
            const originalMatchTypeDisplay = matchTypeEl ? matchTypeEl.style.display : '';
            const originalMatchScoreDisplay = matchScoreEl ? matchScoreEl.style.display : '';

            if (controls) controls.style.display = 'none';
            if (gameSelect) gameSelect.style.display = 'none';
            if (screenSaveBtn) screenSaveBtn.style.display = 'none';
            if (screenUploadBtn) screenUploadBtn.style.display = 'none';
            if (screenshotBtn) screenshotBtn.style.display = 'none';
            if (invertBtn) invertBtn.style.display = 'none';
            if (boardToolbar) boardToolbar.style.display = 'none';
            if (adminButtonContainer) adminButtonContainer.style.display = 'none';
            // Keep crawfordLabel visible for screenshots
            if (hideInfoCheckbox && hideInfoCheckbox.checked) {
                if (playersInfoDiv) {
                    playersInfoDiv.style.display = 'none';
                }
                if (matchTypeEl) matchTypeEl.style.display = 'none';
                if (matchScoreEl) matchScoreEl.style.display = 'none';
                if (matchInfoDiv) {
                    if (matchPoint > 0) {
                        const crawfordVisible = (enable_crawford_game_number && currentGameNum === enable_crawford_game_number) ? 'visible' : 'hidden';
                        matchInfoDiv.innerHTML = `<div style="display: flex; justify-content: space-between; align-items: center; position: relative;"><span>Матч до ${matchPoint}</span><span style="position: absolute; left: 50%; transform: translateX(-50%);">Счет: ${gameRedScore} - ${gameBlackScore}</span><span style="position: absolute; right: 0; visibility: ${crawfordVisible};">Кроуфорд</span></div>`;
                    } else {
                        matchInfoDiv.innerHTML = 'Манигейм';
                    }
                }
                if (gameSelect) gameSelect.style.display = 'none';
                if (crawfordLabel) {
                    crawfordLabel.style.position = 'absolute';
                    crawfordLabel.style.right = '10px';
                    crawfordLabel.style.left = 'auto';
                    crawfordLabel.style.transform = 'none';
                }
            }

            if (hidePipsCheckbox && hidePipsCheckbox.checked) {
                if (blackPips) blackPips.style.display = 'none';
                if (redPips) redPips.style.display = 'none';
            }

            captureBoardViewerScreenshot().then(canvas => {
                // Restore after screenshot
                if (controls) controls.style.display = originalControlsDisplay;
                if (gameSelect) gameSelect.style.display = originalGameSelectDisplay;
                if (screenSaveBtn) screenSaveBtn.style.display = originalScreenSaveBtnDisplay;
                if (screenUploadBtn) screenUploadBtn.style.display = originalScreenUploadBtnDisplay;
                if (screenshotBtn) screenshotBtn.style.display = originalScreenshotDisplay;
                if (invertBtn) invertBtn.style.display = originalInvertDisplay;
                if (boardToolbar) boardToolbar.style.display = originalBoardToolbarDisplay;
                restoreAdminButtonContainerAfterScreenshot(
                    adminButtonContainer,
                    originalAdminButtonContainerDisplay
                );
                if (blackPips) blackPips.style.display = originalBlackPipsDisplay;
                if (redPips) redPips.style.display = originalRedPipsDisplay;
                if (playersInfoDiv) {
                    playersInfoDiv.style.display = originalPlayersInfoDisplay;
                    playersInfoDiv.innerHTML = originalPlayersInfoHTML;
                }
                if (matchInfoDiv) {
                    matchInfoDiv.innerHTML = originalMatchInfoHTML;
                }
                if (matchTypeEl) matchTypeEl.style.display = originalMatchTypeDisplay;
                if (matchScoreEl) matchScoreEl.style.display = originalMatchScoreDisplay;
                // Restore crawfordLabel style
                if (crawfordLabel) {
                    crawfordLabel.style.position = '';
                    crawfordLabel.style.right = '';
                    crawfordLabel.style.left = '';
                    crawfordLabel.style.transform = '';
                }

                canvas.toBlob(blob => {
                    const formData = new FormData();
                    formData.append('photo', blob);
                    const saveUrl = isWebStandaloneBoardViewer()
                        ? '/web/hints/api/save_screenshot'
                        : `/api/save_screenshot?chat_id=${chat_id}`;
                    fetch(saveUrl, {
                        method: 'POST',
                        body: formData
                    }).then(async response => {
                        if (response.ok) {
                            showMessageModal('Скриншот сохранен в буфер', 'success');
                        } else if (response.status === 401) {
                            showMessageModal('Нужна авторизация', 'error');
                        } else if (response.status === 402) {
                            const data = await response.json();
                            const msg = (data.detail && typeof data.detail === 'string')
                                ? data.detail
                                : 'Недостаточно баланса для сохранения скриншота. Активируйте промокод или приобретите услугу.';
                            showMessageModal(msg, 'warning');
                        } else {
                            showMessageModal('Ошибка при сохранении скриншота', 'error');
                        }
                    }).catch(error => {
                        console.error('Error saving screenshot:', error);
                        showMessageModal('Ошибка при сохранении скриншота', 'error');
                    });
                });
            }).catch(error => {
                console.error('Error creating screenshot:', error);
                if (controls) controls.style.display = originalControlsDisplay;
                if (gameSelect) gameSelect.style.display = originalGameSelectDisplay;
                if (screenSaveBtn) screenSaveBtn.style.display = originalScreenSaveBtnDisplay;
                if (screenUploadBtn) screenUploadBtn.style.display = originalScreenUploadBtnDisplay;
                if (screenshotBtn) screenshotBtn.style.display = originalScreenshotDisplay;
                if (invertBtn) invertBtn.style.display = originalInvertDisplay;
                if (boardToolbar) boardToolbar.style.display = originalBoardToolbarDisplay;
                restoreAdminButtonContainerAfterScreenshot(
                    adminButtonContainer,
                    originalAdminButtonContainerDisplay
                );
                if (blackPips) blackPips.style.display = originalBlackPipsDisplay;
                if (redPips) redPips.style.display = originalRedPipsDisplay;
                if (playersInfoDiv) {
                    playersInfoDiv.style.display = originalPlayersInfoDisplay;
                    playersInfoDiv.innerHTML = originalPlayersInfoHTML;
                }
                if (matchInfoDiv) {
                    matchInfoDiv.innerHTML = originalMatchInfoHTML;
                }
                if (matchTypeEl) matchTypeEl.style.display = originalMatchTypeDisplay;
                if (matchScoreEl) matchScoreEl.style.display = originalMatchScoreDisplay;
                showMessageModal('Ошибка при создании скриншота', 'error');
            });
        }

        function uploadScreenshots() {
            if (isWebStandaloneBoardViewer()) {
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
                    showMessageModal('Архив скачан', 'success');
                }).catch(error => {
                    console.error('Error downloading screenshots:', error);
                    showMessageModal('Ошибка при скачивании архива', 'error');
                });
                return;
            }
            fetch(`/api/upload_screenshots?chat_id=${chat_id}`, { method: 'POST' }).then(async response => {
                if (response.ok) {
                    showMessageModal('Скриншоты отправлены', 'success');
                } else if (response.status === 402) {
                    const data = await response.json();
                    const msg = (data.detail && typeof data.detail === 'string')
                        ? data.detail
                        : 'Недостаточно баланса для отправки скриншотов. Активируйте промокод или приобретите услугу.';
                    showMessageModal(msg, 'warning');
                } else {
                    showMessageModal('Ошибка при отправке скриншотов', 'error');
                }
            }).catch(error => {
                console.error('Error uploading screenshots:', error);
                showMessageModal('Ошибка при отправке скриншотов', 'error');
            });
        }

        function takeScreenshot() {
            const controls = document.getElementById('controls');
            const gameSelect = document.getElementById('gameSelect');
            const screenSaveBtn = document.getElementById('screenSaveBtn');
            const screenUploadBtn = document.getElementById('screenUploadBtn');
            const screenshotBtn = document.getElementById('screenshotBtn');
            const invertBtn = document.getElementById('invertBtn');
            const boardToolbar = document.getElementById('boardToolbar');
            const blackPips = document.getElementById('black-pips');
            const redPips = document.getElementById('red-pips');
            const adminButtonContainer = document.getElementById('adminButtonContainer');
            const matchTypeEl = document.getElementById('match-type');
            const matchScoreEl = document.getElementById('match-score');
            const originalControlsDisplay = controls ? controls.style.display : '';
            const originalGameSelectDisplay = gameSelect ? gameSelect.style.display : '';
            const originalScreenSaveBtnDisplay = screenSaveBtn ? screenSaveBtn.style.display : '';
            const originalScreenUploadBtnDisplay = screenUploadBtn ? screenUploadBtn.style.display : '';
            const originalScreenshotDisplay = screenshotBtn ? screenshotBtn.style.display : '';
            const originalInvertDisplay = invertBtn ? invertBtn.style.display : '';
            const originalBoardToolbarDisplay = boardToolbar ? boardToolbar.style.display : '';
            const originalBlackPipsDisplay = blackPips ? blackPips.style.display : '';
            const originalRedPipsDisplay = redPips ? redPips.style.display : '';
            const originalAdminButtonContainerDisplay = adminButtonContainer
                ? adminButtonContainer.style.display
                : null;
            const originalPlayersInfoDisplay = playersInfoDiv ? playersInfoDiv.style.display : '';
            const originalPlayersInfoHTML = playersInfoDiv ? playersInfoDiv.innerHTML : '';
            const originalMatchInfoHTML = matchInfoDiv ? matchInfoDiv.innerHTML : '';
            const originalMatchTypeDisplay = matchTypeEl ? matchTypeEl.style.display : '';
            const originalMatchScoreDisplay = matchScoreEl ? matchScoreEl.style.display : '';

            if (controls) controls.style.display = 'none';
            if (gameSelect) gameSelect.style.display = 'none';
            if (screenSaveBtn) screenSaveBtn.style.display = 'none';
            if (screenUploadBtn) screenUploadBtn.style.display = 'none';
            if (screenshotBtn) screenshotBtn.style.display = 'none';
            if (invertBtn) invertBtn.style.display = 'none';
            if (boardToolbar) boardToolbar.style.display = 'none';
            if (adminButtonContainer) adminButtonContainer.style.display = 'none';
            // Keep crawfordLabel visible for screenshots
            if (hideInfoCheckbox && hideInfoCheckbox.checked) {
                if (playersInfoDiv) {
                    playersInfoDiv.style.display = 'none';
                }
                if (matchTypeEl) matchTypeEl.style.display = 'none';
                if (matchScoreEl) matchScoreEl.style.display = 'none';
                if (matchInfoDiv) {
                    if (matchPoint > 0) {
                        const crawfordVisible = (enable_crawford_game_number && currentGameNum === enable_crawford_game_number) ? 'visible' : 'hidden';
                        matchInfoDiv.innerHTML = `<div style="display: flex; justify-content: space-between; align-items: center; position: relative;"><span>Матч до ${matchPoint}</span><span style="position: absolute; left: 50%; transform: translateX(-50%);">Счет: ${gameRedScore} - ${gameBlackScore}</span><span style="position: absolute; right: 0; visibility: ${crawfordVisible};">Кроуфорд</span></div>`;
                    } else {
                        matchInfoDiv.innerHTML = 'Манигейм';
                    }
                }
                if (gameSelect) gameSelect.style.display = 'none';
            }

            if (hidePipsCheckbox && hidePipsCheckbox.checked) {
                if (blackPips) blackPips.style.display = 'none';
                if (redPips) redPips.style.display = 'none';
            }

            captureBoardViewerScreenshot().then(canvas => {
                // Restore after screenshot
                if (controls) controls.style.display = originalControlsDisplay;
                if (gameSelect) gameSelect.style.display = originalGameSelectDisplay;
                if (screenSaveBtn) screenSaveBtn.style.display = originalScreenSaveBtnDisplay;
                if (screenUploadBtn) screenUploadBtn.style.display = originalScreenUploadBtnDisplay;
                if (screenshotBtn) screenshotBtn.style.display = originalScreenshotDisplay;
                if (invertBtn) invertBtn.style.display = originalInvertDisplay;
                if (boardToolbar) boardToolbar.style.display = originalBoardToolbarDisplay;
                restoreAdminButtonContainerAfterScreenshot(
                    adminButtonContainer,
                    originalAdminButtonContainerDisplay
                );
                if (blackPips) blackPips.style.display = originalBlackPipsDisplay;
                if (redPips) redPips.style.display = originalRedPipsDisplay;
                if (playersInfoDiv) {
                    playersInfoDiv.style.display = originalPlayersInfoDisplay;
                    playersInfoDiv.innerHTML = originalPlayersInfoHTML;
                }
                if (matchInfoDiv) {
                    matchInfoDiv.innerHTML = originalMatchInfoHTML;
                }
                if (matchTypeEl) matchTypeEl.style.display = originalMatchTypeDisplay;
                if (matchScoreEl) matchScoreEl.style.display = originalMatchScoreDisplay;

                canvas.toBlob(blob => {
                    if (isWebStandaloneBoardViewer() || !(window.Telegram && window.Telegram.WebApp)) {
                        const link = document.createElement('a');
                        link.download = screenshotImageFileName();
                        link.href = canvas.toDataURL();
                        link.click();
                        showMessageModal('Скриншот скачан', 'success');
                        return;
                    }
                    const file = new File([blob], screenshotImageFileName(), { type: 'image/png' });
                    const formData = new FormData();
                    formData.append('photo', file);
                    fetch(`/api/send_screenshot?chat_id=${chat_id}`, {
                        method: 'POST',
                        body: formData
                    }).then(async response => {
                        if (response.ok) {
                            showMessageModal('Скриншот отправлен', 'success');
                        } else if (response.status === 402) {
                            const data = await response.json();
                            const msg = (data.detail && typeof data.detail === 'string')
                                ? data.detail
                                : 'Недостаточно баланса для отправки скриншота. Активируйте промокод или приобретите услугу.';
                            showMessageModal(msg, 'warning');
                        } else {
                            const text = await response.text();
                            try {
                                const errorData = JSON.parse(text);
                                showMessageModal(
                                    'Ошибка при отправке скриншота: ' + (errorData.detail || text),
                                    'error'
                                );
                            } catch (e) {
                                showMessageModal('Ошибка при отправке скриншота', 'error');
                            }
                        }
                    }).catch(error => {
                        console.error('Error sending screenshot:', error);
                        showMessageModal('Ошибка при отправке скриншота', 'error');
                    });
                });
            }).catch(error => {
                console.error('Error creating screenshot:', error);
                if (controls) controls.style.display = originalControlsDisplay;
                if (gameSelect) gameSelect.style.display = originalGameSelectDisplay;
                if (screenSaveBtn) screenSaveBtn.style.display = originalScreenSaveBtnDisplay;
                if (screenUploadBtn) screenUploadBtn.style.display = originalScreenUploadBtnDisplay;
                if (screenshotBtn) screenshotBtn.style.display = originalScreenshotDisplay;
                if (invertBtn) invertBtn.style.display = originalInvertDisplay;
                if (boardToolbar) boardToolbar.style.display = originalBoardToolbarDisplay;
                restoreAdminButtonContainerAfterScreenshot(
                    adminButtonContainer,
                    originalAdminButtonContainerDisplay
                );
                if (blackPips) blackPips.style.display = originalBlackPipsDisplay;
                if (redPips) redPips.style.display = originalRedPipsDisplay;
                if (playersInfoDiv) {
                    playersInfoDiv.style.display = originalPlayersInfoDisplay;
                    playersInfoDiv.innerHTML = originalPlayersInfoHTML;
                }
                if (matchInfoDiv) {
                    matchInfoDiv.innerHTML = originalMatchInfoHTML;
                }
                if (matchTypeEl) matchTypeEl.style.display = originalMatchTypeDisplay;
                if (matchScoreEl) matchScoreEl.style.display = originalMatchScoreDisplay;
                showMessageModal('Ошибка при создании скриншота', 'error');
            });
        }

        // Event listeners
        document.getElementById('gameSelect').addEventListener('change', (e) => {
            const gameIndex = parseInt(e.target.value);
            currentGameNum = gameIndex + 1;
            data = availableGames[gameIndex].turns;
            gameRedScore = availableGames[gameIndex].first_score;
            gameBlackScore = availableGames[gameIndex].second_score;
            current = 0;
            inverted = false;
            const matchInfoDiv = document.getElementById('match-info');
            const game = availableGames[gameIndex];
            const matchText = game.point_match === 0 ? 'Манигейм' : `Матч до ${game.point_match}`;
            const gameSpan = game.point_match === 0 ? '' : `<span>Игра ${currentGameNum}</span>`;
            matchInfoDiv.innerHTML = gameSpan;
            const matchTypeEl = document.getElementById('match-type');
            const matchScoreEl = document.getElementById('match-score');
            if (matchTypeEl) matchTypeEl.textContent = matchText;
            if (matchScoreEl) matchScoreEl.textContent = `Счет: ${gameRedScore} - ${gameBlackScore}`;
            let crawfordVisibility = (enable_crawford_game_number && currentGameNum === enable_crawford_game_number) ? 'visible' : 'hidden';
            document.getElementById('crawfordLabel').style.visibility = crawfordVisibility;
            const gameSelectEl = document.getElementById('gameSelect');
            if (gameSelectEl) gameSelectEl.style.display = game.point_match === 0 ? 'none' : 'block';
            drawBoard();
            updateButtons();
            updateInfo();
        });

        const hideInfoCheckbox = document.getElementById('hideInfoCheckbox');
        if (hideInfoCheckbox) {
            const savedState = localStorage.getItem('hideInfoCheckbox');
            if (savedState === 'true') {
                hideInfoCheckbox.checked = true;
            }
            hideInfoCheckbox.addEventListener('change', () => {
                localStorage.setItem('hideInfoCheckbox', hideInfoCheckbox.checked);
                syncBoardOptionToggleVisual('hideInfoToggle', hideInfoCheckbox, true);
            });
        }

        const hidePipsCheckbox = document.getElementById('hidePipsCheckbox');
        if (hidePipsCheckbox) {
            const savedState = localStorage.getItem('hidePipsCheckbox');
            if (savedState === 'true') {
                hidePipsCheckbox.checked = true;
            }
            hidePipsCheckbox.addEventListener('change', () => {
                localStorage.setItem('hidePipsCheckbox', hidePipsCheckbox.checked);
                drawBoard();
                syncBoardOptionToggleVisual('hidePipsToggle', hidePipsCheckbox, true);
            });
        }

        const skipAnimationCheckbox = document.getElementById('skipAnimationCheckbox');
        if (skipAnimationCheckbox) {
            skipAnimationEnabled = skipAnimationCheckbox.checked;
            skipAnimationCheckbox.addEventListener('change', (e) => {
                skipAnimationEnabled = e.target.checked;
                syncBoardOptionToggleVisual('skipAnimationToggle', skipAnimationCheckbox, true);
            });
        }

        function syncBoardOptionToggleVisual(toggleId, checkbox, invertDisplay) {
            const toggleBtn = document.getElementById(toggleId);
            if (!toggleBtn || !checkbox) return;
            const isOn = invertDisplay ? !checkbox.checked : checkbox.checked;
            toggleBtn.classList.toggle('active', isOn);
            toggleBtn.setAttribute('aria-pressed', isOn ? 'true' : 'false');
        }

        if (hideInfoCheckbox) {
            syncBoardOptionToggleVisual('hideInfoToggle', hideInfoCheckbox, true);
        }
        if (hidePipsCheckbox) {
            syncBoardOptionToggleVisual('hidePipsToggle', hidePipsCheckbox, true);
        }
        if (skipAnimationCheckbox) {
            syncBoardOptionToggleVisual('skipAnimationToggle', skipAnimationCheckbox, true);
        }

        document.getElementById('animationSpeedSlider').addEventListener('change', (e) => {
            animationSpeed = parseFloat(e.target.value);
        });

        function isBoardViewerTypingTarget(target) {
            if (!target) return false;
            const tag = target.tagName;
            if (tag === 'TEXTAREA' || tag === 'INPUT' || tag === 'SELECT') return true;
            return !!target.isContentEditable;
        }

        document.addEventListener('keydown', function (event) {
            if (isBoardViewerTypingTarget(event.target)) return;

            const supportModal = document.getElementById('supportModal');
            if (supportModal && supportModal.style.display === 'block') return;

            const prevBtn = document.getElementById('prevBtn');
            const nextBtn = document.getElementById('nextBtn');
            const code = event.code;

            if (code === 'ArrowLeft' || code === 'KeyA') {
                if (prevBtn && !prevBtn.disabled) {
                    event.preventDefault();
                    prevTurn();
                }
                return;
            }

            if (code === 'ArrowRight' || code === 'KeyD') {
                if (nextBtn && !nextBtn.disabled) {
                    event.preventDefault();
                    nextTurn();
                }
            }
        });

        // Draw board when images are loaded
        let imagesLoaded = 0;
        const totalImages = 21;

        function imageLoaded() {
            imagesLoaded++;
            if (imagesLoaded === totalImages && dataLoaded) {
                drawBoard();
            }
        }

        boardImg.onload = imageLoaded;
        whiteChecker.onload = imageLoaded;
        blackChecker.onload = imageLoaded;
        Dice1w.onload = imageLoaded;
        Dice2w.onload = imageLoaded;
        Dice3w.onload = imageLoaded;
        Dice4w.onload = imageLoaded;
        Dice5w.onload = imageLoaded;
        Dice6w.onload = imageLoaded;
        Dice1b.onload = imageLoaded;
        Dice2b.onload = imageLoaded;
        Dice3b.onload = imageLoaded;
        Dice4b.onload = imageLoaded;
        Dice5b.onload = imageLoaded;
        Dice6b.onload = imageLoaded;
        Double2.onload = imageLoaded;
        Double4.onload = imageLoaded;
        Double8.onload = imageLoaded;
        Double16.onload = imageLoaded;
        Double32.onload = imageLoaded;
        Double64.onload = imageLoaded;

        function openSupportModal() {
            if (isWebStandaloneBoardViewer()) {
                const widget = window.WebSupportWidget;
                if (widget && typeof widget.open === 'function') {
                    widget.open();
                    return;
                }
            }
            const modal = document.getElementById('supportModal');
            const textEl = document.getElementById('supportText');
            if (!modal || !textEl) return;
            modal.style.display = 'block';
            textEl.value = '';
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
                alert('Пожалуйста, введите описание проблемы');
                return;
            }

            const sendBtn = document.getElementById('sendSupportBtn');
            const originalBtnText = sendBtn.innerText;
            sendBtn.disabled = true;
            sendBtn.innerText = 'Отправка...';

            // Hide screenshot-related UI elements for capture
            const boardToolbar = document.getElementById('boardToolbar');
            const originalBoardToolbarDisplay = boardToolbar ? boardToolbar.style.display : '';
            if (boardToolbar) boardToolbar.style.display = 'none';

            // Still hide modal as requested previously
            const modal = document.getElementById('supportModal');
            const originalModalDisplay = modal.style.display;
            modal.style.display = 'none';

            applyScreenshotFontScale();
            boardViewerHtml2Canvas(document.body, {
                useCORS: true,
                allowTaint: true,
                backgroundColor: '#1a1a1a'
            }).then(canvas => {
                removeScreenshotFontScale();
                canvas.toBlob(blob => {
                    const formData = new FormData();
                    formData.append('photo', blob);
                    formData.append('text', text);
                    formData.append('chat_id', chat_id);

                    fetch('/api/send_to_support', {
                        method: 'POST',
                        body: formData
                    }).then(async response => {
                        if (response.ok) {
                            showFadingMessage('Сообщение отправлено в техподдержку');
                        } else if (response.status === 429) {
                            const data = await response.json();
                            const waitText = (data.detail && data.detail.wait_text) ? data.detail.wait_text : 'некоторое время';
                            alert(`Слишком много запросов. Пожалуйста, подождите ${waitText} перед следующей отправкой.`);
                            modal.style.display = originalModalDisplay;
                        } else {
                            alert('Ошибка при отправке сообщения');
                            modal.style.display = originalModalDisplay;
                        }
                    }).catch(error => {
                        console.error('Error sending to support:', error);
                        alert('Ошибка при отправке сообщения');
                        modal.style.display = originalModalDisplay;
                    }).finally(() => {
                        sendBtn.disabled = false;
                        sendBtn.innerText = originalBtnText;
                        if (boardToolbar) boardToolbar.style.display = originalBoardToolbarDisplay;
                    });
                });
            }).catch(error => {
                removeScreenshotFontScale();
                console.error('Error creating screenshot:', error);
                alert('Ошибка при создании скриншота');
                modal.style.display = originalModalDisplay;
                sendBtn.disabled = false;
                sendBtn.innerText = originalBtnText;
                if (boardToolbar) boardToolbar.style.display = originalBoardToolbarDisplay;
            });
        }

        if (window.Telegram && window.Telegram.WebApp) {
            const tg = window.Telegram.WebApp;
            const allowFullscreen = (document.querySelector('meta[name="webapp-fullscreen-enabled"]') || {}).content === '1';
            tg.ready();
            tg.expand();
            document.documentElement.style.height = 'auto';
            document.body.style.height = 'auto';
            document.body.style.overflowY = 'auto';
            if (typeof tg.disableVerticalSwipes === 'function') {
                try {
                    tg.disableVerticalSwipes();
                } catch (e) {
                    console.warn('disableVerticalSwipes(board_viewer) failed:', e);
                }
            }
            if (allowFullscreen) {
                try {
                    if (
                        typeof tg.requestFullscreen === 'function' &&
                        tg.isFullscreen !== true
                    ) {
                        tg.requestFullscreen();
                    }
                } catch (e) {
                    console.warn('requestFullscreen(board_viewer) failed:', e);
                }
            }
        }

        function boardViewerPositionsToRedBlack(raw) {
            if (!raw || typeof raw !== 'object') return null;
            if (raw.red && raw.black) {
                return {
                    red: JSON.parse(JSON.stringify(raw.red)),
                    black: JSON.parse(JSON.stringify(raw.black)),
                };
            }
            if (raw.first && raw.second) {
                return {
                    red: JSON.parse(JSON.stringify(raw.first)),
                    black: JSON.parse(JSON.stringify(raw.second)),
                };
            }
            return null;
        }

        function getBoardViewerPositionsForFrame() {
            if (!dataLoaded || !data) return null;
            const idx = current;
            if (idx === 0) {
                const game = availableGames.find((g) => g.game_number === currentGameNum);
                if (!game) return null;
                return boardViewerPositionsToRedBlack(getInitialPositions(inverted, game.is_long_game));
            }
            const prev = data[idx - 1];
            if (!prev) return null;
            const raw = inverted ? prev.inverted_positions : prev.positions;
            return boardViewerPositionsToRedBlack(raw);
        }

        function getBoardViewerCubeVisual(row) {
            if (!row) return null;
            if (row.action === 'win') {
                return { mode: 'center', value: 64 };
            }
            if (row.cube_owner === null || row.cube_owner === undefined) {
                return { mode: 'center', value: 64 };
            }
            const cubeVal = row.cube_value != null ? Number(row.cube_value) : 64;
            const ownerRaw = String(row.cube_owner || '').toLowerCase();
            const player =
                ownerRaw === 'first' || ownerRaw === 'red'
                    ? 'red'
                    : ownerRaw === 'second' || ownerRaw === 'black'
                      ? 'black'
                      : null;
            if (cubeVal > 1) {
                if (row.cube_location === 'center' && row.action !== 'drop') {
                    return { mode: 'side', value: cubeVal, player };
                }
                return { mode: 'bar', value: cubeVal, player };
            }
            return { mode: 'center', value: 64 };
        }

        window.getHintViewerBoardSnapshot = function () {
            try {
                const gid = game_id || 'default';
                if (!dataLoaded || !data || current === undefined) {
                    return {
                        frameId: `${gid}_g_na_f_na`,
                        gameId: gid,
                        currentGameNum: typeof currentGameNum !== 'undefined' ? currentGameNum : null,
                        frameIndex: null,
                        error: 'no_game_data',
                    };
                }
                const gNum = currentGameNum != null ? currentGameNum : 'na';
                const idx = current;
                const frameId = `${gid}_g${gNum}_f${idx}`;
                const positions = getBoardViewerPositionsForFrame();
                const row = data[idx] || null;
                let player = row && row.turn ? row.turn : null;
                if (player === 'first') player = 'red';
                else if (player === 'second') player = 'black';

                const ml = typeof matchPoint !== 'undefined' ? matchPoint : matchLength;

                return {
                    frameId,
                    gameId: gid,
                    currentGameNum: currentGameNum != null ? currentGameNum : null,
                    frameIndex: idx,
                    invertColors: !!inverted,
                    xgid: '',
                    positions,
                    cubeVisual: getBoardViewerCubeVisual(row),
                    scores:
                        typeof ml !== 'undefined'
                            ? {
                                  matchLength: ml,
                                  gameRedScore:
                                      typeof gameRedScore !== 'undefined' ? gameRedScore : null,
                                  gameBlackScore:
                                      typeof gameBlackScore !== 'undefined' ? gameBlackScore : null,
                              }
                            : null,
                    players: {
                        red: redPlayer,
                        black: blackPlayer,
                    },
                    turn: row
                        ? {
                              turn: row.turn,
                              action: row.action,
                              player,
                              player_name:
                                  row.player_name ||
                                  (row.turn === 'first'
                                      ? redPlayer
                                      : row.turn === 'second'
                                        ? blackPlayer
                                        : null),
                              dice: row.dice,
                              cube: row.cube_value != null ? row.cube_value : row.cube,
                              gnu_move: row.gnu_move,
                          }
                        : null,
                };
            } catch (e) {
                console.error('getHintViewerBoardSnapshot (board_viewer):', e);
                return { error: String(e.message || e) };
            }
        };

        window.getHintViewerCurrentCardData = function () {
            try {
                if (!dataLoaded || !data || current === undefined) {
                    return null;
                }
                return data.length > 0 ? data[current] : null;
            } catch (e) {
                console.error('getHintViewerCurrentCardData (board_viewer):', e);
                return null;
            }
        };

        async function checkAdminStatus() {
            if (isBoardViewerAdminFromMeta()) {
                applyBoardViewerAdminUi();
                return;
            }
            try {
                const tg = window.Telegram && window.Telegram.WebApp;
                const initData = tg && tg.initData ? tg.initData : '';
                if (!initData) {
                    return;
                }

                const response = await fetch('/api/check_admin', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ initData }),
                });

                if (response.ok) {
                    const data = await response.json();
                    if (data.is_admin) {
                        const adminContainer = document.getElementById('adminButtonContainer');
                        if (adminContainer) {
                            adminContainer.style.display = 'block';
                        }
                        const fontScaleSelect = document.getElementById('screenshotFontScaleSelect');
                        if (fontScaleSelect) {
                            fontScaleSelect.value = String(boardViewerScreenshotFontScale);
                        }
                    }
                }
            } catch (error) {
                console.error('Error checking admin status:', error);
            }
        }

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
                if (typeof contentEditor.renderEditorBoardDisplay === 'function') {
                    contentEditor.boardMatchBannerEnabled = true;
                    contentEditor.syncBoardMatchBannerToolbarVisibility();
                    contentEditor.renderEditorBoardDisplay();
                }
            } catch (e) {
                console.error('openPipCountCardEditor:', e);
            }
        }

        document.addEventListener('DOMContentLoaded', function () {
            checkAdminStatus();
        });

    
window.takeScreenshot = takeScreenshot;
window.saveScreenshot = saveScreenshot;
window.uploadScreenshots = uploadScreenshots;
window.prevTurn = prevTurn;
window.nextTurn = nextTurn;
window.toggleInvert = toggleInvert;
window.openSupportModal = openSupportModal;
window.closeSupportModal = closeSupportModal;
window.sendToSupport = sendToSupport;
window.openPipCountCardEditor = openPipCountCardEditor;
window.saveBoardViewerScreenshotFontScale = saveBoardViewerScreenshotFontScale;
