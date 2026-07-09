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
    """DuckDB 단일 connection을 보호하는 wrapper.

    멀티스레드 환경에서 RLock으로 접근을 직렬화하여 thread-safe하게 동작한다.
    """

    def __init__(self, db_path: str) -> None:
        """DuckDB 연결을 열고 lock을 초기화한다.

        Args:
            db_path: 연결할 DuckDB 파일 경로.
        """
        self._db_path = db_path
        self._conn = duckdb.connect(db_path)
        self._lock = threading.RLock()
        logger.info(f"DuckDB connected: {db_path}")

    def execute(self, sql: str, params: Iterable[Any] | None = None) -> None:
        """SQL 1건을 실행한다 (lock 보호).

        Args:
            sql: 실행할 SQL 문.
            params: 바인딩 파라미터 (없으면 None).
        """
        with self._lock:
            if params is None:
                self._conn.execute(sql)
            else:
                self._conn.execute(sql, list(params))

    def executemany(self, sql: str, rows: list[list[Any]]) -> None:
        """다중 행을 일괄 실행한다 (lock 보호).

        Args:
            sql: 실행할 SQL 문.
            rows: 각 행의 바인딩 파라미터 목록.
        """
        with self._lock:
            self._conn.executemany(sql, rows)

    def to_pandas(self, sql: str, params: Iterable[Any] | None = None) -> pd.DataFrame:
        """SELECT 결과를 DataFrame으로 반환한다.

        Args:
            sql: 실행할 SELECT 문.
            params: 바인딩 파라미터 (없으면 None).

        Returns:
            조회 결과 DataFrame.
        """
        with self._lock:
            if params is None:
                return self._conn.execute(sql).df()
            else:
                return self._conn.execute(sql, list(params)).df()

    def fetchone(self, sql: str, params: Iterable[Any] | None = None) -> tuple | None:
        """첫 행 1건을 반환한다.

        Args:
            sql: 실행할 SELECT 문.
            params: 바인딩 파라미터 (없으면 None).

        Returns:
            첫 행 tuple, 결과가 없으면 None.
        """
        with self._lock:
            if params is None:
                return self._conn.execute(sql).fetchone()
            return self._conn.execute(sql, list(params)).fetchone()

    def fetchall(self, sql: str, params: Iterable[Any] | None = None) -> list[tuple]:
        """전체 행을 반환한다.

        Args:
            sql: 실행할 SELECT 문.
            params: 바인딩 파라미터 (없으면 None).

        Returns:
            전체 행 tuple의 목록.
        """
        with self._lock:
            if params is None:
                return self._conn.execute(sql).fetchall()
            return self._conn.execute(sql, list(params)).fetchall()

    def close(self) -> None:
        """connection을 종료한다."""
        with self._lock:
            self._conn.close()


_executor: DuckDBExecutor | None = None


def get_executor() -> DuckDBExecutor:
    """DuckDB Executor 싱글톤을 반환한다.

    최초 호출 시 settings.DB_PATH로 인스턴스를 생성하여 캐시한다.

    Returns:
        프로세스 전역 DuckDBExecutor 싱글톤.
    """
    global _executor
    if _executor is None:
        _executor = DuckDBExecutor(settings.DB_PATH)
    return _executor


def init_db() -> None:
    """스키마를 생성하고 카탈로그를 시드한다.

    schema.sql을 읽어 statement 단위로 실행한 뒤 카탈로그 시드를 수행한다.
    DuckDB는 multi-statement를 한 번에 받지 못하므로 ';' 기준으로 분리 실행한다.
    """
    ex = get_executor()
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        schema_sql = f.read()
    for stmt in [s.strip() for s in schema_sql.split(";") if s.strip()]:
        ex.execute(stmt)

    # 카탈로그 시드
    from data.seed import seed_catalogs
    seed_catalogs()
