import {
    clearContentEditorIndexedDB,
    clearContentEditorLocalStorage,
    shouldClearEditorStorageOnBoot,
} from '/static/js/content-editor/infra/storage_telegram_bridge.js';
import {
    bootstrapViewMode,
    createContentEditorCore,
} from '/static/js/content-editor/core/content_editor_core.js';

function ensureStorageCleanup() {
    if (!shouldClearEditorStorageOnBoot()) return;
    clearContentEditorLocalStorage();
    clearContentEditorIndexedDB();
}

document.addEventListener('DOMContentLoaded', function () {
    ensureStorageCleanup();
    const contentEditor = createContentEditorCore();
    window.contentEditor = contentEditor;
    if (window.__CONTENT_CARD_VIEW_ONLY__ === true) {
        bootstrapViewMode(contentEditor).catch((e) => {
            console.error('content card view bootstrap:', e);
        });
    }
});
