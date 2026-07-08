"""seeds/*.sql로 시드한 인메모리 SQLite에서 ReferenceData를 로드하는 공용 테스트 픽스처.

운영과 동일한 경로(SQL 시드 → DB 조회)로 기준정보를 만들고, 서버 전역 캐시
server.REFERENCE도 같은 값으로 채워 dart·AI 분류처럼 캐시를 읽는 서버 함수도
테스트할 수 있게 한다. 로드는 한 번만 하고 모든 테스트가 읽기 전용으로 공유한다.
"""

import os
import sqlite3
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _candidate in (_HERE, os.path.dirname(_HERE)):
    if os.path.exists(os.path.join(_candidate, "server.py")):
        sys.path.insert(0, _candidate)
        break

import server  # noqa: E402


def seeded_connection() -> sqlite3.Connection:
    """스키마 생성 + 기준정보 시드(FK 순서)까지 마친 인메모리 DB 연결을 돌려준다."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(server.SQLITE_SCHEMA_PATH.read_text(encoding="utf-8"))
    server.ensure_reference_accounts(conn)
    server.ensure_checklist_items(conn)
    server.ensure_account_aliases(conn)
    server.ensure_statement_templates(conn)
    server.ensure_standards_paragraphs(conn)
    return conn


_cached = None


def load_reference():
    """시드된 DB에서 ReferenceData를 로드한다 (계약 검증 포함, 프로세스당 1회)."""
    global _cached
    if _cached is None:
        conn = seeded_connection()
        _cached = server.refresh_reference_cache(conn)
        conn.close()
    else:
        server.REFERENCE = _cached
    return _cached
