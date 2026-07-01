from __future__ import annotations

import csv
import base64
import hmac
import io
import importlib.util
import json
import mimetypes
import os
import re
import sqlite3
import uuid
import zipfile
from decimal import Decimal
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import xml.etree.ElementTree as ET
from urllib import error as url_error
from urllib import request as url_request
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "gtf.sqlite3"
ENV_PATHS = (ROOT / ".env", ROOT / ".env.local")
GEMINI_INLINE_LIMIT_BYTES = 20 * 1024 * 1024
CLAUDE_API_ENDPOINT = "https://api.anthropic.com/v1/messages"
CLAUDE_DEFAULT_MODEL = "claude-sonnet-5"


def load_local_env() -> None:
    for env_path in ENV_PATHS:
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


load_local_env()


STANDARD_ACCOUNTS = {
    "cash": {
        "code": "A1000",
        "label": "현금및현금성자산",
        "ifrs": "Cash and cash equivalents",
        "type": "simple",
        "rule": "사용 제한 여부를 확인한 뒤 현금및현금성자산으로 단순 매핑합니다.",
    },
    "receivables": {
        "code": "A1100",
        "label": "매출채권",
        "ifrs": "Trade and other receivables",
        "type": "judgment",
        "rule": "IFRS 9 기준에 따라 매출채권 분류와 기대신용손실 충당금을 검토합니다.",
    },
    "inventory": {
        "code": "A1200",
        "label": "재고자산",
        "ifrs": "Inventories",
        "type": "simple",
        "rule": "IAS 2 재고자산으로 매핑하고 원가와 순실현가능가치 비교를 검토합니다.",
    },
    "lease": {
        "code": "A2100",
        "label": "리스",
        "ifrs": "Right-of-use asset and lease liability",
        "type": "judgment",
        "rule": "IFRS 16 측정을 위해 리스기간, 지급액, 선택권, 할인율을 추가 확인합니다.",
    },
    "development": {
        "code": "A3100",
        "label": "개발비",
        "ifrs": "Intangible assets or R&D expense",
        "type": "judgment",
        "rule": "IAS 38 개발단계 자산화 요건 충족 여부를 검토합니다.",
    },
    "revenue": {
        "code": "R1000",
        "label": "수익",
        "ifrs": "Revenue from contracts with customers",
        "type": "judgment",
        "rule": "IFRS 15 기준에 따라 수행의무와 수익인식 시점을 확인합니다.",
    },
    "financial_instrument": {
        "code": "F1000",
        "label": "금융상품",
        "ifrs": "Financial assets/liabilities",
        "type": "judgment",
        "rule": "IFRS 9 기준에 따라 사업모형과 계약상 현금흐름 특성을 검토합니다.",
    },
    "provision": {
        "code": "L2200",
        "label": "충당부채",
        "ifrs": "Provisions and contingencies",
        "type": "judgment",
        "rule": "IAS 37 기준에 따라 현재의무, 유출가능성, 신뢰성 있는 추정 여부를 검토합니다.",
    },
    "other": {
        "code": "X9999",
        "label": "미분류 계정",
        "ifrs": "Review required",
        "type": "judgment",
        "rule": "자동 매핑 신뢰도가 낮아 담당자 분류 검토가 필요합니다.",
    },
}


FINANCIAL_STATEMENT_TEMPLATES = [
    {
        "id": "ifrs_bs_cash",
        "standard_set": "IFRS",
        "statement_type": "재무상태표",
        "section": "유동자산",
        "line_item": "현금및현금성자산",
        "account_key": "cash",
        "display_order": 10,
        "basis": "IAS 7 표시 목적의 현금및현금성자산 라인입니다.",
    },
    {
        "id": "ifrs_bs_receivables",
        "standard_set": "IFRS",
        "statement_type": "재무상태표",
        "section": "유동자산",
        "line_item": "매출채권 및 기타채권",
        "account_key": "receivables",
        "display_order": 20,
        "basis": "IFRS 9 기대신용손실 검토 후 채권 라인에 표시합니다.",
    },
    {
        "id": "ifrs_bs_inventory",
        "standard_set": "IFRS",
        "statement_type": "재무상태표",
        "section": "유동자산",
        "line_item": "재고자산",
        "account_key": "inventory",
        "display_order": 30,
        "basis": "IAS 2에 따라 원가와 순실현가능가치를 검토한 뒤 표시합니다.",
    },
    {
        "id": "ifrs_bs_lease_asset",
        "standard_set": "IFRS",
        "statement_type": "재무상태표",
        "section": "비유동자산/부채",
        "line_item": "사용권자산 및 리스부채",
        "account_key": "lease",
        "display_order": 90,
        "basis": "IFRS 16에 따라 사용권자산과 리스부채 표시를 검토합니다.",
    },
    {
        "id": "ifrs_bs_development",
        "standard_set": "IFRS",
        "statement_type": "재무상태표 또는 손익계산서",
        "section": "무형자산/비용",
        "line_item": "무형자산 또는 연구개발비",
        "account_key": "development",
        "display_order": 100,
        "basis": "IAS 38 개발단계 자산화 요건에 따라 표시 라인이 달라집니다.",
    },
    {
        "id": "ifrs_bs_financial_instrument",
        "standard_set": "IFRS",
        "statement_type": "재무상태표",
        "section": "금융자산/금융부채",
        "line_item": "금융자산 또는 금융부채",
        "account_key": "financial_instrument",
        "display_order": 110,
        "basis": "IFRS 9 분류 결과에 따라 금융자산 또는 금융부채로 표시합니다.",
    },
    {
        "id": "ifrs_bs_provision",
        "standard_set": "IFRS",
        "statement_type": "재무상태표",
        "section": "부채",
        "line_item": "충당부채",
        "account_key": "provision",
        "display_order": 120,
        "basis": "IAS 37 인식요건을 충족하면 충당부채로 표시합니다.",
    },
    {
        "id": "ifrs_pl_revenue",
        "standard_set": "IFRS",
        "statement_type": "손익계산서",
        "section": "수익",
        "line_item": "고객과의 계약에서 생기는 수익",
        "account_key": "revenue",
        "display_order": 10,
        "basis": "IFRS 15 수행의무와 인식시점 검토 후 수익 라인에 표시합니다.",
    },
    {
        "id": "ifrs_review_required",
        "standard_set": "IFRS",
        "statement_type": "검토 필요",
        "section": "미분류",
        "line_item": "검토자 분류 필요",
        "account_key": "other",
        "display_order": 999,
        "basis": "내부 표준계정 매핑 신뢰도가 낮아 사람이 표시 라인을 확정합니다.",
    },
]


CHECKLISTS = {
    "lease": [
        {"key": "lease_term_months", "label": "리스기간(개월)", "type": "number", "required": True},
        {"key": "monthly_payment", "label": "월 리스료", "type": "number", "required": True},
        {"key": "discount_rate", "label": "증분차입이자율(%)", "type": "number", "required": True},
        {"key": "renewal_option", "label": "연장선택권 행사가 상당히 확실한가?", "type": "boolean", "required": False},
    ],
    "development": [
        {"key": "technical_feasibility", "label": "기술적 실현가능성이 입증되었는가?", "type": "boolean", "required": True},
        {"key": "intention_to_complete", "label": "완성 의도와 능력이 있는가?", "type": "boolean", "required": True},
        {"key": "probable_future_benefits", "label": "미래경제적효익이 개연적인가?", "type": "boolean", "required": True},
        {"key": "reliable_measurement", "label": "원가를 신뢰성 있게 측정할 수 있는가?", "type": "boolean", "required": True},
    ],
    "revenue": [
        {"key": "contract_type", "label": "계약 유형", "type": "text", "required": True},
        {"key": "performance_obligations", "label": "수행의무", "type": "text", "required": True},
        {"key": "recognition_timing", "label": "한 시점 또는 기간에 걸친 인식", "type": "text", "required": True},
        {"key": "variable_consideration", "label": "변동대가가 있는가?", "type": "boolean", "required": False},
    ],
    "financial_instrument": [
        {"key": "instrument_terms", "label": "주요 계약조건", "type": "text", "required": True},
        {"key": "business_model", "label": "보유 사업모형", "type": "text", "required": True},
        {"key": "sppi_passed", "label": "원금과 이자 지급만으로 구성된 현금흐름(SPPI) 요건을 충족하는가?", "type": "boolean", "required": True},
    ],
    "provision": [
        {"key": "present_obligation", "label": "현재의무가 존재하는가?", "type": "boolean", "required": True},
        {"key": "probable_outflow", "label": "자원 유출 가능성이 높은가?", "type": "boolean", "required": True},
        {"key": "reliable_estimate", "label": "금액을 신뢰성 있게 추정할 수 있는가?", "type": "boolean", "required": True},
    ],
    "receivables": [
        {"key": "credit_risk_method", "label": "기대신용손실 산정 방식", "type": "text", "required": True},
        {"key": "aging_available", "label": "연령분석표가 있는가?", "type": "boolean", "required": True},
    ],
    "other": [
        {"key": "management_memo", "label": "경영진 분류 메모", "type": "text", "required": True},
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def database_config() -> dict:
    backend = os.environ.get("DATABASE_BACKEND", "sqlite").strip().lower() or "sqlite"
    database_url = os.environ.get("DATABASE_URL") or os.environ.get("NEON_DATABASE_URL") or ""
    postgres_driver_ready = importlib.util.find_spec("psycopg") is not None
    return {
        "backend": backend,
        "sqlite_path": str(DB_PATH),
        "sqlite_ready": DB_PATH.exists(),
        "database_url_ready": bool(database_url),
        "postgres_driver_ready": postgres_driver_ready,
        "postgres_ready": backend == "postgres" and bool(database_url) and postgres_driver_ready,
    }


def normalize_db_value(value):
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [normalize_db_value(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_db_value(item) for key, item in value.items()}
    return value


def parse_json_field(value, fallback):
    if value is None:
        return fallback
    if isinstance(value, (list, dict)):
        return normalize_db_value(value)
    if isinstance(value, str):
        return json.loads(value)
    return value


def postgres_param(value):
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                from psycopg.types.json import Jsonb

                return Jsonb(json.loads(stripped))
            except (ImportError, json.JSONDecodeError):
                return value
    return value


class PostgresConnection:
    def __init__(self, database_url: str):
        import psycopg
        from psycopg.rows import dict_row

        self.connection = psycopg.connect(database_url, row_factory=dict_row)

    def __enter__(self):
        self.connection.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        return self.connection.__exit__(exc_type, exc, tb)

    def execute(self, sql: str, params: tuple | list = ()):
        translated = sql.replace("?", "%s")
        converted = tuple(postgres_param(value) for value in params)
        cursor = self.connection.cursor()
        cursor.execute(translated, converted)
        return cursor

    def executescript(self, _script: str):
        raise RuntimeError("Postgres schema must be initialized with postgres/schema.sql before starting the app.")


def connect():
    config = database_config()
    if config["backend"] == "postgres":
        if not config["database_url_ready"]:
            raise RuntimeError("DATABASE_BACKEND=postgres requires DATABASE_URL or NEON_DATABASE_URL.")
        if not config["postgres_driver_ready"]:
            raise RuntimeError("DATABASE_BACKEND=postgres requires psycopg. Run pip install -r requirements.txt.")
        return PostgresConnection(os.environ.get("DATABASE_URL") or os.environ.get("NEON_DATABASE_URL") or "")
    if config["backend"] != "sqlite":
        raise RuntimeError(f"Unsupported DATABASE_BACKEND: {config['backend']}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    UPLOAD_DIR.mkdir(exist_ok=True)
    if database_config()["backend"] == "postgres":
        with connect() as conn:
            conn.execute("SELECT 1")
        return
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                company_name TEXT NOT NULL,
                source_standard TEXT NOT NULL,
                target_standard TEXT NOT NULL,
                period TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS statements (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                account_name TEXT NOT NULL,
                normalized_account TEXT NOT NULL,
                standard_code TEXT NOT NULL,
                amount REAL NOT NULL,
                period TEXT NOT NULL,
                mapping_type TEXT NOT NULL,
                rule_summary TEXT NOT NULL,
                checklist_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS uploads (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                extraction_status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS extractions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                upload_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                status TEXT NOT NULL,
                rows_json TEXT NOT NULL,
                issues_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(upload_id) REFERENCES uploads(id)
            );

            CREATE TABLE IF NOT EXISTS conversions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                output_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                reviewer_name TEXT NOT NULL,
                decision TEXT NOT NULL,
                memo TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                detail_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS standard_accounts (
                account_key TEXT PRIMARY KEY,
                standard_code TEXT NOT NULL UNIQUE,
                internal_label TEXT NOT NULL,
                ifrs_account TEXT NOT NULL,
                mapping_type TEXT NOT NULL,
                rule_summary TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS kgaap_accounts (
                id TEXT PRIMARY KEY,
                account_key TEXT NOT NULL,
                kgaap_name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(account_key) REFERENCES standard_accounts(account_key)
            );

            CREATE TABLE IF NOT EXISTS ifrs_accounts (
                id TEXT PRIMARY KEY,
                account_key TEXT NOT NULL,
                ifrs_name TEXT NOT NULL,
                standard_ref TEXT NOT NULL,
                recognition_summary TEXT NOT NULL,
                measurement_summary TEXT NOT NULL,
                disclosure_summary TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(account_key) REFERENCES standard_accounts(account_key)
            );

            CREATE TABLE IF NOT EXISTS mapping_rules (
                id TEXT PRIMARY KEY,
                account_key TEXT NOT NULL,
                source_standard TEXT NOT NULL,
                target_standard TEXT NOT NULL,
                mapping_type TEXT NOT NULL,
                rule_summary TEXT NOT NULL,
                checklist_json TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(account_key) REFERENCES standard_accounts(account_key)
            );

            CREATE TABLE IF NOT EXISTS checklist_items (
                id TEXT PRIMARY KEY,
                account_key TEXT NOT NULL,
                item_key TEXT NOT NULL,
                label TEXT NOT NULL,
                input_type TEXT NOT NULL,
                required INTEGER NOT NULL,
                display_order INTEGER NOT NULL,
                FOREIGN KEY(account_key) REFERENCES standard_accounts(account_key)
            );

            CREATE TABLE IF NOT EXISTS standards_references (
                id TEXT PRIMARY KEY,
                standard_set TEXT NOT NULL,
                reference_code TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS financial_statement_templates (
                id TEXT PRIMARY KEY,
                standard_set TEXT NOT NULL,
                statement_type TEXT NOT NULL,
                section TEXT NOT NULL,
                line_item TEXT NOT NULL,
                account_key TEXT NOT NULL,
                display_order INTEGER NOT NULL,
                basis TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(account_key) REFERENCES standard_accounts(account_key)
            );
            """
        )
        seed_reference_data(conn)


def seed_reference_data(conn: sqlite3.Connection) -> None:
    now = utc_now()
    aliases = {
        "cash": ["현금및현금성자산", "현금", "예금", "보통예금"],
        "receivables": ["매출채권", "외상매출금", "받을어음"],
        "inventory": ["재고자산", "상품", "제품", "원재료"],
        "lease": ["리스부채", "사용권자산", "리스"],
        "development": ["개발비", "개발원가", "무형자산개발비"],
        "revenue": ["매출", "수익", "제품매출", "용역매출"],
        "financial_instrument": ["전환사채", "금융상품", "파생상품", "상환전환우선주"],
        "provision": ["충당부채", "판매보증충당부채", "복구충당부채"],
        "other": ["미분류 계정"],
    }
    standard_refs = {
        "cash": ("IAS 7", "현금및현금성자산", "사용 제한 여부와 현금성자산 요건을 확인합니다."),
        "receivables": ("IFRS 9", "매출채권", "분류와 기대신용손실 충당금을 검토합니다."),
        "inventory": ("IAS 2", "재고자산", "원가와 순실현가능가치 비교를 검토합니다."),
        "lease": ("IFRS 16", "리스", "리스기간, 지급액, 선택권, 할인율을 확인합니다."),
        "development": ("IAS 38", "개발비", "개발단계 자산화 요건 충족 여부를 검토합니다."),
        "revenue": ("IFRS 15", "수익", "수행의무와 수익인식 시점을 확인합니다."),
        "financial_instrument": ("IFRS 9", "금융상품", "사업모형과 계약상 현금흐름 특성을 검토합니다."),
        "provision": ("IAS 37", "충당부채", "현재의무, 유출가능성, 신뢰성 있는 추정을 검토합니다."),
        "other": ("Manual Review", "미분류 계정", "담당자 분류 검토가 필요합니다."),
    }

    for account_key, account in STANDARD_ACCOUNTS.items():
        conn.execute(
            """
            INSERT OR REPLACE INTO standard_accounts (
                account_key, standard_code, internal_label, ifrs_account, mapping_type, rule_summary, active, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                account_key,
                account["code"],
                account["label"],
                account["ifrs"],
                account["type"],
                account["rule"],
                now,
            ),
        )
        for index, alias in enumerate(aliases.get(account_key, [account["label"]]), start=1):
            conn.execute(
                """
                INSERT OR REPLACE INTO kgaap_accounts (id, account_key, kgaap_name, normalized_name, active)
                VALUES (?, ?, ?, ?, 1)
                """,
                (f"{account_key}_{index}", account_key, alias, account["label"]),
            )
        ref_code, title, summary = standard_refs[account_key]
        conn.execute(
            """
            INSERT OR REPLACE INTO ifrs_accounts (
                id, account_key, ifrs_name, standard_ref, recognition_summary,
                measurement_summary, disclosure_summary, active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                account_key,
                account_key,
                account["ifrs"],
                ref_code,
                summary,
                account["rule"],
                "검토 결과와 주요 판단 근거를 주석 초안에 반영합니다.",
            ),
        )
        checklist = CHECKLISTS.get(account_key, [])
        conn.execute(
            """
            INSERT OR REPLACE INTO mapping_rules (
                id, account_key, source_standard, target_standard, mapping_type,
                rule_summary, checklist_json, active, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                f"{account_key}_kgaap_ifrs",
                account_key,
                "K-GAAP",
                "IFRS",
                account["type"],
                account["rule"],
                json.dumps(checklist, ensure_ascii=False),
                now,
            ),
        )
        conn.execute("DELETE FROM checklist_items WHERE account_key = ?", (account_key,))
        for order, item in enumerate(checklist, start=1):
            conn.execute(
                """
                INSERT INTO checklist_items (
                    id, account_key, item_key, label, input_type, required, display_order
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{account_key}_{item['key']}",
                    account_key,
                    item["key"],
                    item["label"],
                    item["type"],
                    1 if item.get("required") else 0,
                    order,
                ),
            )

    references = sorted({standard_refs[key][0] for key in standard_refs})
    for ref in references:
        conn.execute(
            """
            INSERT OR REPLACE INTO standards_references (id, standard_set, reference_code, title, summary)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ref.lower().replace(" ", "_"), "IFRS", ref, ref, "기준서 원문 연결 전까지 요약 기준정보로 사용합니다."),
        )

    for template in FINANCIAL_STATEMENT_TEMPLATES:
        conn.execute(
            """
            INSERT OR REPLACE INTO financial_statement_templates (
                id, standard_set, statement_type, section, line_item, account_key,
                display_order, basis, active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                template["id"],
                template["standard_set"],
                template["statement_type"],
                template["section"],
                template["line_item"],
                template["account_key"],
                template["display_order"],
                template["basis"],
            ),
        )


def row_to_dict(row) -> dict:
    return {key: normalize_db_value(row[key]) for key in row.keys()}


def database_ready() -> bool:
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def log_event(conn: sqlite3.Connection, project_id: str, event_type: str, detail: dict, actor: str = "system") -> None:
    conn.execute(
        """
        INSERT INTO audit_logs (id, project_id, event_type, actor, detail_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), project_id, event_type, actor, json.dumps(detail, ensure_ascii=False), utc_now()),
    )


def normalize_account_name(name: str) -> str:
    text = re.sub(r"\s+", " ", name.strip().lower())
    replacements = {
        "현금및현금성자산": "cash",
        "현금": "cash",
        "cash": "cash",
        "매출채권": "receivables",
        "trade receivable": "receivables",
        "재고자산": "inventory",
        "inventory": "inventory",
        "리스": "lease",
        "사용권자산": "lease",
        "lease": "lease",
        "개발비": "development",
        "development": "development",
        "매출": "revenue",
        "수익": "revenue",
        "revenue": "revenue",
        "금융상품": "financial_instrument",
        "파생상품": "financial_instrument",
        "전환사채": "financial_instrument",
        "충당부채": "provision",
        "provision": "provision",
    }
    compact = text.replace(" ", "")
    for needle, account_key in replacements.items():
        if needle in compact or needle in text:
            return account_key
    return "other"


def parse_statement_rows(payload: dict) -> list[dict]:
    rows = []
    if isinstance(payload.get("rows"), list):
        rows = payload["rows"]
    elif payload.get("csv_text"):
        reader = csv.DictReader(io.StringIO(payload["csv_text"]))
        rows = list(reader)

    parsed = []
    for raw in rows:
        name = str(raw.get("account_name") or raw.get("account") or raw.get("계정명") or "").strip()
        if not name:
            continue
        amount = parse_amount(raw.get("amount") or raw.get("금액") or 0)
        parsed.append({"account_name": name, "amount": amount})
    return parsed


def parse_amount(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "0").strip()
    is_negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if cleaned in {"", "-", ".", "-."}:
        return 0.0
    amount = float(cleaned)
    return -abs(amount) if is_negative else amount


def looks_numeric(value) -> bool:
    if isinstance(value, (int, float)):
        return True
    text = str(value or "").strip()
    if not text:
        return False
    return bool(re.fullmatch(r"\(?-?[\d,]+(?:\.\d+)?\)?", text.replace(" ", "")))


def xlsx_col_index(cell_ref: str) -> int:
    letters = re.sub(r"[^A-Z]", "", cell_ref.upper())
    index = 0
    for letter in letters:
        index = index * 26 + (ord(letter) - ord("A") + 1)
    return max(index - 1, 0)


def xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings = []
    for item in root.findall("x:si", ns):
        pieces = [node.text or "" for node in item.findall(".//x:t", ns)]
        strings.append("".join(pieces))
    return strings


def xlsx_first_sheet_path(archive: zipfile.ZipFile) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    ns = {
        "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    }
    sheet = workbook.find("x:sheets/x:sheet", ns)
    if sheet is None:
        raise ValueError("Excel 파일에서 워크시트를 찾지 못했습니다.")
    rel_id = sheet.attrib.get(f"{{{ns['r']}}}id")
    for rel in rels.findall("rel:Relationship", ns):
        if rel.attrib.get("Id") == rel_id:
            target = rel.attrib.get("Target", "")
            return "xl/" + target.lstrip("/") if not target.startswith("xl/") else target
    raise ValueError("Excel 워크시트 관계 정보를 찾지 못했습니다.")


def xlsx_cell_value(cell: ET.Element, shared_strings: list[str], ns: dict) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        pieces = [node.text or "" for node in cell.findall(".//x:t", ns)]
        return "".join(pieces).strip()
    value_node = cell.find("x:v", ns)
    value = value_node.text if value_node is not None else ""
    if cell_type == "s" and value != "":
        index = int(float(value))
        return shared_strings[index].strip() if 0 <= index < len(shared_strings) else ""
    return str(value or "").strip()


def read_xlsx_table(path: Path) -> list[list[str]]:
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        shared_strings = xlsx_shared_strings(archive)
        sheet_path = xlsx_first_sheet_path(archive)
        root = ET.fromstring(archive.read(sheet_path))
    table = []
    for row in root.findall(".//x:sheetData/x:row", ns):
        values = []
        for cell in row.findall("x:c", ns):
            index = xlsx_col_index(cell.attrib.get("r", "A1"))
            while len(values) <= index:
                values.append("")
            values[index] = xlsx_cell_value(cell, shared_strings, ns)
        table.append(values)
    return table


def parse_xlsx_statement_rows(path: Path) -> tuple[list[dict], list[str]]:
    table = read_xlsx_table(path)
    rows = []
    issues = []
    header = None
    account_index = None
    amount_index = None

    for row_index, row in enumerate(table):
        compact = [str(cell).strip() for cell in row]
        lowered = [cell.replace(" ", "").lower() for cell in compact]
        account_candidates = [i for i, cell in enumerate(lowered) if cell in {"계정명", "계정", "account", "accountname"}]
        amount_candidates = [i for i, cell in enumerate(lowered) if cell in {"금액", "amount", "당기", "current"}]
        if account_candidates and amount_candidates:
            header = row_index
            account_index = account_candidates[0]
            amount_index = amount_candidates[-1]
            break

    data_rows = table[header + 1 :] if header is not None else table
    for row in data_rows:
        compact = [str(cell).strip() for cell in row]
        if not any(compact):
            continue
        if account_index is not None and amount_index is not None and len(compact) > max(account_index, amount_index):
            name = compact[account_index]
            amount_value = compact[amount_index]
        else:
            text_cells = [cell for cell in compact if cell and not looks_numeric(cell)]
            numeric_cells = [cell for cell in compact if looks_numeric(cell)]
            if not text_cells or not numeric_cells:
                continue
            name = text_cells[0]
            amount_value = numeric_cells[-1]
        if not name or "계정" in name.replace(" ", "") or "금액" == name.replace(" ", ""):
            continue
        rows.append({"account_name": name, "amount": parse_amount(amount_value)})

    if not rows:
        issues.append("Excel 파일은 읽었지만 계정명/금액 행을 찾지 못했습니다.")
    return rows, issues


def build_statement_record(project_period: str, row: dict) -> dict:
    account_key = normalize_account_name(row["account_name"])
    standard = STANDARD_ACCOUNTS[account_key]
    checklist = CHECKLISTS.get(account_key, []) if standard["type"] == "judgment" else []
    return {
        "id": str(uuid.uuid4()),
        "account_name": row["account_name"],
        "normalized_account": standard["label"],
        "standard_code": standard["code"],
        "amount": row["amount"],
        "period": project_period,
        "mapping_type": standard["type"],
        "rule_summary": standard["rule"],
        "checklist": checklist,
        "ifrs_account": standard["ifrs"],
    }


def validate_statement_records(project: dict, statements: list[sqlite3.Row]) -> dict:
    total = sum(float(row["amount"]) for row in statements)
    judgment_count = sum(1 for row in statements if row["mapping_type"] == "judgment")
    simple_count = sum(1 for row in statements if row["mapping_type"] == "simple")
    issues = []
    warnings = []
    checks = []

    def add_check(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    if not statements:
        issues.append("업로드되거나 매핑된 계정 행이 없습니다.")
        add_check("계정 행", "error", "검증할 계정 데이터가 없습니다.")
        return {
            "row_count": 0,
            "total_amount": 0,
            "judgment_count": 0,
            "simple_count": 0,
            "issues": issues,
            "warnings": warnings,
            "checks": checks,
            "status": "failed",
        }

    add_check("계정 행", "pass", f"{len(statements)}개 계정 행을 확인했습니다.")

    zero_rows = [row["account_name"] for row in statements if abs(float(row["amount"])) < 1]
    if zero_rows:
        warnings.append(f"금액이 0인 계정이 있습니다: {', '.join(zero_rows[:5])}")
        add_check("금액 누락", "warning", f"{len(zero_rows)}개 계정의 금액이 0입니다.")
    else:
        add_check("금액 누락", "pass", "0 또는 빈 금액으로 보이는 계정이 없습니다.")

    normalized_names = [row["normalized_account"] for row in statements]
    duplicate_names = sorted({name for name in normalized_names if normalized_names.count(name) > 1})
    if duplicate_names:
        warnings.append(f"동일 표준계정으로 중복 매핑된 항목이 있습니다: {', '.join(duplicate_names[:5])}")
        add_check("중복 매핑", "warning", f"{len(duplicate_names)}개 표준계정에 복수 행이 매핑되었습니다.")
    else:
        add_check("중복 매핑", "pass", "동일 표준계정 중복 매핑이 없습니다.")

    unmapped = [row["account_name"] for row in statements if row["standard_code"] == "X9999"]
    if unmapped:
        issues.append(f"미분류 계정이 있습니다: {', '.join(unmapped[:5])}")
        add_check("미분류 계정", "error", f"{len(unmapped)}개 계정은 담당자 분류가 필요합니다.")
    else:
        add_check("미분류 계정", "pass", "모든 계정이 내부 표준코드에 연결되었습니다.")

    mismatched_periods = sorted({row["period"] for row in statements if row["period"] != project["period"]})
    if mismatched_periods:
        warnings.append(f"프로젝트 기간과 다른 계정 기간이 있습니다: {', '.join(mismatched_periods)}")
        add_check("기간 일치", "warning", "일부 계정 기간이 프로젝트 기간과 다릅니다.")
    else:
        add_check("기간 일치", "pass", f"모든 계정 기간이 {project['period']}로 일치합니다.")

    if abs(total) < 1:
        warnings.append("합계가 0에 가깝습니다. 차변/대변 부호가 유지되었는지 확인하세요.")
        add_check("합계 검토", "warning", "전체 합계가 0에 가깝습니다.")
    else:
        largest = max(statements, key=lambda row: abs(float(row["amount"])))
        ratio = abs(float(largest["amount"])) / abs(total) if total else 0
        detail = f"합계 {total:,.0f}, 최대 계정 {largest['account_name']} {float(largest['amount']):,.0f}"
        if ratio > 0.8 and len(statements) > 1:
            warnings.append(f"단일 계정이 전체 합계의 {ratio:.0%}를 차지합니다: {largest['account_name']}")
            add_check("큰 금액 비중", "warning", detail)
        else:
            add_check("큰 금액 비중", "pass", detail)

    status = "failed" if issues else "warning" if warnings else "passed"
    return {
        "row_count": len(statements),
        "total_amount": total,
        "judgment_count": judgment_count,
        "simple_count": simple_count,
        "issues": issues,
        "warnings": warnings,
        "checks": checks,
        "status": status,
    }


def ocr_config() -> dict:
    provider = os.environ.get("OCR_PROVIDER", "gemini").strip() or "gemini"
    model = os.environ.get("GEMINI_OCR_MODEL", "gemini-3.5-flash").strip() or "gemini-3.5-flash"
    api_key_source = "environment" if os.environ.get("GEMINI_API_KEY") else "none"
    api_key_ready = api_key_source != "none"
    return {
        "provider": provider,
        "model": model,
        "api_key_ready": api_key_ready,
        "api_key_source": api_key_source,
        "mode": "connected" if api_key_ready else "placeholder",
        "manual_review_on_failure": True,
    }


def claude_config() -> dict:
    model = os.environ.get("CLAUDE_MODEL", CLAUDE_DEFAULT_MODEL).strip() or CLAUDE_DEFAULT_MODEL
    api_key_source = "environment" if os.environ.get("CLAUDE_API_KEY") else "none"
    api_key_ready = api_key_source != "none"
    return {
        "provider": "claude",
        "model": model,
        "api_key_ready": api_key_ready,
        "api_key_source": api_key_source,
        "mode": "connected" if api_key_ready else "not_configured",
        "human_review_required": True,
    }


def access_config() -> dict:
    enabled = bool(os.environ.get("APP_ACCESS_CODE", "").strip())
    return {
        "enabled": enabled,
        "header": "X-GTF-Access-Code",
        "mode": "protected" if enabled else "open",
    }


def supported_ocr_mime(path: Path, content_type: str) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".pdf" or "pdf" in content_type:
        return "application/pdf"
    if suffix in {".png", ".jpg", ".jpeg"}:
        return "image/png" if suffix == ".png" else "image/jpeg"
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed in {"application/pdf", "image/png", "image/jpeg"}:
        return guessed
    return None


def extract_json_object(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def gemini_response_text(response: dict) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    if isinstance(response.get("text"), str):
        return response["text"]
    texts: list[str] = []

    def collect_text(value) -> None:
        if isinstance(value, dict):
            for key in ("output_text", "text"):
                if isinstance(value.get(key), str) and value[key].strip():
                    texts.append(value[key])
            for key in ("model_output", "content", "parts", "steps", "output"):
                collect_text(value.get(key))
        elif isinstance(value, list):
            for item in value:
                collect_text(item)

    collect_text(response.get("model_output"))
    collect_text(response.get("steps"))
    collect_text(response.get("output"))
    if texts:
        return "\n".join(texts).strip()

    candidates = response.get("candidates") or []
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts") or []
    candidate_texts = [part.get("text", "") for part in parts if isinstance(part.get("text"), str)]
    return "\n".join(candidate_texts).strip()


def claude_response_text(response: dict) -> str:
    content = response.get("content") or []
    texts = []
    for part in content:
        if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
            texts.append(part["text"])
    return "\n".join(texts).strip()


def call_claude_judgment(project: dict, entries: list[dict], judgment_items: list[dict]) -> dict:
    config = claude_config()
    if not judgment_items:
        return {
            "provider": "claude",
            "model": config["model"],
            "status": "skipped",
            "items": [],
            "overall_note": "판단 필요 항목이 없어 Claude 판단 보조를 건너뛰었습니다.",
            "human_review_required": True,
        }
    api_key = os.environ.get("CLAUDE_API_KEY", "").strip()
    if not api_key:
        return {
            "provider": "claude",
            "model": config["model"],
            "status": "not_configured",
            "items": [],
            "overall_note": "CLAUDE_API_KEY가 서버 환경변수에 설정되지 않아 규정 근거 요약은 생성하지 않았습니다.",
            "issues": ["CLAUDE_API_KEY가 서버 환경변수에 설정되지 않았습니다."],
            "human_review_required": True,
        }

    compact_entries = [
        {
            "source_account": entry.get("source_account"),
            "standard_code": entry.get("standard_code"),
            "target_account": entry.get("target_account"),
            "statement_line_item": entry.get("statement_line_item"),
            "mapping_type": entry.get("mapping_type"),
            "basis": entry.get("basis"),
            "calculation": entry.get("calculation"),
        }
        for entry in entries
        if entry.get("mapping_type") == "judgment"
    ]
    prompt = {
        "project": {
            "company_name": project.get("company_name"),
            "period": project.get("period"),
            "source_standard": project.get("source_standard"),
            "target_standard": project.get("target_standard"),
        },
        "judgment_entries": compact_entries,
        "checklist_inputs": judgment_items,
        "response_contract": {
            "items": [
                {
                    "account": "계정명",
                    "risk_level": "low|medium|high",
                    "classification_hint": "검토자가 확인할 분류 방향",
                    "additional_questions": ["추가로 확인할 질문"],
                    "review_note": "사람 검토자가 볼 짧은 검토 메모",
                    "basis_summary": "적용 기준과 판단 근거 요약",
                }
            ],
            "overall_note": "전체 검토 메모",
        },
    }
    payload = {
        "model": config["model"],
        "max_tokens": 1200,
        "system": (
            "너는 K-GAAP 재무제표를 IFRS 초안으로 변환하는 회계 검토 보조자다. "
            "최종 회계처리를 확정하지 말고, 사용자가 입력한 체크리스트와 변환 초안을 바탕으로 "
            "판단 필요 항목, 추가 질문, 기준 근거 요약만 한국어로 제시한다. "
            "반드시 사람이 최종 검토하고 승인해야 한다는 전제를 유지한다. JSON만 반환한다."
        ),
        "messages": [
            {
                "role": "user",
                "content": (
                    "다음 변환 초안의 판단 필요 항목을 검토해 JSON만 반환하세요. "
                    "마크다운과 설명 문장은 쓰지 마세요.\n"
                    + json.dumps(prompt, ensure_ascii=False)
                ),
            }
        ],
    }
    request = url_request.Request(
        CLAUDE_API_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with url_request.urlopen(request, timeout=45) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except url_error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")[:500]
        return {
            "provider": "claude",
            "model": config["model"],
            "status": "failed",
            "items": [],
            "overall_note": "Claude 판단 보조 요청이 실패했습니다. 변환 초안은 저장되며 사람이 검토해야 합니다.",
            "issues": [f"Claude 요청 실패: HTTP {exc.code}", message],
            "human_review_required": True,
        }
    except url_error.URLError as exc:
        return {
            "provider": "claude",
            "model": config["model"],
            "status": "failed",
            "items": [],
            "overall_note": "Claude 판단 보조 네트워크 오류가 발생했습니다.",
            "issues": [f"Claude 네트워크 오류: {exc.reason}"],
            "human_review_required": True,
        }
    except TimeoutError:
        return {
            "provider": "claude",
            "model": config["model"],
            "status": "failed",
            "items": [],
            "overall_note": "Claude 판단 보조 요청 시간이 초과되었습니다.",
            "issues": ["Claude 요청 시간이 초과되었습니다."],
            "human_review_required": True,
        }

    text = claude_response_text(response_payload)
    if not text:
        return {
            "provider": "claude",
            "model": config["model"],
            "status": "failed",
            "items": [],
            "overall_note": "Claude 응답에서 검토 텍스트를 찾지 못했습니다.",
            "issues": ["Claude 응답 텍스트가 비어 있습니다."],
            "human_review_required": True,
        }
    try:
        parsed = extract_json_object(text)
    except json.JSONDecodeError:
        return {
            "provider": "claude",
            "model": config["model"],
            "status": "failed",
            "items": [],
            "overall_note": "Claude 응답을 JSON으로 해석하지 못했습니다.",
            "issues": ["Claude 응답 JSON 해석 실패", text[:500]],
            "human_review_required": True,
        }

    items = parsed.get("items") if isinstance(parsed.get("items"), list) else []
    return {
        "provider": "claude",
        "model": config["model"],
        "status": "connected",
        "items": items,
        "overall_note": str(parsed.get("overall_note") or "사람 검토와 승인이 필요합니다."),
        "human_review_required": True,
    }


def call_gemini_ocr(file_path: Path, mime_type: str, model: str) -> tuple[list[dict], list[str]]:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return [], ["GEMINI_API_KEY가 서버 환경변수에 설정되지 않았습니다."]
    file_bytes = file_path.read_bytes()
    if len(file_bytes) > GEMINI_INLINE_LIMIT_BYTES:
        return [], [f"파일이 {GEMINI_INLINE_LIMIT_BYTES // (1024 * 1024)}MB를 초과해 inline OCR 처리 대상에서 제외되었습니다."]

    prompt = """
한국 K-GAAP 재무제표 원본에서 계정명과 금액을 추출하세요.
반드시 JSON만 반환하세요. 설명 문장, 마크다운, 코드블록은 금지합니다.
형식:
{
  "rows": [
    {"account_name": "현금및현금성자산", "amount": 120000000}
  ],
  "issues": ["검토가 필요한 사항"]
}
규칙:
- 재무상태표, 손익계산서, 현금흐름표의 주요 계정과 금액을 추출합니다.
- 금액은 숫자만 반환하고 쉼표, 원, 천원, 백만원 단위 표기는 제거합니다.
- 괄호 금액은 음수로 반환합니다.
- 표가 흐리거나 계정/금액 판단이 불확실하면 issues에 적습니다.
- 계정명이 없거나 합계 제목만 있는 행은 제외합니다.
""".strip()
    input_type = "document" if mime_type == "application/pdf" else "image"
    payload = {
        "model": model,
        "store": False,
        "input": [
            {
                "type": input_type,
                "data": base64.b64encode(file_bytes).decode("ascii"),
                "mime_type": mime_type,
            },
            {"type": "text", "text": prompt},
        ],
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": {
                "type": "object",
                "properties": {
                    "rows": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "account_name": {"type": "string"},
                                "amount": {"type": "number"},
                            },
                            "required": ["account_name", "amount"],
                        },
                    },
                    "issues": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["rows"],
            },
        },
    }
    endpoint = "https://generativelanguage.googleapis.com/v1beta/interactions"
    request = url_request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )

    try:
        with url_request.urlopen(request, timeout=45) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except url_error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")[:500]
        return [], [f"Gemini OCR 요청 실패: HTTP {exc.code}", message]
    except url_error.URLError as exc:
        return [], [f"Gemini OCR 네트워크 오류: {exc.reason}"]
    except TimeoutError:
        return [], ["Gemini OCR 요청 시간이 초과되었습니다."]

    text = gemini_response_text(response_payload)
    if not text:
        return [], ["Gemini OCR 응답에서 추출 텍스트를 찾지 못했습니다."]
    try:
        parsed_payload = extract_json_object(text)
    except json.JSONDecodeError:
        return [], ["Gemini OCR 응답을 JSON으로 해석하지 못했습니다.", text[:500]]

    rows = parse_statement_rows(parsed_payload)
    issues = parsed_payload.get("issues") if isinstance(parsed_payload.get("issues"), list) else []
    issues = [str(issue) for issue in issues if str(issue).strip()]
    if not rows:
        issues.append("Gemini OCR은 실행됐지만 계정/금액 행을 찾지 못했습니다.")
    return rows, issues


def extract_rows_from_upload(upload: dict) -> tuple[list[dict], list[str], str]:
    stored_path = UPLOAD_DIR / upload["stored_name"]
    suffix = Path(upload["original_name"]).suffix.lower()
    content_type = upload["content_type"].lower()
    config = ocr_config()
    if suffix == ".csv" or "csv" in content_type:
        text = stored_path.read_text(encoding="utf-8-sig")
        rows = parse_statement_rows({"csv_text": text})
        issues = [] if rows else ["CSV 파일은 읽었지만 계정 행을 찾지 못했습니다."]
        return rows, issues, "local_csv_parser"

    if suffix == ".xlsx" or "spreadsheetml" in content_type:
        try:
            rows, issues = parse_xlsx_statement_rows(stored_path)
        except (KeyError, ValueError, zipfile.BadZipFile, ET.ParseError) as exc:
            rows, issues = [], [f"Excel 파일 구조를 해석하지 못했습니다: {exc}"]
        return rows, issues, "local_xlsx_parser"

    if suffix == ".xls":
        return [], ["구형 .xls 파일은 아직 지원하지 않습니다. .xlsx 또는 CSV로 변환해 업로드하세요."], "unsupported_excel"

    ocr_mime = supported_ocr_mime(Path(upload["original_name"]), content_type)
    if config["api_key_ready"] and config["provider"] == "gemini" and ocr_mime:
        rows, issues = call_gemini_ocr(stored_path, ocr_mime, config["model"])
        issues = [f"OCR 제공자: {config['provider']} / 모델: {config['model']}", *issues]
        return rows, issues, "gemini_ocr"

    sample_rows = [
        {"account_name": "현금및현금성자산", "amount": 120000000},
        {"account_name": "매출채권", "amount": 88000000},
        {"account_name": "리스부채", "amount": 30000000},
        {"account_name": "개발비", "amount": 45000000},
    ]
    issues = [
        f"OCR 제공자: {config['provider']} / 모델: {config['model']}",
        "GEMINI_API_KEY가 설정되지 않아 실제 OCR 대신 샘플 추출을 사용했습니다." if not config["api_key_ready"] else "이 파일 형식은 현재 OCR 처리 대상이 아니어서 샘플 추출을 사용했습니다.",
        "워크플로우 확인을 위해 샘플 추출 행을 생성했습니다.",
        "변환 전에 담당자가 추출 결과를 교체하거나 확인해야 합니다.",
    ]
    return sample_rows, issues, "ocr_placeholder"


def generate_conversion(project: dict, statements: list[dict], responses: dict, templates: dict | None = None) -> dict:
    templates = templates or {}
    entries = []
    notes = []
    judgment_items = []

    for item in statements:
        account_key = normalize_account_name(item["account_name"])
        standard = STANDARD_ACCOUNTS[account_key]
        checklist_response = responses.get(item["id"], {})
        entry = {
            "source_account": item["account_name"],
            "standard_code": item["standard_code"],
            "target_account": standard["ifrs"],
            "amount": item["amount"],
            "adjustment": 0,
            "mapping_type": item["mapping_type"],
            "basis": item["rule_summary"],
        }
        template = templates.get(account_key)
        if template:
            entry["statement_type"] = template["statement_type"]
            entry["statement_section"] = template["section"]
            entry["statement_line_item"] = template["line_item"]
            entry["presentation_order"] = template["display_order"]
            entry["presentation_basis"] = template["basis"]

        if account_key == "lease":
            months = float(checklist_response.get("lease_term_months") or 0)
            payment = float(checklist_response.get("monthly_payment") or 0)
            discount_rate = float(checklist_response.get("discount_rate") or 0) / 100 / 12
            if months > 0 and payment > 0:
                if discount_rate > 0:
                    pv = payment * (1 - (1 + discount_rate) ** (-months)) / discount_rate
                else:
                    pv = payment * months
                entry["adjustment"] = round(pv - float(item["amount"]), 2)
                entry["calculation"] = "리스료 현재가치에서 K-GAAP 장부금액을 차감해 조정액을 산출했습니다."
        elif account_key == "development":
            criteria = ["technical_feasibility", "intention_to_complete", "probable_future_benefits", "reliable_measurement"]
            qualifies = all(checklist_response.get(key) is True for key in criteria)
            entry["target_account"] = "Intangible assets" if qualifies else "Research and development expense"
            entry["calculation"] = "IAS 38 개발단계 자산화 요건 충족 여부를 검토했습니다."
        elif account_key == "revenue":
            timing = checklist_response.get("recognition_timing") or "추가 검토 필요"
            entry["calculation"] = f"수익인식 시점을 '{timing}'로 문서화했습니다."
        elif account_key in {"financial_instrument", "receivables"}:
            entry["calculation"] = "IFRS 9 분류 및 기대신용손실 검토가 필요합니다."
        elif account_key == "provision":
            recognized = all(
                checklist_response.get(key) is True
                for key in ["present_obligation", "probable_outflow", "reliable_estimate"]
            )
            entry["calculation"] = "충당부채 인식요건을 충족했습니다." if recognized else "충당부채 인식요건이 완전하지 않아 공시 또는 추가 검토가 필요합니다."

        if item["mapping_type"] == "judgment":
            judgment_items.append(
                {
                    "statement_id": item["id"],
                    "account": item["account_name"],
                    "checklist_response": checklist_response,
                    "basis": item["rule_summary"],
                }
            )
            notes.append(
                {
                    "account": item["account_name"],
                    "draft_note": f"{standard['ifrs']} 항목은 검토자 확인이 필요합니다. 표시 양식: {entry.get('statement_line_item', '검토 필요')}. 근거: {item['rule_summary']}",
                }
            )

        entries.append(entry)

    return {
        "project": {
            "id": project["id"],
            "company_name": project["company_name"],
            "period": project["period"],
            "source_standard": project["source_standard"],
            "target_standard": project["target_standard"],
        },
        "statement_template": "IFRS 내부 재무제표 양식 DB",
        "entries": entries,
        "judgment_items": judgment_items,
        "draft_notes": notes,
        "review_status": "사람 검토 필요",
        "generated_at": utc_now(),
    }


def conversion_adjustments_csv(conversion: dict) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["원 계정", "내부 코드", "IFRS 계정", "표시 재무제표", "표시 라인", "금액", "조정액", "유형", "계산/근거"])
    for entry in conversion.get("entries", []):
        writer.writerow(
            [
                entry.get("source_account", ""),
                entry.get("standard_code", ""),
                entry.get("target_account", ""),
                entry.get("statement_type", ""),
                entry.get("statement_line_item", ""),
                entry.get("amount", 0),
                entry.get("adjustment", 0),
                label_backend(entry.get("mapping_type", "")),
                localize_export_text(entry.get("calculation") or entry.get("basis")),
            ]
        )
    return buffer.getvalue()


def label_backend(value: str) -> str:
    labels = {
        "simple": "단순 매핑",
        "judgment": "판단 필요",
        "approved": "승인 완료",
        "changes_requested": "수정 요청",
        "draft_generated": "초안 생성",
        "connected": "연결 완료",
        "not_configured": "키 미설정",
        "failed": "실패",
        "skipped": "건너뜀",
    }
    return labels.get(value, value or "-")


def localize_export_text(value) -> str:
    return str(value or "-").replace("review required", "추가 검토 필요").replace("Human review required", "사람 검토 필요")


def load_statement_template_map(conn) -> dict:
    rows = conn.execute(
        """
        SELECT account_key, statement_type, section, line_item, display_order, basis
        FROM financial_statement_templates
        WHERE standard_set = ? AND active = true
        ORDER BY display_order
        """,
        ("IFRS",),
    ).fetchall()
    return {row["account_key"]: row_to_dict(row) for row in rows}


def conversion_basis_report(conversion: dict) -> str:
    project = conversion.get("project", {})
    lines = [
        "GTF 회계기준 변환 근거 리포트",
        "=" * 32,
        f"회사명: {project.get('company_name', '-')}",
        f"기간: {project.get('period', '-')}",
        f"변환 기준: {project.get('source_standard', 'K-GAAP')} -> {project.get('target_standard', 'IFRS')}",
        f"표시 양식: {conversion.get('statement_template', '-')}",
        f"검토 상태: {conversion.get('review_status', '-')}",
        f"생성 시각: {conversion.get('generated_at', '-')}",
        "",
        "[조정분개]",
    ]
    for index, entry in enumerate(conversion.get("entries", []), start=1):
        lines.extend(
            [
                f"{index}. {entry.get('source_account', '-')} -> {entry.get('target_account', '-')}",
                f"   내부 코드: {entry.get('standard_code', '-')}",
                f"   표시 라인: {entry.get('statement_type', '-')} / {entry.get('statement_line_item', '-')}",
                f"   금액: {float(entry.get('amount') or 0):,.0f}",
                f"   조정액: {float(entry.get('adjustment') or 0):,.0f}",
                f"   근거: {localize_export_text(entry.get('calculation') or entry.get('basis'))}",
            ]
        )
    lines.append("")
    lines.append("[판단 필요 항목]")
    judgment_items = conversion.get("judgment_items", [])
    if not judgment_items:
        lines.append("- 없음")
    for item in judgment_items:
        lines.append(f"- {item.get('account', '-')}: {localize_export_text(item.get('basis'))}")
    lines.append("")
    lines.append("[Claude 판단 보조]")
    ai_assistance = conversion.get("ai_assistance") or {}
    lines.append(f"상태: {label_backend(ai_assistance.get('status', '-'))}")
    lines.append(f"모델: {ai_assistance.get('model', '-')}")
    if ai_assistance.get("overall_note"):
        lines.append(f"전체 메모: {localize_export_text(ai_assistance.get('overall_note'))}")
    ai_issues = ai_assistance.get("issues") or []
    if ai_issues:
        lines.append("실패/주의 사항:")
        for issue in ai_issues:
            lines.append(f"  - {localize_export_text(issue)}")
    ai_items = ai_assistance.get("items") or []
    if not ai_items:
        lines.append("- 없음")
    for item in ai_items:
        questions = ", ".join(str(question) for question in item.get("additional_questions", []) if str(question).strip())
        lines.extend(
            [
                f"- {item.get('account', '-')}: {item.get('risk_level', '-')}",
                f"  분류 힌트: {localize_export_text(item.get('classification_hint'))}",
                f"  추가 질문: {questions or '-'}",
                f"  검토 메모: {localize_export_text(item.get('review_note'))}",
                f"  근거 요약: {localize_export_text(item.get('basis_summary'))}",
            ]
        )
    lines.append("")
    lines.append("[주석 초안]")
    notes = conversion.get("draft_notes", [])
    if not notes:
        lines.append("- 없음")
    for note in notes:
        lines.append(f"- {note.get('account', '-')}: {localize_export_text(note.get('draft_note'))}")
    return "\n".join(lines) + "\n"


class AppHandler(BaseHTTPRequestHandler):
    server_version = "GTFServer/0.1"
    public_paths = {"/", "/styles.css", "/app.js", "/healthz", "/api/access-config"}

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path not in self.public_paths and not self.require_access():
            return
        if path == "/":
            self.respond_html(INDEX_HTML)
        elif path == "/healthz":
            self.respond_json(
                {
                    "status": "ok",
                    "service": "gtf-accounting-conversion",
                    "time": utc_now(),
                    "database": database_ready(),
                    "database_config": database_config(),
                    "ocr": ocr_config(),
                    "claude": claude_config(),
                }
            )
        elif path == "/styles.css":
            self.respond_text(STYLES_CSS, "text/css")
        elif path == "/app.js":
            self.respond_text(APP_JS, "application/javascript")
        elif path == "/api/projects":
            self.handle_list_projects()
        elif path == "/api/ocr-config":
            self.handle_ocr_config()
        elif path == "/api/ai-config":
            self.handle_ai_config()
        elif path == "/api/access-config":
            self.handle_access_config()
        elif path == "/api/reference-data":
            self.handle_reference_data()
        elif re.match(r"^/api/projects/[^/]+$", path):
            self.handle_get_project(path.split("/")[-1])
        elif re.match(r"^/api/projects/[^/]+/uploads$", path):
            self.handle_get_uploads(path.split("/")[-2])
        elif re.match(r"^/api/projects/[^/]+/extractions$", path):
            self.handle_get_extractions(path.split("/")[-2])
        elif re.match(r"^/api/projects/[^/]+/audit$", path):
            self.handle_get_audit(path.split("/")[-2])
        elif re.match(r"^/api/projects/[^/]+/exports/[^/]+$", path):
            parts = path.split("/")
            self.handle_export(parts[3], parts[5])
        else:
            self.respond_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in self.public_paths and not self.require_access():
            return
        if path == "/api/projects":
            self.handle_create_project()
        elif re.match(r"^/api/projects/[^/]+/uploads$", path):
            self.handle_upload_file(path.split("/")[-2])
        elif re.match(r"^/api/projects/[^/]+/uploads/[^/]+/extract$", path):
            parts = path.split("/")
            self.handle_extract_upload(parts[3], parts[5])
        elif re.match(r"^/api/projects/[^/]+/extractions/[^/]+/accept$", path):
            parts = path.split("/")
            self.handle_accept_extraction(parts[-4], parts[-2])
        elif re.match(r"^/api/projects/[^/]+/statements$", path):
            self.handle_add_statements(path.split("/")[-2])
        elif re.match(r"^/api/projects/[^/]+/validate$", path):
            self.handle_validate(path.split("/")[-2])
        elif re.match(r"^/api/projects/[^/]+/convert$", path):
            self.handle_convert(path.split("/")[-2])
        elif re.match(r"^/api/projects/[^/]+/review$", path):
            self.handle_review(path.split("/")[-2])
        else:
            self.respond_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def require_access(self) -> bool:
        required_code = os.environ.get("APP_ACCESS_CODE", "").strip()
        if not required_code:
            return True
        provided_code = self.headers.get("X-GTF-Access-Code", "").strip()
        if provided_code and hmac.compare_digest(provided_code, required_code):
            return True
        self.respond_json(
            {
                "error": "접근 코드가 필요합니다.",
                "access_required": True,
            },
            HTTPStatus.UNAUTHORIZED,
        )
        return False

    def read_upload(self) -> tuple[str, str, bytes]:
        length = int(self.headers.get("Content-Length") or "0")
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            raise ValueError("Expected multipart form data.")

        body = self.rfile.read(length)
        raw_message = (
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
            + body
        )
        message = BytesParser(policy=policy.default).parsebytes(raw_message)
        for part in message.iter_parts():
            if part.get_param("name", header="content-disposition") != "file":
                continue
            filename = part.get_filename()
            if not filename:
                break
            content = part.get_payload(decode=True) or b""
            return filename, part.get_content_type(), content
        raise ValueError("No file field was provided.")

    def respond_json(self, payload: dict | list, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def respond_text(self, body: str, content_type: str) -> None:
        data = body.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def respond_download(self, body: str, content_type: str, filename: str) -> None:
        data = body.encode("utf-8-sig" if content_type == "text/csv" else "utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def respond_html(self, body: str) -> None:
        self.respond_text(body, "text/html")

    def handle_list_projects(self) -> None:
        with connect() as conn:
            projects = [row_to_dict(row) for row in conn.execute("SELECT * FROM projects ORDER BY created_at DESC")]
        self.respond_json(projects)

    def handle_ocr_config(self) -> None:
        self.respond_json(ocr_config())

    def handle_ai_config(self) -> None:
        self.respond_json(claude_config())

    def handle_access_config(self) -> None:
        self.respond_json(access_config())

    def handle_reference_data(self) -> None:
        tables = [
            ("standard_accounts", "내부 표준계정코드 DB"),
            ("kgaap_accounts", "K-GAAP 계정명 DB"),
            ("ifrs_accounts", "IFRS 계정/기준 DB"),
            ("mapping_rules", "변환 룰 DB"),
            ("checklist_items", "판단 체크리스트 DB"),
            ("standards_references", "기준서 참조 DB"),
            ("financial_statement_templates", "재무제표 양식 DB"),
        ]
        with connect() as conn:
            summary = []
            for table, label in tables:
                count = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]
                summary.append({"table": table, "label": label, "count": count})
            accounts = [
                row_to_dict(row)
                for row in conn.execute(
                    """
                    SELECT account_key, standard_code, internal_label, ifrs_account, mapping_type
                    FROM standard_accounts
                    ORDER BY standard_code
                    """
                )
            ]
            templates = [
                row_to_dict(row)
                for row in conn.execute(
                    """
                    SELECT statement_type, section, line_item, account_key, display_order
                    FROM financial_statement_templates
                    WHERE standard_set = ? AND active = true
                    ORDER BY statement_type, display_order
                    """,
                    ("IFRS",),
                )
            ]
        self.respond_json({"summary": summary, "accounts": accounts, "templates": templates})

    def handle_create_project(self) -> None:
        payload = self.read_json()
        now = utc_now()
        project = {
            "id": str(uuid.uuid4()),
            "company_name": payload.get("company_name") or "Untitled company",
            "source_standard": payload.get("source_standard") or "K-GAAP",
            "target_standard": payload.get("target_standard") or "IFRS",
            "period": payload.get("period") or "2026",
            "status": "created",
            "created_at": now,
            "updated_at": now,
        }
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO projects (id, company_name, source_standard, target_standard, period, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuple(project.values()),
            )
            log_event(conn, project["id"], "project.created", project)
        self.respond_json(project, HTTPStatus.CREATED)

    def handle_get_project(self, project_id: str) -> None:
        with connect() as conn:
            project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not project:
                self.respond_json({"error": "Project not found"}, HTTPStatus.NOT_FOUND)
                return
            statements = [
                dict(row_to_dict(row), checklist=parse_json_field(row["checklist_json"], []))
                for row in conn.execute("SELECT * FROM statements WHERE project_id = ? ORDER BY created_at", (project_id,))
            ]
            uploads = [
                row_to_dict(row)
                for row in conn.execute("SELECT * FROM uploads WHERE project_id = ? ORDER BY created_at DESC", (project_id,))
            ]
            extractions = [
                dict(row_to_dict(row), rows=parse_json_field(row["rows_json"], []), issues=parse_json_field(row["issues_json"], []))
                for row in conn.execute("SELECT * FROM extractions WHERE project_id = ? ORDER BY created_at DESC", (project_id,))
            ]
            conversion = conn.execute(
                "SELECT * FROM conversions WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
            review = conn.execute(
                "SELECT * FROM reviews WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        self.respond_json(
            {
                "project": row_to_dict(project),
                "statements": statements,
                "uploads": uploads,
                "extractions": extractions,
                "conversion": parse_json_field(conversion["output_json"], None) if conversion else None,
                "review": row_to_dict(review) if review else None,
            }
        )

    def handle_get_uploads(self, project_id: str) -> None:
        with connect() as conn:
            rows = conn.execute(
                "SELECT * FROM uploads WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        self.respond_json([row_to_dict(row) for row in rows])

    def handle_get_extractions(self, project_id: str) -> None:
        with connect() as conn:
            rows = conn.execute(
                "SELECT * FROM extractions WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        self.respond_json(
            [dict(row_to_dict(row), rows=parse_json_field(row["rows_json"], []), issues=parse_json_field(row["issues_json"], [])) for row in rows]
        )

    def handle_upload_file(self, project_id: str) -> None:
        with connect() as conn:
            project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not project:
                self.respond_json({"error": "Project not found"}, HTTPStatus.NOT_FOUND)
                return

        try:
            original_name, content_type, content = self.read_upload()
        except ValueError as exc:
            self.respond_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(original_name).name).strip("._")
        stored_name = f"{project_id}_{uuid.uuid4()}_{safe_name or 'upload.bin'}"
        stored_path = UPLOAD_DIR / stored_name
        stored_path.write_bytes(content)

        upload = {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "original_name": original_name,
            "stored_name": stored_name,
            "content_type": content_type,
            "size_bytes": len(content),
            "extraction_status": "pending_ocr",
            "created_at": utc_now(),
        }
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO uploads (
                    id, project_id, original_name, stored_name, content_type, size_bytes, extraction_status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    upload["id"],
                    upload["project_id"],
                    upload["original_name"],
                    upload["stored_name"],
                    upload["content_type"],
                    upload["size_bytes"],
                    upload["extraction_status"],
                    upload["created_at"],
                ),
            )
            conn.execute("UPDATE projects SET status = ?, updated_at = ? WHERE id = ?", ("source_uploaded", utc_now(), project_id))
            log_event(
                conn,
                project_id,
                "source.uploaded",
                {
                    "upload_id": upload["id"],
                    "original_name": original_name,
                    "content_type": content_type,
                    "size_bytes": len(content),
                    "next_step": "Gemini OCR extraction",
                },
            )
        self.respond_json(upload, HTTPStatus.CREATED)

    def handle_extract_upload(self, project_id: str, upload_id: str) -> None:
        with connect() as conn:
            upload = conn.execute(
                "SELECT * FROM uploads WHERE id = ? AND project_id = ?",
                (upload_id, project_id),
            ).fetchone()
            if not upload:
                self.respond_json({"error": "Upload not found"}, HTTPStatus.NOT_FOUND)
                return

            config = ocr_config()
            rows, issues, provider = extract_rows_from_upload(row_to_dict(upload))
            status = "needs_review" if rows else "failed"
            extraction = {
                "id": str(uuid.uuid4()),
                "project_id": project_id,
                "upload_id": upload_id,
                "provider": provider,
                "status": status,
                "rows": rows,
                "issues": issues,
                "created_at": utc_now(),
            }
            conn.execute(
                """
                INSERT INTO extractions (id, project_id, upload_id, provider, status, rows_json, issues_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    extraction["id"],
                    extraction["project_id"],
                    extraction["upload_id"],
                    extraction["provider"],
                    extraction["status"],
                    json.dumps(extraction["rows"], ensure_ascii=False),
                    json.dumps(extraction["issues"], ensure_ascii=False),
                    extraction["created_at"],
                ),
            )
            conn.execute(
                "UPDATE uploads SET extraction_status = ? WHERE id = ?",
                (status, upload_id),
            )
            conn.execute("UPDATE projects SET status = ?, updated_at = ? WHERE id = ?", ("extracted", utc_now(), project_id))
            log_event(
                conn,
                project_id,
                "source.extracted",
                {
                    "upload_id": upload_id,
                    "extraction_id": extraction["id"],
                    "provider": provider,
                    "ocr_config": config,
                    "row_count": len(rows),
                    "issues": issues,
                },
            )
        self.respond_json(extraction, HTTPStatus.CREATED)

    def handle_accept_extraction(self, project_id: str, extraction_id: str) -> None:
        with connect() as conn:
            project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            extraction = conn.execute(
                "SELECT * FROM extractions WHERE id = ? AND project_id = ?",
                (extraction_id, project_id),
            ).fetchone()
            if not project or not extraction:
                self.respond_json({"error": "Extraction not found"}, HTTPStatus.NOT_FOUND)
                return

            rows = parse_json_field(extraction["rows_json"], [])
            records = [build_statement_record(project["period"], row) for row in rows]
            for record in records:
                conn.execute(
                    """
                    INSERT INTO statements (
                        id, project_id, account_name, normalized_account, standard_code, amount, period,
                        mapping_type, rule_summary, checklist_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["id"],
                        project_id,
                        record["account_name"],
                        record["normalized_account"],
                        record["standard_code"],
                        record["amount"],
                        record["period"],
                        record["mapping_type"],
                        record["rule_summary"],
                        json.dumps(record["checklist"], ensure_ascii=False),
                        utc_now(),
                    ),
                )
            conn.execute(
                "UPDATE extractions SET status = ? WHERE id = ?",
                ("accepted", extraction_id),
            )
            conn.execute("UPDATE projects SET status = ?, updated_at = ? WHERE id = ?", ("mapped", utc_now(), project_id))
            log_event(
                conn,
                project_id,
                "extraction.accepted",
                {"extraction_id": extraction_id, "statement_count": len(records)},
            )
        self.respond_json({"statements": records, "extraction_id": extraction_id})

    def handle_add_statements(self, project_id: str) -> None:
        payload = self.read_json()
        with connect() as conn:
            project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not project:
                self.respond_json({"error": "Project not found"}, HTTPStatus.NOT_FOUND)
                return
            raw_rows = parse_statement_rows(payload)
            records = [build_statement_record(project["period"], row) for row in raw_rows]
            for record in records:
                conn.execute(
                    """
                    INSERT INTO statements (
                        id, project_id, account_name, normalized_account, standard_code, amount, period,
                        mapping_type, rule_summary, checklist_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["id"],
                        project_id,
                        record["account_name"],
                        record["normalized_account"],
                        record["standard_code"],
                        record["amount"],
                        record["period"],
                        record["mapping_type"],
                        record["rule_summary"],
                        json.dumps(record["checklist"], ensure_ascii=False),
                        utc_now(),
                    ),
                )
            conn.execute("UPDATE projects SET status = ?, updated_at = ? WHERE id = ?", ("mapped", utc_now(), project_id))
            log_event(conn, project_id, "statements.mapped", {"count": len(records), "source": payload.get("source", "manual")})
        self.respond_json({"statements": records})

    def handle_validate(self, project_id: str) -> None:
        with connect() as conn:
            project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not project:
                self.respond_json({"error": "Project not found"}, HTTPStatus.NOT_FOUND)
                return
            statements = conn.execute("SELECT * FROM statements WHERE project_id = ?", (project_id,)).fetchall()
            result = validate_statement_records(row_to_dict(project), statements)
            log_event(conn, project_id, "validation.completed", result)
        self.respond_json(result)

    def handle_convert(self, project_id: str) -> None:
        payload = self.read_json()
        responses = payload.get("responses") or {}
        with connect() as conn:
            project_row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not project_row:
                self.respond_json({"error": "Project not found"}, HTTPStatus.NOT_FOUND)
                return
            statement_rows = [
                dict(row_to_dict(row), checklist=parse_json_field(row["checklist_json"], []))
                for row in conn.execute("SELECT * FROM statements WHERE project_id = ? ORDER BY created_at", (project_id,))
            ]
            templates = load_statement_template_map(conn)
            project = row_to_dict(project_row)
            output = generate_conversion(project, statement_rows, responses, templates)
            output["ai_assistance"] = call_claude_judgment(project, output["entries"], output["judgment_items"])
            conn.execute(
                "INSERT INTO conversions (id, project_id, output_json, created_at) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), project_id, json.dumps(output, ensure_ascii=False), utc_now()),
            )
            conn.execute("UPDATE projects SET status = ?, updated_at = ? WHERE id = ?", ("draft_generated", utc_now(), project_id))
            log_event(
                conn,
                project_id,
                "conversion.generated",
                {
                    "responses": responses,
                    "entry_count": len(output["entries"]),
                    "template": output["statement_template"],
                    "claude_status": output["ai_assistance"].get("status"),
                },
            )
        self.respond_json(output)

    def handle_review(self, project_id: str) -> None:
        payload = self.read_json()
        decision = payload.get("decision")
        if decision not in {"approved", "changes_requested"}:
            self.respond_json({"error": "Decision must be approved or changes_requested."}, HTTPStatus.BAD_REQUEST)
            return

        reviewer_name = str(payload.get("reviewer_name") or "").strip() or "Unassigned reviewer"
        memo = str(payload.get("memo") or "").strip()
        status = "approved" if decision == "approved" else "changes_requested"
        review = {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "reviewer_name": reviewer_name,
            "decision": decision,
            "memo": memo,
            "created_at": utc_now(),
        }

        with connect() as conn:
            project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not project:
                self.respond_json({"error": "Project not found"}, HTTPStatus.NOT_FOUND)
                return
            conversion = conn.execute(
                "SELECT id FROM conversions WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
            if not conversion:
                self.respond_json({"error": "Generate a conversion draft before review."}, HTTPStatus.BAD_REQUEST)
                return
            conn.execute(
                """
                INSERT INTO reviews (id, project_id, reviewer_name, decision, memo, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    review["id"],
                    review["project_id"],
                    review["reviewer_name"],
                    review["decision"],
                    review["memo"],
                    review["created_at"],
                ),
            )
            conn.execute("UPDATE projects SET status = ?, updated_at = ? WHERE id = ?", (status, utc_now(), project_id))
            log_event(
                conn,
                project_id,
                "review.recorded",
                {
                    "review_id": review["id"],
                    "decision": decision,
                    "memo": memo,
                    "conversion_id": conversion["id"],
                },
                actor=reviewer_name,
            )
        self.respond_json(review, HTTPStatus.CREATED)

    def handle_get_audit(self, project_id: str) -> None:
        with connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_logs WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        logs = [dict(row_to_dict(row), detail=parse_json_field(row["detail_json"], {})) for row in rows]
        self.respond_json(logs)

    def handle_export(self, project_id: str, export_name: str) -> None:
        with connect() as conn:
            conversion = conn.execute(
                "SELECT output_json FROM conversions WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        if not conversion:
            self.respond_json({"error": "Generate a conversion draft before export."}, HTTPStatus.BAD_REQUEST)
            return
        output = parse_json_field(conversion["output_json"], {})
        if export_name == "adjustments.csv":
            self.respond_download(conversion_adjustments_csv(output), "text/csv", "gtf_adjustments.csv")
            return
        if export_name == "basis-report.txt":
            self.respond_download(conversion_basis_report(output), "text/plain", "gtf_basis_report.txt")
            return
        self.respond_json({"error": "Unknown export type"}, HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


INDEX_HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GTF 회계기준 변환</title>
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <header class="topbar">
    <div>
      <h1>GTF 회계기준 변환</h1>
      <p>K-GAAP 재무제표를 IFRS/US GAAP 검토 초안으로 정리하는 작업공간</p>
    </div>
    <button id="sampleBtn" class="ghost">예시 입력</button>
  </header>

  <section id="accessPanel" class="access-panel hidden">
    <div>
      <h2>접근 코드</h2>
      <p id="accessMessage">운영자가 발급한 접근 코드를 입력하세요.</p>
    </div>
    <div class="access-actions">
      <input id="accessCodeInput" type="password" autocomplete="current-password" placeholder="접근 코드">
      <button id="saveAccessCodeBtn" class="primary">저장</button>
      <button id="clearAccessCodeBtn" class="ghost">초기화</button>
    </div>
  </section>

  <main class="layout">
    <aside class="sidebar panel">
      <div class="panel-head">
        <h2>프로젝트</h2>
        <button id="refreshProjectsBtn" class="ghost">새로고침</button>
      </div>
      <div id="projectList" class="project-empty">저장된 프로젝트가 없습니다.</div>
    </aside>

    <section class="panel project-panel">
      <div class="panel-head">
        <h2>기본 정보</h2>
        <span id="statusPill" class="pill">시작 전</span>
      </div>
      <form id="projectForm" class="grid">
        <label>회사명
          <input name="company_name" value="GTF Bio Inc." required>
        </label>
        <label>대상 기간
          <input name="period" value="2026">
        </label>
        <label>원 기준
          <select name="source_standard">
            <option>K-GAAP</option>
          </select>
        </label>
        <label>변환 기준
          <select name="target_standard">
            <option>IFRS</option>
            <option>US GAAP</option>
          </select>
        </label>
        <div class="form-actions">
          <button type="submit" class="primary">프로젝트 생성</button>
        </div>
      </form>
    </section>

    <section class="panel progress-panel">
      <div class="panel-head">
        <h2>진행 현황</h2>
        <span id="nextActionPill" class="pill">프로젝트 생성</span>
      </div>
      <div id="workflowSteps" class="steps"></div>
      <div class="summary-grid">
        <div class="metric">
          <strong id="metricUploads">0</strong>
          <span>원본 파일</span>
        </div>
        <div class="metric">
          <strong id="metricExtractions">0</strong>
          <span>추출 결과</span>
        </div>
        <div class="metric">
          <strong id="metricStatements">0</strong>
          <span>매핑 계정</span>
        </div>
        <div class="metric">
          <strong id="metricJudgments">0</strong>
          <span>판단 필요</span>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>수동 입력</h2>
        <button id="mapBtn" class="primary" disabled>계정 매핑</button>
      </div>
      <textarea id="csvInput" spellcheck="false" placeholder="계정명,금액&#10;현금및현금성자산,120000000&#10;리스부채,30000000&#10;개발비,45000000"></textarea>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>원본 파일</h2>
        <button id="uploadBtn" class="primary" disabled>업로드</button>
      </div>
      <label>재무제표 파일
        <input id="fileInput" type="file" accept=".pdf,.xlsx,.xls,.csv,.png,.jpg,.jpeg">
      </label>
      <div id="uploadList" class="file-empty">업로드된 파일이 없습니다.</div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>OCR 설정</h2>
        <span id="ocrModePill" class="pill">확인 중</span>
      </div>
      <div class="config-list">
        <div>
          <span>제공자</span>
          <strong id="ocrProvider">-</strong>
        </div>
        <div>
          <span>모델</span>
          <strong id="ocrModel">-</strong>
        </div>
        <div>
          <span>API 키</span>
          <strong id="ocrApiKey">-</strong>
        </div>
        <div>
          <span>실패 처리</span>
          <strong id="ocrFailureMode">-</strong>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>AI 판단 보조</h2>
        <span id="aiModePill" class="pill">확인 중</span>
      </div>
      <div class="config-list">
        <div>
          <span>제공자</span>
          <strong id="aiProvider">-</strong>
        </div>
        <div>
          <span>모델</span>
          <strong id="aiModel">-</strong>
        </div>
        <div>
          <span>API 키</span>
          <strong id="aiApiKey">-</strong>
        </div>
        <div>
          <span>검토 방식</span>
          <strong id="aiReviewMode">-</strong>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>기준정보 DB</h2>
        <span id="referenceDbPill" class="pill">확인 중</span>
      </div>
      <div id="referenceDbList" class="config-list"></div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>추출 결과</h2>
        <span id="extractionPill" class="pill">대기</span>
      </div>
      <div id="extractionList" class="file-empty">아직 추출 결과가 없습니다.</div>
    </section>

    <section class="panel wide">
      <div class="panel-head">
        <h2>계정 매핑 및 판단항목</h2>
        <div class="actions">
          <button id="validateBtn" class="ghost" disabled>검증</button>
          <button id="convertBtn" class="primary" disabled>변환 초안 생성</button>
        </div>
      </div>
      <div id="mappingTable" class="table-empty">프로젝트를 생성한 뒤 계정 데이터를 매핑하세요.</div>
      <div id="validation" class="validation-report"></div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>변환 초안</h2>
        <div class="actions">
          <button id="exportCsvBtn" class="ghost" disabled>조정분개 CSV</button>
          <button id="exportReportBtn" class="ghost" disabled>근거 리포트</button>
        </div>
      </div>
      <div id="outputBox" class="draft-empty">아직 생성된 변환 초안이 없습니다.</div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>검토 및 승인</h2>
        <span id="reviewPill" class="pill">대기</span>
      </div>
      <div class="grid">
        <label>검토자
          <input id="reviewerName" value="회계 검토자">
        </label>
        <label>검토 메모
          <input id="reviewMemo" placeholder="승인 근거 또는 수정 요청 사항">
        </label>
      </div>
      <div class="actions review-actions">
        <button id="requestChangesBtn" class="ghost" disabled>수정 요청</button>
        <button id="approveBtn" class="primary" disabled>초안 승인</button>
      </div>
    </section>

    <section class="panel">
      <h2>감사 로그</h2>
      <div id="auditLog" class="log-empty">아직 기록된 이벤트가 없습니다.</div>
    </section>
  </main>

  <script src="/app.js"></script>
</body>
</html>
"""


STYLES_CSS = """
:root {
  color-scheme: light;
  --ink: #182027;
  --muted: #63727a;
  --line: #d8e1e4;
  --surface: #f4f7f7;
  --panel: #ffffff;
  --accent: #0b6b5c;
  --accent-2: #264e86;
  --warn: #9c5b10;
  --danger: #9e2f2f;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", "Segoe UI", sans-serif;
  color: var(--ink);
  background: var(--surface);
  line-height: 1.45;
}

.topbar {
  min-height: 84px;
  padding: 18px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  border-bottom: 1px solid var(--line);
  background: #fff;
}

.hidden { display: none !important; }

.access-panel {
  margin: 16px 16px 0;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  border: 1px solid #d8c08f;
  border-radius: 8px;
  background: #fff8e8;
}

.access-panel p { color: #785315; }

.access-actions {
  min-width: min(420px, 100%);
  display: grid;
  grid-template-columns: minmax(160px, 1fr) auto auto;
  gap: 8px;
}

h1, h2, p { margin: 0; }
h1 { font-size: 22px; letter-spacing: 0; }
h2 { font-size: 15px; letter-spacing: 0; }
p { margin-top: 4px; color: var(--muted); font-size: 13px; }

.layout {
  display: grid;
  grid-template-columns: 300px minmax(360px, 1fr) minmax(520px, 1.25fr);
  align-items: start;
  gap: 16px;
  padding: 16px;
}

.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
  min-width: 0;
  box-shadow: 0 1px 2px rgba(24, 32, 39, 0.03);
}

.sidebar {
  position: sticky;
  top: 16px;
  max-height: calc(100vh - 32px);
  overflow: auto;
}

.project-panel { grid-column: span 2; }

.progress-panel { grid-column: span 2; }

.wide {
  grid-column: span 2;
  grid-row: span 2;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.form-actions {
  grid-column: 1 / -1;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

label {
  display: grid;
  gap: 6px;
  color: var(--muted);
  font-size: 12px;
}

input, select, textarea {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 6px;
  color: var(--ink);
  background: #fff;
  font: inherit;
  font-size: 14px;
}

input, select { height: 38px; padding: 0 10px; }
textarea {
  min-height: 224px;
  resize: vertical;
  padding: 10px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

button {
  min-height: 36px;
  border-radius: 6px;
  border: 1px solid var(--line);
  padding: 0 14px;
  font-weight: 650;
  cursor: pointer;
  background: #fff;
  color: var(--ink);
  white-space: nowrap;
}

button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.primary {
  border-color: var(--accent);
  background: var(--accent);
  color: #fff;
}

.ghost {
  background: #fff;
  color: var(--accent-2);
}

.pill {
  min-width: 94px;
  text-align: center;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 5px 10px;
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.review-actions { margin-top: 12px; }

.steps {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.step {
  min-height: 60px;
  display: grid;
  align-content: center;
  gap: 4px;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 10px;
  background: #fbfcfc;
  color: var(--muted);
}

.step strong {
  display: block;
  color: var(--ink);
  font-size: 12px;
  line-height: 1.25;
}

.step span {
  font-size: 11px;
}

.step.done {
  border-color: #9ccfc2;
  background: #eef8f5;
}

.step.current {
  border-color: var(--accent);
  box-shadow: inset 0 0 0 1px var(--accent);
  background: #f8fffc;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric {
  min-height: 74px;
  display: grid;
  align-content: center;
  gap: 4px;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 12px;
  background: #fff;
}

.metric strong {
  font-size: 24px;
  line-height: 1;
}

.metric span {
  color: var(--muted);
  font-size: 12px;
}

.config-list {
  display: grid;
  gap: 10px;
}

.config-list div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 38px;
  border-bottom: 1px solid var(--line);
}

.config-list div:last-child {
  border-bottom: 0;
}

.config-list span {
  color: var(--muted);
  font-size: 12px;
}

.config-list strong {
  text-align: right;
  font-size: 13px;
  font-weight: 700;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  line-height: 1.45;
}

th, td {
  border-bottom: 1px solid var(--line);
  padding: 10px 9px;
  text-align: left;
  vertical-align: top;
}

th {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  background: #fbfcfc;
}

.badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 12px;
  background: #ecf5f3;
  color: var(--accent);
}

.badge.warn {
  background: #fff3df;
  color: var(--warn);
}

.checklist {
  display: grid;
  gap: 10px;
  min-width: 260px;
}

.checkitem {
  display: grid;
  gap: 5px;
}

.checklabel {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--ink);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.45;
}

.required-mark {
  color: var(--warn);
  font-weight: 800;
}

.checklist input[type="checkbox"] {
  width: 16px;
  height: 16px;
  margin: 0;
}

.checkline {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  color: var(--ink);
  font-weight: 700;
  line-height: 1.45;
  font-size: 12px;
}

.notice {
  min-height: 26px;
  margin-top: 12px;
  color: var(--muted);
  font-size: 13px;
}

.validation-report {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.validation-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  color: var(--muted);
  font-size: 13px;
}

.validation-checks {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 8px;
}

.validation-check {
  display: grid;
  gap: 4px;
  min-height: 74px;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fbfcfc;
  font-size: 12px;
}

.validation-check strong {
  color: var(--ink);
  font-size: 13px;
}

.validation-check span {
  color: var(--muted);
  line-height: 1.45;
}

.validation-check.pass {
  border-color: #bddbd4;
  background: #f2faf7;
}

.validation-check.warning {
  border-color: #f0d19a;
  background: #fff8ec;
}

.validation-check.error {
  border-color: #efb8b8;
  background: #fff4f4;
}

pre {
  min-height: 220px;
  overflow: auto;
  margin: 0;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #101820;
  color: #f5fbfc;
  font-size: 12px;
}

.draft-empty {
  color: var(--muted);
  font-size: 13px;
}

.draft-view {
  display: grid;
  gap: 16px;
}

.draft-summary {
  display: grid;
  gap: 4px;
  color: var(--muted);
  font-size: 13px;
}

.draft-summary strong {
  color: var(--ink);
  font-size: 15px;
}

.draft-section {
  display: grid;
  gap: 8px;
}

.draft-section h3 {
  margin: 0;
  color: var(--ink);
  font-size: 14px;
}

.draft-list {
  display: grid;
  gap: 8px;
}

.draft-card {
  display: grid;
  gap: 4px;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fbfcfc;
  font-size: 12px;
}

.draft-card strong {
  color: var(--ink);
  font-size: 13px;
}

.draft-card span {
  color: var(--muted);
  line-height: 1.45;
}

.log-item {
  border-bottom: 1px solid var(--line);
  padding: 10px 0;
  font-size: 13px;
}

.log-item strong { display: block; }
.log-item span { color: var(--muted); font-size: 12px; }
.log-detail {
  display: grid;
  gap: 5px;
  margin-top: 8px;
  padding: 8px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fbfcfc;
}

.log-detail-row {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr);
  gap: 8px;
  color: var(--muted);
  font-size: 12px;
}

.log-detail-row strong {
  color: var(--ink);
  font-size: 12px;
}
.table-empty, .log-empty { color: var(--muted); font-size: 13px; }
.file-empty {
  margin-top: 10px;
  color: var(--muted);
  font-size: 13px;
  padding: 10px 0;
}
.file-item {
  display: grid;
  gap: 6px;
  margin-top: 10px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fbfcfc;
  font-size: 13px;
}
.file-item span { color: var(--muted); font-size: 12px; }
.file-item table { margin-top: 8px; }
.item-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}
.issues {
  margin: 8px 0 0;
  padding-left: 18px;
  color: var(--warn);
  font-size: 12px;
}
.project-empty { color: var(--muted); font-size: 13px; }
.project-item {
  width: 100%;
  min-height: 64px;
  display: grid;
  gap: 4px;
  margin-top: 8px;
  padding: 11px 12px;
  text-align: left;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
}
.project-item strong { font-size: 13px; line-height: 1.25; }
.project-item span { color: var(--muted); font-size: 12px; font-weight: 500; }
.project-item.active {
  border-color: var(--accent);
  background: #eef7f4;
}

.project-item:hover:not(:disabled) {
  border-color: #b8c9ce;
  background: #fbfcfc;
}

@media (max-width: 980px) {
  .layout { grid-template-columns: 1fr; }
  .sidebar { position: static; max-height: none; }
  .project-panel { grid-column: auto; }
  .progress-panel { grid-column: auto; }
  .wide { grid-row: auto; }
  .steps { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 640px) {
  .topbar { align-items: flex-start; flex-direction: column; padding: 16px; }
  .access-panel { align-items: stretch; flex-direction: column; margin: 10px 10px 0; }
  .access-actions { grid-template-columns: 1fr; }
  .layout { padding: 10px; }
  .grid { grid-template-columns: 1fr; }
  .form-actions { justify-content: stretch; }
  .form-actions button { width: 100%; }
  .panel-head { align-items: flex-start; flex-direction: column; }
  .panel-head > .actions { width: 100%; }
  .panel-head > .actions button { flex: 1; }
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  table, thead, tbody, tr, th, td { display: block; }
  th { display: none; }
  td { padding: 8px 0; }
}
"""


APP_JS = """
let activeProjectId = null;
let statements = [];
let uploads = [];
let extractions = [];
let hasDraft = false;
let projects = [];
let accessRequired = false;

const $ = (selector) => document.querySelector(selector);
const accessStorageKey = "gtfAccessCode";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function localizeText(value) {
  return String(value ?? "-")
    .replaceAll("review required", "추가 검토 필요")
    .replaceAll("Human review required", "사람 검토 필요")
    .replaceAll("Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits.", "Anthropic API 크레딧이 부족합니다. Anthropic 콘솔의 Plans & Billing에서 크레딧을 충전해야 합니다.");
}

function riskLabel(value) {
  const labels = { low: "낮음", medium: "중간", high: "높음" };
  return labels[value] || value || "-";
}

function savedAccessCode() {
  return sessionStorage.getItem(accessStorageKey) || "";
}

function authHeaders(baseHeaders = {}) {
  const headers = { ...baseHeaders };
  const code = savedAccessCode();
  if (code) {
    headers["X-GTF-Access-Code"] = code;
  }
  return headers;
}

function renderAccessPanel(message = "") {
  const panel = $("#accessPanel");
  if (!panel) return;
  panel.classList.toggle("hidden", !accessRequired);
  if (!accessRequired) return;
  const hasCode = Boolean(savedAccessCode());
  $("#accessMessage").textContent = message || (hasCode ? "접근 코드가 저장되었습니다. API 요청에 자동 적용됩니다." : "운영자가 발급한 접근 코드를 입력하세요.");
  $("#accessCodeInput").value = hasCode ? savedAccessCode() : "";
}

function handleAccessError(data) {
  if (data && data.access_required) {
    accessRequired = true;
    renderAccessPanel(data.error || "접근 코드가 필요합니다.");
  }
}

const workflowDefinitions = [
  { key: "created", title: "프로젝트", hint: "기본 정보" },
  { key: "source_uploaded", title: "원본", hint: "파일 업로드" },
  { key: "extracted", title: "추출", hint: "OCR/Excel" },
  { key: "mapped", title: "매핑", hint: "계정 분류" },
  { key: "draft_generated", title: "초안", hint: "조정분개" },
  { key: "approved", title: "승인", hint: "사람 검토" }
];

const statusLabels = {
  created: "생성됨",
  source_uploaded: "원본 업로드",
  extracted: "추출 완료",
  mapped: "매핑 완료",
  draft_generated: "초안 생성",
  approved: "승인 완료",
  changes_requested: "수정 요청",
  connected: "연결 완료",
  not_configured: "키 미설정",
  skipped: "건너뜀",
  pending_ocr: "OCR 대기",
  needs_review: "검토 필요",
  accepted: "반영 완료",
  failed: "실패",
  simple: "단순 매핑",
  judgment: "판단 필요",
  pass: "통과",
  passed: "통과",
  warning: "주의",
  error: "오류",
  "project.created": "프로젝트 생성",
  "source.uploaded": "원본 파일 업로드",
  "source.extracted": "원본 데이터 추출",
  "extraction.accepted": "추출 결과 반영",
  "statements.mapped": "계정 매핑",
  "validation.completed": "데이터 검증",
  "conversion.generated": "변환 초안 생성",
  "review.recorded": "검토 결과 기록",
  local_csv_parser: "CSV 파서",
  local_xlsx_parser: "Excel 파서",
  unsupported_excel: "지원하지 않는 Excel",
  ocr_placeholder: "OCR 대기 샘플",
  gemini: "Gemini OCR"
};

function labelFor(value) {
  return statusLabels[value] || value || "-";
}

function summarizeValue(value) {
  if (Array.isArray(value)) {
    if (value.length === 0) return "없음";
    if (value.length <= 3 && value.every((item) => typeof item !== "object")) {
      return value.map((item) => String(item)).join(", ");
    }
    return `${value.length}개 항목`;
  }
  if (value && typeof value === "object") {
    const keys = Object.keys(value);
    if (keys.length === 0) return "없음";
    return keys.slice(0, 4).map((key) => `${key}: ${summarizeValue(value[key])}`).join(" / ");
  }
  if (typeof value === "boolean") return value ? "예" : "아니오";
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return Number(value).toLocaleString();
  if (typeof value === "string" && statusLabels[value]) return labelFor(value);
  return String(value);
}

function auditDetailRows(log) {
  const detail = log.detail || {};
  const labels = {
    id: "ID",
    company_name: "회사명",
    source_standard: "원 기준",
    target_standard: "목표 기준",
    period: "기간",
    status: "상태",
    upload_id: "업로드 ID",
    original_name: "파일명",
    content_type: "파일 형식",
    size_bytes: "파일 크기",
    extraction_id: "추출 ID",
    provider: "처리 방식",
    ocr_config: "OCR 설정",
    row_count: "행 수",
    issues: "이슈",
    count: "처리 건수",
    source: "입력 출처",
    responses: "체크리스트 응답",
    entry_count: "조정분개 수",
    review_id: "검토 ID",
    decision: "검토 결과",
    memo: "검토 메모",
    conversion_id: "변환 초안 ID",
    warnings: "주의",
    checks: "검증 항목",
    total_amount: "합계",
    judgment_count: "판단 필요",
    simple_count: "단순 매핑",
    claude_status: "Claude 상태"
  };
  const preferred = [
    "company_name", "period", "source_standard", "target_standard", "original_name",
    "content_type", "size_bytes", "provider", "row_count", "count", "entry_count",
    "status", "decision", "memo", "issues", "warnings", "checks", "responses",
    "total_amount", "judgment_count", "simple_count"
  ];
  const keys = [...preferred.filter((key) => key in detail), ...Object.keys(detail).filter((key) => !preferred.includes(key))];
  return keys.slice(0, 10).map((key) => `
    <div class="log-detail-row">
      <strong>${escapeHtml(labels[key] || key)}</strong>
      <span>${escapeHtml(summarizeValue(detail[key]))}</span>
    </div>
  `).join("");
}

function workflowIndex(status) {
  if (status === "changes_requested") return 4;
  const index = workflowDefinitions.findIndex((step) => step.key === status);
  return index >= 0 ? index : -1;
}

function nextActionLabel(status) {
  if (!status) return "프로젝트 생성";
  if (status === "created") return "원본 업로드";
  if (status === "source_uploaded") return "추출 실행";
  if (status === "extracted") return "계정 반영";
  if (status === "mapped") return "변환 초안 생성";
  if (status === "draft_generated") return "검토 및 승인";
  if (status === "changes_requested") return "수정 후 재검토";
  if (status === "approved") return "완료";
  return labelFor(status);
}

function updateProgress(status) {
  const currentIndex = workflowIndex(status);
  $("#nextActionPill").textContent = nextActionLabel(status);
  $("#workflowSteps").innerHTML = workflowDefinitions.map((step, index) => {
    const state = index < currentIndex ? "done" : index === currentIndex ? "current" : "";
    return `
      <div class="step ${state}">
        <strong>${index + 1}. ${step.title}</strong>
        <span>${step.hint}</span>
      </div>
    `;
  }).join("");
}

function updateMetrics() {
  $("#metricUploads").textContent = uploads.length;
  $("#metricExtractions").textContent = extractions.length;
  $("#metricStatements").textContent = statements.length;
  $("#metricJudgments").textContent = statements.filter((statement) => statement.mapping_type === "judgment").length;
}

async function refreshOcrConfig() {
  const config = await api("/api/ocr-config");
  $("#ocrModePill").textContent = config.api_key_ready ? "연결 준비" : "샘플 모드";
  $("#ocrProvider").textContent = labelFor(config.provider) || config.provider;
  $("#ocrModel").textContent = config.model;
  $("#ocrApiKey").textContent = config.api_key_ready ? "서버 설정됨" : "관리자 설정 필요";
  $("#ocrFailureMode").textContent = config.manual_review_on_failure ? "수동 검토" : "자동 실패";
}

async function refreshAiConfig() {
  const config = await api("/api/ai-config");
  $("#aiModePill").textContent = config.api_key_ready ? "연결 준비" : "키 미설정";
  $("#aiProvider").textContent = labelFor(config.provider) || config.provider;
  $("#aiModel").textContent = config.model;
  $("#aiApiKey").textContent = config.api_key_ready ? "서버 설정됨" : "관리자 설정 필요";
  $("#aiReviewMode").textContent = config.human_review_required ? "사람 최종 검토" : "자동 확정";
}

async function refreshAccessConfig() {
  const res = await fetch("/api/access-config");
  const config = await res.json();
  accessRequired = Boolean(config.enabled);
  renderAccessPanel();
  return config;
}

async function refreshProtectedData() {
  await Promise.all([
    refreshProjects(),
    refreshOcrConfig(),
    refreshAiConfig(),
    refreshReferenceData(),
  ]);
}

async function refreshReferenceData() {
  const data = await api("/api/reference-data");
  const total = (data.summary || []).reduce((sum, item) => sum + Number(item.count || 0), 0);
  $("#referenceDbPill").textContent = `${total.toLocaleString()}건`;
  $("#referenceDbList").innerHTML = (data.summary || []).map((item) => `
    <div>
      <span>${escapeHtml(item.label)}</span>
      <strong>${Number(item.count || 0).toLocaleString()}건</strong>
    </div>
  `).join("");
}

function csvSample() {
  return [
    "계정명,금액",
    "현금및현금성자산,120000000",
    "매출채권,88000000",
    "재고자산,54000000",
    "리스부채,30000000",
    "개발비,45000000",
    "제품매출,240000000",
    "전환사채,70000000",
    "충당부채,18000000"
  ].join("\\n");
}

async function api(path, options = {}) {
  const headers = authHeaders({ "Content-Type": "application/json", ...(options.headers || {}) });
  const res = await fetch(path, {
    ...options,
    headers
  });
  const data = await res.json().catch(() => ({}));
  handleAccessError(data);
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}

async function uploadApi(path, file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(path, {
    method: "POST",
    headers: authHeaders(),
    body: form
  });
  const data = await res.json().catch(() => ({}));
  handleAccessError(data);
  if (!res.ok) throw new Error(data.error || "Upload failed");
  return data;
}

async function downloadApi(path, filename) {
  const res = await fetch(path, { headers: authHeaders() });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    handleAccessError(data);
    throw new Error(data.error || "Download failed");
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function setStatus(text) {
  $("#statusPill").textContent = labelFor(text);
  updateProgress(text);
}

function setReviewState(text) {
  $("#reviewPill").textContent = labelFor(text);
}

function setWorkflowEnabled(enabled) {
  $("#mapBtn").disabled = !enabled;
  $("#uploadBtn").disabled = !enabled;
}

function setExportEnabled(enabled) {
  $("#exportCsvBtn").disabled = !enabled;
  $("#exportReportBtn").disabled = !enabled;
}

function getChecklistResponses() {
  const responses = {};
  document.querySelectorAll("[data-statement]").forEach((cell) => {
    const id = cell.dataset.statement;
    responses[id] = {};
    cell.querySelectorAll("input").forEach((input) => {
      if (input.type === "checkbox") {
        responses[id][input.name] = input.checked;
      } else if (input.type === "number") {
        responses[id][input.name] = input.value === "" ? null : Number(input.value);
      } else {
        responses[id][input.name] = input.value;
      }
    });
  });
  return responses;
}

function checklistHtml(statement) {
  if (!statement.checklist || statement.checklist.length === 0) {
    return '<span class="badge">1:1 매핑</span>';
  }
  const controls = statement.checklist.map((item) => {
    const requiredMark = item.required ? '<span class="required-mark">필수</span>' : '<span class="badge">선택</span>';
    const placeholder = item.type === "number" ? "숫자 입력" : "내용 입력";
    if (item.type === "boolean") {
      return `
        <label class="checkline">
          <input type="checkbox" name="${item.key}">
          <span>${item.label}</span>
          ${requiredMark}
        </label>
      `;
    }
    return `
      <label class="checkitem">
        <span class="checklabel"><span>${item.label}</span>${requiredMark}</span>
        <input type="${item.type === "number" ? "number" : "text"}" name="${item.key}" placeholder="${placeholder}">
      </label>
    `;
  }).join("");
  return `<div class="checklist" data-statement="${statement.id}">${controls}</div>`;
}

function renderMapping() {
  updateMetrics();
  if (!statements.length) {
    $("#mappingTable").innerHTML = '<div class="table-empty">아직 매핑된 계정이 없습니다.</div>';
    return;
  }
  const rows = statements.map((s) => `
    <tr>
      <td>${s.account_name}</td>
      <td>${s.standard_code}<br>${s.normalized_account}</td>
      <td>${Number(s.amount).toLocaleString()}</td>
      <td><span class="badge ${s.mapping_type === "judgment" ? "warn" : ""}">${labelFor(s.mapping_type)}</span></td>
      <td>${s.rule_summary}</td>
      <td>${checklistHtml(s)}</td>
    </tr>
  `).join("");
  $("#mappingTable").innerHTML = `
    <table>
      <thead>
        <tr>
          <th>K-GAAP 계정</th>
          <th>내부 코드</th>
          <th>금액</th>
          <th>유형</th>
          <th>적용 룰</th>
          <th>체크리스트</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderValidation(result) {
  if (!result) {
    $("#validation").innerHTML = "";
    return;
  }
  const issueItems = [...(result.issues || []), ...(result.warnings || [])]
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  const checks = (result.checks || []).map((check) => `
    <div class="validation-check ${escapeHtml(check.status)}">
      <strong>${escapeHtml(check.name)} · ${labelFor(check.status)}</strong>
      <span>${escapeHtml(check.detail)}</span>
    </div>
  `).join("");
  $("#validation").innerHTML = `
    <div class="validation-summary">
      <span class="badge ${result.status === "passed" ? "" : "warn"}">${labelFor(result.status)}</span>
      <span>${Number(result.row_count || 0).toLocaleString()}개 행</span>
      <span>단순 매핑 ${Number(result.simple_count || 0).toLocaleString()}개</span>
      <span>판단 필요 ${Number(result.judgment_count || 0).toLocaleString()}개</span>
      <span>합계 ${Number(result.total_amount || 0).toLocaleString()}</span>
    </div>
    ${checks ? `<div class="validation-checks">${checks}</div>` : ""}
    ${issueItems ? `<ul class="issues">${issueItems}</ul>` : ""}
  `;
}

function renderDraft(draft) {
  if (!draft) {
    $("#outputBox").className = "draft-empty";
    $("#outputBox").innerHTML = "아직 생성된 변환 초안이 없습니다.";
    return;
  }
  $("#outputBox").className = "draft-view";
  const entries = draft.entries || [];
  const entryRows = entries.map((entry) => `
    <tr>
      <td>${escapeHtml(entry.source_account)}</td>
      <td>${escapeHtml(entry.standard_code)}</td>
      <td>${escapeHtml(entry.target_account)}</td>
      <td>${escapeHtml(entry.statement_type || "-")} · ${escapeHtml(entry.statement_line_item || "-")}</td>
      <td>${Number(entry.amount || 0).toLocaleString()}</td>
      <td>${Number(entry.adjustment || 0).toLocaleString()}</td>
      <td>${escapeHtml(localizeText(entry.calculation || entry.basis || "-"))}</td>
    </tr>
  `).join("");
  const judgmentCards = (draft.judgment_items || []).map((item) => `
    <div class="draft-card">
      <strong>${escapeHtml(item.account)}</strong>
      <span>${escapeHtml(localizeText(item.basis))}</span>
    </div>
  `).join("");
  const noteCards = (draft.draft_notes || []).map((note) => `
    <div class="draft-card">
      <strong>${escapeHtml(note.account)}</strong>
      <span>${escapeHtml(localizeText(note.draft_note))}</span>
    </div>
  `).join("");
  const ai = draft.ai_assistance || {};
  const aiCards = (ai.items || []).map((item) => {
    const questions = (item.additional_questions || []).map((question) => escapeHtml(question)).join("<br>");
    return `
      <div class="draft-card">
        <strong>${escapeHtml(item.account || "-")} · 위험도 ${escapeHtml(riskLabel(item.risk_level))}</strong>
        <span>${escapeHtml(localizeText(item.classification_hint || "-"))}</span>
        <span>${escapeHtml(localizeText(item.review_note || "-"))}</span>
        <span>근거 요약: ${escapeHtml(localizeText(item.basis_summary || "-"))}</span>
        <span>추가 질문: ${questions || "-"}</span>
      </div>
    `;
  }).join("");
  const aiIssues = (ai.issues || []).map((issue) => `<li>${escapeHtml(localizeText(issue))}</li>`).join("");
  const aiStatus = `${labelFor(ai.status || "not_configured")} · ${ai.model || "모델 미설정"}`;
  $("#outputBox").innerHTML = `
    <div class="draft-summary">
      <strong>${escapeHtml(draft.project?.company_name || "-")} · ${escapeHtml(draft.project?.period || "-")}</strong>
      <span>${escapeHtml(draft.project?.source_standard || "K-GAAP")} → ${escapeHtml(draft.project?.target_standard || "IFRS")} · ${escapeHtml(localizeText(draft.review_status || "검토 필요"))}</span>
      <span>생성 시각 ${draft.generated_at ? new Date(draft.generated_at).toLocaleString() : "-"}</span>
    </div>
    <div class="draft-section">
      <h3>조정분개 리스트</h3>
      <table>
        <thead>
          <tr>
            <th>원 계정</th>
            <th>코드</th>
            <th>IFRS 계정</th>
            <th>표시 양식</th>
            <th>금액</th>
            <th>조정액</th>
            <th>계산/근거</th>
          </tr>
        </thead>
        <tbody>${entryRows || '<tr><td colspan="7">생성된 조정분개가 없습니다.</td></tr>'}</tbody>
      </table>
    </div>
    <div class="draft-section">
      <h3>판단 필요 항목</h3>
      <div class="draft-list">${judgmentCards || '<div class="draft-empty">판단 필요 항목이 없습니다.</div>'}</div>
    </div>
    <div class="draft-section">
      <h3>Claude 판단 보조</h3>
      <div class="draft-list">
        <div class="draft-card">
          <strong>${escapeHtml(aiStatus)}</strong>
          <span>${escapeHtml(localizeText(ai.overall_note || "Claude 판단 보조 결과가 없습니다."))}</span>
          ${aiIssues ? `<ul class="issues">${aiIssues}</ul>` : ""}
        </div>
        ${aiCards || '<div class="draft-empty">표시할 판단 보조 결과가 없습니다.</div>'}
      </div>
    </div>
    <div class="draft-section">
      <h3>주석 초안</h3>
      <div class="draft-list">${noteCards || '<div class="draft-empty">생성된 주석 초안이 없습니다.</div>'}</div>
    </div>
  `;
}

function renderUploads() {
  updateMetrics();
  if (!uploads.length) {
    $("#uploadList").innerHTML = '<div class="file-empty">업로드된 파일이 없습니다.</div>';
    return;
  }
  $("#uploadList").innerHTML = uploads.map((file) => `
      <div class="file-item">
        <strong>${file.original_name}</strong>
        <span>${file.content_type} · ${Number(file.size_bytes).toLocaleString()} bytes · ${labelFor(file.extraction_status)}</span>
        <div class="item-actions">
          <button class="ghost extract-btn" data-upload-id="${file.id}">추출 실행</button>
        </div>
      </div>
  `).join("");
  document.querySelectorAll("[data-upload-id]").forEach((button) => {
    button.addEventListener("click", () => extractUpload(button.dataset.uploadId));
  });
}

function renderExtractions() {
  updateMetrics();
  if (!extractions.length) {
    $("#extractionList").innerHTML = '<div class="file-empty">아직 추출 결과가 없습니다.</div>';
    $("#extractionPill").textContent = "대기";
    return;
  }
  $("#extractionPill").textContent = labelFor(extractions[0].status);
  $("#extractionList").innerHTML = extractions.map((extraction) => {
    const rows = (extraction.rows || []).map((row) => `
      <tr><td>${row.account_name}</td><td>${Number(row.amount).toLocaleString()}</td></tr>
    `).join("");
    const issues = (extraction.issues || []).map((issue) => `<li>${issue}</li>`).join("");
    return `
      <div class="file-item">
        <strong>${labelFor(extraction.provider)} · ${labelFor(extraction.status)}</strong>
        <span>${(extraction.rows || []).length}개 행 추출</span>
        <table>
          <thead><tr><th>계정명</th><th>금액</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
        ${issues ? `<ul class="issues">${issues}</ul>` : ""}
        <div class="item-actions">
          <button class="primary accept-extraction-btn" data-extraction-id="${extraction.id}" ${extraction.status === "accepted" ? "disabled" : ""}>계정 반영</button>
        </div>
      </div>
    `;
  }).join("");
  document.querySelectorAll("[data-extraction-id]").forEach((button) => {
    button.addEventListener("click", () => acceptExtraction(button.dataset.extractionId));
  });
}

function renderProjects() {
  if (!projects.length) {
    $("#projectList").innerHTML = '<div class="project-empty">저장된 프로젝트가 없습니다.</div>';
    return;
  }
  $("#projectList").innerHTML = projects.map((project) => `
    <button class="project-item ${project.id === activeProjectId ? "active" : ""}" data-project-id="${project.id}">
      <strong>${project.company_name}</strong>
      <span>${project.period} · ${project.target_standard} · ${labelFor(project.status)}</span>
    </button>
  `).join("");
  document.querySelectorAll("[data-project-id]").forEach((button) => {
    button.addEventListener("click", () => loadProject(button.dataset.projectId));
  });
}

async function refreshProjects() {
  projects = await api("/api/projects");
  renderProjects();
}

function resetWorkspace() {
  statements = [];
  uploads = [];
  extractions = [];
  hasDraft = false;
  renderMapping();
  renderUploads();
  renderExtractions();
  updateMetrics();
  renderDraft(null);
  $("#validation").textContent = "";
  $("#approveBtn").disabled = true;
  $("#requestChangesBtn").disabled = true;
  setExportEnabled(false);
  setReviewState("대기");
  updateProgress(null);
}

function syncProjectForm(project) {
  $("#projectForm").elements.company_name.value = project.company_name;
  $("#projectForm").elements.period.value = project.period;
  $("#projectForm").elements.source_standard.value = project.source_standard;
  $("#projectForm").elements.target_standard.value = project.target_standard;
}

async function loadProject(projectId) {
  const data = await api(`/api/projects/${projectId}`);
  activeProjectId = data.project.id;
  syncProjectForm(data.project);
  setStatus(data.project.status);
  statements = data.statements || [];
  uploads = data.uploads || [];
  extractions = data.extractions || [];
  renderMapping();
  renderValidation(null);
  renderUploads();
  renderExtractions();
  hasDraft = Boolean(data.conversion);
  renderDraft(data.conversion);
  $("#validateBtn").disabled = statements.length === 0;
  $("#convertBtn").disabled = statements.length === 0;
  $("#approveBtn").disabled = !hasDraft;
  $("#requestChangesBtn").disabled = !hasDraft;
  setExportEnabled(hasDraft);
  setWorkflowEnabled(true);
  if (data.review) {
    setReviewState(data.review.decision === "approved" ? "approved" : "changes_requested");
    $("#reviewerName").value = data.review.reviewer_name;
    $("#reviewMemo").value = data.review.memo;
  } else {
    setReviewState(hasDraft ? "검토 가능" : "대기");
  }
  await refreshAudit();
  renderProjects();
}

async function refreshAudit() {
  if (!activeProjectId) return;
  const logs = await api(`/api/projects/${activeProjectId}/audit`);
  $("#auditLog").innerHTML = logs.length ? logs.map((log) => {
    const detailRows = auditDetailRows(log);
    return `
      <div class="log-item">
        <strong>${labelFor(log.event_type)}</strong>
        <span>${new Date(log.created_at).toLocaleString()} by ${escapeHtml(log.actor)}</span>
        ${detailRows ? `<div class="log-detail">${detailRows}</div>` : ""}
      </div>
    `;
  }).join("") : '<div class="log-empty">아직 기록된 이벤트가 없습니다.</div>';
}

$("#sampleBtn").addEventListener("click", () => {
  $("#csvInput").value = csvSample();
});

$("#saveAccessCodeBtn").addEventListener("click", async () => {
  const code = $("#accessCodeInput").value.trim();
  if (!code) {
    renderAccessPanel("접근 코드를 입력하세요.");
    return;
  }
  sessionStorage.setItem(accessStorageKey, code);
  renderAccessPanel("접근 코드가 저장되었습니다. 데이터를 다시 불러옵니다.");
  try {
    await refreshProtectedData();
    renderAccessPanel("접근 코드가 확인되었습니다.");
  } catch (error) {
    renderAccessPanel(error.message || "접근 코드 확인에 실패했습니다.");
  }
});

$("#clearAccessCodeBtn").addEventListener("click", () => {
  sessionStorage.removeItem(accessStorageKey);
  renderAccessPanel("접근 코드가 초기화되었습니다.");
});

$("#projectForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = Object.fromEntries(form.entries());
  const project = await api("/api/projects", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  activeProjectId = project.id;
  setStatus(project.status);
  setWorkflowEnabled(true);
  $("#validateBtn").disabled = true;
  $("#convertBtn").disabled = true;
  $("#approveBtn").disabled = true;
  $("#requestChangesBtn").disabled = true;
  setExportEnabled(false);
  hasDraft = false;
  setReviewState("대기");
  statements = [];
  uploads = [];
  extractions = [];
  renderMapping();
  renderUploads();
  renderExtractions();
  renderDraft(null);
  $("#validation").textContent = "";
  await refreshProjects();
  await refreshAudit();
});

$("#uploadBtn").addEventListener("click", async () => {
  const file = $("#fileInput").files[0];
  if (!file) {
    $("#uploadList").innerHTML = '<div class="file-empty">먼저 PDF, Excel, CSV 또는 이미지 파일을 선택하세요.</div>';
    return;
  }
  const upload = await uploadApi(`/api/projects/${activeProjectId}/uploads`, file);
  uploads = [upload, ...uploads];
  renderUploads();
  setStatus("source_uploaded");
  await refreshProjects();
  await refreshAudit();
});

async function extractUpload(uploadId) {
  const extraction = await api(`/api/projects/${activeProjectId}/uploads/${uploadId}/extract`, {
    method: "POST",
    body: "{}"
  });
  extractions = [extraction, ...extractions];
  uploads = uploads.map((upload) => (
    upload.id === uploadId ? { ...upload, extraction_status: extraction.status } : upload
  ));
  renderUploads();
  renderExtractions();
  setStatus("extracted");
  await refreshProjects();
  await refreshAudit();
}

async function acceptExtraction(extractionId) {
  const result = await api(`/api/projects/${activeProjectId}/extractions/${extractionId}/accept`, {
    method: "POST",
    body: "{}"
  });
  statements = [...statements, ...result.statements];
  extractions = extractions.map((extraction) => (
    extraction.id === extractionId ? { ...extraction, status: "accepted" } : extraction
  ));
  renderMapping();
  renderExtractions();
  $("#validateBtn").disabled = false;
  $("#convertBtn").disabled = false;
  setStatus("mapped");
  await refreshProjects();
  await refreshAudit();
}

$("#mapBtn").addEventListener("click", async () => {
  const result = await api(`/api/projects/${activeProjectId}/statements`, {
    method: "POST",
    body: JSON.stringify({ csv_text: $("#csvInput").value, source: "manual_csv" })
  });
  statements = result.statements;
  renderMapping();
  $("#validateBtn").disabled = false;
  $("#convertBtn").disabled = false;
  setStatus("mapped");
  await refreshProjects();
  await refreshAudit();
});

$("#validateBtn").addEventListener("click", async () => {
  const result = await api(`/api/projects/${activeProjectId}/validate`, { method: "POST", body: "{}" });
  renderValidation(result);
  await refreshAudit();
});

$("#convertBtn").addEventListener("click", async () => {
  const result = await api(`/api/projects/${activeProjectId}/convert`, {
    method: "POST",
    body: JSON.stringify({ responses: getChecklistResponses() })
  });
  renderDraft(result);
  setStatus("draft_generated");
  hasDraft = true;
  $("#approveBtn").disabled = false;
  $("#requestChangesBtn").disabled = false;
  setExportEnabled(true);
  setReviewState("검토 가능");
  await refreshProjects();
  await refreshAudit();
});

async function submitReview(decision) {
  if (!hasDraft) return;
  const review = await api(`/api/projects/${activeProjectId}/review`, {
    method: "POST",
    body: JSON.stringify({
      decision,
      reviewer_name: $("#reviewerName").value,
      memo: $("#reviewMemo").value
    })
  });
  const label = review.decision === "approved" ? "approved" : "changes_requested";
  setStatus(label);
  setReviewState(label);
  await refreshProjects();
  await refreshAudit();
}

$("#approveBtn").addEventListener("click", () => submitReview("approved"));
$("#requestChangesBtn").addEventListener("click", () => submitReview("changes_requested"));
$("#refreshProjectsBtn").addEventListener("click", refreshProjects);
$("#exportCsvBtn").addEventListener("click", () => {
  if (!activeProjectId || !hasDraft) return;
  downloadApi(`/api/projects/${activeProjectId}/exports/adjustments.csv`, "gtf_adjustments.csv");
});
$("#exportReportBtn").addEventListener("click", () => {
  if (!activeProjectId || !hasDraft) return;
  downloadApi(`/api/projects/${activeProjectId}/exports/basis-report.txt`, "gtf_basis_report.txt");
});

$("#csvInput").value = csvSample();
updateProgress(null);
updateMetrics();

async function initApp() {
  await refreshAccessConfig();
  if (accessRequired && !savedAccessCode()) {
    renderAccessPanel("운영자가 발급한 접근 코드를 입력하면 프로젝트 데이터를 불러옵니다.");
    return;
  }
  try {
    await refreshProtectedData();
  } catch (error) {
    renderAccessPanel(error.message || "초기 데이터를 불러오지 못했습니다.");
  }
}

initApp();
"""


def main() -> None:
    init_db()
    port = int(os.environ.get("PORT", "4173"))
    host = os.environ.get("HOST", "127.0.0.1")
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"GTF server running on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
