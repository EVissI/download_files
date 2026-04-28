export function initEditorFeature(editorInstance) {
    if (!editorInstance) return;
    editorInstance.createModal();
    editorInstance.loadTools();
    editorInstance.setupEventListeners();
    editorInstance.setupCanvasEvents();
}
