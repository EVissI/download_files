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
