# 🤝 Contributing Guide

> **Руководство по разработке и контрибьютингу в проект Backgammon Bot**

---

## 📋 Содержание

- [Требования к разработчикам](#-требования-к-разработчикам)
- [Установка окружения](#-установка-окружения)
- [Структура проекта](#-структура-проекта)
- [Написание кода](#-написание-кода)
- [Тестирование](#-тестирование)
- [Git рабочий процесс](#-git-рабочий-процесс)
- [Code Review](#-code-review)
- [Нейминг соглашения](#-нейминг-соглашения)

---

## 🛠️ Требования к разработчикам

### Обязательные знания:
- ✅ Python 3.8+ и асинхронное программирование
- ✅ SQL (PostgreSQL)
- ✅ Git и GitHub
- ✅ REST API и HTTP протокол

### Желательные знания:
- ✅ aiogram 3.x (Telegram Bot Framework)
- ✅ FastAPI
- ✅ SQLAlchemy ORM
- ✅ Docker и Docker Compose
- ✅ Linux/MacOS (или WSL2 для Windows)

### Инструменты:
- ✅ IDE: VS Code, PyCharm или другой
- ✅ Git client
- ✅ Docker Desktop
- ✅ Postman (опционально, для тестирования API)

---

## 💻 Установка окружения

### 1️⃣ Клонирование репозитория

```bash
git clone <repository-url>
cd download_files
git checkout develop  # Работать от develop ветки
```

### 2️⃣ Создание виртуального окружения

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3️⃣ Установка зависимостей

```bash
pip install -r requirements.txt

# Установить dev зависимости
pip install pytest pytest-asyncio black flake8 mypy isort
```

### 4️⃣ Конфигурация

```bash
cp .env.example .env
# Отредактировать .env с вашими данными
```

### 5️⃣ Запуск Docker сервисов

```bash
# Только БД и Redis (без самого приложения)
docker-compose up -d db redis

# Применить миграции
alembic upgrade head
```

### 6️⃣ Запуск приложения

```bash
# Терминал 1: Бот
python -m bot.init

# Терминал 2: API
uvicorn bot.api:app --reload

# Терминал 3: Админ-панель
python -m bot.flask_admin.appbuilder_main
```

---

## 📁 Структура проекта для разработчиков

```
bot/
├── routers/              # ← Добавляйте новые команды здесь
│   └── my_new_feature.py # Новый файл с роутерами
│
├── common/
│   ├── func/            # ← Добавляйте бизнес-логику здесь
│   │   └── my_service.py # Новый сервис
│   │
│   ├── kbds/            # ← Добавляйте кнопки здесь
│   │   └── inline/my_buttons.py
│   │
│   └── general_states.py # ← Добавляйте FSM состояния здесь
│
├── db/
│   ├── models.py        # ← Добавляйте новые модели здесь
│   └── dao.py           # ← Добавляйте DAOs здесь
│
└── migration/           # ← Миграции создаются автоматически
    └── versions/
```

---

## ✍️ Написание кода

### 1. Новый Telegram Router

**Файл:** `bot/routers/my_feature.py`

```python
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Инициализация роутера
router = Router()

# Обработчик команды
@router.message(Command("mycommand"))
async def my_command(message: types.Message):
    """Описание команды"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Кнопка 1", callback_data="action_1")],
            [InlineKeyboardButton(text="Кнопка 2", callback_data="action_2")],
        ]
    )
    
    await message.answer(
        text="Выберите действие:",
        reply_markup=keyboard
    )

# Обработчик callback
@router.callback_query(lambda c: c.data == "action_1")
async def handle_action_1(callback: types.CallbackQuery):
    await callback.message.edit_text("Вы выбрали действие 1")
    await callback.answer("✅ Готово!")
```

**Регистрация в `bot/init.py`:**

```python
from bot.routers.my_feature import router as my_feature_router

# ...в функции создания dispatcher...
dp.include_router(my_feature_router)
```

### 2. Добавление FSM состояния

**Файл:** `bot/common/general_states.py`

```python
from aiogram.fsm.state import State, StatesGroup

class MyFeatureStates(StatesGroup):
    """Состояния для моей фичи"""
    waiting_for_input = State()
    confirming_action = State()
    processing = State()
```

**Использование в роутере:**

```python
@router.message(MyFeatureStates.waiting_for_input)
async def handle_input(message: types.Message, state: FSMContext):
    await state.update_data(user_input=message.text)
    await state.set_state(MyFeatureStates.confirming_action)
    await message.answer("Подтвердить?")
```

### 3. Добавление новой модели БД

**Файл:** `bot/db/models.py`

```python
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, ForeignKey
from bot.db.database import Base

class MyModel(Base):
    __tablename__ = "my_table"
    
    # Поля
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    
    # Отношения
    user: Mapped["User"] = relationship("User", back_populates="my_models")
```

**Создание миграции:**

```bash
alembic revision --autogenerate -m "add my_model table"
alembic upgrade head
```

### 4. Добавление DAO

**Файл:** `bot/db/dao.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.select import select
from bot.db.models import MyModel

class MyModelDAO:
    """Data Access Object для MyModel"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, name: str, description: str, user_id: int) -> MyModel:
        """Создать новую запись"""
        obj = MyModel(name=name, description=description, user_id=user_id)
        self.session.add(obj)
        await self.session.commit()
        return obj
    
    async def get_by_id(self, id: int) -> MyModel | None:
        """Получить по ID"""
        return await self.session.get(MyModel, id)
    
    async def get_all(self) -> list[MyModel]:
        """Получить все записи"""
        result = await self.session.execute(select(MyModel))
        return result.scalars().all()
    
    async def update(self, id: int, **kwargs) -> MyModel | None:
        """Обновить запись"""
        obj = await self.get_by_id(id)
        if not obj:
            return None
        
        for key, value in kwargs.items():
            setattr(obj, key, value)
        
        await self.session.commit()
        return obj
    
    async def delete(self, id: int) -> bool:
        """Удалить запись"""
        obj = await self.get_by_id(id)
        if not obj:
            return False
        
        await self.session.delete(obj)
        await self.session.commit()
        return True
```

### 5. Добавление сервиса (бизнес-логики)

**Файл:** `bot/common/func/my_service.py`

```python
from bot.db.dao import MyModelDAO

class MyService:
    """Сервис для работы с моей фичей"""
    
    def __init__(self, my_model_dao: MyModelDAO):
        self.dao = my_model_dao
    
    async def process_user_input(self, user_id: int, input_text: str):
        """Обработать ввод пользователя"""
        # Сложная бизнес-логика
        validated_text = self._validate_input(input_text)
        
        # Сохранить в БД
        obj = await self.dao.create(
            name=validated_text,
            user_id=user_id,
            description="Auto-generated"
        )
        
        return obj
    
    @staticmethod
    def _validate_input(text: str) -> str:
        """Валидировать ввод"""
        return text.strip().lower()
```

### 6. Добавление FastAPI эндпоинта

**Файл:** `bot/api.py` или новый `bot/routers/api_my_feature.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from bot.db.dao import MyModelDAO

router = APIRouter(prefix="/api/my-feature", tags=["my-feature"])

# Pydantic схема для валидации
class MyModelSchema(BaseModel):
    name: str
    description: str | None = None
    
    class Config:
        from_attributes = True

# Эндпоинт GET
@router.get("/", response_model=list[MyModelSchema])
async def get_all(
    session = Depends(get_async_session)
):
    """Получить все записи"""
    dao = MyModelDAO(session)
    models = await dao.get_all()
    return models

# Эндпоинт POST
@router.post("/", response_model=MyModelSchema)
async def create(
    data: MyModelSchema,
    session = Depends(get_async_session)
):
    """Создать запись"""
    dao = MyModelDAO(session)
    obj = await dao.create(**data.dict())
    return obj

# Эндпоинт GET по ID
@router.get("/{item_id}", response_model=MyModelSchema)
async def get_by_id(
    item_id: int,
    session = Depends(get_async_session)
):
    """Получить по ID"""
    dao = MyModelDAO(session)
    obj = await dao.get_by_id(item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    return obj

# Эндпоинт PUT
@router.put("/{item_id}", response_model=MyModelSchema)
async def update(
    item_id: int,
    data: MyModelSchema,
    session = Depends(get_async_session)
):
    """Обновить запись"""
    dao = MyModelDAO(session)
    obj = await dao.update(item_id, **data.dict(exclude_unset=True))
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    return obj

# Эндпоинт DELETE
@router.delete("/{item_id}")
async def delete(
    item_id: int,
    session = Depends(get_async_session)
):
    """Удалить запись"""
    dao = MyModelDAO(session)
    success = await dao.delete(item_id)
    if not success:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": True}
```

---

## 🧪 Тестирование

### Unit тесты

**Файл:** `tests/test_dao.py`

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from bot.db.models import MyModel, Base
from bot.db.dao import MyModelDAO

@pytest.fixture
async def async_session():
    """Fixture для async сессии"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_local = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session_local() as session:
        yield session

@pytest.mark.asyncio
async def test_create_model(async_session):
    """Тест создания модели"""
    dao = MyModelDAO(async_session)
    
    obj = await dao.create(
        name="Test",
        description="Test description",
        user_id=1
    )
    
    assert obj.name == "Test"
    assert obj.id is not None

@pytest.mark.asyncio
async def test_get_by_id(async_session):
    """Тест получения по ID"""
    dao = MyModelDAO(async_session)
    
    created = await dao.create(name="Test", user_id=1)
    fetched = await dao.get_by_id(created.id)
    
    assert fetched.name == "Test"
```

### Запуск тестов

```bash
# Запустить все тесты
pytest

# С verbose выводом
pytest -v

# Только один тест файл
pytest tests/test_dao.py

# С покрытием кода
pytest --cov=bot tests/
```

---

## 📚 Git рабочий процесс

### 1. Создание ветки для фичи

```bash
git checkout develop

# Создать ветку с нейм: feature/описание
git checkout -b feature/my-new-feature
```

### 2. Коммиты

```bash
# Коммиты должны быть:
# - Часто (каждая логическая единица)
# - С ясным описанием

git commit -m "Add MyModel to database"
git commit -m "Implement MyModelDAO CRUD operations"
git commit -m "Add /mycommand router handler"
```

### 3. Push и Pull Request

```bash
# Push в origin
git push origin feature/my-new-feature

# На GitHub создать Pull Request
# - Заполнить описание
# - Указать связанные issues (#123)
```

### 4. Форматирование кода перед Push

```bash
# Форматирование Black
black bot/

# Сортировка импортов
isort bot/

# Проверка Flake8
flake8 bot/

# Type checking
mypy bot/

# Все вместе
black bot/ && isort bot/ && flake8 bot/ && mypy bot/
```

---

## 👀 Code Review

### Чек-лист перед PR:

- [ ] Код следует стайл гайду (Black, isort)
- [ ] Все импорты отсортированы
- [ ] Добавлены docstrings к функциям
- [ ] Нет `print()` - использовать логирование
- [ ] Все типы аннотированы (type hints)
- [ ] Обработаны исключения (try/except где нужно)
- [ ] Добавлены юнит тесты
- [ ] Миграции созданы (для БД изменений)
- [ ] Обновлена документация

### Что ожидается в Code Review:

1. **Качество кода** - следование лучшим практикам
2. **Функциональность** - реализация требований
3. **Тесты** - достаточное покрытие
4. **Документация** - ясные комментарии
5. **Производительность** - оптимизированный код

---

## 📝 Нейминг соглашения

### Python файлы
```
my_feature.py           # lowercase with underscores
my_complex_feature.py   # не CamelCase
```

### Функции и переменные
```python
def get_user_by_id(user_id: int):  # snake_case
async def process_payment():       # snake_case
my_variable = "value"              # snake_case
```

### Классы и исключения
```python
class MyModel:                      # PascalCase
class UserDAO:                      # PascalCase
class ValidationError(Exception):   # PascalCase
```

### FSM состояния
```python
class MyFeatureStates(StatesGroup):
    waiting_for_input = State()     # snake_case
    processing = State()
```

### Константы
```python
MAX_USERS = 1000        # UPPER_CASE
DEFAULT_TIMEOUT = 30
API_TIMEOUT = 5
```

### Ветки Git
```
feature/user-authentication     # feature/что-то
bugfix/payment-issue            # bugfix/что-то
docs/update-readme              # docs/что-то
refactor/optimize-database      # refactor/что-то
```

### Коммиты
```
Add new user authentication feature
Fix database connection timeout issue
Update README with installation steps
Refactor DAO pattern implementation
```

---

## 🔗 Соглашения коментариев

```python
# Плохо: очень очевидно
x = x + 1  # increment x

# Хорошо: объясняет ПОЧЕМУ
# Используем retry logic для сетевых ошибок
try:
    response = await http_client.get(url)
except ConnectionError:
    # Retry after exponential backoff
    await asyncio.sleep(2 ** attempt)
```

### Docstrings

```python
def calculate_discount(price: float, percentage: float) -> float:
    """
    Рассчитать скидку на товар.
    
    Args:
        price: Оригинальная цена товара
        percentage: Процент скидки (0-100)
    
    Returns:
        Цена после применения скидки
    
    Raises:
        ValueError: Если percentage не в диапазоне 0-100
    """
    if not 0 <= percentage <= 100:
        raise ValueError("Percentage must be between 0 and 100")
    
    return price * (1 - percentage / 100)
```

---

## 📚 Ссылки и ресурсы

### Документация:
- [aiogram docs](https://docs.aiogram.dev/)
- [FastAPI docs](https://fastapi.tiangolo.com/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [Python async/await](https://docs.python.org/3/library/asyncio.html)

### Инструменты:
- [Black formatter](https://black.readthedocs.io/)
- [isort import sorter](https://pycqa.github.io/isort/)
- [Flake8 linter](https://flake8.pycqa.org/)
- [mypy type checker](https://www.mypy-lang.org/)

### Примеры в проекте:
- **Роутер:** [bot/routers/start.py](../bot/routers/start.py)
- **DAO:** [bot/db/dao.py](../bot/db/dao.py)
- **Модель:** [bot/db/models.py](../bot/db/models.py)

---

## 🎯 Примеры Pull Requests

### Пример хорошего PR:

```
Title: Add user profile view endpoint

Description:
Added new FastAPI endpoint to retrieve user profile information.

Changes:
- Added /api/users/{user_id} GET endpoint
- Added UserProfileSchema for response validation
- Added comprehensive unit tests
- Updated API documentation

Related Issues:
- Closes #123
- Related to #456

Testing:
- [x] Unit tests added (3/3 passing)
- [x] Manual testing completed
- [x] No breaking changes
```

---

## 💬 Вопросы?

При возникновении вопросов:
1. Проверьте существующий код в проекте
2. Посмотрите примеры в `bot/routers/`, `bot/db/`, etc.
3. Прочитайте документацию в [ARCHITECTURE.md](ARCHITECTURE.md)
4. Откройте Issue или обсудите в PR

---

**Спасибо за контрибьютинг!** 🙏

**Версия:** 1.0  
**Дата:** 27.12.2024
