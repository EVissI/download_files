#!/bin/sh
# Первичный выпуск сертификата Let's Encrypt. Запускать ОДИН раз на новом сервере
# из корня проекта:  sh nginx/init-letsencrypt.sh
# Для проверки без расхода лимитов LE:  STAGING=1 sh nginx/init-letsencrypt.sh
#
# Дальше продление полностью автоматическое: контейнер certbot проверяет
# сертификат каждые 12 ч, nginx перечитывает конфиг каждые 6 ч.
set -eu

cd "$(dirname "$0")/.."

[ -f .env ] || { echo "Нет .env в корне проекта"; exit 1; }
# .env читаем построчно, а НЕ через `. ./.env`: docker-овский .env не обязан
# быть валидным shell-скриптом — символы вроде # ? ~ в паролях ломают sh.
env_value() {
    grep -E "^$1=" .env 2>/dev/null | tail -n 1 | cut -d= -f2- | tr -d '\r' | tr -d '"'
}

DOMAIN="$(env_value APP_DOMAIN)"
EMAIL="$(env_value CERTBOT_EMAIL)"
[ -n "$DOMAIN" ] || { echo "В .env не задан APP_DOMAIN"; exit 1; }
[ -n "$EMAIL" ]  || { echo "В .env не задан CERTBOT_EMAIL"; exit 1; }

COMPOSE="docker compose"
$COMPOSE version >/dev/null 2>&1 || COMPOSE="docker-compose"

LIVE="/etc/letsencrypt/live/$DOMAIN"

echo "==> Домен: $DOMAIN, контакт: $EMAIL"

# Во всех вызовах обязателен --entrypoint: у сервиса certbot entrypoint
# переопределён на цикл автопродления, и аргументы ушли бы в тот скрипт.

echo "==> Временный самоподписанный сертификат (иначе nginx не стартует)"
$COMPOSE run --rm --entrypoint sh certbot -c \
  "mkdir -p $LIVE && openssl req -x509 -nodes -newkey rsa:2048 -days 1 -keyout $LIVE/privkey.pem -out $LIVE/fullchain.pem -subj /CN=$DOMAIN"

echo "==> Поднимаем nginx"
$COMPOSE up -d nginx
sleep 3

echo "==> Убираем временный сертификат"
$COMPOSE run --rm --entrypoint sh certbot -c \
  "rm -rf /etc/letsencrypt/live/$DOMAIN /etc/letsencrypt/archive/$DOMAIN /etc/letsencrypt/renewal/$DOMAIN.conf"

echo "==> Запрашиваем настоящий сертификат"
STAGING_ARG=""
[ "${STAGING:-0}" = "1" ] && STAGING_ARG="--staging"

$COMPOSE run --rm --entrypoint certbot certbot \
  certonly --webroot -w /var/www/certbot \
    $STAGING_ARG \
    -d "$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos --no-eff-email \
    --rsa-key-size 4096 \
    --non-interactive

echo "==> Перечитываем конфиг nginx"
$COMPOSE exec nginx nginx -s reload

echo "==> Готово. Проверь: https://$DOMAIN"
