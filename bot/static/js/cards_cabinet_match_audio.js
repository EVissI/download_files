(function () {
    'use strict';

    var listModal = document.getElementById('maAudioListModal');
    var listOverlay = document.getElementById('maAudioListModalOverlay');
    var listCloseBtn = document.getElementById('maAudioListModalCloseBtn');
    var listImportBtn = document.getElementById('maAudioListImportBtn');
    var listExportBtn = document.getElementById('maAudioListExportBtn');
    var listExportFileInput = document.getElementById('maAudioListExportFileInput');
    var listEl = document.getElementById('maAudioListModalList');
    var listMsg = document.getElementById('maAudioListModalMsg');
    var listProgress = document.getElementById('maAudioListProgress');
    var listProgressBar = listProgress
        ? listProgress.querySelector('.ma-audio-modal__progress-bar')
        : null;
    var listSub = document.getElementById('maAudioListModalSub');
    var listTitle = document.getElementById('maAudioListModalTitle');

    var editModal = document.getElementById('maAudioEditModal');
    var editOverlay = document.getElementById('maAudioEditModalOverlay');
    var editCloseBtn = document.getElementById('maAudioEditModalCloseBtn');
    var editSub = document.getElementById('maAudioEditModalSub');
    var editMsg = document.getElementById('maAudioEditModalMsg');
    var editAttachBtn = document.getElementById('maAudioEditAttachBtn');
    var editRecordBtn = document.getElementById('maAudioEditRecordBtn');
    var editFileInput = document.getElementById('maAudioEditFileInput');

    var exportFormatModal = document.getElementById('maAudioExportFormatModal');
    var exportFormatOverlay = document.getElementById('maAudioExportFormatOverlay');
    var exportFormatCancelBtn = document.getElementById('maAudioExportFormatCancelBtn');
    var exportFormatConfirmBtn = document.getElementById('maAudioExportFormatConfirmBtn');
    var EXPORT_FORMAT_LS_KEY = 'ma_audio_export_format_v1';
    var exportFormatResolver = null;

    var state = {
        matchId: null,
        matchTitle: '',
        items: [],
        editItem: null,
        busy: false,
        convertActive: false,
        mediaRecorder: null,
        recordChunks: [],
        audioEl: null,
        playingKey: null,
        expandedKey: null,
        boardAssets: null,
        boardAssetsPromise: null,
    };

    function itemKey(item) {
        if (!item) return '';
        return String(item.game_number) + ':' + String(item.move_index) + ':' + String(item.audio_s3_key || '');
    }

    function mediaUrl(s3Key) {
        return '/api/match_analysis/media?key=' + encodeURIComponent(String(s3Key || ''));
    }

    function assetBust() {
        var v = '';
        try {
            v = (window.__STATIC_ASSET_V || '') ||
                ((document.querySelector('meta[name="static-asset-v"]') || {}).getAttribute
                    ? document.querySelector('meta[name="static-asset-v"]').getAttribute('content')
                    : '') ||
                '';
        } catch (_e) {
            v = '';
        }
        return v ? ('?t=' + encodeURIComponent(v)) : '';
    }

    function loadImage(src) {
        return new Promise(function (resolve, reject) {
            var img = new Image();
            img.onload = function () { resolve(img); };
            img.onerror = function () { reject(new Error(src)); };
            img.src = src;
        });
    }

    function loadBoardAssets() {
        if (state.boardAssets) return Promise.resolve(state.boardAssets);
        if (state.boardAssetsPromise) return state.boardAssetsPromise;
        var bust = assetBust();
        var paths = {
            board: '/static/board.webp' + bust,
            black: '/static/black_checker.webp' + bust,
            white: '/static/white_checker.webp' + bust,
        };
        var i;
        for (i = 1; i <= 6; i++) {
            paths['d' + i + 'w'] = '/static/' + i + 'w.webp' + bust;
            paths['d' + i + 'b'] = '/static/' + i + 'b.webp' + bust;
        }
        state.boardAssetsPromise = Promise.all(
            Object.keys(paths).map(function (key) {
                return loadImage(paths[key]).then(function (img) {
                    return [key, img];
                });
            })
        ).then(function (pairs) {
            var out = {};
            pairs.forEach(function (pair) { out[pair[0]] = pair[1]; });
            state.boardAssets = out;
            return out;
        }).catch(function (err) {
            state.boardAssetsPromise = null;
            throw err;
        });
        return state.boardAssetsPromise;
    }

    function getPointX(point) {
        if (point >= 13 && point <= 18) {
            return 50 + (point - 13) * 60 - (point === 13 ? 8 : 0);
        }
        if (point >= 19 && point <= 24) {
            return 450 + (point - 19) * 60;
        }
        if (point >= 7 && point <= 12) {
            return 50 + (12 - point) * 60 - (point === 12 ? 4 : 0);
        }
        if (point >= 1 && point <= 6) {
            return 450 + (6 - point) * 60;
        }
        return 0;
    }

    function getBaseY(point) {
        return point > 12 ? 70 : 690;
    }

    function getDy(point) {
        return point > 12 ? 55 : -55;
    }

    function drawCheckers(ctx, player, img, positions, currentPlayer, invertColors) {
        if (!positions) return;
        ctx.font = 'bold 30px Arial';
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        if (player === currentPlayer) {
            for (var point = 1; point <= 24; point++) {
                var x = getPointX(point);
                var y = getBaseY(point);
                var displayPoint = point;
                if (invertColors) {
                    if (player === 'red') displayPoint = 25 - point;
                } else if (player === 'black') {
                    displayPoint = 25 - point;
                }
                var numberY = point > 12 ? y - 50 : y + 60;
                ctx.fillText(String(displayPoint), x, numberY);
            }
        }

        Object.keys(positions).forEach(function (pointStr) {
            if (pointStr === 'bar' || pointStr === 'off') return;
            var p = parseInt(pointStr, 10);
            var count = positions[pointStr];
            var px = getPointX(p);
            var py = getBaseY(p);
            var dy = getDy(p);
            var i;
            for (i = 0; i < Math.min(count, 6); i++) {
                ctx.drawImage(img, px - 31.25, py + (i * dy) - 31.25, 62.5, 62.5);
            }
            if (count > 6) {
                ctx.fillText(String(count), px + 40, py + (5 * dy) + 5);
            }
        });

        var barX = 400;
        var barY = player === 'black' ? 220 : 520;
        if (invertColors) barY = player === 'black' ? 520 : 220;
        if (positions.bar && positions.bar !== 0) {
            var by = barY;
            var bdy = player === 'black' ? 55 : -55;
            for (var bi = 0; bi < Math.min(Math.abs(positions.bar), 6); bi++) {
                ctx.drawImage(img, barX - 31.25, by + (bi * bdy) - 31.25, 62.5, 62.5);
            }
            if (Math.abs(positions.bar) > 6) {
                ctx.fillText('(' + Math.abs(positions.bar) + ')', barX + 30, by + (5 * bdy) + 5);
            }
        }

        if (positions.off && positions.off !== 0) {
            var offX = 783;
            var offY = invertColors
                ? (player === 'black' ? 440 : 340)
                : (player === 'black' ? 340 : 440);
            var prevFont = ctx.font;
            ctx.font = 'bold 32px Arial';
            ctx.fillText(String(positions.off), offX, offY);
            ctx.font = prevFont;
        }
    }

    function calculatePips(positions, player, invertColors) {
        var totalPips = 0;
        if (!positions) return 0;
        Object.keys(positions).forEach(function (pointStr) {
            if (pointStr === 'bar') {
                totalPips += Math.abs(positions[pointStr]) * 25;
                return;
            }
            if (pointStr === 'off') return;
            var point = parseInt(pointStr, 10);
            if (!Number.isFinite(point)) return;
            var count = Number(positions[pointStr]) || 0;
            var effectivePoint = point;
            if (invertColors) {
                if (player === 'red') {
                    effectivePoint = 25 - point;
                } else if (player === 'black') {
                    effectivePoint = point;
                }
            } else if (player === 'black') {
                effectivePoint = 25 - point;
            } else {
                effectivePoint = point;
            }
            totalPips += count * effectivePoint;
        });
        return totalPips;
    }

    function applyPipsLabels(board, topEl, bottomEl) {
        if (!board || !topEl || !bottomEl) return;
        var invertColors = !!board.invert_colors;
        var positions = board.positions || {};
        var redPips = calculatePips(positions.red || {}, 'red', invertColors);
        var blackPips = calculatePips(positions.black || {}, 'black', invertColors);
        if (invertColors) {
            // Как в hint_viewer: сверху красные, снизу чёрные; стили инвертированы.
            topEl.textContent = String(redPips);
            bottomEl.textContent = String(blackPips);
            topEl.className = 'ma-audio-modal__pips ma-audio-modal__pips--above ma-audio-modal__pips--inverted';
            bottomEl.className = 'ma-audio-modal__pips ma-audio-modal__pips--below ma-audio-modal__pips--inverted';
        } else {
            topEl.textContent = String(blackPips);
            bottomEl.textContent = String(redPips);
            topEl.className = 'ma-audio-modal__pips ma-audio-modal__pips--above';
            bottomEl.className = 'ma-audio-modal__pips ma-audio-modal__pips--below';
        }
    }

    function paintMiniBoard(canvas, board, imgs) {
        if (!canvas || !board || !imgs || !imgs.board) return false;
        var ctx = canvas.getContext('2d');
        if (!ctx) return false;
        ctx.clearRect(0, 0, 800, 800);
        ctx.drawImage(imgs.board, 0, 0, 800, 800);

        var invertColors = !!board.invert_colors;
        var positions = board.positions || {};
        var redPositions = positions.red || {};
        var blackPositions = positions.black || {};
        var currentPlayer = String(board.player || 'Red').toLowerCase();

        drawCheckers(ctx, 'red', imgs.white, redPositions, currentPlayer, invertColors);
        drawCheckers(ctx, 'black', imgs.black, blackPositions, currentPlayer, invertColors);

        var dice = board.dice;
        var action = board.action;
        if (dice && dice.length >= 2 && ['double', 'take', 'win'].indexOf(action) === -1) {
            var d1 = dice[0];
            var d2 = dice[1];
            var diceY = 350;
            var diceX1;
            var diceX2;
            var diceSet;
            var isRed = String(board.player || '').toLowerCase() === 'red';
            var whiteDice = {
                1: imgs.d1w, 2: imgs.d2w, 3: imgs.d3w, 4: imgs.d4w, 5: imgs.d5w, 6: imgs.d6w,
            };
            var blackDice = {
                1: imgs.d1b, 2: imgs.d2b, 3: imgs.d3b, 4: imgs.d4b, 5: imgs.d5b, 6: imgs.d6b,
            };
            if (invertColors) {
                if (isRed) {
                    diceX1 = 130; diceX2 = 220; diceSet = whiteDice;
                } else {
                    diceX1 = 530; diceX2 = 620; diceSet = blackDice;
                }
            } else if (isRed) {
                diceX1 = 530; diceX2 = 620; diceSet = whiteDice;
            } else {
                diceX1 = 130; diceX2 = 220; diceSet = blackDice;
            }
            if (diceSet[d1]) ctx.drawImage(diceSet[d1], diceX1, diceY, 60, 60);
            if (diceSet[d2]) ctx.drawImage(diceSet[d2], diceX2, diceY, 60, 60);
        }
        return true;
    }

    function setPlayButtonState(btn, isPlaying) {
        if (!btn) return;
        btn.classList.toggle('is-playing', !!isPlaying);
        btn.title = isPlaying ? 'Пауза' : 'Слушать';
        btn.setAttribute('aria-label', isPlaying ? 'Пауза' : 'Слушать');
        btn.innerHTML = isPlaying
            ? '<i class="fa fa-pause" aria-hidden="true"></i>'
            : '<i class="fa fa-play" aria-hidden="true"></i>';
    }

    function syncPlayButtons() {
        if (!listEl) return;
        var buttons = listEl.querySelectorAll('.ma-audio-modal__play-btn');
        for (var i = 0; i < buttons.length; i++) {
            var btn = buttons[i];
            var key = btn.getAttribute('data-audio-key') || '';
            var isPlaying = !!(
                state.playingKey &&
                state.playingKey === key &&
                state.audioEl &&
                !state.audioEl.paused
            );
            setPlayButtonState(btn, isPlaying);
        }
    }

    function stopPlayback() {
        if (state.audioEl) {
            try { state.audioEl.pause(); } catch (_e) { /* ignore */ }
            try { state.audioEl.src = ''; } catch (_e2) { /* ignore */ }
            state.audioEl = null;
        }
        state.playingKey = null;
        syncPlayButtons();
    }

    function togglePlayback(item, btn) {
        if (!item || !item.audio_s3_key) return;
        var key = itemKey(item);
        if (state.playingKey === key && state.audioEl) {
            if (!state.audioEl.paused) {
                state.audioEl.pause();
                syncPlayButtons();
                return;
            }
            state.audioEl.play().then(function () {
                syncPlayButtons();
            }).catch(function (err) {
                console.error(err);
                setListMsg('Не удалось воспроизвести аудио', true);
                stopPlayback();
            });
            return;
        }
        stopPlayback();
        var audio = new Audio(mediaUrl(item.audio_s3_key));
        state.audioEl = audio;
        state.playingKey = key;
        audio.onended = function () {
            state.playingKey = null;
            state.audioEl = null;
            syncPlayButtons();
        };
        audio.onerror = function () {
            setListMsg('Ошибка воспроизведения аудио', true);
            stopPlayback();
        };
        setPlayButtonState(btn, true);
        audio.play().then(function () {
            syncPlayButtons();
        }).catch(function (err) {
            console.error(err);
            setListMsg('Не удалось воспроизвести аудио', true);
            stopPlayback();
        });
    }

    function api() {
        return window.CardsCabinetMatchAudioApi || {};
    }

    function getInitData() {
        if (typeof api().getInitData === 'function') {
            return api().getInitData() || '';
        }
        try {
            return (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || '';
        } catch (_e) {
            return '';
        }
    }

    function getFabToken() {
        if (typeof api().getFabToken === 'function') {
            return api().getFabToken() || '';
        }
        try {
            return new URLSearchParams(window.location.search || '').get('fab_token') || '';
        } catch (_e) {
            return '';
        }
    }

    function authPayload(extra) {
        var base = {};
        var initData = getInitData();
        var fabToken = getFabToken();
        if (initData) base.init_data = initData;
        else if (fabToken) base.fab_token = fabToken;
        if (extra && typeof extra === 'object') {
            Object.keys(extra).forEach(function (k) { base[k] = extra[k]; });
        }
        return base;
    }

    function isWebStandalone() {
        if (typeof api().isWebStandalone === 'function') {
            return !!api().isWebStandalone();
        }
        try {
            var meta = document.querySelector('meta[name="web-standalone-mode"]');
            return !!(meta && meta.getAttribute('content') === '1');
        } catch (_e) {
            return false;
        }
    }

    function hasAuth() {
        return !!(getInitData() || getFabToken() || isWebStandalone());
    }

    function requireAuth() {
        if (hasAuth()) return true;
        showNotice('Нет Telegram initData / FAB-токена', 'Ошибка');
        return false;
    }

    function showNotice(message, title) {
        if (typeof api().showNotice === 'function') {
            return api().showNotice(message, title);
        }
        window.alert(String(message || ''));
        return Promise.resolve();
    }

    function showConfirm(message, title, options) {
        if (typeof api().showConfirm === 'function') {
            return api().showConfirm(message, title, options || {});
        }
        return Promise.resolve(window.confirm(String(message || '')));
    }

    function buildViewUrl(matchId, gameNumber, moveIndex) {
        if (typeof api().buildMatchAnalysisViewUrl === 'function') {
            var base = api().buildMatchAnalysisViewUrl(matchId);
            var sep = base.indexOf('?') >= 0 ? '&' : '?';
            return (
                base +
                sep +
                'game=' + encodeURIComponent(String(gameNumber)) +
                '&move=' + encodeURIComponent(String(moveIndex))
            );
        }
        return (
            '/match-analysis-view?id=' + encodeURIComponent(String(matchId)) +
            '&error=0&game=' + encodeURIComponent(String(gameNumber)) +
            '&move=' + encodeURIComponent(String(moveIndex))
        );
    }

    function setListMsg(text, isError) {
        if (!listMsg) return;
        listMsg.textContent = String(text || '');
        listMsg.classList.toggle('is-error', !!isError && !!text);
    }

    function setEditMsg(text, isError) {
        if (!editMsg) return;
        editMsg.textContent = String(text || '');
        editMsg.classList.toggle('is-error', !!isError && !!text);
    }

    function playerSideLetter(item) {
        var raw = String(
            (item && item.player) ||
            (item && item.board && item.board.player) ||
            ''
        ).toLowerCase();
        if (raw === 'red' || raw === 'white') return 'б';
        if (raw === 'black') return 'ч';
        return '';
    }

    function frameLabel(item) {
        var parts = ['Игра ' + String(item.game_number)];
        if (item.turn != null && item.turn !== '') {
            var side = playerSideLetter(item);
            parts.push('ход ' + String(item.turn) + (side ? ' ' + side : ''));
        }
        if (item.gnu_move) {
            parts.push(String(item.gnu_move));
        } else if (item.action) {
            parts.push(String(item.action));
        }
        return parts.join(' · ');
    }

    function closeEditModal() {
        stopRecordingIfNeeded();
        if (!editModal) return;
        editModal.classList.remove('is-open');
        editModal.setAttribute('aria-hidden', 'true');
        state.editItem = null;
        setEditMsg('');
        if (editRecordBtn) {
            editRecordBtn.classList.remove('is-recording');
            editRecordBtn.innerHTML = '<i class="fa fa-microphone" aria-hidden="true"></i> Записать';
        }
    }

    function setCabinetFooterHidden(hidden) {
        var footer = document.querySelector('.cabinet-footer');
        if (!footer || footer.classList.contains('is-feature-hidden')) return;
        footer.classList.toggle('is-modal-overlay-hidden', !!hidden);
    }

    function closeListModal() {
        closeEditModal();
        stopPlayback();
        state.expandedKey = null;
        if (!listModal) return;
        listModal.classList.remove('is-open');
        listModal.setAttribute('aria-hidden', 'true');
        state.matchId = null;
        state.items = [];
        setListMsg('');
        setCabinetFooterHidden(false);
        // Конвертация на фоне продолжается; прогресс скрываем вместе с модалкой.
        setConvertProgressVisible(false);
    }

    function getEqThreshold() {
        try {
            var saved = localStorage.getItem('eqThreshold');
            if (saved != null && saved !== '') {
                var n = parseFloat(saved);
                if (Number.isFinite(n)) return n;
            }
        } catch (_e) { /* ignore */ }
        return 0.030;
    }

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function buildMoveHintsTableHtml(item) {
        var html = '<table><tr><th>Ход</th><th>%</th><th>%</th><th>Эквити</th></tr>';
        if (item && item.action === 'win') {
            html +=
                '<tr class="hint-best"><td>Победа ' +
                escapeHtml(item.player_name || '') +
                ' (' + escapeHtml(item.points) + ' очков)</td><td>-</td><td>-</td><td>-</td></tr>';
            html += '</table>';
            return html;
        }
        var hints = (item && Array.isArray(item.hints)) ? item.hints : [];
        var firstEq = hints.length > 0 && hints[0].eq != null ? hints[0].eq : null;
        var eqThreshold = getEqThreshold();
        var rows = 0;
        hints.forEach(function (hint, index) {
            if (!hint || !hint.probs || hint.probs.length < 2) return;
            var prob1 = hint.probs[0] != null ? (hint.probs[0] * 100).toFixed(1) : '-';
            var prob2 = hint.probs[1] != null ? (hint.probs[1] * 100).toFixed(1) : '-';
            var eq = hint.eq != null ? Number(hint.eq).toFixed(3) : '-';
            var displayEq = (firstEq != null && hint.eq != null && index > 0)
                ? '(' + (Number(hint.eq) - Number(firstEq)).toFixed(3) + ')'
                : eq;
            var move = hint.move || '-';
            var rowClass = '';
            var moveNorm = String(hint.move || '').replace(/\*/g, '');
            var gnuNorm = item.gnu_move ? String(item.gnu_move).trim().replace(/\*/g, '') : '';
            if (gnuNorm && moveNorm === gnuNorm && firstEq != null && hint.eq != null) {
                var diff = Number(firstEq) - Number(hint.eq);
                if (diff < eqThreshold) {
                    rowClass = 'hint-best';
                } else if (index >= 1 && index <= 4) {
                    rowClass = 'hint-good';
                } else {
                    rowClass = 'hint-poor';
                }
            }
            html +=
                '<tr class="' + rowClass + '"><td>' + escapeHtml(move) +
                '</td><td>' + escapeHtml(prob1) +
                '</td><td>' + escapeHtml(prob2) +
                '</td><td>' + escapeHtml(displayEq) + '</td></tr>';
            rows += 1;
        });
        if (!rows) {
            html += '<tr><td colspan="4">Нет подсказок по ходу</td></tr>';
        }
        html += '</table>';
        return html;
    }

    function buildCubeHintsTableHtml(item) {
        var html = '<table><tr><th>Действие</th><th>Эквити</th></tr>';
        var cubeHints = (item && Array.isArray(item.cube_hints)) ? item.cube_hints : [];
        if (!cubeHints.length || !cubeHints[0] || !Array.isArray(cubeHints[0].cubeful_equities)) {
            html += '<tr><td colspan="2">Нет подсказок по кубу</td></tr></table>';
            return html;
        }
        var nextGnuMove = item.next_gnu_move
            ? String(item.next_gnu_move).trim()
            : 'pass';
        var equities = cubeHints[0].cubeful_equities || [];
        var noDoubleHint = equities.find(function (h) { return h && h.action_1 === 'No double'; });
        var passHint = equities.find(function (h) {
            return h && h.action_1 === 'Double' && h.action_2 === 'pass';
        });
        var noDoubleEq = noDoubleHint && noDoubleHint.eq != null ? noDoubleHint.eq : null;
        var passHintEq = passHint && passHint.eq != null ? passHint.eq : null;
        var gnu = item.gnu_move ? String(item.gnu_move).trim() : '';
        equities.forEach(function (hint, index) {
            if (!hint) return;
            var eq = hint.eq != null ? Number(hint.eq).toFixed(3) : '-';
            var displayAction = hint.action_1 || '';
            if (hint.action_2) displayAction += ', ' + hint.action_2;
            var rowClass = '';
            if (gnu === 'Double' && hint.action_1 === 'Double' && hint.action_2 === nextGnuMove) {
                if (noDoubleEq != null && hint.eq != null) {
                    rowClass = hint.eq > noDoubleEq ? 'hint-best' : 'hint-good';
                }
            } else if (gnu === 'take' && hint.action_2 === 'take') {
                if (passHintEq != null && hint.eq != null) {
                    rowClass = hint.eq > passHintEq ? 'hint-best' : 'hint-good';
                }
            } else if (gnu !== 'take' && gnu !== 'Double' && hint.action_1 === 'No double') {
                if (index === 0) rowClass = 'hint-best';
                else if (index === 1) rowClass = 'hint-good';
                else if (index === 2) rowClass = 'hint-poor';
            }
            html +=
                '<tr class="' + rowClass + '"><td>' + escapeHtml(displayAction) +
                '</td><td>' + escapeHtml(eq) + '</td></tr>';
        });
        html += '</table>';
        return html;
    }

    function buildHintsPanel(item) {
        var root = document.createElement('div');
        root.className = 'ma-audio-modal__hints';

        var buttons = document.createElement('div');
        buttons.className = 'ma-audio-modal__hints-buttons';

        var moveBtn = document.createElement('button');
        moveBtn.type = 'button';
        moveBtn.className = 'ma-audio-modal__hint-toggle is-active';
        moveBtn.textContent = 'Ход';

        var cubeBtn = document.createElement('button');
        cubeBtn.type = 'button';
        cubeBtn.className = 'ma-audio-modal__hint-toggle';
        cubeBtn.textContent = 'Куб';

        buttons.appendChild(moveBtn);
        buttons.appendChild(cubeBtn);

        var moveContent = document.createElement('div');
        moveContent.className = 'ma-audio-modal__hints-content is-active';
        moveContent.innerHTML = item && item.action === 'win'
            ? '<p class="ma-audio-modal__hints-empty">Победа — таблица ходов не нужна</p>'
            : buildMoveHintsTableHtml(item);

        var cubeContent = document.createElement('div');
        cubeContent.className = 'ma-audio-modal__hints-content';
        cubeContent.innerHTML = item && item.action === 'win'
            ? '<p class="ma-audio-modal__hints-empty">Победа — таблица куба не нужна</p>'
            : buildCubeHintsTableHtml(item);

        function showMove() {
            moveContent.classList.add('is-active');
            cubeContent.classList.remove('is-active');
            moveBtn.classList.add('is-active');
            cubeBtn.classList.remove('is-active');
        }
        function showCube() {
            cubeContent.classList.add('is-active');
            moveContent.classList.remove('is-active');
            cubeBtn.classList.add('is-active');
            moveBtn.classList.remove('is-active');
        }

        moveBtn.addEventListener('click', function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            showMove();
        });
        cubeBtn.addEventListener('click', function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            showCube();
        });

        // Автовыбор вкладки: куб, если это решение по кубу и есть cube_hints.
        var action = item && item.action ? String(item.action) : '';
        var hasCube = Array.isArray(item && item.cube_hints) && item.cube_hints.length > 0;
        if ((action === 'double' || action === 'take' || action === 'drop') && hasCube) {
            showCube();
        }

        root.appendChild(buttons);
        root.appendChild(moveContent);
        root.appendChild(cubeContent);
        return root;
    }

    function buildBoardPanel(item) {
        var panel = document.createElement('div');
        panel.className = 'ma-audio-modal__board-panel';

        if (!item.board || !item.board.positions) {
            var empty = document.createElement('p');
            empty.className = 'ma-audio-modal__board-empty';
            empty.textContent = 'Нет данных доски для этого хода';
            panel.appendChild(empty);
            return panel;
        }

        var topPips = document.createElement('div');
        topPips.className = 'ma-audio-modal__pips ma-audio-modal__pips--above';
        topPips.textContent = '0';

        var stage = document.createElement('div');
        stage.className = 'ma-audio-modal__board-stage';

        var canvas = document.createElement('canvas');
        canvas.width = 800;
        canvas.height = 800;
        canvas.className = 'ma-audio-modal__board-canvas';
        canvas.setAttribute('aria-label', 'Доска хода');
        stage.appendChild(canvas);

        var footer = document.createElement('div');
        footer.className = 'ma-audio-modal__board-footer';
        var bottomPips = document.createElement('div');
        bottomPips.className = 'ma-audio-modal__pips ma-audio-modal__pips--below';
        bottomPips.textContent = '0';
        footer.appendChild(bottomPips);

        panel.appendChild(topPips);
        panel.appendChild(stage);
        panel.appendChild(footer);
        applyPipsLabels(item.board, topPips, bottomPips);

        loadBoardAssets().then(function (imgs) {
            if (state.expandedKey !== itemKey(item)) return;
            if (!paintMiniBoard(canvas, item.board, imgs)) {
                panel.innerHTML = '';
                var fail = document.createElement('p');
                fail.className = 'ma-audio-modal__board-empty';
                fail.textContent = 'Не удалось отрисовать доску';
                panel.appendChild(fail);
            }
        }).catch(function (err) {
            console.error(err);
            if (state.expandedKey !== itemKey(item)) return;
            panel.innerHTML = '';
            var errEl = document.createElement('p');
            errEl.className = 'ma-audio-modal__board-empty';
            errEl.textContent = 'Ошибка загрузки ресурсов доски';
            panel.appendChild(errEl);
        });

        return panel;
    }

    function bindCarousel(carousel, track, slides, dots, nextBtn) {
        var index = 0;
        var startX = 0;
        var startY = 0;
        var deltaX = 0;
        var tracking = false;
        var lockedAxis = null;
        var activePointerId = null;

        function setIndex(nextIndex, withAnim) {
            var total = slides.length;
            if (!total) return;
            index = ((nextIndex % total) + total) % total;
            if (withAnim === false) track.classList.add('is-dragging');
            else track.classList.remove('is-dragging');
            track.style.transform = 'translate3d(' + (-index * 100) + '%, 0, 0)';
            for (var i = 0; i < slides.length; i++) {
                slides[i].classList.toggle('is-active', i === index);
            }
            if (dots) {
                for (var d = 0; d < dots.length; d++) {
                    dots[d].classList.toggle('is-active', d === index);
                }
            }
            if (withAnim === false) {
                void track.offsetWidth;
            }
        }

        function cycleNext() {
            setIndex(index + 1, true);
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', function (ev) {
                ev.preventDefault();
                ev.stopPropagation();
                cycleNext();
            });
        }

        function onPointerDown(clientX, clientY, pointerId) {
            tracking = true;
            lockedAxis = null;
            activePointerId = pointerId == null ? null : pointerId;
            startX = clientX;
            startY = clientY;
            deltaX = 0;
            track.classList.add('is-dragging');
        }

        function onPointerMove(clientX, clientY) {
            if (!tracking) return;
            var dx = clientX - startX;
            var dy = clientY - startY;
            if (!lockedAxis) {
                if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return;
                lockedAxis = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
                if (lockedAxis === 'y') {
                    tracking = false;
                    activePointerId = null;
                    track.classList.remove('is-dragging');
                    track.style.transform = 'translate3d(' + (-index * 100) + '%, 0, 0)';
                    return;
                }
            }
            if (lockedAxis !== 'x') return;
            deltaX = dx;
            var width = carousel.clientWidth || 1;
            var pct = (-index * 100) + (deltaX / width) * 100;
            track.style.transform = 'translate3d(' + pct + '%, 0, 0)';
        }

        function onPointerUp() {
            if (!tracking) {
                track.classList.remove('is-dragging');
                lockedAxis = null;
                activePointerId = null;
                return;
            }
            var wasHorizontal = lockedAxis === 'x';
            tracking = false;
            track.classList.remove('is-dragging');
            if (wasHorizontal) {
                var width = carousel.clientWidth || 1;
                var threshold = Math.min(72, width * 0.18);
                if (deltaX <= -threshold) setIndex(index + 1, true);
                else if (deltaX >= threshold) setIndex(index - 1, true);
                else setIndex(index, true);
            } else {
                setIndex(index, true);
            }
            deltaX = 0;
            lockedAxis = null;
            activePointerId = null;
        }

        carousel.addEventListener('touchstart', function (ev) {
            if (!ev.touches || !ev.touches[0]) return;
            onPointerDown(ev.touches[0].clientX, ev.touches[0].clientY, null);
        }, { passive: true });
        carousel.addEventListener('touchmove', function (ev) {
            if (!ev.touches || !ev.touches[0]) return;
            onPointerMove(ev.touches[0].clientX, ev.touches[0].clientY);
            if (lockedAxis === 'x' && ev.cancelable) ev.preventDefault();
        }, { passive: false });
        carousel.addEventListener('touchend', onPointerUp);
        carousel.addEventListener('touchcancel', onPointerUp);

        carousel.addEventListener('pointerdown', function (ev) {
            if (ev.pointerType === 'touch') return;
            if (ev.button != null && ev.button !== 0) return;
            // Не перехватываем клики по кнопкам внутри карусели.
            if (ev.target && ev.target.closest && (
                ev.target.closest('.ma-audio-modal__carousel-next') ||
                ev.target.closest('.ma-audio-modal__hint-toggle')
            )) {
                return;
            }
            onPointerDown(ev.clientX, ev.clientY, ev.pointerId);
            try {
                carousel.setPointerCapture(ev.pointerId);
            } catch (_e) { /* ignore */ }
        });
        carousel.addEventListener('pointermove', function (ev) {
            if (ev.pointerType === 'touch') return;
            if (!tracking) return;
            if (activePointerId != null && ev.pointerId !== activePointerId) return;
            onPointerMove(ev.clientX, ev.clientY);
        });
        carousel.addEventListener('pointerup', function (ev) {
            if (ev.pointerType === 'touch') return;
            onPointerUp();
        });
        carousel.addEventListener('pointercancel', function (ev) {
            if (ev.pointerType === 'touch') return;
            onPointerUp();
        });

        setIndex(0, false);
        return { setIndex: setIndex, cycleNext: cycleNext };
    }

    function paintExpandedBoard(li, item) {
        if (!li || !item) return;
        var wrap = li.querySelector('.ma-audio-modal__board-wrap');
        if (!wrap) return;
        wrap.innerHTML = '';

        var carousel = document.createElement('div');
        carousel.className = 'ma-audio-modal__carousel';

        var track = document.createElement('div');
        track.className = 'ma-audio-modal__carousel-track';

        var slides = [];

        var boardSlide = document.createElement('div');
        boardSlide.className = 'ma-audio-modal__carousel-slide is-active';
        boardSlide.appendChild(buildBoardPanel(item));
        track.appendChild(boardSlide);
        slides.push(boardSlide);

        var hintsSlide = document.createElement('div');
        hintsSlide.className = 'ma-audio-modal__carousel-slide';
        hintsSlide.appendChild(buildHintsPanel(item));
        track.appendChild(hintsSlide);
        slides.push(hintsSlide);

        carousel.appendChild(track);

        var nextBtn = document.createElement('button');
        nextBtn.type = 'button';
        nextBtn.className = 'ma-audio-modal__carousel-next';
        nextBtn.title = 'Следующий экран';
        nextBtn.setAttribute('aria-label', 'Следующий экран');
        nextBtn.innerHTML = '<i class="fa fa-chevron-right" aria-hidden="true"></i>';
        carousel.appendChild(nextBtn);

        wrap.appendChild(carousel);

        var dotsWrap = document.createElement('div');
        dotsWrap.className = 'ma-audio-modal__carousel-dots';
        var dots = [];
        for (var i = 0; i < slides.length; i++) {
            var dot = document.createElement('span');
            dot.className = 'ma-audio-modal__carousel-dot' + (i === 0 ? ' is-active' : '');
            dotsWrap.appendChild(dot);
            dots.push(dot);
        }
        wrap.appendChild(dotsWrap);

        bindCarousel(carousel, track, slides, dots, nextBtn);
    }

    function toggleExpand(li, item) {
        var key = itemKey(item);
        var wasExpanded = state.expandedKey === key;
        if (listEl) {
            var nodes = listEl.querySelectorAll('.ma-audio-modal__item.is-expanded');
            for (var i = 0; i < nodes.length; i++) {
                nodes[i].classList.remove('is-expanded');
            }
        }
        if (wasExpanded) {
            state.expandedKey = null;
            return;
        }
        state.expandedKey = key;
        li.classList.add('is-expanded');
        paintExpandedBoard(li, item);
        try {
            li.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        } catch (_e) { /* ignore */ }
    }

    function openListModal() {
        if (!listModal) return;
        listModal.classList.add('is-open');
        listModal.setAttribute('aria-hidden', 'false');
        setCabinetFooterHidden(true);
        setConvertProgressVisible();
    }

    function openEditModal(item) {
        stopPlayback();
        state.editItem = item;
        if (editSub) {
            editSub.textContent =
                (state.matchTitle ? state.matchTitle + ' — ' : '') + frameLabel(item) +
                (item.audio_name ? '\nТекущий файл: ' + item.audio_name : '');
        }
        setEditMsg('');
        if (!editModal) return;
        editModal.classList.add('is-open');
        editModal.setAttribute('aria-hidden', 'false');
    }

    function renderList() {
        if (!listEl) return;
        listEl.innerHTML = '';
        if (!state.items.length) {
            var empty = document.createElement('p');
            empty.className = 'ma-audio-modal__empty';
            empty.textContent = 'В этом анализе пока нет прикреплённых аудио';
            listEl.appendChild(empty);
            return;
        }
        state.items.forEach(function (item) {
            var key = itemKey(item);
            var li = document.createElement('li');
            li.className = 'ma-audio-modal__item';
            if (state.expandedKey === key) {
                li.classList.add('is-expanded');
            }

            var row = document.createElement('div');
            row.className = 'ma-audio-modal__row';
            row.title = 'Показать доску хода';

            var meta = document.createElement('div');
            meta.className = 'ma-audio-modal__meta';

            var nameRow = document.createElement('div');
            nameRow.className = 'ma-audio-modal__name-row';

            var playBtn = document.createElement('button');
            playBtn.type = 'button';
            playBtn.className = 'ma-audio-modal__play-btn';
            playBtn.setAttribute('data-audio-key', key);
            setPlayButtonState(
                playBtn,
                !!(
                    state.playingKey &&
                    state.playingKey === key &&
                    state.audioEl &&
                    !state.audioEl.paused
                )
            );
            playBtn.addEventListener('click', function (ev) {
                ev.stopPropagation();
                togglePlayback(item, playBtn);
            });

            var name = document.createElement('span');
            name.className = 'ma-audio-modal__name';
            name.textContent = item.audio_name || 'аудио';
            name.title = item.audio_name || '';
            nameRow.appendChild(playBtn);
            nameRow.appendChild(name);

            var frame = document.createElement('span');
            frame.className = 'ma-audio-modal__frame';
            frame.textContent = frameLabel(item);
            meta.appendChild(nameRow);
            meta.appendChild(frame);

            var actions = document.createElement('div');
            actions.className = 'ma-audio-modal__actions-row';

            var downloadBtn = document.createElement('button');
            downloadBtn.type = 'button';
            downloadBtn.className = 'ma-audio-modal__icon-btn';
            downloadBtn.title = 'Скачать';
            downloadBtn.setAttribute('aria-label', 'Скачать аудио');
            downloadBtn.innerHTML = '<i class="fa fa-download" aria-hidden="true"></i>';
            downloadBtn.addEventListener('click', function (ev) {
                ev.stopPropagation();
                downloadAudioItem(item);
            });

            var redirectBtn = document.createElement('button');
            redirectBtn.type = 'button';
            redirectBtn.className = 'ma-audio-modal__icon-btn';
            redirectBtn.title = 'Перейти к кадру';
            redirectBtn.setAttribute('aria-label', 'Перейти к кадру');
            redirectBtn.innerHTML = '<i class="fa fa-external-link" aria-hidden="true"></i>';
            redirectBtn.addEventListener('click', function (ev) {
                ev.stopPropagation();
                window.location.assign(
                    buildViewUrl(state.matchId, item.game_number, item.move_index)
                );
            });

            var editBtn = document.createElement('button');
            editBtn.type = 'button';
            editBtn.className = 'ma-audio-modal__icon-btn';
            editBtn.title = 'Изменить';
            editBtn.setAttribute('aria-label', 'Изменить аудио');
            editBtn.innerHTML = '<i class="fa fa-pencil" aria-hidden="true"></i>';
            editBtn.addEventListener('click', function (ev) {
                ev.stopPropagation();
                openEditModal(item);
            });

            var delBtn = document.createElement('button');
            delBtn.type = 'button';
            delBtn.className = 'ma-audio-modal__icon-btn ma-audio-modal__icon-btn--danger';
            delBtn.title = 'Удалить';
            delBtn.setAttribute('aria-label', 'Удалить аудио');
            delBtn.innerHTML = '<i class="fa fa-trash" aria-hidden="true"></i>';
            delBtn.addEventListener('click', function (ev) {
                ev.stopPropagation();
                deleteAudio(item);
            });

            actions.appendChild(downloadBtn);
            actions.appendChild(redirectBtn);
            actions.appendChild(editBtn);
            actions.appendChild(delBtn);
            row.appendChild(meta);
            row.appendChild(actions);

            var boardWrap = document.createElement('div');
            boardWrap.className = 'ma-audio-modal__board-wrap';

            row.addEventListener('click', function () {
                toggleExpand(li, item);
            });

            li.appendChild(row);
            li.appendChild(boardWrap);
            listEl.appendChild(li);

            if (state.expandedKey === key) {
                paintExpandedBoard(li, item);
            }
        });
    }

    function patchAudioTotals(matchId, count, minutes) {
        if (typeof api().onAudioCountChanged === 'function') {
            api().onAudioCountChanged(matchId, count, minutes);
        }
    }

    function decodeArrayBufferDurationSec(arrayBuffer) {
        return new Promise(function (resolve) {
            var Ctx = window.AudioContext || window.webkitAudioContext;
            if (!Ctx || !arrayBuffer) {
                resolve(null);
                return;
            }
            var ctx = null;
            var finished = false;
            var finish = function (value) {
                if (finished) return;
                finished = true;
                try {
                    if (ctx && typeof ctx.close === 'function') ctx.close();
                } catch (_e) { /* ignore */ }
                resolve(value);
            };
            try {
                ctx = new Ctx();
            } catch (_e2) {
                resolve(null);
                return;
            }
            var copy = arrayBuffer.slice(0);
            var onOk = function (buf) {
                var d = buf && Number(buf.duration);
                finish(Number.isFinite(d) && d > 0 ? d : null);
            };
            var onErr = function () { finish(null); };
            try {
                // Современные браузеры возвращают Promise; старые — только callbacks.
                var result = ctx.decodeAudioData(copy);
                if (result && typeof result.then === 'function') {
                    result.then(onOk).catch(onErr);
                } else {
                    ctx.decodeAudioData(copy, onOk, onErr);
                }
            } catch (_e3) {
                try {
                    ctx.decodeAudioData(copy, onOk, onErr);
                } catch (_e4) {
                    onErr();
                }
            }
        });
    }

    function measureViaHtmlAudioFromUrl(url, revoke) {
        return new Promise(function (resolve) {
            var audio = new Audio();
            var done = false;
            var finish = function (value) {
                if (done) return;
                done = true;
                if (revoke) {
                    try { URL.revokeObjectURL(url); } catch (_e) { /* ignore */ }
                }
                resolve(value);
            };
            audio.preload = 'metadata';
            audio.onloadedmetadata = function () {
                var d = Number(audio.duration);
                if (Number.isFinite(d) && d > 0 && d !== Infinity) finish(d);
                else finish(null);
            };
            audio.onerror = function () { finish(null); };
            setTimeout(function () { finish(null); }, 10000);
            audio.src = url;
        });
    }

    function measureBlobDurationSec(blob) {
        if (!blob) return Promise.resolve(null);
        return blob.arrayBuffer()
            .then(function (ab) { return decodeArrayBufferDurationSec(ab); })
            .then(function (decoded) {
                if (decoded != null) return decoded;
                var url = '';
                try {
                    url = URL.createObjectURL(blob);
                } catch (_e) {
                    return null;
                }
                return measureViaHtmlAudioFromUrl(url, true);
            })
            .catch(function () { return null; });
    }

    function measureMediaUrlDurationSec(s3Key) {
        if (!s3Key) return Promise.resolve(null);
        var url = mediaUrl(s3Key);
        return fetch(url)
            .then(function (resp) {
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                return resp.arrayBuffer();
            })
            .then(function (ab) { return decodeArrayBufferDurationSec(ab); })
            .then(function (decoded) {
                if (decoded != null) return decoded;
                return measureViaHtmlAudioFromUrl(url, false);
            })
            .catch(function () {
                return measureViaHtmlAudioFromUrl(url, false);
            });
    }

    function totalsFromItems(items) {
        var list = Array.isArray(items) ? items : [];
        var seconds = 0;
        list.forEach(function (it) {
            var d = Number(it && it.duration_sec);
            if (Number.isFinite(d) && d > 0) seconds += d;
        });
        return {
            count: list.length,
            seconds: seconds,
            minutes: Math.floor(seconds / 60),
        };
    }

    function backfillMissingDurations(items) {
        var missing = (items || []).filter(function (it) {
            var d = Number(it && it.duration_sec);
            return it && it.audio_s3_key && !(Number.isFinite(d) && d > 0);
        });
        if (!missing.length) {
            return Promise.resolve(false);
        }
        if (!hasAuth() || !state.matchId) {
            return Promise.resolve(false);
        }
        return Promise.all(
            missing.map(function (it) {
                return measureMediaUrlDurationSec(it.audio_s3_key).then(function (dur) {
                    return dur
                        ? {
                            game_number: it.game_number,
                            move_index: it.move_index,
                            duration_sec: dur,
                        }
                        : null;
                });
            })
        ).then(function (measured) {
            var payloadItems = measured.filter(Boolean);
            if (!payloadItems.length) return false;
            return fetch('/api/match_analysis/audio/set_durations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(authPayload({id: state.matchId,
                    items: payloadItems,})),
            })
                .then(function (resp) {
                    return resp.json().catch(function () { return {}; }).then(function (payload) {
                        if (!resp.ok) {
                            throw new Error(payload.detail || ('HTTP ' + resp.status));
                        }
                        return payload;
                    });
                })
                .then(function (payload) {
                    var byKey = {};
                    payloadItems.forEach(function (it) {
                        byKey[String(it.game_number) + ':' + String(it.move_index)] = it.duration_sec;
                    });
                    state.items.forEach(function (it) {
                        var key = String(it.game_number) + ':' + String(it.move_index);
                        if (byKey[key] != null) {
                            it.duration_sec = byKey[key];
                        }
                    });
                    var totals = totalsFromItems(state.items);
                    if (payload && payload.audio_minutes != null) {
                        totals.minutes = Math.floor(Number(payload.audio_minutes) || 0);
                    }
                    patchAudioTotals(state.matchId, totals.count, totals.minutes);
                    return true;
                })
                .catch(function (err) {
                    console.warn('audio duration backfill failed', err);
                    return false;
                });
        });
    }

    function loadAudios() {
        if (!requireAuth() || !state.matchId) {
            if (!state.matchId) setListMsg('Нет ID матча', true);
            return Promise.resolve();
        }
        setListMsg('Загрузка…');
        return fetch('/api/match_analysis/audio/list', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(authPayload({ id: state.matchId })),
        })
            .then(function (resp) {
                return resp.json().catch(function () { return {}; }).then(function (payload) {
                    if (!resp.ok) {
                        throw new Error(payload.detail || ('HTTP ' + resp.status));
                    }
                    return payload;
                });
            })
            .then(function (payload) {
                state.items = Array.isArray(payload.items) ? payload.items : [];
                setListMsg(state.items.length ? ('Файлов: ' + state.items.length) : '');
                if (listSub) {
                    listSub.textContent = state.matchTitle
                        ? ('Матч: ' + state.matchTitle)
                        : ('ID #' + String(state.matchId));
                }
                renderList();
                var totals = totalsFromItems(state.items);
                if (payload.audio_minutes != null) {
                    totals.minutes = Math.floor(Number(payload.audio_minutes) || 0);
                }
                patchAudioTotals(state.matchId, totals.count, totals.minutes);
                return backfillMissingDurations(state.items);
            })
            .catch(function (err) {
                console.error(err);
                state.items = [];
                renderList();
                setListMsg('Ошибка загрузки: ' + (err.message || err), true);
            });
    }

    function ensureAllCardMinutes(cards) {
        if (!hasAuth()) return Promise.resolve();
        var ids = [];
        var seen = {};
        (cards || []).forEach(function (row) {
            var count = Number(row && row.audio_count) || 0;
            var idNum = Number(row && row.content_card_id);
            if (count <= 0 || !idNum || seen[idNum]) return;
            seen[idNum] = true;
            ids.push(idNum);
        });
        if (!ids.length) return Promise.resolve();

        return fetch('/api/match_analysis/audio/ensure_durations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(authPayload({ids: ids})),
        })
            .then(function (resp) {
                return resp.json().catch(function () { return {}; }).then(function (payload) {
                    if (!resp.ok) {
                        throw new Error(payload.detail || ('HTTP ' + resp.status));
                    }
                    return payload;
                });
            })
            .then(function (payload) {
                var items = Array.isArray(payload.items) ? payload.items : [];
                // Сразу обновляем минуты по серверному probe.
                items.forEach(function (it) {
                    patchAudioTotals(
                        it.id,
                        it.audio_count,
                        it.audio_minutes
                    );
                });

                // Оставшиеся webm без duration — последовательно на клиенте.
                var pending = items.filter(function (it) {
                    return Array.isArray(it.missing) && it.missing.length > 0;
                });
                var chain = Promise.resolve();
                pending.forEach(function (it) {
                    chain = chain.then(function () {
                        return Promise.all(
                            it.missing.map(function (m) {
                                return measureMediaUrlDurationSec(m.audio_s3_key).then(function (dur) {
                                    return dur
                                        ? {
                                            game_number: m.game_number,
                                            move_index: m.move_index,
                                            duration_sec: dur,
                                        }
                                        : null;
                                });
                            })
                        ).then(function (measured) {
                            var payloadItems = measured.filter(Boolean);
                            if (!payloadItems.length) return;
                            return fetch('/api/match_analysis/audio/set_durations', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify(authPayload({id: it.id,
                                    items: payloadItems,})),
                            })
                                .then(function (resp) {
                                    return resp.json().catch(function () { return {}; }).then(function (body) {
                                        if (!resp.ok) {
                                            throw new Error(body.detail || ('HTTP ' + resp.status));
                                        }
                                        return body;
                                    });
                                })
                                .then(function (body) {
                                    if (body && body.audio_minutes != null) {
                                        patchAudioTotals(
                                            it.id,
                                            body.audio_count != null ? body.audio_count : it.audio_count,
                                            body.audio_minutes
                                        );
                                    }
                                })
                                .catch(function (err) {
                                    console.warn('client duration fill failed', it.id, err);
                                });
                        });
                    });
                });
                return chain;
            })
            .catch(function (err) {
                console.warn('ensureAllCardMinutes failed', err);
            });
    }

    function ensureMinutes(matchId) {
        return ensureAllCardMinutes([{ content_card_id: matchId, audio_count: 1 }]);
    }

    function downloadAudioItem(item) {
        if (!item || state.busy || state.matchId == null || item.move_index == null) return;
        if (!requireAuth()) return;
        var initData = getInitData();
        chooseExportFormat({
            subtitle: 'Выберите формат файла для скачивания',
        }).then(function (fmt) {
            if (!fmt) return;
            startSingleAudioDownload(item, initData, fmt);
        });
    }

    function startSingleAudioDownload(item, initData, fmt) {
        fmt = normalizeExportFormat(fmt);
        saveExportFormat(fmt);
        var matchId = state.matchId;
        var fallbackName = String(item.audio_name || 'audio.webm').split(/[\\/]/).pop() || 'audio.webm';
        var stem = fallbackName.replace(/\.[^.]+$/, '') || 'audio';
        var formatLabel = fmt === 'mp3' ? 'MP3' : 'WAV';
        var ext = fmt === 'mp3' ? '.mp3' : '.wav';
        setZipBusy(true);
        startConvertEstimate('Конвертация в ' + formatLabel + '…', {
            files: 1,
            msPerFile: fmt === 'mp3' ? 4200 : 3800,
        });
        fetch('/api/match_analysis/audio/download_mp3', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(authPayload({id: matchId,
                game_number: item.game_number,
                move_index: item.move_index,
                format: fmt,})),
        })
            .then(function (resp) {
                return resp.json().catch(function () { return {}; }).then(function (payload) {
                    if (!resp.ok) {
                        var detail = payload.detail || ('HTTP ' + resp.status);
                        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
                    }
                    return payload;
                });
            })
            .then(function (payload) {
                completeConvertEstimate();
                var url = payload && payload.url ? String(payload.url) : '';
                var filename = (payload && payload.file_name)
                    ? String(payload.file_name)
                    : (stem + ext);
                var downloadName = (payload && payload.download_file_name)
                    ? String(payload.download_file_name)
                    : filename;
                if (!url) {
                    throw new Error('Сервер не вернул ссылку для скачивания');
                }
                return requestTelegramDownload(url, filename, { downloadFileName: downloadName });
            })
            .then(function () {
                if (isListModalOpen() && state.matchId === matchId) {
                    setListMsg(state.items.length ? ('Файлов: ' + state.items.length) : '');
                }
            })
            .catch(function (err) {
                console.error(err);
                if (isListModalOpen() && state.matchId === matchId) {
                    setListMsg('Ошибка скачивания: ' + (err.message || err), true);
                }
                showNotice('Не удалось скачать ' + formatLabel + ': ' + (err.message || err), 'Ошибка');
            })
            .finally(function () {
                setZipBusy(false);
            });
    }

    function deleteAudio(item) {
        if (!item || state.busy) return;
        showConfirm(
            'Удалить аудио «' + (item.audio_name || 'файл') + '» с кадра «' + frameLabel(item) + '»?',
            'Удаление аудио',
            { confirmLabel: 'Удалить', danger: true }
        ).then(function (ok) {
            if (!ok) return;
            if (!requireAuth()) return;
            state.busy = true;
            setListMsg('Удаление…');
            fetch('/api/match_analysis/audio/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(authPayload({
                    id: state.matchId,
                    game_number: item.game_number,
                    move_index: item.move_index,
                    delete_s3: true,
                })),
            })
                .then(function (resp) {
                    return resp.json().catch(function () { return {}; }).then(function (payload) {
                        if (!resp.ok) {
                            throw new Error(payload.detail || ('HTTP ' + resp.status));
                        }
                        return payload;
                    });
                })
                .then(function () {
                    return loadAudios();
                })
                .catch(function (err) {
                    console.error(err);
                    setListMsg('Ошибка удаления: ' + (err.message || err), true);
                    showNotice('Ошибка удаления аудио: ' + (err.message || err), 'Ошибка');
                })
                .finally(function () {
                    state.busy = false;
                });
        });
    }

    function uploadBlob(blob, filename, preferredDurationSec) {
        var item = state.editItem;
        var initData = getInitData();
        if (!item || !state.matchId) {
            setEditMsg('Не выбран кадр', true);
            return Promise.resolve();
        }
        if (!hasAuth()) {
            setEditMsg('Нет данных авторизации', true);
            return Promise.resolve();
        }
        state.busy = true;
        setEditMsg('Загрузка…');
        if (editAttachBtn) editAttachBtn.disabled = true;
        if (editRecordBtn) editRecordBtn.disabled = true;

        var preferred = Number(preferredDurationSec);
        var durationPromise = (Number.isFinite(preferred) && preferred > 0)
            ? Promise.resolve(preferred)
            : measureBlobDurationSec(blob);

        return durationPromise.then(function (durationSec) {
            var fd = new FormData();
            if (initData) fd.append('init_data', initData);
            if (getFabToken()) fd.append('fab_token', getFabToken());
            fd.append('match_analysis_id', String(state.matchId));
            fd.append('game_number', String(item.game_number));
            fd.append('move_index', String(item.move_index));
            fd.append('file', blob, filename || 'audio.webm');
            if (durationSec != null && Number.isFinite(Number(durationSec)) && Number(durationSec) > 0) {
                fd.append('duration_sec', String(durationSec));
            }

            return fetch('/api/match_analysis/audio/upload', {
                method: 'POST',
                body: fd,
            })
                .then(function (resp) {
                    return resp.json().catch(function () { return {}; }).then(function (payload) {
                        if (!resp.ok) {
                            var detail = payload.detail || ('HTTP ' + resp.status);
                            throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
                        }
                        return payload;
                    });
                })
                .then(function (payload) {
                    if (payload && payload.audio_minutes != null) {
                        patchAudioTotals(
                            state.matchId,
                            payload.count != null ? payload.count : null,
                            payload.audio_minutes
                        );
                    }
                    closeEditModal();
                    return loadAudios().then(function () {
                        showNotice('Аудио обновлено', 'Готово');
                    });
                });
        })
            .catch(function (err) {
                console.error(err);
                setEditMsg('Ошибка: ' + (err.message || err), true);
                showNotice('Ошибка загрузки аудио: ' + (err.message || err), 'Ошибка');
            })
            .finally(function () {
                state.busy = false;
                if (editAttachBtn) editAttachBtn.disabled = false;
                if (editRecordBtn) editRecordBtn.disabled = false;
            });
    }

    function stopRecordingIfNeeded() {
        if (state.mediaRecorder && state.mediaRecorder.state === 'recording') {
            try {
                state.mediaRecorder.stop();
            } catch (_e) { /* ignore */ }
        }
        state.mediaRecorder = null;
        state.recordChunks = [];
        state.recordStartedAt = null;
    }

    function startOrStopRecording() {
        if (state.busy) return;
        if (state.mediaRecorder && state.mediaRecorder.state === 'recording') {
            state.mediaRecorder.stop();
            return;
        }
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            setEditMsg('Запись не поддерживается в этом браузере', true);
            return;
        }
        navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
            state.recordChunks = [];
            state.recordStartedAt = Date.now();
            var mimeCandidates = [
                'audio/ogg;codecs=opus',
                'audio/ogg',
                'audio/webm;codecs=opus',
                'audio/webm',
            ];
            var mime = '';
            for (var i = 0; i < mimeCandidates.length; i++) {
                if (window.MediaRecorder && MediaRecorder.isTypeSupported(mimeCandidates[i])) {
                    mime = mimeCandidates[i];
                    break;
                }
            }
            state.mediaRecorder = mime
                ? new MediaRecorder(stream, { mimeType: mime })
                : new MediaRecorder(stream);
            state.mediaRecorder.ondataavailable = function (e) {
                if (e.data && e.data.size) state.recordChunks.push(e.data);
            };
            state.mediaRecorder.onstop = function () {
                try {
                    stream.getTracks().forEach(function (t) { t.stop(); });
                } catch (_e) { /* ignore */ }
                if (editRecordBtn) {
                    editRecordBtn.classList.remove('is-recording');
                    editRecordBtn.innerHTML = '<i class="fa fa-microphone" aria-hidden="true"></i> Записать';
                }
                var wallSec = null;
                if (state.recordStartedAt) {
                    wallSec = (Date.now() - state.recordStartedAt) / 1000;
                }
                state.recordStartedAt = null;
                var blobType = (state.mediaRecorder && state.mediaRecorder.mimeType) || mime || 'audio/webm';
                var blob = new Blob(state.recordChunks, { type: blobType });
                state.recordChunks = [];
                state.mediaRecorder = null;
                if (!blob.size) {
                    setEditMsg('Пустая запись', true);
                    return;
                }
                var ext = blobType.indexOf('ogg') >= 0 ? 'ogg' : 'webm';
                uploadBlob(blob, 'voice_' + Date.now() + '.' + ext, wallSec);
            };
            state.mediaRecorder.start();
            if (editRecordBtn) {
                editRecordBtn.classList.add('is-recording');
                editRecordBtn.innerHTML = '<i class="fa fa-stop" aria-hidden="true"></i> Стоп';
            }
            setEditMsg('Идёт запись… нажмите «Стоп», чтобы сохранить');
        }).catch(function (err) {
            console.error(err);
            setEditMsg('Нет доступа к микрофону: ' + (err.message || err), true);
        });
    }

    var convertProgress = {
        timer: null,
        label: '',
        pct: 0,
        startedAt: 0,
        expectedMs: 0,
    };

    function isListModalOpen() {
        return !!(listModal && listModal.classList.contains('is-open'));
    }

    function setProgressBarPct(pct) {
        if (!listProgressBar) return;
        var v = Math.max(0, Math.min(100, Number(pct) || 0));
        listProgressBar.style.width = v + '%';
    }

    function formatConvertMsg(label, pct) {
        var p = Math.max(0, Math.min(99, Math.floor(Number(pct) || 0)));
        return String(label || 'Конвертация…') + ' ' + p + '%';
    }

    function refreshConvertMsg() {
        if (!state.convertActive || !convertProgress.label) return;
        if (!isListModalOpen()) return;
        setListMsg(formatConvertMsg(convertProgress.label, convertProgress.pct));
    }

    function stopConvertEstimate() {
        if (convertProgress.timer) {
            clearInterval(convertProgress.timer);
            convertProgress.timer = null;
        }
        convertProgress.label = '';
        convertProgress.pct = 0;
        convertProgress.startedAt = 0;
        convertProgress.expectedMs = 0;
        setProgressBarPct(0);
    }

    function startConvertEstimate(label, opts) {
        stopConvertEstimate();
        var files = Math.max(1, Math.floor(Number(opts && opts.files) || 1));
        var msPerFile = Math.max(800, Number(opts && opts.msPerFile) || 2800);
        convertProgress.label = String(label || 'Конвертация…');
        convertProgress.startedAt = Date.now();
        convertProgress.expectedMs = Math.max(2200, files * msPerFile);
        convertProgress.pct = 1;
        setProgressBarPct(1);
        refreshConvertMsg();
        convertProgress.timer = setInterval(function () {
            if (!state.convertActive) return;
            var elapsed = Date.now() - convertProgress.startedAt;
            // Асимптота к ~95%: примерный прогресс, пока сервер не ответил.
            var raw = 1 - Math.exp((-elapsed / convertProgress.expectedMs) * 2.15);
            var pct = Math.min(95, Math.max(1, Math.floor(raw * 95)));
            if (pct < convertProgress.pct) pct = convertProgress.pct;
            if (pct === convertProgress.pct && convertProgress.pct < 95 && elapsed > convertProgress.expectedMs) {
                pct = Math.min(95, convertProgress.pct + 1);
            }
            if (pct === convertProgress.pct) return;
            convertProgress.pct = pct;
            setProgressBarPct(pct);
            refreshConvertMsg();
        }, 250);
    }

    function completeConvertEstimate() {
        if (convertProgress.timer) {
            clearInterval(convertProgress.timer);
            convertProgress.timer = null;
        }
        convertProgress.pct = 100;
        setProgressBarPct(100);
        if (state.convertActive && convertProgress.label && isListModalOpen()) {
            setListMsg(String(convertProgress.label) + ' 100%');
        }
    }

    function setConvertProgressVisible(force) {
        if (!listProgress) return;
        var show = (force != null) ? !!force : (!!state.convertActive && isListModalOpen());
        listProgress.hidden = !show;
        listProgress.setAttribute('aria-hidden', show ? 'false' : 'true');
        if (show) {
            setProgressBarPct(convertProgress.pct || 1);
            refreshConvertMsg();
        }
    }

    function setZipBusy(isBusy) {
        state.busy = !!isBusy;
        state.convertActive = !!isBusy;
        if (listImportBtn) listImportBtn.disabled = !!isBusy;
        if (listExportBtn) listExportBtn.disabled = !!isBusy;
        // «Закрыть» не блокируем — закрытие модалки не отменяет конвертацию.
        if (listCloseBtn) listCloseBtn.disabled = false;
        if (!isBusy) {
            stopConvertEstimate();
        }
        setConvertProgressVisible();
    }

    function sleepMs(ms) {
        return new Promise(function (resolve) {
            setTimeout(resolve, ms);
        });
    }

    function downloadViaFetchBlob(absUrl, safeName, attempt, maxAttempts) {
        attempt = attempt || 0;
        maxAttempts = maxAttempts || 4;
        return fetch(absUrl, { credentials: 'same-origin', cache: 'no-store' })
            .then(function (resp) {
                if (!resp.ok) {
                    throw new Error('HTTP ' + resp.status);
                }
                return resp.blob();
            })
            .then(function (blob) {
                if (!blob || !blob.size) {
                    throw new Error('Пустой файл');
                }
                var objectUrl = URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.href = objectUrl;
                a.setAttribute('download', safeName);
                a.rel = 'noopener noreferrer';
                document.body.appendChild(a);
                a.click();
                a.remove();
                setTimeout(function () {
                    URL.revokeObjectURL(objectUrl);
                }, 60000);
            })
            .catch(function (err) {
                if (attempt + 1 < maxAttempts) {
                    var delay = Math.min(12000, 1500 * Math.pow(2, attempt));
                    return sleepMs(delay).then(function () {
                        return downloadViaFetchBlob(absUrl, safeName, attempt + 1, maxAttempts);
                    });
                }
                throw err;
            });
    }

    function toTelegramFileName(name) {
        var safe = String(name || 'file').replace(/[\\/]/g, '_').trim() || 'file';
        var ascii = safe
            .replace(/[^\x20-\x7E._-]+/g, '_')
            .replace(/_+/g, '_')
            .replace(/^[._]+|[._]+$/g, '');
        if (ascii) return ascii;
        if (/\.zip$/i.test(safe)) return 'download.zip';
        if (/\.wav$/i.test(safe)) return 'download.wav';
        if (/\.mp3$/i.test(safe)) return 'download.mp3';
        return 'download.bin';
    }

    function verifyDownloadUrl(absUrl) {
        return fetch(absUrl, {
            method: 'HEAD',
            credentials: 'same-origin',
            cache: 'no-store',
        }).then(function (resp) {
            if (!resp.ok) {
                throw new Error('Файл недоступен (HTTP ' + resp.status + ')');
            }
            var len = resp.headers.get('content-length');
            if (len !== null && Number(len) <= 0) {
                throw new Error('Пустой файл на сервере');
            }
        });
    }

    function shouldPreferFetchBlobDownload() {
        var tw = window.Telegram && window.Telegram.WebApp;
        if (!tw) return true;
        var p = String(tw.platform || '').toLowerCase();
        return p === 'web' || p === 'weba' || p === 'unknown' || !p;
    }

    function requestTelegramDownload(path, fileName, opts) {
        opts = opts || {};
        if (!path) {
            return Promise.reject(new Error('Нет ссылки для скачивания'));
        }
        var tgName = toTelegramFileName(opts.downloadFileName || fileName);
        var absUrl;
        try {
            absUrl = new URL(path, window.location.href).href;
        } catch (_e) {
            absUrl = path;
        }

        return verifyDownloadUrl(absUrl).then(function () {
            if (shouldPreferFetchBlobDownload()) {
                return downloadViaFetchBlob(absUrl, tgName).then(function () {
                    return { via: 'blob' };
                });
            }
            var tw = window.Telegram && window.Telegram.WebApp;
            if (tw && typeof tw.downloadFile === 'function') {
                return new Promise(function (resolve, reject) {
                    try {
                        tw.downloadFile({ url: absUrl, file_name: tgName }, function (accepted) {
                            if (accepted === false) {
                                downloadViaFetchBlob(absUrl, tgName)
                                    .then(function () { resolve({ via: 'blob' }); })
                                    .catch(reject);
                                return;
                            }
                            resolve({ via: 'telegram' });
                        });
                    } catch (err) {
                        downloadViaFetchBlob(absUrl, tgName)
                            .then(function () { resolve({ via: 'blob' }); })
                            .catch(reject);
                    }
                });
            }
            return downloadViaFetchBlob(absUrl, tgName).then(function () {
                return { via: 'blob' };
            });
        });
    }

    function pollExportJob(jobId, initData) {
        var pollMs = 2000;
        var maxWaitMs = 45 * 60 * 1000;
        var startedAt = Date.now();

        function pollOnce() {
            if (Date.now() - startedAt > maxWaitMs) {
                return Promise.reject(new Error('Превышено время ожидания экспорта'));
            }
            return fetch('/api/match_analysis/audio/export_job_status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(authPayload({job_id: jobId})),
            })
                .then(function (resp) {
                    return resp.json().catch(function () { return {}; }).then(function (payload) {
                        if (!resp.ok) {
                            var detail = payload.detail || ('HTTP ' + resp.status);
                            throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
                        }
                        return payload;
                    });
                })
                .then(function (payload) {
                    var status = String((payload && payload.status) || '').toLowerCase();
                    if (status === 'ready') {
                        return payload;
                    }
                    if (status === 'error') {
                        throw new Error(String((payload && payload.error) || 'Ошибка экспорта'));
                    }
                    var prog = Number(payload && payload.progress);
                    if (Number.isFinite(prog) && prog > convertProgress.pct && prog < 100) {
                        convertProgress.pct = prog;
                        setProgressBarPct(prog);
                        refreshConvertMsg();
                    }
                    return sleepMs(pollMs).then(pollOnce);
                });
        }

        return pollOnce();
    }

    function downloadImportMp3Zip() {
        if (state.busy || !state.matchId) return;
        if (!requireAuth()) return;
        var initData = getInitData();
        if (!state.items.length) {
            showNotice('В этом анализе нет аудио для экспорта', 'Экспорт');
            return;
        }
        chooseExportFormat({
            subtitle: 'Выберите формат файлов в ZIP',
        }).then(function (fmt) {
            if (!fmt) return;
            startZipExport(fmt, initData);
        });
    }

    function normalizeExportFormat(raw) {
        var fmt = String(raw || '').trim().toLowerCase();
        return fmt === 'mp3' ? 'mp3' : 'wav';
    }

    function getSavedExportFormat() {
        try {
            return normalizeExportFormat(localStorage.getItem(EXPORT_FORMAT_LS_KEY) || 'wav');
        } catch (_e) {
            return 'wav';
        }
    }

    function saveExportFormat(fmt) {
        try {
            localStorage.setItem(EXPORT_FORMAT_LS_KEY, normalizeExportFormat(fmt));
        } catch (_e) { }
    }

    function setExportFormatRadios(fmt) {
        var value = normalizeExportFormat(fmt);
        var radios = document.querySelectorAll('input[name="maAudioExportFormat"]');
        Array.prototype.forEach.call(radios, function (radio) {
            radio.checked = String(radio.value) === value;
        });
    }

    function getSelectedExportFormat() {
        var checked = document.querySelector('input[name="maAudioExportFormat"]:checked');
        return normalizeExportFormat(checked && checked.value);
    }

    function closeExportFormatModal(result) {
        if (exportFormatModal) {
            exportFormatModal.classList.remove('is-open');
            exportFormatModal.setAttribute('aria-hidden', 'true');
        }
        var resolve = exportFormatResolver;
        exportFormatResolver = null;
        if (resolve) resolve(result || null);
    }

    function chooseExportFormat(options) {
        var opts = options || {};
        var subtitle = opts.subtitle
            ? String(opts.subtitle)
            : 'Выберите формат файлов в ZIP';
        return new Promise(function (resolve) {
            if (!exportFormatModal) {
                resolve(getSavedExportFormat());
                return;
            }
            if (exportFormatResolver) {
                exportFormatResolver(null);
            }
            exportFormatResolver = resolve;
            setExportFormatRadios(getSavedExportFormat());
            var subEl = document.getElementById('maAudioExportFormatSub');
            if (subEl) subEl.textContent = subtitle;
            exportFormatModal.classList.add('is-open');
            exportFormatModal.setAttribute('aria-hidden', 'false');
        });
    }

    function startZipExport(fmt, initData) {
        fmt = normalizeExportFormat(fmt);
        saveExportFormat(fmt);
        var matchId = state.matchId;
        var fileCount = Math.max(1, state.items.length || 1);
        var formatLabel = fmt === 'mp3' ? 'MP3' : 'WAV';
        setZipBusy(true);
        startConvertEstimate('Экспорт: конвертация в ' + formatLabel + '…', {
            files: fileCount,
            msPerFile: fmt === 'mp3' ? 3600 : 3000,
        });
        fetch('/api/match_analysis/audio/import_mp3_zip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(authPayload({id: matchId, format: fmt})),
        })
            .then(function (resp) {
                return resp.json().catch(function () { return {}; }).then(function (payload) {
                    if (!resp.ok) {
                        var detail = payload.detail || ('HTTP ' + resp.status);
                        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
                    }
                    return payload;
                });
            })
            .then(function (payload) {
                var jobId = payload && payload.job_id ? String(payload.job_id) : '';
                if (jobId) {
                    if (isListModalOpen() && state.matchId === matchId) {
                        setListMsg('Экспорт: конвертация на сервере…');
                    }
                    return pollExportJob(jobId, initData);
                }
                if (payload && payload.url) {
                    return Promise.resolve(payload);
                }
                throw new Error('Сервер не вернул задачу экспорта');
            })
            .then(function (payload) {
                completeConvertEstimate();
                var url = payload && payload.url ? String(payload.url) : '';
                var filename = (payload && payload.file_name)
                    ? String(payload.file_name)
                    : ('match_' + matchId + '_audio_' + fmt + '.zip');
                var downloadName = (payload && payload.download_file_name)
                    ? String(payload.download_file_name)
                    : filename;
                if (!url) {
                    throw new Error('Сервер не вернул ссылку для скачивания');
                }
                if (isListModalOpen() && state.matchId === matchId) {
                    setListMsg('Экспорт: скачивание ZIP…');
                }
                return requestTelegramDownload(url, filename, { downloadFileName: downloadName })
                    .then(function (result) {
                        return { result: result, formatLabel: formatLabel };
                    });
            })
            .then(function (pack) {
                var result = pack && pack.result;
                var formatLabel = (pack && pack.formatLabel) || 'WAV';
                if (isListModalOpen() && state.matchId === matchId) {
                    setListMsg(
                        result && result.via === 'blob'
                            ? 'Экспорт готов: ZIP скачан'
                            : 'Скачивание запущено в Telegram'
                    );
                }
                showNotice(
                    result && result.via === 'blob'
                        ? ('ZIP с ' + formatLabel + ' скачан')
                        : 'Скачивание запущено — проверьте загрузки Telegram',
                    'Экспорт'
                );
            })
            .catch(function (err) {
                console.error(err);
                if (isListModalOpen() && state.matchId === matchId) {
                    setListMsg('Ошибка экспорта: ' + (err.message || err), true);
                }
                showNotice('Ошибка экспорта: ' + (err.message || err), 'Ошибка');
            })
            .finally(function () {
                setZipBusy(false);
            });
    }

    function uploadExportMp3Zip(file) {
        if (state.busy || !state.matchId || !file) return;
        if (!requireAuth()) return;
        var initData = getInitData();
        var matchId = state.matchId;
        var approxFiles = Math.max(
            1,
            state.items.length || Math.round((Number(file.size) || 400000) / 400000)
        );
        setZipBusy(true);
        startConvertEstimate('Импорт: конвертация WAV/MP3 → WebM…', {
            files: approxFiles,
            msPerFile: 3400,
        });
        var fd = new FormData();
        fd.append('init_data', initData || '');
            if (getFabToken()) fd.append('fab_token', getFabToken());
        fd.append('match_analysis_id', String(matchId));
        fd.append('file', file, file.name || 'audio.zip');
        fetch('/api/match_analysis/audio/export_mp3_zip', {
            method: 'POST',
            body: fd,
        })
            .then(function (resp) {
                return resp.json().catch(function () { return {}; }).then(function (payload) {
                    if (!resp.ok) {
                        var detail = payload.detail || ('HTTP ' + resp.status);
                        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
                    }
                    return payload;
                });
            })
            .then(function (payload) {
                completeConvertEstimate();
                if (payload.audio_minutes != null) {
                    patchAudioTotals(
                        matchId,
                        payload.audio_count,
                        payload.audio_minutes
                    );
                }
                var skipped = Array.isArray(payload.skipped) ? payload.skipped : [];
                var msg = 'Заменено: ' + String(payload.replaced || 0);
                if (skipped.length) {
                    msg += ', пропущено: ' + skipped.length;
                }
                if (isListModalOpen() && state.matchId === matchId) {
                    setListMsg(msg);
                }
                showNotice(msg, 'Импорт');
                if (state.matchId === matchId) {
                    return loadAudios();
                }
            })
            .catch(function (err) {
                console.error(err);
                if (isListModalOpen() && state.matchId === matchId) {
                    setListMsg('Ошибка импорта: ' + (err.message || err), true);
                }
                showNotice('Ошибка импорта: ' + (err.message || err), 'Ошибка');
            })
            .finally(function () {
                setZipBusy(false);
            });
    }

    function openForMatch(matchId, matchTitle) {
        var idNum = Number(matchId);
        if (!idNum) return;
        state.matchId = idNum;
        state.matchTitle = String(matchTitle || '').trim();
        if (listTitle) {
            listTitle.textContent = 'Аудиофайлы анализа';
        }
        if (listSub) {
            listSub.textContent = state.matchTitle
                ? ('Матч: ' + state.matchTitle)
                : ('ID #' + String(idNum));
        }
        openListModal();
        loadAudios();
    }

    if (listOverlay) listOverlay.addEventListener('click', closeListModal);
    if (listCloseBtn) listCloseBtn.addEventListener('click', closeListModal);
    if (listImportBtn) listImportBtn.addEventListener('click', downloadImportMp3Zip);
    if (exportFormatOverlay) {
        exportFormatOverlay.addEventListener('click', function () {
            closeExportFormatModal(null);
        });
    }
    if (exportFormatCancelBtn) {
        exportFormatCancelBtn.addEventListener('click', function () {
            closeExportFormatModal(null);
        });
    }
    if (exportFormatConfirmBtn) {
        exportFormatConfirmBtn.addEventListener('click', function () {
            closeExportFormatModal(getSelectedExportFormat());
        });
    }
    if (listExportBtn) {
        listExportBtn.addEventListener('click', function () {
            if (state.busy) return;
            if (listExportFileInput) listExportFileInput.click();
        });
    }
    if (listExportFileInput) {
        listExportFileInput.addEventListener('change', function (ev) {
            var file = ev.target && ev.target.files && ev.target.files[0];
            if (ev.target) ev.target.value = '';
            if (!file) return;
            uploadExportMp3Zip(file);
        });
    }
    if (editOverlay) editOverlay.addEventListener('click', closeEditModal);
    if (editCloseBtn) editCloseBtn.addEventListener('click', closeEditModal);
    if (editAttachBtn) {
        editAttachBtn.addEventListener('click', function () {
            if (state.busy) return;
            if (editFileInput) editFileInput.click();
        });
    }
    if (editRecordBtn) {
        editRecordBtn.addEventListener('click', startOrStopRecording);
    }
    if (editFileInput) {
        editFileInput.addEventListener('change', function (ev) {
            var file = ev.target && ev.target.files && ev.target.files[0];
            if (ev.target) ev.target.value = '';
            if (!file) return;
            uploadBlob(file, file.name || 'audio.webm');
        });
    }

    window.CardsCabinetMatchAudio = {
        open: openForMatch,
        close: closeListModal,
        ensureMinutes: ensureMinutes,
        ensureAllCardMinutes: ensureAllCardMinutes,
    };
})();
