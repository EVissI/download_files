FROM nginx:1.27-alpine

# Скрипт кладём через COPY, а не bind-mount: официальный entrypoint выполняет
# файлы из /docker-entrypoint.d только с битом +x, а он теряется при монтировании
# из Windows-хоста.
COPY reload-loop.sh /docker-entrypoint.d/40-reload-loop.sh
RUN chmod +x /docker-entrypoint.d/40-reload-loop.sh

# Дефолтный сайт образа (server_name localhost) мешает и не нужен:
# конфиг генерируется из templates/app.conf.template в этот же каталог.
RUN rm -f /etc/nginx/conf.d/default.conf
