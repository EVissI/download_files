"""
Блоки лендинга: «Сервисы», «По шагам» и «Где играть».

Состав по умолчанию описан здесь, а не в шаблоне: админ может убирать блоки и
добавлять свои, поэтому шаблон перебирает готовый список, а не жёстко
перечисляет карточки. Ключи текстов совпадают с прежними (services-p-3 и
т.д.) - уже сохранённые правки продолжают действовать.

Раскладка (порядок, удалённые и добавленные блоки) лежит в той же таблице
landing_texts под ключами layout-services / layout-steps / layout-play.
"""

from __future__ import annotations

import re
import secrets
from typing import Any

SECTIONS = ("services", "steps", "play", "faq")
CUSTOM_ID_RE = re.compile(r"^c[0-9a-f]{8}$")
MAX_BLOCKS_PER_SECTION = 40
LAYOUT_KEY_PREFIX = "layout-"


# Секции лендинга, которые админ может переставлять. Первый экран и финальный
# призыв написать остаются на своих местах.
PAGE_SECTIONS = ("services", "steps", "guides", "faq", "play")
PAGE_LAYOUT_KEY = "layout-page"


def clean_page_order(raw: Any) -> list[str]:
    """Любой мусор превращаем в корректную перестановку PAGE_SECTIONS."""
    out: list[str] = []
    for item in raw if isinstance(raw, list) else []:
        name = str(item or "").strip()
        if name in PAGE_SECTIONS and name not in out:
            out.append(name)
    out.extend(name for name in PAGE_SECTIONS if name not in out)
    return out


def new_block_id() -> str:
    return "c" + secrets.token_hex(4)


def layout_key(section: str) -> str:
    return f"{LAYOUT_KEY_PREFIX}{section}"


# Карточки «Сервисы»: номер, заголовок, описание, ссылка.
DEFAULT_SERVICES: list[dict[str, Any]] = [
    {
        "id": "services-1",
        "num": ("services-p-3", '01'),
        "title": ("services-h3-4", 'Анализ'),
        "text": ("services-p-5", 'Загрузите протокол матча или манигейма и получите уровень игры - свой и соперника - по шкале, сопоставимой с pr в Extreme Gammon. Пакетный анализ, статистика, автоматическое сохранение результата в PDF.'),
        "link": ("services-a-6", 'Открыть «Анализ»'),
        "href": '/web/analyze',
    },
    {
        "id": "services-2",
        "num": ("services-p-7", '02'),
        "title": ("services-h3-8", 'Плеер'),
        "text": ("services-p-9", 'Просмотр сыгранной партии ход за ходом. Скриншот любого момента, чтобы переслать друзьям. Поддерживается просмотр коротких нард с 16 шашками.'),
        "link": ("services-a-10", 'Открыть «Плеер»'),
        "href": '/web/board',
    },
    {
        "id": "services-3",
        "num": ("services-p-11", '03'),
        "title": ("services-h3-12", 'Ошибки'),
        "text": ("services-p-13", 'Через 3-4 минуты после загрузки протокола - список ошибок, ваших и соперника. Можно смотреть одну сторону или все ходы, отправить непонятную позицию эксперту, перенести её в «Позицию» одной кнопкой.'),
        "link": ("services-a-14", 'Открыть «Ошибки»'),
        "href": '/web/hints',
    },
    {
        "id": "services-4",
        "num": ("services-p-15", '04'),
        "title": ("services-h3-16", 'Позиция'),
        "text": ("services-p-17", 'Расставьте любую позицию и получите анализ. Таблица лучших ходов не закрывает доску; переход по любому ходу, случайный бросок кубиков, режим «Эталон» с угадыванием лучшего хода.'),
        "link": ("services-a-18", 'Открыть «Позицию»'),
        "href": '/web/pokaz',
    },
    {
        "id": "services-5",
        "num": ("services-p-19", '05'),
        "title": ("services-h3-20", 'Карточки'),
        "text": ("services-p-21", '120 прокомментированных задач в месяц. Сортировка на решённые, сложные и избранные; случайная выборка для самопроверки; аудио-разбор; назначение карточек по темам - гонка, прайминг, холдинг, атака, обратная игра, выброс.'),
        "link": ("services-a-22", 'Открыть «Карточки»'),
        "href": '/web/cards',
    },
    {
        "id": "services-6",
        "num": ("services-p-23", '06'),
        "title": ("services-h3-24", 'Анализ матча'),
        "text": ("services-p-25", 'Разбор матча целиком: партии собраны в папки, помечены метками, к разобранным позициям можно приложить аудио-комментарий.'),
        "link": ("services-a-26", 'Открыть «Анализ матча»'),
        "href": '/web/match-analysis',
    },
    {
        "id": "services-7",
        "num": ("services-p-27", '07'),
        "title": ("services-h3-28", 'Подсчёт пипсов'),
        "text": ("services-p-29", 'Тренировка быстрого счёта пипсов и разницы пипсов в любой позиции - и решения по ходу и кубу на её основе.'),
        "link": ("services-a-30", 'Открыть «Подсчёт пипсов»'),
        "href": '/web/pip-count',
    },
    {
        "id": "services-8",
        "num": ("services-p-31", '08'),
        "title": ("services-h3-32", 'Всё о матче'),
        "text": ("services-p-33", 'Загрузили матч один раз - получили сразу всё: таблицу статистики с выгрузкой в PDF, разбор ошибок по каждому игроку и просмотр партии в плеере. Не нужно отправлять файл из сервиса в сервис и ждать дважды.'),
        "link": ("services-a-34", 'Открыть «Всё о матче»'),
        "href": '/web/match',
    },
]

# Блоки «По шагам»: подпись, заголовок, описание и пара скриншотов.
DEFAULT_STEPS: list[dict[str, Any]] = [
    {
        "id": "steps-1",
        "label": ("steps-p-3", 'ШАГ 1 · АНАЛИЗ'),
        "title": ("steps-h3-4", 'Узнали уровень игры'),
        "text": ("steps-p-5", 'Сыграли матч или серию манигеймов, загрузили протокол в «Анализ». Определили уровень соперника. Нашли партии, результат которых не устраивает, и передали их в «Ошибки».'),
        "shot": 'analyze',
        "images": ['steps-analyze-dark', 'steps-analyze-light'],
    },
    {
        "id": "steps-2",
        "label": ("steps-p-6", 'ШАГ 2 · ОШИБКИ'),
        "title": ("steps-h3-7", 'Разобрали ошибки'),
        "text": ("steps-p-8", 'Выбрали, чьи ошибки смотреть, и прошли их по очереди: почему правильный ход правильный и почему сыграли иначе. Непонятное отправили эксперту кнопкой «Комментарий», важное сохранили скриншотом.'),
        "shot": 'hints',
        "images": ['steps-hints-dark', 'steps-hints-light'],
    },
    {
        "id": "steps-3",
        "label": ("steps-p-9", 'ШАГ 3 · ПОЗИЦИЯ'),
        "title": ("steps-h3-10", 'Проработали позицию'),
        "text": ("steps-p-11", 'Перенесли позицию из «Ошибок» одной кнопкой. Поменяли положение шашек, счёт, куб и посмотрели, как меняется оценка. Особенно полезно на выбросе, при битве праймов и когда шашка на баре.'),
        "shot": 'pokaz',
        "images": ['steps-pokaz-dark', 'steps-pokaz-light'],
    },
    {
        "id": "steps-4",
        "label": ("steps-p-12", 'ШАГ 4 · ВСЁ О МАТЧЕ'),
        "title": ("steps-h3-13", 'Сделали всё за один заход'),
        "text": ("steps-p-14", 'Когда нужен сразу весь разбор, загрузите матч в «Всё о матче» - файл сам пройдёт анализ и разбор ошибок. В истории окажется готовая карточка матча: таблица с PDF, четыре режима просмотра ошибок и кнопка в плеер. Первые три шага складываются в один.'),
        "shot": 'match',
        # у этого шага пока один слот: скриншота ещё нет, показываем заглушку
        "images": ['steps-match'],
    },
]

# Карточки «Где играть».
DEFAULT_PLAY: list[dict[str, Any]] = [
    {
        "id": "play-1",
        "title": ("play-h3-3", 'PPNards'),
        "text": ("play-p-4", 'Игровая площадка для коротких нард. Протокол сыгранного матча скачивается сразу после игры.'),
        "link": ("play-a-5", 'Начать играть на PPNards →'),
        "href": 'https://app.ppn-app.ru/share/v2/club?t=1722613517&mkid=79585ae6-4c7c-4a04-8cb6-5d176db3f41e&l=ru',
    },
    {
        "id": "play-2",
        "title": ("play-h3-6", 'Приложение ФНР'),
        "text": ("play-p-7", 'Турниры Федерации нардов России. Приложение доступно в RuStore.'),
        "link": ("play-a-8", 'Установить из RuStore →'),
        "href": 'https://www.rustore.ru/catalog/app/com.khrustalnydom.fnr',
    },
]

# Вопросы и ответы. Живут на отдельной странице /web/faq, админ правит их
# там же, в обычном режиме редактирования.
DEFAULT_FAQ: list[dict[str, Any]] = [
    {
        "id": "faq-1",
        "question": ("faq-q-1", "Что нужно, чтобы начать?"),
        "answer": (
            "faq-a-1",
            "Доступ к сервисам выдаётся по логину и паролю - напишите мне в "
            "Telegram, и я всё подключу. Ничего устанавливать на компьютер не "
            "нужно: всё работает в браузере, в том числе с телефона.",
        ),
    },
    {
        "id": "faq-2",
        "question": ("faq-q-2", "Откуда взять протокол матча?"),
        "answer": (
            "faq-a-2",
            "Протокол скачивается на площадке, где вы играли: на PPNards - "
            "сразу после матча, в приложении ФНР - из истории игр. Подойдёт "
            "файл .mat, а также zip с несколькими матчами.",
        ),
    },
    {
        "id": "faq-3",
        "question": ("faq-q-3", "Сколько ждать разбор?"),
        "answer": (
            "faq-a-3",
            "Анализ матча занимает около минуты, разбор ошибок - 3-4 минуты. "
            "Страницу можно закрыть: результат появится в истории сервиса, а "
            "в браузере придёт уведомление.",
        ),
    },
]

DEFAULTS: dict[str, list[dict[str, Any]]] = {
    "services": DEFAULT_SERVICES,
    "steps": DEFAULT_STEPS,
    "play": DEFAULT_PLAY,
    "faq": DEFAULT_FAQ,
}


# Заготовки для блоков, которые админ добавляет сам.
CUSTOM_DEFAULTS: dict[str, dict[str, Any]] = {
    "services": {
        "num": ("num", ""),
        "title": ("title", "Новый сервис"),
        "text": ("text", "Коротко о том, что делает сервис."),
        "link": ("link", "Открыть"),
        "href": "/web",
    },
    "steps": {
        "label": ("label", "ШАГ"),
        "title": ("title", "Что сделали"),
        "text": ("text", "Коротко о шаге."),
    },
    "faq": {
        "question": ("q", "Новый вопрос"),
        "answer": ("a", "Ответ на вопрос."),
    },
    "play": {
        "title": ("title", "Площадка"),
        "text": ("text", "Коротко о площадке."),
        "link": ("link", "Перейти"),
        # заглушка: ведёт в никуда, пока админ не подставит адрес площадки
        "href": "#",
    },
}


def _field(key: str, default: str) -> dict[str, str]:
    return {"key": key, "default": default}


def _custom_block(section: str, block_id: str) -> dict[str, Any] | None:
    spec = CUSTOM_DEFAULTS.get(section)
    if not spec or not CUSTOM_ID_RE.match(block_id or ""):
        return None
    out: dict[str, Any] = {"id": block_id, "custom": True}
    for name, value in spec.items():
        if name == "href":
            out["href"] = value
            continue
        suffix, default = value
        out[name] = _field(f"{section}-{block_id}-{suffix}", default)
    if section == "steps":
        # у своего шага один слот под картинку вместо пары «тёмная/светлая»
        out["shot"] = block_id
        out["images"] = [f"{section}-{block_id}"]
    if "href" in out:
        out["href_key"] = out["link"]["key"]
    return out


def _default_block(section: str, raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"id": raw["id"], "custom": False}
    for name, value in raw.items():
        if name in ("id", "href", "shot", "images"):
            continue
        out[name] = _field(value[0], value[1])
    if "href" in raw:
        out["href"] = raw["href"]
        out["href_key"] = raw["link"][0]
    if "shot" in raw:
        out["shot"] = raw["shot"]
        out["images"] = list(raw.get("images") or [])
    return out


def default_ids(section: str) -> list[str]:
    return [row["id"] for row in DEFAULTS.get(section, [])]


def clean_layout(section: str, raw: Any) -> list[str] | None:
    """
    Из хранилища приходит список id блоков. Оставляем только те, что реально
    существуют: свои по формату id, штатные - по совпадению с DEFAULTS.
    """
    if not isinstance(raw, list):
        return None
    known = set(default_ids(section))
    out: list[str] = []
    seen: set[str] = set()
    for item in raw[:MAX_BLOCKS_PER_SECTION]:
        block_id = str(item or "").strip()
        if block_id in seen:
            continue
        if block_id in known or CUSTOM_ID_RE.match(block_id):
            seen.add(block_id)
            out.append(block_id)
    return out


def build_blocks(section: str, layout: list[str] | None) -> list[dict[str, Any]]:
    """
    Итоговый список блоков для шаблона. Без раскладки - всё как в коде;
    с раскладкой - её порядок и состав.
    """
    by_id = {row["id"]: row for row in DEFAULTS.get(section, [])}
    if layout is None:
        return [_default_block(section, row) for row in DEFAULTS.get(section, [])]
    out: list[dict[str, Any]] = []
    for block_id in layout:
        raw = by_id.get(block_id)
        if raw is not None:
            out.append(_default_block(section, raw))
            continue
        block = _custom_block(section, block_id)
        if block is not None:
            out.append(block)
    _number_custom_cards(section, out)
    return out


def _number_custom_cards(section: str, blocks: list[dict[str, Any]]) -> None:
    """Свой блок «Сервисов» получает следующий номер по порядку, а не пустой."""
    if section != "services":
        return
    for index, block in enumerate(blocks, 1):
        if block.get("custom"):
            block["num"]["default"] = f"{index:02d}"
