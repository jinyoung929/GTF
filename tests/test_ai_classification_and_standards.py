"""
AI 1차 분류 및 기준서 문단 검색 DB 테스트
==========================================

검증 범위:
  - standards_paragraphs 시드: K-GAAP/K-IFRS 분리 보관
  - find_standards_paragraphs: 계정키/기준세트/키워드 검색
  - generate_conversion: 판단 필요 항목에 기준서 문단 첨부
  - conversion_basis_report / 엑셀 워크북: 문단 근거 표시
  - call_ai_classification: 키 미설정/미분류 없음/정상 응답/무효 제안 방어
  - build_statement_record: AI 제안의 사람 확정 적용 (X9999 한정)

실행:
    python3 -m unittest tests.test_ai_classification_and_standards -v
"""

import io
import json
import os
import sqlite3
import sys
import unittest
import zipfile
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
for _candidate in (_HERE, os.path.dirname(_HERE)):
    if os.path.exists(os.path.join(_candidate, "server.py")):
        sys.path.insert(0, _candidate)
        break

import server  # noqa: E402
from gtf_app.domain import (  # noqa: E402
    STANDARDS_PARAGRAPHS,
    build_statement_record,
    conversion_basis_report,
    generate_conversion,
)
from gtf_app.excel_export import review_workbook_bytes  # noqa: E402


PROJECT = {
    "id": "proj-test",
    "company_name": "테스트회사",
    "period": "2024",
    "source_standard": "K-GAAP",
    "target_standard": "IFRS",
}


def seeded_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    server.ensure_standards_paragraphs(conn)
    return conn


class StandardsParagraphsSeedTest(unittest.TestCase):
    def test_both_standard_sets_are_seeded_separately(self):
        conn = seeded_connection()
        rows = server.find_standards_paragraphs(conn)
        self.assertEqual(len(rows), len(STANDARDS_PARAGRAPHS))
        sets = {row["standard_set"] for row in rows}
        self.assertEqual(sets, {"K-GAAP", "K-IFRS"})

    def test_seed_is_idempotent(self):
        conn = seeded_connection()
        server.ensure_standards_paragraphs(conn)
        rows = server.find_standards_paragraphs(conn)
        self.assertEqual(len(rows), len(STANDARDS_PARAGRAPHS))

    def test_judgment_account_has_paragraphs_from_both_sets(self):
        conn = seeded_connection()
        for account_key in ("lease", "development", "revenue", "financial_instrument", "provision", "receivables"):
            sets = {row["standard_set"] for row in server.find_standards_paragraphs(conn, account_key=account_key)}
            self.assertEqual(sets, {"K-GAAP", "K-IFRS"}, account_key)


class StandardsParagraphsSearchTest(unittest.TestCase):
    def test_keyword_search_hits_content_and_keywords(self):
        conn = seeded_connection()
        hits = server.find_standards_paragraphs(conn, query="기대신용손실")
        self.assertTrue(hits)
        self.assertTrue(all("receivables" == row["account_key"] for row in hits))

    def test_standard_set_filter(self):
        conn = seeded_connection()
        hits = server.find_standards_paragraphs(conn, account_key="lease", standard_set="K-GAAP")
        self.assertEqual({row["standard_set"] for row in hits}, {"K-GAAP"})
        self.assertIn("운용리스", hits[0]["content"])

    def test_no_match_returns_empty(self):
        conn = seeded_connection()
        self.assertEqual(server.find_standards_paragraphs(conn, query="존재하지않는키워드"), [])


class ConversionParagraphAttachmentTest(unittest.TestCase):
    def make_statement(self, account_name, mapping_type="judgment"):
        return {
            "id": "row-1",
            "account_name": account_name,
            "standard_code": "A2100",
            "amount": 1000.0,
            "mapping_type": mapping_type,
            "rule_summary": "테스트 규칙",
        }

    def test_judgment_item_includes_both_standard_sets(self):
        conn = seeded_connection()
        standards_map = server.load_standards_paragraph_map(conn)
        output = generate_conversion(PROJECT, [self.make_statement("리스부채")], {}, {}, standards_map)
        paragraphs = output["judgment_items"][0]["standards_paragraphs"]
        self.assertTrue(paragraphs)
        self.assertEqual({p["standard_set"] for p in paragraphs}, {"K-GAAP", "K-IFRS"})

    def test_fallback_without_db_map_uses_domain_data(self):
        output = generate_conversion(PROJECT, [self.make_statement("리스부채")], {})
        paragraphs = output["judgment_items"][0]["standards_paragraphs"]
        self.assertEqual({p["standard_set"] for p in paragraphs}, {"K-GAAP", "K-IFRS"})

    def test_basis_report_lists_paragraphs(self):
        output = generate_conversion(PROJECT, [self.make_statement("리스부채")], {})
        report = conversion_basis_report(output)
        self.assertIn("K-IFRS 제1116호", report)
        self.assertIn("일반기업회계기준 제13장", report)

    def test_excel_workbook_review_sheet_contains_paragraphs(self):
        output = generate_conversion(PROJECT, [self.make_statement("리스부채")], {})
        workbook = review_workbook_bytes(PROJECT, [], [], output, [])
        with zipfile.ZipFile(io.BytesIO(workbook)) as archive:
            sheet4 = archive.read("xl/worksheets/sheet4.xml").decode("utf-8")
        self.assertIn("기준서 문단", sheet4)
        self.assertIn("일반기업회계기준", sheet4)


class AiClassificationCallTest(unittest.TestCase):
    def test_no_unmapped_accounts_skips(self):
        result = server.call_ai_classification([])
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["suggestions"], {})

    def test_missing_api_key_reports_not_configured(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            result = server.call_ai_classification(["임차보증금"])
        self.assertEqual(result["status"], "not_configured")
        self.assertTrue(result["human_review_required"])

    def _fake_openai(self, items):
        body = json.dumps({"output_text": json.dumps({"items": items}, ensure_ascii=False)}).encode("utf-8")

        class FakeResponse:
            def read(self):
                return body

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        return FakeResponse()

    def test_connected_response_builds_validated_suggestions(self):
        items = [
            {
                "account_name": "임차보증금",
                "suggested_account_key": "financial_instrument",
                "confidence": "medium",
                "rationale": "보증금은 금융자산 성격의 계약상 권리입니다.",
            },
            {"account_name": "이상한계정", "suggested_account_key": "없는키", "confidence": "low", "rationale": "-"},
            {"account_name": "모르는계정", "suggested_account_key": "other", "confidence": "low", "rationale": "-"},
        ]
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with mock.patch.object(server.url_request, "urlopen", return_value=self._fake_openai(items)):
                result = server.call_ai_classification(["임차보증금", "이상한계정", "모르는계정"])
        self.assertEqual(result["status"], "connected")
        self.assertEqual(set(result["suggestions"].keys()), {"임차보증금"})
        suggestion = result["suggestions"]["임차보증금"]
        self.assertEqual(suggestion["account_key"], "financial_instrument")
        self.assertTrue(suggestion["human_review_required"])

    def test_attach_only_marks_unmapped_rows(self):
        rows = [
            {"account_name": "임차보증금", "amount": 500.0},
            {"account_name": "현금", "amount": 100.0},
        ]
        items = [
            {
                "account_name": "임차보증금",
                "suggested_account_key": "financial_instrument",
                "confidence": "medium",
                "rationale": "보증금은 금융자산 성격입니다.",
            }
        ]
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with mock.patch.object(server.url_request, "urlopen", return_value=self._fake_openai(items)):
                rows, result = server.attach_ai_classification(rows)
        self.assertEqual(result["status"], "connected")
        self.assertIn("ai_suggestion", rows[0])
        self.assertNotIn("ai_suggestion", rows[1])


class AiSuggestionHumanAcceptanceTest(unittest.TestCase):
    SUGGESTION = {
        "account_key": "financial_instrument",
        "label": "금융상품",
        "confidence": "medium",
        "rationale": "보증금은 금융자산 성격입니다.",
        "provider": "openai",
        "model": "gpt-4.1-mini",
        "human_review_required": True,
    }

    def test_suggestion_applied_only_for_unmapped_account(self):
        record = build_statement_record("2024", {"account_name": "임차보증금", "amount": 500.0, "ai_suggestion": self.SUGGESTION})
        self.assertEqual(record["standard_code"], "F1000")
        self.assertEqual(record["mapping_source"], "ai_suggested_human_accepted")
        self.assertIn("[AI 1차 분류 제안", record["rule_summary"])

    def test_suggestion_ignored_when_rule_mapping_succeeds(self):
        record = build_statement_record("2024", {"account_name": "리스부채", "amount": 500.0, "ai_suggestion": self.SUGGESTION})
        self.assertEqual(record["standard_code"], "A2100")
        self.assertEqual(record["mapping_source"], "rule_based")

    def test_invalid_suggestion_key_falls_back_to_manual_review(self):
        record = build_statement_record("2024", {"account_name": "임차보증금", "amount": 500.0, "ai_suggestion": {"account_key": "없는키"}})
        self.assertEqual(record["standard_code"], "X9999")
        self.assertEqual(record["mapping_source"], "rule_based")

    def test_plain_record_keeps_previous_shape(self):
        record = build_statement_record("2024", {"account_name": "현금", "amount": 1.0})
        self.assertEqual(record["standard_code"], "A1000")
        self.assertEqual(record["mapping_source"], "rule_based")
        self.assertIsNone(record["ai_suggestion"])


if __name__ == "__main__":
    unittest.main()
