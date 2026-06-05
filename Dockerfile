# Hugging Face Spaces — Docker SDK용
# roadshow-server-v3 (FastAPI + DuckDB + MLflow)

FROM python:3.11-slim

# ── 시스템 의존성 ─────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python 의존성 (캐시 활용 위해 먼저 복사) ──────────────────
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── 애플리케이션 코드 ─────────────────────────────────────────
COPY . /app

# HF Spaces 표준 포트 7860, 쓰기 가능 디렉토리는 /tmp 또는 /data
ENV PORT=7860 \
    DB_PATH=/data/roadshow_v3.duckdb \
    MLFLOW_URI=sqlite:////data/mlflow_v3.db \
    MLFLOW_ARTIFACT_ROOT=/data/mlruns_v3 \
    PYTHONUNBUFFERED=1

# HF Spaces는 /data 디렉토리에만 쓰기 권한 부여
RUN mkdir -p /data && chmod 777 /data

EXPOSE 7860

# 단일 worker (메모리 절약, WebSocket 세션 유지)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
