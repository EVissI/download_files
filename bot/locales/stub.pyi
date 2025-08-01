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
    @staticmethod
    def payment() -> Literal["""Buy Analysis"""]: ...

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
    def detailed_statistics(*, cube_error_rate: PossibleValue, detailed_count: PossibleValue, detailed_rank_chequer: PossibleValue, detailed_rank_cube: PossibleValue, detailed_rank_overall: PossibleValue, error_rate_chequer: PossibleValue, missed_doubles_above_cp: PossibleValue, missed_doubles_below_cp: PossibleValue, player_username: PossibleValue, rolls_marked_lucky: PossibleValue, rolls_marked_unlucky: PossibleValue, rolls_marked_very_lucky: PossibleValue, rolls_marked_very_unlucky: PossibleValue, snowie_error_rate: PossibleValue, wrong_doubles_above_tg: PossibleValue, wrong_doubles_below_sp: PossibleValue, wrong_passes: PossibleValue, wrong_takes: PossibleValue) -> Literal["""🎯 Gnu( { $detailed_count } games, Nickname: { $player_username })
Playing checkers:
├ Error rate: { $error_rate_chequer }
└ Rating: { $detailed_rank_chequer }
Luck:
├ Very Lucky: { $rolls_marked_very_lucky }
├ Lucky: { $rolls_marked_lucky }
├ Unlucky: { $rolls_marked_unlucky }
└ Very Unlucky: { $rolls_marked_very_unlucky }
Cube decisions:
├ Missed doubles below CP: { $missed_doubles_below_cp }
├ Missed doubles above CP: { $missed_doubles_above_cp }
├ Wrong doubles below SP: { $wrong_doubles_below_sp }
├ Wrong doubles above TG: { $wrong_doubles_above_tg }
├ Wrong takes: { $wrong_takes }
├ Wrong passes: { $wrong_passes }
├ Error rate: { $cube_error_rate }
└ Cube rating: { $detailed_rank_cube }
Overall Stats:
├ Error Rate: { $snowie_error_rate }
└ Your Rank: { $detailed_rank_overall }"""]: ...
    @staticmethod
    def no_detailed_statistics() -> Literal["""No detailed statistics available. Please play more games to generate detailed stats."""]: ...
    @staticmethod
    def error_retrieving_statistics() -> Literal["""There was an error retrieving your statistics."""]: ...
    @staticmethod
    def payment_success(*, amount: PossibleValue, name: PossibleValue) -> Literal["""✅ Purchase of the &#34;{ $name }&#34; package for { $amount } analyses completed successfully!"""]: ...
    @staticmethod
    def payment_error() -> Literal["""❌ An error occurred while processing the payment. Please try again later."""]: ...
    @staticmethod
    def payment_not_found() -> Literal["""❌ Package not found. Please select another one."""]: ...
    @staticmethod
    def payment_invalid_payload() -> Literal["""❌ Invalid payment. Please try again."""]: ...
    @staticmethod
    def payment_text() -> Literal["""Select a package to buy:"""]: ...
    @staticmethod
    def expire_notice(*, amount: PossibleValue, source: PossibleValue) -> Literal["""⏳ { $amount } analyses from { $source } have expired."""]: ...

class UserInline:
    @staticmethod
    def activate_promo() -> Literal["""Activate promocode"""]: ...
    @staticmethod
    def take_promo() -> Literal["""Take promocode"""]: ...

class UserRank:
    @staticmethod
    def superchamp() -> Literal["""🏆 World Champion"""]: ...
    @staticmethod
    def champ() -> Literal["""🥇 World Class"""]: ...
    @staticmethod
    def expert() -> Literal["""🥈 Expert"""]: ...
    @staticmethod
    def advanced() -> Literal["""🥉 Advanced"""]: ...
    @staticmethod
    def intermediate() -> Literal["""🎓 Intermediate"""]: ...
    @staticmethod
    def casual() -> Literal["""🎲 Casual"""]: ...
    @staticmethod
    def beginner() -> Literal["""🐣 Beginner"""]: ...

class User:
    static: UserStatic
    profile: UserProfile
    inline: UserInline
    rank: UserRank

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
    @staticmethod
    def download_pdf() -> Literal["""📄 Download PDF"""]: ...
    @staticmethod
    def no_thanks() -> Literal["""❌ No, thanks"""]: ...
    @staticmethod
    def ask_pdf() -> Literal["""Would you like to get the analysis as a PDF?"""]: ...
    @staticmethod
    def pdf_ready() -> Literal["""Your analysis in PDF format:"""]: ...
    @staticmethod
    def no_pdf() -> Literal["""Okay, PDF will not be sent. Thank you for using the bot!"""]: ...

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
    def rating() -> Literal["""Cube decision rating"""]: ...
    @staticmethod
    def missed_doubles_below_cp() -> Literal["""Missed doubles below CP"""]: ...
    @staticmethod
    def missed_doubles_above_cp() -> Literal["""Missed doubles above CP"""]: ...
    @staticmethod
    def wrong_doubles_below_sp() -> Literal["""Wrong doubles below SP"""]: ...
    @staticmethod
    def wrong_doubles_above_tg() -> Literal["""Wrong doubles above TG"""]: ...
    @staticmethod
    def wrong_takes() -> Literal["""Wrong takes"""]: ...
    @staticmethod
    def wrong_passes() -> Literal["""Wrong passes"""]: ...
    @staticmethod
    def error_rate() -> Literal["""Error rate"""]: ...

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
