# 🎮 Backgammon Bot - Telegram Bot с Анализом Игр

> **Полнофункциональный Telegram-бот для управления игрой в нарды (backgammon) с встроенной админ-панелью, анализом игр, системой прямых трансляций и управлением платежами.**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-latest-336791.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-✓-blue.svg)](https://www.docker.com/)

---

## 📋 Содержание

- [Функциональность](#-функциональность)
- [Требования](#-требования)
- [Установка](#-установка)
- [Конфигурация](#-конфигурация)
- [Запуск](#-запуск)
- [Архитектура](#-архитектура)
- [API документация](#-api-документация)
- [Команды управления](#-команды-управления)
- [Структура проекта](#-структура-проекта)
- [Разработка](#-разработка)
- [Решение проблем](#-решение-проблем)

---

## ✨ Функциональность

### 🤖 Telegram Bot (aiogram 3.21)
- ✅ **Интерактивные inline-кнопки** с состояниями (FSM)
- ✅ **Многоязычность** - поддержка EN, RU (i18n с Fluentogram)
- ✅ **Профиль пользователя** - личный кабинет с статистикой
- ✅ **Система промокодов** - активация и управление
- ✅ **Платежная система** - интеграция с ЮKassa
- ✅ **Анализ игр** - парсинг и сохранение анализов
- ✅ **Прямые трансляции** - управление трансляциями игр
- ✅ **История платежей** - отслеживание всех операций
- ✅ **Подсказки** - интегрированный помощник

### 📊 Админ-панель (Flask-AppBuilder)
- ✅ **CRUD операции** над всеми сущностями
- ✅ **Управление пользователями** - роли и права доступа
- ✅ **Управление промокодами** - создание и отслеживание
- ✅ **Редактирование платежей** - управление тарифами
- ✅ **Настройка рассылок** - сообщения для новых пользователей
- ✅ **Поиск и фильтрация** - быстрый доступ к данным
- ✅ **Экспорт в CSV** - выгрузка данных

### 🔧 Backend API (FastAPI)
- ✅ **REST API** для фронтенда
- ✅ **Интеграция Syncthing** - синхронизация файлов
- ✅ **Загрузка файлов** - MAT-файлы с анализами
- ✅ **Кеширование Redis** - оптимизация производительности
- ✅ **Асинхронная обработка** - APScheduler для задач

### 🗄️ База данных (PostgreSQL + SQLAlchemy)
- ✅ **ORM модели** - типобезопасная работа с БД
- ✅ **Миграции** - Alembic для версионирования
- ✅ **Кешированые данные** - Redis для сессий и кеша
- ✅ **Async SQL** - asyncpg для асинхронности

---

## 🛠️ Требования

### Минимум:
- **Python:** 3.8+
- **Docker & Docker Compose:** последняя версия
- **Git:** для клонирования репозитория

### Программное обеспечение:
- **PostgreSQL:** 12+
- **Redis:** 6+
- **Tesseract OCR** (опционально, для распознавания текста)

### Токены и ключи (необходимо получить):
1. **BOT_TOKEN** - от [@BotFather](https://t.me/botfather) в Telegram
2. **YA_API_TOKEN** - от [Яндекс API](https://yandex.cloud/)
3. **YO_KASSA_TEL_API_KEY** - от [ЮKassa](https://kassa.yandex.ru/)
4. **SYNCTHING_API_KEY** - от своего сервера Syncthing

---

## 🚀 Установка

### 1️⃣ Клонирование репозитория

```bash
git clone <repository-url>
cd download_files
```

### 2️⃣ Создание файла переменных окружения

```bash
cp .env.example .env
```

Отредактируйте `.env`:

```bash
# === TELEGRAM BOT ===
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
CHAT_GROUP_ID=YOUR_TELEGRAM_GROUP_ID
ROOT_ADMIN_IDS=[YOUR_USER_ID]
MINI_APP_URL=https://your-domain.com

# === API ИНТЕГРАЦИИ ===
YA_API_TOKEN=your_yandex_token
YO_KASSA_TEL_API_KEY=your_yokassa_key
SYNCTHING_API_KEY=your_syncthing_key
SYNCTHING_HOST=localhost:8384

# === БД И КЕШИРОВАНИЕ ===
POSTGRES_USER=backgammon
POSTGRES_PASSWORD=super_secure_password
POSTGRES_DB=backgammon

REDIS_PASSWORD=redis_password
REDIS_USER_PASSWORD=redis_user_password

# === АДМИН-ПАНЕЛЬ ===
SECRET_KEY=your-very-long-random-secret-key-min-32-chars
```

### 3️⃣ Установка зависимостей (без Docker)

```bash
# Создать виртуальное окружение
python -m venv venv

# Активировать (Windows)
venv\Scripts\activate

# Активировать (Linux/Mac)
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt
```

---

## ⚙️ Конфигурация

### Файл конфигурации: [bot/config.py](bot/config.py)

Все переменные читаются из `.env` файла через Pydantic Settings:

```python
class Settings(BaseSettings):
    # Telegram Bot
    BOT_TOKEN: str
    CHAT_GROUP_ID: int
    ROOT_ADMIN_IDS: List[int]
    
    # API
    YA_API_TOKEN: str
    YO_KASSA_TEL_API_KEY: str
    
    # Syncthing
    SYNCTHING_API_KEY: str
    SYNCTHING_FOLDER: str = 'backgammon-files'
    
    # База данных
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str = 'backgammon'
    
    # Redis
    REDIS_PASSWORD: str
    REDIS_HOST: str = 'redis'
    REDIS_PORT: int = 6379
    
    # Admin Panel
    SECRET_KEY: str

## 🏃 Запуск

### Вариант 1️⃣: Docker Compose (рекомендуется)

```bash
# Запуск всех сервисов
docker-compose up -d

# Запуск только бота
docker-compose up backgammon-bot

# Запуск только админ-панели
docker-compose up admin-panel

# Просмотр логов
docker-compose logs -f backgammon-bot

# Остановка
docker-compose down
```

### Вариант 2️⃣: Локальный запуск

```bash
# Убедитесь, что PostgreSQL и Redis запущены

# Применить миграции
alembic upgrade head

# Запустить бота
python -m bot.init

# Запустить админ-панель (отдельный терминал)
python -m bot.flask_admin.appbuilder_main

# Запустить API (отдельный терминал)
uvicorn bot.api:app --reload --host 0.0.0.0 --port 8000
```

### 📍 Доступные адреса:

| Сервис | URL | Описание |
|--------|-----|---------|
| 🤖 Telegram Bot | [t.me/backgammon_bot](https://t.me/backgammon_bot) | Основной бот |
| 📊 Админ-панель | http://localhost:5000 | Flask-AppBuilder |
| 🔌 API | http://localhost:8000 | FastAPI docs |
| 🔴 Redis | localhost:6379 | Кеширование |
| 🐘 PostgreSQL | localhost:5432 | База данных |

---

## 🏗️ Архитектура

### 📦 Слоистая архитектура

```
┌─────────────────────────────────────────┐
│         Telegram Bot (aiogram)          │  ← Пользовательский интерфейс
└─────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────────┐
│  Routers + Handlers + Middlewares + FSM States  │  ← Бизнес-логика
└──────────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────────┐
│  Services (DAOs) + Database Models (SQLAlchemy)  │  ← Data Access Layer
└──────────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────────┐
│   PostgreSQL Database + Redis Cache              │  ← Persistence
└──────────────────────────────────────────────────┘
```

### 🔄 Основные компоненты:

| Компонент | Назначение | Технология |
|-----------|-----------|-----------|
| **Bot** | Основной бот | aiogram 3.21 |
| **API** | REST API | FastAPI |
| **Admin** | Управление данными | Flask-AppBuilder |
| **Database** | Хранение данных | PostgreSQL + SQLAlchemy |
| **Cache** | Кешировка сессий | Redis |
| **Scheduler** | Фоновые задачи | APScheduler |
| **i18n** | Многоязычность | Fluentogram |

---

## 📚 API Документация

### FastAPI Docs:
```
http://localhost:8000/docs
```

### Основные эндпоинты:

#### 📥 Загрузка файлов
```http
POST /api/upload
Content-Type: multipart/form-data

user_id: int
file: file (MAT-файл)
```

#### 📊 Получение анализа
```http
GET /api/analysis/{analysis_id}
```

#### 🎬 Управление трансляциями
```http
GET /api/broadcasts
POST /api/broadcasts
PUT /api/broadcasts/{id}
DELETE /api/broadcasts/{id}
```

**Полная документация в Swagger:** http://localhost:8000/docs

---

## 🎯 Команды управления

### Общие команды

| Команда | Описание |
|---------|---------|
| `/start` | Начать работу с ботом |
| `/profile` | Открыть профиль |
| `/help` | Справка |
| `/settings` | Настройки аккаунта |

### Админ-команды (только для администраторов)

| Команда | Описание |
|---------|---------|
| `/admin` | Админ-меню |
| `/broadcast` | Отправить рассылку |
| `/cleanup` | Очистить скриншоты |

### Миграции БД

```bash
# Создать новую миграцию
alembic revision --autogenerate -m "описание изменений"

# Применить все миграции
alembic upgrade head

# Откатить последнюю миграцию
alembic downgrade -1

# Показать текущую версию
alembic current
```

### i18n Команды

```bash
# Обновить переводы
fluentogram -f bot/locales/en/LC_MESSAGES/txt.ftl -o bot/locales/stub.pyi

# Добавить новый язык
# 1. Создать папку: bot/locales/[lang_code]/LC_MESSAGES/
# 2. Скопировать .ftl файлы
# 3. Обновить config.py
```

---

## 📁 Структура проекта

```
download_files/
├── 📄 README.md                          # Это файл
├── 📄 ADMIN_PANEL_GUIDE.md               # Гайд по админ-панели
├── 📄 requirements.txt                   # Зависимости Python
├── 📄 docker-compose.yml                 # Docker Compose конфигурация
├── 📄 dockerfile                         # Docker образ
├── 📄 .env.example                       # Пример переменных окружения
│
├── 🤖 bot/                               # Основной модуль бота
│   ├── api.py                            # FastAPI приложение
│   ├── config.py                         # Конфигурация
│   ├── init.py                           # Инициализация бота
│   │
│   ├── 📂 common/                        # Общие утилиты
│   │   ├── general_states.py             # FSM состояния
│   │   ├── texts.py                      # Текстовые сообщения
│   │   ├── filters/                      # Фильтры (роль, пользователь)
│   │   ├── func/                         # Бизнес-функции
│   │   │   ├── analiz_func.py
│   │   │   ├── excel_generate.py
│   │   │   ├── game_parser.py
│   │   │   ├── generate_pdf.py
│   │   │   └── ...
│   │   ├── kbds/                         # Клавиатуры
│   │   │   ├── inline/                   # Inline-кнопки
│   │   │   └── markup/                   # Обычные кнопки
│   │   ├── middlewares/                  # Middleware (auth, i18n, db)
│   │   ├── tasks/                        # Фоновые задачи
│   │   └── utils/                        # Утилиты (notify, i18n)
│   │
│   ├── 📂 routers/                       # Обработчики команд
│   │   ├── start.py                      # /start команда
│   │   ├── profile.py                    # Профиль пользователя
│   │   ├── payment.py                    # Платежи
│   │   ├── contact_info.py               # Контакты
│   │   ├── download_flie.py              # Загрузка файлов
│   │   ├── activate_promo.py             # Промокоды
│   │   ├── admin/                        # Админ команды
│   │   └── ...
│   │
│   ├── 📂 db/                            # База данных
│   │   ├── models.py                     # SQLAlchemy модели
│   │   ├── schemas.py                    # Pydantic схемы
│   │   ├── dao.py                        # Data Access Objects
│   │   ├── database.py                   # Конфигурация БД
│   │   ├── pg_backup.py                  # Резервная копия
│   │   └── redis.py                      # Redis клиент
│   │
│   ├── 📂 flask-admin/                   # Админ-панель
│   │   ├── appbuilder_main.py            # Flask-AppBuilder (рекомендуется)
│   │   └── main.py                       # Flask-Admin (старая версия)
│   │
│   ├── 📂 migration/                     # Alembic миграции
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/                     # Миграции
│   │
│   ├── 📂 locales/                       # Переводы (i18n)
│   │   ├── en/LC_MESSAGES/
│   │   └── ru/LC_MESSAGES/
│   │
│   ├── 📂 static/                        # Статические файлы
│   └── 📂 templates/                     # HTML шаблоны
│
├── 📂 files/                             # Загруженные файлы
│   └── [user_id]/                        # Папки пользователей
│
├── 📂 log/                               # Логи приложения
│   ├── log_bot.txt
│   └── log_bot_error.txt
│
├── 📂 temp/                              # Временные файлы
│
└── 📂 redisdata/                         # Данные Redis

```

---

## 👨‍💻 Разработка

### Установка для разработки

```bash
# Активировать виртуальное окружение
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установить зависимости для разработки
pip install -r requirements.txt
pip install pytest pytest-asyncio black flake8 mypy

# Предварительные проверки кода
black bot/
flake8 bot/
mypy bot/
```

### Добавление новой команды

1. **Создать файл маршрута:** `bot/routers/my_command.py`
```python
from aiogram import Router, types
from aiogram.filters import Command

router = Router()

@router.message(Command("mycommand"))
async def my_command(message: types.Message):
    await message.answer("Hello!")
```

2. **Зарегистрировать в `bot/init.py`:**
```python
from bot.routers.my_command import router as my_command_router
# ...
dp.include_router(my_command_router)
```

### Добавление новой модели БД

1. **Создать модель в `bot/db/models.py`:**
```python
from bot.db.database import Base

class MyModel(Base):
    __tablename__ = "my_table"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
```

2. **Создать миграцию:**
```bash
alembic revision --autogenerate -m "add my_model"
alembic upgrade head
```

3. **Создать DAO в `bot/db/dao.py`:**
```python
class MyModelDAO:
    def __init__(self, session):
        self.session = session
    
    async def get_by_id(self, id: int):
        return await self.session.get(MyModel, id)
```

---

## 🐛 Решение проблем

### ❌ "Connection refused" при запуске

**Проблема:** БД или Redis не доступны

```bash
# Проверить статус контейнеров
docker-compose ps

# Перезагрузить контейнеры
docker-compose down && docker-compose up -d
```

### ❌ "ModuleNotFoundError: No module named 'bot'"

**Проблема:** Python не находит модуль bot

```bash
# Убедиться, что вы в корневой директории проекта
pwd  # Должен быть путь к download_files/

# Добавить текущую папку в PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"  # Linux/Mac
set PYTHONPATH=%PYTHONPATH%;%cd%  # Windows
```

### ❌ "401 Unauthorized" в админ-панели

**Проблема:** Неверные учетные данные

1. Стандартные учетные данные: `admin/admin`
2. Смотреть логи: `docker logs admin_panel`
3. Пересоздать админа (удалить БД и перезагрузить)

### ❌ "CSRF token missing" ошибки

**Проблема:** Проблемы с сессией

```bash
# Очистить cookies браузера
# Или перезагрузить контейнер
docker-compose restart admin-panel
```

### ❌ Бот не отвечает на команды

**Проблема:** BOT_TOKEN неверный или бот не запущен

```bash
# Проверить логи бота
docker-compose logs backgammon-bot

# Проверить токен в .env
grep BOT_TOKEN .env

# Перезагрузить бота
docker-compose restart backgammon-bot
```

### ❌ Ошибка миграции БД

**Проблема:** Неправильная версия миграции

```bash
# Откатить на шаг назад
alembic downgrade -1

# Просмотреть историю
alembic history

# Откатить на конкретную версию
alembic downgrade abc123def456
```

---

## 📚 Дополнительные ресурсы

### Документация:
- [aiogram Documentation](https://docs.aiogram.dev/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Flask-AppBuilder Documentation](https://flask-appbuilder.readthedocs.io/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/en/20/orm/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)

### Смежные проекты:
- [Admin Panel Guide](ADMIN_PANEL_GUIDE.md) - Подробный гайд по админ-панели
- [Bot Config](bot/config.py) - Файл конфигурации

### Примеры:
- **Обработчик команды:** [bot/routers/start.py](bot/routers/start.py)
- **Модель БД:** [bot/db/models.py](bot/db/models.py)
- **API эндпоинт:** [bot/api.py](bot/api.py)

---

## 📞 Поддержка и контакты

### Логирование:
- **Логи бота:** `log/log_bot.txt`
- **Ошибки бота:** `log/log_bot_error.txt`
- **Docker логи:** `docker-compose logs [service]`

### Ошибки:
1. **Проверить логи** первым делом
2. **Убедиться в конфигурации** (.env файл)
3. **Перезагрузить контейнеры**
4. **Очистить БД и перезапустить** (последний вариант)

---

## 📝 Лицензия

**Все права защищены.** Для использования получите разрешение автора.

---

