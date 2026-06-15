from __future__ import annotations
"""앱 환경 설정 (env/.env override). settings 싱글톤으로 전역 사용."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """환경변수·.env로 주입되는 앱 설정 (서버/DB/MLflow/추론/CORS)."""
    ENV: str = "local"
    PORT: int = 3002
    RELOAD: bool = True

    SCENARIO_ID: str = "cs-myk-v3"

    DB_TYPE: str = "duckdb"
    DB_PATH: str = "roadshow_v3.duckdb"

    MLFLOW_URI: str = "sqlite:///mlflow_v3.db"
    MLFLOW_ARTIFACT_ROOT: str = "./mlruns_v3"

    TOP_N_INTENT: int = 5
    INTENT_SCORE_THRESHOLD: float = 0.05

    DATABRICKS_CATALOG: str = "main"
    DATABRICKS_SCHEMA: str = "roadshow_v3"

    # ── CORS ──────────────────────────────────────────────────
    # 쉼표로 구분된 origin 목록 (예: "https://x.pages.dev,https://y.vercel.app")
    # 빈 값이면 "*" 허용 (배포 환경 어디든)
    CORS_ORIGINS: str = ""

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    """Settings 싱글톤(캐시)."""
    return Settings()


settings = get_settings()
