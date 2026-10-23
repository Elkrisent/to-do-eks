# --- build stage: compile the React app into static files ---
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY index.html vite.config.js ./
COPY src ./src
RUN npm run build

# --- runtime stage: tiny non-root nginx serving the static files ---
FROM nginxinc/nginx-unprivileged:1.27-alpine
# The base image lags behind Alpine's security fixes; pull in patched OS packages
# (Trivy in CI fails the build on fixable HIGH/CRITICAL CVEs), then drop back to non-root.
USER root
RUN apk upgrade --no-cache
USER 101
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
