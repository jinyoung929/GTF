"""
조정분개 대차 일치 불변식 테스트
=================================

조정분개는 계정별 조정액 명세이고, 상대계정은 K-IFRS 제1101호 문단 10에 따라
이익잉여금이다. 그래서 `entries + equity_counterpart`의 차변 합계와 대변 합계는
어떤 입력에서도 일치해야 한다. 이 파일은 그 성질을 고정한다.

가장 중요한 건 마지막 테스트다: 구역 부호(NET_EQUITY_SIGNS)에 없는 내부 코드가
생기면 그 행은 조용히 0으로 빠지고 대차는 여전히 맞는 것처럼 보인다. 시드의 모든
코드 접두사가 매핑돼 있는지 확인해서 그 구멍을 막는다.

실행:
    python3 -m unittest tests.test_journal_balance -v
"""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
for _candidate in (_HERE, os.path.dirname(_HERE)):
    if os.path.exists(os.path.join(_candidate, "server.py")):
        _ROOT = _candidate
        sys.path.insert(0, _candidate)
        break

from gtf_app.domain import (  # noqa: E402
    NET_EQUITY_SIGNS,
    UNSECTIONED_CODE_PREFIXES,
    _net_equity_effect,
    entry_debit_credit,
    equity_counterpart_entry,
    generate_conversion,
    journal_rows,
)

sys.path.insert(0, _HERE)
from reference_fixture import load_reference  # noqa: E402

REF = load_reference()

PROJECT = {
    "id": "proj-journal",
    "company_name": "대차테스트",
    "period": "2024",
    "source_standard": "K-GAAP",
    "target_standard": "IFRS",
}


def row(account_name, amount, mapping_type, standard_code, statement_id):
    return {
        "id": statement_id,
        "account_name": account_name,
        "standard_code": standard_code,
        "amount": amount,
        "mapping_type": mapping_type,
        "rule_summary": "테스트 규칙",
    }


def totals(rows):
    debit = round(sum(float(r.get("debit") or 0) for r in rows), 2)
    credit = round(sum(float(r.get("credit") or 0) for r in rows), 2)
    return debit, credit


# 실제 계산기를 태우는 시나리오들. 자산만/부채까지/손익까지 서로 다른 구역을 건드린다.
SCENARIOS = {
    "리스(자산+부채 쌍 생성)": (
        [row("사무실 리스", 0, "judgment", "A2100", "r-lease")],
        {"r-lease": {"lease_term_months": 24, "monthly_payment": 1_000_000, "discount_rate": 0}},
    ),
    "재고자산(후입선출 재계산)": (
        [row("재고자산", 5_000_000, "judgment", "A1200", "r-inv")],
        {"r-inv": {"cost_method": "후입선출법", "new_cost_method": "선입선출법", "fifo_restated_amount": 5_800_000}},
    ),
    "차입원가(손익 구역)": (
        [row("차입원가", 0, "judgment", "R4000", "r-bc")],
        {"r-bc": {"qualifying_asset": True, "expenditure": 100_000_000, "capitalization_rate": 5, "capitalization_months": 12}},
    ),
    "영업권(누적 상각 환입)": (
        [row("영업권", 3_000_000, "judgment", "A3200", "r-gw")],
        {"r-gw": {"accumulated_amortization": 1_200_000, "impairment_indicator": False}},
    ),
    "단순 매핑만(조정 없음)": (
        [row("현금및현금성자산", 9_000_000, "simple", "A1000", "r-cash")],
        {},
    ),
    "여러 계정 혼합": (
        [
            row("사무실 리스", 0, "judgment", "A2100", "r-1"),
            row("재고자산", 5_000_000, "judgment", "A1200", "r-2"),
            row("차입원가", 0, "judgment", "R4000", "r-3"),
            row("현금및현금성자산", 9_000_000, "simple", "A1000", "r-4"),
        ],
        {
            "r-1": {"lease_term_months": 24, "monthly_payment": 1_000_000, "discount_rate": 0},
            "r-2": {"cost_method": "후입선출법", "new_cost_method": "선입선출법", "fifo_restated_amount": 5_800_000},
            "r-3": {"qualifying_asset": True, "expenditure": 100_000_000, "capitalization_rate": 5, "capitalization_months": 12},
        },
    ),
}


class JournalBalanceTests(unittest.TestCase):
    def test_debit_equals_credit_in_every_scenario(self):
        # 핵심 불변식: 이익잉여금 상계 행까지 포함하면 차·대가 항상 맞는다.
        for name, (statements, responses) in SCENARIOS.items():
            with self.subTest(scenario=name):
                conversion = generate_conversion(PROJECT, statements, responses, REF)
                debit, credit = totals(journal_rows(conversion))
                self.assertEqual(debit, credit, f"{name}: 차변 {debit:,.2f} ≠ 대변 {credit:,.2f}")

    def test_counterpart_equals_net_equity_effect(self):
        # 상계 행 금액은 전환조정 요약이 쓰는 순자산 영향과 같은 수여야 한다.
        # 두 경로가 독립적으로 계산되므로 한쪽만 바뀌면 여기서 잡힌다.
        statements, responses = SCENARIOS["여러 계정 혼합"]
        conversion = generate_conversion(PROJECT, statements, responses, REF)
        counterpart = conversion["equity_counterpart"]
        self.assertIsNotNone(counterpart)
        self.assertEqual(counterpart["adjustment"], round(_net_equity_effect(conversion["entries"]), 2))
        self.assertEqual(counterpart["standard_code"], "E1200")  # 이익잉여금 (시드에 이미 존재)
        self.assertEqual(counterpart["target_account"], "이익잉여금")

    def test_counterpart_is_not_inside_entries(self):
        # 상계 행을 entries에 넣으면 자본 구역으로 다시 집계돼 순자산 영향이 이중 계상된다.
        statements, responses = SCENARIOS["여러 계정 혼합"]
        conversion = generate_conversion(PROJECT, statements, responses, REF)
        self.assertNotIn("E1200", [e.get("standard_code") for e in conversion["entries"]])
        self.assertEqual(len(journal_rows(conversion)), len(conversion["entries"]) + 1)

    def test_lease_pair_lands_on_both_sides(self):
        # 사용권자산은 차변, 리스부채는 대변 — '반쪽 분개'가 아니라는 것을 고정한다.
        statements, responses = SCENARIOS["리스(자산+부채 쌍 생성)"]
        conversion = generate_conversion(PROJECT, statements, responses, REF)
        by_code = {e["standard_code"]: e for e in conversion["entries"]}
        self.assertGreater(by_code["A2100"]["debit"], 0)
        self.assertEqual(by_code["A2100"]["credit"], 0)
        self.assertGreater(by_code["L2150"]["credit"], 0)
        self.assertEqual(by_code["L2150"]["debit"], 0)
        self.assertEqual(by_code["A2100"]["debit"], by_code["L2150"]["credit"])  # 수정소급법: 동액

    def test_reclassification_has_no_journal_effect(self):
        # 조정액 0(재분류)은 차·대 모두 0이고, 상계 행 자체가 생기지 않는다.
        statements, responses = SCENARIOS["단순 매핑만(조정 없음)"]
        conversion = generate_conversion(PROJECT, statements, responses, REF)
        for entry in conversion["entries"]:
            self.assertEqual((entry["debit"], entry["credit"]), (0.0, 0.0))
        self.assertIsNone(conversion["equity_counterpart"])

    def test_direction_follows_net_asset_effect(self):
        self.assertEqual(entry_debit_credit({"standard_code": "A1000", "adjustment": 100}), (100.0, 0.0))
        self.assertEqual(entry_debit_credit({"standard_code": "A1000", "adjustment": -100}), (0.0, 100.0))
        self.assertEqual(entry_debit_credit({"standard_code": "L1000", "adjustment": 100}), (0.0, 100.0))
        self.assertEqual(entry_debit_credit({"standard_code": "L1000", "adjustment": -100}), (100.0, 0.0))
        self.assertEqual(entry_debit_credit({"standard_code": "A1000", "adjustment": 0}), (0.0, 0.0))

    def test_unknown_code_prefix_fails_loudly(self):
        # 구역 부호가 없으면 조용히 0으로 빠져 대차가 맞는 것처럼 보인다 — 즉시 실패해야 한다.
        with self.assertRaises(ValueError):
            entry_debit_credit({"standard_code": "Z9999", "adjustment": 100})

    def test_every_seeded_code_prefix_has_a_sign(self):
        # 위 테스트의 짝: 실제로는 그 예외가 절대 안 나야 한다.
        # 시드의 모든 계정 코드 + 계산기가 만드는 합성 코드(L2150 리스부채)를 검사한다.
        # 구역 미정(X9999 미분류)만 예외이며, 그 예외는 코드에 명시돼 있어야 한다.
        prefixes = {str(account["code"])[:1] for account in REF.accounts.values() if account.get("code")}
        prefixes.add("L")  # L2150: 리스부채 표시용 합성 코드 (별도 계정 시드 없음)
        missing = prefixes - set(NET_EQUITY_SIGNS) - UNSECTIONED_CODE_PREFIXES
        self.assertEqual(missing, set(), f"구역 부호가 없는 코드 접두사: {sorted(missing)}")

    def test_unclassified_account_does_not_break_the_journal(self):
        # 미분류(X9999)는 구역이 없지만 조정액도 없다 — 변환이 깨지지 않아야 한다.
        statements = [row("권리금", 4_000_000, "unmapped", "X9999", "r-unmapped")]
        conversion = generate_conversion(PROJECT, statements, {}, REF)
        unmapped = next(e for e in conversion["entries"] if e["standard_code"] == "X9999")
        self.assertEqual((unmapped["debit"], unmapped["credit"]), (0.0, 0.0))
        debit, credit = totals(journal_rows(conversion))
        self.assertEqual(debit, credit)

    def test_counterpart_none_when_nothing_to_balance(self):
        self.assertIsNone(equity_counterpart_entry([]))
        self.assertIsNone(equity_counterpart_entry([{"standard_code": "A1000", "adjustment": 0}]))


if __name__ == "__main__":
    unittest.main()
