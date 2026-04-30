#!/bin/sh
set -e

# Default backend URL if not provided
BACKEND_URL="${BACKEND_URL:-http://shop-chat-backend:8000}"

# Substitute environment variables into nginx config template.
# Write to /tmp since /etc/nginx is read-only for non-root users in OpenShift.
envsubst '${BACKEND_URL}' < /etc/nginx/nginx.conf.template > /tmp/nginx.conf

exec nginx -c /tmp/nginx.conf -g 'daemon off;'
