#!/bin/sh
# Выпускает настоящий сертификат Let's Encrypt для домена (и www, если он резолвится).
# Запускать ПОСЛЕ того, как A-запись домена указывает на этот сервер.
#
#   sh nginx/issue-cert.sh learnbg.ru
#   STAGING=1 sh nginx/issue-cert.sh learnbg.ru   # репетиция без расхода лимитов
set -eu

cd "$(dirname "$0")/.."

DOMAIN="${1:-}"
[ -n "$DOMAIN" ] || { echo "Использование: sh nginx/issue-cert.sh <домен>"; exit 1; }

[ -f .env ] || { echo "Нет .env в корне проекта"; exit 1; }
# shellcheck disable=SC1091
. ./.env
EMAIL="${CERTBOT_EMAIL:-}"
[ -n "$EMAIL" ] || { echo "В .env не задан CERTBOT_EMAIL"; exit 1; }

COMPOSE="docker compose"
$COMPOSE version >/dev/null 2>&1 || COMPOSE="docker-compose"

# www включаем в сертификат, только если он реально резолвится —
# иначе certbot провалит выпуск целиком.
WWW_ARG=""
if command -v getent >/dev/null 2>&1 && getent hosts "www.$DOMAIN" >/dev/null 2>&1; then
    WWW_ARG="-d www.$DOMAIN"
    echo "==> www.$DOMAIN резолвится, включаю в сертификат"
else
    echo "==> www.$DOMAIN не резолвится, выпускаю только для $DOMAIN"
fi

STAGING_ARG=""
[ "${STAGING:-0}" = "1" ] && STAGING_ARG="--staging"

echo "==> Выпускаю сертификат для $DOMAIN"
# --force-renewal: перезатирает временный самоподписанный, созданный ensure-cert.sh
$COMPOSE run --rm --entrypoint certbot certbot \
  certonly --webroot -w /var/www/certbot \
    $STAGING_ARG \
    --cert-name "$DOMAIN" \
    -d "$DOMAIN" $WWW_ARG \
    --email "$EMAIL" \
    --agree-tos --no-eff-email \
    --rsa-key-size 4096 \
    --force-renewal \
    --non-interactive

echo "==> Перечитываю конфиг nginx"
$COMPOSE exec nginx nginx -s reload

echo "==> Готово: https://$DOMAIN"
