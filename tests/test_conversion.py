"""
GTF 회계 변환 로직 단위 테스트
=================================

`generate_conversion`의 기준서별 계산/분류 로직을 검증한다.
외부 의존성 없이 표준 라이브러리 unittest만 사용한다 (프로젝트 철학 유지).

검증 범위:
  - 리스 (IFRS 16) : 리스료 현재가치 조정액 산출
  - 개발비 (IAS 38): 자산화 4요건에 따른 무형자산/비용 분류
  - 충당부채 (IAS 37): 인식 3요건 판정
  - 수익 (IFRS 15) : 인식 시점 문서화
  - 매핑 일반    : simple/judgment 분기, judgment_items·draft_notes 집계
  - normalize_account_name: 매칭 동작 및 알려진 한계 문서화

실행:
    python3 -m unittest discover -s tests -v
    # 또는
    python3 -m unittest tests.test_conversion -v
"""

import os
import sys
import unittest

# 이 파일이 repo 루트에 있든 tests/ 아래에 있든 server.py를 찾도록 처리
_HERE = os.path.dirname(os.path.abspath(__file__))
for _candidate in (_HERE, os.path.dirname(_HERE)):
    if os.path.exists(os.path.join(_candidate, "server.py")):
        sys.path.insert(0, _candidate)
        break

import server  # noqa: E402


# ---------------------------------------------------------------------------
# 테스트 헬퍼
# ---------------------------------------------------------------------------

PROJECT = {
    "id": "proj-test",
    "company_name": "테스트회사",
    "period": "2024",
    "source_standard": "K-GAAP",
    "target_standard": "IFRS",
}


def make_statement(account_name, amount, mapping_type, standard_code="A0000",
                   rule_summary="테스트 규칙", statement_id="row-1"):
    """generate_conversion이 기대하는 형태의 계정 행 dict를 만든다."""
    return {
        "id": statement_id,
        "account_name": account_name,
        "standard_code": standard_code,
        "amount": amount,
        "mapping_type": mapping_type,
        "rule_summary": rule_summary,
    }


def convert_single(account_name, amount, mapping_type, response=None,
                   standard_code="A0000"):
    """계정 한 행을 변환하고 (전체 결과, 첫 entry)를 반환한다."""
    stmt = make_statement(account_name, amount, mapping_type,
                          standard_code=standard_code)
    responses = {stmt["id"]: (response or {})}
    result = server.generate_conversion(PROJECT, [stmt], responses)
    return result, result["entries"][0]


# ---------------------------------------------------------------------------
# 리스 (IFRS 16) — 리스료 현재가치
# ---------------------------------------------------------------------------

class TestLeasePresentValue(unittest.TestCase):

    def _independent_pv(self, payment, annual_rate_pct, months):
        """폐쇄형 공식과 별개로 매기 현금흐름을 직접 할인·합산한 검증값."""
        monthly_r = annual_rate_pct / 100 / 12
        return sum(payment / (1 + monthly_r) ** t for t in range(1, months + 1))

    def test_positive_discount_rate_matches_summation(self):
        # 월 500만원, 연 6%, 24개월, K-GAAP 장부금액 1억
        payment, rate, months, book = 5_000_000, 6.0, 24, 100_000_000
        _, entry = convert_single(
            "리스부채", book, "judgment",
            response={
                "lease_term_months": months,
                "monthly_payment": payment,
                "discount_rate": rate,
            },
        )
        # 함수가 낸 조정액으로부터 PV를 복원해 독립 합산값과 비교
        pv_from_func = entry["adjustment"] + book
        pv_expected = self._independent_pv(payment, rate, months)
        self.assertAlmostEqual(pv_from_func, pv_expected, delta=0.01)
        self.assertIn("현재가치", entry["calculation"])

    def test_zero_discount_rate_is_simple_sum(self):
        # 할인율 0이면 PV = 월지급액 × 개월수 (할인 없음)
        payment, months, book = 1_000_000, 12, 8_000_000
        _, entry = convert_single(
            "리스", book, "judgment",
            response={
                "lease_term_months": months,
                "monthly_payment": payment,
                "discount_rate": 0,
            },
        )
        expected_adjustment = round(payment * months - book, 2)  # 12,000,000 - 8,000,000
        self.assertEqual(entry["adjustment"], expected_adjustment)
        self.assertEqual(entry["adjustment"], 4_000_000)

    def test_annual_rate_is_converted_to_monthly(self):
        # 연 12%는 월 1%로 환산되어야 한다. 월 1%로 직접 할인한 값과 일치해야 함.
        payment, months, book = 2_000_000, 6, 0
        _, entry = convert_single(
            "리스부채", book, "judgment",
            response={
                "lease_term_months": months,
                "monthly_payment": payment,
                "discount_rate": 12.0,
            },
        )
        monthly_r = 0.01
        pv_monthly = sum(payment / (1 + monthly_r) ** t for t in range(1, months + 1))
        self.assertAlmostEqual(entry["adjustment"], round(pv_monthly, 2), delta=0.01)

    def test_missing_inputs_produce_no_adjustment(self):
        # 개월수나 지급액이 없으면 조정액은 기본값 0, calculation 미기재
        _, entry = convert_single(
            "리스", 5_000_000, "judgment",
            response={"lease_term_months": 0, "monthly_payment": 0},
        )
        self.assertEqual(entry["adjustment"], 0)
        self.assertNotIn("calculation", entry)


# ---------------------------------------------------------------------------
# 개발비 (IAS 38) — 자산화 요건
# ---------------------------------------------------------------------------

class TestDevelopmentCapitalization(unittest.TestCase):

    ALL_TRUE = {
        "technical_feasibility": True,
        "intention_to_complete": True,
        "probable_future_benefits": True,
        "reliable_measurement": True,
    }

    def test_all_criteria_met_capitalizes_as_intangible(self):
        _, entry = convert_single("개발비", 30_000_000, "judgment",
                                  response=dict(self.ALL_TRUE))
        self.assertEqual(entry["target_account"], "무형자산")

    def test_one_criterion_missing_expenses_it(self):
        partial = dict(self.ALL_TRUE)
        partial["reliable_measurement"] = False
        _, entry = convert_single("개발비", 30_000_000, "judgment",
                                  response=partial)
        self.assertEqual(entry["target_account"], "연구개발비(비용)")

    def test_none_criteria_defaults_to_expense(self):
        # 체크리스트 미입력(빈 응답)이면 자산화 요건 불충족 → 비용
        _, entry = convert_single("개발비", 30_000_000, "judgment", response={})
        self.assertEqual(entry["target_account"], "연구개발비(비용)")

    def test_truthy_but_not_true_does_not_qualify(self):
        # `is True` 엄격 비교이므로 "true"/1 같은 truthy 값은 자산화 안 됨
        almost = {k: 1 for k in self.ALL_TRUE}  # 값이 1 (True 아님)
        _, entry = convert_single("개발비", 30_000_000, "judgment", response=almost)
        self.assertEqual(entry["target_account"], "연구개발비(비용)")


# ---------------------------------------------------------------------------
# 충당부채 (IAS 37) — 인식 3요건
# ---------------------------------------------------------------------------

class TestProvisionRecognition(unittest.TestCase):

    def test_all_three_conditions_recognized(self):
        _, entry = convert_single(
            "충당부채", 10_000_000, "judgment",
            response={
                "present_obligation": True,
                "probable_outflow": True,
                "reliable_estimate": True,
            },
        )
        self.assertIn("충족", entry["calculation"])

    def test_incomplete_conditions_flag_review(self):
        _, entry = convert_single(
            "충당부채", 10_000_000, "judgment",
            response={
                "present_obligation": True,
                "probable_outflow": False,
                "reliable_estimate": True,
            },
        )
        self.assertIn("추가 검토", entry["calculation"])


# ---------------------------------------------------------------------------
# 수익 (IFRS 15) — 인식 시점 문서화
# ---------------------------------------------------------------------------

class TestRevenueTiming(unittest.TestCase):

    def test_timing_is_documented(self):
        _, entry = convert_single(
            "매출", 50_000_000, "judgment",
            response={"recognition_timing": "기간에 걸쳐 인식"},
        )
        self.assertIn("기간에 걸쳐 인식", entry["calculation"])

    def test_missing_timing_falls_back(self):
        _, entry = convert_single("매출", 50_000_000, "judgment", response={})
        self.assertIn("추가 검토 필요", entry["calculation"])


# ---------------------------------------------------------------------------
# 매핑 일반 — simple/judgment 분기와 집계
# ---------------------------------------------------------------------------

class TestMappingAggregation(unittest.TestCase):

    def test_simple_account_maps_without_adjustment(self):
        _, entry = convert_single("현금및현금성자산", 20_000_000, "simple")
        self.assertEqual(entry["target_account"], "현금및현금성자산")
        self.assertEqual(entry["adjustment"], 0)

    def test_judgment_rows_collected_simple_rows_excluded(self):
        cash = make_statement("현금및현금성자산", 20_000_000, "simple",
                              statement_id="cash-1")
        prov = make_statement("충당부채", 10_000_000, "judgment",
                              statement_id="prov-1")
        responses = {
            "cash-1": {},
            "prov-1": {"present_obligation": True,
                       "probable_outflow": True,
                       "reliable_estimate": True},
        }
        result = server.generate_conversion(PROJECT, [cash, prov], responses)

        # judgment 항목만 judgment_items / draft_notes 에 잡혀야 한다
        self.assertEqual(len(result["judgment_items"]), 1)
        self.assertEqual(result["judgment_items"][0]["account"], "충당부채")
        self.assertEqual(len(result["draft_notes"]), 1)
        self.assertEqual(len(result["entries"]), 2)  # entries에는 둘 다 존재

    def test_review_status_flags_human_review(self):
        result, _ = convert_single("매출채권", 5_000_000, "judgment")
        self.assertEqual(result["review_status"], "사람 검토 필요")


# ---------------------------------------------------------------------------
# 계정 정규화 — 현재 동작 및 알려진 한계 문서화
# ---------------------------------------------------------------------------

class TestNormalizeAccountName(unittest.TestCase):

    def test_known_aliases_resolve(self):
        self.assertEqual(server.normalize_account_name("현금및현금성자산"), "cash")
        self.assertEqual(server.normalize_account_name("리스부채"), "lease")
        self.assertEqual(server.normalize_account_name("충당부채"), "provision")

    def test_whitespace_and_case_are_ignored(self):
        self.assertEqual(server.normalize_account_name("  Cash  "), "cash")

    def test_unknown_account_falls_back_to_other(self):
        self.assertEqual(server.normalize_account_name("이연법인세자산"), "other")

    def test_known_limitation_substring_overmatch(self):
        # [한계 문서화] 부분문자열 매칭이라 '무형자산'이 무조건 development로 감.
        # 무형자산이 개발비만은 아니므로 오탐 가능 — 리팩터링 시 이 테스트가 신호가 됨.
        self.assertEqual(server.normalize_account_name("영업권"), "other")   # 무형자산이지만 별칭 없음
        self.assertEqual(server.normalize_account_name("무형자산"), "development")  # 현재 동작(주의)


if __name__ == "__main__":
    unittest.main(verbosity=2)
