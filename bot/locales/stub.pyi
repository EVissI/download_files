from decimal import Decimal
from typing import Literal

from fluent_compiler.types import FluentType
from typing_extensions import TypeAlias

PossibleValue: TypeAlias = str | int | float | Decimal | bool | FluentType

class TranslatorRunner:
    def get(self, path: str, **kwargs: PossibleValue) -> str: ...
    user: User
    keyboard: Keyboard
    auto: Auto
    analysis: Analysis
    waiting: Waiting

class UserStatic:
    @staticmethod
    def hello() -> Literal["""Hello! I&#39;m an analysis bot.I can help you analyze your backgammon games and collect statistics."""]: ...
    @staticmethod
    def has_no_sub() -> Literal["""You have no active subscription. Please activate a subscription to continue."""]: ...
    @staticmethod
    def input_promo() -> Literal["""Please enter the promocode to activate"""]: ...
    @staticmethod
    def promo_activated() -> Literal["""Promocode activated successfully!"""]: ...
    @staticmethod
    def invalid_promo() -> Literal["""Invalid promocode. Please check and try again."""]: ...
    @staticmethod
    def error_processing_promo() -> Literal["""An error occurred while processing the promocode. Please try again"""]: ...

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
    def text(*, analiz_balance: PossibleValue, lang_code: PossibleValue, player_username: PossibleValue) -> Literal["""🧍‍♂️ &lt;b&gt;Profile&lt;/b&gt;
├ 🎲 Nickname: &lt;code&gt;{ $player_username }&lt;/code&gt;
├ 📊 Games available for analysis: &lt;b&gt;{ $analiz_balance }&lt;/b&gt;
└ 🌐 Language: &lt;b&gt;{ $lang_code }&lt;/b&gt;"""]: ...
    @staticmethod
    def detailed_statistics(*, detailed_count: PossibleValue, detailed_rank_chequer: PossibleValue, detailed_rank_overall: PossibleValue, error_rate_chequer: PossibleValue, player_username: PossibleValue, rolls_marked_lucky: PossibleValue, rolls_marked_unlucky: PossibleValue, rolls_marked_very_lucky: PossibleValue, rolls_marked_very_unlucky: PossibleValue, snowie_error_rate: PossibleValue) -> Literal["""🎯 Gnu( { $detailed_count } games, Nickname: { $player_username })
Playing checkers:
├ Error rate: { $error_rate_chequer }
└ Rating: { $detailed_rank_chequer }
Luck:
├ Very Lucky: { $rolls_marked_very_lucky }
├ Lucky: { $rolls_marked_lucky }
├ Unlucky: { $rolls_marked_unlucky }
└ Very Unlucky: { $rolls_marked_very_unlucky }
Overall Stats:
├ Error Rate: { $snowie_error_rate }
└ Your Rank: { $detailed_rank_overall }"""]: ...
    @staticmethod
    def no_detailed_statistics() -> Literal["""No detailed statistics available. Please play more games to generate detailed stats."""]: ...
    @staticmethod
    def error_retrieving_statistics() -> Literal["""There was an error retrieving your statistics."""]: ...

class UserInline:
    @staticmethod
    def activate_promo() -> Literal["""Activate promocode"""]: ...
    @staticmethod
    def take_promo() -> Literal["""Take promocode"""]: ...

class User:
    static: UserStatic
    profile: UserProfile
    inline: UserInline

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

class AutoAnalyzeError:
    @staticmethod
    def parse() -> Literal["""An error occurred while parsing the file."""]: ...
    @staticmethod
    def save() -> Literal["""An error occurred while saving data."""]: ...

class AutoAnalyze:
    error: AutoAnalyzeError

    @staticmethod
    def submit() -> Literal["""Submit .mat file for automatic analysis"""]: ...
    @staticmethod
    def invalid() -> Literal["""Please send .mat file."""]: ...
    @staticmethod
    def complete() -> Literal["""File analysis complete. Select which player you were:"""]: ...

class Auto:
    analyze: AutoAnalyze

class AnalysisLuck:
    @staticmethod
    def __call__() -> Literal["""Luck"""]: ...
    @staticmethod
    def luck_plus_move() -> Literal["""Luck+ move"""]: ...
    @staticmethod
    def luck_move() -> Literal["""Luck move"""]: ...
    @staticmethod
    def unluck_plus_move() -> Literal["""Unluck+ move"""]: ...
    @staticmethod
    def unluck_move() -> Literal["""Unluck move"""]: ...
    @staticmethod
    def luck_rate() -> Literal["""Luck rate"""]: ...
    @staticmethod
    def rating() -> Literal["""Rating"""]: ...

class AnalysisCube:
    @staticmethod
    def __call__() -> Literal["""Cube"""]: ...
    @staticmethod
    def rating() -> Literal["""Rating"""]: ...

class AnalysisChequerplay:
    @staticmethod
    def bad_move() -> Literal["""Bad move"""]: ...
    @staticmethod
    def bad_plus_move() -> Literal["""Bad+ move"""]: ...
    @staticmethod
    def error_rate() -> Literal["""Error rate"""]: ...
    @staticmethod
    def rating() -> Literal["""Rating"""]: ...

class AnalysisOverall:
    @staticmethod
    def error_rate() -> Literal["""Error rate"""]: ...
    @staticmethod
    def rating() -> Literal["""Rating"""]: ...

class Analysis:
    luck: AnalysisLuck
    cube: AnalysisCube
    chequerplay: AnalysisChequerplay
    overall: AnalysisOverall

    @staticmethod
    def results() -> Literal["""Analysis results"""]: ...
    @staticmethod
    def vs(*, player1_name: PossibleValue, player2_name: PossibleValue) -> Literal["""{ $player1_name } vs { $player2_name }"""]: ...
    @staticmethod
    def playing_checkers() -> Literal["""Playing checkers"""]: ...
    @staticmethod
    def overall_statistic() -> Literal["""Overall statistic"""]: ...
    @staticmethod
    def error_formatting() -> Literal["""Error formatting analysis results."""]: ...
    @staticmethod
    def param() -> Literal["""Param"""]: ...

class Waiting:
    @staticmethod
    def think1() -> Literal["""Think."""]: ...
    @staticmethod
    def think2() -> Literal["""Think.."""]: ...
    @staticmethod
    def think3() -> Literal["""Think..."""]: ...
