#!/bin/sh
set -e

case "$1" in
  server)
    echo "[entrypoint] applying database migrations..."
    oopsys-server migrate
    echo "[entrypoint] starting server..."
    exec oopsys-server run
    ;;
  bot)
    echo "[entrypoint] starting bot worker..."
    exec oopsys-bot
    ;;
  migrate)
    exec oopsys-server migrate
    ;;
  *)
    exec "$@"
    ;;
esac
