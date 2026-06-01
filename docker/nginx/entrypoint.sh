#!/bin/bash
set -euo pipefail

CERT_NAME=oopsys
CERT="/etc/letsencrypt/live/${CERT_NAME}/fullchain.pem"
WEBROOT=/var/www/certbot
RENEW_EVERY="${CERTBOT_RENEW_INTERVAL_SECONDS:-21600}"
CONF=/etc/nginx/conf.d/default.conf

use_http() {
  cp /etc/nginx/templates/http.conf "$CONF"
}

use_https() {
  cp /etc/nginx/templates/https.conf "$CONF"
}

if [ -z "${OOPSYS_PUBLIC_IP:-}" ]; then
  echo "[nginx] no OOPSYS_PUBLIC_IP — HTTP only"
  use_http
  exec nginx -g 'daemon off;'
fi

: "${OOPSYS_ACME_EMAIL:?OOPSYS_ACME_EMAIL required with OOPSYS_PUBLIC_IP}"

use_http
nginx -g 'daemon on;'

if [ ! -f "$CERT" ]; then
  extra=()
  if [ "${OOPSYS_ACME_STAGING:-false}" = "true" ]; then
    extra+=(--staging)
  fi
  echo "[certbot] requesting certificate for ${OOPSYS_PUBLIC_IP}..."
  certbot certonly \
    --webroot -w "$WEBROOT" \
    --preferred-profile shortlived \
    --ip-address "$OOPSYS_PUBLIC_IP" \
    --cert-name "$CERT_NAME" \
    --email "$OOPSYS_ACME_EMAIL" \
    --agree-tos \
    --non-interactive \
    --no-eff-email \
    "${extra[@]}"
fi

use_https
nginx -s reload

(
  while true; do
    sleep "$RENEW_EVERY"
    certbot renew --quiet --deploy-hook "nginx -s reload" || true
  done
) &

nginx -s quit
sleep 1
exec nginx -g 'daemon off;'
