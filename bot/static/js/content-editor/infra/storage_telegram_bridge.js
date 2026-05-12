export function clearContentEditorLocalStorage() {
    if (typeof localStorage === 'undefined') return;
    const toRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && k.startsWith('contentEditor_')) {
            toRemove.push(k);
        }
    }
    toRemove.forEach((k) => localStorage.removeItem(k));
}

export function clearContentEditorIndexedDB() {
    try {
        if (typeof indexedDB !== 'undefined') {
            indexedDB.deleteDatabase('contentEditorMedia');
        }
    } catch (e) {
        // ignore
    }
}

export function shouldClearEditorStorageOnBoot() {
    return typeof window === 'undefined' || window.__CONTENT_CARD_VIEW_ONLY__ !== true;
}

export function getTelegramInitData() {
    try {
        return (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || '';
    } catch (e) {
        return '';
    }
}

/**
 * На части клиентов Telegram (в т.ч. Desktop) initData может появиться чуть позже первого чтения после tg.ready().
 */
export function waitForTelegramWebAppInitData(maxWaitMs = 5000, stepMs = 50) {
    if (typeof window === 'undefined') {
        return Promise.resolve('');
    }
    try {
        const params = new URLSearchParams(window.location.search || '');
        if (params.get('fab_token')) {
            return Promise.resolve('');
        }
    } catch (_e) {
        // ignore
    }
    const tg = window.Telegram && window.Telegram.WebApp;
    if (!tg) {
        return Promise.resolve('');
    }
    const existing = tg.initData || '';
    if (existing) {
        return Promise.resolve(existing);
    }
    try {
        if (typeof tg.ready === 'function') {
            tg.ready();
        }
    } catch (_e) {}
    const deadline = Date.now() + maxWaitMs;
    return new Promise((resolve) => {
        function tick() {
            try {
                const v =
                    (window.Telegram &&
                        window.Telegram.WebApp &&
                        window.Telegram.WebApp.initData) ||
                    '';
                if (v) {
                    resolve(v);
                    return;
                }
            } catch (_e) {}
            if (Date.now() >= deadline) {
                resolve('');
                return;
            }
            setTimeout(tick, stepMs);
        }
        tick();
    });
}
