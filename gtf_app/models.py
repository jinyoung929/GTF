"""SQLAlchemy ORM 모델 (SQLite/Postgres 공용).

테이블 정의의 단일 출처다. Base.metadata.create_all(engine)이 두 백엔드 모두에서
스키마를 만들어 주므로 sqlite/schema.sql·postgres/schema.sql을 따로 관리하지 않는다.

시각 컬럼은 ISO8601 문자열(TEXT)로 저장한다. 두 백엔드가 타임존을 다르게 다루는 문제를
피하고, 감사 로그가 저장된 문자열 그대로 재현되도록 하기 위한 의도적 선택이다.
불리언은 SQLite에 0/1로, Postgres에 boolean으로 매핑된다(Boolean 타입이 흡수).
"""

from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, LargeBinary, String, Text, false, text, true
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# --- 인증 ---

class AppUser(Base):
    __tablename__ = "app_users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_read_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("app_users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[str] = mapped_column(String, nullable=False)


# --- 변환 워크플로 ---

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    source_standard: Mapped[str] = mapped_column(String, nullable=False)
    target_standard: Mapped[str] = mapped_column(String, nullable=False)
    period: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class Statement(Base):
    __tablename__ = "statements"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"), nullable=False, index=True)
    account_name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_account: Mapped[str] = mapped_column(String, nullable=False)
    standard_code: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    period: Mapped[str] = mapped_column(String, nullable=False)
    mapping_type: Mapped[str] = mapped_column(String, nullable=False)
    rule_summary: Mapped[str] = mapped_column(Text, nullable=False)
    checklist_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"), nullable=False, index=True)
    original_name: Mapped[str] = mapped_column(String, nullable=False)
    stored_name: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    file_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"), nullable=False, index=True)
    upload_id: Mapped[str] = mapped_column(String, ForeignKey("uploads.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    rows_json: Mapped[str] = mapped_column(Text, nullable=False)
    issues_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class Conversion(Base):
    __tablename__ = "conversions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"), nullable=False, index=True)
    output_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"), nullable=False, index=True)
    reviewer_name: Mapped[str] = mapped_column(String, nullable=False)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    memo: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    detail_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


# --- 기준정보 (seeds/*.sql이 데이터의 단일 출처) ---

class StandardAccount(Base):
    __tablename__ = "standard_accounts"

    account_key: Mapped[str] = mapped_column(String, primary_key=True)
    standard_code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    internal_label: Mapped[str] = mapped_column(String, nullable=False)
    ifrs_account: Mapped[str] = mapped_column(String, nullable=False)
    mapping_type: Mapped[str] = mapped_column(String, nullable=False)
    rule_summary: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class KgaapAccount(Base):
    """K-GAAP 계정명 별칭. match_priority(별칭 길이)가 큰 것부터 부분문자열 매칭한다."""

    __tablename__ = "kgaap_accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_key: Mapped[str] = mapped_column(String, ForeignKey("standard_accounts.account_key"), nullable=False)
    kgaap_name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    match_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))


class IfrsAccount(Base):
    __tablename__ = "ifrs_accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_key: Mapped[str] = mapped_column(String, ForeignKey("standard_accounts.account_key"), nullable=False)
    ifrs_name: Mapped[str] = mapped_column(String, nullable=False)
    standard_ref: Mapped[str] = mapped_column(Text, nullable=False)
    recognition_summary: Mapped[str] = mapped_column(Text, nullable=False)
    measurement_summary: Mapped[str] = mapped_column(Text, nullable=False)
    disclosure_summary: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())


class MappingRule(Base):
    __tablename__ = "mapping_rules"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_key: Mapped[str] = mapped_column(String, ForeignKey("standard_accounts.account_key"), nullable=False)
    source_standard: Mapped[str] = mapped_column(String, nullable=False)
    target_standard: Mapped[str] = mapped_column(String, nullable=False)
    mapping_type: Mapped[str] = mapped_column(String, nullable=False)
    rule_summary: Mapped[str] = mapped_column(Text, nullable=False)
    checklist_json: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class ChecklistItem(Base):
    """판단 필요 계정의 체크리스트. item_key는 계산기가 읽는 계약이라 코드와 일치해야 한다."""

    __tablename__ = "checklist_items"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_key: Mapped[str] = mapped_column(String, ForeignKey("standard_accounts.account_key"), nullable=False)
    item_key: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    input_type: Mapped[str] = mapped_column(String, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)


class StandardsReference(Base):
    __tablename__ = "standards_references"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    standard_set: Mapped[str] = mapped_column(String, nullable=False)
    reference_code: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)


class FinancialStatementTemplate(Base):
    __tablename__ = "financial_statement_templates"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    standard_set: Mapped[str] = mapped_column(String, nullable=False)
    statement_type: Mapped[str] = mapped_column(String, nullable=False)
    section: Mapped[str] = mapped_column(String, nullable=False)
    line_item: Mapped[str] = mapped_column(String, nullable=False)
    account_key: Mapped[str] = mapped_column(String, ForeignKey("standard_accounts.account_key"), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    basis: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())


class StandardsParagraph(Base):
    """RAG 검색 코퍼스. embedding은 이식성을 위해 JSON 텍스트로 저장한다(pgvector 미사용)."""

    __tablename__ = "standards_paragraphs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    standard_set: Mapped[str] = mapped_column(String, nullable=False)
    reference_code: Mapped[str] = mapped_column(String, nullable=False)
    paragraph_label: Mapped[str] = mapped_column(String, nullable=False)
    account_key: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String, nullable=True)
