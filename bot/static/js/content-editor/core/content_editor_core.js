function getCacheQueryFromModuleUrl() {
    try {
        return new URL(import.meta.url).search || '';
    } catch (_e) {
        return '';
    }
}

export async function createContentEditorCore() {
    const cacheQuery = getCacheQueryFromModuleUrl();
    const [{ default: ContentEditor }, { attachPreviewFeature }] = await Promise.all([
        import(`/static/js/content_editor.js${cacheQuery}`),
        import(`/static/js/content-editor/features/preview.js${cacheQuery}`),
    ]);
    const editor = new ContentEditor();
    attachPreviewFeature(editor);
    return editor;
}

export async function bootstrapViewMode(editor) {
    const cacheQuery = getCacheQueryFromModuleUrl();
    const { bootstrapContentCardViewFeature } = await import(
        `/static/js/content-editor/features/content_card_view.js${cacheQuery}`
    );
    await bootstrapContentCardViewFeature(editor);
}
