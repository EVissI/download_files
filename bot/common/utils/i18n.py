from loguru import logger
from fluent_compiler.bundle import FluentBundle

from fluentogram import FluentTranslator, TranslatorHub


def create_translator_hub() -> TranslatorHub:
    translator_hub = TranslatorHub(
        {"ru": ("ru", "en"), "en": ("en", "ru")},
        [
            FluentTranslator(
                locale="ru",
                translator=FluentBundle.from_files(
                    locale="ru-RU", filenames=["bot/locales/ru/LC_MESSAGES/txt.ftl"]
                ),
            ),
            FluentTranslator(
                locale="en",
                translator=FluentBundle.from_files(
                    locale="en-US", filenames=["bot/locales/en/LC_MESSAGES/txt.ftl"]
                ),
            ),
        ],
    )
    return translator_hub


def get_all_locales_for_key(translator_hub: TranslatorHub, key: str) -> list:
    """
    Возвращает список переводов для всех локалей, зарегистрированных в TranslatorHub по ключу key.
    пример 'main.profile.button.text'.
    """
    translations = []
    for translator in translator_hub.storage.get_translators_list():
        try:
            value = translator.get(key)
        except Exception as e:
            logger.error(f"Translation error for {translator.locale}: {e}")
            value = None
        translations.append(value)
    return translations
