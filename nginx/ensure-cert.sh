#!/bin/sh
# Создаёт временный самоподписанный сертификат для домена, если настоящего ещё нет.
# Нужен, чтобы nginx стартовал с новым доменом ДО того, как на него переехал DNS
# (Let's Encrypt не выпустит сертификат, пока домен не резолвится на этот сервер).
#
#   sh nginx/ensure-cert.sh learnbg.ru
#
# Настоящий сертификат выпускается позже: nginx/issue-cert.sh
set -eu

cd "$(dirname "$0")/.."

DOMAIN="${1:-}"
[ -n "$DOMAIN" ] || { echo "Использование: sh nginx/ensure-cert.sh <домен>"; exit 1; }

COMPOSE="docker compose"
$COMPOSE version >/dev/null 2>&1 || COMPOSE="docker-compose"

LIVE="/etc/letsencrypt/live/$DOMAIN"

if $COMPOSE run --rm --entrypoint sh certbot -c "[ -f $LIVE/fullchain.pem ]" 2>/dev/null; then
    echo "Сертификат для $DOMAIN уже есть — ничего не делаю"
    exit 0
fi

echo "==> Временный самоподписанный сертификат для $DOMAIN"
$COMPOSE run --rm --entrypoint sh certbot -c \
  "mkdir -p $LIVE && openssl req -x509 -nodes -newkey rsa:2048 -days 1 -keyout $LIVE/privkey.pem -out $LIVE/fullchain.pem -subj /CN=$DOMAIN"

echo "Готово. Теперь nginx поднимется, но браузер будет ругаться на сертификат —"
echo "это нормально до выпуска настоящего: sh nginx/issue-cert.sh $DOMAIN"
