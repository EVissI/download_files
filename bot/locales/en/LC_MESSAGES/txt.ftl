﻿
user-static-hello = Hello! I'm an analysis bot.I can help you analyze your backgammon games and collect statistics.

keyboard-user-reply-autoanalyze = 🔮 Autoanalyze
keyboard-user-reply-profile = 🧍‍♂️ Profile
keyboard-admin-reply-admin_panel = Admin Panel

keyboard-reply-cancel = Cancel
keyboard-reply-back = Back

keyboard-inline-change_language-ru = 🇷🇺 Русский
keyboard-inline-change_language-en = 🇺🇸 English

user-profile-change_language_text = Select a language for the bot:
user-profile-text = 
    🧍‍♂️ <b>Profile</b>
    ├ 🎲 Nickname: <code>{ $player_username }</code>
    ├ 📊 Games available for analysis: <b>{ $analiz_balance }</b>
    └ 🌐 Language: <b>{ $lang_code }</b>
user-profile-inline_button-my_stats = My Statistics
user-profile-inline_button-change_language = Change Language
user-profile-inline_button-payment = Buy Analysis
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

user-rank-superchamp = 🏆 World Champion
user-rank-champ = 🥇 World Class
user-rank-expert = 🥈 Expert
user-rank-advanced = 🥉 Advanced
user-rank-intermediate = 🎓 Intermediate
user-rank-casual = 🎲 Casual
user-rank-beginner = 🐣 Beginner

user-profile-payment_success = ✅ Purchase of the "{ $name }" package for { $amount } analyses completed successfully!
user-profile-payment_error = ❌ An error occurred while processing the payment. Please try again later.
user-profile-payment_not_found = ❌ Package not found. Please select another one.
user-profile-payment_invalid_payload = ❌ Invalid payment. Please try again.

user-profile-payment_text = Select a package to buy:
user-profile-expire_notice = ⏳ { $amount } analyses from { $source } have expired.

auto-analyze-download_pdf = 📄 Download PDF
auto-analyze-no_thanks = ❌ No, thanks
auto-analyze-ask_pdf = Would you like to get the analysis as a PDF?
auto-analyze-pdf_ready = Your analysis in PDF format:
auto-analyze-no_pdf = Okay, PDF will not be sent. Thank you for using the bot!

analysis-cube-missed_doubles_below_cp = Missed doubles below CP
analysis-cube-missed_doubles_above_cp = Missed doubles above CP
analysis-cube-wrong_doubles_below_sp = Wrong doubles below SP
analysis-cube-wrong_doubles_above_tg = Wrong doubles above TG
analysis-cube-wrong_takes = Wrong takes
analysis-cube-wrong_passes = Wrong passes
analysis-cube-error_rate = Error rate
analysis-cube-rating = Cube decision rating

