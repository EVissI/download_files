# Базовый образ — стабильный Debian, совместим с Puppeteer
FROM node:20-bullseye

# Рабочая директория
WORKDIR /app

# Устанавливаем системные зависимости для Chromium
RUN apt-get update && apt-get install -y \
    chromium \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    xdg-utils \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Копируем package.json и lock-файл
COPY package*.json ./

# Устанавливаем зависимости Node
RUN npm install

# Копируем проект
COPY . .

# Переменные окружения
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV NODE_ENV=production

# Открываем порт
EXPOSE 3000

# Запуск Next.js
CMD ["npm", "run", "dev"]
