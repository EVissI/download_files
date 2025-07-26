FROM python:3.12-slim

# Установка зависимостей
RUN apt update && apt install -y \
    gnubg \
    tesseract-ocr \
    libtesseract-dev \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    poppler-utils \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/games/gnubg /usr/bin/gnubg
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY . .


WORKDIR /app
