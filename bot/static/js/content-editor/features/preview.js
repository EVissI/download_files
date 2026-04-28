export function attachPreviewFeature(editorInstance) {
    if (!editorInstance) return;
    // Вынесенный модуль предпросмотра: пока оставляет текущую реализацию
    // внутри класса ContentEditor и формирует отдельный feature-layer
    // для безопасной поэтапной декомпозиции.
}
