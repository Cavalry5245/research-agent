#!/bin/sh
set -e

# Defaults keep docker-compose working unchanged (frontend proxies to the "api" service).
# Railway sets PORT and API_UPSTREAM/API_HOST via service variables.
export PORT="${PORT:-80}"
export API_UPSTREAM="${API_UPSTREAM:-http://api:8000}"

# Host header sent upstream. Default derives from the upstream authority so docker-compose
# keeps sending Host: api:8000; on Railway set API_HOST to the api service's public hostname.
if [ -z "${API_HOST}" ]; then
    API_HOST=$(printf '%s' "${API_UPSTREAM}" | sed -E 's#^[a-zA-Z]+://##; s#/.*$##')
fi
export API_HOST

# Only substitute our three vars — leave nginx runtime vars ($remote_addr, $uri, ...) intact.
envsubst '${PORT} ${API_UPSTREAM} ${API_HOST}' \
    < /etc/nginx/templates/nginx.conf.template \
    > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
