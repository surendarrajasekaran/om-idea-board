FROM node:26-alpine@sha256:c6ad9e9c1d80f6eb607c26b4b0a132ff7a2344fad1c78ea3baa2a7d4c8de6d94 AS build
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
EXPOSE 8080
