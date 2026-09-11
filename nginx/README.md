# nginx + HTTPS в Docker

Заменяет nginx из systemd на хосте. Весь конфиг лежит в репозитории, поэтому при переезде
на новый сервер ничего настраивать руками не нужно.

## Что внутри

| Файл | Назначение |
|---|---|
| `templates/app.conf.template` | конфиг сайта; `${APP_DOMAIN}` подставляется при старте контейнера |
| `Dockerfile` | `nginx:1.27-alpine` + скрипт перечитывания конфига |
| `reload-loop.sh` | раз в 6 ч делает `nginx -s reload`, чтобы подхватить продлённый сертификат |
| `init-letsencrypt.sh` | первичный выпуск сертификата (один раз на сервер) |

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

## Смена домена

Поменять `APP_DOMAIN` в `.env`, там же `MINI_APP_URL`, затем:

```bash
docker compose up -d --force-recreate nginx
sh nginx/init-letsencrypt.sh
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
docker compose run --rm certbot certificates   # срок действия сертификатов
```

После правки `templates/app.conf.template` нужен `--force-recreate` контейнера
(подстановка домена выполняется только при старте), либо `reload` — если менялось
то, что не зависит от `${APP_DOMAIN}`.
