﻿
user-static-hello = Привет! Я бот для анализа. Я могу помочь вам проанализировать ваши партии в нарды и собрать статистику.

keyboard-user-reply-autoanalyze = 🔮 Автоанализ
keyboard-user-reply-profile = 🧍‍♂️ Профиль
keyboard-admin-reply-admin_panel = Админпанель

keyboard-reply-cancel = Отмена
keyboard-reply-back = Назад

keyboard-inline-change_language-ru = 🇷🇺 Русский
keyboard-inline-change_language-en = 🇺🇸 English

user-profile-change_language_text = Выберите язык для бота:
user-profile-text = 
    🧍‍♂️ <b>Профиль</b>
    ├ 🎲 Никнейм: <code>{ $player_username }</code>
    ├ 📊 Доступно игр для анализа: <b>{ $analiz_balance }</b>
    └ 🌐 Язык: <b>{ $lang_code }</b>
user-profile-inline_button-my_stats = Моя статистика
user-profile-inline_button-change_language = Изменить язык
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
    Общая статистика:
    ├ Ошибка: { $snowie_error_rate }
    └ Ваш ранг: { $detailed_rank_overall }

user-profile-no_detailed_statistics = Подробная статистика отсутствует. Пожалуйста, сыграйте больше игр для её генерации. 
user-profile-error_retrieving_statistics = Произошла ошибка при получении ваших статистических данных.

auto-analyze-submit = Отправьте .mat файл для автоматического анализа 
auto-analyze-invalid = Пожалуйста, отправьте .mat файл. 
auto-analyze-complete = Анализ файла завершен. Выберите, кем вы были: 
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

user-static-has_no_sub = У вас нет активной подписки. Пожалуйста, активируйте подписку, чтобы продолжить.
user-inline-activate_promo = Активировать промокод
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