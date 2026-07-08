"""
계정명 별칭 DB 단일 출처 + 부분문자열 충돌 해결 테스트
=====================================================

핵심 검증:
  - 긴 별칭 우선 매칭으로 부분문자열 충돌 해결 (금융상품 ⊃ 상품, 퇴직급여충당부채 ⊃ 충당부채)
  - 코드 폴백(ACCOUNT_ALIASES)과 DB 로드 맵이 동일한 정규화 결과를 낸다
  - ensure_account_aliases 시드가 멱등하며 우선순위(길이)를 저장한다
  - 계정 행 표시 순서가 계정코드 기반으로 정렬된다

실행:
    python3 -m unittest tests.test_account_aliases -v
"""

import os
import sqlite3
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
for _candidate in (_HERE, os.path.dirname(_HERE)):
    if os.path.exists(os.path.join(_candidate, "server.py")):
        sys.path.insert(0, _candidate)
        break

import server  # noqa: E402
from gtf_app.domain import ACCOUNT_ALIASES, normalize_account_name  # noqa: E402


# 부분문자열이 서로 포함되지만 계정이 다른, 순서에 취약한 쌍들
COLLISION_CASES = [
    ("금융상품", "financial_instrument"),
    ("상품", "inventory"),
    ("파생상품", "financial_instrument"),
    ("퇴직급여충당부채", "retirement_benefit"),
    ("충당부채", "provision"),
    ("미수수익", "receivables"),
    ("수익", "revenue"),
    ("매출채권", "receivables"),
    ("매출", "revenue"),
]


class CodeFallbackNormalizationTest(unittest.TestCase):
    def test_substring_collisions_resolve_with_code_dict(self):
        for name, expected in COLLISION_CASES:
            self.assertEqual(normalize_account_name(name), expected, f"{name} 오분류")

    def test_unknown_returns_other(self):
        self.assertEqual(normalize_account_name("가수금"), "other")

    def test_longer_alias_wins_regardless_of_dict_order(self):
        # 짧은 별칭을 먼저 나열해도 긴 별칭이 우선되어야 한다
        shuffled = {"상품": "inventory", "금융상품": "financial_instrument"}
        self.assertEqual(normalize_account_name("금융상품", shuffled), "financial_instrument")
        self.assertEqual(normalize_account_name("상품", shuffled), "inventory")


class AliasDbSingleSourceTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(server.SQLITE_SCHEMA_PATH.read_text(encoding="utf-8"))
        server.ensure_reference_accounts(self.conn)  # FK 대상 먼저
        server.ensure_account_aliases(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_all_aliases_seeded(self):
        count = self.conn.execute("SELECT COUNT(*) AS c FROM kgaap_accounts").fetchone()["c"]
        self.assertEqual(count, len(ACCOUNT_ALIASES))

    def test_match_priority_is_alias_length(self):
        rows = self.conn.execute("SELECT kgaap_name, match_priority FROM kgaap_accounts").fetchall()
        for row in rows:
            self.assertEqual(row["match_priority"], len(row["kgaap_name"]))

    def test_db_map_matches_code_fallback(self):
        alias_map = server.load_account_alias_map(self.conn)
        samples = [
            "현금", "재고자산", "리스부채", "개발비", "이연법인세부채", "정부보조금",
            "차입원가", "유형자산", "투자부동산", "자본금", "가수금", *[c[0] for c in COLLISION_CASES],
        ]
        for name in samples:
            self.assertEqual(
                normalize_account_name(name, alias_map),
                normalize_account_name(name),
                f"{name}: DB 맵과 코드 폴백 결과 불일치",
            )

    def test_db_map_resolves_collisions(self):
        alias_map = server.load_account_alias_map(self.conn)
        for name, expected in COLLISION_CASES:
            self.assertEqual(normalize_account_name(name, alias_map), expected)

    def test_seed_is_idempotent(self):
        server.ensure_account_aliases(self.conn)
        server.ensure_account_aliases(self.conn)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) AS c FROM kgaap_accounts").fetchone()["c"],
            len(ACCOUNT_ALIASES),
        )

    def test_build_statement_record_uses_injected_map(self):
        alias_map = server.load_account_alias_map(self.conn)
        record = server.build_statement_record("2024", {"account_name": "금융상품", "amount": 100}, alias_map)
        self.assertEqual(record["standard_code"], "F1000")


class StatementCodeOrderingTest(unittest.TestCase):
    def test_sorted_by_presentation_order_not_insertion(self):
        rows = [
            {"standard_code": "R1000", "created_at": "1"},  # 손익
            {"standard_code": "L2200", "created_at": "2"},  # 부채
            {"standard_code": "A1000", "created_at": "3"},  # 자산
            {"standard_code": "E1000", "created_at": "4"},  # 자본
        ]
        ordered = [r["standard_code"] for r in server.sort_statements_by_code(rows)]
        self.assertEqual(ordered, ["A1000", "L2200", "E1000", "R1000"])  # 자산→부채→자본→손익


if __name__ == "__main__":
    unittest.main()
