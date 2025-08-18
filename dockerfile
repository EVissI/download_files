FROM python:3.12.6-slim

# Установка зависимостей
RUN apt update && apt install -y \
    wget \
    gnupg2 \
    gnubg \
    tesseract-ocr \
    libtesseract-dev \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    poppler-utils \
    ghostscript && \
    echo "deb http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
    wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - && \
    apt update && apt install -y postgresql-client-17 && \
    rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/games/gnubg /usr/bin/gnubg
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /app
