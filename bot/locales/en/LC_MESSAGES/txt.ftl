
user-static-hello = Hello! I'm an analysis bot.I can help you analyze your backgammon games and collect statistics.

keyboard-user-reply-autoanalyze = 🔮 Analysis
keyboard-user-reply-profile = 🧍‍♂️ Profile
keyboard-admin-reply-admin_panel = Admin Panel
keyboard-user-reply-short_board_view = 📊 Pleer
keyboard-user-reply-pokaz = 🎯 Position
user-pokaz-select_action = Select an action:
user-pokaz-open_editor = Open position editor
keyboard-reply-cancel = Cancel
keyboard-reply-back = Back

keyboard-inline-change_language-ru = 🇷🇺 Русский
keyboard-inline-change_language-en = 🇺🇸 English
keyboard-confirm = Confirm
user-profile-change_language_text = Select a language for the bot:
user-profile-text = 
    🧍‍♂️ <b>Profile</b>
    ├ 🎲 Nickname: <code>{ $player_username }</code>
    ├ 🔮 Matches: <b>{ $match_balance }</b>
    ├ 📊 Moneygames: <b>{ $analiz_balance }</b>
    ├ 💎 Pleer <b>{ $short_board_balance }</b>
    ├ 👁️ Mistakes <b>{ $hints_balance }</b>
    ├ 🎯 Position <b>{ $pokaz_balance }</b>
    ├ 💬 Comments <b>{ $comments_balance }</b>
    ├ 📷 Screenshots <b>{ $screenshots_balance }</b>
    └ 🌐 Language: <b>{ $lang_code }</b>
user-profile-inline_button-my_stats = My Statistics
user-profile-inline_button-change_language = Change Language
user-profile-inline_button-payment = Buy a subscription
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

auto-analyze-submit = Submit file for automatic analysis
auto-analyze-invalid = Invalide file type. 
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

user-inline-activate_promo = Activate promo code
user-inline-activate_promo_2 = Activate promo code
user-inline-take_promo = Take promo code

user-static-input_promo = Please enter the promo code to activate
user-static-promo_activated = Promocode activated successfully!
user-static-invalid_promo = Invalid promo code. Please check and try again.
user-static-error_processing_promo = An error occurred while processing the promo code. Please try again

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
auto-analyze-send_to_hints = 👁️ Error Analysis
auto-analyze-ask_hints = Would you like to send this file for error analysis?
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

user-static-share_phone = Share phone
user-static-missing_contact_info = Please share your contact information to continue payment.
user-static-share_email = Share email
user-static-contact_info_shared = Contact information shared successfully!

user-static-invalid_email_format = Invalid email format. Please enter a valid email address.
user-static-phone_request_sent = Phone request sent. Please share your phone number.
user-static-enter_email = Email request sent. Please enter your email address.

user-static-gift = 🎁 You have a gift!
    You have access to the promo code <code>NEW</code>!
    You can activate it in <b>Profile</b> → <b>Activate promo code.</b>

auto-analyze-choose_type = Please select the type of analysis: 
auto-analyze-moneygame = Moneygame 
auto-analyze-games_match = Match 
auto-analyze-submit_moneygame = Please submit a Moneygame file for analysis. 
auto-analyze-submit_match = Please submit a Match file for analysis. 
auto-analyze-wrong_type_match = This file is a Match, but you selected Moneygame. Please select the correct analysis type. 
auto-analyze-wrong_type_moneygame = This file is a Moneygame, but you selected Match. Please select the correct analysis type.
auto-analyze-not_ebought_balance = Not enough balance for this service, activate promo code or buy balance in profile
auto-analyze-select_autoanalyze_type = Please select the type of auto analysis:
auto-batch-choose_type = Please select the upload method for batch analysis: 
auto-batch-sequential = Upload one by one 
auto-batch-zip = Upload ZIP archive 
auto-batch-submit_sequential = Upload match files one by one. Press "Stop uploading" when done. 
auto-batch-stop = Stop uploading 
auto-batch-submit_zip = Please upload a ZIP archive containing match files. 
auto-batch-invalid_zip = Invalid file; please upload a ZIP archive. 
auto-batch-added = File added. Current queue: { $count } 
auto-batch-no_files = No files uploaded. Returning to main menu. 
auto-batch-no_valid_files = No valid match files in ZIP. 
auto-batch-progress = Analyzing { $current } / { $total } 
auto-batch-summary = Average results from { $count } matches: 
auto-batch-no_matches = No match files found; no analyses performed. 
auto-batch-wrong_file = Skipped: Not a match file. 
auto-batch-no_data_pdf = No batch analysis data available for PDF generation.
auto-analyze-error-balance = Not enough balance for full analysis. Please activate promo code or buy balance in profile.
auto-analyze-batch_type = Batch analysis
auto-analyze-single_match = One game
user-static-select_autoanalyze_type = Please select the type of auto analysis:
auto-batch-summary_pr_header = Games: { $count }
    Date: { $date }
auto-batch-summary_pr = pr for <b>{ $player }</b> - average <b>{ $average_pr }</b>: 
    ({ $pr_list })
keyboard-user-reply-hint_viewer = 👁️ Mistakes

# Pokaz page (position editor) — en
pokaz-page-title = Position Editor
pokaz-page-hide-pips = Hide pips
pokaz-page-hide-point-dropdowns = Hide point dropdowns
pokaz-page-lower-player = Lower player:
pokaz-page-toggle-lower-player = Toggle lower player
pokaz-page-place-checkers = Place checkers
pokaz-page-delete-checkers = Remove checkers
pokaz-page-moneygame = Moneygame
pokaz-page-match = Match
pokaz-page-checkers = Checkers
pokaz-page-white-checkers = White checkers
pokaz-page-black-checkers = Black checkers
pokaz-page-on-bar = On bar
pokaz-page-jacobi-beaver-max = Jacoby Beaver Max cube
pokaz-page-yes = Yes
pokaz-page-no = No
pokaz-page-game-type = Game type
pokaz-page-match-headers-lower = Lower pts
pokaz-page-match-headers-upper = Upper pts
pokaz-page-match-headers-length = Match len
pokaz-page-match-headers-max-cube = Max cube
pokaz-page-cube-shown = Cube shown?
pokaz-page-cube = Cube
pokaz-page-whose-cube = Whose cube?
pokaz-page-crawford = Crawford
pokaz-page-whose-turn = Whose turn?
pokaz-page-dice = Dice
pokaz-page-history-back = History back
pokaz-page-history-forward = History forward
pokaz-page-confirm-move = Confirm move
pokaz-page-random-dice = Random dice
pokaz-page-analyze-position = Analyze position
pokaz-page-collapse-table = Collapse table
pokaz-page-expand-table = Expand table
pokaz-page-toggle-table = Collapse/expand table
pokaz-page-take-screenshot = Take screenshot
pokaz-page-save-screenshot = Save screenshot to clipboard
pokaz-page-upload-screenshots = Upload screenshots
pokaz-page-confirm = Confirmation
pokaz-page-clear = Clear
pokaz-page-clear-confirm-msg = Are you sure you want to clear the board?
pokaz-page-init = Set up
pokaz-page-init-confirm-msg = Are you sure you want to set up the initial position?
pokaz-page-admin-comment-placeholder = Enter message text...
pokaz-page-move = Move
pokaz-page-equity = Equity
pokaz-page-restore-position = Restore saved position
pokaz-page-next-cube = Next cube
pokaz-page-match-to = Match to __LENGTH__. Score __MAX__-__MIN__
pokaz-page-table-header-move = Move
pokaz-page-table-header-equity = Equity
pokaz-page-table-header-action = Action
pokaz-page-impossible-move = Impossible move
pokaz-page-unknown-hint-type = Unknown hint type
pokaz-page-turn-white = White to move
pokaz-page-turn-black = Black to move
pokaz-page-loading-hints = Loading hints...
pokaz-page-error-insufficient-balance = Insufficient balance for hints
pokaz-page-error-no-chat-id = Missing chat_id. Open via Telegram.
pokaz-page-cube-no-double = no double
pokaz-page-cube-double = double
pokaz-page-cube-take = take
pokaz-page-cube-pass = pass
pokaz-page-comment-btn = Comment
pokaz-page-comment-modal-title = Ask a question about the position
pokaz-page-comment-send = Send
pokaz-page-comment-empty-alert = Please enter a description of the issue