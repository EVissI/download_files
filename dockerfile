FROM python:3.12.6-slim

ENV DEBIAN_FRONTEND=noninteractive

# Установка зависимостей
RUN apt update && apt install -y --no-install-recommends \
    wget \
    gnupg2 \
    gnubg \
    tesseract-ocr \
    libtesseract-dev \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    poppler-utils \
    ghostscript \
    ca-certificates \
    && \
    echo "deb http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
    wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - && \
    apt update && apt install -y --no-install-recommends postgresql-client-17 && \
    rm -rf /var/lib/apt/lists/*

# Подавляем ALSA ошибки, задав null-устройство для звука
RUN printf '%s\n' \
    'pcm.!default {' \
    '  type plug' \
    '  slave.pcm "null"' \
    '}' \
    'pcm.null {' \
    '  type null' \
    '}' \
    'ctl.!default {' \
    '  type hw' \
    '  card 0' \
    '}' > /etc/asound.conf

RUN ln -s /usr/games/gnubg /usr/bin/gnubg || true

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /app
