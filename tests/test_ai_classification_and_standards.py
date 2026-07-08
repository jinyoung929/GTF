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
    build_statement_record,
    conversion_basis_report,
    generate_conversion,
)
from gtf_app.excel_export import review_workbook_bytes  # noqa: E402

sys.path.insert(0, _HERE)
from reference_fixture import load_reference  # noqa: E402

# 기준정보는 운영과 동일하게 SQL 시드 → DB 조회로 로드해 주입한다
REF = load_reference()


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
        self.assertTrue(rows)
        sets = {row["standard_set"] for row in rows}
        self.assertEqual(sets, {"K-GAAP", "K-IFRS"})

    def test_seed_is_idempotent(self):
        conn = seeded_connection()
        before = len(server.find_standards_paragraphs(conn))
        server.ensure_standards_paragraphs(conn)
        self.assertEqual(len(server.find_standards_paragraphs(conn)), before)

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
        output = generate_conversion(PROJECT, [self.make_statement("리스부채")], {}, REF)
        paragraphs = output["judgment_items"][0]["standards_paragraphs"]
        self.assertTrue(paragraphs)
        self.assertEqual({p["standard_set"] for p in paragraphs}, {"K-GAAP", "K-IFRS"})

    def test_basis_report_lists_paragraphs(self):
        output = generate_conversion(PROJECT, [self.make_statement("리스부채")], {}, REF)
        report = conversion_basis_report(output)
        self.assertIn("K-IFRS 제1116호", report)
        self.assertIn("일반기업회계기준 제13장", report)

    def test_excel_workbook_review_sheet_contains_paragraphs(self):
        output = generate_conversion(PROJECT, [self.make_statement("리스부채")], {}, REF)
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


class ExpandedStandardCatalogTest(unittest.TestCase):
    def test_catalog_includes_ifrs_accounts_beyond_core_eight(self):
        for key in ("ppe", "deferred_tax_asset", "prepaid_expense", "share_capital", "retained_earnings", "cost_of_sales"):
            self.assertIn(key, REF.accounts)

    def test_ai_can_suggest_expanded_account(self):
        # 임차보증금은 키워드 사전에 없어 미분류(X9999)로 빠지므로 AI 제안 대상이 된다.
        row = {
            "account_name": "임차보증금",
            "amount": 60000000,
            "ai_suggestion": {"account_key": "deposits", "label": "보증금", "confidence": "high", "rationale": "반환 예정 보증금은 금융자산 성격"},
        }
        record = build_statement_record("2024", row, REF)
        self.assertEqual(record["standard_code"], "A1400")
        self.assertEqual(record["mapping_source"], "ai_suggested_human_accepted")

    def test_classification_candidates_exclude_only_other(self):
        candidates = [key for key in REF.accounts if key != "other"]
        self.assertGreater(len(candidates), 8)
        self.assertNotIn("other", candidates)

    def test_seed_reference_data_handles_expanded_accounts(self):
        # 보조 조회 테이블(ifrs_accounts 등)은 핵심 시드 테이블에서 파생 생성된다
        from reference_fixture import seeded_connection as fixture_connection

        conn = fixture_connection()
        server.seed_reference_data(conn)
        accounts = conn.execute("SELECT COUNT(*) AS c FROM standard_accounts").fetchone()["c"]
        derived = conn.execute("SELECT COUNT(*) AS c FROM ifrs_accounts").fetchone()["c"]
        self.assertEqual(derived, accounts)
        self.assertEqual(accounts, len(REF.accounts))


class StatementTemplateSeedTest(unittest.TestCase):
    """표준양식 라인 SQL 시드(단일 출처)가 전 계정을 커버하고 코드 도출 순서와 일치하는지 검증."""

    def setUp(self):
        import sqlite3

        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(server.SQLITE_SCHEMA_PATH.read_text(encoding="utf-8"))
        server.ensure_reference_accounts(self.conn)
        server.ensure_statement_templates(self.conn)

    def tearDown(self):
        self.conn.close()

    def rows(self):
        return self.conn.execute(
            "SELECT account_key, display_order, line_item FROM financial_statement_templates"
        ).fetchall()

    def test_every_standard_account_has_a_template_line(self):
        mapped = {row["account_key"] for row in self.rows()}
        self.assertEqual(mapped, set(REF.accounts.keys()))

    def test_display_order_matches_account_code_derivation(self):
        from gtf_app.domain import account_presentation_order

        for row in self.rows():
            code = REF.accounts[row["account_key"]]["code"]
            self.assertEqual(
                row["display_order"],
                account_presentation_order(code),
                f"{row['account_key']}의 SQL display_order가 계정코드 도출값과 다릅니다",
            )

    def test_seed_is_idempotent(self):
        server.ensure_reference_accounts(self.conn)
        server.ensure_statement_templates(self.conn)
        self.assertEqual(len(self.rows()), len(REF.accounts))

    def test_new_catalog_accounts_get_statement_lines_in_conversion(self):
        statement = build_statement_record(
            "2024",
            {
                "account_name": "이연법인세자산",
                "amount": 35000000.0,
                "ai_suggestion": {"account_key": "deferred_tax_asset", "label": "이연법인세자산", "confidence": "high", "rationale": "IAS 12"},
            },
            REF,
        )
        output = generate_conversion(PROJECT, [statement], {}, REF)
        entry = output["entries"][0]
        self.assertEqual(entry["statement_line_item"], "이연법인세자산")
        self.assertEqual(entry["statement_type"], "재무상태표")


class PresentationOrderTest(unittest.TestCase):
    def test_order_derived_from_account_code(self):
        from gtf_app.domain import account_presentation_order

        # 자산(A) < 금융상품(F) < 부채(L) < 자본(E) < 손익(R) < 미분류(X)
        self.assertLess(account_presentation_order("A1000"), account_presentation_order("A1100"))
        self.assertLess(account_presentation_order("A3100"), account_presentation_order("F1000"))
        self.assertLess(account_presentation_order("F1000"), account_presentation_order("L1000"))
        self.assertLess(account_presentation_order("L2200"), account_presentation_order("E1000"))
        self.assertLess(account_presentation_order("E1200"), account_presentation_order("R1000"))
        self.assertLess(account_presentation_order("R3000"), account_presentation_order("X9999"))

    def test_malformed_code_does_not_crash(self):
        from gtf_app.domain import account_presentation_order

        self.assertIsInstance(account_presentation_order(""), int)
        self.assertIsInstance(account_presentation_order("ZZZZ"), int)

    def test_conversion_entries_sorted_by_code(self):
        stmts = [
            build_statement_record("2024", {"account_name": "매출액", "amount": 1000}, REF),
            build_statement_record("2024", {"account_name": "현금및현금성자산", "amount": 1000}, REF),
            build_statement_record("2024", {"account_name": "충당부채", "amount": 1000}, REF),
            build_statement_record("2024", {"account_name": "매출채권", "amount": 1000}, REF),
        ]
        output = generate_conversion(PROJECT, stmts, {}, REF)
        codes = [entry["standard_code"] for entry in output["entries"]]
        self.assertEqual(codes, sorted(codes, key=lambda c: __import__("server").account_presentation_order(c)))
        self.assertEqual(codes[0], "A1000")  # 현금이 맨 앞


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
        record = build_statement_record("2024", {"account_name": "임차보증금", "amount": 500.0, "ai_suggestion": self.SUGGESTION}, REF)
        self.assertEqual(record["standard_code"], "F1000")
        self.assertEqual(record["mapping_source"], "ai_suggested_human_accepted")
        self.assertIn("[AI 1차 분류 제안", record["rule_summary"])

    def test_suggestion_ignored_when_rule_mapping_succeeds(self):
        record = build_statement_record("2024", {"account_name": "리스부채", "amount": 500.0, "ai_suggestion": self.SUGGESTION}, REF)
        self.assertEqual(record["standard_code"], "A2100")
        self.assertEqual(record["mapping_source"], "rule_based")

    def test_invalid_suggestion_key_falls_back_to_manual_review(self):
        record = build_statement_record("2024", {"account_name": "임차보증금", "amount": 500.0, "ai_suggestion": {"account_key": "없는키"}}, REF)
        self.assertEqual(record["standard_code"], "X9999")
        self.assertEqual(record["mapping_source"], "rule_based")

    def test_plain_record_keeps_previous_shape(self):
        record = build_statement_record("2024", {"account_name": "현금", "amount": 1.0}, REF)
        self.assertEqual(record["standard_code"], "A1000")
        self.assertEqual(record["mapping_source"], "rule_based")
        self.assertIsNone(record["ai_suggestion"])


if __name__ == "__main__":
    unittest.main()
