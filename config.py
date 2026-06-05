from __future__ import annotations
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
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
    return Settings()


settings = get_settings()
