"""
계정명 별칭 DB 단일 출처 + 기준정보 계약 검증 테스트
=====================================================

핵심 검증:
  - 별칭 사전은 seeds/kgaap_accounts.sql → DB가 단일 출처 (코드에 별칭 데이터 없음)
  - 긴 별칭 우선 매칭으로 부분문자열 충돌 해결 (금융상품 ⊃ 상품, 퇴직급여충당부채 ⊃ 충당부채)
  - ensure_account_aliases 시드가 멱등하며 우선순위(길이)를 저장한다
  - verify_reference_contract: 계산기가 요구하는 계정키·체크리스트 키가 시드에 빠지면
    서버 시작이 실패한다 (조정액 0 무증상 버그 방지)
  - 계정 행 표시 순서가 계정코드 기반으로 정렬된다

실행:
    python3 -m unittest tests.test_account_aliases -v
"""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
for _candidate in (_HERE, os.path.dirname(_HERE)):
    if os.path.exists(os.path.join(_candidate, "server.py")):
        sys.path.insert(0, _candidate)
        break

from sqlalchemy import delete, func, select  # noqa: E402

import server  # noqa: E402
from gtf_app.models import ChecklistItem, KgaapAccount, StandardAccount  # noqa: E402
from gtf_app.domain import (  # noqa: E402
    CALC_ACCOUNT_KEYS,
    CALC_CHECKLIST_KEYS,
    ReferenceData,
    normalize_account_name,
    verify_reference_contract,
)

sys.path.insert(0, _HERE)
from reference_fixture import load_reference, seeded_session  # noqa: E402

REF = load_reference()


# 부분문자열이 서로 포함되지만 계정이 다른, 순서에 취약한 쌍들
COLLISION_CASES = [
    ("금융상품", "financial_instrument"),
    ("상품", "inventory"),
    ("파생상품", "derivative"),  # 전문가 검토 영역 신설로 재지정
    ("퇴직급여충당부채", "retirement_benefit"),
    ("충당부채", "provision"),
    ("미수수익", "receivables"),
    ("수익", "revenue"),
    ("매출채권", "receivables"),
    ("매출", "revenue"),
]


class DbNormalizationTest(unittest.TestCase):
    def test_substring_collisions_resolve_with_db_aliases(self):
        for name, expected in COLLISION_CASES:
            self.assertEqual(normalize_account_name(name, REF.aliases), expected, f"{name} 오분류")

    def test_unknown_returns_other(self):
        self.assertEqual(normalize_account_name("가수금", REF.aliases), "other")

    def test_longer_alias_wins_regardless_of_dict_order(self):
        # 짧은 별칭을 먼저 나열해도 긴 별칭이 우선되어야 한다
        shuffled = {"상품": "inventory", "금융상품": "financial_instrument"}
        self.assertEqual(normalize_account_name("금융상품", shuffled), "financial_instrument")
        self.assertEqual(normalize_account_name("상품", shuffled), "inventory")


class AliasDbSingleSourceTest(unittest.TestCase):
    def setUp(self):
        self.session = seeded_session()

    def tearDown(self):
        self.session.close()

    def alias_count(self):
        return self.session.scalar(select(func.count()).select_from(KgaapAccount))

    def test_aliases_seeded_and_loaded(self):
        self.assertGreater(self.alias_count(), 0)
        self.assertEqual(self.alias_count(), len(REF.aliases))

    def test_match_priority_is_alias_length(self):
        rows = self.session.execute(select(KgaapAccount.kgaap_name, KgaapAccount.match_priority)).all()
        for name, priority in rows:
            self.assertEqual(priority, len(name))

    def test_alias_targets_exist_in_standard_accounts(self):
        # 별칭이 가리키는 계정키가 표준계정 테이블에 실재해야 한다 (시드 간 정합성)
        known_keys = set(self.session.scalars(select(StandardAccount.account_key)))
        orphans = [
            name
            for name, key in self.session.execute(select(KgaapAccount.kgaap_name, KgaapAccount.account_key)).all()
            if key not in known_keys
        ]
        self.assertEqual(orphans, [])

    def test_seed_is_idempotent(self):
        before = self.alias_count()
        server.ensure_account_aliases(self.session)
        server.ensure_account_aliases(self.session)
        self.assertEqual(self.alias_count(), before)

    def test_build_statement_record_uses_injected_reference(self):
        record = server.build_statement_record("2024", {"account_name": "금융상품", "amount": 100}, REF)
        self.assertEqual(record["standard_code"], "F1000")


class ReferenceContractTest(unittest.TestCase):
    """SQL 시드와 계산기 코드가 어긋나면 서버 시작이 실패해야 한다."""

    def test_seeded_db_passes_contract(self):
        self.assertEqual(verify_reference_contract(REF), [])

    def test_empty_reference_reports_all_calc_keys(self):
        errors = verify_reference_contract(ReferenceData())
        for key in CALC_ACCOUNT_KEYS:
            self.assertTrue(any(key in e for e in errors), f"{key} 누락이 보고되지 않음")

    def test_missing_checklist_key_fails_startup(self):
        session = seeded_session()
        try:
            session.execute(
                delete(ChecklistItem).where(
                    ChecklistItem.account_key == "lease", ChecklistItem.item_key == "discount_rate"
                )
            )
            with self.assertRaises(RuntimeError) as ctx:
                server.refresh_reference_cache(session)
            self.assertIn("discount_rate", str(ctx.exception))
        finally:
            session.close()
            load_reference()  # 전역 REFERENCE 캐시를 정상 상태로 복원

    def test_missing_account_key_fails_startup(self):
        session = seeded_session()
        try:
            for model in (KgaapAccount, ChecklistItem, StandardAccount):
                session.execute(delete(model).where(model.account_key == "provision"))
            with self.assertRaises(RuntimeError) as ctx:
                server.refresh_reference_cache(session)
            self.assertIn("provision", str(ctx.exception))
        finally:
            session.close()
            load_reference()

    def test_calc_checklist_keys_cover_all_judgment_calculators(self):
        # 계약 정의 자체의 자기 검증: 계산기 키는 모두 표준계정 키 안에 있어야 한다
        self.assertTrue(set(CALC_CHECKLIST_KEYS).issubset(CALC_ACCOUNT_KEYS))


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
