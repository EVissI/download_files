# 🚀 Быстрый старт - Backgammon Bot

> **За 5 минут запустите бота, админ-панель и API**

---

## 📋 Необходимо перед началом:

1. ✅ **Git** - для клонирования репозитория
2. ✅ **Docker & Docker Compose** - для контейнеризации
3. ✅ **BOT_TOKEN** - от [@BotFather](https://t.me/botfather)
4. ✅ **Текстовый редактор** - для редактирования `.env`

---

## ⚡ 5-минутный старт

### Шаг 1️⃣: Клонирование (1 минута)

```bash
git clone <repository-url>
cd download_files
```

### Шаг 2️⃣: Конфигурация (2 минуты)

```bash
# Копируем пример конфигурации
cp .env.example .env

# Открываем в редакторе и заполняем:
# - BOT_TOKEN (обязательно)
# - POSTGRES_PASSWORD (минимум сменить)
# - REDIS_PASSWORD (минимум сменить)
```

**Минимальная конфигурация:**

```env
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
POSTGRES_PASSWORD=your_postgres_password
REDIS_PASSWORD=your_redis_password
ROOT_ADMIN_IDS=[YOUR_TELEGRAM_ID]
```

### Шаг 3️⃣: Запуск (2 минуты)

```bash
# Запуск всех сервисов
docker-compose up -d

# Проверка статуса
docker-compose ps
```

---

## ✅ Проверка запуска

### 🤖 Бот в Telegram

```
Напишите вашему боту: /start
Должно появиться главное меню
```

### 📊 Админ-панель

```
http://localhost:5000

Логин: admin
Пароль: admin
```

### 🔌 API документация

```
http://localhost:8000/docs
http://localhost:8000/redoc
```

---

## 📊 Основные команды

### Управление контейнерами:

```bash
# Запустить все
docker-compose up -d

# Остановить все
docker-compose down

# Просмотреть логи бота
docker-compose logs -f backgammon-bot

# Просмотреть логи админ-панели
docker-compose logs -f admin-panel

# Перезагрузить бота
docker-compose restart backgammon-bot
```

### Миграции БД:

```bash
# Применить все миграции (происходит автоматически)
docker-compose exec backgammon-bot alembic upgrade head

# Создать новую миграцию
docker-compose exec backgammon-bot alembic revision --autogenerate -m "описание"

# Откатить на шаг назад
docker-compose exec backgammon-bot alembic downgrade -1
```

---

## 🔐 Первые шаги в админ-панели

### 1. Вход

1. Перейти на http://localhost:5000
2. Логин: `admin`
3. Пароль: `admin`

### 2. Смена пароля администратора ⚠️

1. Нажать на аватар в верхнем правом углу
2. Выбрать **"Security"**
3. Нажать **"Change Password"**
4. Ввести новый пароль (минимум 6 символов)

### 3. Смена SECRET_KEY ⚠️

1. Отредактировать `.env` файл:
   ```bash
   SECRET_KEY=your-new-secret-key-min-32-chars
   ```
2. Перезагрузить контейнер:
   ```bash
   docker-compose restart admin-panel
   ```

### 4. Добавление первого промокода

1. Перейти в **Промокоды** → **Промокоды**
2. Нажать **"Add Promocode"**
3. Заполнить поля:
   - Code: `WELCOME` (пример)
   - Is Active: ✓ (галочка)
   - Max Usage: `10`
   - Duration Days: `30`
4. Нажать **"Save"**

---

## 📱 Тестирование бота

### Команды для тестирования:

```
/start         - начать
/profile       - профиль
/help          - справка
/settings      - настройки
/contact       - контакты
```

### Тестирование промокода:

```
/activate_promo
[Нажать кнопку промокода]
Ввести код: WELCOME
Готово! Промокод активирован
```

---

## 🐛 Быстрое решение проблем

### ❌ "Connection refused"

```bash
# Проверить статус контейнеров
docker-compose ps

# Если не запущены, перезагрузить
docker-compose down && docker-compose up -d
```

### ❌ "BOT_TOKEN is not set"

```bash
# Проверить .env файл
grep BOT_TOKEN .env

# Если пусто, заполнить и перезагрузить
docker-compose restart backgammon-bot
```

### ❌ "401 Unauthorized" в админ-панели

```bash
# Очистить cookies браузера (Ctrl+Shift+Del)
# Затем перезагрузить странице (Ctrl+Shift+R)

# Или перезагрузить контейнер
docker-compose restart admin-panel
```

### ❌ "Database is locked"

```bash
# Остановить все
docker-compose down

# Удалить volume БД и перезагрузить
docker volume rm download_files_pgdata
docker-compose up -d
```

---

## 📚 Дальнейшее изучение

После успешного запуска рекомендуем прочитать:

1. **[README.md](README.md)** - Полная документация проекта
2. **[ADMIN_PANEL_GUIDE.md](ADMIN_PANEL_GUIDE.md)** - Подробный гайд админ-панели
3. **[FastAPI Docs](http://localhost:8000/docs)** - API документация

---

## 🎯 Чек-лист первого запуска

- [ ] Git клонирован
- [ ] `.env` файл создан и заполнен
- [ ] `docker-compose up -d` выполнен
- [ ] Все контейнеры запущены (`docker-compose ps`)
- [ ] Бот отвечает на `/start` команду
- [ ] Админ-панель доступна на http://localhost:5000
- [ ] API документация доступна на http://localhost:8000/docs
- [ ] Пароль администратора изменен
- [ ] SECRET_KEY обновлен для продакшена
- [ ] Создан первый промокод

---

## ⏭️ Что дальше?

### Для разработчиков:
1. Изучить структуру проекта в [README.md](README.md)
2. Добавить свою команду бота (смотреть `bot/routers/`)
3. Добавить новую модель БД (смотреть `bot/db/models.py`)

### Для администраторов:
1. Управление пользователями в админ-панели
2. Создание и управление промокодами
3. Просмотр платежей и статистики
4. Отправка рассылок новым пользователям

### Для деплоя:
1. Обновить `.env` переменные для продакшена
2. Использовать SSL сертификаты
3. Настроить резервные копии БД (`bot/db/pg_backup.py`)
4. Мониторить логи приложения

---

## 📞 Справка

**Документация:** [README.md](README.md)
**Админ-панель:** [ADMIN_PANEL_GUIDE.md](ADMIN_PANEL_GUIDE.md)
**API Docs:** http://localhost:8000/docs

---

**Версия:** 1.0  
**Дата:** 27.12.2024

Приятного использования! 🎮
