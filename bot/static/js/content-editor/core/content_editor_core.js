import ContentEditor from '/static/js/content_editor.js';
import { attachPreviewFeature } from '/static/js/content-editor/features/preview.js';
import { bootstrapContentCardViewFeature } from '/static/js/content-editor/features/content_card_view.js';

export function createContentEditorCore() {
    const editor = new ContentEditor();
    attachPreviewFeature(editor);
    return editor;
}

export async function bootstrapViewMode(editor) {
    await bootstrapContentCardViewFeature(editor);
}
