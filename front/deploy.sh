#!/bin/bash

# Папка проекта
PROJECT_DIR="/var/www/nards"

echo "➡ Перехожу в директорию проекта: $PROJECT_DIR"
cd "$PROJECT_DIR" || exit 1

echo "🔄 Получаю последние изменения из Git..."
git pull origin main || { echo "❌ Ошибка при git pull"; exit 1; }

echo "📦 Устанавливаю зависимости..."
npm install || { echo "❌ Ошибка при npm install"; exit 1; }

echo "🔨 Билд проекта..."
npm run build || { echo "❌ Ошибка при npm run build"; exit 1; }

echo "🚀 Останавливаю текущий инстанс"
sudo kill -9 $(sudo lsof -t -i :3000)

echo "🚀 Запускаю через nohup..."
nohup npm run dev > output.log 2>&1 &

echo "✅ Деплой завершен. Приложение запущено"
