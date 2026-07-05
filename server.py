from __future__ import annotations

import csv
import base64
import io
import importlib.util
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import uuid
import zipfile
from decimal import Decimal
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import xml.etree.ElementTree as ET
from urllib import error as url_error
from urllib import request as url_request
from urllib.parse import parse_qs, urlparse

from gtf_app.auth import (
    admin_config,
    hash_password,
    normalize_email,
    session_token_hash,
    user_public_dict,
    verify_password,
)
from gtf_app.dart import (
    dart_raw_rows_from_upload,
    dart_raw_statement_rows,
    dart_statement_rows,
    fetch_dart_available_reports,
    fetch_dart_statement_rows,
    normalize_dart_amount,
)
from gtf_app.domain import (
    CHECKLISTS,
    FINANCIAL_STATEMENT_TEMPLATES,
    STANDARD_ACCOUNTS,
    build_statement_record,
    conversion_adjustments_csv,
    conversion_basis_report,
    generate_conversion,
    looks_numeric,
    normalize_account_name,
    parse_amount,
    parse_statement_rows,
    validate_statement_records,
)
from gtf_app.excel_export import review_workbook_bytes
from gtf_app.routing import PUBLIC_PATHS, resolve_delete, resolve_get, resolve_post


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "gtf.sqlite3"
SQLITE_SCHEMA_PATH = ROOT / "sqlite" / "schema.sql"
FIGMA_DIST_DIR = ROOT / "figma_make" / "dist"
ENV_PATHS = (ROOT / ".env", ROOT / ".env.local")
GEMINI_INLINE_LIMIT_BYTES = 20 * 1024 * 1024
OPENAI_API_ENDPOINT = "https://api.openai.com/v1/responses"
OPENAI_DEFAULT_MODEL = "gpt-4.1-mini"
SESSION_COOKIE = "gtf_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 7
ADMIN_USER_ID = "admin"
DEMO_USER_ID = "demo"
DEFAULT_DEMO_EMAIL = "demo@gtf.local"
DEFAULT_DEMO_PASSWORD = "change-this-demo-password"
INDEX_HTML = """<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>GTF</title></head>
<body><main><h1>GTF</h1><p>Figma UI build is not available. Run the frontend build and try again.</p></main></body>
</html>"""
STYLES_CSS = "body{font-family:system-ui,sans-serif;margin:2rem}"
APP_JS = "console.info('GTF fallback bundle')"


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


def upload_public_dict(row_or_upload) -> dict:
    upload = row_to_dict(row_or_upload) if hasattr(row_or_upload, "keys") else dict(row_or_upload)
    upload.pop("file_bytes", None)
    upload["db_file_ready"] = bool(row_or_upload["file_bytes"]) if hasattr(row_or_upload, "keys") and "file_bytes" in row_or_upload.keys() else bool(row_or_upload.get("file_bytes"))
    return upload


def figma_static_file(path: str) -> Path | None:
    if not FIGMA_DIST_DIR.exists():
        return None
    relative = "index.html" if path == "/" else path.lstrip("/")
    candidate = (FIGMA_DIST_DIR / relative).resolve()
    try:
        candidate.relative_to(FIGMA_DIST_DIR.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


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
            conn.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS owner_user_id text")
            conn.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS is_test boolean NOT NULL DEFAULT false")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_owner_created_at ON projects(owner_user_id, created_at DESC)")
            conn.execute("ALTER TABLE uploads ADD COLUMN IF NOT EXISTS file_bytes bytea")
            ensure_auth_tables(conn)
            conn.execute("ALTER TABLE app_users ADD COLUMN IF NOT EXISTS is_read_only boolean NOT NULL DEFAULT false")
            ensure_admin_user(conn)
        return
    with connect() as conn:
        conn.executescript(SQLITE_SCHEMA_PATH.read_text(encoding="utf-8"))
        user_columns = [row["name"] for row in conn.execute("PRAGMA table_info(app_users)").fetchall()]
        if "is_read_only" not in user_columns:
            conn.execute("ALTER TABLE app_users ADD COLUMN is_read_only INTEGER NOT NULL DEFAULT 0")
        upload_columns = [row["name"] for row in conn.execute("PRAGMA table_info(uploads)").fetchall()]
        if "file_bytes" not in upload_columns:
            conn.execute("ALTER TABLE uploads ADD COLUMN file_bytes BLOB")
        project_columns = [row["name"] for row in conn.execute("PRAGMA table_info(projects)").fetchall()]
        if "owner_user_id" not in project_columns:
            conn.execute("ALTER TABLE projects ADD COLUMN owner_user_id TEXT")
        if "is_test" not in project_columns:
            conn.execute("ALTER TABLE projects ADD COLUMN is_test INTEGER NOT NULL DEFAULT 0")
        seed_reference_data(conn)
        ensure_admin_user(conn)


def ensure_auth_tables(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_read_only BOOLEAN NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES app_users(id)
        )
        """
    )


def ensure_admin_user(conn) -> None:
    config = admin_config()
    if not config["configured"]:
        return
    now = utc_now()
    row = conn.execute("SELECT id FROM app_users WHERE id = ?", (ADMIN_USER_ID,)).fetchone()
    password_hash = hash_password(os.environ.get("ADMIN_PASSWORD") or os.environ.get("GTF_ADMIN_PASSWORD") or "")
    read_only = bool(config["read_only"])
    if row:
        conflicting = conn.execute(
            "SELECT id FROM app_users WHERE email = ? AND id != ?",
            (config["email"], ADMIN_USER_ID),
        ).fetchone()
        if conflicting:
            conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (conflicting["id"],))
            conn.execute("DELETE FROM app_users WHERE id = ?", (conflicting["id"],))
        conn.execute(
            "UPDATE app_users SET email = ?, password_hash = ?, is_read_only = ? WHERE id = ?",
            (config["email"], password_hash, read_only, ADMIN_USER_ID),
        )
        return
    existing = conn.execute("SELECT id FROM app_users WHERE email = ?", (config["email"],)).fetchone()
    if existing:
        conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (existing["id"],))
        conn.execute(
            "UPDATE app_users SET id = ?, password_hash = ?, is_read_only = ? WHERE email = ?",
            (ADMIN_USER_ID, password_hash, read_only, config["email"]),
        )
        return
    conn.execute(
        "INSERT INTO app_users (id, email, password_hash, is_read_only, created_at) VALUES (?, ?, ?, ?, ?)",
        (ADMIN_USER_ID, config["email"], password_hash, read_only, now),
    )


def demo_config() -> dict:
    enabled_env = os.environ.get("DEMO_LOGIN_ENABLED") or os.environ.get("GTF_DEMO_LOGIN_ENABLED") or "true"
    enabled = enabled_env.strip().lower() not in {"0", "false", "no", "off"}
    email = normalize_email(os.environ.get("DEMO_EMAIL") or os.environ.get("GTF_DEMO_EMAIL") or DEFAULT_DEMO_EMAIL)
    password = os.environ.get("DEMO_PASSWORD") or os.environ.get("GTF_DEMO_PASSWORD") or DEFAULT_DEMO_PASSWORD
    return {"enabled": enabled, "email": email, "password": password}


def ensure_demo_user(conn) -> dict | None:
    config = demo_config()
    if not config["enabled"] or not config["email"]:
        return None
    now = utc_now()
    password_hash = hash_password(config["password"])
    row = conn.execute("SELECT * FROM app_users WHERE email = ?", (config["email"],)).fetchone()
    if row:
        conn.execute(
            "UPDATE app_users SET password_hash = ?, is_read_only = ? WHERE id = ?",
            (password_hash, True, row["id"]),
        )
        return row_to_dict(conn.execute("SELECT * FROM app_users WHERE id = ?", (row["id"],)).fetchone())
    conn.execute(
        "INSERT INTO app_users (id, email, password_hash, is_read_only, created_at) VALUES (?, ?, ?, ?, ?)",
        (DEMO_USER_ID, config["email"], password_hash, True, now),
    )
    return row_to_dict(conn.execute("SELECT * FROM app_users WHERE id = ?", (DEMO_USER_ID,)).fetchone())


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


def clean_pdf_account_name(value) -> str:
    text = re.sub(r"\s+", " ", str(value or "").replace("\n", " ")).strip()
    text = re.sub(r"\(주석\s*[^)]*\)", "", text).strip()
    text = re.sub(r"^[ㆍ·]\s*", "", text)
    text = re.sub(r"^(?:[0-9]+\.|\([0-9]+\)|[가-힣]\.|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩXI]+\.?)\s*", "", text).strip()
    return text


def pdf_statement_account_key(name: str) -> str:
    compact = re.sub(r"\s+", "", name)
    if not compact:
        return "other"
    exclusions = [
        "매출원가",
        "매출총이익",
        "영업활동",
        "현금흐름",
        "현금의유입",
        "현금의유출",
        "현금유입",
        "현금유출",
        "활동으로인한",
        "감소",
        "증가",
        "기초",
        "기말",
        "감가상각",
        "상각비",
        "처분손실",
        "처분이익",
        "당기순",
        "주당",
        "전환사채발행",
        "유상증자",
        "주식선택권",
        "토지재평가",
        "영업외수익",
        "이자수익",
    ]
    if any(token in compact for token in exclusions):
        return "other"
    return normalize_account_name(name)


def pdf_row_current_amount(row: list) -> float | None:
    for cell in row[1:]:
        if looks_numeric(cell):
            return parse_amount(cell)
    return None


def parse_pdf_text_statement_rows(text: str) -> list[dict]:
    rows: list[dict] = []
    account_keywords = {
        "cash": ["현금및현금성자산", "현금및 현금성자산", "현금성자산"],
        "receivables": ["매출채권", "미수금", "미수수익", "계약자산"],
        "inventory": ["재고자산", "상품", "제품", "원재료"],
        "lease": ["사용권자산", "리스부채"],
        "development": ["개발비", "무형자산"],
        "revenue": ["매출액", "매출", "영업수익", "수익"],
        "financial_instrument": ["금융자산", "금융부채", "단기차입금", "장기차입금", "전환사채", "파생상품"],
        "provision": ["충당부채", "판매보증충당부채", "복구충당부채"],
    }
    amount_pattern = r"\(?-?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?|\(?-?\d{5,}(?:\.\d+)?\)?"
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line or len(line) > 180:
            continue
        compact = re.sub(r"\s+", "", line)
        matched_name = ""
        for keywords in account_keywords.values():
            matched_name = next((keyword for keyword in keywords if keyword.replace(" ", "") in compact), "")
            if matched_name:
                break
        if not matched_name:
            continue
        amounts = re.findall(amount_pattern, line)
        if not amounts:
            continue
        rows.append({"account_name": matched_name, "amount": parse_amount(amounts[0])})
    return rows


def parse_pdf_statement_rows(path: Path) -> tuple[list[dict], list[str]]:
    try:
        import pdfplumber
    except ImportError:
        return [], ["PDF 표 직접 추출을 위해 pdfplumber 패키지가 필요합니다."]

    rows: list[dict] = []
    issues: list[str] = []
    started = False
    pages_scanned = 0

    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            compact_text = re.sub(r"\s+", "", text)
            if started and "재무제표주석" in compact_text:
                break
            if any(marker in compact_text for marker in ("재무상태표", "손익계산서", "현금흐름표", "자본변동표")):
                started = True
            if not started:
                continue

            pages_scanned += 1
            for row in parse_pdf_text_statement_rows(text):
                rows.append(row)
            for table in page.extract_tables() or []:
                for raw_row in table:
                    if not raw_row:
                        continue
                    name = clean_pdf_account_name(raw_row[0])
                    if not name or name in {"과목", "과 목", "구분", "자산", "자 산", "부채", "자본"}:
                        continue
                    account_key = pdf_statement_account_key(name)
                    if account_key == "other":
                        continue
                    amount = pdf_row_current_amount(raw_row)
                    if amount is None:
                        continue
                    rows.append({"account_name": name, "amount": amount})

    deduped: list[dict] = []
    seen: set[tuple[str, float]] = set()
    for row in rows:
        key = (row["account_name"], float(row["amount"]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    if pages_scanned:
        issues.append(f"PDF 표 직접 추출: 재무제표 본문 {pages_scanned}쪽을 분석했습니다.")
    if not deduped:
        issues.append("PDF 표는 읽었지만 변환 가능한 핵심 계정 행을 찾지 못했습니다.")
    return deduped, issues


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


def ai_config() -> dict:
    model = os.environ.get("OPENAI_MODEL", OPENAI_DEFAULT_MODEL).strip() or OPENAI_DEFAULT_MODEL
    api_key_source = "environment" if os.environ.get("OPENAI_API_KEY") else "none"
    api_key_ready = api_key_source != "none"
    return {
        "provider": "openai",
        "model": model,
        "api_key_ready": api_key_ready,
        "api_key_source": api_key_source,
        "mode": "connected" if api_key_ready else "not_configured",
        "human_review_required": True,
    }


def access_config() -> dict:
    return {
        "enabled": False,
        "header": "X-GTF-Access-Code",
        "mode": "open",
    }


def dart_config() -> dict:
    return {
        "provider": "opendart",
        "api_key_ready": bool(os.environ.get("DART_API_KEY", "").strip()),
        "corp_code_lookup": True,
        "supported_reports": {
            "11013": "1분기보고서",
            "11012": "반기보고서",
            "11014": "3분기보고서",
            "11011": "사업보고서",
        },
        "supported_fs_div": {"CFS": "연결", "OFS": "별도"},
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
    json_like_texts: list[str] = []

    def collect_text(value) -> None:
        if isinstance(value, dict):
            for key in ("output_text", "text"):
                if isinstance(value.get(key), str) and value[key].strip():
                    texts.append(value[key])
            for item in value.values():
                if isinstance(item, str) and '"rows"' in item and "account_name" in item:
                    json_like_texts.append(item)
            for key in ("model_output", "content", "parts", "steps", "output", "outputs"):
                collect_text(value.get(key))
        elif isinstance(value, list):
            for item in value:
                collect_text(item)

    collect_text(response.get("model_output"))
    collect_text(response.get("steps"))
    collect_text(response.get("output"))
    if texts:
        return "\n".join(texts).strip()
    if json_like_texts:
        return "\n".join(json_like_texts).strip()

    candidates = response.get("candidates") or []
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts") or []
    candidate_texts = [part.get("text", "") for part in parts if isinstance(part.get("text"), str)]
    return "\n".join(candidate_texts).strip()


def openai_response_text(response: dict) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"].strip()
    content = response.get("content") or []
    texts = []
    output = response.get("output") or []
    for item in output:
        for part in item.get("content", []) if isinstance(item, dict) else []:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                texts.append(part["text"])
    for part in content:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            texts.append(part["text"])
    return "\n".join(texts).strip()


def call_ai_judgment(project: dict, entries: list[dict], judgment_items: list[dict]) -> dict:
    config = ai_config()
    if not judgment_items:
        return {
            "provider": "openai",
            "model": config["model"],
            "status": "skipped",
            "items": [],
            "overall_note": "판단 필요 항목이 없어 OpenAI 판단 보조를 건너뛰었습니다.",
            "human_review_required": True,
        }
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {
            "provider": "openai",
            "model": config["model"],
            "status": "not_configured",
            "items": [],
            "overall_note": "OPENAI_API_KEY가 서버 환경변수에 설정되지 않아 규정 근거 요약은 생성하지 않았습니다.",
            "issues": ["OPENAI_API_KEY가 서버 환경변수에 설정되지 않았습니다."],
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
        "max_output_tokens": 1200,
        "instructions": (
            "너는 K-GAAP 재무제표를 IFRS 초안으로 변환하는 회계 검토 보조자다. "
            "최종 회계처리를 확정하지 말고, 사용자가 입력한 체크리스트와 변환 초안을 바탕으로 "
            "판단 필요 항목, 추가 질문, 기준 근거 요약만 한국어로 제시한다. "
            "반드시 사람이 최종 검토하고 승인해야 한다는 전제를 유지한다. JSON만 반환한다."
        ),
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "다음 변환 초안의 판단 필요 항목을 검토해 JSON만 반환하세요. "
                            "마크다운과 설명 문장은 쓰지 마세요.\n"
                            + json.dumps(prompt, ensure_ascii=False)
                        ),
                    }
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "gtf_judgment_assistance",
                "schema": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "account": {"type": "string"},
                                    "risk_level": {"type": "string"},
                                    "classification_hint": {"type": "string"},
                                    "additional_questions": {"type": "array", "items": {"type": "string"}},
                                    "review_note": {"type": "string"},
                                    "basis_summary": {"type": "string"},
                                },
                                "required": [
                                    "account",
                                    "risk_level",
                                    "classification_hint",
                                    "additional_questions",
                                    "review_note",
                                    "basis_summary",
                                ],
                                "additionalProperties": False,
                            },
                        },
                        "overall_note": {"type": "string"},
                    },
                    "required": ["items", "overall_note"],
                    "additionalProperties": False,
                },
                "strict": True,
            }
        },
    }
    request = url_request.Request(
        OPENAI_API_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with url_request.urlopen(request, timeout=45) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except url_error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")[:500]
        return {
            "provider": "openai",
            "model": config["model"],
            "status": "failed",
            "items": [],
            "overall_note": "OpenAI 판단 보조 요청이 실패했습니다. 변환 초안은 저장되며 사람이 검토해야 합니다.",
            "issues": [f"OpenAI 요청 실패: HTTP {exc.code}", message],
            "human_review_required": True,
        }
    except url_error.URLError as exc:
        return {
            "provider": "openai",
            "model": config["model"],
            "status": "failed",
            "items": [],
            "overall_note": "OpenAI 판단 보조 네트워크 오류가 발생했습니다.",
            "issues": [f"OpenAI 네트워크 오류: {exc.reason}"],
            "human_review_required": True,
        }
    except TimeoutError:
        return {
            "provider": "openai",
            "model": config["model"],
            "status": "failed",
            "items": [],
            "overall_note": "OpenAI 판단 보조 요청 시간이 초과되었습니다.",
            "issues": ["OpenAI 요청 시간이 초과되었습니다."],
            "human_review_required": True,
        }

    text = openai_response_text(response_payload)
    if not text:
        return {
            "provider": "openai",
            "model": config["model"],
            "status": "failed",
            "items": [],
            "overall_note": "OpenAI 응답에서 검토 텍스트를 찾지 못했습니다.",
            "issues": ["OpenAI 응답 텍스트가 비어 있습니다."],
            "human_review_required": True,
        }
    try:
        parsed = extract_json_object(text)
    except json.JSONDecodeError:
        return {
            "provider": "openai",
            "model": config["model"],
            "status": "failed",
            "items": [],
            "overall_note": "OpenAI 응답을 JSON으로 해석하지 못했습니다.",
            "issues": ["OpenAI 응답 JSON 해석 실패", text[:500]],
            "human_review_required": True,
        }

    items = parsed.get("items") if isinstance(parsed.get("items"), list) else []
    return {
        "provider": "openai",
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
        response_keys = ", ".join(sorted(response_payload.keys())) or "없음"
        return [], [f"Gemini OCR 응답에서 추출 텍스트를 찾지 못했습니다. 응답 키: {response_keys}"]
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


def upload_file_path(upload: dict) -> Path:
    stored_path = UPLOAD_DIR / upload["stored_name"]
    if stored_path.exists():
        return stored_path
    file_bytes = upload.get("file_bytes")
    if isinstance(file_bytes, memoryview):
        file_bytes = file_bytes.tobytes()
    if isinstance(file_bytes, bytes):
        stored_path.write_bytes(file_bytes)
        return stored_path
    raise FileNotFoundError("업로드 원본 파일을 로컬 디스크 또는 DB에서 찾지 못했습니다.")


def extract_rows_from_upload(upload: dict) -> tuple[list[dict], list[str], str]:
    try:
        stored_path = upload_file_path(upload)
    except FileNotFoundError as exc:
        return [], [str(exc)], "missing_upload_file"
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
    pdf_table_issues: list[str] = []
    if suffix == ".pdf" or ocr_mime == "application/pdf":
        rows, pdf_table_issues = parse_pdf_statement_rows(stored_path)
        if rows:
            return rows, pdf_table_issues, "local_pdf_table_parser"
        if pdf_table_issues:
            pdf_table_issues = [*pdf_table_issues, "PDF 표 직접 추출 실패 후 OCR 분석으로 전환합니다."]

    if config["api_key_ready"] and config["provider"] == "gemini" and ocr_mime:
        rows, issues = call_gemini_ocr(stored_path, ocr_mime, config["model"])
        issues = [*pdf_table_issues, f"OCR 제공자: {config['provider']} / 모델: {config['model']}", *issues]
        return rows, issues, "gemini_ocr"

    if ocr_mime:
        return (
            [],
            [
                *pdf_table_issues,
                f"OCR 제공자: {config['provider']} / 모델: {config['model']}",
                "서버 OCR 키가 설정되지 않아 실제 PDF/이미지 분석을 실행하지 못했습니다.",
                "관리자가 서버 환경변수 GEMINI_API_KEY를 설정한 뒤 다시 분석하세요.",
            ],
            "ocr_not_configured",
        )

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



class AppHandler(BaseHTTPRequestHandler):
    server_version = "GTFServer/0.1"
    public_paths = PUBLIC_PATHS

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        static_file = figma_static_file(path)
        if static_file is not None:
            self.respond_file(static_file)
            return
        if path not in self.public_paths and not self.require_access():
            return
        route = resolve_get(path)
        if route is None:
            self.respond_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        elif route.name == "index":
            self.respond_html(INDEX_HTML)
        elif route.name == "healthz":
            self.respond_json(
                {
                    "status": "ok",
                    "service": "gtf-accounting-conversion",
                    "time": utc_now(),
                    "database": database_ready(),
                    "database_config": database_config(),
                    "ocr": ocr_config(),
                    "ai": ai_config(),
                    "dart": dart_config(),
                }
            )
        elif route.name == "styles":
            self.respond_text(STYLES_CSS, "text/css")
        elif route.name == "script":
            self.respond_text(APP_JS, "application/javascript")
        elif route.name == "projects.list":
            self.handle_list_projects()
        elif route.name == "ocr.config":
            self.handle_ocr_config()
        elif route.name == "ai.config":
            self.handle_ai_config()
        elif route.name == "dart.config":
            self.handle_dart_config()
        elif route.name == "access.config":
            self.handle_access_config()
        elif route.name == "auth.session":
            self.handle_auth_session()
        elif route.name == "reference.data":
            self.handle_reference_data()
        elif route.name == "projects.get":
            self.handle_get_project(*route.args)
        elif route.name == "uploads.list":
            self.handle_get_uploads(*route.args)
        elif route.name == "extractions.list":
            self.handle_get_extractions(*route.args)
        elif route.name == "audit.list":
            self.handle_get_audit(*route.args)
        elif route.name == "exports.get":
            self.handle_export(*route.args)
        else:
            self.respond_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in self.public_paths and not self.require_access():
            return
        route = resolve_post(path)
        if route is None:
            self.respond_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        elif not self.require_write_access(route.name):
            return
        elif route.name == "projects.create":
            self.handle_create_project()
        elif route.name == "auth.login":
            self.handle_login()
        elif route.name == "auth.demo":
            self.handle_demo_login()
        elif route.name == "auth.logout":
            self.handle_logout()
        elif route.name == "uploads.create":
            self.handle_upload_file(*route.args)
        elif route.name == "uploads.extract":
            self.handle_extract_upload(*route.args)
        elif route.name == "dart.import":
            self.handle_dart_import(*route.args)
        elif route.name == "dart.reports":
            self.handle_dart_reports(*route.args)
        elif route.name == "extractions.accept":
            self.handle_accept_extraction(*route.args)
        elif route.name == "statements.add":
            self.handle_add_statements(*route.args)
        elif route.name == "statements.validate":
            self.handle_validate(*route.args)
        elif route.name == "conversion.create":
            self.handle_convert(*route.args)
        elif route.name == "reviews.create":
            self.handle_review(*route.args)
        else:
            self.respond_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        if path not in self.public_paths and not self.require_access():
            return
        route = resolve_delete(path)
        if route is None:
            self.respond_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        elif not self.require_write_access(route.name):
            return
        elif route.name == "projects.delete":
            self.handle_delete_project(*route.args)
        elif route.name == "uploads.delete":
            self.handle_delete_upload(*route.args)
        else:
            self.respond_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def require_access(self) -> bool:
        user = self.current_user()
        if user:
            return True
        self.respond_json(
            {
                "error": "로그인이 필요합니다.",
                "login_required": True,
            },
            HTTPStatus.UNAUTHORIZED,
        )
        return False

    def require_write_access(self, route_name: str) -> bool:
        if route_name in {"auth.login", "auth.demo", "auth.logout"}:
            return True
        user = self.current_user()
        if user and user.get("is_read_only"):
            self.respond_json(
                {
                    "error": "읽기 전용 데모 계정에서는 데이터를 생성, 수정, 삭제할 수 없습니다.",
                    "read_only": True,
                },
                HTTPStatus.FORBIDDEN,
            )
            return False
        return True

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

    def cookie_token(self) -> str:
        cookie_header = self.headers.get("Cookie", "")
        if not cookie_header:
            return ""
        cookie = SimpleCookie()
        try:
            cookie.load(cookie_header)
        except Exception:
            return ""
        morsel = cookie.get(SESSION_COOKIE)
        return morsel.value if morsel else ""

    def current_user(self) -> dict | None:
        token = self.cookie_token()
        if not token:
            return None
        token_hash = session_token_hash(token)
        now = utc_now()
        with connect() as conn:
            row = conn.execute(
                """
                SELECT u.id, u.email, u.is_read_only, u.created_at
                FROM user_sessions s
                JOIN app_users u ON u.id = s.user_id
                WHERE s.token_hash = ? AND s.expires_at > ?
                """,
                (token_hash, now),
            ).fetchone()
        return row_to_dict(row) if row else None

    def session_cookie_header(self, token: str, max_age: int = SESSION_MAX_AGE_SECONDS) -> str:
        return f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={max_age}"

    def clear_session_cookie_header(self) -> str:
        return f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"

    def respond_json(
        self,
        payload: dict | list,
        status: HTTPStatus = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
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

    def respond_file(self, path: Path) -> None:
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache" if path.name == "index.html" else "public, max-age=31536000, immutable")
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

    def respond_binary_download(self, data: bytes, content_type: str, filename: str) -> None:
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def respond_html(self, body: str) -> None:
        self.respond_text(body, "text/html")

    def handle_list_projects(self) -> None:
        user = self.current_user()
        if not user:
            self.respond_json([])
            return
        with connect() as conn:
            projects = [
                row_to_dict(row)
                for row in conn.execute(
                    """
                    SELECT * FROM projects
                    WHERE owner_user_id = ?
                    ORDER BY created_at DESC
                    """,
                    (user["id"],),
                )
            ]
        self.respond_json(projects)

    def handle_ocr_config(self) -> None:
        self.respond_json(ocr_config())

    def handle_ai_config(self) -> None:
        self.respond_json(ai_config())

    def handle_dart_config(self) -> None:
        self.respond_json(dart_config())

    def handle_access_config(self) -> None:
        self.respond_json(access_config())

    def handle_auth_session(self) -> None:
        user = self.current_user()
        self.respond_json(
            {
                "authenticated": bool(user),
                "user": user_public_dict(user) if user else None,
                "admin_configured": admin_config()["configured"],
            }
        )

    def create_session(self, conn, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        now = utc_now()
        expires_at = datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() + SESSION_MAX_AGE_SECONDS,
            tz=timezone.utc,
        ).isoformat()
        conn.execute(
            """
            INSERT INTO user_sessions (id, user_id, token_hash, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), user_id, session_token_hash(token), now, expires_at),
        )
        return token

    def handle_register(self) -> None:
        self.respond_json({"error": "회원가입은 비활성화되어 있습니다. 관리자 계정으로 로그인하세요."}, HTTPStatus.FORBIDDEN)

    def handle_login(self) -> None:
        payload = self.read_json()
        email = normalize_email(payload.get("email", ""))
        password = str(payload.get("password") or "")
        if not email or not password:
            self.respond_json({"error": "이메일과 비밀번호를 입력하세요."}, HTTPStatus.BAD_REQUEST)
            return
        with connect() as conn:
            ensure_admin_user(conn)
            row = conn.execute("SELECT * FROM app_users WHERE email = ?", (email,)).fetchone()
            user = row_to_dict(row) if row else None
            if not user and not admin_config()["configured"]:
                self.respond_json(
                    {"error": "관리자 계정이 설정되지 않았습니다. ADMIN_EMAIL과 ADMIN_PASSWORD를 서버 환경변수에 설정하세요."},
                    HTTPStatus.SERVICE_UNAVAILABLE,
                )
                return
            if not user or not verify_password(password, user["password_hash"]):
                self.respond_json({"error": "이메일 또는 비밀번호가 올바르지 않습니다."}, HTTPStatus.UNAUTHORIZED)
                return
            token = self.create_session(conn, user["id"])
        self.respond_json(
            {"authenticated": True, "user": user_public_dict(user)},
            headers={"Set-Cookie": self.session_cookie_header(token)},
        )

    def handle_demo_login(self) -> None:
        with connect() as conn:
            ensure_admin_user(conn)
            user = ensure_demo_user(conn)
            if not user:
                self.respond_json({"error": "데모 로그인이 비활성화되어 있습니다."}, HTTPStatus.FORBIDDEN)
                return
            token = self.create_session(conn, user["id"])
        self.respond_json(
            {"authenticated": True, "user": user_public_dict(user), "demo": True},
            headers={"Set-Cookie": self.session_cookie_header(token)},
        )

    def handle_logout(self) -> None:
        token = self.cookie_token()
        if token:
            with connect() as conn:
                conn.execute("DELETE FROM user_sessions WHERE token_hash = ?", (session_token_hash(token),))
        self.respond_json(
            {"authenticated": False, "user": None},
            headers={"Set-Cookie": self.clear_session_cookie_header()},
        )

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
        user = self.current_user()
        if not user:
            self.respond_json({"error": "로그인이 필요합니다."}, HTTPStatus.UNAUTHORIZED)
            return
        now = utc_now()
        project = {
            "id": str(uuid.uuid4()),
            "owner_user_id": user["id"],
            "is_test": False,
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
                INSERT INTO projects (
                    id, owner_user_id, is_test, company_name, source_standard,
                    target_standard, period, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project["id"],
                    project["owner_user_id"],
                    project["is_test"],
                    project["company_name"],
                    project["source_standard"],
                    project["target_standard"],
                    project["period"],
                    project["status"],
                    project["created_at"],
                    project["updated_at"],
                ),
            )
            log_event(conn, project["id"], "project.created", project)
        self.respond_json(project, HTTPStatus.CREATED)

    def handle_get_project(self, project_id: str) -> None:
        user = self.current_user()
        if not user:
            self.respond_json({"error": "로그인이 필요합니다."}, HTTPStatus.UNAUTHORIZED)
            return
        with connect() as conn:
            project = conn.execute(
                "SELECT * FROM projects WHERE id = ? AND owner_user_id = ?",
                (project_id, user["id"]),
            ).fetchone()
            if not project:
                self.respond_json({"error": "Project not found"}, HTTPStatus.NOT_FOUND)
                return
            statements = [
                dict(row_to_dict(row), checklist=parse_json_field(row["checklist_json"], []))
                for row in conn.execute("SELECT * FROM statements WHERE project_id = ? ORDER BY created_at", (project_id,))
            ]
            uploads = [
                upload_public_dict(row)
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

    def handle_delete_project(self, project_id: str) -> None:
        user = self.current_user()
        if not user:
            self.respond_json({"error": "로그인이 필요합니다."}, HTTPStatus.UNAUTHORIZED)
            return
        with connect() as conn:
            project = conn.execute(
                "SELECT * FROM projects WHERE id = ? AND owner_user_id = ?",
                (project_id, user["id"]),
            ).fetchone()
            if not project:
                self.respond_json({"error": "Project not found"}, HTTPStatus.NOT_FOUND)
                return
            uploads = [
                row_to_dict(row)
                for row in conn.execute("SELECT stored_name FROM uploads WHERE project_id = ?", (project_id,))
            ]
            conn.execute("DELETE FROM extractions WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM uploads WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM statements WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM conversions WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM reviews WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM audit_logs WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM projects WHERE id = ? AND owner_user_id = ?", (project_id, user["id"]))
        for upload in uploads:
            stored_name = str(upload.get("stored_name") or "")
            if not stored_name:
                continue
            try:
                (UPLOAD_DIR / stored_name).unlink(missing_ok=True)
            except OSError:
                pass
        self.respond_json({"deleted": True, "project_id": project_id})

    def handle_get_uploads(self, project_id: str) -> None:
        with connect() as conn:
            rows = conn.execute(
                "SELECT * FROM uploads WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        self.respond_json([upload_public_dict(row) for row in rows])

    def handle_delete_upload(self, project_id: str, upload_id: str) -> None:
        with connect() as conn:
            upload = conn.execute(
                "SELECT * FROM uploads WHERE id = ? AND project_id = ?",
                (upload_id, project_id),
            ).fetchone()
            if not upload:
                self.respond_json({"error": "Upload not found"}, HTTPStatus.NOT_FOUND)
                return
            upload_dict = row_to_dict(upload)
            conn.execute("DELETE FROM extractions WHERE upload_id = ? AND project_id = ?", (upload_id, project_id))
            conn.execute("DELETE FROM uploads WHERE id = ? AND project_id = ?", (upload_id, project_id))
            remaining = conn.execute("SELECT COUNT(*) AS count FROM uploads WHERE project_id = ?", (project_id,)).fetchone()["count"]
            next_status = "created" if int(remaining or 0) == 0 else "source_uploaded"
            conn.execute("UPDATE projects SET status = ?, updated_at = ? WHERE id = ?", (next_status, utc_now(), project_id))
            log_event(
                conn,
                project_id,
                "source.deleted",
                {
                    "upload_id": upload_id,
                    "original_name": upload_dict.get("original_name"),
                    "remaining_uploads": remaining,
                },
            )
        stored_name = str(upload_dict.get("stored_name") or "")
        if stored_name:
            try:
                (UPLOAD_DIR / stored_name).unlink(missing_ok=True)
            except OSError:
                pass
        self.respond_json({"deleted": True, "upload_id": upload_id, "project_status": next_status})

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
            "file_bytes": content,
            "extraction_status": "pending_ocr",
            "created_at": utc_now(),
        }
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO uploads (
                    id, project_id, original_name, stored_name, content_type, size_bytes, file_bytes, extraction_status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    upload["id"],
                    upload["project_id"],
                    upload["original_name"],
                    upload["stored_name"],
                    upload["content_type"],
                    upload["size_bytes"],
                    upload["file_bytes"],
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
        self.respond_json(upload_public_dict(upload), HTTPStatus.CREATED)

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

    def handle_dart_import(self, project_id: str) -> None:
        payload = self.read_json()
        with connect() as conn:
            project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not project:
                self.respond_json({"error": "Project not found"}, HTTPStatus.NOT_FOUND)
                return

        rows, issues, metadata = fetch_dart_statement_rows(payload)
        raw_rows = metadata.pop("raw_rows", [])
        raw_payload = {
            "metadata": metadata,
            "raw_rows": raw_rows,
            "filtered_rows": rows,
            "issues": issues,
        }
        raw_bytes = json.dumps(raw_payload, ensure_ascii=False).encode("utf-8")
        status = "needs_review" if rows else "failed"
        now = utc_now()
        upload = {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "original_name": f"DART_API_{metadata.get('corp_code', 'unknown')}_{metadata.get('bsns_year', payload.get('bsns_year', 'unknown'))}.json",
            "stored_name": "",
            "content_type": "application/json",
            "size_bytes": len(raw_bytes),
            "file_bytes": raw_bytes,
            "extraction_status": status,
            "created_at": now,
        }
        extraction = {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "upload_id": upload["id"],
            "provider": "dart_api",
            "status": status,
            "rows": rows,
            "issues": issues,
            "metadata": metadata,
            "created_at": now,
        }
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO uploads (
                    id, project_id, original_name, stored_name, content_type, size_bytes, file_bytes, extraction_status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    upload["id"],
                    upload["project_id"],
                    upload["original_name"],
                    upload["stored_name"],
                    upload["content_type"],
                    upload["size_bytes"],
                    upload["file_bytes"],
                    upload["extraction_status"],
                    upload["created_at"],
                ),
            )
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
                    json.dumps([*extraction["issues"], json.dumps(metadata, ensure_ascii=False)], ensure_ascii=False),
                    extraction["created_at"],
                ),
            )
            next_status = "extracted" if rows else "source_import_failed"
            conn.execute("UPDATE projects SET status = ?, updated_at = ? WHERE id = ?", (next_status, utc_now(), project_id))
            log_event(
                conn,
                project_id,
                "dart.imported",
                {
                    "upload_id": upload["id"],
                    "extraction_id": extraction["id"],
                    "row_count": len(rows),
                    "raw_row_count": len(raw_rows),
                    "issues": issues,
                    "metadata": metadata,
                },
            )
        self.respond_json({**extraction, "upload": upload_public_dict(upload)}, HTTPStatus.CREATED if rows else HTTPStatus.BAD_REQUEST)

    def handle_dart_reports(self, project_id: str) -> None:
        payload = self.read_json()
        with connect() as conn:
            project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not project:
                self.respond_json({"error": "Project not found"}, HTTPStatus.NOT_FOUND)
                return

        reports, issues, metadata = fetch_dart_available_reports(payload)
        self.respond_json({"reports": reports, "issues": issues, "metadata": metadata})

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
            output["ai_assistance"] = call_ai_judgment(project, output["entries"], output["judgment_items"])
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
                    "ai_status": output["ai_assistance"].get("status"),
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
            project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            conversion = conn.execute(
                "SELECT output_json FROM conversions WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
            statements = [
                dict(row_to_dict(row), checklist=parse_json_field(row["checklist_json"], []))
                for row in conn.execute("SELECT * FROM statements WHERE project_id = ? ORDER BY created_at", (project_id,))
            ]
            latest_extraction = conn.execute(
                """
                SELECT e.rows_json, u.file_bytes
                FROM extractions e
                LEFT JOIN uploads u ON u.id = e.upload_id
                WHERE e.project_id = ?
                ORDER BY e.created_at DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            audit_rows = [
                dict(row_to_dict(row), detail=parse_json_field(row["detail_json"], {}))
                for row in conn.execute("SELECT * FROM audit_logs WHERE project_id = ? ORDER BY created_at", (project_id,))
            ]
        if not project:
            self.respond_json({"error": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
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
        if export_name == "review-workbook.xlsx":
            extraction_rows = dart_raw_rows_from_upload(row_to_dict(latest_extraction) if latest_extraction else None)
            if not extraction_rows and latest_extraction:
                extraction_rows = parse_json_field(latest_extraction["rows_json"], [])
            workbook = review_workbook_bytes(row_to_dict(project), extraction_rows, statements, output, audit_rows)
            self.respond_binary_download(
                workbook,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "gtf_review_workbook.xlsx",
            )
            return
        self.respond_json({"error": "Unknown export type"}, HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def main() -> None:
    init_db()
    port = int(os.environ.get("PORT", "4173"))
    host = os.environ.get("HOST", "127.0.0.1")
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"GTF server running on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
