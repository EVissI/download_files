# 🏗️ Архитектура Backgammon Bot

> **Полное описание архитектуры, дизайна и потока данных приложения**

---

## 📊 Общая архитектура

```
┌──────────────────────────────────────────────────────────────────┐
│                        ПОЛЬЗОВАТЕЛИ                              │
│     (Telegram Bot, Web Frontend, Admin Panel)                    │
└────────┬─────────────────────────────────────────────────────────┘
         │
         │ Telegram API / HTTP
         ▼
┌──────────────────────────────────────────────────────────────────┐
│                     APPLICATION LAYER                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │           TELEGRAM BOT (aiogram 3.21)                      │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │ Routers: start, profile, payment, admin, etc.       │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │ Middlewares: auth, i18n, db, contact_info, sub      │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │ FSM States: payments, contact_info, admin, etc.     │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │         ADMIN PANEL (Flask-AppBuilder)                     │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │ CRUD Views: Users, Promos, Payments, etc.           │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │         WEB API (FastAPI)                                  │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │ Endpoints: upload, analysis, broadcasts, etc.       │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└────────┬─────────────────────────────────────────────────────────┘
         │ SQL / Redis / File I/O
         ▼
┌──────────────────────────────────────────────────────────────────┐
│                    DATA PERSISTENCE LAYER                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │   PostgreSQL     │  │   Redis Cache    │  │  File System │  │
│  │   (Main DB)      │  │  (Sessions)      │  │  (Uploads)   │  │
│  │                  │  │  (Caching)       │  │  (Backups)   │  │
│  └──────────────────┘  └──────────────────┘  └──────────────┘  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Поток данных

### 1. Telegram Bot Workflow

```
User Message
    ↓
Telegram API → Dispatcher (aiogram)
    ↓
Middlewares:
  - Single User Middleware (проверка блокировки)
  - Database Middleware (инициализация DAOs)
  - I18n Middleware (установка языка)
  - Contact Info Middleware (получение контакта)
  - Subscription Middleware (проверка подписки)
    ↓
Filters:
  - Role Filter (проверка роли админа)
  - User Info Filter (получение инфо о пользователе)
    ↓
Handler (Router)
    ↓
Service Layer (DAOs, Functions)
    ↓
Database / Cache Operations
    ↓
Response → Telegram Bot API
    ↓
User receives message
```

### 2. Admin Panel Workflow

```
Admin opens URL (localhost:5000)
    ↓
Flask-AppBuilder routes request
    ↓
Authentication check (session validation)
    ↓
Authorization check (role-based access)
    ↓
ModelView processes request (CRUD operation)
    ↓
SQLAlchemy ORM query
    ↓
PostgreSQL database
    ↓
Response rendered to HTML
    ↓
Admin sees updated data
```

### 3. API Workflow

```
Frontend/Client HTTP Request
    ↓
FastAPI route handler
    ↓
Request validation (Pydantic)
    ↓
Authentication/Authorization
    ↓
Business logic
    ↓
Database operations (async)
    ↓
Response serialization (JSON)
    ↓
Response sent to client
```

---

## 📁 Модульная структура

### 🤖 Bot Module (`bot/`)

```
bot/
├── init.py                    # Инициализация бота
│   ├── Создает Dispatcher
│   ├── Регистрирует роутеры
│   ├── Регистрирует middleware
│   ├── Применяет миграции БД
│   └── Запускает polling
│
├── api.py                     # FastAPI приложение
│   ├── Инициализирует FastAPI
│   ├── Подключает роутеры
│   ├── Монтирует статические файлы
│   └── Запускает сервер
│
├── config.py                  # Конфигурация
│   ├── Settings (Pydantic)
│   ├── Переменные окружения
│   ├── Database URL
│   ├── Redis URL
│   └── Logger настройка
│
├── common/                    # Общие утилиты
│   ├── general_states.py      # FSM состояния для всех роутеров
│   ├── texts.py               # Сообщения (i18n)
│   ├── filters/               # Фильтры сообщений
│   │   ├── role_filter.py     # Проверка роли (админ/юзер)
│   │   └── user_info.py       # Получение инфо о пользователе
│   ├── func/                  # Бизнес-функции
│   │   ├── analiz_func.py     # Анализ игр
│   │   ├── excel_generate.py  # Генерация Excel
│   │   ├── game_parser.py     # Парсинг игр
│   │   ├── generate_pdf.py    # Генерация PDF
│   │   ├── progress_bar.py    # Progress bar в сообщениях
│   │   ├── validators.py      # Валидация данных
│   │   ├── waiting_message.py # Ожидающие сообщения
│   │   ├── yadisk.py          # Интеграция Яндекс.Диск
│   │   ├── hint_viewer.py     # Отображение подсказок
│   │   └── aps_sheldure.py    # APScheduler интеграция
│   ├── kbds/                  # Клавиатуры
│   │   ├── inline/            # Inline-кнопки (callback)
│   │   └── markup/            # Обычные кнопки (reply)
│   ├── middlewares/           # ASGI Middlewares
│   │   ├── contact_info.py    # Запрос контакта при необходимости
│   │   ├── database_middleware.py  # Инициализация DAOs
│   │   ├── i18n.py            # Установка языка пользователя
│   │   ├── single_user_middleware.py  # Проверка блокировки
│   │   └── sub_middleware.py   # Проверка подписки на канал
│   ├── tasks/                 # Фоновые задачи (celery/rq)
│   │   ├── cleanup_screenshots.py  # Удаление старых скриншотов
│   │   ├── deactivate.py      # Деактивация промокодов
│   │   ├── gift.py            # Распределение подарков
│   │   └── __init__.py
│   ├── service/               # Сервисы
│   │   └── sync_folder_service.py  # Syncthing синхронизация
│   └── utils/                 # Утилиты
│       ├── i18n.py            # i18n функции
│       └── notify.py          # Отправка уведомлений
│
├── routers/                   # Обработчики команд (роутеры)
│   ├── start.py               # /start команда (главное меню)
│   ├── profile.py             # Профиль пользователя
│   ├── payment.py             # Обработка платежей
│   ├── contact_info.py        # Сбор контактной информации
│   ├── download_flie.py       # Загрузка MAT-файлов
│   ├── activate_promo.py      # Активация промокодов
│   ├── hint_viewer_router.py  # Просмотр подсказок
│   ├── short_board.py         # Короткая доска (игра)
│   ├── stat.py                # Статистика пользователя
│   ├── setup.py               # Настройки аккаунта
│   └── admin/                 # Админ-команды
│       ├── answer.py          # Ответ на сообщение пользователя
│       ├── analyze.py         # Запуск анализа
│       ├── broadcast.py       # Отправка рассылки
│       └── ...
│
├── db/                        # База данных (SQLAlchemy)
│   ├── models.py              # ORM модели
│   │   ├── User               # Пользователь
│   │   ├── UserGroup          # Группа пользователей
│   │   ├── UserInGroup        # Связь пользователя с группой
│   │   ├── Promocode          # Промокод
│   │   ├── UserPromocode      # Использованный промокод
│   │   ├── AnalizePayment     # Тариф анализа
│   │   ├── UserAnalizePayment # Платеж пользователя
│   │   ├── Analysis           # Анализ игры
│   │   ├── Broadcast          # Прямая трансляция
│   │   └── ... (еще модели)
│   ├── schemas.py             # Pydantic schemas (валидация)
│   ├── dao.py                 # Data Access Objects (CRUD)
│   │   ├── UserDAO
│   │   ├── PromocodeDAO
│   │   ├── PaymentDAO
│   │   └── ...
│   ├── database.py            # Инициализация БД
│   │   ├── Base (declarative base)
│   │   ├── get_async_session (async context manager)
│   │   └── AsyncSessionLocal
│   ├── redis.py               # Redis клиент
│   ├── pg_backup.py           # Резервная копия PostgreSQL
│   ├── custom_comparators.py  # Кастомные SQLAlchemy comparators
│   └── mock.py                # Mock данные для тестирования
│
├── flask-admin/               # Админ-панель (Flask-AppBuilder)
│   ├── appbuilder_main.py     # Основной файл (рекомендуется)
│   │   ├── create_app()       # Создание Flask-AppBuilder приложения
│   │   ├── register_models()  # Регистрация моделей
│   │   └── ModelView классы   # CRUD представления
│   ├── main.py                # Flask-Admin (старая версия)
│   └── __init__.py            # Экспорт функций
│
├── migration/                 # Alembic миграции
│   ├── env.py                 # Конфигурация Alembic
│   ├── script.py.mako         # Шаблон миграции
│   └── versions/              # Файлы миграций
│       ├── 001_initial_schema.py
│       ├── 002_add_new_table.py
│       └── ...
│
├── locales/                   # Интернационализация (i18n)
│   ├── stub.pyi               # Type hints для переводов
│   ├── en/                    # Английский
│   │   └── LC_MESSAGES/
│   │       ├── txt.ftl        # Fluent файл (переводы)
│   │       └── messages.po    # Gettext файл
│   └── ru/                    # Русский
│       └── LC_MESSAGES/
│           └── txt.ftl
│
├── static/                    # Статические файлы (CSS, JS, images)
│   ├── css/
│   ├── js/
│   └── images/
│
└── templates/                 # HTML шаблоны
    ├── base.html
    ├── board_viewer.html
    ├── hint_viewer.html
    └── ...
```

---

## 🔌 Интеграции

### Telegram API
- **Библиотека:** aiogram 3.21
- **Использование:** Отправка/получение сообщений
- **Вызовы:** Из любого роутера/хэндлера

### PostgreSQL
- **Драйвер:** asyncpg
- **ORM:** SQLAlchemy 2.0
- **Использование:** Хранение всех данных
- **Вызовы:** Через DAOs в `bot/db/dao.py`

### Redis
- **Клиент:** redis-py
- **Использование:** Кеширование, сессии, RQ queue
- **Вызовы:** Через `bot/db/redis.py`

### Яндекс API
- **Использование:** Облачные сервисы Яндекса
- **Где:** `bot/common/func/yadisk.py`

### ЮKassa
- **Использование:** Обработка платежей
- **Где:** `bot/routers/payment.py`

### Syncthing
- **Использование:** Синхронизация файлов между серверами
- **Где:** `bot/common/service/sync_folder_service.py`

### APScheduler
- **Использование:** Планирование фоновых задач
- **Где:** `bot/common/func/aps_sheldure.py`

---

## 🔐 Безопасность и аутентификация

### Telegram Bot
```
User Message
    ↓
Verify chat_id matches registered user
    ↓
Check if user is blocked/banned
    ↓
Process request
```

### Admin Panel
```
Login Form
    ↓
Hash password (werkzeug.security)
    ↓
Verify against user in DB
    ↓
Create Flask session
    ↓
Store user role in session
    ↓
CSRF token validation on every form
    ↓
Role-based access control (ModelView.can_*)
```

### API
```
Request with token/API key
    ↓
Verify token signature
    ↓
Get user from token
    ↓
Check endpoint permissions
    ↓
Process request
```

---

## 📊 Схема БД (упрощено)

```
users
├── id (PK)
├── username
├── email
├── role (enum: user/admin)
├── lang_code (en/ru)
└── ...relationships...

user_groups
├── id (PK)
├── name
└── ...

user_in_group
├── id (PK)
├── user_id (FK)
└── group_id (FK)

promocodes
├── id (PK)
├── code (UNIQUE)
├── is_active
├── max_usage
├── activate_count
└── ...

user_promocodes
├── id (PK)
├── user_id (FK)
├── promocode_id (FK)
└── is_active

analize_payments
├── id (PK)
├── name
├── price
├── duration_days
└── ...

user_analize_payments
├── id (PK)
├── user_id (FK)
├── analize_payment_id (FK)
├── transaction_id
└── ...

broadcasts
├── id (PK)
├── user_id (FK)
├── title
├── description
└── ...

... и другие таблицы
```

---

## 🔄 Паттерны проектирования

### 1. **Middleware Pattern**
```python
# bot/common/middlewares/
class MyMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        # Выполнить до хэндлера
        result = await handler(event, data)
        # Выполнить после хэндлера
        return result
```

### 2. **Router/Handler Pattern**
```python
# bot/routers/my_command.py
router = Router()

@router.message(Command("mycommand"))
async def handle_command(message: Message, ...):
    # Обработать команду
    pass
```

### 3. **DAO Pattern**
```python
# bot/db/dao.py
class UserDAO:
    def __init__(self, session):
        self.session = session
    
    async def get_by_id(self, user_id):
        # SELECT * FROM users WHERE id = user_id
        return await self.session.get(User, user_id)
```

### 4. **Service Pattern**
```python
# bot/common/func/my_service.py
class MyService:
    def __init__(self, dao: MyDAO):
        self.dao = dao
    
    async def do_something(self):
        # Сложная бизнес-логика
        pass
```

### 5. **FSM (Finite State Machine)**
```python
# bot/common/general_states.py
class MyForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_email = State()

# bot/routers/my_router.py
@router.message(MyForm.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(MyForm.waiting_for_email)
```

---

## 🚀 Оптимизация

### Database:
- ✅ **Async queries** (asyncpg)
- ✅ **Connection pooling**
- ✅ **Indexes** на часто запрашиваемые поля
- ✅ **Lazy loading** отношений

### Cache:
- ✅ **Redis** для часто используемых данных
- ✅ **TTL** на кеш записи

### API:
- ✅ **Pagination** на больших результатах
- ✅ **Compression** (gzip)
- ✅ **Rate limiting**

### Bot:
- ✅ **Batch processing** сообщений
- ✅ **Message queues** для обработки

---

## 🧪 Тестирование

### Unit Tests
```python
# tests/test_dao.py
async def test_get_user_by_id():
    dao = UserDAO(session)
    user = await dao.get_by_id(1)
    assert user.id == 1
```

### Integration Tests
```python
# tests/test_bot_handler.py
async def test_start_command():
    # Отправить /start команду
    # Проверить ответ
    pass
```

### Load Tests
```bash
# tests/load_test.py
locust -f load_test.py --host=http://localhost:8000
```

---

## 📈 Масштабируемость

### Текущая архитектура поддерживает:
- ✅ **Горизонтальное масштабирование** (multiple workers)
- ✅ **Async IO** (не блокирует на I/O операциях)
- ✅ **Connection pooling** (эффективное использование БД)
- ✅ **Кеширование** (Redis)


---

## 📚 Дополнительно

- **[README.md](README.md)** - Общая документация
- **[QUICKSTART.md](QUICKSTART.md)** - Быстрый старт
- **[ADMIN_PANEL_GUIDE.md](ADMIN_PANEL_GUIDE.md)** - Админ-панель

---
