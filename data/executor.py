from __future__ import annotations
"""
DuckDB Executor (싱글톤)
"""
import logging
import threading
from pathlib import Path
from typing import Any, Iterable

import duckdb
import pandas as pd

from config import settings

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class DuckDBExecutor:
    """
    DuckDB 단일 connection 보호 wrapper.
    멀티스레드 환경에서 쓰기 lock 보호.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = duckdb.connect(db_path)
        self._lock = threading.RLock()
        logger.info(f"DuckDB connected: {db_path}")

    def execute(self, sql: str, params: Iterable[Any] | None = None) -> None:
        """SQL 1건 실행 (lock 보호)."""
        with self._lock:
            if params is None:
                self._conn.execute(sql)
            else:
                self._conn.execute(sql, list(params))

    def executemany(self, sql: str, rows: list[list[Any]]) -> None:
        """다중 행 일괄 실행 (lock 보호)."""
        with self._lock:
            self._conn.executemany(sql, rows)

    def to_pandas(self, sql: str, params: Iterable[Any] | None = None) -> pd.DataFrame:
        """SELECT 결과를 DataFrame으로 반환."""
        with self._lock:
            if params is None:
                return self._conn.execute(sql).df()
            else:
                return self._conn.execute(sql, list(params)).df()

    def fetchone(self, sql: str, params: Iterable[Any] | None = None) -> tuple | None:
        """첫 행 1건 반환 (없으면 None)."""
        with self._lock:
            if params is None:
                return self._conn.execute(sql).fetchone()
            return self._conn.execute(sql, list(params)).fetchone()

    def fetchall(self, sql: str, params: Iterable[Any] | None = None) -> list[tuple]:
        """전체 행 반환."""
        with self._lock:
            if params is None:
                return self._conn.execute(sql).fetchall()
            return self._conn.execute(sql, list(params)).fetchall()

    def close(self) -> None:
        """connection 종료."""
        with self._lock:
            self._conn.close()


_executor: DuckDBExecutor | None = None


def get_executor() -> DuckDBExecutor:
    """DuckDB Executor 싱글톤."""
    global _executor
    if _executor is None:
        _executor = DuckDBExecutor(settings.DB_PATH)
    return _executor


def init_db() -> None:
    """스키마 생성 + 카탈로그 시드"""
    ex = get_executor()
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        schema_sql = f.read()
    # DuckDB는 multi-statement를 한 번에 못 받음. 분리 실행.
    for stmt in [s.strip() for s in schema_sql.split(";") if s.strip()]:
        ex.execute(stmt)

    # 카탈로그 시드
    from data.seed import seed_catalogs
    seed_catalogs()
