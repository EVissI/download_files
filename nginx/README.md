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

Сертификаты лежат в хостовой папке `/etc/letsencrypt` (смонтирована в оба контейнера),
webroot для ACME — в docker-томе `certbot_www`. Продлением занимается контейнер `certbot`
(проверка каждые 12 ч).

Хостовая папка выбрана вместо docker-тома, чтобы уже выпущенные сертификаты подхватывались
без копирования, а хостовый certbot (если он ещё жив) видел те же файлы. На чистом сервере
Docker создаст папку сам, а заполнит её `init-letsencrypt.sh`.

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

```bash
sudo tar czf le.tar.gz -C /etc letsencrypt     # на старом сервере
# скопировать le.tar.gz на новый, затем там же:
sudo tar xzf le.tar.gz -C /etc
docker compose up -d
```

`init-letsencrypt.sh` в этом случае не нужен — контейнер `certbot` подхватит
существующие `renewal/*.conf` и продолжит продлевать.

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
