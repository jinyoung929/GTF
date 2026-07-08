"""
1차 승인(AI 제안 계정별 확정)과 2차 승인(검토 요약·게이트) 테스트
=================================================================

검증 범위:
  - apply_ai_decisions: 계정별 승인/거절/미결정 처리와 구버전(결정 없음) 호환
  - build_review_summary: 확인 필요(문제 상황)와 회계 판단(계정 종류) 그룹 분리,
    미분류 잔존 시 승인 차단(can_approve=False), 경고는 승인 허용

실행:
    python3 -m unittest tests.test_review_approval -v
"""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
for _candidate in (_HERE, os.path.dirname(_HERE)):
    if os.path.exists(os.path.join(_candidate, "server.py")):
        sys.path.insert(0, _candidate)
        break

import server  # noqa: E402
from gtf_app.domain import build_review_summary, build_statement_record  # noqa: E402

sys.path.insert(0, _HERE)
from reference_fixture import load_reference  # noqa: E402

REF = load_reference()


SUGGESTION = {"account_key": "financial_instrument", "label": "금융상품", "confidence": "medium", "rationale": "테스트"}


def suggested_row(name, amount=100.0):
    return {"account_name": name, "amount": amount, "ai_suggestion": dict(SUGGESTION)}


class ApplyAiDecisionsTest(unittest.TestCase):
    def test_approved_suggestion_is_kept(self):
        rows, summary = server.apply_ai_decisions([suggested_row("임차보증금")], {"임차보증금": "approved"})
        self.assertIn("ai_suggestion", rows[0])
        self.assertEqual(summary["approved"], ["임차보증금"])
        self.assertTrue(summary["per_account_review"])

    def test_rejected_suggestion_is_stripped(self):
        rows, summary = server.apply_ai_decisions([suggested_row("임차보증금")], {"임차보증금": "rejected"})
        self.assertNotIn("ai_suggestion", rows[0])
        self.assertEqual(summary["rejected"], ["임차보증금"])
        record = build_statement_record("2024", rows[0], REF)
        self.assertEqual(record["standard_code"], "X9999")

    def test_undecided_suggestion_is_not_applied(self):
        rows, summary = server.apply_ai_decisions([suggested_row("임차보증금")], {})
        self.assertNotIn("ai_suggestion", rows[0])
        self.assertEqual(summary["undecided"], ["임차보증금"])

    def test_legacy_client_without_decisions_applies_all(self):
        rows, summary = server.apply_ai_decisions([suggested_row("임차보증금")], None)
        self.assertIn("ai_suggestion", rows[0])
        self.assertFalse(summary["per_account_review"])

    def test_rows_without_suggestion_pass_through(self):
        rows, summary = server.apply_ai_decisions([{"account_name": "현금", "amount": 1}], {"현금": "rejected"})
        self.assertEqual(rows[0]["account_name"], "현금")
        self.assertEqual(summary["approved"], [])
        self.assertEqual(summary["rejected"], [])

    def test_original_rows_are_not_mutated(self):
        original = [suggested_row("임차보증금")]
        server.apply_ai_decisions(original, {"임차보증금": "rejected"})
        self.assertIn("ai_suggestion", original[0])


class BuildReviewSummaryTest(unittest.TestCase):
    def lease_statement(self):
        return build_statement_record("2024", {"account_name": "리스부채", "amount": 1000.0}, REF)

    def unclassified_statement(self):
        return build_statement_record("2024", {"account_name": "이상한계정", "amount": 10.0}, REF)

    def conversion_for(self, statement, response=None, paragraphs=3):
        return {
            "judgment_items": [
                {
                    "statement_id": statement["id"],
                    "account": statement["account_name"],
                    "checklist_response": response or {},
                    "standards_paragraphs": [{"standard_set": "K-IFRS"}] * paragraphs,
                }
            ]
        }

    def test_unclassified_blocks_approval(self):
        statements = [self.lease_statement(), self.unclassified_statement()]
        summary = build_review_summary(statements, self.conversion_for(statements[0], {"lease_term_months": 36}), None)
        self.assertFalse(summary["can_approve"])
        self.assertEqual(summary["counts"]["unclassified"], 1)
        types = {item["type"] for item in summary["attention"]}
        self.assertIn("unclassified", types)

    def test_missing_checklist_is_warning_not_blocking(self):
        statement = self.lease_statement()
        summary = build_review_summary([statement], self.conversion_for(statement, response={}), None)
        flags = [item for item in summary["attention"] if item["type"] == "checklist_missing"]
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]["severity"], "warning")
        self.assertTrue(summary["can_approve"])

    def test_answered_checklist_produces_clean_judgment_item(self):
        statement = self.lease_statement()
        summary = build_review_summary([statement], self.conversion_for(statement, {"lease_term_months": 36}), None)
        self.assertTrue(summary["can_approve"])
        item = summary["judgment"][0]
        self.assertTrue(item["checklist_answered"])
        self.assertEqual(item["standards_paragraph_count"], 3)
        self.assertEqual(summary["counts"]["attention"], 0)

    def test_validation_error_blocks_and_warning_does_not(self):
        statement = self.lease_statement()
        conversion = self.conversion_for(statement, {"lease_term_months": 36})
        warned = build_review_summary([statement], conversion, {"checks": [{"name": "단위 검토", "status": "warning", "detail": "확인"}]})
        self.assertTrue(warned["can_approve"])
        blocked = build_review_summary([statement], conversion, {"checks": [{"name": "계정 행", "status": "error", "detail": "없음"}]})
        self.assertFalse(blocked["can_approve"])

    def test_no_conversion_blocks_approval(self):
        statement = self.lease_statement()
        summary = build_review_summary([statement], None, None)
        self.assertFalse(summary["can_approve"])
        self.assertFalse(summary["has_conversion"])

    def test_simple_accounts_are_not_listed_as_judgment(self):
        statement = build_statement_record("2024", {"account_name": "현금", "amount": 100.0}, REF)
        summary = build_review_summary([statement], {"judgment_items": []}, None)
        self.assertEqual(summary["judgment"], [])
        self.assertTrue(summary["can_approve"])


if __name__ == "__main__":
    unittest.main()
