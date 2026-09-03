        (function () {
            var bootEl = document.getElementById('cards-cabinet-boot');
            var boot = {};
            try {
                boot = JSON.parse((bootEl && bootEl.textContent) || '{}') || {};
            } catch (bootErr) {
                console.warn('cards_cabinet boot config parse failed:', bootErr);
                boot = {};
            }
            var WEB_STANDALONE = !!boot.web_standalone_mode;
            if (!WEB_STANDALONE && window.Telegram && window.Telegram.WebApp) {
                var tg = window.Telegram.WebApp;
                var allowFullscreen = !!boot.webapp_fullscreen_enabled;
                var cabinetChromeColor = '#1a1a1a';
                tg.ready();
                tg.expand();
                try {
                    if (typeof tg.setBackgroundColor === 'function') {
                        tg.setBackgroundColor(cabinetChromeColor);
                    }
                    if (typeof tg.setHeaderColor === 'function') {
                        tg.setHeaderColor(cabinetChromeColor);
                    }
                    if (typeof tg.onEvent === 'function') {
                        tg.onEvent('themeChanged', function () {
                            if (typeof tg.setBackgroundColor === 'function') {
                                tg.setBackgroundColor(cabinetChromeColor);
                            }
                            if (typeof tg.setHeaderColor === 'function') {
                                tg.setHeaderColor(cabinetChromeColor);
                            }
                        });
                    }
                } catch (themeErr) {
                    console.warn('Telegram theme lock (cards_cabinet) failed:', themeErr);
                }
                try {
                    var canFullscreen =
                        allowFullscreen &&
                        typeof tg.requestFullscreen === 'function' &&
                        (typeof tg.isVersionAtLeast !== 'function' || tg.isVersionAtLeast('8.0'));
                    if (canFullscreen && !tg.isFullscreen) {
                        tg.requestFullscreen();
                    }
                } catch (fsErr) {
                    console.warn('requestFullscreen(cards_cabinet) failed:', fsErr);
                }
            }
            var initData = '';
            var _urlParams = new URLSearchParams(window.location.search || '');
            var fabToken = _urlParams.get('fab_token') || '';
            var CABINET_KIND = boot.cabinet_kind || 'content_cards';
            var IS_MATCH_ANALYSIS = CABINET_KIND === 'match_analysis';
            var FEATURES = Object.assign({
                enable_gallery: true,
                enable_admin_fab: true,
                enable_search: true,
                enable_folders: true,
                enable_labels: true,
                enable_status_filter: true,
                enable_shuffle: true,
                enable_selection: true,
                enable_bulk_bg: true,
                enable_interactive_stats: true,
                enable_create_empty: true,
            }, boot.cabinet_features || {});
            var CABINET_POOL = boot.cabinet_pool || 'cards';
            var CABINET_BASE_PATH = boot.cabinet_base_path || '/cards-cabinet';
            var CABINET_DEFAULT_TITLE = boot.cabinet_title || 'Мои карточки';
            var cabinetStateKey = boot.cabinet_state_key || 'cards_cabinet_state_v1';
            var openHintsStateKey = boot.cabinet_open_hints_key || 'cards_cabinet_open_hints_v1';
            var userPreviewStateKey = boot.cabinet_user_preview_key || 'match_analysis_cabinet_user_preview_v1';
            var maAudioOnlyStateKey = boot.cabinet_audio_only_key || 'match_analysis_cabinet_audio_only_v1';
            var cabinetConfig = (function () {
                var folderToken = _urlParams.get('folder_token') || '';
                if (folderToken) {
                    return { mode: 'folder', folderToken: folderToken };
                }
                return { mode: 'main' };
            })();
            var cabinetFolderId = null;
            var cabinetParentFolderId = null;
            var addToFolderBtn = document.getElementById('add-to-folder-btn');
            var manageFoldersBtn = document.getElementById('manage-folders-btn');
            var cabinetHomeBtn = document.getElementById('cabinet-home-btn');
            var cabinetBackToParentBtn = document.getElementById('cabinet-back-to-parent-btn');

            function buildCardsCabinetUrl(opts) {
                var params = new URLSearchParams();
                if (fabToken) {
                    params.set('fab_token', fabToken);
                }
                var includeFolder = !opts || opts.includeFolder !== false;
                if (includeFolder && cabinetConfig.mode === 'folder' && cabinetConfig.folderToken) {
                    params.set('folder_token', cabinetConfig.folderToken);
                }
                var qs = params.toString();
                return CABINET_BASE_PATH + (qs ? '?' + qs : '');
            }

            function goToMainCabinet() {
                window.location.assign(buildCardsCabinetUrl({ includeFolder: false }));
            }

            if (cabinetHomeBtn) {
                cabinetHomeBtn.addEventListener('click', goToMainCabinet);
            }
            var errEl = document.getElementById('err');
            var gridEl = document.getElementById('grid');
            var searchInput = document.getElementById('card-search');
            var statusFilter = document.getElementById('status-filter');
            var labelFilterWrap = document.getElementById('label-filter-wrap');
            var labelFilter = document.getElementById('label-filter');
            var scrollToBottomBtn = document.getElementById('scroll-to-bottom-btn');
            var cardBgOpenBtn = document.getElementById('card-bg-open-btn');
            var labelPresetsOpenBtn = document.getElementById('label-presets-open-btn');
            var cardBgModal = document.getElementById('cardBgModal');
            var cardBgModalOverlay = document.getElementById('cardBgModalOverlay');
            var cardBgUploadBtn = document.getElementById('cardBgUploadBtn');
            var cardBgFileInput = document.getElementById('cardBgFileInput');
            var cardBgRefreshBtn = document.getElementById('cardBgRefreshBtn');
            var cardBgPreview = document.getElementById('cardBgPreview');
            var cardBgPreviewImg = document.getElementById('cardBgPreviewImg');
            var cardBgSelectedLabel = document.getElementById('cardBgSelectedLabel');
            var cardBgModalMsg = document.getElementById('cardBgModalMsg');
            var cardBgLibraryGrid = document.getElementById('cardBgLibraryGrid');
            var cardBgLoadMoreBtn = document.getElementById('cardBgLoadMoreBtn');
            var cardBgClearBtn = document.getElementById('cardBgClearBtn');
            var cardBgCloseBtn = document.getElementById('cardBgCloseBtn');
            var cardBgApplyBtn = document.getElementById('cardBgApplyBtn');
            var cardBgColorInput = document.getElementById('cardBgColorInput');
            var cardBgColorText = document.getElementById('cardBgColorText');
            var cardBgApplyColorBtn = document.getElementById('cardBgApplyColorBtn');
            var cardBgSelectedKey = '';
            var cardBgSelectedName = '';
            var cardBgNextToken = null;
            var cardBgBusy = false;
            var labelPresetsModalCabinet = document.getElementById('labelPresetsModalCabinet');
            var labelPresetsModalCabinetOverlay = document.getElementById('labelPresetsModalCabinetOverlay');
            var labelPresetsModalCabinetInput = document.getElementById('labelPresetsModalCabinetInput');
            var labelPresetsModalCabinetAddBtn = document.getElementById('labelPresetsModalCabinetAddBtn');
            var labelPresetsModalCabinetMsg = document.getElementById('labelPresetsModalCabinetMsg');
            var labelPresetsModalCabinetList = document.getElementById('labelPresetsModalCabinetList');
            var labelPresetsModalCabinetCloseBtn = document.getElementById('labelPresetsModalCabinetCloseBtn');
            var adminFabBtn = document.getElementById('admin-fab-btn');
            var quickSelectInput = document.getElementById('quick-select-input');
            var selectModeBtn = document.getElementById('select-mode-btn');
            var generateLinkBtn = document.getElementById('generate-link-btn');
            var sendSelectedBtn = document.getElementById('send-selected-btn');
            var shuffleCardsBtn = document.getElementById('shuffle-cards-btn');
            var idToggleBtn = document.getElementById('id-toggle-btn');
            var shuffleModal = document.getElementById('shuffleModal');
            var shuffleModalOverlay = document.getElementById('shuffleModalOverlay');
            var shuffleModalMsg = document.getElementById('shuffleModalMsg');
            var shuffleCountInput = document.getElementById('shuffleCountInput');
            var shuffleModalApplyBtn = document.getElementById('shuffleModalApplyBtn');
            var shuffleModalCancelBtn = document.getElementById('shuffleModalCancelBtn');
            var shuffleModalResetBtn = document.getElementById('shuffleModalResetBtn');
            var interactiveStatsModal = document.getElementById('interactiveStatsModal');
            var interactiveStatsModalOverlay = document.getElementById('interactiveStatsModalOverlay');
            var interactiveStatsModalBody = document.getElementById('interactiveStatsModalBody');
            var interactiveStatsModalCloseBtn = document.getElementById('interactiveStatsModalCloseBtn');
            var interactiveStatsModalClearBtn = document.getElementById('interactiveStatsModalClearBtn');
            var assignCardsModal = document.getElementById('assignCardsModal');
            var assignCardsModalOverlay = document.getElementById('assignCardsModalOverlay');
            var assignCardsModalMsg = document.getElementById('assignCardsModalMsg');
            var assignUsersSearchInput = document.getElementById('assignUsersSearchInput');
            var assignUsersTbody = document.getElementById('assignUsersTbody');
            var assignCardsModalCancelBtn = document.getElementById('assignCardsModalCancelBtn');
            var assignCardsModalSubmitBtn = document.getElementById('assignCardsModalSubmitBtn');
            var assignAlreadyHaveModal = document.getElementById('assignAlreadyHaveModal');
            var assignAlreadyHaveModalOverlay = document.getElementById('assignAlreadyHaveModalOverlay');
            var assignAlreadyHaveModalText = document.getElementById('assignAlreadyHaveModalText');
            var assignAlreadyHaveCancelBtn = document.getElementById('assignAlreadyHaveCancelBtn');
            var assignAlreadyHaveContinueBtn = document.getElementById('assignAlreadyHaveContinueBtn');
            var generateLinkModal = document.getElementById('generateLinkModal');
            var generateLinkModalOverlay = document.getElementById('generateLinkModalOverlay');
            var generateLinkModalInput = document.getElementById('generateLinkModalInput');
            var generateLinkModalTitle = document.getElementById('generateLinkModalTitle');
            var generateLinkModalMsg = document.getElementById('generateLinkModalMsg');
            var generateLinkModalCloseBtn = document.getElementById('generateLinkModalCloseBtn');
            var generateLinkModalCopyBtn = document.getElementById('generateLinkModalCopyBtn');
            var cabinetInteractiveStatsBtn = document.getElementById('cabinet-interactive-stats-btn');
            var cabinetGalleryBtn = document.getElementById('cabinet-gallery-btn');
            var matchRenameModal = document.getElementById('matchRenameModal');
            var matchRenameModalOverlay = document.getElementById('matchRenameModalOverlay');
            var matchRenameModalInput = document.getElementById('matchRenameModalInput');
            var matchRenameModalMsg = document.getElementById('matchRenameModalMsg');
            var matchRenameModalCancelBtn = document.getElementById('matchRenameModalCancelBtn');
            var matchRenameModalSubmitBtn = document.getElementById('matchRenameModalSubmitBtn');
            var matchRenameTargetId = null;

            function applyCabinetFeatureGating() {
                function hideEl(el) {
                    if (el) el.style.display = 'none';
                }
                if (!FEATURES.enable_gallery) hideEl(cabinetGalleryBtn);
                if (!FEATURES.enable_shuffle) hideEl(shuffleCardsBtn);
                if (!FEATURES.enable_interactive_stats) hideEl(cabinetInteractiveStatsBtn);
                if (!FEATURES.enable_folders) {
                    hideEl(manageFoldersBtn);
                    hideEl(cabinetHomeBtn);
                    hideEl(cabinetBackToParentBtn);
                    hideEl(addToFolderBtn);
                }
                if (!FEATURES.enable_status_filter) {
                    hideEl(document.querySelector('.status-filter-wrap'));
                }
                if (!FEATURES.enable_labels) {
                    hideEl(labelFilterWrap);
                }
                if (!FEATURES.enable_bulk_bg) {
                    hideEl(cardBgOpenBtn);
                }
                if (!FEATURES.enable_selection) {
                    hideEl(selectModeBtn);
                    hideEl(generateLinkBtn);
                    hideEl(sendSelectedBtn);
                    hideEl(quickSelectInput);
                    hideEl(idToggleBtn);
                    var footer = document.querySelector('.cabinet-footer');
                    if (footer) footer.classList.add('is-feature-hidden');
                    var wrapEl = document.querySelector('.wrap');
                    if (wrapEl) wrapEl.classList.add('wrap--no-footer');
                } else if (IS_MATCH_ANALYSIS) {
                    // Для MA: выделение + assign/link; id-toggle — цикл название/номер/ID.
                }
                if (!FEATURES.enable_search) {
                    hideEl(document.querySelector('.search-wrap'));
                } else if (IS_MATCH_ANALYSIS && searchInput) {
                    searchInput.removeAttribute('inputmode');
                    searchInput.removeAttribute('pattern');
                    searchInput.placeholder = 'Поиск по названию или игрокам';
                    var searchWrapEl = document.querySelector('.search-wrap');
                    if (searchWrapEl) searchWrapEl.classList.add('search-wrap--ma');
                    var maAudioOnlyWrap = document.getElementById('ma-audio-only-filter-wrap');
                    if (maAudioOnlyWrap) maAudioOnlyWrap.classList.add('is-visible');
                    if (statusFilter) {
                        statusFilter.innerHTML =
                            '<option value="">Все статусы</option>' +
                            '<option value="RECENT">Недавно добавленные</option>' +
                            '<option value="UNVIEWED">Не просмотренные</option>' +
                            '<option value="VIEWED">Просмотренные</option>' +
                            '<option value="FAVORITE">Избранные</option>';
                        statusFilter.title = 'Фильтр по статусу';
                    }
                }
                if (IS_MATCH_ANALYSIS) {
                    var scheduleCountLabel = document.querySelector('label[for="folderScheduleCountInput"]');
                    if (scheduleCountLabel) scheduleCountLabel.textContent = 'Матчей за запуск';
                    var scheduleLabelsBlock = document.getElementById('folderScheduleLabels');
                    if (scheduleLabelsBlock) {
                        var labelsTitle = scheduleLabelsBlock.previousElementSibling;
                        if (labelsTitle && labelsTitle.classList.contains('shuffle-modal__label')) {
                            labelsTitle.style.display = 'none';
                        }
                        scheduleLabelsBlock.style.display = 'none';
                    }
                }
            }
            applyCabinetFeatureGating();
            var cabinetGalleryModal = document.getElementById('cabinetGalleryModal');
            var cabinetGalleryModalOverlay = document.getElementById('cabinetGalleryModalOverlay');
            var cabinetGalleryModalClose = document.getElementById('cabinetGalleryModalClose');
            var cabinetGalleryUploadBtn = document.getElementById('cabinetGalleryUploadBtn');
            var cabinetGalleryModalBox = document.getElementById('cabinetGalleryModalBox');
            var cabinetGalleryFile = document.getElementById('cabinetGalleryFile');
            var cabinetGalleryGrid = document.getElementById('cabinetGalleryGrid');
            var cabinetGalleryMsg = document.getElementById('cabinetGalleryMsg');
            var cabinetGalleryPrev = document.getElementById('cabinetGalleryPrev');
            var cabinetGalleryNext = document.getElementById('cabinetGalleryNext');
            var cabinetGalleryCounter = document.getElementById('cabinetGalleryCounter');
            var galleryCanManage = false;
            var galleryUploadBusy = false;
            var galleryShareBusy = false;
            var galleryItemsList = [];
            var gallerySlideIndex = 0;
            var allCards = [];
            var shuffledCards = null;
            var isRootAdminUser = false;
            var isSelectionMode = false;
            var selectedCardIds = {};
            var assignUsers = [];
            var selectedAssignUserId = null;
            var assignUsersLoaded = false;
            var alreadyHaveModalResolver = null;
            var isDbIdMode = false;
            var maTileDisplayMode = 'title';
            var labelPresetsLoaded = false;
            var labelPresets = [];
            var pendingLabelFilterValue = '';
            var quickSelectionInvalid = false;
            var generatedActivationLink = '';
            var openHintsToggle = document.getElementById('open-hints-toggle');
            var userPreviewToggle = document.getElementById('user-preview-toggle');
            var userPreviewToggleWrap = document.getElementById('user-preview-toggle-wrap');

            function isOpenHintsEnabled() {
                try {
                    var raw = localStorage.getItem(openHintsStateKey);
                    if (raw === null || raw === undefined) return true;
                    return raw !== '0' && raw !== 'false';
                } catch (_e) {
                    return true;
                }
            }

            function saveOpenHintsState() {
                try {
                    var v = openHintsToggle && openHintsToggle.checked ? '1' : '0';
                    localStorage.setItem(openHintsStateKey, v);
                } catch (_e) { }
            }

            function restoreOpenHintsState() {
                if (!openHintsToggle) return;
                openHintsToggle.checked = isOpenHintsEnabled();
            }

            if (openHintsToggle) {
                restoreOpenHintsState();
                openHintsToggle.addEventListener('change', saveOpenHintsState);
            }

            function isUserPreviewEnabled() {
                try {
                    return localStorage.getItem(userPreviewStateKey) === '1';
                } catch (_e) {
                    return false;
                }
            }

            function saveUserPreviewState() {
                try {
                    var v = userPreviewToggle && userPreviewToggle.checked ? '1' : '0';
                    localStorage.setItem(userPreviewStateKey, v);
                } catch (_e) { }
            }

            function restoreUserPreviewState() {
                if (!userPreviewToggle) return;
                userPreviewToggle.checked = isUserPreviewEnabled();
            }

            if (userPreviewToggle) {
                restoreUserPreviewState();
                userPreviewToggle.addEventListener('change', saveUserPreviewState);
            }

            var maAudioOnlyToggle = document.getElementById('ma-audio-only-filter');

            function isMaAudioOnlyEnabled() {
                try {
                    return localStorage.getItem(maAudioOnlyStateKey) === '1';
                } catch (_e) {
                    return false;
                }
            }

            function saveMaAudioOnlyState() {
                try {
                    var v = maAudioOnlyToggle && maAudioOnlyToggle.checked ? '1' : '0';
                    localStorage.setItem(maAudioOnlyStateKey, v);
                } catch (_e) { }
            }

            function restoreMaAudioOnlyState() {
                if (!maAudioOnlyToggle) return;
                maAudioOnlyToggle.checked = isMaAudioOnlyEnabled();
            }

            if (maAudioOnlyToggle) {
                restoreMaAudioOnlyState();
                maAudioOnlyToggle.addEventListener('change', saveMaAudioOnlyState);
            }

            function buildMatchAnalysisViewUrl(id) {
                var url = '/match-analysis-view?id=' + encodeURIComponent(String(id)) + '&error=0';
                if (isUserPreviewEnabled()) {
                    url += '&as_user=1';
                }
                if (isMaAudioOnlyEnabled()) {
                    url += '&audio_only=1';
                }
                return url;
            }

            window.CardsCabinetMatchAudioApi = {
                getInitData: function () { return initData || ''; },
                getFabToken: function () { return fabToken || ''; },
                isWebStandalone: function () { return !!WEB_STANDALONE; },
                showNotice: function (message, title) {
                    return showCabinetNotice(message, title);
                },
                showConfirm: function (message, title, options) {
                    return showCabinetConfirm(message, title, options);
                },
                buildMatchAnalysisViewUrl: buildMatchAnalysisViewUrl,
                onAudioCountChanged: function (matchId, count, minutes) {
                    var idNum = Number(matchId);
                    var n = count == null || count === undefined ? null : (Number(count) || 0);
                    var mins = minutes == null || minutes === undefined
                        ? null
                        : Math.max(0, Math.floor(Number(minutes) || 0));
                    function patch(list) {
                        if (!Array.isArray(list)) return;
                        list.forEach(function (row) {
                            if (Number(row && row.content_card_id) === idNum) {
                                if (n != null) row.audio_count = n;
                                if (mins != null) row.audio_minutes = mins;
                            }
                        });
                    }
                    patch(allCards);
                    patch(shuffledCards);
                    var btn = document.querySelector(
                        '.tile__audio[data-match-id="' + String(idNum) + '"]'
                    );
                    if (btn && n != null) {
                        btn.classList.toggle('has-audio', n > 0);
                        btn.title = n > 0
                            ? ('Аудиофайлы (' + n + ')')
                            : 'Аудиофайлы анализа';
                    }
                    var minsEl = document.querySelector(
                        '.tile__audio-minutes[data-match-id="' + String(idNum) + '"]'
                    );
                    if (minsEl && mins != null) {
                        minsEl.textContent = String(mins);
                    }
                },
            };

            function showErr(msg) {
                errEl.textContent = msg;
                errEl.style.display = 'block';
            }

            var cabinetNoticeModal = document.getElementById('cabinetNoticeModal');
            var cabinetNoticeModalOverlay = document.getElementById('cabinetNoticeModalOverlay');
            var cabinetNoticeModalTitle = document.getElementById('cabinetNoticeModalTitle');
            var cabinetNoticeModalText = document.getElementById('cabinetNoticeModalText');
            var cabinetNoticeModalOkBtn = document.getElementById('cabinetNoticeModalOkBtn');
            var cabinetConfirmModal = document.getElementById('cabinetConfirmModal');
            var cabinetConfirmModalOverlay = document.getElementById('cabinetConfirmModalOverlay');
            var cabinetConfirmModalTitle = document.getElementById('cabinetConfirmModalTitle');
            var cabinetConfirmModalText = document.getElementById('cabinetConfirmModalText');
            var cabinetConfirmModalCancelBtn = document.getElementById('cabinetConfirmModalCancelBtn');
            var cabinetConfirmModalSubmitBtn = document.getElementById('cabinetConfirmModalSubmitBtn');
            var cabinetNoticeResolver = null;
            var cabinetConfirmResolver = null;

            function closeCabinetNoticeModal() {
                if (!cabinetNoticeModal) return;
                cabinetNoticeModal.classList.remove('is-open');
                cabinetNoticeModal.setAttribute('aria-hidden', 'true');
                if (cabinetNoticeResolver) {
                    var noticeDone = cabinetNoticeResolver;
                    cabinetNoticeResolver = null;
                    noticeDone();
                }
            }

            function showCabinetNotice(message, title) {
                return new Promise(function (resolve) {
                    if (!cabinetNoticeModal) {
                        resolve();
                        return;
                    }
                    cabinetNoticeResolver = resolve;
                    if (cabinetNoticeModalTitle) {
                        cabinetNoticeModalTitle.textContent = title || 'Сообщение';
                    }
                    if (cabinetNoticeModalText) {
                        cabinetNoticeModalText.textContent = String(message || '');
                    }
                    cabinetNoticeModal.classList.add('is-open');
                    cabinetNoticeModal.setAttribute('aria-hidden', 'false');
                });
            }

            function closeCabinetConfirmModal(confirmed) {
                if (!cabinetConfirmModal) return;
                cabinetConfirmModal.classList.remove('is-open');
                cabinetConfirmModal.setAttribute('aria-hidden', 'true');
                if (cabinetConfirmModalSubmitBtn) {
                    cabinetConfirmModalSubmitBtn.classList.remove('link-modal__btn--danger');
                }
                if (cabinetConfirmResolver) {
                    var confirmDone = cabinetConfirmResolver;
                    cabinetConfirmResolver = null;
                    confirmDone(!!confirmed);
                }
            }

            function showCabinetConfirm(message, title, options) {
                var opts = options || {};
                return new Promise(function (resolve) {
                    if (!cabinetConfirmModal) {
                        resolve(false);
                        return;
                    }
                    cabinetConfirmResolver = resolve;
                    if (cabinetConfirmModalTitle) {
                        cabinetConfirmModalTitle.textContent = title || 'Подтверждение';
                    }
                    if (cabinetConfirmModalText) {
                        cabinetConfirmModalText.textContent = String(message || '');
                    }
                    if (cabinetConfirmModalSubmitBtn) {
                        cabinetConfirmModalSubmitBtn.textContent = opts.confirmLabel || 'OK';
                        if (opts.danger) {
                            cabinetConfirmModalSubmitBtn.classList.add('link-modal__btn--danger');
                        }
                    }
                    cabinetConfirmModal.classList.add('is-open');
                    cabinetConfirmModal.setAttribute('aria-hidden', 'false');
                });
            }

            if (cabinetNoticeModalOkBtn) {
                cabinetNoticeModalOkBtn.addEventListener('click', closeCabinetNoticeModal);
            }
            if (cabinetNoticeModalOverlay) {
                cabinetNoticeModalOverlay.addEventListener('click', closeCabinetNoticeModal);
            }
            if (cabinetConfirmModalCancelBtn) {
                cabinetConfirmModalCancelBtn.addEventListener('click', function () {
                    closeCabinetConfirmModal(false);
                });
            }
            if (cabinetConfirmModalOverlay) {
                cabinetConfirmModalOverlay.addEventListener('click', function () {
                    closeCabinetConfirmModal(false);
                });
            }
            if (cabinetConfirmModalSubmitBtn) {
                cabinetConfirmModalSubmitBtn.addEventListener('click', function () {
                    closeCabinetConfirmModal(true);
                });
            }

            /** На части клиентов Telegram (в т.ч. Desktop) initData может появиться позже tg.ready(). */
            function waitForTelegramWebAppInitData(maxMs, stepMs) {
                if (WEB_STANDALONE) {
                    return Promise.resolve('');
                }
                maxMs = typeof maxMs === 'number' ? maxMs : 5000;
                stepMs = typeof stepMs === 'number' ? stepMs : 50;
                if (fabToken) {
                    return Promise.resolve('');
                }
                var tg = window.Telegram && window.Telegram.WebApp;
                if (!tg) {
                    return Promise.resolve('');
                }
                var cur = tg.initData || '';
                if (cur) {
                    return Promise.resolve(cur);
                }
                try {
                    if (typeof tg.ready === 'function') {
                        tg.ready();
                    }
                } catch (_e) { }
                return new Promise(function (resolve) {
                    var t0 = Date.now();
                    function tick() {
                        var v = (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || '';
                        if (v) {
                            resolve(v);
                            return;
                        }
                        if (Date.now() - t0 >= maxMs) {
                            resolve('');
                            return;
                        }
                        setTimeout(tick, stepMs);
                    }
                    tick();
                });
            }

            function saveCabinetState() {
                try {
                    var payload = {
                        search: String(searchInput ? (searchInput.value || '') : ''),
                        status: String(statusFilter ? (statusFilter.value || '') : ''),
                        label: String(labelFilter ? (labelFilter.value || '') : ''),
                        isDbIdMode: !!isDbIdMode,
                        maTileDisplayMode: IS_MATCH_ANALYSIS ? maTileDisplayMode : undefined,
                    };
                    localStorage.setItem(cabinetStateKey, JSON.stringify(payload));
                } catch (_e) { }
            }

            function restoreCabinetState() {
                try {
                    var raw = localStorage.getItem(cabinetStateKey);
                    if (!raw) return;
                    var state = JSON.parse(raw);
                    if (searchInput && state && typeof state.search === 'string') {
                        searchInput.value = IS_MATCH_ANALYSIS
                            ? state.search
                            : state.search.replace(/\D+/g, '');
                    }
                    if (statusFilter && state && typeof state.status === 'string') {
                        statusFilter.value = state.status;
                    }
                    if (state && typeof state.label === 'string') {
                        pendingLabelFilterValue = state.label;
                    }
                    isDbIdMode = !!(state && state.isDbIdMode);
                    if (IS_MATCH_ANALYSIS && state && typeof state.maTileDisplayMode === 'string') {
                        var mode = state.maTileDisplayMode;
                        if (mode === 'title' || mode === 'order' || mode === 'id') {
                            maTileDisplayMode = mode;
                        }
                    }
                } catch (_e) { }
            }

            function applyPendingLabelFilterValue() {
                if (!labelFilter) return;
                if (!pendingLabelFilterValue) {
                    labelFilter.value = '';
                    return;
                }
                var hasOption = Array.from(labelFilter.options || []).some(function (opt) {
                    return String(opt.value || '') === pendingLabelFilterValue;
                });
                labelFilter.value = hasOption ? pendingLabelFilterValue : '';
            }

            function getCardDisplayId(row) {
                if (isDbIdMode) {
                    return Number((row && row.content_card_id) || 0);
                }
                return Number(((row && row.__index) || 0) + 1);
            }

            function getMatchAnalysisDisplayOrder(row) {
                return Number(((row && row.__index) || 0) + 1);
            }

            function getMatchAnalysisTileText(row, fullTitle) {
                if (maTileDisplayMode === 'order') {
                    return String(getMatchAnalysisDisplayOrder(row));
                }
                if (maTileDisplayMode === 'id') {
                    return String((row && row.content_card_id) || '');
                }
                var titleText = String(fullTitle || '');
                if (titleText.length > 32) {
                    titleText = titleText.slice(0, 31) + '…';
                }
                return titleText;
            }

            function applyMatchAnalysisTileDisplay(btn, row, fullTitle, isSelected) {
                var showTitle = maTileDisplayMode === 'title';
                var status = String((row && row.status) || 'UNVIEWED').toUpperCase();
                btn.className = 'tile' + (showTitle ? ' tile--match' : '') + (isSelected ? ' tile--selected' : '');
                if (status === 'VIEWED') {
                    btn.classList.add('tile--viewed');
                } else if (status === 'SOLVED') {
                    btn.classList.add('tile--solved');
                } else if (status === 'FAVORITE') {
                    btn.classList.add('tile--favorite');
                } else if (status === 'HARD') {
                    btn.classList.add('tile--hard');
                } else if (status === 'RECENT') {
                    btn.classList.add('tile--recent');
                }
                btn.textContent = getMatchAnalysisTileText(row, fullTitle);
            }

            function updateMaTileDisplayModeUi() {
                if (!idToggleBtn) return;
                var label = 'Название';
                var hint = 'Показаны названия матчей';
                if (maTileDisplayMode === 'order') {
                    label = 'Номер';
                    hint = 'Показаны порядковые номера';
                } else if (maTileDisplayMode === 'id') {
                    label = 'ID';
                    hint = 'Показаны ID анализов';
                }
                idToggleBtn.textContent = label;
                idToggleBtn.classList.toggle('is-active', maTileDisplayMode !== 'title');
                idToggleBtn.title = hint;
                idToggleBtn.setAttribute('aria-label', hint);
                if (searchInput) {
                    if (maTileDisplayMode === 'id') {
                        searchInput.placeholder = 'Поиск по ID';
                    } else if (maTileDisplayMode === 'order') {
                        searchInput.placeholder = 'Поиск по номеру';
                    } else {
                        searchInput.placeholder = 'Поиск по названию или игрокам';
                    }
                }
                if (quickSelectInput) {
                    quickSelectInput.placeholder = maTileDisplayMode === 'id'
                        ? '101,205,300-315'
                        : '11,22,25-30';
                }
            }

            function cycleMaTileDisplayMode() {
                if (maTileDisplayMode === 'title') maTileDisplayMode = 'order';
                else if (maTileDisplayMode === 'order') maTileDisplayMode = 'id';
                else maTileDisplayMode = 'title';
            }

            function getCardHoverTitle(row, cardIdNum) {
                var notes = String((row && row.notes) || '').trim();
                if (notes) {
                    return notes;
                }
                return 'Карточка #' + cardIdNum;
            }

            function updateCardNotesInLists(cardIdNum, notes) {
                var value = String(notes || '').trim();
                function patch(list) {
                    if (!Array.isArray(list)) return;
                    list.forEach(function (row) {
                        if (Number(row && row.content_card_id) === cardIdNum) {
                            row.notes = value;
                        }
                    });
                }
                patch(allCards);
                patch(shuffledCards);
            }

            function updateIdModeUi() {
                if (!idToggleBtn) return;
                idToggleBtn.textContent = isDbIdMode ? 'ID' : 'Номер';
                idToggleBtn.classList.toggle('is-active', isDbIdMode);
                idToggleBtn.title = isDbIdMode
                    ? 'Показаны ID карточек'
                    : 'Показаны относительные номера карточек';
                if (searchInput) {
                    searchInput.placeholder = isDbIdMode
                        ? 'Поиск по ID'
                        : 'Поиск по номеру карточки';
                }
                if (quickSelectInput) {
                    quickSelectInput.placeholder = isDbIdMode ? '101,205,300-315' : '11,22,25-30';
                }
            }

            function beginCabinetAuth(resolvedInitData) {
                initData =
                    resolvedInitData ||
                    (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) ||
                    '';
                if (!WEB_STANDALONE) {
                    if (IS_MATCH_ANALYSIS) {
                        if (!initData && !fabToken) {
                            showErr('Откройте кабинет через Telegram (/match_analysis) или через FAB.');
                            return;
                        }
                    } else if (!initData && !fabToken) {
                        showErr('Откройте страницу из Telegram или через FAB-мост.');
                        return;
                    }
                }
                restoreCabinetState();

                function authPayload(extra) {
                    var base = IS_MATCH_ANALYSIS ? {} : { pool: CABINET_POOL };
                    if (initData) {
                        base.init_data = initData;
                    } else if (fabToken) {
                        base.fab_token = fabToken;
                    }
                    if (cabinetConfig.mode === 'folder' && cabinetConfig.folderToken) {
                        base.folder_token = cabinetConfig.folderToken;
                    }
                    if (extra && typeof extra === 'object') {
                        Object.keys(extra).forEach(function (k) { base[k] = extra[k]; });
                    }
                    return base;
                }

                function setCabinetGalleryMsg(text) {
                    if (!cabinetGalleryMsg) return;
                    var t = String(text || '').trim();
                    cabinetGalleryMsg.textContent = t;
                    cabinetGalleryMsg.classList.toggle('is-visible', !!t);
                }

                function closeCabinetGalleryModal() {
                    if (!cabinetGalleryModal) return;
                    cabinetGalleryModal.classList.remove('is-open');
                    cabinetGalleryModal.setAttribute('aria-hidden', 'true');
                    if (cabinetGalleryModalBox) {
                        cabinetGalleryModalBox.classList.remove('is-admin');
                    }
                    galleryCanManage = false;
                    galleryItemsList = [];
                    gallerySlideIndex = 0;
                    setCabinetGalleryMsg('');
                    updateCabinetGallerySlide();
                }

                function syncCabinetGalleryNav() {
                    var n = galleryItemsList.length;
                    if (cabinetGalleryCounter) {
                        cabinetGalleryCounter.textContent = n ? String(gallerySlideIndex + 1) + ' / ' + String(n) : '';
                    }
                    if (cabinetGalleryPrev) {
                        cabinetGalleryPrev.disabled = !n || gallerySlideIndex <= 0;
                    }
                    if (cabinetGalleryNext) {
                        cabinetGalleryNext.disabled = !n || gallerySlideIndex >= n - 1;
                    }
                }

                function updateCabinetGallerySlide() {
                    if (!cabinetGalleryGrid) return;
                    cabinetGalleryGrid.innerHTML = '';
                    if (!galleryItemsList.length) {
                        var empty = document.createElement('div');
                        empty.className = 'cabinet-gallery-modal__empty';
                        empty.setAttribute('aria-hidden', 'true');
                        cabinetGalleryGrid.appendChild(empty);
                        syncCabinetGalleryNav();
                        return;
                    }
                    if (gallerySlideIndex < 0) {
                        gallerySlideIndex = 0;
                    }
                    if (gallerySlideIndex >= galleryItemsList.length) {
                        gallerySlideIndex = galleryItemsList.length - 1;
                    }
                    var it = galleryItemsList[gallerySlideIndex];
                    var key = it && it.key;
                    if (!key) {
                        galleryItemsList.splice(gallerySlideIndex, 1);
                        if (gallerySlideIndex >= galleryItemsList.length) {
                            gallerySlideIndex = Math.max(0, galleryItemsList.length - 1);
                        }
                        updateCabinetGallerySlide();
                        return;
                    }
                    var cell = document.createElement('div');
                    cell.className = 'cabinet-gallery-modal__cell';
                    cell.dataset.s3Key = key;
                    var img = document.createElement('img');
                    img.alt = '';
                    img.loading = gallerySlideIndex === 0 ? 'eager' : 'lazy';
                    img.src = '/api/content_cards/media?' + new URLSearchParams({ key: key }).toString();
                    cell.appendChild(img);
                    if (galleryCanManage) {
                        var del = document.createElement('button');
                        del.type = 'button';
                        del.className = 'cabinet-gallery-modal__del';
                        del.setAttribute('aria-label', 'Удалить');
                        del.textContent = '\u00d7';
                        del.addEventListener('click', function (ev) {
                            ev.preventDefault();
                            ev.stopPropagation();
                            deleteCabinetGalleryItem(key);
                        });
                        cell.appendChild(del);
                    }
                    cabinetGalleryGrid.appendChild(cell);
                    syncCabinetGalleryNav();
                }

                function goCabinetGalleryPrev() {
                    if (gallerySlideIndex > 0) {
                        gallerySlideIndex -= 1;
                        updateCabinetGallerySlide();
                    }
                }

                function goCabinetGalleryNext() {
                    if (gallerySlideIndex < galleryItemsList.length - 1) {
                        gallerySlideIndex += 1;
                        updateCabinetGallerySlide();
                    }
                }

                function renderCabinetGalleryGrid(items) {
                    galleryItemsList = [];
                    if (items && items.length) {
                        for (var gi = 0; gi < items.length; gi++) {
                            var row = items[gi];
                            if (row && row.key) {
                                galleryItemsList.push(row);
                            }
                        }
                    }
                    gallerySlideIndex = 0;
                    updateCabinetGallerySlide();
                }

                function copyTextViaTextarea(text) {
                    return new Promise(function (resolve, reject) {
                        try {
                            var value = String(text || '');
                            if (!value) {
                                reject(new Error('Пустая строка для копирования.'));
                                return;
                            }
                            var ta = document.createElement('textarea');
                            ta.value = value;
                            ta.setAttribute('readonly', '');
                            ta.style.position = 'fixed';
                            ta.style.left = '-9999px';
                            ta.style.top = '0';
                            ta.style.opacity = '0';
                            document.body.appendChild(ta);
                            ta.focus();
                            ta.select();
                            if (typeof ta.setSelectionRange === 'function') {
                                ta.setSelectionRange(0, value.length);
                            }
                            var ok = document.execCommand('copy');
                            document.body.removeChild(ta);
                            if (!ok) {
                                reject(new Error('execCommand copy failed'));
                                return;
                            }
                            resolve();
                        } catch (e) {
                            reject(e);
                        }
                    });
                }

                function copyTextToClipboard(text) {
                    var value = String(text || '');
                    if (!value) {
                        return Promise.reject(new Error('Пустая строка для копирования.'));
                    }
                    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
                        return navigator.clipboard.writeText(value).catch(function () {
                            return copyTextViaTextarea(value);
                        });
                    }
                    return copyTextViaTextarea(value);
                }

                function copyGalleryDeepLinkToClipboard(url, onOk, onFail) {
                    copyTextToClipboard(url).then(onOk).catch(onFail);
                }

                function notifyGalleryLinkCopiedToClipboard() {
                    var text = 'Ссылка скопирована в буфер обмена.';
                    try {
                        var tg = window.Telegram && window.Telegram.WebApp;
                        if (tg && typeof tg.showAlert === 'function') {
                            tg.showAlert(text);
                        }
                    } catch (_e) { }
                    try {
                        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
                            window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
                        }
                    } catch (_h) { }
                }

                function requestGalleryImageShareLink(s3Key) {
                    if (galleryShareBusy || !s3Key) return;
                    galleryShareBusy = true;
                    setCabinetGalleryMsg('');
                    fetch('/api/content_cards/cabinet_gallery/share_link', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(authPayload({ s3_key: s3Key })),
                    })
                        .then(function (r) {
                            if (!r.ok) {
                                return r.json().then(function (j) {
                                    throw new Error((j && j.detail) || r.statusText);
                                }).catch(function () {
                                    throw new Error('Ошибка');
                                });
                            }
                            return r.json();
                        })
                        .then(function (data) {
                            var link = data && data.start_link;
                            if (!link) {
                                throw new Error('Нет ссылки');
                            }
                            copyGalleryDeepLinkToClipboard(
                                link,
                                function () {
                                    galleryShareBusy = false;
                                    notifyGalleryLinkCopiedToClipboard();
                                },
                                function () {
                                    galleryShareBusy = false;
                                    setCabinetGalleryMsg('Не удалось скопировать: ' + link);
                                }
                            );
                        })
                        .catch(function (e) {
                            galleryShareBusy = false;
                            setCabinetGalleryMsg(e.message || String(e));
                        });
                }

                function deleteCabinetGalleryItem(key) {
                    fetch('/api/content_cards/cabinet_gallery/delete', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(authPayload({ key: key })),
                    })
                        .then(function (r) {
                            if (!r.ok) {
                                return r.json().then(function (j) {
                                    throw new Error((j && j.detail) || r.statusText);
                                }).catch(function () {
                                    throw new Error('Ошибка');
                                });
                            }
                            return r.json();
                        })
                        .then(function () {
                            var removedIdx = -1;
                            for (var i = 0; i < galleryItemsList.length; i++) {
                                if (galleryItemsList[i] && galleryItemsList[i].key === key) {
                                    removedIdx = i;
                                    break;
                                }
                            }
                            if (removedIdx >= 0) {
                                galleryItemsList.splice(removedIdx, 1);
                            }
                            if (removedIdx >= 0 && removedIdx < gallerySlideIndex) {
                                gallerySlideIndex -= 1;
                            } else if (removedIdx >= 0 && removedIdx === gallerySlideIndex) {
                                if (gallerySlideIndex >= galleryItemsList.length) {
                                    gallerySlideIndex = Math.max(0, galleryItemsList.length - 1);
                                }
                            }
                            updateCabinetGallerySlide();
                        })
                        .catch(function (e) {
                            setCabinetGalleryMsg(e.message || String(e));
                        });
                }

                function loadCabinetGalleryIntoModal() {
                    if (!cabinetGalleryGrid) return;
                    galleryCanManage = false;
                    galleryItemsList = [];
                    gallerySlideIndex = 0;
                    updateCabinetGallerySlide();

                    function collect(token, acc) {
                        return fetch('/api/content_cards/cabinet_gallery/list', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(authPayload({
                                continuation_token: token || undefined,
                                limit: 100,
                            })),
                        }).then(function (r) {
                            if (!r.ok) {
                                return r.json().then(function (j) {
                                    throw new Error((j && j.detail) || r.statusText);
                                }).catch(function () {
                                    throw new Error('Ошибка');
                                });
                            }
                            return r.json();
                        }).then(function (data) {
                            var items = (data && data.items) || [];
                            items.forEach(function (it) { acc.push(it); });
                            if (data && data.can_manage) {
                                galleryCanManage = true;
                            }
                            var nt = data && data.continuation_token;
                            if (nt) {
                                return collect(nt, acc);
                            }
                            return acc;
                        });
                    }

                    collect(null, []).then(function (allItems) {
                        if (cabinetGalleryModalBox) {
                            cabinetGalleryModalBox.classList.toggle('is-admin', !!galleryCanManage);
                        }
                        renderCabinetGalleryGrid(allItems);
                    }).catch(function (e) {
                        setCabinetGalleryMsg(e.message || String(e));
                    });
                }

                function openCabinetGalleryModal() {
                    if (!cabinetGalleryModal || !cabinetGalleryGrid) return;
                    galleryCanManage = false;
                    cabinetGalleryModal.classList.add('is-open');
                    cabinetGalleryModal.setAttribute('aria-hidden', 'false');
                    if (cabinetGalleryModalBox) {
                        cabinetGalleryModalBox.classList.remove('is-admin');
                    }
                    setCabinetGalleryMsg('');
                    loadCabinetGalleryIntoModal();
                    try {
                        if (cabinetGalleryModalBox && typeof cabinetGalleryModalBox.focus === 'function') {
                            cabinetGalleryModalBox.focus({ preventScroll: true });
                        }
                    } catch (_f) { }
                }

                function uploadCabinetGalleryFiles(fileList) {
                    if (!cabinetGalleryModalBox || !cabinetGalleryModalBox.classList.contains('is-admin')) {
                        return;
                    }
                    if (galleryUploadBusy) return;
                    var files = Array.prototype.slice.call(fileList || []).filter(function (f) {
                        return f && /^image\//i.test(f.type || '');
                    });
                    if (!files.length) return;
                    galleryUploadBusy = true;
                    setCabinetGalleryMsg('');
                    var i = 0;
                    function next() {
                        if (i >= files.length) {
                            galleryUploadBusy = false;
                            loadCabinetGalleryIntoModal();
                            return;
                        }
                        var f = files[i];
                        i += 1;
                        var fd = new FormData();
                        if (initData) {
                            fd.append('init_data', initData);
                        } else if (fabToken) {
                            fd.append('fab_token', fabToken);
                        }
                        fd.append('file', f, f.name || 'image');
                        fetch('/api/content_cards/cabinet_gallery/upload', { method: 'POST', body: fd })
                            .then(function (r) {
                                if (!r.ok) {
                                    return r.json().then(function (j) {
                                        throw new Error((j && j.detail) || r.statusText);
                                    }).catch(function () {
                                        throw new Error('Ошибка загрузки');
                                    });
                                }
                                return r.json();
                            })
                            .then(function () { next(); })
                            .catch(function (e) {
                                galleryUploadBusy = false;
                                setCabinetGalleryMsg(e.message || String(e));
                            });
                    }
                    next();
                }

                function setAssignModalMsg(msg) {
                    if (!assignCardsModalMsg) return;
                    assignCardsModalMsg.textContent = String(msg || '');
                }

                function parseQuickSelectionInput(raw) {
                    var value = String(raw || '').trim();
                    if (!value) return { valid: true, numbers: [] };
                    var tokens = value.split(',');
                    var out = [];
                    for (var i = 0; i < tokens.length; i++) {
                        var token = String(tokens[i] || '').replace(/\s+/g, '');
                        if (!token) continue;
                        var mNum = token.match(/^\d+$/);
                        if (mNum) {
                            var numVal = Number(token);
                            if (!Number.isFinite(numVal) || numVal < 1) return { valid: false, numbers: [] };
                            out.push(numVal);
                            continue;
                        }
                        var mRange = token.match(/^(\d+)-(\d+)$/);
                        if (mRange) {
                            var a = Number(mRange[1]);
                            var b = Number(mRange[2]);
                            if (!Number.isFinite(a) || !Number.isFinite(b) || a < 1 || b < 1) {
                                return { valid: false, numbers: [] };
                            }
                            if (a > b) {
                                var tmp = a;
                                a = b;
                                b = tmp;
                            }
                            for (var n = a; n <= b; n++) out.push(n);
                            continue;
                        }
                        return { valid: false, numbers: [] };
                    }
                    var unique = {};
                    var dedup = [];
                    out.forEach(function (n) {
                        if (!unique[n]) {
                            unique[n] = true;
                            dedup.push(n);
                        }
                    });
                    return { valid: true, numbers: dedup };
                }

                function applyQuickSelectionFromInput() {
                    if (!quickSelectInput) return;
                    var parsed = parseQuickSelectionInput(quickSelectInput.value);
                    quickSelectionInvalid = !parsed.valid;
                    quickSelectInput.classList.toggle('is-invalid', quickSelectionInvalid);
                    if (!parsed.valid) {
                        selectedCardIds = {};
                        updateSelectionUi();
                        renderCards();
                        return;
                    }
                    var selectedByNumber = {};
                    if (parsed.numbers.length) {
                        allCards.forEach(function (row) {
                            var matchValue;
                            if (IS_MATCH_ANALYSIS) {
                                matchValue = maTileDisplayMode === 'id'
                                    ? Number(row && row.content_card_id)
                                    : Number((row && row.__index) || 0) + 1;
                            } else {
                                matchValue = isDbIdMode
                                    ? Number(row && row.content_card_id)
                                    : Number((row && row.__index) || 0) + 1;
                            }
                            if (parsed.numbers.indexOf(matchValue) === -1) return;
                            var cardIdNum = Number(row && row.content_card_id);
                            if (Number.isFinite(cardIdNum) && cardIdNum > 0) {
                                selectedByNumber[String(cardIdNum)] = true;
                            }
                        });
                    }
                    selectedCardIds = selectedByNumber;
                    updateSelectionUi();
                    renderCards();
                }

                function setLabelPresetsModalMsg(msg) {
                    if (!labelPresetsModalCabinetMsg) return;
                    labelPresetsModalCabinetMsg.textContent = String(msg || '');
                }

                function renderLabelPresetsModalList() {
                    if (!labelPresetsModalCabinetList) return;
                    labelPresetsModalCabinetList.innerHTML = '';
                    if (!labelPresets.length) {
                        labelPresetsModalCabinetList.innerHTML = '<span class="presets-modal__empty">Пока нет пресетов</span>';
                        return;
                    }
                    labelPresets.forEach(function (preset) {
                        var text = String((preset && preset.value) || '').trim();
                        if (!text) return;
                        var chip = document.createElement('span');
                        chip.className = 'presets-modal__chip';
                        chip.textContent = text;
                        var removeBtn = document.createElement('button');
                        removeBtn.type = 'button';
                        removeBtn.className = 'presets-modal__chip-remove';
                        removeBtn.textContent = '×';
                        removeBtn.title = 'Удалить пресет';
                        removeBtn.setAttribute('aria-label', 'Удалить пресет');
                        removeBtn.addEventListener('click', function () {
                            deleteLabelPreset(preset && preset.id);
                        });
                        chip.appendChild(removeBtn);
                        labelPresetsModalCabinetList.appendChild(chip);
                    });
                }

                function closeLabelPresetsModalCabinet() {
                    if (!labelPresetsModalCabinet) return;
                    labelPresetsModalCabinet.classList.remove('is-open');
                    labelPresetsModalCabinet.setAttribute('aria-hidden', 'true');
                    setLabelPresetsModalMsg('');
                }

                function loadLabelPresets() {
                    if (labelPresetsLoaded) {
                        renderLabelPresetsModalList();
                        return Promise.resolve();
                    }
                    return fetch('/api/content_cards/label_presets', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(authPayload()),
                    })
                        .then(function (r) {
                            if (!r.ok) {
                                return r.json().then(function (j) {
                                    throw new Error(j.detail || r.statusText);
                                }).catch(function () {
                                    throw new Error('Не удалось загрузить пресеты');
                                });
                            }
                            return r.json();
                        })
                        .then(function (data) {
                            labelPresets = Array.isArray(data && data.presets) ? data.presets : [];
                            labelPresetsLoaded = true;
                            renderLabelPresetsModalList();
                        });
                }

                function restoreLabelPresetsInputFocus() {
                    if (!labelPresetsModalCabinetInput) return;
                    labelPresetsModalCabinetInput.disabled = false;
                    labelPresetsModalCabinetInput.readOnly = false;
                    labelPresetsModalCabinetInput.style.pointerEvents = 'auto';
                    requestAnimationFrame(function () {
                        labelPresetsModalCabinetInput.focus();
                    });
                }

                function addLabelPreset() {
                    if (!isRootAdminUser) return;
                    var text = String(labelPresetsModalCabinetInput ? labelPresetsModalCabinetInput.value : '').trim();
                    if (!text) {
                        setLabelPresetsModalMsg('Введите текст пресета');
                        restoreLabelPresetsInputFocus();
                        return;
                    }
                    setLabelPresetsModalMsg('');
                    fetch('/api/content_cards/label_presets/create', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(authPayload({ value: text })),
                    })
                        .then(function (r) {
                            return r.json().catch(function () { return {}; }).then(function (j) {
                                if (!r.ok) {
                                    var detail = (j && j.detail) || r.statusText || 'Не удалось добавить пресет';
                                    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
                                }
                                return j;
                            });
                        })
                        .then(function (data) {
                            if (labelPresetsModalCabinetInput) labelPresetsModalCabinetInput.value = '';
                            var id = data && data.id;
                            var value = String((data && data.value) || '').trim();
                            if (id != null && value) {
                                labelPresets.push({ id: id, value: value });
                                labelPresets.sort(function (a, b) {
                                    return String(a.value || '').localeCompare(String(b.value || ''), undefined, { sensitivity: 'base' });
                                });
                                labelPresetsLoaded = true;
                                renderLabelPresetsModalList();
                                return;
                            }
                            labelPresetsLoaded = false;
                            return loadLabelPresets();
                        })
                        .catch(function (e) {
                            setLabelPresetsModalMsg(e && e.message ? e.message : 'Не удалось добавить пресет');
                        })
                        .finally(function () {
                            restoreLabelPresetsInputFocus();
                        });
                }

                function deleteLabelPreset(presetId) {
                    var idNum = Number(presetId);
                    if (!Number.isFinite(idNum) || idNum < 1) return;
                    if (!isRootAdminUser) return;
                    showCabinetConfirm('Удалить этот пресет?', 'Удаление пресета', {
                        danger: true,
                        confirmLabel: 'Удалить',
                    }).then(function (ok) {
                        if (!ok) return;
                        setLabelPresetsModalMsg('');
                        fetch('/api/content_cards/label_presets/delete', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(authPayload({ preset_id: idNum })),
                    })
                        .then(function (r) {
                            return r.json().catch(function () { return {}; }).then(function (j) {
                                if (!r.ok) {
                                    var detail = (j && j.detail) || r.statusText || 'Не удалось удалить пресет';
                                    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
                                }
                                return j;
                            });
                        })
                        .then(function () {
                            labelPresets = labelPresets.filter(function (p) { return Number(p && p.id) !== idNum; });
                            renderLabelPresetsModalList();
                        })
                        .catch(function (e) {
                            setLabelPresetsModalMsg(e && e.message ? e.message : 'Не удалось удалить пресет');
                        })
                        .finally(function () {
                            restoreLabelPresetsInputFocus();
                        });
                    });
                }

                function openLabelPresetsModalCabinet() {
                    if (!isRootAdminUser || !labelPresetsModalCabinet) return;
                    setLabelPresetsModalMsg('');
                    labelPresetsModalCabinet.classList.add('is-open');
                    labelPresetsModalCabinet.setAttribute('aria-hidden', 'false');
                    loadLabelPresets().catch(function (e) {
                        setLabelPresetsModalMsg(e && e.message ? e.message : 'Ошибка загрузки пресетов');
                    });
                }

                function setCardBgModalMsg(msg) {
                    if (!cardBgModalMsg) return;
                    cardBgModalMsg.textContent = String(msg || '');
                }

                function setCardBgBusy(busy) {
                    cardBgBusy = !!busy;
                    [
                        cardBgUploadBtn,
                        cardBgRefreshBtn,
                        cardBgLoadMoreBtn,
                        cardBgClearBtn,
                        cardBgApplyBtn,
                        cardBgApplyColorBtn,
                        cardBgColorInput,
                        cardBgColorText,
                    ].forEach(function (btn) {
                        if (!btn) return;
                        if (btn === cardBgApplyBtn) {
                            btn.disabled = cardBgBusy || !cardBgSelectedKey;
                        } else {
                            btn.disabled = cardBgBusy;
                        }
                    });
                }

                function normalizeCardBgColor(raw) {
                    var s = String(raw || '').trim();
                    var m6 = s.match(/^#([0-9A-Fa-f]{6})$/);
                    if (m6) return '#' + m6[1].toLowerCase();
                    var m3 = s.match(/^#([0-9A-Fa-f]{3})$/);
                    if (m3) {
                        return '#' + m3[1].split('').map(function (c) { return c + c; }).join('').toLowerCase();
                    }
                    return '';
                }

                function syncCardBgColorInputs(fromPicker) {
                    if (!cardBgColorInput || !cardBgColorText) return;
                    if (fromPicker) {
                        cardBgColorText.value = cardBgColorInput.value;
                        return;
                    }
                    var normalized = normalizeCardBgColor(cardBgColorText.value);
                    if (normalized) {
                        cardBgColorInput.value = normalized;
                        cardBgColorText.value = normalized;
                    }
                }

                function applyCardBgColor() {
                    if (!isRootAdminUser || cardBgBusy) return;
                    syncCardBgColorInputs(false);
                    var color = normalizeCardBgColor(
                        cardBgColorText ? cardBgColorText.value : (cardBgColorInput && cardBgColorInput.value)
                    );
                    if (!color) {
                        setCardBgModalMsg('Укажите цвет в формате #rgb или #rrggbb');
                        return;
                    }
                    setCardBgBusy(true);
                    setCardBgModalMsg('Ставлю цвет фона на все кадры (картинка будет снята)…');
                    fetch('/api/content_cards/bulk_canvas_bg/set_color', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(authPayload({ color: color })),
                    })
                        .then(function (r) {
                            return r.json().catch(function () { return {}; }).then(function (j) {
                                if (!r.ok) {
                                    var detail = (j && j.detail) || r.statusText || 'Не удалось применить цвет';
                                    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
                                }
                                return j;
                            });
                        })
                        .then(function (data) {
                            var msg =
                                'Цвет ' + (data.color || color) + '. Карточек: ' + (data.cards_total || 0) +
                                ', изменено: ' + (data.cards_updated || 0) +
                                ', кадров: ' + (data.frames_updated || 0);
                            setCardBgModalMsg(msg);
                            showCabinetNotice(msg, 'Фон кадров');
                        })
                        .catch(function (e) {
                            setCardBgModalMsg(e && e.message ? e.message : 'Ошибка применения цвета');
                        })
                        .finally(function () {
                            setCardBgBusy(false);
                        });
                }

                function mediaUrlForKey(key) {
                    return '/api/content_cards/media?' + new URLSearchParams({ key: key }).toString();
                }

                function shortenCardBgFilename(name, maxLen) {
                    var s = String(name || '').trim() || '—';
                    var lim = maxLen || 22;
                    if (s.length <= lim) return s;
                    var ext = s.includes('.') ? s.slice(s.lastIndexOf('.')) : '';
                    var base = ext ? s.slice(0, s.length - ext.length) : s;
                    var keep = lim - ext.length - 1;
                    if (keep < 4) return s.slice(0, lim - 1) + '…';
                    return base.slice(0, Math.ceil(keep / 2)) + '…' + base.slice(-Math.floor(keep / 2)) + ext;
                }

                function syncCardBgSelectionUi() {
                    if (cardBgSelectedLabel) {
                        cardBgSelectedLabel.textContent = cardBgSelectedKey
                            ? ('Выбрано: ' + (cardBgSelectedName || cardBgSelectedKey))
                            : '';
                    }
                    if (cardBgPreview && cardBgPreviewImg) {
                        if (cardBgSelectedKey) {
                            cardBgPreviewImg.src = mediaUrlForKey(cardBgSelectedKey);
                            cardBgPreview.classList.add('is-visible');
                            cardBgPreview.setAttribute('aria-hidden', 'false');
                        } else {
                            cardBgPreviewImg.removeAttribute('src');
                            cardBgPreview.classList.remove('is-visible');
                            cardBgPreview.setAttribute('aria-hidden', 'true');
                        }
                    }
                    if (cardBgApplyBtn) {
                        cardBgApplyBtn.disabled = cardBgBusy || !cardBgSelectedKey;
                    }
                    if (cardBgLibraryGrid) {
                        Array.prototype.forEach.call(
                            cardBgLibraryGrid.querySelectorAll('.card-bg-modal__cell'),
                            function (cell) {
                                cell.classList.toggle(
                                    'is-selected',
                                    cell.dataset.s3Key === cardBgSelectedKey
                                );
                            }
                        );
                    }
                }

                function selectCardBgKey(key, filename) {
                    cardBgSelectedKey = String(key || '').trim();
                    cardBgSelectedName = String(filename || '').trim() || cardBgSelectedKey;
                    setCardBgModalMsg('');
                    syncCardBgSelectionUi();
                }

                function closeCardBgModal() {
                    if (!cardBgModal) return;
                    cardBgModal.classList.remove('is-open');
                    cardBgModal.setAttribute('aria-hidden', 'true');
                    setCardBgModalMsg('');
                }

                function appendCardBgLibraryItems(items) {
                    if (!cardBgLibraryGrid) return;
                    (items || []).forEach(function (it) {
                        if (!it || !it.key) return;
                        var cell = document.createElement('button');
                        cell.type = 'button';
                        cell.className = 'card-bg-modal__cell';
                        cell.dataset.s3Key = it.key;
                        cell.title = it.filename || it.key;
                        if (it.key === cardBgSelectedKey) {
                            cell.classList.add('is-selected');
                        }
                        var img = document.createElement('img');
                        img.alt = '';
                        img.loading = 'lazy';
                        img.src = mediaUrlForKey(it.key);
                        var cap = document.createElement('span');
                        cap.className = 'card-bg-modal__cell-cap';
                        cap.textContent = shortenCardBgFilename(it.filename || it.key);
                        cell.appendChild(img);
                        cell.appendChild(cap);
                        cell.addEventListener('click', function () {
                            selectCardBgKey(it.key, it.filename || '');
                        });
                        cardBgLibraryGrid.appendChild(cell);
                    });
                }

                function loadCardBgLibrary(reset) {
                    if (!isRootAdminUser) return Promise.resolve();
                    if (reset) {
                        cardBgNextToken = null;
                        if (cardBgLibraryGrid) cardBgLibraryGrid.innerHTML = '';
                    }
                    setCardBgModalMsg(reset ? 'Загрузка медиатеки…' : 'Загрузка…');
                    return fetch('/api/content_cards/media/list', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(authPayload({
                            continuation_token: reset ? null : cardBgNextToken,
                            limit: 48,
                        })),
                    })
                        .then(function (r) {
                            return r.json().catch(function () { return {}; }).then(function (j) {
                                if (!r.ok) {
                                    var detail = (j && j.detail) || r.statusText || 'Не удалось загрузить медиатеку';
                                    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
                                }
                                return j;
                            });
                        })
                        .then(function (data) {
                            var items = Array.isArray(data && data.items) ? data.items.slice() : [];
                            items.sort(function (a, b) {
                                var ta = a && a.last_modified ? Date.parse(a.last_modified) : 0;
                                var tb = b && b.last_modified ? Date.parse(b.last_modified) : 0;
                                return tb - ta;
                            });
                            cardBgNextToken = data && data.continuation_token ? data.continuation_token : null;
                            if (reset && !items.length && cardBgLibraryGrid) {
                                cardBgLibraryGrid.innerHTML =
                                    '<div class="card-bg-modal__empty">В медиатеке пока нет изображений. Загрузите файл.</div>';
                            } else {
                                if (reset && cardBgLibraryGrid) {
                                    cardBgLibraryGrid.innerHTML = '';
                                }
                                appendCardBgLibraryItems(items);
                            }
                            if (cardBgLoadMoreBtn) {
                                cardBgLoadMoreBtn.style.display = cardBgNextToken ? 'inline-flex' : 'none';
                            }
                            setCardBgModalMsg('');
                            syncCardBgSelectionUi();
                        })
                        .catch(function (e) {
                            setCardBgModalMsg(e && e.message ? e.message : 'Ошибка загрузки медиатеки');
                        });
                }

                function openCardBgModal() {
                    if (!isRootAdminUser || !cardBgModal) return;
                    cardBgSelectedKey = '';
                    cardBgSelectedName = '';
                    syncCardBgSelectionUi();
                    setCardBgModalMsg('');
                    cardBgModal.classList.add('is-open');
                    cardBgModal.setAttribute('aria-hidden', 'false');
                    loadCardBgLibrary(true);
                }

                function uploadCardBgFile(file) {
                    if (!file || cardBgBusy) return;
                    if (!/^image\//i.test(file.type || '')) {
                        setCardBgModalMsg('Нужен файл изображения');
                        return;
                    }
                    setCardBgBusy(true);
                    setCardBgModalMsg('Загрузка в S3…');
                    var fd = new FormData();
                    if (initData) {
                        fd.append('init_data', initData);
                    } else if (fabToken) {
                        fd.append('fab_token', fabToken);
                    }
                    fd.append('file', file, file.name || 'image');
                    fetch('/api/content_cards/media/upload', { method: 'POST', body: fd })
                        .then(function (r) {
                            return r.json().catch(function () { return {}; }).then(function (j) {
                                if (!r.ok) {
                                    var detail = (j && j.detail) || r.statusText || 'Ошибка загрузки';
                                    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
                                }
                                return j;
                            });
                        })
                        .then(function (data) {
                            var key = data && data.s3_key;
                            if (!key) throw new Error('Сервер не вернул s3_key');
                            selectCardBgKey(key, file.name || key);
                            setCardBgModalMsg('Загружено. Можно применить фон.');
                            return loadCardBgLibrary(true);
                        })
                        .catch(function (e) {
                            setCardBgModalMsg(e && e.message ? e.message : 'Ошибка загрузки');
                        })
                        .finally(function () {
                            setCardBgBusy(false);
                            if (cardBgFileInput) cardBgFileInput.value = '';
                        });
                }

                function applyCardBgSelection() {
                    if (!isRootAdminUser || !cardBgSelectedKey || cardBgBusy) return;
                    setCardBgBusy(true);
                    setCardBgModalMsg('Применяю картинку-фон ко всем кадрам…');
                    fetch('/api/content_cards/bulk_canvas_bg/set', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(authPayload({
                            s3_key: cardBgSelectedKey,
                            file_name: cardBgSelectedName || null,
                        })),
                    })
                        .then(function (r) {
                            return r.json().catch(function () { return {}; }).then(function (j) {
                                if (!r.ok) {
                                    var detail = (j && j.detail) || r.statusText || 'Не удалось применить фон';
                                    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
                                }
                                return j;
                            });
                        })
                        .then(function (data) {
                            var msg =
                                'Готово. Карточек: ' + (data.cards_total || 0) +
                                ', изменено: ' + (data.cards_updated || 0) +
                                ', кадров с новым фоном: ' + (data.frames_updated || 0);
                            setCardBgModalMsg(msg);
                            showCabinetNotice(msg, 'Фон кадров');
                        })
                        .catch(function (e) {
                            setCardBgModalMsg(e && e.message ? e.message : 'Ошибка применения');
                        })
                        .finally(function () {
                            setCardBgBusy(false);
                        });
                }

                function clearAllCardImageBackgrounds() {
                    if (!isRootAdminUser || cardBgBusy) return;
                    showCabinetConfirm(
                        'Обнулить фон у всех кадров во всех карточках? Картинка будет снята, цвет станет белым (#ffffff).',
                        'Обнуление фона',
                        { danger: true, confirmLabel: 'Обнулить' }
                    ).then(function (ok) {
                        if (!ok) return;
                        setCardBgBusy(true);
                        setCardBgModalMsg('Обнуляю фон у всех кадров…');
                        fetch('/api/content_cards/bulk_canvas_bg/clear', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(authPayload()),
                        })
                            .then(function (r) {
                                return r.json().catch(function () { return {}; }).then(function (j) {
                                    if (!r.ok) {
                                        var detail = (j && j.detail) || r.statusText || 'Не удалось обнулить';
                                        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
                                    }
                                    return j;
                                });
                            })
                            .then(function (data) {
                                var msg =
                                    'Фон обнулён. Карточек: ' + (data.cards_total || 0) +
                                    ', изменено: ' + (data.cards_updated || 0) +
                                    ', кадров: ' + (data.frames_cleared || 0);
                                setCardBgModalMsg(msg);
                                showCabinetNotice(msg, 'Фон кадров');
                            })
                            .catch(function (e) {
                                setCardBgModalMsg(e && e.message ? e.message : 'Ошибка обнуления');
                            })
                            .finally(function () {
                                setCardBgBusy(false);
                            });
                    });
                }

                function selectedCardIdsCount() {
                    return Object.keys(selectedCardIds).length;
                }

                function getSelectedCardsInCabinetOrder() {
                    if (!Array.isArray(allCards) || !allCards.length) {
                        return [];
                    }
                    var out = [];
                    allCards.forEach(function (row) {
                        var cardIdNum = Number(row && row.content_card_id);
                        if (!Number.isFinite(cardIdNum) || cardIdNum < 1) {
                            return;
                        }
                        if (!selectedCardIds[String(cardIdNum)]) {
                            return;
                        }
                        out.push({
                            id: cardIdNum,
                            number: Number((row && row.__index) || 0) + 1,
                        });
                    });
                    return out;
                }

                function updateSelectionUi() {
                    var selectedCount = getSelectedCardsInCabinetOrder().length;
                    var hasQuickInput = !!(quickSelectInput && String(quickSelectInput.value || '').trim());
                    var quickReady = hasQuickInput && !quickSelectionInvalid && selectedCount > 0;
                    if (selectModeBtn) {
                        selectModeBtn.textContent = isSelectionMode ? 'Выделение' : 'Обычный режим';
                        selectModeBtn.classList.toggle('is-active', isSelectionMode);
                    }
                    var canUseSelectionAction = (isSelectionMode || quickReady) && selectedCount > 0;
                    if (sendSelectedBtn) {
                        sendSelectedBtn.disabled = !canUseSelectionAction;
                    }
                    if (generateLinkBtn) {
                        generateLinkBtn.disabled = !canUseSelectionAction;
                    }
                    if (addToFolderBtn) {
                        addToFolderBtn.disabled = !canUseSelectionAction;
                    }
                }

                function setGenerateLinkModalMsg(msg) {
                    if (!generateLinkModalMsg) return;
                    generateLinkModalMsg.textContent = String(msg || '');
                }

                function closeGenerateLinkModal() {
                    if (!generateLinkModal) return;
                    generateLinkModal.classList.remove('is-open');
                    generateLinkModal.setAttribute('aria-hidden', 'true');
                    setGenerateLinkModalMsg('');
                }

                function openGenerateLinkModal(link) {
                    if (!generateLinkModal || !generateLinkModalInput) return;
                    generatedActivationLink = String(link || '');
                    generateLinkModalInput.value = generatedActivationLink;
                    setGenerateLinkModalMsg('');
                    generateLinkModal.classList.add('is-open');
                    generateLinkModal.setAttribute('aria-hidden', 'false');
                    generateLinkModalInput.focus();
                    generateLinkModalInput.select();
                }

                function copyGeneratedLinkToClipboard() {
                    var textToCopy = generatedActivationLink
                        || (generateLinkModalInput ? String(generateLinkModalInput.value || '').trim() : '');
                    if (!textToCopy) {
                        setGenerateLinkModalMsg('Ссылка еще не сгенерирована.');
                        return;
                    }
                    copyTextToClipboard(textToCopy)
                        .then(function () {
                            setGenerateLinkModalMsg('Ссылка скопирована.');
                            if (generateLinkModalInput) {
                                generateLinkModalInput.focus();
                                generateLinkModalInput.select();
                            }
                        })
                        .catch(function () {
                            setGenerateLinkModalMsg('Не удалось скопировать автоматически. Выделите ссылку и скопируйте вручную.');
                            if (generateLinkModalInput) {
                                generateLinkModalInput.focus();
                                generateLinkModalInput.select();
                            }
                        });
                }

                function clearSelection() {
                    selectedCardIds = {};
                    if (quickSelectInput) {
                        quickSelectInput.value = '';
                        quickSelectInput.classList.remove('is-invalid');
                    }
                    quickSelectionInvalid = false;
                    updateSelectionUi();
                }

                function setSelectionMode(nextValue) {
                    isSelectionMode = !!nextValue;
                    if (!isSelectionMode) {
                        clearSelection();
                    } else {
                        updateSelectionUi();
                    }
                    renderCards();
                }

                function closeAssignModal() {
                    if (!assignCardsModal) return;
                    assignCardsModal.classList.remove('is-open');
                    assignCardsModal.setAttribute('aria-hidden', 'true');
                    setAssignModalMsg('');
                    selectedAssignUserId = null;
                }

                function closeAlreadyHaveModal(confirmed) {
                    if (!assignAlreadyHaveModal) return;
                    assignAlreadyHaveModal.classList.remove('is-open');
                    assignAlreadyHaveModal.setAttribute('aria-hidden', 'true');
                    if (alreadyHaveModalResolver) {
                        var resolver = alreadyHaveModalResolver;
                        alreadyHaveModalResolver = null;
                        resolver(!!confirmed);
                    }
                }

                function openAlreadyHaveModal(cardItems) {
                    return new Promise(function (resolve) {
                        alreadyHaveModalResolver = resolve;
                        if (!assignAlreadyHaveModal || !assignAlreadyHaveModalText) {
                            resolve(false);
                            return;
                        }
                        assignAlreadyHaveModalText.textContent =
                            'У пользователя уже есть карточки: ' + cardItems.join(', ') + '. Продолжить отправку остальных?';
                        assignAlreadyHaveModal.classList.add('is-open');
                        assignAlreadyHaveModal.setAttribute('aria-hidden', 'false');
                    });
                }

                function setAssignUsersLoadingState(isLoading) {
                    if (!assignCardsModalSubmitBtn) return;
                    assignCardsModalSubmitBtn.disabled = !!isLoading;
                }

                function renderAssignUsersTable() {
                    if (!assignUsersTbody) return;
                    assignUsersTbody.innerHTML = '';
                    var filterText = String(assignUsersSearchInput ? assignUsersSearchInput.value : '').trim().toLowerCase();
                    var rows = assignUsers.filter(function (row) {
                        if (!filterText) return true;
                        var idText = String(row && row.id || '');
                        var username = String((row && row.username) || '').toLowerCase();
                        var assignedName = String((row && row.assigned_name) || '').toLowerCase();
                        return idText.indexOf(filterText) !== -1 ||
                            username.indexOf(filterText) !== -1 ||
                            assignedName.indexOf(filterText) !== -1;
                    });

                    if (!rows.length) {
                        var emptyTr = document.createElement('tr');
                        var emptyTd = document.createElement('td');
                        emptyTd.colSpan = 3;
                        emptyTd.textContent = 'Пользователи не найдены.';
                        emptyTr.appendChild(emptyTd);
                        assignUsersTbody.appendChild(emptyTr);
                        return;
                    }

                    rows.forEach(function (row) {
                        var tr = document.createElement('tr');
                        tr.classList.toggle('is-selected', row.id === selectedAssignUserId);
                        tr.addEventListener('click', function () {
                            selectedAssignUserId = row.id;
                            setAssignModalMsg('');
                            renderAssignUsersTable();
                        });

                        var idTd = document.createElement('td');
                        idTd.textContent = String(row.id);
                        tr.appendChild(idTd);

                        var usernameTd = document.createElement('td');
                        usernameTd.textContent = row.username ? ('@' + row.username) : '—';
                        tr.appendChild(usernameTd);

                        var assignedNameTd = document.createElement('td');
                        assignedNameTd.textContent = row.assigned_name || '—';
                        tr.appendChild(assignedNameTd);

                        assignUsersTbody.appendChild(tr);
                    });
                }

                function loadAssignUsers() {
                    if (assignUsersLoaded) {
                        renderAssignUsersTable();
                        return Promise.resolve();
                    }
                    setAssignUsersLoadingState(true);
                    return fetch('/api/content_cards/admin_users', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(authPayload()),
                    })
                        .then(function (r) {
                            if (!r.ok) {
                                return r.json().then(function (j) {
                                    throw new Error(j.detail || r.statusText);
                                }).catch(function () {
                                    throw new Error('Не удалось загрузить пользователей');
                                });
                            }
                            return r.json();
                        })
                        .then(function (data) {
                            assignUsers = Array.isArray(data && data.users) ? data.users : [];
                            assignUsersLoaded = true;
                            renderAssignUsersTable();
                        })
                        .finally(function () {
                            setAssignUsersLoadingState(false);
                        });
                }

                function openAssignModal() {
                    if (!assignCardsModal) return;
                    if (!isRootAdminUser) return;
                    if (getSelectedCardsInCabinetOrder().length < 1) return;
                    if (assignUsersSearchInput) {
                        assignUsersSearchInput.value = '';
                    }
                    selectedAssignUserId = null;
                    setAssignModalMsg('');
                    assignCardsModal.classList.add('is-open');
                    assignCardsModal.setAttribute('aria-hidden', 'false');
                    loadAssignUsers().catch(function (e) {
                        setAssignModalMsg(e && e.message ? e.message : 'Ошибка загрузки списка пользователей');
                    });
                }

                function requestActivationLink() {
                    if (!isRootAdminUser || !generateLinkBtn) return;
                    if (generateLinkModalTitle) {
                        generateLinkModalTitle.textContent = IS_MATCH_ANALYSIS
                            ? 'Одноразовая ссылка на анализы'
                            : 'Одноразовая ссылка';
                    }
                    var selectedCards = getSelectedCardsInCabinetOrder();
                    var selectedIds = selectedCards.map(function (row) { return row.id; });
                    if (!selectedIds.length) {
                        return;
                    }

                    generateLinkBtn.disabled = true;
                    var linkUrl = IS_MATCH_ANALYSIS
                        ? '/api/match_analysis/generate_link'
                        : '/api/content_cards/generate_link';
                    var linkBody = IS_MATCH_ANALYSIS
                        ? authPayload({ match_analysis_ids: selectedIds })
                        : authPayload({ content_card_ids: selectedIds });
                    fetch(linkUrl, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(linkBody),
                    })
                        .then(function (r) {
                            if (!r.ok) {
                                return r.json().then(function (j) {
                                    throw new Error(j.detail || r.statusText);
                                }).catch(function () {
                                    throw new Error('Не удалось сгенерировать ссылку');
                                });
                            }
                            return r.json();
                        })
                        .then(function (data) {
                            var link = String((data && data.link) || '').trim();
                            if (!link) {
                                throw new Error('Сервер не вернул ссылку');
                            }
                            openGenerateLinkModal(link);
                        })
                        .catch(function (e) {
                            showCabinetNotice(
                                e && e.message ? e.message : 'Ошибка генерации ссылки',
                                'Ошибка'
                            );
                        })
                        .finally(function () {
                            updateSelectionUi();
                        });
                }

                function submitSelectedCardsToUser() {
                    if (!selectedAssignUserId) {
                        setAssignModalMsg('Выберите пользователя.');
                        return;
                    }
                    var selectedCards = getSelectedCardsInCabinetOrder();
                    var selectedIds = selectedCards.map(function (row) { return row.id; });
                    var numberByCardId = {};
                    selectedCards.forEach(function (row) {
                        numberByCardId[String(row.id)] = row.number;
                    });
                    if (!selectedCards.length) {
                        setAssignModalMsg(
                            IS_MATCH_ANALYSIS
                                ? 'Выберите хотя бы один анализ.'
                                : 'Выберите хотя бы одну карточку.'
                        );
                        return;
                    }

                    function sendAssignRequest() {
                        if (IS_MATCH_ANALYSIS) {
                            return fetch('/api/match_analysis/assign_to_user', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify(
                                    authPayload({
                                        target_user_id: selectedAssignUserId,
                                        match_analysis_ids: selectedIds,
                                    })
                                ),
                            });
                        }
                        return fetch('/api/content_cards/assign_to_user', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(
                                authPayload({
                                    target_user_id: selectedAssignUserId,
                                    content_card_ids: selectedIds,
                                })
                            ),
                        });
                    }

                    function handleAssignResult(data) {
                        var issuedCount = Number((data && data.issued_count) || 0);
                        var alreadyHadCount = Number((data && data.already_had_count) || 0);
                        var invalidCount = Number((data && data.invalid_count) || 0);
                        var pieces = ['Выдано: ' + issuedCount + '.'];
                        if (alreadyHadCount > 0) {
                            pieces.push('Уже были у пользователя: ' + alreadyHadCount + '.');
                        }
                        if (invalidCount > 0) {
                            pieces.push('Не найдены: ' + invalidCount + '.');
                        }
                        if (data && data.notify_sent === false && data.notify_error) {
                            pieces.push('Уведомление не отправлено: ' + data.notify_error + '.');
                        }
                        return showCabinetNotice(
                            pieces.join(' '),
                            IS_MATCH_ANALYSIS ? 'Анализы отправлены' : 'Карточки отправлены'
                        );
                    }

                    setAssignUsersLoadingState(true);

                    if (IS_MATCH_ANALYSIS) {
                        sendAssignRequest()
                            .then(function (r) {
                                if (!r.ok) {
                                    return r.json().then(function (j) {
                                        throw new Error(j.detail || r.statusText);
                                    }).catch(function () {
                                        throw new Error('Ошибка отправки анализов');
                                    });
                                }
                                return r.json();
                            })
                            .then(handleAssignResult)
                            .then(function () {
                                closeAssignModal();
                                setSelectionMode(false);
                            })
                            .catch(function (e) {
                                setAssignModalMsg(
                                    e && e.message ? e.message : 'Ошибка отправки анализов'
                                );
                            })
                            .finally(function () {
                                setAssignUsersLoadingState(false);
                            });
                        return;
                    }

                    fetch('/api/content_cards/assign_preview', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(
                            authPayload({
                                target_user_id: selectedAssignUserId,
                                content_card_ids: selectedIds,
                            })
                        ),
                    })
                        .then(function (r) {
                            if (!r.ok) {
                                return r.json().then(function (j) {
                                    throw new Error(j.detail || r.statusText);
                                }).catch(function () {
                                    throw new Error('Ошибка проверки карточек');
                                });
                            }
                            return r.json();
                        })
                        .then(function (previewData) {
                            var alreadyHadIds = Array.isArray(previewData && previewData.already_had_ids)
                                ? previewData.already_had_ids
                                : [];
                            if (alreadyHadIds.length) {
                                var numberWithIdItems = alreadyHadIds
                                    .map(function (cardId) {
                                        var n = numberByCardId[String(cardId)];
                                        if (!Number.isFinite(n)) {
                                            return null;
                                        }
                                        return {
                                            number: n,
                                            id: Number(cardId),
                                        };
                                    })
                                    .filter(function (row) { return !!row; })
                                    .sort(function (a, b) { return a.number - b.number; })
                                    .map(function (row) {
                                        return '№' + row.number + ' (id: ' + row.id + ')';
                                    });
                                if (!numberWithIdItems.length) {
                                    numberWithIdItems = alreadyHadIds.map(function (cardId) {
                                        return 'id: ' + cardId;
                                    });
                                }
                                return openAlreadyHaveModal(numberWithIdItems).then(function (confirmed) {
                                    if (!confirmed) {
                                        throw new Error('__PREVIEW_CANCELLED__');
                                    }
                                    return sendAssignRequest();
                                });
                            }
                            return sendAssignRequest();
                        })
                        .then(function (r) {
                            if (!r.ok) {
                                return r.json().then(function (j) {
                                    throw new Error(j.detail || r.statusText);
                                }).catch(function () {
                                    throw new Error('Ошибка отправки карточек');
                                });
                            }
                            return r.json();
                        })
                        .then(handleAssignResult)
                        .then(function () {
                            closeAssignModal();
                            setSelectionMode(false);
                        })
                        .catch(function (e) {
                            if (e && e.message === '__PREVIEW_CANCELLED__') {
                                return;
                            }
                            setAssignModalMsg(e && e.message ? e.message : 'Ошибка отправки карточек');
                        })
                        .finally(function () {
                            setAssignUsersLoadingState(false);
                        });
                }

                if (searchInput) {
                    searchInput.addEventListener('input', function () {
                        if (!IS_MATCH_ANALYSIS) {
                            var digitsOnly = this.value.replace(/\D+/g, '');
                            if (this.value !== digitsOnly) {
                                this.value = digitsOnly;
                            }
                        }
                        saveCabinetState();
                        renderCards();
                    });
                }
                if (statusFilter) {
                    statusFilter.addEventListener('change', function () {
                        saveCabinetState();
                        renderCards();
                    });
                }
                if (labelFilter) {
                    labelFilter.addEventListener('change', function () {
                        saveCabinetState();
                        renderCards();
                    });
                }
                if (scrollToBottomBtn) {
                    scrollToBottomBtn.addEventListener('click', function () {
                        var lastCard = gridEl && gridEl.lastElementChild;
                        if (lastCard && typeof lastCard.scrollIntoView === 'function') {
                            lastCard.scrollIntoView({ behavior: 'smooth', block: 'end' });
                            return;
                        }
                        window.scrollTo({
                            top: Math.max(
                                document.documentElement.scrollHeight || 0,
                                document.body.scrollHeight || 0
                            ),
                            behavior: 'smooth'
                        });
                    });
                }
                if (cardBgOpenBtn) {
                    cardBgOpenBtn.addEventListener('click', openCardBgModal);
                }
                if (cardBgModalOverlay) {
                    cardBgModalOverlay.addEventListener('click', closeCardBgModal);
                }
                if (cardBgCloseBtn) {
                    cardBgCloseBtn.addEventListener('click', closeCardBgModal);
                }
                if (cardBgRefreshBtn) {
                    cardBgRefreshBtn.addEventListener('click', function () {
                        loadCardBgLibrary(true);
                    });
                }
                if (cardBgLoadMoreBtn) {
                    cardBgLoadMoreBtn.addEventListener('click', function () {
                        if (cardBgNextToken) loadCardBgLibrary(false);
                    });
                }
                if (cardBgUploadBtn && cardBgFileInput) {
                    cardBgUploadBtn.addEventListener('click', function () {
                        if (!cardBgBusy) cardBgFileInput.click();
                    });
                    cardBgFileInput.addEventListener('change', function () {
                        var f = cardBgFileInput.files && cardBgFileInput.files[0];
                        if (f) uploadCardBgFile(f);
                    });
                }
                if (cardBgApplyBtn) {
                    cardBgApplyBtn.addEventListener('click', applyCardBgSelection);
                }
                if (cardBgClearBtn) {
                    cardBgClearBtn.addEventListener('click', clearAllCardImageBackgrounds);
                }
                if (cardBgColorInput) {
                    cardBgColorInput.addEventListener('input', function () {
                        syncCardBgColorInputs(true);
                    });
                }
                if (cardBgColorText) {
                    cardBgColorText.addEventListener('change', function () {
                        syncCardBgColorInputs(false);
                    });
                    cardBgColorText.addEventListener('keydown', function (ev) {
                        if (ev.key === 'Enter') {
                            ev.preventDefault();
                            syncCardBgColorInputs(false);
                            applyCardBgColor();
                        }
                    });
                }
                if (cardBgApplyColorBtn) {
                    cardBgApplyColorBtn.addEventListener('click', applyCardBgColor);
                }
                if (labelPresetsOpenBtn) {
                    labelPresetsOpenBtn.addEventListener('click', openLabelPresetsModalCabinet);
                }
                if (labelPresetsModalCabinetAddBtn) {
                    labelPresetsModalCabinetAddBtn.addEventListener('click', addLabelPreset);
                }
                if (labelPresetsModalCabinetInput) {
                    labelPresetsModalCabinetInput.addEventListener('keydown', function (e) {
                        if (e.key === 'Enter') {
                            e.preventDefault();
                            addLabelPreset();
                        }
                    });
                }
                if (labelPresetsModalCabinetOverlay) {
                    labelPresetsModalCabinetOverlay.addEventListener('click', closeLabelPresetsModalCabinet);
                }
                if (labelPresetsModalCabinetCloseBtn) {
                    labelPresetsModalCabinetCloseBtn.addEventListener('click', closeLabelPresetsModalCabinet);
                }

                function reindexAllCards() {
                    allCards.forEach(function (row, index) {
                        row.__index = index;
                    });
                }

                function removeCardFromLists(cardId) {
                    var cardIdNum = Number(cardId);
                    allCards = allCards.filter(function (row) {
                        return Number(row && row.content_card_id) !== cardIdNum;
                    });
                    reindexAllCards();
                    if (shuffledCards && shuffledCards.length) {
                        shuffledCards = shuffledCards.filter(function (row) {
                            return Number(row && row.content_card_id) !== cardIdNum;
                        });
                        if (!shuffledCards.length) {
                            shuffledCards = null;
                        }
                    }
                    delete selectedCardIds[String(cardIdNum)];
                    updateSelectionUi();
                }

                function appendCreateCardTile() {
                    var btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'tile tile--create';
                    btn.textContent = '+';
                    btn.title = 'Создать новую карточку';
                    btn.setAttribute('aria-label', 'Создать новую карточку');
                    btn.addEventListener('click', function () {
                        createEmptyContentCard();
                    });
                    gridEl.appendChild(btn);
                }

                function createEmptyContentCard() {
                    if (!isRootAdminUser || !FEATURES.enable_create_empty) return;
                    showCabinetConfirm('Создать новую пустую карточку?', 'Новая карточка', {
                        confirmLabel: 'Создать',
                    }).then(function (ok) {
                        if (!ok) return;
                        fetch('/api/content_cards/create_empty', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(authPayload({})),
                        })
                            .then(function (r) {
                                if (!r.ok) {
                                    return r.json().then(function (j) {
                                        throw new Error((j && j.detail) || r.statusText);
                                    }).catch(function () {
                                        throw new Error('Не удалось создать карточку');
                                    });
                                }
                                return r.json();
                            })
                            .then(function (data) {
                                var newId = Number(data && data.content_card_id);
                                if (!Number.isFinite(newId) || newId <= 0) {
                                    throw new Error('Некорректный ответ сервера');
                                }
                                var status = String((data && data.status) || 'UNVIEWED').toUpperCase();
                                allCards.push({
                                    content_card_id: newId,
                                    status: status,
                                    labels: [],
                                    notes: '',
                                    is_ready: false,
                                    __index: allCards.length,
                                });
                                reindexAllCards();
                                renderCards();
                            })
                            .catch(function (e) {
                                showCabinetNotice(e.message || String(e), 'Ошибка');
                            });
                    });
                }

                function isCabinetFolderView() {
                    return cabinetConfig.mode === 'folder' && cabinetFolderId != null;
                }

                function deleteContentCard(cardId) {
                    if (!isRootAdminUser || IS_MATCH_ANALYSIS) return;
                    var cardIdNum = Number(cardId);
                    if (!Number.isFinite(cardIdNum) || cardIdNum <= 0) return;
                    var fromFolder = isCabinetFolderView();
                    var confirmMessage = fromFolder
                        ? 'Убрать карточку #' + cardIdNum + ' из этой папки? Сама карточка в базе останется.'
                        : 'Удалить карточку #' + cardIdNum + ' из базы? Это действие необратимо.';
                    var confirmTitle = fromFolder ? 'Убрать из папки' : 'Удаление карточки';
                    var confirmLabel = fromFolder ? 'Убрать' : 'Удалить';
                    var deletedWasReady = false;
                    for (var di = 0; di < allCards.length; di++) {
                        if (Number(allCards[di] && allCards[di].content_card_id) === cardIdNum) {
                            deletedWasReady = !!allCards[di].is_ready;
                            break;
                        }
                    }
                    showCabinetConfirm(confirmMessage, confirmTitle, {
                        danger: true,
                        confirmLabel: confirmLabel,
                    }).then(function (ok) {
                        if (!ok) return;
                        var requestPromise = fromFolder
                            ? folderApiPost('remove_items', {
                                folder_id: cabinetFolderId,
                                card_ids: [cardIdNum],
                            })
                            : fetch('/api/content_cards/delete', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify(authPayload({ content_card_id: cardIdNum })),
                            }).then(function (r) {
                                if (!r.ok) {
                                    return r.json().then(function (j) {
                                        throw new Error((j && j.detail) || r.statusText);
                                    }).catch(function () {
                                        throw new Error('Не удалось удалить карточку');
                                    });
                                }
                                return r.json();
                            });
                        requestPromise
                            .then(function (data) {
                                if (fromFolder) {
                                    var removed = (data && data.removed_count) || 0;
                                    if (!removed) {
                                        throw new Error('Карточка не найдена в этой папке');
                                    }
                                } else if (deletedWasReady) {
                                    bumpReadyForIssueCount(-1);
                                }
                                removeCardFromLists(cardIdNum);
                                renderCards();
                            })
                            .catch(function (e) {
                                showCabinetNotice(e.message || String(e), 'Ошибка');
                            });
                    });
                }

                function setTileReadyButtonState(btn, isReady) {
                    if (!btn) return;
                    var ready = !!isReady;
                    btn.classList.toggle('is-ready', ready);
                    btn.title = ready
                        ? 'Готова к выдаче'
                        : 'Не готова к выдаче';
                    btn.setAttribute(
                        'aria-label',
                        ready
                            ? 'Карточка готова к выдаче'
                            : 'Карточка не готова к выдаче'
                    );
                    btn.innerHTML = ready
                        ? '<i class="fa fa-check" aria-hidden="true"></i>'
                        : '<i class="fa fa-times" aria-hidden="true"></i>';
                }

                function toggleContentCardReady(cardId) {
                    if (!isRootAdminUser) return;
                    var cardIdNum = Number(cardId);
                    if (!Number.isFinite(cardIdNum) || cardIdNum <= 0) return;
                    var row = null;
                    for (var i = 0; i < allCards.length; i++) {
                        if (Number(allCards[i] && allCards[i].content_card_id) === cardIdNum) {
                            row = allCards[i];
                            break;
                        }
                    }
                    if (!row) return;
                    var nextReady = !row.is_ready;
                    var readyUrl = IS_MATCH_ANALYSIS
                        ? '/api/match_analysis/update_meta'
                        : '/api/content_cards/update_meta';
                    var readyBody = IS_MATCH_ANALYSIS
                        ? authPayload({ id: cardIdNum, is_ready: nextReady })
                        : authPayload({ content_card_id: cardIdNum, is_ready: nextReady });
                    fetch(readyUrl, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(readyBody),
                    })
                        .then(function (r) {
                            return parseApiJsonResponse(r, 'Не удалось обновить готовность');
                        })
                        .then(function (data) {
                            var ready = data && typeof data.is_ready === 'boolean'
                                ? !!data.is_ready
                                : nextReady;
                            var wasReady = !!row.is_ready;
                            row.is_ready = ready;
                            if (shuffledCards && shuffledCards.length) {
                                shuffledCards.forEach(function (item) {
                                    if (Number(item && item.content_card_id) === cardIdNum) {
                                        item.is_ready = ready;
                                    }
                                });
                            }
                            if (wasReady !== ready) {
                                bumpReadyForIssueCount(ready ? 1 : -1);
                            }
                            renderCards();
                        })
                        .catch(function (e) {
                            showCabinetNotice(e.message || String(e), 'Ошибка');
                        });
                }

                function matchAnalysisCardTitle(row) {
                    var t = String((row && row.title) || '').trim();
                    if (t) return t;
                    var red = String((row && row.red_player) || '').trim();
                    var black = String((row && row.black_player) || '').trim();
                    if (red || black) {
                        return (red || 'Red') + ' vs ' + (black || 'Black');
                    }
                    var id = (row && row.content_card_id) != null ? row.content_card_id : '';
                    return 'Матч #' + id;
                }

                function truncateMatchTitle(text, maxLen) {
                    var s = String(text || '');
                    var max = maxLen || 28;
                    if (s.length <= max) return s;
                    return s.slice(0, Math.max(1, max - 1)) + '…';
                }

                function closeMatchRenameModal() {
                    matchRenameTargetId = null;
                    if (matchRenameModal) {
                        matchRenameModal.classList.remove('is-open');
                        matchRenameModal.setAttribute('aria-hidden', 'true');
                    }
                    if (matchRenameModalMsg) matchRenameModalMsg.textContent = '';
                    if (matchRenameModalInput) matchRenameModalInput.value = '';
                }

                function openMatchRenameModal(matchId, currentTitle) {
                    matchRenameTargetId = Number(matchId);
                    if (!Number.isFinite(matchRenameTargetId) || matchRenameTargetId <= 0) return;
                    if (matchRenameModalMsg) matchRenameModalMsg.textContent = '';
                    if (matchRenameModalInput) {
                        matchRenameModalInput.value = String(currentTitle || '');
                    }
                    if (matchRenameModal) {
                        matchRenameModal.classList.add('is-open');
                        matchRenameModal.setAttribute('aria-hidden', 'false');
                    }
                    if (matchRenameModalInput) {
                        setTimeout(function () {
                            matchRenameModalInput.focus();
                            matchRenameModalInput.select();
                        }, 0);
                    }
                }

                function saveMatchRename() {
                    if (matchRenameTargetId == null) return;
                    var title = matchRenameModalInput
                        ? String(matchRenameModalInput.value || '').trim()
                        : '';
                    if (!title) {
                        if (matchRenameModalMsg) {
                            matchRenameModalMsg.textContent = 'Название не может быть пустым';
                        }
                        return;
                    }
                    if (matchRenameModalSubmitBtn) matchRenameModalSubmitBtn.disabled = true;
                    if (matchRenameModalMsg) matchRenameModalMsg.textContent = '';
                    fetch('/api/match_analysis/update_meta', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(authPayload({
                            id: matchRenameTargetId,
                            title: title,
                        })),
                    })
                        .then(function (r) {
                            return parseApiJsonResponse(r, 'Не удалось переименовать');
                        })
                        .then(function (payload) {
                            var idStr = String(matchRenameTargetId);
                            allCards.forEach(function (row) {
                                if (String(row.content_card_id) === idStr) {
                                    row.title = (payload && payload.title) || title;
                                }
                            });
                            closeMatchRenameModal();
                            renderCards();
                        })
                        .catch(function (e) {
                            if (matchRenameModalMsg) {
                                matchRenameModalMsg.textContent = e.message || String(e);
                            }
                        })
                        .finally(function () {
                            if (matchRenameModalSubmitBtn) {
                                matchRenameModalSubmitBtn.disabled = false;
                            }
                        });
                }

                function deleteMatchAnalysis(matchId) {
                    if (!isRootAdminUser) return;
                    var matchIdNum = Number(matchId);
                    if (!Number.isFinite(matchIdNum) || matchIdNum <= 0) return;
                    var fromFolder = isCabinetFolderView();
                    var confirmMessage = fromFolder
                        ? 'Убрать матч #' + matchIdNum + ' из этой папки? Сам анализ останется.'
                        : 'Удалить анализ матча #' + matchIdNum + '? Это действие необратимо.';
                    var confirmTitle = fromFolder ? 'Убрать из папки' : 'Удаление анализа';
                    var confirmLabel = fromFolder ? 'Убрать' : 'Удалить';
                    showCabinetConfirm(confirmMessage, confirmTitle, {
                        danger: true,
                        confirmLabel: confirmLabel,
                    }).then(function (ok) {
                        if (!ok) return;
                        var requestPromise = fromFolder
                            ? folderApiPost('remove_items', {
                                folder_id: cabinetFolderId,
                                card_ids: [matchIdNum],
                            })
                            : fetch('/api/match_analysis/delete', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify(authPayload({ id: matchIdNum })),
                            }).then(function (r) {
                                return parseApiJsonResponse(r, 'Не удалось удалить анализ');
                            });
                        requestPromise
                            .then(function (data) {
                                if (fromFolder) {
                                    var removed = (data && data.removed_count) || 0;
                                    if (!removed) {
                                        throw new Error('Матч не найден в этой папке');
                                    }
                                }
                                removeCardFromLists(matchIdNum);
                                renderCards();
                            })
                            .catch(function (e) {
                                showCabinetNotice(e.message || String(e), 'Ошибка');
                            });
                    });
                }

                function renderCards() {
                    gridEl.innerHTML = '';
                    var filter = searchInput ? String(searchInput.value || '').trim().toLowerCase() : '';

                    if (IS_MATCH_ANALYSIS) {
                        var statusFilterValue = statusFilter
                            ? String(statusFilter.value || '').toUpperCase()
                            : '';
                        var maCards = allCards.filter(function (row) {
                            if (statusFilterValue) {
                                var st = String((row && row.status) || 'UNVIEWED').toUpperCase();
                                if (st !== statusFilterValue) return false;
                            }
                            if (!filter) return true;
                            if (maTileDisplayMode === 'order') {
                                return String(getMatchAnalysisDisplayOrder(row)).indexOf(filter) !== -1;
                            }
                            if (maTileDisplayMode === 'id') {
                                return String((row && row.content_card_id) || '').indexOf(filter) !== -1;
                            }
                            var title = matchAnalysisCardTitle(row).toLowerCase();
                            var red = String((row && row.red_player) || '').toLowerCase();
                            var black = String((row && row.black_player) || '').toLowerCase();
                            var idStr = String((row && row.content_card_id) || '');
                            return (
                                title.indexOf(filter) !== -1 ||
                                red.indexOf(filter) !== -1 ||
                                black.indexOf(filter) !== -1 ||
                                idStr.indexOf(filter) !== -1
                            );
                        });
                        if (!maCards.length) {
                            gridEl.innerHTML = allCards.length
                                ? '<p class="empty">Ничего не найдено по запросу.</p>'
                                : (isRootAdminUser
                                    ? '<p class="empty">Пока нет сохранённых анализов</p>'
                                    : '<p class="empty">Вам пока не выданы анализы матча</p>');
                            return;
                        }
                        maCards.forEach(function (row) {
                            var id = row.content_card_id;
                            var cardIdNum = Number(id);
                            var fullTitle = matchAnalysisCardTitle(row);
                            var btn = document.createElement('button');
                            btn.type = 'button';
                            var isSelected = !!selectedCardIds[String(cardIdNum)];
                            applyMatchAnalysisTileDisplay(btn, row, fullTitle, isSelected);
                            btn.title = fullTitle + ' · №' + String(getMatchAnalysisDisplayOrder(row)) +
                                ' · id:' + String(cardIdNum);
                            btn.addEventListener('click', function () {
                                if (isSelectionMode) {
                                    var selectedKey = String(cardIdNum);
                                    if (selectedCardIds[selectedKey]) {
                                        delete selectedCardIds[selectedKey];
                                    } else {
                                        selectedCardIds[selectedKey] = true;
                                    }
                                    updateSelectionUi();
                                    renderCards();
                                    return;
                                }
                                var openMa = function () {
                                    window.location.assign(buildMatchAnalysisViewUrl(id));
                                };
                                var maStatus = String((row && row.status) || 'UNVIEWED').toUpperCase();
                                if (maStatus !== 'UNVIEWED' && maStatus !== 'RECENT') {
                                    openMa();
                                    return;
                                }
                                fetch('/api/match_analysis/mark_viewed', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify(authPayload({ id: Number(id) })),
                                }).catch(function () {
                                    // Даже если отметка статуса не удалась, всё равно открываем.
                                }).finally(openMa);
                            });
                            if (!isRootAdminUser) {
                                gridEl.appendChild(btn);
                                return;
                            }
                            var tileWrap = document.createElement('div');
                            tileWrap.className = 'tile-wrap';
                            var editBtn = document.createElement('button');
                            editBtn.type = 'button';
                            editBtn.className = 'tile__edit-notes';
                            editBtn.title = 'Переименовать';
                            editBtn.setAttribute('aria-label', 'Переименовать матч #' + id);
                            editBtn.innerHTML =
                                '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
                                '<path d="M4 20h4l10.5-10.5a1.4 1.4 0 0 0 0-2L14.5 3.5a1.4 1.4 0 0 0-2 0L3 13v4Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>' +
                                '<path d="M13.5 5.5l5 5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>' +
                                '</svg>';
                            editBtn.addEventListener('click', function (ev) {
                                ev.stopPropagation();
                                ev.preventDefault();
                                openMatchRenameModal(cardIdNum, row.title || fullTitle);
                            });
                            var readyBtn = document.createElement('button');
                            readyBtn.type = 'button';
                            readyBtn.className = 'tile__ready';
                            setTileReadyButtonState(readyBtn, !!row.is_ready);
                            readyBtn.addEventListener('click', function (ev) {
                                ev.stopPropagation();
                                ev.preventDefault();
                                toggleContentCardReady(cardIdNum);
                            });
                            var delBtn = document.createElement('button');
                            delBtn.type = 'button';
                            delBtn.className = 'tile__del';
                            var fromFolder = isCabinetFolderView();
                            delBtn.setAttribute(
                                'aria-label',
                                fromFolder
                                    ? 'Убрать матч #' + id + ' из папки'
                                    : 'Удалить матч #' + id
                            );
                            delBtn.title = fromFolder
                                ? 'Убрать матч из папки'
                                : 'Удалить анализ';
                            delBtn.textContent = '×';
                            delBtn.addEventListener('click', function (ev) {
                                ev.stopPropagation();
                                ev.preventDefault();
                                deleteMatchAnalysis(cardIdNum);
                            });
                            var audioBtn = document.createElement('button');
                            audioBtn.type = 'button';
                            audioBtn.className = 'tile__audio';
                            audioBtn.setAttribute('data-match-id', String(cardIdNum));
                            var audioCount = Number(row && row.audio_count) || 0;
                            var audioMinutes = Math.max(
                                0,
                                Math.floor(Number(row && row.audio_minutes) || 0)
                            );
                            if (audioCount > 0) {
                                audioBtn.classList.add('has-audio');
                            }
                            audioBtn.title = audioCount > 0
                                ? ('Аудиофайлы (' + audioCount + ')')
                                : 'Аудиофайлы анализа';
                            audioBtn.setAttribute('aria-label', 'Аудиофайлы анализа #' + id);
                            audioBtn.innerHTML = '<i class="fa fa-headphones" aria-hidden="true"></i>';
                            audioBtn.addEventListener('click', function (ev) {
                                ev.stopPropagation();
                                ev.preventDefault();
                                if (
                                    window.CardsCabinetMatchAudio &&
                                    typeof window.CardsCabinetMatchAudio.open === 'function'
                                ) {
                                    window.CardsCabinetMatchAudio.open(cardIdNum, fullTitle);
                                }
                            });
                            var audioMinutesEl = document.createElement('span');
                            audioMinutesEl.className = 'tile__audio-minutes';
                            audioMinutesEl.setAttribute('data-match-id', String(cardIdNum));
                            audioMinutesEl.textContent = String(audioMinutes);
                            tileWrap.appendChild(editBtn);
                            tileWrap.appendChild(btn);
                            tileWrap.appendChild(readyBtn);
                            tileWrap.appendChild(audioMinutesEl);
                            tileWrap.appendChild(audioBtn);
                            tileWrap.appendChild(delBtn);
                            gridEl.appendChild(tileWrap);
                        });
                        return;
                    }

                    var statusFilterValue = statusFilter ? String(statusFilter.value || '').toUpperCase() : '';
                    var labelFilterValue = labelFilter ? String(labelFilter.value || '') : '';
                    var sourceCards = shuffledCards && shuffledCards.length ? shuffledCards : allCards;
                    var cards = sourceCards.filter(function (row) {
                        var cardNumber = String(getCardDisplayId(row));
                        var status = String((row && row.status) || 'UNVIEWED').toUpperCase();
                        var labels = Array.isArray(row && row.labels) ? row.labels : [];
                        var passNumber = !filter || cardNumber.indexOf(filter) !== -1;
                        var passStatus = !statusFilterValue || status === statusFilterValue;
                        var passLabel = !labelFilterValue || labels.indexOf(labelFilterValue) !== -1;
                        return passNumber && passStatus && passLabel;
                    });

                    if (!cards.length && !isRootAdminUser) {
                        gridEl.innerHTML = '<p class="empty">Карточки по вашему запросу не найдены.</p>';
                        return;
                    }

                    cards.forEach(function (row) {
                        var id = row.content_card_id;
                        var index = row.__index;
                        var status = String((row && row.status) || 'UNVIEWED').toUpperCase();
                        var cardIdNum = Number(id);
                        var btn = document.createElement('button');
                        btn.type = 'button';
                        btn.className = 'tile';
                        if (status === 'VIEWED') {
                            btn.classList.add('tile--viewed');
                        } else if (status === 'SOLVED') {
                            btn.classList.add('tile--solved');
                        } else if (status === 'FAVORITE') {
                            btn.classList.add('tile--favorite');
                        } else if (status === 'HARD') {
                            btn.classList.add('tile--hard');
                        } else if (status === 'RECENT') {
                            btn.classList.add('tile--recent');
                        }
                        if (selectedCardIds[String(cardIdNum)]) {
                            btn.classList.add('tile--selected');
                        }
                        var displayId = getCardDisplayId(row);
                        btn.textContent = String(displayId);
                        btn.title = getCardHoverTitle(row, cardIdNum);
                        btn.addEventListener('click', function () {
                            if (isSelectionMode) {
                                var selectedKey = String(cardIdNum);
                                if (selectedCardIds[selectedKey]) {
                                    delete selectedCardIds[selectedKey];
                                } else {
                                    selectedCardIds[selectedKey] = true;
                                }
                                updateSelectionUi();
                                renderCards();
                                return;
                            }
                            var cardNumber = index + 1;
                            var openCard = function () {
                                var cacheBust = Date.now();
                                var cardParams = new URLSearchParams({
                                    content_card_id: String(id),
                                    card_number: String(cardNumber),
                                    v: String(cacheBust),
                                });
                                if (fabToken) {
                                    cardParams.set('fab_token', fabToken);
                                }
                                if (cabinetConfig.mode === 'folder' && cabinetConfig.folderToken) {
                                    cardParams.set('folder_token', cabinetConfig.folderToken);
                                }
                                cardParams.set('pool', CABINET_POOL);
                                window.location.assign(
                                    '/content-card-view?' + cardParams.toString()
                                );
                            };
                            if (status !== 'UNVIEWED' && status !== 'RECENT') {
                                openCard();
                                return;
                            }
                            fetch('/api/content_cards/mark_viewed', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify(
                                    authPayload({ content_card_id: Number(id) })
                                ),
                            }).catch(function () {
                                // Даже если отметка статуса не удалась, всё равно открываем карточку.
                            }).finally(openCard);
                        });
                        if (isRootAdminUser) {
                            var tileWrap = document.createElement('div');
                            tileWrap.className = 'tile-wrap';
                            var editNotesBtn = document.createElement('button');
                            editNotesBtn.type = 'button';
                            editNotesBtn.className = 'tile__edit-notes';
                            editNotesBtn.title = 'Изменить описание';
                            editNotesBtn.setAttribute('aria-label', 'Изменить описание карточки #' + id);
                            editNotesBtn.innerHTML =
                                '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
                                '<path d="M4 20h4l10.5-10.5a1.4 1.4 0 0 0 0-2L14.5 3.5a1.4 1.4 0 0 0-2 0L3 13v4Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>' +
                                '<path d="M13.5 5.5l5 5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>' +
                                '</svg>';
                            editNotesBtn.addEventListener('click', function (ev) {
                                ev.stopPropagation();
                                ev.preventDefault();
                                openCardNotesModal(cardIdNum, row.notes || '');
                            });
                            var readyBtn = document.createElement('button');
                            readyBtn.type = 'button';
                            readyBtn.className = 'tile__ready';
                            setTileReadyButtonState(readyBtn, !!row.is_ready);
                            readyBtn.addEventListener('click', function (ev) {
                                ev.stopPropagation();
                                ev.preventDefault();
                                toggleContentCardReady(cardIdNum);
                            });
                            var delBtn = document.createElement('button');
                            delBtn.type = 'button';
                            delBtn.className = 'tile__del';
                            var fromFolder = isCabinetFolderView();
                            delBtn.setAttribute(
                                'aria-label',
                                fromFolder
                                    ? 'Убрать карточку #' + id + ' из папки'
                                    : 'Удалить карточку #' + id
                            );
                            delBtn.title = fromFolder
                                ? 'Убрать карточку из папки'
                                : 'Удалить карточку из базы';
                            delBtn.textContent = '×';
                            delBtn.addEventListener('click', function (ev) {
                                ev.stopPropagation();
                                ev.preventDefault();
                                deleteContentCard(cardIdNum);
                            });
                            tileWrap.appendChild(editNotesBtn);
                            tileWrap.appendChild(readyBtn);
                            tileWrap.appendChild(btn);
                            tileWrap.appendChild(delBtn);
                            gridEl.appendChild(tileWrap);
                        } else {
                            gridEl.appendChild(btn);
                        }
                    });
                    if (isRootAdminUser && FEATURES.enable_create_empty) {
                        appendCreateCardTile();
                    }
                }

                function closeInteractiveStatsModal() {
                    if (!interactiveStatsModal) return;
                    interactiveStatsModal.classList.remove('is-open');
                    interactiveStatsModal.setAttribute('aria-hidden', 'true');
                    if (interactiveStatsModalBody) {
                        interactiveStatsModalBody.textContent = '';
                    }
                }

                function renderInteractiveStatsBody(c, w) {
                    if (!interactiveStatsModalBody) return;
                    var totalAttempts = c + w;
                    var correctPct =
                        totalAttempts > 0
                            ? String(Math.round((c / totalAttempts) * 100))
                            : '—';
                    interactiveStatsModalBody.innerHTML =
                        'Верных ответов: <strong>' +
                        c +
                        '</strong><br>Ошибок: <strong>' +
                        w +
                        '</strong><br>Процент верных решений: <strong>' +
                        correctPct +
                        (totalAttempts > 0 ? '%' : '') +
                        '</strong>';
                }

                function loadInteractiveStatsModal() {
                    if (!interactiveStatsModal || !interactiveStatsModalBody) return;
                    interactiveStatsModalBody.textContent = 'Загрузка…';
                    fetch('/api/content_cards/interactive/stats_total', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(authPayload({}))
                    })
                        .then(function (r) {
                            return r.json().then(function (data) {
                                return { ok: r.ok, data: data };
                            });
                        })
                        .then(function (res) {
                            if (!res.ok) {
                                var d = res.data && res.data.detail;
                                interactiveStatsModalBody.textContent =
                                    typeof d === 'string' ? d : 'Не удалось загрузить статистику';
                                return;
                            }
                            var c = Number((res.data && res.data.correct_count) || 0);
                            var w = Number((res.data && res.data.wrong_count) || 0);
                            renderInteractiveStatsBody(c, w);
                        })
                        .catch(function () {
                            interactiveStatsModalBody.textContent = 'Ошибка сети';
                        });
                }

                function openInteractiveStatsModal() {
                    if (!interactiveStatsModal || !interactiveStatsModalBody) return;
                    interactiveStatsModal.classList.add('is-open');
                    interactiveStatsModal.setAttribute('aria-hidden', 'false');
                    loadInteractiveStatsModal();
                }

                function clearInteractiveStats() {
                    if (!window.confirm('Очистить статистику? После этого можно будет снова пройти карточки.')) {
                        return;
                    }
                    if (!interactiveStatsModalBody) return;
                    interactiveStatsModalBody.textContent = 'Очистка…';
                    fetch('/api/content_cards/interactive/stats_clear', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(authPayload({}))
                    })
                        .then(function (r) {
                            return r.json().then(function (data) {
                                return { ok: r.ok, data: data };
                            });
                        })
                        .then(function (res) {
                            if (!res.ok) {
                                var d = res.data && res.data.detail;
                                interactiveStatsModalBody.textContent =
                                    typeof d === 'string' ? d : 'Не удалось очистить статистику';
                                return;
                            }
                            renderInteractiveStatsBody(0, 0);
                        })
                        .catch(function () {
                            interactiveStatsModalBody.textContent = 'Ошибка сети';
                        });
                }

                function setShuffleModalMsg(msg) {
                    if (!shuffleModalMsg) return;
                    shuffleModalMsg.textContent = String(msg || '');
                }

                function closeShuffleModal() {
                    if (!shuffleModal) return;
                    shuffleModal.classList.remove('is-open');
                    shuffleModal.setAttribute('aria-hidden', 'true');
                    setShuffleModalMsg('');
                }

                function openShuffleModal() {
                    if (!shuffleModal) return;
                    if (shuffleCountInput) {
                        shuffleCountInput.value = String(Math.min(allCards.length || 1, 20));
                    }
                    setShuffleModalMsg('');
                    shuffleModal.classList.add('is-open');
                    shuffleModal.setAttribute('aria-hidden', 'false');
                }

                function collectSelectedShuffleStatuses() {
                    if (!shuffleModal) return [];
                    var checks = shuffleModal.querySelectorAll('input[name="shuffle-status"]:checked');
                    var out = [];
                    checks.forEach(function (el) {
                        var v = String((el && el.value) || '').toUpperCase();
                        if (v) out.push(v);
                    });
                    return out;
                }

                function applyShuffleSelection() {
                    if (!allCards || !allCards.length) {
                        setShuffleModalMsg('Нет карточек для выборки.');
                        return;
                    }
                    var count = parseInt(shuffleCountInput ? shuffleCountInput.value : '', 10);
                    if (!Number.isFinite(count) || count <= 0) {
                        setShuffleModalMsg('Введите корректное количество (> 0).');
                        return;
                    }
                    var selectedStatuses = collectSelectedShuffleStatuses();
                    if (!selectedStatuses.length) {
                        setShuffleModalMsg('Выберите хотя бы один статус.');
                        return;
                    }

                    var candidates = allCards.filter(function (row) {
                        var status = String((row && row.status) || 'UNVIEWED').toUpperCase();
                        return selectedStatuses.indexOf(status) !== -1;
                    });
                    if (!candidates.length) {
                        setShuffleModalMsg('По выбранным статусам карточек нет.');
                        return;
                    }

                    var pool = candidates.slice();
                    for (var i = pool.length - 1; i > 0; i--) {
                        var j = Math.floor(Math.random() * (i + 1));
                        var tmp = pool[i];
                        pool[i] = pool[j];
                        pool[j] = tmp;
                    }
                    var limit = Math.min(count, pool.length);
                    shuffledCards = pool.slice(0, limit);
                    closeShuffleModal();
                    renderCards();
                }

                if (shuffleCardsBtn) {
                    shuffleCardsBtn.addEventListener('click', function () {
                        openShuffleModal();
                    });
                }
                if (idToggleBtn) {
                    idToggleBtn.addEventListener('click', function () {
                        if (IS_MATCH_ANALYSIS) {
                            cycleMaTileDisplayMode();
                            updateMaTileDisplayModeUi();
                        } else {
                            isDbIdMode = !isDbIdMode;
                            updateIdModeUi();
                        }
                        saveCabinetState();
                        renderCards();
                    });
                    if (IS_MATCH_ANALYSIS) {
                        updateMaTileDisplayModeUi();
                    } else {
                        updateIdModeUi();
                    }
                }
                if (shuffleModalOverlay) {
                    shuffleModalOverlay.addEventListener('click', closeShuffleModal);
                }
                if (shuffleModalCancelBtn) {
                    shuffleModalCancelBtn.addEventListener('click', closeShuffleModal);
                }
                if (shuffleModalApplyBtn) {
                    shuffleModalApplyBtn.addEventListener('click', applyShuffleSelection);
                }
                if (shuffleModalResetBtn) {
                    shuffleModalResetBtn.addEventListener('click', function () {
                        shuffledCards = null;
                        closeShuffleModal();
                        renderCards();
                    });
                }
                if (interactiveStatsModalOverlay) {
                    interactiveStatsModalOverlay.addEventListener('click', closeInteractiveStatsModal);
                }
                if (interactiveStatsModalCloseBtn) {
                    interactiveStatsModalCloseBtn.addEventListener('click', closeInteractiveStatsModal);
                }
                if (interactiveStatsModalClearBtn) {
                    interactiveStatsModalClearBtn.addEventListener('click', clearInteractiveStats);
                }
                if (cabinetInteractiveStatsBtn) {
                    cabinetInteractiveStatsBtn.addEventListener('click', function () {
                        openInteractiveStatsModal();
                    });
                }
                if (selectModeBtn) {
                    selectModeBtn.addEventListener('click', function () {
                        setSelectionMode(!isSelectionMode);
                    });
                }
                if (sendSelectedBtn) {
                    sendSelectedBtn.addEventListener('click', openAssignModal);
                }
                if (generateLinkBtn) {
                    generateLinkBtn.addEventListener('click', requestActivationLink);
                }
                if (quickSelectInput) {
                    quickSelectInput.addEventListener('input', applyQuickSelectionFromInput);
                }
                if (assignUsersSearchInput) {
                    assignUsersSearchInput.addEventListener('input', renderAssignUsersTable);
                }
                if (assignCardsModalOverlay) {
                    assignCardsModalOverlay.addEventListener('click', closeAssignModal);
                }
                if (assignCardsModalCancelBtn) {
                    assignCardsModalCancelBtn.addEventListener('click', closeAssignModal);
                }
                if (assignCardsModalSubmitBtn) {
                    assignCardsModalSubmitBtn.addEventListener('click', submitSelectedCardsToUser);
                }
                if (assignAlreadyHaveModalOverlay) {
                    assignAlreadyHaveModalOverlay.addEventListener('click', function () {
                        closeAlreadyHaveModal(false);
                    });
                }
                if (assignAlreadyHaveCancelBtn) {
                    assignAlreadyHaveCancelBtn.addEventListener('click', function () {
                        closeAlreadyHaveModal(false);
                    });
                }
                if (assignAlreadyHaveContinueBtn) {
                    assignAlreadyHaveContinueBtn.addEventListener('click', function () {
                        closeAlreadyHaveModal(true);
                    });
                }
                if (generateLinkModalOverlay) {
                    generateLinkModalOverlay.addEventListener('click', closeGenerateLinkModal);
                }
                if (generateLinkModalCloseBtn) {
                    generateLinkModalCloseBtn.addEventListener('click', closeGenerateLinkModal);
                }
                if (generateLinkModalCopyBtn) {
                    generateLinkModalCopyBtn.addEventListener('click', copyGeneratedLinkToClipboard);
                }
                if (cabinetGalleryBtn) {
                    cabinetGalleryBtn.addEventListener('click', openCabinetGalleryModal);
                }
                if (cabinetGalleryModalOverlay) {
                    cabinetGalleryModalOverlay.addEventListener('click', closeCabinetGalleryModal);
                }
                if (cabinetGalleryModalClose) {
                    cabinetGalleryModalClose.addEventListener('click', closeCabinetGalleryModal);
                }
                if (cabinetGalleryUploadBtn && cabinetGalleryFile) {
                    cabinetGalleryUploadBtn.addEventListener('click', function (ev) {
                        ev.preventDefault();
                        ev.stopPropagation();
                        if (!galleryCanManage) return;
                        cabinetGalleryFile.click();
                    });
                }
                if (cabinetGalleryGrid) {
                    cabinetGalleryGrid.addEventListener('click', function (ev) {
                        if (ev.target && ev.target.closest && ev.target.closest('.cabinet-gallery-modal__del')) {
                            return;
                        }
                        var cell = ev.target && ev.target.closest
                            ? ev.target.closest('.cabinet-gallery-modal__cell')
                            : null;
                        if (!cell || !cell.dataset || !cell.dataset.s3Key) {
                            return;
                        }
                        ev.preventDefault();
                        requestGalleryImageShareLink(cell.dataset.s3Key);
                    });
                }
                if (cabinetGalleryPrev) {
                    cabinetGalleryPrev.addEventListener('click', function (ev) {
                        ev.preventDefault();
                        ev.stopPropagation();
                        goCabinetGalleryPrev();
                    });
                }
                if (cabinetGalleryNext) {
                    cabinetGalleryNext.addEventListener('click', function (ev) {
                        ev.preventDefault();
                        ev.stopPropagation();
                        goCabinetGalleryNext();
                    });
                }
                if (cabinetGalleryModal) {
                    cabinetGalleryModal.addEventListener('keydown', function (ev) {
                        if (!cabinetGalleryModal.classList.contains('is-open')) return;
                        if (ev.key === 'ArrowLeft') {
                            ev.preventDefault();
                            goCabinetGalleryPrev();
                        } else if (ev.key === 'ArrowRight') {
                            ev.preventDefault();
                            goCabinetGalleryNext();
                        }
                    }, true);
                }
                function cabinetGalleryDataTransferHasFiles(dt) {
                    if (!dt || !dt.types) return false;
                    for (var ti = 0; ti < dt.types.length; ti++) {
                        if (dt.types[ti] === 'Files') return true;
                    }
                    return false;
                }
                if (cabinetGalleryModalBox) {
                    cabinetGalleryModalBox.addEventListener('dragover', function (ev) {
                        if (!cabinetGalleryModalBox.classList.contains('is-admin')) return;
                        if (!cabinetGalleryDataTransferHasFiles(ev.dataTransfer)) return;
                        ev.preventDefault();
                        ev.stopPropagation();
                    }, true);
                    cabinetGalleryModalBox.addEventListener('drop', function (ev) {
                        if (!cabinetGalleryModalBox.classList.contains('is-admin')) return;
                        ev.preventDefault();
                        ev.stopPropagation();
                        if (ev.dataTransfer && ev.dataTransfer.files) {
                            uploadCabinetGalleryFiles(ev.dataTransfer.files);
                        }
                    }, true);
                    cabinetGalleryModalBox.addEventListener('click', function (ev) {
                        if (!galleryCanManage || !cabinetGalleryFile) return;
                        var t = ev.target;
                        if (t && t.closest && t.closest('.cabinet-gallery-modal__toolbar')) return;
                        if (t && t.closest && t.closest('.cabinet-gallery-modal__cell')) return;
                        if (t && t.closest && t.closest('.cabinet-gallery-modal__nav')) return;
                        if (t && t.closest && t.closest('.cabinet-gallery-modal__counter')) return;
                        if (t && t.id === 'cabinetGalleryMsg') return;
                        cabinetGalleryFile.click();
                    });
                }
                if (cabinetGalleryFile) {
                    cabinetGalleryFile.addEventListener('change', function () {
                        if (cabinetGalleryFile.files) {
                            uploadCabinetGalleryFiles(cabinetGalleryFile.files);
                        }
                        cabinetGalleryFile.value = '';
                    });
                }
                updateSelectionUi();

                // ── Кабинет: единая инициализация (main | folder) ───────────
                var folderViewBar = document.getElementById('folder-view-bar');
                var folderViewSubfolders = document.getElementById('folder-view-subfolders');

                function parseApiJsonResponse(r, fallbackMessage) {
                    if (!r.ok) {
                        return r.json().then(function (j) {
                            throw new Error(j.detail || r.statusText);
                        }).catch(function () {
                            throw new Error(fallbackMessage || 'Ошибка');
                        });
                    }
                    return r.json();
                }

                var readyForIssueCount = 0;
                var cabinetAdminStatus = document.getElementById('cabinet-admin-status');
                var readyForIssueCountEl = document.getElementById('ready-for-issue-count');

                function setReadyForIssueCount(count) {
                    var n = Number(count);
                    readyForIssueCount = Number.isFinite(n) && n > 0 ? Math.floor(n) : 0;
                    if (readyForIssueCountEl) {
                        readyForIssueCountEl.textContent = String(readyForIssueCount);
                    }
                }

                function bumpReadyForIssueCount(delta) {
                    setReadyForIssueCount(readyForIssueCount + Number(delta || 0));
                }

                function updateAdminStatusBar() {
                    var show = isRootAdminUser;
                    if (cabinetAdminStatus) {
                        cabinetAdminStatus.classList.toggle('is-visible', show);
                    }
                }

                function applyRootAdminCabinetUi() {
                    if (!isRootAdminUser) return;
                    updateAdminStatusBar();
                    if (FEATURES.enable_admin_fab && adminFabBtn) {
                        adminFabBtn.classList.add('is-visible');
                    }
                    if (FEATURES.enable_folders && manageFoldersBtn) {
                        manageFoldersBtn.classList.add('is-visible');
                    }
                    if (FEATURES.enable_folders && addToFolderBtn) {
                        addToFolderBtn.classList.add('is-visible');
                    }
                    if (FEATURES.enable_selection && selectModeBtn) {
                        selectModeBtn.classList.add('is-visible');
                    }
                    if (FEATURES.enable_selection && quickSelectInput) {
                        quickSelectInput.classList.add('is-visible');
                    }
                    if (FEATURES.enable_selection && sendSelectedBtn) {
                        sendSelectedBtn.classList.add('is-visible');
                        if (IS_MATCH_ANALYSIS) {
                            sendSelectedBtn.title = 'Отправить выбранные анализы пользователю';
                            sendSelectedBtn.setAttribute(
                                'aria-label',
                                'Отправить выбранные анализы пользователю'
                            );
                        }
                    }
                    if (FEATURES.enable_selection && generateLinkBtn) {
                        generateLinkBtn.classList.add('is-visible');
                        if (IS_MATCH_ANALYSIS) {
                            generateLinkBtn.title = 'Получить одноразовую ссылку на анализы';
                            generateLinkBtn.setAttribute(
                                'aria-label',
                                'Получить одноразовую ссылку на анализы'
                            );
                        }
                    }
                    if (IS_MATCH_ANALYSIS && userPreviewToggleWrap) {
                        userPreviewToggleWrap.style.display = '';
                    }
                    if (!IS_MATCH_ANALYSIS) {
                        if (FEATURES.enable_labels && labelFilterWrap) {
                            labelFilterWrap.classList.add('is-visible');
                        }
                        if (FEATURES.enable_bulk_bg && cardBgOpenBtn) {
                            cardBgOpenBtn.classList.add('is-visible');
                        }
                        if (FEATURES.enable_labels && scrollToBottomBtn) {
                            scrollToBottomBtn.classList.add('is-visible');
                        }
                        if (FEATURES.enable_labels && labelPresetsOpenBtn) {
                            labelPresetsOpenBtn.classList.add('is-visible');
                        }
                    }
                }

                function hideFolderSubfoldersBar() {
                    if (!folderViewBar) return;
                    folderViewBar.classList.remove('is-visible');
                    folderViewBar.setAttribute('aria-hidden', 'true');
                    if (folderViewSubfolders) folderViewSubfolders.innerHTML = '';
                }

                function renderFolderSubfoldersBar(payload) {
                    if (!folderViewBar || !folderViewSubfolders) return;
                    var children = (payload && payload.child_folders) || [];
                    folderViewSubfolders.innerHTML = '';
                    children.forEach(function (child) {
                        var chip = document.createElement('button');
                        chip.type = 'button';
                        chip.className = 'folder-view-bar__chip';
                        var cnt = child.direct_cards_count || 0;
                        chip.textContent = child.name + (cnt ? ' (' + cnt + ')' : '');
                        chip.addEventListener('click', function () {
                            navigateToFolder(child.id, child.link_token || '');
                        });
                        folderViewSubfolders.appendChild(chip);
                    });
                    folderViewBar.classList.add('is-visible');
                    folderViewBar.setAttribute('aria-hidden', 'false');
                }

                function getNewFolderParentId() {
                    if (cabinetConfig.mode === 'folder' && cabinetFolderId) {
                        return cabinetFolderId;
                    }
                    return null;
                }

                function normalizeMatchAnalysisCard(it, index) {
                    var mid = it.id != null ? it.id : it.content_card_id;
                    var ready = !!it.is_ready;
                    var status = String(it.status || 'UNVIEWED').toUpperCase();
                    return {
                        content_card_id: mid,
                        title: it.title || '',
                        red_player: it.red_player || '',
                        black_player: it.black_player || '',
                        notes: it.notes || '',
                        is_ready: ready,
                        status: status,
                        labels: [],
                        audio_count: Number(it.audio_count) || 0,
                        audio_seconds: Number(it.audio_seconds) || 0,
                        audio_minutes: Math.max(0, Math.floor(Number(it.audio_minutes) || 0)),
                        __index: index,
                    };
                }

                function fetchCabinetData(config) {
                    if (IS_MATCH_ANALYSIS) {
                        if (config.mode === 'folder') {
                            return fetch('/api/match_analysis/folders/link_resolve', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify(authPayload({
                                    folder_token: config.folderToken,
                                    direct_only: true,
                                })),
                            })
                                .then(function (r) {
                                    return parseApiJsonResponse(r, 'Ошибка загрузки папки');
                                })
                                .then(function (data) {
                                    var cards = (data && data.cards) || [];
                                    return {
                                        is_root_admin: !!(data && data.is_root_admin),
                                        folder: data && data.folder,
                                        child_folders: (data && data.child_folders) || [],
                                        cards: cards.map(function (card, index) {
                                            return normalizeMatchAnalysisCard(card, index);
                                        }),
                                    };
                                });
                        }
                        return fetch('/api/match_analysis/list', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(authPayload()),
                        })
                            .then(function (r) {
                                return parseApiJsonResponse(r, 'Ошибка загрузки списка');
                            })
                            .then(function (data) {
                                var items = (data && data.items) || [];
                                return {
                                    is_root_admin: !!(data && data.is_root_admin),
                                    ready_for_issue_count: Number(
                                        (data && data.ready_for_issue_count) || 0
                                    ),
                                    folder: null,
                                    child_folders: [],
                                    cards: items.map(function (it, index) {
                                        return normalizeMatchAnalysisCard(it, index);
                                    }),
                                };
                            });
                    }
                    if (config.mode === 'folder') {
                        return fetch('/api/content_cards/folders/link_resolve', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(authPayload({
                                folder_token: config.folderToken,
                                direct_only: true,
                            })),
                        })
                            .then(function (r) {
                                return parseApiJsonResponse(r, 'Ошибка загрузки папки');
                            })
                            .then(function (data) {
                                var cards = (data && data.cards) || [];
                                return {
                                    is_root_admin: !!(data && data.is_root_admin),
                                    ready_for_issue_count: Number(
                                        (data && data.ready_for_issue_count) || 0
                                    ),
                                    folder: data && data.folder,
                                    child_folders: (data && data.child_folders) || [],
                                    cards: cards.map(function (card, index) {
                                        return {
                                            content_card_id: card.id,
                                            status: 'UNVIEWED',
                                            labels: card.labels || [],
                                            notes: (card.notes || '').trim(),
                                            is_ready: !!card.is_ready,
                                            __index: index,
                                        };
                                    }),
                                };
                            });
                    }
                    return fetch('/api/content_cards/my_list', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(authPayload()),
                    })
                        .then(function (r) {
                            return parseApiJsonResponse(r, 'Ошибка загрузки списка');
                        })
                        .then(function (data) {
                            var cards = (data && data.cards) || [];
                            return {
                                is_root_admin: !!(data && data.is_root_admin),
                                ready_for_issue_count: Number(
                                    (data && data.ready_for_issue_count) || 0
                                ),
                                folder: null,
                                child_folders: [],
                                cards: cards.map(function (row, index) {
                                    return Object.assign({}, row, { __index: index });
                                }),
                            };
                        });
                }

                function updateFolderNavButtons(payload, config) {
                    var folder = payload && payload.folder;
                    var inFolderView = config.mode === 'folder';
                    var parentId = folder && folder.parent_id != null ? Number(folder.parent_id) : null;
                    cabinetParentFolderId = parentId;

                    if (cabinetHomeBtn) {
                        cabinetHomeBtn.classList.toggle('is-visible', inFolderView && isRootAdminUser);
                    }
                    if (cabinetBackToParentBtn) {
                        cabinetBackToParentBtn.classList.toggle(
                            'is-visible',
                            inFolderView && parentId != null && parentId > 0
                        );
                    }
                }

                function applyCabinetPayload(payload, config) {
                    isRootAdminUser = !!(payload && payload.is_root_admin);
                    applyRootAdminCabinetUi();
                    setReadyForIssueCount(
                        payload && payload.ready_for_issue_count != null
                            ? payload.ready_for_issue_count
                            : readyForIssueCount
                    );
                    updateAdminStatusBar();

                    var headerTitle = document.querySelector('.cabinet-header h1');
                    if (config.mode === 'folder') {
                        cabinetFolderId = payload.folder && payload.folder.id;
                        updateFolderNavButtons(payload, config);
                        if (payload.folder && headerTitle) {
                            headerTitle.textContent = payload.folder.name;
                        }
                        renderFolderSubfoldersBar(payload);
                    } else {
                        cabinetFolderId = null;
                        cabinetParentFolderId = null;
                        updateFolderNavButtons(payload, config);
                        if (headerTitle) {
                            headerTitle.textContent = CABINET_DEFAULT_TITLE;
                        }
                        hideFolderSubfoldersBar();
                    }

                    var cards = (payload && payload.cards) || [];
                    if (!cards.length) {
                        allCards = [];
                        if (IS_MATCH_ANALYSIS) {
                            if (config.mode === 'folder') {
                                gridEl.innerHTML =
                                    '<p class="empty">В этой папке пока нет матчей.</p>';
                            } else if (!isRootAdminUser) {
                                gridEl.innerHTML =
                                    '<p class="empty">Вам пока не выданы анализы матча</p>';
                            } else {
                                gridEl.innerHTML =
                                    '<p class="empty">Пока нет выданных вам анализов</p>';
                            }
                            updateSelectionUi();
                            return;
                        }
                        if (config.mode === 'folder') {
                            gridEl.innerHTML = '<p class="empty">В этой папке пока нет карточек.</p>';
                        } else if (!isRootAdminUser) {
                            gridEl.innerHTML =
                                '<p class="empty">У вас пока нет доступных карточек.</p>';
                        } else {
                            renderCards();
                        }
                        return;
                    }
                    allCards = cards;
                    if (quickSelectInput && String(quickSelectInput.value || '').trim()) {
                        applyQuickSelectionFromInput();
                    } else {
                        updateSelectionUi();
                    }
                    renderCards();
                    if (
                        IS_MATCH_ANALYSIS &&
                        isRootAdminUser &&
                        window.CardsCabinetMatchAudio &&
                        typeof window.CardsCabinetMatchAudio.ensureAllCardMinutes === 'function'
                    ) {
                        window.CardsCabinetMatchAudio.ensureAllCardMinutes(allCards);
                    }
                }

                function reloadCabinet() {
                    return fetchCabinetData(cabinetConfig).then(function (payload) {
                        applyCabinetPayload(payload, cabinetConfig);
                    });
                }

                function loadAllLabelsFilter() {
                    if (!isRootAdminUser || IS_MATCH_ANALYSIS || !FEATURES.enable_labels) {
                        return;
                    }
                    fetch('/api/content_cards/all_labels', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(authPayload()),
                    })
                        .then(function (r) {
                            if (!r.ok) {
                                throw new Error('Нет доступа к фильтру меток');
                            }
                            return r.json();
                        })
                        .then(function (data) {
                            var labels = (data && data.labels) || [];
                            cabinetAllLabels = labels.slice();
                            if (!labels.length || !labelFilter || !labelFilterWrap) {
                                return;
                            }
                            labels.forEach(function (label) {
                                var opt = document.createElement('option');
                                opt.value = label;
                                opt.textContent = label;
                                labelFilter.appendChild(opt);
                            });
                            applyPendingLabelFilterValue();
                            labelFilterWrap.classList.add('is-visible');
                            saveCabinetState();
                            renderCards();
                        })
                        .catch(function () {
                            // Для не-админов фильтр меток просто скрыт.
                        });
                }

                reloadCabinet()
                    .then(function () {
                        loadAllLabelsFilter();
                    })
                    .catch(function (e) {
                        showErr(e.message || String(e));
                    });

                if (matchRenameModalOverlay) {
                    matchRenameModalOverlay.addEventListener('click', closeMatchRenameModal);
                }
                if (matchRenameModalCancelBtn) {
                    matchRenameModalCancelBtn.addEventListener('click', closeMatchRenameModal);
                }
                if (matchRenameModalSubmitBtn) {
                    matchRenameModalSubmitBtn.addEventListener('click', saveMatchRename);
                }
                if (matchRenameModalInput) {
                    matchRenameModalInput.addEventListener('keydown', function (e) {
                        if (e.key === 'Enter') {
                            e.preventDefault();
                            saveMatchRename();
                        } else if (e.key === 'Escape') {
                            closeMatchRenameModal();
                        }
                    });
                }

                // ============================================================
                //  Папки
                // ============================================================
                var folderManageModal = document.getElementById('folderManageModal');
                var folderManageModalOverlay = document.getElementById('folderManageModalOverlay');
                var folderManageModalClose = document.getElementById('folderManageModalClose');
                var folderManageTree = document.getElementById('folderManageTree');
                var folderManageMsg = document.getElementById('folderManageMsg');

                var folderTreeData = [];
                var cabinetAllLabels = [];
                var expandedFolderIds = {};
                var expandedFolderPickIds = {};
                var expandedFolderCreateParentIds = {};
                var folderActionPendingCardIds = [];
                var folderPickPendingCardIds = [];
                var folderInsertPending = null;

                var folderActionModal = document.getElementById('folderActionModal');
                var folderActionModalOverlay = document.getElementById('folderActionModalOverlay');
                var folderActionModalSubtitle = document.getElementById('folderActionModalSubtitle');
                var folderActionModalCancelBtn = document.getElementById('folderActionModalCancelBtn');
                var folderActionCreateBtn = document.getElementById('folderActionCreateBtn');
                var folderActionInsertBtn = document.getElementById('folderActionInsertBtn');
                var folderPickModal = document.getElementById('folderPickModal');
                var folderPickModalOverlay = document.getElementById('folderPickModalOverlay');
                var folderPickModalClose = document.getElementById('folderPickModalClose');
                var folderPickModalSubtitle = document.getElementById('folderPickModalSubtitle');
                var folderPickTree = document.getElementById('folderPickTree');
                var folderPickMsg = document.getElementById('folderPickMsg');
                var folderInsertConfirmModal = document.getElementById('folderInsertConfirmModal');
                var folderInsertConfirmModalOverlay = document.getElementById('folderInsertConfirmModalOverlay');
                var folderInsertConfirmModalText = document.getElementById('folderInsertConfirmModalText');
                var folderInsertConfirmModalMsg = document.getElementById('folderInsertConfirmModalMsg');
                var folderInsertConfirmCancelBtn = document.getElementById('folderInsertConfirmCancelBtn');
                var folderInsertConfirmSubmitBtn = document.getElementById('folderInsertConfirmSubmitBtn');
                var folderManageCreateBtn = document.getElementById('folderManageCreateBtn');
                var folderCreateParentModal = document.getElementById('folderCreateParentModal');
                var folderCreateParentModalOverlay = document.getElementById('folderCreateParentModalOverlay');
                var folderCreateParentModalClose = document.getElementById('folderCreateParentModalClose');
                var folderCreateRootBtn = document.getElementById('folderCreateRootBtn');
                var folderCreateParentTree = document.getElementById('folderCreateParentTree');
                var folderCreateParentMsg = document.getElementById('folderCreateParentMsg');

                var folderScheduleModal = document.getElementById('folderScheduleModal');
                var folderScheduleModalOverlay = document.getElementById('folderScheduleModalOverlay');
                var folderScheduleModalTitle = document.getElementById('folderScheduleModalTitle');
                var folderScheduleModalSubtitle = document.getElementById('folderScheduleModalSubtitle');
                var folderScheduleModalMeta = document.getElementById('folderScheduleModalMeta');
                var folderScheduleWeekdayToolbar = document.getElementById('folderScheduleWeekdayToolbar');
                var folderScheduleWeekdays = document.getElementById('folderScheduleWeekdays');
                var folderScheduleTimeInput = document.getElementById('folderScheduleTimeInput');
                var folderScheduleCountInput = document.getElementById('folderScheduleCountInput');
                var folderScheduleLabels = document.getElementById('folderScheduleLabels');
                var folderScheduleActiveInput = document.getElementById('folderScheduleActiveInput');
                var folderScheduleModalMsg = document.getElementById('folderScheduleModalMsg');
                var folderScheduleDeleteBtn = document.getElementById('folderScheduleDeleteBtn');
                var folderScheduleCancelBtn = document.getElementById('folderScheduleCancelBtn');
                var folderScheduleSaveBtn = document.getElementById('folderScheduleSaveBtn');

                var FOLDER_SCHEDULE_DAYS = [
                    { value: 'mon', short: 'Пн', full: 'Понедельник' },
                    { value: 'tue', short: 'Вт', full: 'Вторник' },
                    { value: 'wed', short: 'Ср', full: 'Среда' },
                    { value: 'thu', short: 'Чт', full: 'Четверг' },
                    { value: 'fri', short: 'Пт', full: 'Пятница' },
                    { value: 'sat', short: 'Сб', full: 'Суббота' },
                    { value: 'sun', short: 'Вс', full: 'Воскресенье' }
                ];
                var folderSchedulePending = null;
                var folderScheduleSelectedWeekdays = {};
                var folderScheduleSelectedLabels = {};

                function setFolderScheduleModalMsg(msg) {
                    if (folderScheduleModalMsg) folderScheduleModalMsg.textContent = msg || '';
                }

                function renderFolderScheduleWeekdays() {
                    if (!folderScheduleWeekdays) return;
                    folderScheduleWeekdays.innerHTML = '';
                    FOLDER_SCHEDULE_DAYS.forEach(function (day) {
                        var btn = document.createElement('button');
                        btn.type = 'button';
                        btn.className = 'folder-schedule-modal__weekday-btn' +
                            (folderScheduleSelectedWeekdays[day.value] ? ' is-active' : '');
                        btn.textContent = day.short;
                        btn.title = day.full;
                        btn.addEventListener('click', function () {
                            folderScheduleSelectedWeekdays[day.value] = !folderScheduleSelectedWeekdays[day.value];
                            renderFolderScheduleWeekdays();
                        });
                        folderScheduleWeekdays.appendChild(btn);
                    });
                }

                function setFolderScheduleWeekdays(values) {
                    folderScheduleSelectedWeekdays = {};
                    (values || []).forEach(function (value) {
                        var key = String(value || '').trim().toLowerCase();
                        if (key) folderScheduleSelectedWeekdays[key] = true;
                    });
                    renderFolderScheduleWeekdays();
                }

                function getFolderScheduleWeekdays() {
                    return FOLDER_SCHEDULE_DAYS
                        .map(function (day) { return day.value; })
                        .filter(function (value) { return !!folderScheduleSelectedWeekdays[value]; });
                }

                function renderFolderScheduleWeekdayToolbar() {
                    if (!folderScheduleWeekdayToolbar || folderScheduleWeekdayToolbar.dataset.ready === '1') return;
                    folderScheduleWeekdayToolbar.dataset.ready = '1';
                    [
                        { label: 'Будни', values: ['mon', 'tue', 'wed', 'thu', 'fri'] },
                        { label: 'Выходные', values: ['sat', 'sun'] },
                        { label: 'Все дни', values: ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] },
                        { label: 'Очистить', values: [] }
                    ].forEach(function (item) {
                        var btn = document.createElement('button');
                        btn.type = 'button';
                        btn.className = 'folder-schedule-modal__toolbar-btn';
                        btn.textContent = item.label;
                        btn.addEventListener('click', function () {
                            setFolderScheduleWeekdays(item.values);
                        });
                        folderScheduleWeekdayToolbar.appendChild(btn);
                    });
                }

                function renderFolderScheduleLabels(selectedLabels) {
                    if (!folderScheduleLabels) return;
                    folderScheduleLabels.innerHTML = '';
                    folderScheduleSelectedLabels = {};
                    (selectedLabels || []).forEach(function (label) {
                        var text = String(label || '').trim();
                        if (text) folderScheduleSelectedLabels[text] = true;
                    });
                    if (!cabinetAllLabels.length) {
                        folderScheduleLabels.innerHTML =
                            '<p style="margin:0;color:#9aa3b2;font-size:12px;">Метки не найдены.</p>';
                        return;
                    }
                    cabinetAllLabels.forEach(function (label) {
                        var row = document.createElement('label');
                        row.className = 'folder-schedule-modal__label-row';
                        var input = document.createElement('input');
                        input.type = 'checkbox';
                        input.value = label;
                        input.checked = !!folderScheduleSelectedLabels[label];
                        input.addEventListener('change', function () {
                            if (input.checked) folderScheduleSelectedLabels[label] = true;
                            else delete folderScheduleSelectedLabels[label];
                        });
                        var text = document.createElement('span');
                        text.textContent = label;
                        row.appendChild(input);
                        row.appendChild(text);
                        folderScheduleLabels.appendChild(row);
                    });
                }

                function getFolderScheduleSelectedLabels() {
                    return Object.keys(folderScheduleSelectedLabels).filter(function (label) {
                        return !!folderScheduleSelectedLabels[label];
                    });
                }

                function formatFolderScheduleMeta(schedule) {
                    if (!schedule || !schedule.last_run_at) return '';
                    try {
                        var dt = new Date(schedule.last_run_at);
                        if (isNaN(dt.getTime())) return '';
                        return 'Последний запуск: ' + dt.toLocaleString('ru-RU');
                    } catch (e) {
                        return '';
                    }
                }

                function closeFolderScheduleModal() {
                    if (!folderScheduleModal) return;
                    folderScheduleModal.classList.remove('is-open');
                    folderScheduleModal.setAttribute('aria-hidden', 'true');
                    folderSchedulePending = null;
                    setFolderScheduleModalMsg('');
                    if (folderScheduleSaveBtn) folderScheduleSaveBtn.disabled = false;
                    if (folderScheduleDeleteBtn) folderScheduleDeleteBtn.disabled = false;
                }

                function openFolderScheduleModal(folderId, folderName, existingSchedule) {
                    if (!folderScheduleModal) return;
                    folderSchedulePending = {
                        folderId: folderId,
                        folderName: folderName,
                        hasSchedule: !!existingSchedule
                    };
                    renderFolderScheduleWeekdayToolbar();
                    if (folderScheduleModalTitle) {
                        folderScheduleModalTitle.textContent = 'Расписание папки';
                    }
                    if (folderScheduleModalSubtitle) {
                        folderScheduleModalSubtitle.textContent = '«' + folderName + '»';
                    }
                    if (folderScheduleModalMeta) {
                        folderScheduleModalMeta.textContent = formatFolderScheduleMeta(existingSchedule);
                    }
                    var schedule = existingSchedule || {};
                    setFolderScheduleWeekdays(schedule.weekdays || ['mon', 'tue', 'wed', 'thu', 'fri']);
                    if (folderScheduleTimeInput) {
                        folderScheduleTimeInput.value = schedule.issue_time_msk || '09:00';
                    }
                    if (folderScheduleCountInput) {
                        folderScheduleCountInput.value = String(schedule.cards_per_run || 1);
                    }
                    renderFolderScheduleLabels(schedule.labels || []);
                    if (folderScheduleActiveInput) {
                        folderScheduleActiveInput.checked = existingSchedule ? !!schedule.is_active : true;
                    }
                    if (folderScheduleDeleteBtn) {
                        folderScheduleDeleteBtn.style.display = existingSchedule ? '' : 'none';
                    }
                    setFolderScheduleModalMsg('');
                    folderScheduleModal.classList.add('is-open');
                    folderScheduleModal.setAttribute('aria-hidden', 'false');
                }

                function ensureCabinetAllLabelsLoaded() {
                    if (IS_MATCH_ANALYSIS || !isRootAdminUser) {
                        cabinetAllLabels = [];
                        return Promise.resolve(cabinetAllLabels);
                    }
                    if (cabinetAllLabels.length) {
                        return Promise.resolve(cabinetAllLabels);
                    }
                    return fetch('/api/content_cards/all_labels', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(authPayload()),
                    }).then(function (r) {
                        if (!r.ok) {
                            throw new Error('Не удалось загрузить метки');
                        }
                        return r.json();
                    }).then(function (data) {
                        cabinetAllLabels = ((data && data.labels) || []).slice();
                        return cabinetAllLabels;
                    });
                }

                function loadFolderScheduleAndOpen(folderId, folderName, existingSchedule) {
                    ensureCabinetAllLabelsLoaded().then(function () {
                        if (existingSchedule) {
                            openFolderScheduleModal(folderId, folderName, existingSchedule);
                            return;
                        }
                        return folderApiPost('schedule_get', { folder_id: folderId })
                            .then(function (data) {
                                openFolderScheduleModal(folderId, folderName, data && data.schedule);
                            });
                    }).catch(function (e) {
                        if (folderManageMsg) {
                            folderManageMsg.textContent = 'Ошибка: ' + (e.message || e);
                        }
                    });
                }

                function submitFolderScheduleSave() {
                    if (!folderSchedulePending) return;
                    var weekdays = getFolderScheduleWeekdays();
                    if (!weekdays.length) {
                        setFolderScheduleModalMsg('Выберите хотя бы один день недели.');
                        return;
                    }
                    var labels = getFolderScheduleSelectedLabels();
                    var timeValue = folderScheduleTimeInput ? String(folderScheduleTimeInput.value || '').trim() : '';
                    if (!/^\d{2}:\d{2}$/.test(timeValue)) {
                        setFolderScheduleModalMsg('Укажите время в формате ЧЧ:ММ.');
                        return;
                    }
                    var cardsPerRun = folderScheduleCountInput ? parseInt(folderScheduleCountInput.value, 10) : 1;
                    if (!cardsPerRun || cardsPerRun < 1) {
                        setFolderScheduleModalMsg(
                            IS_MATCH_ANALYSIS
                                ? 'Количество матчей должно быть не меньше 1.'
                                : 'Количество карточек должно быть не меньше 1.'
                        );
                        return;
                    }
                    if (folderScheduleSaveBtn) folderScheduleSaveBtn.disabled = true;
                    setFolderScheduleModalMsg('Сохранение...');
                    folderApiPost('schedule_save', {
                        folder_id: folderSchedulePending.folderId,
                        weekdays: weekdays,
                        issue_time_msk: timeValue,
                        cards_per_run: cardsPerRun,
                        labels: IS_MATCH_ANALYSIS ? [] : labels,
                        is_active: !!(folderScheduleActiveInput && folderScheduleActiveInput.checked),
                    }).then(function () {
                        closeFolderScheduleModal();
                        return loadFolderTreeData().then(function () {
                            refreshFolderManageList();
                            if (folderManageMsg) {
                                folderManageMsg.textContent = 'Расписание сохранено.';
                            }
                        });
                    }).catch(function (e) {
                        setFolderScheduleModalMsg(e.message || String(e));
                        if (folderScheduleSaveBtn) folderScheduleSaveBtn.disabled = false;
                    });
                }

                function submitFolderScheduleDelete() {
                    if (!folderSchedulePending || !folderSchedulePending.hasSchedule) return;
                    showCabinetConfirm(
                        'Удалить расписание для «' + folderSchedulePending.folderName + '»?',
                        'Удаление расписания',
                        { danger: true, confirmLabel: 'Удалить' }
                    ).then(function (ok) {
                        if (!ok) return;
                        if (folderScheduleDeleteBtn) folderScheduleDeleteBtn.disabled = true;
                        setFolderScheduleModalMsg('Удаление...');
                        folderApiPost('schedule_delete', {
                            folder_id: folderSchedulePending.folderId,
                        }).then(function () {
                            closeFolderScheduleModal();
                            return loadFolderTreeData().then(function () {
                                refreshFolderManageList();
                                if (folderManageMsg) {
                                    folderManageMsg.textContent = 'Расписание удалено.';
                                }
                            });
                        }).catch(function (e) {
                            setFolderScheduleModalMsg(e.message || String(e));
                            if (folderScheduleDeleteBtn) folderScheduleDeleteBtn.disabled = false;
                        });
                    });
                }

                function folderApiPost(endpoint, extraBody) {
                    var basePath = IS_MATCH_ANALYSIS
                        ? '/api/match_analysis/folders/'
                        : '/api/content_cards/folders/';
                    var url = endpoint.startsWith('/') ? endpoint : basePath + endpoint;
                    return fetch(url, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(authPayload(extraBody || {})),
                    }).then(function (r) {
                        if (!r.ok) {
                            return r.json().then(function (d) {
                                throw new Error((d && d.detail) || r.statusText);
                            });
                        }
                        return r.json();
                    });
                }

                function defaultNewFolderName(prefix) {
                    var d = new Date();
                    var pad = function (n) { return n < 10 ? '0' + n : String(n); };
                    var base = pad(d.getDate()) + '.' + pad(d.getMonth() + 1) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
                    return (prefix || 'Папка') + ' ' + base;
                }

                function buildFolderShareUrl(linkToken) {
                    var params = new URLSearchParams();
                    params.set('folder_token', linkToken);
                    if (fabToken) {
                        params.set('fab_token', fabToken);
                    }
                    return CABINET_BASE_PATH + '?' + params.toString();
                }

                function openFolderShareLinkModal(folderId) {
                    if (!generateLinkModal || !generateLinkModalInput) return;
                    folderApiPost('generate_link', { folder_id: folderId }).then(function (data) {
                        var startLink = data && data.start_link;
                        if (!startLink) throw new Error('Не удалось получить ссылку');
                        generatedActivationLink = startLink;
                        if (generateLinkModalTitle) {
                            generateLinkModalTitle.textContent = 'Ссылка на папку';
                        }
                        generateLinkModalInput.value = generatedActivationLink;
                        setGenerateLinkModalMsg('');
                        generateLinkModal.classList.add('is-open');
                        generateLinkModal.setAttribute('aria-hidden', 'false');
                        generateLinkModalInput.focus();
                        generateLinkModalInput.select();
                    }).catch(function (e) {
                        if (folderManageMsg) folderManageMsg.textContent = 'Ошибка: ' + (e.message || e);
                    });
                }

                function navigateToFolder(folderId, childLinkToken) {
                    if (childLinkToken) {
                        window.location.assign(buildFolderShareUrl(childLinkToken));
                        return;
                    }
                    if (cabinetConfig.mode === 'folder' && cabinetConfig.folderToken) {
                        folderApiPost('navigate_link', {
                            folder_token: cabinetConfig.folderToken,
                            target_folder_id: folderId,
                        }).then(function (data) {
                            var token = data && data.link_token;
                            if (!token) throw new Error('Не удалось открыть папку');
                            window.location.assign(buildFolderShareUrl(token));
                        }).catch(function (e) {
                            showErr(e.message || String(e));
                        });
                        return;
                    }
                    folderApiPost('generate_link', { folder_id: folderId }).then(function (data) {
                        var token = data && data.link_token;
                        if (!token) throw new Error('Не удалось открыть папку');
                        window.location.assign(buildFolderShareUrl(token));
                    }).catch(function (e) {
                        showErr(e.message || String(e));
                    });
                }

                if (cabinetBackToParentBtn) {
                    cabinetBackToParentBtn.addEventListener('click', function () {
                        if (cabinetParentFolderId == null) return;
                        navigateToFolder(cabinetParentFolderId);
                    });
                }

                var folderTreeLoadSeq = 0;

                function folderExistsInTree(nodes, folderId) {
                    if (!Array.isArray(nodes) || folderId == null) return false;
                    for (var i = 0; i < nodes.length; i++) {
                        var node = nodes[i];
                        if (!node) continue;
                        if (Number(node.id) === Number(folderId)) return true;
                        if (folderExistsInTree(node.children, folderId)) return true;
                    }
                    return false;
                }

                function loadFolderTreeData() {
                    var seq = ++folderTreeLoadSeq;
                    return folderApiPost('tree').then(function (data) {
                        if (seq !== folderTreeLoadSeq) {
                            return folderTreeData;
                        }
                        folderTreeData = (data && data.folders) || [];
                        return folderTreeData;
                    });
                }

                function afterFolderStructureChanged(deletedFolderId) {
                    if (deletedFolderId != null) {
                        delete expandedFolderIds[deletedFolderId];
                        delete expandedFolderPickIds[deletedFolderId];
                        delete expandedFolderCreateParentIds[deletedFolderId];
                    }
                    if (folderManageMsg) folderManageMsg.textContent = '';
                    return loadFolderTreeData().then(function () {
                        if (folderManageModal && folderManageModal.classList.contains('is-open')) {
                            refreshFolderManageList();
                        }
                        if (folderPickModal && folderPickModal.classList.contains('is-open')) {
                            refreshFolderPickList();
                        }
                        if (folderCreateParentModal && folderCreateParentModal.classList.contains('is-open')) {
                            refreshFolderCreateParentList();
                        }
                        if (cabinetConfig.mode === 'folder' && cabinetFolderId) {
                            if (!folderExistsInTree(folderTreeData, cabinetFolderId)) {
                                goToMainCabinet();
                                return;
                            }
                            return reloadCabinet().catch(function () {
                                goToMainCabinet();
                            });
                        }
                    });
                }

                function refreshFolderManageList() {
                    if (!folderManageTree) return;
                    folderManageTree.innerHTML = '';
                    if (!folderTreeData.length) {
                        folderManageTree.innerHTML = '<p style="color:#aaa;font-size:13px;text-align:center;padding:16px 0;">Папок пока нет.</p>';
                        return;
                    }
                    folderTreeData.forEach(function (node) {
                        folderManageTree.appendChild(buildFolderManageNodeEl(node));
                    });
                }

                function refreshFolderPickList() {
                    if (!folderPickTree) return;
                    folderPickTree.innerHTML = '';
                    if (!folderTreeData.length) {
                        folderPickTree.innerHTML =
                            '<p style="color:#aaa;font-size:13px;text-align:center;padding:16px 0;">Папок пока нет. Сначала создайте папку.</p>';
                        return;
                    }
                    folderTreeData.forEach(function (node) {
                        folderPickTree.appendChild(buildFolderPickNodeEl(node));
                    });
                }

                function refreshFolderCreateParentList() {
                    if (!folderCreateParentTree) return;
                    folderCreateParentTree.innerHTML = '';
                    if (!folderTreeData.length) {
                        return;
                    }
                    folderTreeData.forEach(function (node) {
                        folderCreateParentTree.appendChild(buildFolderCreateParentNodeEl(node));
                    });
                }

                function openEmptyFolderNameModal(parentId, parentName) {
                    var isSubfolder = parentId != null;
                    openFolderNameModal({
                        mode: 'empty',
                        parentId: parentId,
                        cardIds: [],
                        title: isSubfolder ? 'Новая подпапка' : 'Новая папка',
                        subtitle: isSubfolder
                            ? 'Внутри «' + parentName + '»'
                            : 'Корневая папка',
                        defaultName: defaultNewFolderName(isSubfolder ? 'Подпапка' : 'Папка'),
                    });
                }

                function buildFolderCreateParentNodeEl(node) {
                    var wrap = document.createElement('div');
                    var hasChildren = node.children && node.children.length;
                    wrap.className =
                        'folder-node folder-node--pick' +
                        (expandedFolderCreateParentIds[node.id] ? ' is-expanded' : '');

                    var row = document.createElement('div');
                    row.className = 'folder-node__row';

                    var toggle = document.createElement('span');
                    toggle.className = 'folder-node__toggle';
                    toggle.textContent = hasChildren ? (expandedFolderCreateParentIds[node.id] ? '▾' : '▸') : '';
                    row.appendChild(toggle);

                    var name = document.createElement('span');
                    name.className = 'folder-node__name';
                    name.textContent = node.name;
                    row.appendChild(name);

                    var count = document.createElement('span');
                    count.className = 'folder-node__count';
                    var cnt = node.direct_cards_count || 0;
                    count.textContent = cnt ? String(cnt) : '';
                    row.appendChild(count);

                    var pickLabel = document.createElement('span');
                    pickLabel.className = 'folder-node__pick-label';
                    pickLabel.textContent = 'Подпапка';
                    row.appendChild(pickLabel);

                    row.addEventListener('click', function (ev) {
                        if (ev.target === toggle) return;
                        openEmptyFolderNameModal(node.id, node.name);
                    });
                    toggle.addEventListener('click', function (ev) {
                        ev.stopPropagation();
                        if (!hasChildren) return;
                        expandedFolderCreateParentIds[node.id] = !expandedFolderCreateParentIds[node.id];
                        refreshFolderCreateParentList();
                    });

                    wrap.appendChild(row);
                    if (hasChildren) {
                        var childrenWrap = document.createElement('div');
                        childrenWrap.className = 'folder-node__children';
                        node.children.forEach(function (child) {
                            childrenWrap.appendChild(buildFolderCreateParentNodeEl(child));
                        });
                        wrap.appendChild(childrenWrap);
                    }
                    return wrap;
                }

                function closeFolderCreateParentModal() {
                    if (!folderCreateParentModal) return;
                    folderCreateParentModal.classList.remove('is-open');
                    folderCreateParentModal.setAttribute('aria-hidden', 'true');
                    if (folderCreateParentMsg) folderCreateParentMsg.textContent = '';
                }

                function openFolderCreateParentModal() {
                    if (!isRootAdminUser || !folderCreateParentModal) return;
                    if (folderCreateParentMsg) folderCreateParentMsg.textContent = '';
                    folderCreateParentModal.classList.add('is-open');
                    folderCreateParentModal.setAttribute('aria-hidden', 'false');
                    loadFolderTreeData()
                        .then(function () {
                            refreshFolderCreateParentList();
                        })
                        .catch(function (e) {
                            if (folderCreateParentMsg) {
                                folderCreateParentMsg.textContent = e.message || String(e);
                            }
                        });
                }

                function buildFolderPickNodeEl(node) {
                    var wrap = document.createElement('div');
                    var hasChildren = node.children && node.children.length;
                    wrap.className =
                        'folder-node folder-node--pick' +
                        (expandedFolderPickIds[node.id] ? ' is-expanded' : '');

                    var row = document.createElement('div');
                    row.className = 'folder-node__row';

                    var toggle = document.createElement('span');
                    toggle.className = 'folder-node__toggle';
                    toggle.textContent = hasChildren ? (expandedFolderPickIds[node.id] ? '▾' : '▸') : '';
                    row.appendChild(toggle);

                    var name = document.createElement('span');
                    name.className = 'folder-node__name';
                    name.textContent = node.name;
                    row.appendChild(name);

                    var count = document.createElement('span');
                    count.className = 'folder-node__count';
                    var cnt = node.direct_cards_count || 0;
                    count.textContent = cnt ? String(cnt) : '';
                    row.appendChild(count);

                    var pickLabel = document.createElement('span');
                    pickLabel.className = 'folder-node__pick-label';
                    pickLabel.textContent = 'Выбрать';
                    row.appendChild(pickLabel);

                    function onPickFolder() {
                        openFolderInsertConfirmModal(node.id, node.name, folderPickPendingCardIds);
                    }

                    row.addEventListener('click', function (ev) {
                        if (ev.target === toggle) return;
                        onPickFolder();
                    });
                    toggle.addEventListener('click', function (ev) {
                        ev.stopPropagation();
                        if (!hasChildren) return;
                        expandedFolderPickIds[node.id] = !expandedFolderPickIds[node.id];
                        refreshFolderPickList();
                    });

                    wrap.appendChild(row);
                    if (hasChildren) {
                        var childrenWrap = document.createElement('div');
                        childrenWrap.className = 'folder-node__children';
                        node.children.forEach(function (child) {
                            childrenWrap.appendChild(buildFolderPickNodeEl(child));
                        });
                        wrap.appendChild(childrenWrap);
                    }
                    return wrap;
                }

                function buildFolderManageNodeEl(node) {
                    var wrap = document.createElement('div');
                    var hasChildren = node.children && node.children.length;
                    wrap.className = 'folder-node' + (expandedFolderIds[node.id] ? ' is-expanded' : '');

                    var row = document.createElement('div');
                    row.className = 'folder-node__row';

                    var toggle = document.createElement('span');
                    toggle.className = 'folder-node__toggle';
                    toggle.textContent = hasChildren ? (expandedFolderIds[node.id] ? '▾' : '▸') : '';
                    row.appendChild(toggle);

                    var nameWrap = document.createElement('span');
                    nameWrap.className = 'folder-node__name-wrap';

                    var name = document.createElement('span');
                    name.className = 'folder-node__name';
                    name.textContent = node.name;
                    nameWrap.appendChild(name);

                    var renameBtn = document.createElement('button');
                    renameBtn.type = 'button';
                    renameBtn.className = 'folder-node__rename';
                    renameBtn.title = 'Переименовать папку';
                    renameBtn.setAttribute('aria-label', 'Переименовать папку «' + node.name + '»');
                    renameBtn.innerHTML =
                        '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
                        '<path d="M4 20h4l10.5-10.5a1.4 1.4 0 0 0 0-2L14.5 3.5a1.4 1.4 0 0 0-2 0L3 13v4Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>' +
                        '<path d="M13.5 5.5l5 5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>' +
                        '</svg>';
                    renameBtn.addEventListener('click', function (ev) {
                        ev.stopPropagation();
                        openRenameFolderModal(node.id, node.name);
                    });
                    nameWrap.appendChild(renameBtn);
                    row.appendChild(nameWrap);

                    var rightCluster = document.createElement('span');
                    rightCluster.className = 'folder-node__right';

                    var count = document.createElement('span');
                    count.className = 'folder-node__count';
                    var cnt = node.direct_cards_count || 0;
                    count.textContent = cnt ? String(cnt) : '';
                    rightCluster.appendChild(count);

                    var actions = document.createElement('span');
                    actions.className = 'folder-node__actions';

                    var linkBtn = document.createElement('button');
                    linkBtn.type = 'button';
                    linkBtn.className = 'folder-node__action';
                    linkBtn.innerHTML = '<i class="fa fa-link" aria-hidden="true"></i>';
                    linkBtn.title = 'Получить ссылку';
                    linkBtn.setAttribute('aria-label', 'Получить ссылку на папку «' + node.name + '»');
                    linkBtn.addEventListener('click', function (ev) {
                        ev.stopPropagation();
                        openFolderShareLinkModal(node.id);
                    });
                    actions.appendChild(linkBtn);

                    var scheduleBtn = document.createElement('button');
                    scheduleBtn.type = 'button';
                    scheduleBtn.className = 'folder-node__action';
                    if (node.schedule && node.schedule.is_active) {
                        scheduleBtn.className += ' folder-node__action--schedule-active';
                    }
                    scheduleBtn.innerHTML = '<i class="fa fa-calendar" aria-hidden="true"></i>';
                    scheduleBtn.title = node.schedule && node.schedule.is_active
                        ? 'Расписание активно'
                        : 'Настроить расписание';
                    scheduleBtn.setAttribute(
                        'aria-label',
                        (node.schedule && node.schedule.is_active
                            ? 'Расписание активно: '
                            : 'Настроить расписание: ') + node.name
                    );
                    scheduleBtn.addEventListener('click', function (ev) {
                        ev.stopPropagation();
                        loadFolderScheduleAndOpen(node.id, node.name, node.schedule || null);
                    });
                    actions.appendChild(scheduleBtn);

                    var goBtn = document.createElement('button');
                    goBtn.type = 'button';
                    goBtn.className = 'folder-node__action';
                    goBtn.innerHTML = '<i class="fa fa-arrow-right" aria-hidden="true"></i>';
                    goBtn.title = 'Открыть папку';
                    goBtn.setAttribute('aria-label', 'Открыть папку «' + node.name + '»');
                    goBtn.addEventListener('click', function (ev) {
                        ev.stopPropagation();
                        navigateToFolder(node.id);
                    });
                    actions.appendChild(goBtn);

                    var delBtn = document.createElement('button');
                    delBtn.type = 'button';
                    delBtn.className = 'folder-node__action folder-node__action--danger';
                    delBtn.innerHTML = '<i class="fa fa-times" aria-hidden="true"></i>';
                    delBtn.title = 'Удалить папку';
                    delBtn.setAttribute('aria-label', 'Удалить папку «' + node.name + '»');
                    delBtn.addEventListener('click', function (ev) {
                        ev.stopPropagation();
                        showCabinetConfirm(
                            'Удалить «' + node.name + '»?',
                            'Удаление папки',
                            { danger: true, confirmLabel: 'Удалить' }
                        ).then(function (ok) {
                            if (!ok) return;
                            var deletedFolderId = node.id;
                            folderApiPost('delete', { folder_id: deletedFolderId })
                                .then(function () {
                                    return afterFolderStructureChanged(deletedFolderId);
                                })
                                .catch(function (e) {
                                    if (folderManageMsg) {
                                        folderManageMsg.textContent = 'Ошибка: ' + (e.message || e);
                                    }
                                });
                        });
                    });
                    actions.appendChild(delBtn);

                    rightCluster.appendChild(actions);
                    row.appendChild(rightCluster);

                    toggle.addEventListener('click', function (ev) {
                        ev.stopPropagation();
                        if (!hasChildren) return;
                        expandedFolderIds[node.id] = !expandedFolderIds[node.id];
                        refreshFolderManageList();
                    });

                    row.addEventListener('click', function (ev) {
                        if (ev.target.closest('.folder-node__toggle, .folder-node__rename, .folder-node__actions')) {
                            return;
                        }
                        navigateToFolder(node.id);
                    });

                    wrap.appendChild(row);
                    if (hasChildren) {
                        var childrenWrap = document.createElement('div');
                        childrenWrap.className = 'folder-node__children';
                        node.children.forEach(function (child) {
                            childrenWrap.appendChild(buildFolderManageNodeEl(child));
                        });
                        wrap.appendChild(childrenWrap);
                    }
                    return wrap;
                }

                function closeFolderManageModal() {
                    if (!folderManageModal) return;
                    folderManageModal.classList.remove('is-open');
                    folderManageModal.setAttribute('aria-hidden', 'true');
                    if (folderManageMsg) folderManageMsg.textContent = '';
                }

                function openFolderManageModal() {
                    if (!isRootAdminUser || !folderManageModal) return;
                    if (folderManageMsg) folderManageMsg.textContent = '';
                    folderManageModal.classList.add('is-open');
                    folderManageModal.setAttribute('aria-hidden', 'false');
                    loadFolderTreeData().then(function () {
                        refreshFolderManageList();
                    }).catch(function (e) {
                        if (folderManageMsg) folderManageMsg.textContent = 'Ошибка: ' + (e.message || e);
                    });
                }

                var cardNotesModal = document.getElementById('cardNotesModal');
                var cardNotesModalOverlay = document.getElementById('cardNotesModalOverlay');
                var cardNotesModalInput = document.getElementById('cardNotesModalInput');
                var cardNotesModalTitle = document.getElementById('cardNotesModalTitle');
                var cardNotesModalSubtitle = document.getElementById('cardNotesModalSubtitle');
                var cardNotesModalMsg = document.getElementById('cardNotesModalMsg');
                var cardNotesModalCancelBtn = document.getElementById('cardNotesModalCancelBtn');
                var cardNotesModalSubmitBtn = document.getElementById('cardNotesModalSubmitBtn');
                var cardNotesModalPendingId = null;

                function setCardNotesModalMsg(msg) {
                    if (cardNotesModalMsg) cardNotesModalMsg.textContent = msg || '';
                }

                function closeCardNotesModal() {
                    if (!cardNotesModal) return;
                    cardNotesModal.classList.remove('is-open');
                    cardNotesModal.setAttribute('aria-hidden', 'true');
                    cardNotesModalPendingId = null;
                    setCardNotesModalMsg('');
                    if (cardNotesModalSubmitBtn) cardNotesModalSubmitBtn.disabled = false;
                }

                function openCardNotesModal(cardIdNum, currentNotes) {
                    if (!isRootAdminUser || !cardNotesModal || !cardNotesModalInput) return;
                    cardNotesModalPendingId = cardIdNum;
                    if (cardNotesModalTitle) {
                        cardNotesModalTitle.textContent = 'Описание карточки #' + cardIdNum;
                    }
                    if (cardNotesModalSubtitle) {
                        cardNotesModalSubtitle.textContent = '';
                        cardNotesModalSubtitle.style.display = 'none';
                    }
                    cardNotesModalInput.value = String(currentNotes || '');
                    setCardNotesModalMsg('');
                    cardNotesModal.classList.add('is-open');
                    cardNotesModal.setAttribute('aria-hidden', 'false');
                    cardNotesModalInput.focus();
                }

                function submitCardNotesModal() {
                    if (!cardNotesModalPendingId || !cardNotesModalInput) return;
                    var notes = String(cardNotesModalInput.value || '').trim();
                    if (cardNotesModalSubmitBtn) cardNotesModalSubmitBtn.disabled = true;
                    setCardNotesModalMsg('Сохранение…');
                    var cardIdNum = cardNotesModalPendingId;
                    fetch('/api/content_cards/update_meta', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(
                            authPayload({
                                content_card_id: cardIdNum,
                                notes: notes,
                            })
                        ),
                    })
                        .then(function (r) {
                            if (!r.ok) {
                                return r.json().then(function (j) {
                                    throw new Error((j && j.detail) || r.statusText);
                                });
                            }
                            return r.json();
                        })
                        .then(function () {
                            updateCardNotesInLists(cardIdNum, notes);
                            closeCardNotesModal();
                            renderCards();
                        })
                        .catch(function (e) {
                            setCardNotesModalMsg(e.message || String(e));
                            if (cardNotesModalSubmitBtn) cardNotesModalSubmitBtn.disabled = false;
                        });
                }

                if (cardNotesModalCancelBtn) {
                    cardNotesModalCancelBtn.addEventListener('click', closeCardNotesModal);
                }
                if (cardNotesModalOverlay) {
                    cardNotesModalOverlay.addEventListener('click', closeCardNotesModal);
                }
                if (cardNotesModalSubmitBtn) {
                    cardNotesModalSubmitBtn.addEventListener('click', submitCardNotesModal);
                }
                if (cardNotesModalInput) {
                    cardNotesModalInput.addEventListener('keydown', function (ev) {
                        if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) {
                            ev.preventDefault();
                            submitCardNotesModal();
                        }
                    });
                }

                var folderNameModal = document.getElementById('folderNameModal');
                var folderNameModalOverlay = document.getElementById('folderNameModalOverlay');
                var folderNameModalInput = document.getElementById('folderNameModalInput');
                var folderNameModalSubtitle = document.getElementById('folderNameModalSubtitle');
                var folderNameModalMsg = document.getElementById('folderNameModalMsg');
                var folderNameModalCancelBtn = document.getElementById('folderNameModalCancelBtn');
                var folderNameModalSubmitBtn = document.getElementById('folderNameModalSubmitBtn');
                var folderNameModalTitle = document.getElementById('folderNameModalTitle');
                var folderNameModalPending = null;

                function setFolderNameModalMsg(msg) {
                    if (folderNameModalMsg) folderNameModalMsg.textContent = msg || '';
                }

                function closeFolderNameModal() {
                    if (!folderNameModal) return;
                    folderNameModal.classList.remove('is-open');
                    folderNameModal.setAttribute('aria-hidden', 'true');
                    folderNameModalPending = null;
                    setFolderNameModalMsg('');
                    if (folderNameModalSubmitBtn) {
                        folderNameModalSubmitBtn.disabled = false;
                        folderNameModalSubmitBtn.textContent = 'Создать';
                    }
                }

                function openFolderNameModal(options) {
                    if (!folderNameModal || !folderNameModalInput) return;
                    var opts = options || {};
                    var mode = opts.mode || 'with_cards';
                    var parentId;
                    if (Object.prototype.hasOwnProperty.call(opts, 'parentId')) {
                        parentId = opts.parentId;
                    } else if (mode === 'with_cards') {
                        parentId = getNewFolderParentId();
                    } else {
                        parentId = null;
                    }
                    folderNameModalPending = {
                        mode: mode,
                        parentId: parentId,
                        cardIds: opts.cardIds || [],
                        folderId: opts.folderId != null ? opts.folderId : null,
                    };
                    if (folderNameModalTitle) {
                        folderNameModalTitle.textContent = opts.title || 'Новая папка';
                    }
                    if (folderNameModalSubtitle) {
                        folderNameModalSubtitle.textContent = opts.subtitle || '';
                        folderNameModalSubtitle.style.display = opts.subtitle ? '' : 'none';
                    }
                    if (folderNameModalSubmitBtn) {
                        folderNameModalSubmitBtn.textContent =
                            opts.submitLabel || (mode === 'rename' ? 'Сохранить' : 'Создать');
                    }
                    folderNameModalInput.value = String(
                        opts.defaultName != null
                            ? opts.defaultName
                            : (mode === 'rename' ? '' : defaultNewFolderName('Папка'))
                    );
                    setFolderNameModalMsg('');
                    folderNameModal.classList.add('is-open');
                    folderNameModal.setAttribute('aria-hidden', 'false');
                    folderNameModalInput.focus();
                    folderNameModalInput.select();
                }

                function openRenameFolderModal(folderId, currentName) {
                    openFolderNameModal({
                        mode: 'rename',
                        folderId: folderId,
                        title: 'Переименовать папку',
                        subtitle: '',
                        defaultName: currentName,
                        submitLabel: 'Сохранить',
                    });
                }

                function submitFolderNameModal() {
                    if (!folderNameModalPending || !folderNameModalInput) return;
                    var name = String(folderNameModalInput.value || '').trim();
                    if (!name) {
                        setFolderNameModalMsg('Введите название папки.');
                        folderNameModalInput.focus();
                        return;
                    }
                    if (folderNameModalSubmitBtn) folderNameModalSubmitBtn.disabled = true;

                    var pending = folderNameModalPending;

                    if (pending.mode === 'rename') {
                        setFolderNameModalMsg('Сохранение…');
                        folderApiPost('update', {
                            folder_id: pending.folderId,
                            name: name,
                        }).then(function () {
                            closeFolderNameModal();
                            return loadFolderTreeData();
                        }).then(function () {
                            refreshFolderManageList();
                            if (
                                cabinetConfig.mode === 'folder' &&
                                cabinetFolderId === pending.folderId
                            ) {
                                return reloadCabinet();
                            }
                        }).catch(function (e) {
                            setFolderNameModalMsg(e.message || String(e));
                            if (folderNameModalSubmitBtn) folderNameModalSubmitBtn.disabled = false;
                        });
                        return;
                    }

                    setFolderNameModalMsg('Создание…');
                    folderApiPost('create', {
                        name: name,
                        parent_id: pending.parentId,
                        sort_order: 0,
                    }).then(function (data) {
                        var folder = data && data.folder;
                        if (!folder || !folder.id) throw new Error('Не удалось создать папку');
                        if (pending.mode === 'with_cards' && pending.cardIds.length) {
                            return folderApiPost('add_items', {
                                folder_id: folder.id,
                                card_ids: pending.cardIds,
                            }).then(function (addData) {
                                return {
                                    folder: folder,
                                    added: (addData && addData.added_count) || 0,
                                    withCards: true,
                                };
                            });
                        }
                        return { folder: folder, added: 0, withCards: false };
                    }).then(function (result) {
                        closeFolderNameModal();
                        if (result.withCards) {
                            clearSelection();
                            setSelectionMode(false);
                            updateSelectionUi();
                            return loadFolderTreeData().then(function () {
                                if (folderManageModal && folderManageModal.classList.contains('is-open')) {
                                    refreshFolderManageList();
                                }
                            });
                        }
                        return loadFolderTreeData().then(function () {
                            if (pending.mode === 'empty' && pending.parentId != null) {
                                expandedFolderIds[pending.parentId] = true;
                                expandedFolderCreateParentIds[pending.parentId] = true;
                            }
                            if (folderManageModal && folderManageModal.classList.contains('is-open')) {
                                refreshFolderManageList();
                            }
                            if (folderCreateParentModal && folderCreateParentModal.classList.contains('is-open')) {
                                refreshFolderCreateParentList();
                            }
                            if (cabinetConfig.mode === 'folder') {
                                return reloadCabinet();
                            }
                        });
                    }).catch(function (e) {
                        setFolderNameModalMsg(e.message || String(e));
                        if (folderNameModalSubmitBtn) folderNameModalSubmitBtn.disabled = false;
                    });
                }

                function getSelectedCardIdsForFolderAction() {
                    return getSelectedCardsInCabinetOrder().map(function (row) { return row.id; });
                }

                function closeFolderActionModal() {
                    if (!folderActionModal) return;
                    folderActionModal.classList.remove('is-open');
                    folderActionModal.setAttribute('aria-hidden', 'true');
                    folderActionPendingCardIds = [];
                }

                function openFolderActionModal() {
                    if (!isRootAdminUser || !folderActionModal) return;
                    var cardIds = getSelectedCardIdsForFolderAction();
                    if (!cardIds.length) return;
                    folderActionPendingCardIds = cardIds.slice();
                    if (folderActionModalSubtitle) {
                        folderActionModalSubtitle.textContent = IS_MATCH_ANALYSIS
                            ? ('Выбрано матчей: ' + cardIds.length)
                            : ('Выбрано карточек: ' + cardIds.length);
                        folderActionModalSubtitle.style.display = '';
                    }
                    folderActionModal.classList.add('is-open');
                    folderActionModal.setAttribute('aria-hidden', 'false');
                }

                function openCreateFolderWithSelectedCardsModal(cardIds) {
                    if (!isRootAdminUser) return;
                    var ids = cardIds || getSelectedCardIdsForFolderAction();
                    if (!ids.length) return;
                    var parentId = getNewFolderParentId();
                    openFolderNameModal({
                        mode: 'with_cards',
                        parentId: parentId,
                        cardIds: ids,
                        title: parentId ? 'Новая подпапка' : 'Новая папка',
                        subtitle: 'Выбрано карточек: ' + ids.length,
                        defaultName: defaultNewFolderName(parentId ? 'Подпапка' : 'Папка'),
                    });
                }

                function closeFolderPickModal() {
                    if (!folderPickModal) return;
                    folderPickModal.classList.remove('is-open');
                    folderPickModal.setAttribute('aria-hidden', 'true');
                    folderPickPendingCardIds = [];
                    if (folderPickMsg) folderPickMsg.textContent = '';
                }

                function openFolderPickModal(cardIds) {
                    if (!isRootAdminUser || !folderPickModal) return;
                    var ids = cardIds || [];
                    if (!ids.length) return;
                    folderPickPendingCardIds = ids.slice();
                    if (folderPickModalSubtitle) {
                        folderPickModalSubtitle.textContent =
                            'Выберите папку · карточек: ' + ids.length;
                    }
                    if (folderPickMsg) folderPickMsg.textContent = '';
                    folderPickModal.classList.add('is-open');
                    folderPickModal.setAttribute('aria-hidden', 'false');
                    loadFolderTreeData()
                        .then(function () {
                            refreshFolderPickList();
                        })
                        .catch(function (e) {
                            if (folderPickMsg) {
                                folderPickMsg.textContent = 'Ошибка: ' + (e.message || e);
                            }
                        });
                }

                function closeFolderInsertConfirmModal() {
                    if (!folderInsertConfirmModal) return;
                    folderInsertConfirmModal.classList.remove('is-open');
                    folderInsertConfirmModal.setAttribute('aria-hidden', 'true');
                    folderInsertPending = null;
                    if (folderInsertConfirmModalMsg) folderInsertConfirmModalMsg.textContent = '';
                    if (folderInsertConfirmSubmitBtn) folderInsertConfirmSubmitBtn.disabled = false;
                }

                function openFolderInsertConfirmModal(folderId, folderName, cardIds) {
                    if (!folderInsertConfirmModal) return;
                    closeFolderPickModal();
                    folderInsertPending = {
                        folderId: folderId,
                        folderName: folderName,
                        cardIds: (cardIds || []).slice(),
                    };
                    var n = folderInsertPending.cardIds.length;
                    if (folderInsertConfirmModalText) {
                        folderInsertConfirmModalText.textContent =
                            'Добавить ' + n + ' ' + (n === 1 ? 'карточку' : 'карточек') +
                            ' в папку «' + folderName + '»?';
                    }
                    if (folderInsertConfirmModalMsg) folderInsertConfirmModalMsg.textContent = '';
                    folderInsertConfirmModal.classList.add('is-open');
                    folderInsertConfirmModal.setAttribute('aria-hidden', 'false');
                }

                function submitFolderInsertConfirm() {
                    if (!folderInsertPending) return;
                    if (folderInsertConfirmSubmitBtn) folderInsertConfirmSubmitBtn.disabled = true;
                    if (folderInsertConfirmModalMsg) folderInsertConfirmModalMsg.textContent = 'Вставка…';

                    var pending = folderInsertPending;
                    folderApiPost('add_items', {
                        folder_id: pending.folderId,
                        card_ids: pending.cardIds,
                    })
                        .then(function (data) {
                            var added = (data && data.added_count) || 0;
                            closeFolderInsertConfirmModal();
                            clearSelection();
                            setSelectionMode(false);
                            updateSelectionUi();
                            return showCabinetNotice(
                                'В папку «' + pending.folderName + '» добавлено карточек: ' + added + '.',
                                'Карточки добавлены'
                            );
                        })
                        .then(function () {
                            if (cabinetConfig.mode === 'folder') {
                                return reloadCabinet();
                            }
                        })
                        .catch(function (e) {
                            if (folderInsertConfirmModalMsg) {
                                folderInsertConfirmModalMsg.textContent = e.message || String(e);
                            }
                            if (folderInsertConfirmSubmitBtn) folderInsertConfirmSubmitBtn.disabled = false;
                        });
                }

                if (addToFolderBtn) {
                    addToFolderBtn.addEventListener('click', openFolderActionModal);
                }
                if (folderActionModalCancelBtn) {
                    folderActionModalCancelBtn.addEventListener('click', closeFolderActionModal);
                }
                if (folderActionModalOverlay) {
                    folderActionModalOverlay.addEventListener('click', closeFolderActionModal);
                }
                if (folderActionCreateBtn) {
                    folderActionCreateBtn.addEventListener('click', function () {
                        var cardIds = folderActionPendingCardIds.slice();
                        closeFolderActionModal();
                        openCreateFolderWithSelectedCardsModal(cardIds);
                    });
                }
                if (folderActionInsertBtn) {
                    folderActionInsertBtn.addEventListener('click', function () {
                        var cardIds = folderActionPendingCardIds.slice();
                        closeFolderActionModal();
                        openFolderPickModal(cardIds);
                    });
                }
                if (folderPickModalClose) {
                    folderPickModalClose.addEventListener('click', closeFolderPickModal);
                }
                if (folderPickModalOverlay) {
                    folderPickModalOverlay.addEventListener('click', closeFolderPickModal);
                }
                if (folderInsertConfirmCancelBtn) {
                    folderInsertConfirmCancelBtn.addEventListener('click', closeFolderInsertConfirmModal);
                }
                if (folderInsertConfirmModalOverlay) {
                    folderInsertConfirmModalOverlay.addEventListener('click', closeFolderInsertConfirmModal);
                }
                if (folderInsertConfirmSubmitBtn) {
                    folderInsertConfirmSubmitBtn.addEventListener('click', submitFolderInsertConfirm);
                }
                if (folderNameModalCancelBtn) {
                    folderNameModalCancelBtn.addEventListener('click', closeFolderNameModal);
                }
                if (folderNameModalOverlay) {
                    folderNameModalOverlay.addEventListener('click', closeFolderNameModal);
                }
                if (folderNameModalSubmitBtn) {
                    folderNameModalSubmitBtn.addEventListener('click', submitFolderNameModal);
                }
                if (folderNameModalInput) {
                    folderNameModalInput.addEventListener('keydown', function (ev) {
                        if (ev.key === 'Enter') {
                            ev.preventDefault();
                            submitFolderNameModal();
                        }
                    });
                }
                if (manageFoldersBtn) {
                    manageFoldersBtn.addEventListener('click', openFolderManageModal);
                }
                if (folderManageCreateBtn) {
                    folderManageCreateBtn.addEventListener('click', openFolderCreateParentModal);
                }
                if (folderManageModalClose) {
                    folderManageModalClose.addEventListener('click', closeFolderManageModal);
                }
                if (folderManageModalOverlay) {
                    folderManageModalOverlay.addEventListener('click', closeFolderManageModal);
                }
                if (folderCreateRootBtn) {
                    folderCreateRootBtn.addEventListener('click', function () {
                        openEmptyFolderNameModal(null, '');
                    });
                }
                if (folderCreateParentModalClose) {
                    folderCreateParentModalClose.addEventListener('click', closeFolderCreateParentModal);
                }
                if (folderCreateParentModalOverlay) {
                    folderCreateParentModalOverlay.addEventListener('click', closeFolderCreateParentModal);
                }
                if (folderScheduleCancelBtn) {
                    folderScheduleCancelBtn.addEventListener('click', closeFolderScheduleModal);
                }
                if (folderScheduleModalOverlay) {
                    folderScheduleModalOverlay.addEventListener('click', closeFolderScheduleModal);
                }
                if (folderScheduleSaveBtn) {
                    folderScheduleSaveBtn.addEventListener('click', submitFolderScheduleSave);
                }
                if (folderScheduleDeleteBtn) {
                    folderScheduleDeleteBtn.addEventListener('click', submitFolderScheduleDelete);
                }

            }
            if (WEB_STANDALONE || fabToken) {
                beginCabinetAuth('');
            } else {
                waitForTelegramWebAppInitData(5000, 50).then(beginCabinetAuth);
            }
        })();
    