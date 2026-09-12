# nginx + HTTPS в Docker

Заменяет nginx из systemd на хосте. Весь конфиг лежит в репозитории, поэтому при переезде
на новый сервер ничего настраивать руками не нужно.

## Что внутри

| Файл | Назначение |
|---|---|
| `templates/app.conf.template` | server-блоки доменов; `${APP_DOMAIN}` и `${APP_DOMAIN_OLD}` подставляются при старте |
| `snippets/app.conf` | проксирование и locations — общее для всех доменов |
| `snippets/ssl.conf` | параметры TLS |
| `Dockerfile` | `nginx:1.27-alpine` + скрипт перечитывания конфига |
| `reload-loop.sh` | раз в 6 ч делает `nginx -s reload`, чтобы подхватить продлённый сертификат |
| `init-letsencrypt.sh` | первичный выпуск сертификата на новом сервере |
| `ensure-cert.sh` | временный самоподписанный сертификат, чтобы nginx стартовал до переезда DNS |
| `issue-cert.sh` | выпуск настоящего сертификата для домена (и `www`, если резолвится) |

Сертификаты и webroot для ACME живут в docker-томах `certbot_conf` / `certbot_www`.
Продлением занимается контейнер `certbot` (проверка каждые 12 ч).

Именно тома, а не хостовая `/etc/letsencrypt`: docker на сервере работает в **rootless**-режиме,
root внутри контейнера отображается в обычного пользователя хоста и не может прочитать
`live/` и `archive/` с правами `0700 root:root`. В томе владелец совпадает автоматически.

## Переезд на новый сервер

```bash
git clone <repo> && cd download_files
cp .env.example .env && nano .env      # APP_DOMAIN, CERTBOT_EMAIL и остальные секреты
```

Дальше — A-запись домена на IP нового сервера, открыть порты 80 и 443, и:

```bash
docker compose up -d db redis fastapi backgammon-bot
sh nginx/init-letsencrypt.sh
docker compose up -d
```

Проверить выпуск без расхода лимитов Let's Encrypt (5 сертификатов на домен в неделю):

```bash
STAGING=1 sh nginx/init-letsencrypt.sh
```

После успешной проверки удалить тестовый сертификат и выпустить настоящий:

```bash
docker compose run --rm --entrypoint "rm -rf /etc/letsencrypt/live /etc/letsencrypt/archive /etc/letsencrypt/renewal" certbot
sh nginx/init-letsencrypt.sh
```

## Переезд на другой домен (learnbg.ru)

Порядок важен: Let's Encrypt не выпустит сертификат, пока домен не резолвится
на этот сервер, а nginx не стартует с доменом, у которого сертификата ещё нет.
Поэтому сначала ставим временный самоподписанный.

**1. Понизить TTL** у A-записи домена до 300 секунд — за сутки до переезда.

**2. Прописать домены в `.env`:**

```
APP_DOMAIN=learnbg.ru
APP_DOMAIN_OLD=nards.mini.app.gnubg.ru
```

**3. Временный сертификат и запуск nginx** (DNS ещё на старом хостинге):

```bash
sh nginx/ensure-cert.sh learnbg.ru
docker compose up -d --force-recreate nginx
```

**4. Открепить домен на старом хостинге** (в Тильде: Настройки сайта → Домен → открепить).

**5. Сменить A-запись** `learnbg.ru` на IP этого сервера. `CNAME www → learnbg.ru`
менять не нужно, он поедет следом. MX и TXT не трогать.

**6. Дождаться DNS и проверить:**

```bash
dig +short learnbg.ru && curl -sI http://learnbg.ru/.well-known/acme-challenge/test
```

Должен вернуться IP сервера и ответ 404 от nginx (не от старого хостинга).

**7. Выпустить настоящий сертификат:**

```bash
sh nginx/issue-cert.sh learnbg.ru
```

Скрипт сам определит, резолвится ли `www`, и включит его в сертификат.
Репетиция без расхода лимитов — `STAGING=1 sh nginx/issue-cert.sh learnbg.ru`.

**8. Переключить приложение на новый домен:** в `.env` поменять `MINI_APP_URL`
на `https://learnbg.ru`, затем

```bash
docker compose up -d --force-recreate fastapi backgammon-bot
```

Кнопки Mini App инлайновые, домен в BotFather не привязан — там ничего менять не нужно.

**9. Включить редирект со старого домена** (только после проверки шага 8):
в `templates/app.conf.template`, в последнем server-блоке закомментировать
`include /etc/nginx/snippets/app.conf;` и раскомментировать `return 301`.

```bash
docker compose up -d --force-recreate nginx
```

## Перенос существующих сертификатов (чтобы не выпускать заново)

Если сертификаты уже есть в `/etc/letsencrypt` (например, остались от nginx в systemd),
их можно перелить в том, не выпуская заново.

Том сначала должен создать сам compose — созданный руками `docker volume create` он
может не принять из-за отсутствия своих меток:

```bash
docker compose create nginx
```

Затем копируем содержимое. `tar` запускается на хосте от root (иначе не прочитает `0700`),
а в контейнер данные уходят через stdin:

```bash
sudo tar czf - -C /etc letsencrypt | docker run --rm -i -v download_files_certbot_conf:/dst alpine sh -c "tar xzf - -C /tmp && cp -a /tmp/letsencrypt/. /dst/"
```

Имя тома — `<имя_проекта>_certbot_conf`, имя проекта по умолчанию равно имени папки.
После этого `docker compose up -d`, а `init-letsencrypt.sh` не нужен: контейнер `certbot`
подхватит существующие `renewal/*.conf` и продолжит продлевать.

## Отключение старого nginx

Пока systemd-nginx держит порты 80/443, контейнер не поднимется:

```bash
systemctl disable --now nginx
```

## Полезные команды

```bash
docker compose exec nginx nginx -t          # проверить конфиг
docker compose exec nginx nginx -s reload   # перечитать после правки шаблона
docker compose logs -f nginx certbot
# Срок действия сертификатов. --entrypoint обязателен: у сервиса certbot
# entrypoint переопределён на цикл автопродления, и без этого аргументы
# уйдут в тот скрипт, а контейнер молча зависнет.
docker compose run --rm --entrypoint certbot certbot certificates

# Проверка автопродления: ходит на тестовый сервер LE, лимиты не тратит.
docker compose run --rm --entrypoint certbot certbot renew --webroot -w /var/www/certbot --dry-run
```

После правки `templates/app.conf.template` нужен `--force-recreate` контейнера
(подстановка домена выполняется только при старте), либо `reload` — если менялось
то, что не зависит от `${APP_DOMAIN}`.
