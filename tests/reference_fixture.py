"""seeds/*.sql로 시드한 인메모리 DB에서 ReferenceData를 로드하는 공용 테스트 픽스처.

운영과 동일한 경로(ORM 스키마 생성 → SQL 시드 → DB 조회)로 기준정보를 만들고, 서버 전역
캐시 server.REFERENCE도 같은 값으로 채워 dart·AI 분류처럼 캐시를 읽는 서버 함수도
테스트할 수 있게 한다. 로드는 한 번만 하고 모든 테스트가 읽기 전용으로 공유한다.
"""

import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_HERE = os.path.dirname(os.path.abspath(__file__))
for _candidate in (_HERE, os.path.dirname(_HERE)):
    if os.path.exists(os.path.join(_candidate, "server.py")):
        sys.path.insert(0, _candidate)
        break

import server  # noqa: E402
from gtf_app.models import Base  # noqa: E402


def memory_session() -> Session:
    """ORM 스키마만 만든 빈 인메모리 세션."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def paragraph_session() -> Session:
    """기준서 문단만 시드한 인메모리 세션 (RAG·검색 테스트용)."""
    session = memory_session()
    server.ensure_standards_paragraphs(session)
    return session


def seeded_session() -> Session:
    """스키마 생성 + 기준정보 시드(FK 순서)까지 마친 인메모리 세션을 돌려준다."""
    session = memory_session()
    server.ensure_reference_accounts(session)
    server.ensure_checklist_items(session)
    server.ensure_account_aliases(session)
    server.ensure_statement_templates(session)
    server.ensure_standards_paragraphs(session)
    return session


_cached = None


def load_reference():
    """시드된 DB에서 ReferenceData를 로드한다 (계약 검증 포함, 프로세스당 1회)."""
    global _cached
    if _cached is None:
        session = seeded_session()
        _cached = server.refresh_reference_cache(session)
        session.close()
    else:
        server.REFERENCE = _cached
    return _cached
