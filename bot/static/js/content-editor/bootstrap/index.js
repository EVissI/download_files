function getCacheQueryFromModuleUrl() {
    try {
        return new URL(import.meta.url).search || '';
    } catch (_e) {
        return '';
    }
}

document.addEventListener('DOMContentLoaded', async function () {
    const cacheQuery = getCacheQueryFromModuleUrl();
    const [storageBridge, core] = await Promise.all([
        import(`/static/js/content-editor/infra/storage_telegram_bridge.js${cacheQuery}`),
        import(`/static/js/content-editor/core/content_editor_core.js${cacheQuery}`),
    ]);
    if (storageBridge.shouldClearEditorStorageOnBoot()) {
        storageBridge.clearContentEditorLocalStorage();
        storageBridge.clearContentEditorIndexedDB();
    }
    const contentEditor = await core.createContentEditorCore();
    window.contentEditor = contentEditor;
    if (window.__CONTENT_CARD_VIEW_ONLY__ === true) {
        core.bootstrapViewMode(contentEditor).catch((e) => {
            console.error('content card view bootstrap:', e);
        });
    }
});
