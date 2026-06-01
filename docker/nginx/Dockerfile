FROM nginx:stable-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip \
    && pip3 install --break-system-packages "certbot>=5.4" \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/www/certbot /etc/nginx/templates

COPY http.conf https.conf /etc/nginx/templates/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
