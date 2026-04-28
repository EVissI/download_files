export function initContentCardViewFeature(editorInstance) {
    if (!editorInstance) return;
    editorInstance.initContentCardViewOnly();
}

export async function bootstrapContentCardViewFeature(editorInstance) {
    if (!editorInstance) return;
    await editorInstance.bootstrapContentCardViewPage();
}
