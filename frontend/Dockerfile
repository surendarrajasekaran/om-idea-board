FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:stable-alpine
ENV BACKEND_HOST=backend
USER root
RUN apk upgrade --no-cache && mkdir -p /etc/nginx/templates && printf 'limit_req_zone $binary_remote_addr zone=ideas:10m rate=5r/s;\n' > /etc/nginx/conf.d/rate-limit.conf
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
USER 101
EXPOSE 8080
