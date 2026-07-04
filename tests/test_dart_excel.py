import io
import json
import zipfile
import unittest

import server
from gtf_app.routing import resolve_get, resolve_post


class DartImportAndWorkbookTests(unittest.TestCase):
    def test_financial_product_names_do_not_map_to_inventory(self):
        self.assertEqual(server.normalize_account_name("단기금융상품"), "financial_instrument")
        self.assertEqual(server.normalize_account_name("파생상품"), "financial_instrument")

    def test_dart_statement_rows_parse_current_amounts(self):
        payload = {
            "status": "000",
            "message": "정상",
            "list": [
                {
                    "account_nm": "자산총계",
                    "thstrm_amount": "514,531,948,000,000",
                    "sj_nm": "재무상태표",
                },
                {
                    "account_nm": "리스부채",
                    "thstrm_amount": "30,000,000",
                    "sj_nm": "재무상태표",
                    "currency": "KRW",
                    "account_id": "ifrs-full_LeaseLiabilities",
                },
                {
                    "account_nm": "매출",
                    "thstrm_amount": "(250,000,000)",
                    "sj_nm": "손익계산서",
                },
            ],
        }

        rows, issues = server.dart_statement_rows(payload)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["account_name"], "리스부채")
        self.assertEqual(rows[0]["amount"], 30_000_000)
        self.assertEqual(rows[0]["account_key"], "lease")
        self.assertEqual(rows[0]["source"], "dart_api")
        self.assertEqual(rows[1]["amount"], -250_000_000)
        self.assertIn("DART 원본 3개 계정 중 변환 대상 핵심 계정 2개", issues[0])

    def test_dart_statement_rows_filters_totals_and_unmapped_accounts(self):
        payload = {
            "status": "000",
            "message": "정상",
            "list": [
                {"account_nm": "자산총계", "thstrm_amount": "1000000", "sj_nm": "재무상태표"},
                {"account_nm": "유동자산", "thstrm_amount": "900000", "sj_nm": "재무상태표"},
                {"account_nm": "현금및현금성자산", "thstrm_amount": "500000", "sj_nm": "재무상태표"},
                {"account_nm": "영업권", "thstrm_amount": "300000", "sj_nm": "재무상태표"},
                {"account_nm": "매출채권", "thstrm_amount": "200000", "sj_nm": "재무상태표"},
            ],
        }

        rows, _issues = server.dart_statement_rows(payload)

        self.assertEqual([row["account_name"] for row in rows], ["현금및현금성자산", "매출채권"])

    def test_dart_raw_statement_rows_preserves_filtered_out_accounts(self):
        payload = {
            "status": "000",
            "message": "정상",
            "list": [
                {"account_nm": "자산총계", "thstrm_amount": "1000000", "sj_nm": "재무상태표"},
                {"account_nm": "현금및현금성자산", "thstrm_amount": "500000", "sj_nm": "재무상태표"},
            ],
        }

        raw_rows = server.dart_raw_statement_rows(payload)
        filtered_rows, _issues = server.dart_statement_rows(payload)

        self.assertEqual([row["account_name"] for row in raw_rows], ["자산총계", "현금및현금성자산"])
        self.assertEqual([row["account_name"] for row in filtered_rows], ["현금및현금성자산"])
        self.assertFalse(raw_rows[0]["conversion_candidate"])
        self.assertIn("합계", raw_rows[0]["filter_reason"])

    def test_dart_raw_rows_from_upload_reads_saved_payload(self):
        saved_payload = {
            "raw_rows": [{"account_name": "자산총계", "conversion_candidate": False}],
            "filtered_rows": [{"account_name": "현금및현금성자산"}],
        }

        rows = server.dart_raw_rows_from_upload({"file_bytes": json.dumps(saved_payload).encode("utf-8")})

        self.assertEqual(rows, saved_payload["raw_rows"])

    def test_dart_statement_rows_reports_api_error(self):
        rows, issues = server.dart_statement_rows({"status": "013", "message": "조회된 데이터가 없습니다."})

        self.assertEqual(rows, [])
        self.assertIn("DART API 오류 013", issues[0])

    def test_review_workbook_contains_expected_sheets(self):
        workbook = server.review_workbook_bytes(
            {"company_name": "샘플테크", "period": "2024"},
            [
                {
                    "account_name": "자산총계",
                    "amount": 100_000_000,
                    "statement_type": "재무상태표",
                    "conversion_candidate": False,
                    "filter_reason": "합계/소계/성과지표/현금흐름표 활동 항목",
                },
                {"account_name": "리스부채", "amount": 30_000_000, "statement_type": "재무상태표"},
            ],
            [
                {
                    "account_name": "리스부채",
                    "normalized_account": "리스",
                    "standard_code": "A2100",
                    "amount": 30_000_000,
                    "period": "2024",
                    "mapping_type": "judgment",
                    "rule_summary": "K-IFRS 제1116호 검토",
                }
            ],
            {
                "entries": [
                    {
                        "source_account": "리스부채",
                        "standard_code": "A2100",
                        "target_account": "Right-of-use asset and lease liability",
                        "statement_type": "재무상태표",
                        "statement_line_item": "사용권자산 및 리스부채",
                        "amount": 30_000_000,
                        "adjustment": 3_812_000,
                        "mapping_type": "judgment",
                        "calculation": "리스료 현재가치",
                    }
                ],
                "draft_notes": [{"account": "리스부채", "draft_note": "K-IFRS 제1116호 검토 필요"}],
                "ai_assistance": {"status": "skipped", "overall_note": "사람 검토 필요"},
            },
            [{"created_at": "2026-07-03T00:00:00+00:00", "actor": "system", "event_type": "test", "detail": {}}],
        )

        with zipfile.ZipFile(io.BytesIO(workbook)) as archive:
            names = set(archive.namelist())
            workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
            sheet1_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")

        self.assertIn("[Content_Types].xml", names)
        self.assertIn("xl/worksheets/sheet5.xml", names)
        self.assertIn("01_원본_DART", workbook_xml)
        self.assertIn("05_감사로그", workbook_xml)
        self.assertIn("자산총계", sheet1_xml)
        self.assertIn("제외사유", sheet1_xml)

    def test_routes_include_dart_import_and_workbook_export(self):
        self.assertEqual(resolve_post("/api/projects/p1/dart/import").name, "dart.import")
        match = resolve_get("/api/projects/p1/exports/review-workbook.xlsx")
        self.assertEqual(match.name, "exports.get")
        self.assertEqual(match.args, ("p1", "review-workbook.xlsx"))


if __name__ == "__main__":
    unittest.main()
