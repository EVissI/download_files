def get_text(key: str, **kwargs) -> str:
    """
    Получить текст по ключу с возможностью форматирования через kwargs.
    """
    template = text.get(key, "")
    return template.format(**kwargs)

text = {
    'start': 'Hello! I\'m an analysis bot.I can help you analyze your backgammon games and collect statistics.',
    'file_save_error': 'You can only send text files (.txt, .mat).',
    'file_saved': 'Your file: {file_name} has been saved',
    'cancel': 'Сancel',
    'send_file': 'Please send a file for analysis. Supported formats: .sgf, .mat',
    'file_save_error': 'You can only send .sgf or .mat files.',
    'file_saved': 'File saved successfully. Thank you! Wait for analysis.',
}