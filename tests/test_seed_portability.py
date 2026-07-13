"""
시드 SQL의 크로스-DB 이식성 가드
==================================

SQLite는 BOOLEAN 컬럼에 정수 1/0을 관대하게 받지만 Postgres는 거부한다(에러 42804).
그래서 "로컬은 되는데 배포만 깨지는" 사고가 난다. 이 테스트는 ORM 모델(models.py)에서
Boolean 컬럼을 읽어와, seeds/*.sql이 그 컬럼 자리에 정수가 아니라 true/false(또는 NULL)만
쓰는지 검사한다. 시드 생성기가 표기를 흐트러뜨리면 여기서 바로 실패한다.

실행:
    python3 -m unittest tests.test_seed_portability -v
"""

import os
import re
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)

from sqlalchemy import Boolean  # noqa: E402

from gtf_app.models import Base  # noqa: E402

SEED_DIR = os.path.join(_ROOT, "seeds")

# 어떤 SQL 파일이 어떤 테이블을 시드하는지 (핵심 기준정보 전부 — 파생 테이블 없음)
SEED_TABLES = {
    "standard_accounts.sql": "standard_accounts",
    "checklist_items.sql": "checklist_items",
    "kgaap_accounts.sql": "kgaap_accounts",
    "financial_statement_templates.sql": "financial_statement_templates",
    "standards_paragraphs.sql": "standards_paragraphs",
}


def boolean_columns(table_name: str) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {c.name for c in table.columns if isinstance(c.type, Boolean)}


def split_top_level(inner: str) -> list[str]:
    """SQL 튜플 내부를 최상위 콤마 기준으로 나눈다 (따옴표·괄호 안의 콤마는 무시)."""
    fields, cur, depth, in_quote = [], [], 0, False
    i = 0
    while i < len(inner):
        ch = inner[i]
        if in_quote:
            cur.append(ch)
            if ch == "'":
                if i + 1 < len(inner) and inner[i + 1] == "'":  # '' 이스케이프
                    cur.append(inner[i + 1])
                    i += 2
                    continue
                in_quote = False
        elif ch == "'":
            in_quote = True
            cur.append(ch)
        elif ch == "(":
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            fields.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    if "".join(cur).strip():
        fields.append("".join(cur).strip())
    return fields


def parse_insert(sql: str) -> tuple[list[str], list[list[str]]]:
    """INSERT ... (컬럼들) VALUES (행)... 에서 컬럼 목록과 각 값 튜플을 파싱한다."""
    header = re.search(r"INSERT\s+INTO\s+\w+\s*\((.*?)\)\s*VALUES", sql, re.S | re.I)
    columns = [c.strip() for c in split_top_level(header.group(1))]

    body = sql[header.end():]
    body = re.split(r"\bON\s+CONFLICT\b", body, flags=re.I)[0]
    rows, depth, start = [], 0, None
    for i, ch in enumerate(body):
        if ch == "(" and depth == 0:
            depth, start = 1, i + 1
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                rows.append(split_top_level(body[start:i]))
    return columns, rows


class SeedBooleanPortabilityTest(unittest.TestCase):
    def test_boolean_columns_use_true_false_not_integers(self):
        checked_any = False
        for filename, table in SEED_TABLES.items():
            path = os.path.join(SEED_DIR, filename)
            with open(path, encoding="utf-8") as fh:
                columns, rows = parse_insert(fh.read())
            bool_cols = boolean_columns(table) & set(columns)
            for col in bool_cols:
                idx = columns.index(col)
                for row_no, row in enumerate(rows, start=1):
                    value = row[idx].lower()
                    checked_any = True
                    self.assertIn(
                        value,
                        {"true", "false", "null"},
                        f"{filename} {row_no}행 '{col}' 컬럼이 이식 불가한 값 '{row[idx]}' 사용 "
                        f"(Postgres BOOLEAN은 정수 1/0을 거부한다 → true/false로).",
                    )
        self.assertTrue(checked_any, "검사한 불리언 컬럼이 하나도 없음 — 매핑을 확인하라")

    def test_on_conflict_boolean_literals_are_portable(self):
        for filename, table in SEED_TABLES.items():
            path = os.path.join(SEED_DIR, filename)
            with open(path, encoding="utf-8") as fh:
                sql = fh.read()
            for col in boolean_columns(table):
                bad = re.search(rf"\b{col}\s*=\s*[01]\b", sql)
                self.assertIsNone(
                    bad,
                    f"{filename} ON CONFLICT 절의 '{col} = {bad.group(0) if bad else ''}'가 정수 사용 → true/false로.",
                )


if __name__ == "__main__":
    unittest.main()
