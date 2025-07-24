from decimal import Decimal
from typing import Literal

from fluent_compiler.types import FluentType
from typing_extensions import TypeAlias

PossibleValue: TypeAlias = str | int | float | Decimal | bool | FluentType

class TranslatorRunner:
    def get(self, path: str, **kwargs: PossibleValue) -> str: ...
    user: User
    keyboard: Keyboard

class UserStatic:
    @staticmethod
    def hello() -> Literal["""Hello! I&#39;m an analysis bot.I can help you analyze your backgammon games and collect statistics."""]: ...

class UserProfileInlineButton:
    @staticmethod
    def my_stats() -> Literal["""My Statistics"""]: ...
    @staticmethod
    def change_language() -> Literal["""Change Language"""]: ...

class UserProfileChangeLanguage:
    @staticmethod
    def confirm() -> Literal["""Language changed successfully!"""]: ...

class UserProfile:
    inline_button: UserProfileInlineButton
    change_language: UserProfileChangeLanguage

    @staticmethod
    def change_language_text() -> Literal["""Select a language for the bot:"""]: ...
    @staticmethod
    def text() -> Literal["""Placeholder"""]: ...
    @staticmethod
    def no_detailed_statistics() -> Literal["""No detailed statistics available. Please play more games to generate detailed stats."""]: ...
    @staticmethod
    def error_retrieving_statistics() -> Literal["""There was an error retrieving your statistics."""]: ...

class User:
    static: UserStatic
    profile: UserProfile

class KeyboardUserReply:
    @staticmethod
    def autoanalyze() -> Literal["""🔮 Autoanalyze"""]: ...
    @staticmethod
    def profile() -> Literal["""🧍‍♂️ Profile"""]: ...

class KeyboardUser:
    reply: KeyboardUserReply

class KeyboardAdminReply:
    @staticmethod
    def admin_panel() -> Literal["""Admin Panel"""]: ...

class KeyboardAdmin:
    reply: KeyboardAdminReply

class KeyboardReply:
    @staticmethod
    def cancel() -> Literal["""Cancel"""]: ...
    @staticmethod
    def back() -> Literal["""Back"""]: ...

class KeyboardInlineChangeLanguage:
    @staticmethod
    def ru() -> Literal["""🇷🇺 Русский"""]: ...
    @staticmethod
    def en() -> Literal["""🇺🇸 English"""]: ...

class KeyboardInline:
    change_language: KeyboardInlineChangeLanguage

class Keyboard:
    user: KeyboardUser
    admin: KeyboardAdmin
    reply: KeyboardReply
    inline: KeyboardInline
