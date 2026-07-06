from __future__ import annotations

import io
import json
import zipfile

from gtf_app.domain import label_backend, localize_export_text


def xlsx_escape(value) -> str:
    text = str(value if value is not None else "")
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def xlsx_col_name(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def xlsx_sheet_xml(rows: list[list]) -> str:
    xml_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(row):
            ref = f"{xlsx_col_name(col_index)}{row_index}"
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{xlsx_escape(value)}</t></is></c>')
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(xml_rows)}</sheetData>'
        "</worksheet>"
    )


def create_xlsx_workbook(sheets: list[tuple[str, list[list]]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            + "".join(
                f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for index in range(1, len(sheets) + 1)
            )
            + "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        workbook_sheets = "".join(
            f'<sheet name="{xlsx_escape(name[:31])}" sheetId="{index}" r:id="rId{index}"/>'
            for index, (name, _rows) in enumerate(sheets, start=1)
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f"<sheets>{workbook_sheets}</sheets>"
            "</workbook>",
        )
        relationships = "".join(
            f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
            for index in range(1, len(sheets) + 1)
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f"{relationships}</Relationships>",
        )
        for index, (_name, rows) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", xlsx_sheet_xml(rows))
    return buffer.getvalue()


def review_workbook_bytes(project: dict, extraction_rows: list[dict], statements: list[dict], conversion: dict, audit_logs: list[dict]) -> bytes:
    entries = conversion.get("entries") or []
    notes = conversion.get("draft_notes") or []
    ai_assistance = conversion.get("ai_assistance") or {}
    judgment_items = conversion.get("judgment_items") or []
    sheets = [
        (
            "01_원본_DART",
            [
                ["회사명", project.get("company_name", "")],
                ["기간", project.get("period", "")],
                [],
                ["계정명", "금액", "재무제표", "통화", "DART 계정ID", "변환후보", "제외사유"],
                *[
                    [
                        row.get("account_name", ""),
                        row.get("amount", 0),
                        row.get("statement_type", ""),
                        row.get("currency", ""),
                        row.get("dart_account_id", ""),
                        "Y" if row.get("conversion_candidate", True) else "N",
                        row.get("filter_reason", ""),
                    ]
                    for row in extraction_rows
                ],
            ],
        ),
        (
            "02_계정매핑",
            [
                ["원 계정", "표준계정", "내부 코드", "금액", "기간", "매핑 유형", "룰 요약"],
                *[
                    [
                        row.get("account_name", ""),
                        row.get("normalized_account", ""),
                        row.get("standard_code", ""),
                        row.get("amount", 0),
                        row.get("period", ""),
                        label_backend(row.get("mapping_type", "")),
                        row.get("rule_summary", ""),
                    ]
                    for row in statements
                ],
            ],
        ),
        (
            "03_조정분개",
            [
                ["원 계정", "내부 코드", "K-IFRS 계정", "표시 재무제표", "표시 라인", "금액", "조정액", "유형", "계산/근거"],
                *[
                    [
                        entry.get("source_account", ""),
                        entry.get("standard_code", ""),
                        entry.get("target_account", ""),
                        entry.get("statement_type", ""),
                        entry.get("statement_line_item", ""),
                        entry.get("amount", 0),
                        entry.get("adjustment", 0),
                        label_backend(entry.get("mapping_type", "")),
                        localize_export_text(entry.get("calculation") or entry.get("basis")),
                    ]
                    for entry in entries
                ],
            ],
        ),
        (
            "04_KIFRS_검토근거",
            [
                ["구분", "계정", "근거/메모"],
                *[["주석 초안", note.get("account", ""), localize_export_text(note.get("draft_note"))] for note in notes],
                *[
                    [
                        f"기준서 문단 ({para.get('standard_set', '')})",
                        item.get("account", ""),
                        f"{para.get('reference_code', '')} {para.get('paragraph_label', '')}: {para.get('content', '')}",
                    ]
                    for item in judgment_items
                    for para in item.get("standards_paragraphs", [])
                ],
                ["AI 판단 보조", "상태", label_backend(ai_assistance.get("status", "-"))],
                ["AI 판단 보조", "전체 메모", localize_export_text(ai_assistance.get("overall_note", ""))],
            ],
        ),
        (
            "05_감사로그",
            [
                ["시각", "사용자", "이벤트", "상세"],
                *[
                    [
                        row.get("created_at", ""),
                        row.get("actor", ""),
                        row.get("event_type", ""),
                        json.dumps(row.get("detail", row.get("detail_json", {})), ensure_ascii=False),
                    ]
                    for row in audit_logs
                ],
            ],
        ),
    ]
    return create_xlsx_workbook(sheets)
