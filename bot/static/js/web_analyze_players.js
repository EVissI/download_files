(function () {
    var cfg = window.WebAnalyzePlayerStatsConfig || {};
    if (!cfg.enabled) return;

    var apiBase = cfg.apiBase || '/web/analyze';
    var isAdmin = !!cfg.isAdmin;
    var uploadsPanel = document.getElementById('analyzeUploadsPanel');
    var playersPanel = document.getElementById('analyzePlayersPanel');
    var ownerSelect = document.getElementById('playerStatsOwner');
    var playerSelect = document.getElementById('playerStatsSelect');
    var lastInput = document.getElementById('playerStatsLast');
    var showBtn = document.getElementById('playerStatsShowBtn');
    var excelBtn = document.getElementById('playerStatsExcelBtn');
    var resultEl = document.getElementById('playerStatsResult');
    var tabs = document.querySelectorAll('[data-analyze-tab]');
    var players = [];
    var currentTab = 'uploads';

    function setMsg(text, muted) {
        if (!resultEl) return;
        resultEl.textContent = text || '';
        resultEl.classList.toggle('muted', !!muted);
    }

    function ownerParam() {
        if (!isAdmin || !ownerSelect) return '';
        var value = String(ownerSelect.value || '').trim();
        return value ? ('owner_user_id=' + encodeURIComponent(value)) : '';
    }

    function withOwner(url) {
        var extra = ownerParam();
        if (!extra) return url;
        return url + (url.indexOf('?') === -1 ? '?' : '&') + extra;
    }

    function setTab(tab) {
        currentTab = tab === 'players' ? 'players' : 'uploads';
        tabs.forEach(function (btn) {
            btn.classList.toggle('is-active', btn.getAttribute('data-analyze-tab') === currentTab);
        });
        if (uploadsPanel) uploadsPanel.hidden = currentTab !== 'uploads';
        if (playersPanel) playersPanel.hidden = currentTab !== 'players';
        if (currentTab === 'players') {
            loadPlayers();
        }
        try {
            if (currentTab === 'players') {
                history.replaceState(null, '', '#stats');
            } else if (location.hash === '#stats' || location.hash === '#players') {
                history.replaceState(null, '', location.pathname + location.search);
            }
        } catch (e) {}
    }

    function selectedPlayerName() {
        if (!playerSelect) return '';
        return String(playerSelect.value || '').trim();
    }

    function fillPlayers(list) {
        players = Array.isArray(list) ? list : [];
        if (!playerSelect) return;
        var prev = selectedPlayerName();
        playerSelect.innerHTML = '';
        if (!players.length) {
            var empty = document.createElement('option');
            empty.value = '';
            empty.textContent = 'Нет игроков';
            playerSelect.appendChild(empty);
            setMsg('Пока нет игроков. Загрузите матч на анализ.', true);
            return;
        }
        players.forEach(function (row) {
            var opt = document.createElement('option');
            opt.value = row.name_norm || row.name || '';
            opt.textContent = (row.name || row.name_norm || '') +
                ' · ' + Number(row.games || 0) +
                ' · ' + Number(row.avg_pr || 0).toFixed(2);
            playerSelect.appendChild(opt);
        });
        var found = players.some(function (row) {
            return (row.name_norm || row.name) === prev;
        });
        playerSelect.value = found ? prev : (players[0].name_norm || players[0].name || '');
        loadDetail();
    }

    function loadUsers() {
        if (!isAdmin || !ownerSelect) return Promise.resolve();
        return fetch(apiBase + '/api/players/users', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var current = ownerSelect.value;
                ownerSelect.innerHTML = '';
                var allOpt = document.createElement('option');
                allOpt.value = '';
                allOpt.textContent = 'Все пользователи';
                ownerSelect.appendChild(allOpt);
                ((data && data.users) || []).forEach(function (row) {
                    var opt = document.createElement('option');
                    opt.value = String(row.id);
                    opt.textContent = row.username || ('#' + row.id);
                    ownerSelect.appendChild(opt);
                });
                ownerSelect.value = current || '';
            })
            .catch(function () {});
    }

    function loadPlayers() {
        return fetch(withOwner(apiBase + '/api/players'), { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                fillPlayers((data && data.players) || []);
            })
            .catch(function () {
                fillPlayers([]);
                setMsg('Не удалось загрузить список игроков.', true);
            });
    }

    function lastQuery() {
        var raw = lastInput ? String(lastInput.value || '').trim() : '';
        if (!raw) return '';
        var n = parseInt(raw, 10);
        if (!Number.isFinite(n) || n < 1) return '';
        return 'last=' + n;
    }

    function loadDetail() {
        var name = selectedPlayerName();
        if (!name) {
            setMsg('Выберите игрока.', true);
            return Promise.resolve();
        }
        var qs = 'name=' + encodeURIComponent(name);
        var last = lastQuery();
        if (last) qs += '&' + last;
        var extra = ownerParam();
        if (extra) qs += '&' + extra;
        setMsg('Загрузка…', true);
        return fetch(apiBase + '/api/players/detail?' + qs, { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data || !data.name) {
                    setMsg('Нет данных по игроку.', true);
                    return;
                }
                var text = data.text || (
                    data.name + ': ' + (data.avg_pr_text || '0.00') + ':\n(' +
                    (data.values_text || '') + ')'
                );
                if (data.last && data.total_games && data.games !== data.total_games) {
                    text += '\n\nСреднее за ' + data.games + ' из ' + data.total_games + ' игр.';
                }
                setMsg(text, false);
            })
            .catch(function () {
                setMsg('Не удалось загрузить статистику.', true);
            });
    }

    function downloadExcel() {
        var name = selectedPlayerName();
        if (!name) {
            setMsg('Выберите игрока.', true);
            return;
        }
        var url = withOwner(apiBase + '/api/players/excel?name=' + encodeURIComponent(name));
        window.location.assign(url);
    }

    tabs.forEach(function (btn) {
        btn.addEventListener('click', function () {
            setTab(btn.getAttribute('data-analyze-tab'));
        });
    });
    if (ownerSelect) {
        ownerSelect.addEventListener('change', function () {
            loadPlayers();
        });
    }
    if (playerSelect) {
        playerSelect.addEventListener('change', function () {
            loadDetail();
        });
    }
    if (showBtn) {
        showBtn.addEventListener('click', function () {
            loadDetail();
        });
    }
    if (lastInput) {
        lastInput.addEventListener('keydown', function (ev) {
            if (ev.key === 'Enter') {
                ev.preventDefault();
                loadDetail();
            }
        });
    }
    if (excelBtn) {
        excelBtn.addEventListener('click', downloadExcel);
    }

    loadUsers();
    if (location.hash === '#stats' || location.hash === '#players') {
        setTab('players');
    }
})();
