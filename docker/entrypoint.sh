#!/bin/sh
set -e

case "$1" in
  server)
    exec oopsys-server run
    ;;
  bot)
    exec oopsys-bot
    ;;
  migrate)
    exec oopsys-server migrate
    ;;
  *)
    exec "$@"
    ;;
esac
