FROM node:25-alpine@sha256:bdf2cca6fe3dabd014ea60163eca3f0f7015fbd5c7ee1b0e9ccb4ced6eb02ef4 AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:stable-alpine@sha256:f5116ed4606f3eb015dd4a8e28cb9b351476dc0ad4bc6e9f93b19cec130cdf03
ENV BACKEND_HOST=backend TLS_LISTEN="" RELEASE_ID=local NGINX_ENVSUBST_FILTER="BACKEND_HOST|TLS_LISTEN|RELEASE_ID"
USER root
RUN apk upgrade --no-cache && mkdir -p /etc/nginx/templates && printf 'limit_req_zone $binary_remote_addr zone=ideas:10m rate=5r/s;\n' > /etc/nginx/templates/rate-limit.conf.template
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
USER 101
# Exposing it to the outside world
EXPOSE 8080
# fixed