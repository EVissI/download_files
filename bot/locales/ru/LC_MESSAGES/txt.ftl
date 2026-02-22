
user-static-hello = Привет! Я бот для анализа игр в короткие нарды. Я проанализирую Ваши игры и соберу статистику

keyboard-user-reply-autoanalyze = 🔮 Анализ
keyboard-user-reply-profile = 🧍‍♂️ Профиль
keyboard-user-reply-short_board_view = 📊 Плеер
keyboard-admin-reply-admin_panel = Админпанель
keyboard-user-reply-hint_viewer = 👁️ Ошибки
keyboard-user-reply-pokaz = 🎯 Позиция
user-pokaz-select_action = Для входа в редактор, перейдите по ссылке ниже ⬇


keyboard-reply-cancel = Отмена
keyboard-reply-back = Назад

keyboard-inline-change_language-ru = 🇷🇺 Русский
keyboard-inline-change_language-en = 🇺🇸 English
keyboard-confirm = Подтвердить

user-profile-change_language_text = Выберите язык для бота:
user-profile-text = 
    🧍‍♂️ <b>Профиль</b>
    ├ 🎲 Никнейм: <code>{ $player_username }</code>
    ├ 🔮 Матчи: <b>{ $match_balance }</b>
    ├ 📊 Манигеймы: <b>{ $analiz_balance }</b>
    ├ 💎 Плеер <b>{ $short_board_balance }</b>
    ├ 👁️ Ошибки <b>{ $hints_balance }</b>
    ├ 🎯 Позиция <b>{ $pokaz_balance }</b>
    ├ 💬 Комментарии <b>{ $comments_balance }</b>
    ├ 📷 Скриншоты <b>{ $screenshots_balance }</b>
    └ 🌐 Язык: <b>{ $lang_code }</b>
user-profile-inline_button-my_stats = Моя статистика
user-profile-inline_button-change_language = Изменить язык
user-profile-inline_button-payment = Пакеты
user-profile-change_language-confirm = Язык бота успешно изменён!

user-profile-detailed_statistics = 🎯 Gnu( { $detailed_count ->
    [one] 1 игра
    [few] { $detailed_count } игры
    *[other] { $detailed_count } игр
    }, Никнейм: { $player_username })
    Игра в шашки:
    ├ Ошибка: { $error_rate_chequer }
    └ Рейтинг: { $detailed_rank_chequer }
    Удача:
    ├ Очень удачно: { $rolls_marked_very_lucky }
    ├ Удачно: { $rolls_marked_lucky }
    ├ Неудачно: { $rolls_marked_unlucky }
    └ Очень неудачно: { $rolls_marked_very_unlucky }
    Игра кубом:
    ├ Пропущенный куб по ДП: { $missed_doubles_below_cp }
    ├ Пропущенный куб по ТГ: { $missed_doubles_above_cp }
    ├ Ошибочный куб по ДП: { $wrong_doubles_below_sp }
    ├ Ошибочный куб по ТГ: { $wrong_doubles_above_tg }
    ├ Ошибочно принято кубов: { $wrong_takes }
    ├ Ошибочных пассов: { $wrong_passes }
    ├ Оценка ошибок: { $cube_error_rate }
    └ Оценка решений по кубу: { $detailed_rank_cube }
    Общая статистика:
    ├ Ошибка: { $snowie_error_rate }
    └ Ваш ранг: { $detailed_rank_overall }

user-profile-no_detailed_statistics = Подробная статистика отсутствует. Пожалуйста, сыграйте больше игр для её генерации. 
user-profile-error_retrieving_statistics = Произошла ошибка при получении ваших статистических данных.

auto-analyze-submit = Отправьте файл для автоматического анализа
auto-analyze-invalid = Неподерживаемый тип файла. 
auto-analyze-complete = Анализ завершен. Какой Ваш ник?
auto-analyze-error-parse = Произошла ошибка при разборе файла. 
auto-analyze-error-save = Произошла ошибка при сохранении данных.

analysis-results = Результаты анализа 
analysis-vs = { $player1_name } против { $player2_name } 
analysis-playing_checkers = Игра шашками 
analysis-luck = Удача 
analysis-cube = Игра кубом
analysis-overall_statistic = Общая статистика 
analysis-error_formatting = Ошибка при форматировании результатов анализа.

analysis-param = Параметр
analysis-chequerplay-bad_move = Плохой ход 
analysis-chequerplay-bad_plus_move = Плохой+ ход 
analysis-chequerplay-error_rate = Ошибки 
analysis-chequerplay-rating = Рейтинг

analysis-luck-luck_plus_move = Удачный+ ход 
analysis-luck-luck_move = Удачный ход 
analysis-luck-unluck_plus_move = Неудачный+ ход 
analysis-luck-unluck_move = Неудачный ход 
analysis-luck-luck_rate = Удача
analysis-luck-rating = Рейтинг

analysis-cube-rating = Общ Рейтинг

analysis-overall-error_rate = Ошибка 
analysis-overall-rating = Рейтинг

waiting-think1 = Думаю. 
waiting-think2 = Думаю.. 
waiting-think3 = Думаю...

user-static-has_no_sub = Недостаточно баланса для этого сервиса, активируйте промокод или купите баланс в профиле 
user-inline-activate_promo = Промокоды
user-inline-activate_promo_2 = У меня есть промокод
user-inline-take_promo = Получить промокод

user-static-input_promo = Пожалуйста, введите промокод для активации
user-static-promo_activated = Промокод успешно активирован!
user-static-invalid_promo = Неверный промокод. Пожалуйста, проверьте и попробуйте снова.
user-static-error_processing_promo = Произошла ошибка при обработке промокода. Пожалуйста, попробуйте позже.

user-rank-superchamp = 🏆 Супер чемпион
user-rank-champ = 🥇 Чемпион
user-rank-expert = 🥈 Эксперт
user-rank-advanced = 🥉 Опытный
user-rank-intermediate = 🎓 Средний
user-rank-casual = 🎲 Ниже среднего
user-rank-beginner = 🐣 Новичок

user-profile-payment_success = ✅ Покупка пакета "{ $name }" на { $amount } анализов успешно завершена!
user-profile-payment_error = ❌ Произошла ошибка при обработке оплаты. Попробуйте позже.
user-profile-payment_not_found = ❌ Пакет не найден. Попробуйте выбрать другой.
user-profile-payment_invalid_payload = ❌ Некорректный платеж. Попробуйте ещё раз.
user-profile-payment_text = Выберите пакет для покупки:

user-profile-expire_notice = ⏳ { $amount } анализов по { $source } сгорели.

auto-analyze-download_pdf = 📄 Скачать PDF
auto-analyze-send_to_hints = 👁️ Анализ ошибок
auto-analyze-ask_hints = Хотите отправить этот файл на анализ ошибок?
auto-analyze-no_thanks = ❌ Нет, спасибо
auto-analyze-ask_pdf = Хотите ли получить анализ в формате PDF?
auto-analyze-pdf_ready = Ваш анализ в формате PDF:
auto-analyze-no_pdf = Хорошо, PDF не будет отправлен. Спасибо за использование бота!

analysis-cube-missed_doubles_below_cp = Пропущенный куб по ДП
analysis-cube-missed_doubles_above_cp = Пропущенный куб по ТГ
analysis-cube-wrong_doubles_below_sp = Ошибочный куб по ДП
analysis-cube-wrong_doubles_above_tg = Ошибочный куб по ТГ
analysis-cube-wrong_takes = Ошибочно принято кубов
analysis-cube-wrong_passes = Ошибочных пассов
analysis-cube-error_rate = Оценка ошибок
analysis-cube-rating = Оценка решений по кубу

user-static-share_phone = Поделиться телефоном
user-static-missing_contact_info = Пожалуйста, поделитесь своей контактной информацией для продолжения оплаты.
user-static-share_email = Поделиться email
user-static-contact_info_shared = Контактная информация успешно отправлена! Можете продолжать оплату.
user-static-invalid_email_format = Неверный формат email. Пожалуйста, введите корректный адрес электронной почты.

user-static-phone_request_sent = Пожалуйста, поделитесь своим номером телефона.
user-static-enter_email = Пожалуйста, введите свой email адрес, куда будем отправлять чеки об оплате.

user-static-gift = 🎁 У вас есть подарок!
    У вас есть доступ к промокоду <code>NEW</code>!
    Вы можете активировать его в <b>Профиль</b> → <b>Промокоды.</b>

auto-analyze-choose_type = Выберите тип анализа: 
auto-analyze-moneygame = Манигейм 
auto-analyze-games_match = Матч 
auto-analyze-submit_moneygame = Пожалуйста, отправьте файл манигейма для анализа. 
auto-analyze-submit_match = Пожалуйста, отправьте файл матча для анализа. 
auto-analyze-wrong_type_match = Этот файл является матчем, но вы выбрали манигейм. Пожалуйста, выберите правильный тип анализа. 
auto-analyze-wrong_type_moneygame = Этот файл является манигеймом, но вы выбрали матч. Пожалуйста, выберите правильный тип анализа.
auto-analyze-not_ebought_balance = Недостаточно баланса для этого сервиса, активируйте промокод или купите баланс в профиле 
auto-analyze-select_autoanalyze_type = Пожалуйста, выберите тип автоанализа:
auto-batch-choose_type = Пожалуйста, выберите метод загрузки для пакетного анализа: 
auto-batch-sequential = Загружать по одному 
auto-batch-zip = Загрузить ZIP-архив 
auto-batch-submit_sequential = Загружайте файлы матчей по одному. Нажмите "Прекратить загрузку" когда закончите. 
auto-batch-stop = Прекратить загрузку 
auto-batch-submit_zip = Пожалуйста, загрузите ZIP-архив с файлами матчей. 
auto-batch-invalid_zip = Некорректный файл; пожалуйста, загрузите ZIP-архив. 
auto-batch-added = Файл добавлен. Текущая очередь: { $count } 
auto-batch-no_files = Ни одного файла не загружено. Возврат в главное меню. 
auto-batch-no_valid_files = Нет валидных файлов матчей в ZIP. 
auto-batch-progress = Анализ { $current } / { $total } 
auto-batch-summary = Средние результаты из { $count } матчей: 
auto-batch-no_matches = Не найдено файлов матчей; анализ не выполнен. 
auto-batch-wrong_file = Пропущено: Не файл матча. 
auto-batch-no_data_pdf = Нет данных пакетного анализа для создания PDF.
auto-analyze-batch_type = Пакетный анализ
auto-analyze-error-balance = Недостаточно баланса для полного анализа. Пожалуйста, активируйте промокод или купите баланс в профиле.
auto-analyze-single_match = Одна игра
user-static-select_autoanalyze_type = Выберите тип анализа:
auto-batch-summary_pr_header = Игр: { $count }  
    Дата: { $date }
auto-batch-summary_pr = <b>{ $player }</b>: <b>{ $average_pr }</b>:
    ({ $pr_list })

# Pokaz page (редактор позиций) — ru
pokaz-page-title = Редактор позиции
pokaz-page-hide-pips = Скрыть пипсы
pokaz-page-lower-player = Нижний игрок:
pokaz-page-toggle-lower-player = Переключить нижнего игрока
pokaz-page-place-checkers = Установка шашек
pokaz-page-moneygame = Манигейм
pokaz-page-match = Матч
pokaz-page-checkers = Шашки
pokaz-page-white-checkers = Белые шашки
pokaz-page-black-checkers = Черные шашки
pokaz-page-on-bar = На баре
pokaz-page-jacobi-beaver-max = Якоби Бивер Макс куб
pokaz-page-yes = Да
pokaz-page-no = Нет
pokaz-page-game-type = Тип игры
pokaz-page-match-headers-lower = Очки Н.
pokaz-page-match-headers-upper = Очки В.
pokaz-page-match-headers-length = Дл. матча
pokaz-page-match-headers-max-cube = Макс куб
pokaz-page-cube-shown = Показан куб?
pokaz-page-cube = Куб
pokaz-page-whose-cube = Чей куб?
pokaz-page-crawford = Кроуфорд
pokaz-page-whose-turn = Чей ход?
pokaz-page-dice = Кубики
pokaz-page-history-back = Назад по истории
pokaz-page-history-forward = Вперёд по истории
pokaz-page-confirm-move = Подтвердить ход
pokaz-page-random-dice = Случайные кубики
pokaz-page-analyze-position = Анализ позиции
pokaz-page-collapse-table = Свернуть таблицу
pokaz-page-expand-table = Развернуть таблицу
pokaz-page-toggle-table = Свернуть/развернуть таблицу
pokaz-page-take-screenshot = Сделать скриншот
pokaz-page-save-screenshot = Сохранить скриншот в буфер
pokaz-page-upload-screenshots = Отправить скриншоты
pokaz-page-confirm = Подтверждение
pokaz-page-clear = Очистить
pokaz-page-clear-confirm-msg = Вы уверены, что хотите очистить доску?
pokaz-page-init = Расставить
pokaz-page-init-confirm-msg = Вы уверены, что хотите расставить начальную позицию?
pokaz-page-admin-comment-placeholder = Введите текст сообщения...
pokaz-page-move = Ход
pokaz-page-equity = Эквити
pokaz-page-restore-position = Восстановить сохранённую позицию
pokaz-page-next-cube = Следующий куб
pokaz-page-match-to = Матч до { $length }. Счет { $max }-{ $min }
