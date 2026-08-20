# SUTRA backend — reproducible deployment image
FROM python:3.13-slim

# FFmpeg for stream ingest; libGL/glib for OpenCV's runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

# non-root runtime
RUN useradd -m -u 10001 sutra && mkdir -p /data && chown -R sutra:sutra /app /data
USER sutra

ENV SUTRA_DATA_DIR=/data \
    PYTHONUNBUFFERED=1

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

WORKDIR /app/backend
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
