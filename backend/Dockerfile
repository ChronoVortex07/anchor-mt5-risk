FROM node:22-bookworm-slim@sha256:6c74791e557ce11fc957704f6d4fe134a7bc8d6f5ca4403205b2966bd488f6b3 AS dashboard
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.lock ./requirements.lock
RUN pip install -r requirements.lock && useradd --uid 10001 --create-home risk
COPY --chown=10001:10001 backend/ ./
COPY --chown=10001:10001 tools/ ./tools/
COPY --chown=10001:10001 --from=dashboard /build/dist ./static
USER 10001
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/readyz', timeout=2)"
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8080 --no-access-log --proxy-headers --forwarded-allow-ips='*'"]
