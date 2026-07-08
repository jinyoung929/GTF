"""SQLAlchemy 엔진·세션 (SQLite/Postgres 단일 경로).

이전에는 sqlite3 커넥션과 psycopg 어댑터(PostgresConnection)를 손으로 갈아끼우고
`?`/`%s` 플레이스홀더를 문자열 치환했다. SQLAlchemy 엔진 하나가 두 백엔드를 모두
처리하므로 그 어댑터 계층이 통째로 사라졌다.

DATABASE_BACKEND=postgres이면 DATABASE_URL(또는 NEON_DATABASE_URL)로, 아니면
로컬 SQLite 파일로 접속한다.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def database_url(sqlite_path: Path) -> str:
    """환경변수에서 SQLAlchemy 접속 URL을 만든다."""
    if backend() == "postgres":
        url = os.environ.get("DATABASE_URL") or os.environ.get("NEON_DATABASE_URL") or ""
        if not url:
            raise RuntimeError("DATABASE_BACKEND=postgres requires DATABASE_URL or NEON_DATABASE_URL.")
        if importlib.util.find_spec("psycopg") is None:
            raise RuntimeError("DATABASE_BACKEND=postgres requires psycopg. Run pip install -r requirements.txt.")
        # Render/Neon이 주는 postgres:// 스킴을 SQLAlchemy가 이해하는 psycopg 드라이버로 정규화
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url
    return f"sqlite:///{sqlite_path}"


def backend() -> str:
    return os.environ.get("DATABASE_BACKEND", "sqlite").strip().lower() or "sqlite"


def create_db_engine(sqlite_path: Path) -> Engine:
    url = database_url(sqlite_path)
    if url.startswith("sqlite"):
        # 여러 요청 스레드가 같은 파일 DB를 쓰므로 스레드 체크를 끄고 커넥션 풀에 맡긴다.
        engine = create_engine(url, connect_args={"check_same_thread": False}, future=True)

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record):
            # SQLite는 외래키 제약이 기본 비활성이라 연결마다 켜 준다 (Postgres는 항상 활성).
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    return create_engine(url, pool_pre_ping=True, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
