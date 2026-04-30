# Stage 1: Build the React app
FROM --platform=linux/amd64 node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# VITE_API_URL is intentionally NOT set here.
# nginx reverse-proxies /api/* to the backend, so the browser always
# talks to the same origin — no CORS and no build-time URL baking needed.
ENV VITE_API_URL=/api

RUN npm run build


# Stage 2: Serve with nginx
FROM --platform=linux/amd64 nginx:1.27-alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy the nginx config template (uses ${BACKEND_URL} substituted at startup)
COPY nginx.conf /etc/nginx/nginx.conf.template

# Copy built static assets
COPY --from=builder /app/dist /usr/share/nginx/html

# OpenShift runs as arbitrary non-root UID — ensure writable paths
RUN chmod -R g=u /usr/share/nginx/html && \
    chmod -R g=u /var/cache/nginx && \
    chmod -R g=u /var/log/nginx && \
    chmod g=u /etc/nginx/nginx.conf.template && \
    touch /tmp/nginx.pid && chmod g=u /tmp/nginx.pid

# Startup script: substitute env vars into nginx config, then start nginx
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/docker-entrypoint.sh"]
