
user-static-hello = Hello! I'm an analysis bot.I can help you analyze your backgammon games and collect statistics.

keyboard-user-reply-autoanalyze = 🔮 Autoanalyze
keyboard-user-reply-profile = 🧍‍♂️ Profile
keyboard-admin-reply-admin_panel = Admin Panel

keyboard-reply-cancel = Cancel
keyboard-reply-back = Back

keyboard-inline-change_language-ru = 🇷🇺 Русский
keyboard-inline-change_language-en = 🇺🇸 English

user-profile-change_language_text = Select a language for the bot:
user-profile-text = Placeholder
user-profile-inline_button-my_stats = My Statistics
user-profile-inline_button-change_language = Change Language
user-profile-change_language-confirm = Language changed successfully!

user-profile-detailed_statistics = 🎯 Gnu( { $detailed_count -> 
    [one] 1 game 
    *[other] { $detailed_count } games 
    }, Nickname: { $player_username })
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
    └ Your Rank: { $detailed_rank_overall }
user-profile-no_detailed_statistics = No detailed statistics available. Please play more games to generate detailed stats. 
user-profile-error_retrieving_statistics = There was an error retrieving your statistics.

auto-analyze-submit = Submit .mat file for automatic analysis 
auto-analyze-invalid = Please send .mat file. 
auto-analyze-complete = File analysis complete. Select which player you were: 
auto-analyze-error-parse = An error occurred while parsing the file. 
auto-analyze-error-save = An error occurred while saving data.