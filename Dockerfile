FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libarchive-tools \
        p7zip-full \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .

RUN addgroup --system sana \
    && adduser --system --ingroup sana --home /app sana \
    && mkdir -p /data/media /data/backups /data/import_jobs /data/support_bundles \
    && chmod +x /app/scripts/*.sh /app/scripts/sana-doctor /app/scripts/sdac-doctor 2>/dev/null || true \
    && chown -R sana:sana /app /data

ENV SDAC_CONFIG_FILE=/data/config.json \
    SDAC_DB_FILE=/data/sdac.db \
    SDAC_MEDIA_DIR=/data/media \
    SDAC_BACKUP_DIR=/data/backups \
    SDAC_IMPORT_JOB_DIR=/data/import_jobs \
    SDAC_BOT_STATUS_FILE=/data/bot_status.json

VOLUME ["/data"]
EXPOSE 5000

USER sana

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/admin/health', timeout=4).read()" || exit 1

CMD ["gunicorn", "--workers", "2", "--threads", "4", "--timeout", "120", "--bind", "0.0.0.0:5000", "dashboard:app"]
