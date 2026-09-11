#!/bin/sh
# Раз в 6 часов перечитываем конфиг: после продления сертификата certbot'ом
# nginx иначе продолжит отдавать старый до перезапуска контейнера.
# Запускается entrypoint'ом nginx ДО старта самого nginx, поэтому уходим в фон.
(
    while :; do
        sleep 6h
        nginx -s reload 2>/dev/null || true
    done
) &
