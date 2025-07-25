
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

analysis-results = Analysis results 
analysis-vs = { $player1_name } vs { $player2_name } 
analysis-playing_checkers = Playing checkers 
analysis-luck = Luck 
analysis-cube = Cube 
analysis-overall_statistic = Overall statistic 
analysis-error_formatting = Error formatting analysis results.

analysis-param = Param
analysis-chequerplay-bad_move = Bad move 
analysis-chequerplay-bad_plus_move = Bad+ move 
analysis-chequerplay-error_rate = Error rate 
analysis-chequerplay-rating = Rating

analysis-luck-luck_plus_move = Luck+ move 
analysis-luck-luck_move = Luck move 
analysis-luck-unluck_plus_move = Unluck+ move 
analysis-luck-unluck_move = Unluck move 
analysis-luck-luck_rate = Luck rate 
analysis-luck-rating = Rating

analysis-cube-rating = Rating

analysis-overall-error_rate = Error rate 
analysis-overall-rating = Rating

waiting-think1 = Think. 
waiting-think2 = Think.. 
waiting-think3 = Think...

user-static-has_no_sub = You have no active subscription. Please activate a subscription to continue.

user-inline-activate_promo = Activate promocode
user-inline-take_promo = Take promocode

user-static-input_promo = Please enter the promocode to activate
user-static-promo_activated = Promocode activated successfully!
user-static-invalid_promo = Invalid promocode. Please check and try again.
user-static-error_processing_promo = An error occurred while processing the promocode. Please try again