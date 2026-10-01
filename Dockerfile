# Kitobxon Hub — single production image:
#   REST API + Telegram bot webhook + Mini App (/app/) + Admin Panel (/admin/)
#
#   docker build -t kitobxon-hub .
#   docker run -p 8000:8000 --env-file .env kitobxon-hub

# ---------- Stage 1: build the two React frontends ----------
FROM node:22-alpine AS frontend
WORKDIR /build
COPY miniapp/package.json miniapp/package-lock.json miniapp/
COPY admin/package.json admin/package-lock.json admin/
RUN cd miniapp && npm ci --no-audit --no-fund && cd ../admin && npm ci --no-audit --no-fund
COPY miniapp/ miniapp/
COPY admin/ admin/
RUN cd miniapp && npm run build && cd ../admin && npm run build

# ---------- Stage 2: Python backend ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STATIC_DIR=/srv/backend/static

WORKDIR /srv/backend

# Pango/HarfBuzz render the official PDF reports (WeasyPrint); Liberation Serif is a
# Times-compatible font with full Uzbek Latin support, DejaVu is the fallback.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-liberation2 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ .
COPY --from=frontend /build/miniapp/dist static/miniapp
COPY --from=frontend /build/admin/dist static/admin

RUN useradd --system --uid 10001 --home /srv appuser \
    && mkdir -p /srv/backend/storage \
    && chown -R appuser /srv/backend/storage
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'), timeout=4).status == 200 else 1)"

CMD ["./start.sh"]
