from __future__ import annotations

import io
import json

from openpyxl import Workbook

from gtf_app.domain import label_backend, localize_export_text


def create_xlsx_workbook(sheets: list[tuple[str, list[list]]]) -> bytes:
    """(시트명, 행 목록) 목록으로 xlsx 파일 바이트를 만든다 (openpyxl)."""
    workbook = Workbook()
    workbook.remove(workbook.active)  # 기본 생성되는 빈 시트 제거
    for name, rows in sheets:
        sheet = workbook.create_sheet(title=name[:31])  # 엑셀 시트명은 31자 제한
        for row in rows:
            sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def transition_summary_rows(entries: list[dict]) -> list[list]:
    """전환조정 요약 시트 행: 구분(자산/부채/자본/손익)별 조정 집계와 순자산 영향.

    순자산 영향 = 자산·금융 조정 − 부채 조정 + 자본·손익 조정. 재분류(조정액 0)는 영향 없음.
    OCI 성격 조정(재평가잉여금·재측정요소)은 이익잉여금이 아닌 별도 자본항목 검토가 필요하다.
    """
    sections = {"A": ("자산 조정", 1), "F": ("금융상품 조정", 1), "L": ("부채 조정", -1), "E": ("자본 조정", 1), "R": ("손익 조정", 1)}
    rows: list[list] = [["구분", "건수", "조정액 합계", "순자산 영향(부호 반영)"]]
    net_effect = 0.0
    for prefix, (label, sign) in sections.items():
        matched = [e for e in entries if str(e.get("standard_code", ""))[:1] == prefix and e.get("adjustment")]
        total = sum(float(e.get("adjustment") or 0) for e in matched)
        net_effect += sign * total
        rows.append([label, len(matched), total, sign * total])
    rows += [
        ["순자산(자본총계) 영향 합계", "", "", net_effect],
        [],
        ["주의", "K-IFRS 제1101호 문단 10: 전환 조정은 원칙적으로 전환일의 이익잉여금(또는 적절한 다른 자본항목)으로 인식합니다."],
        ["주의", "재평가잉여금·확정급여 재측정요소 등 기타포괄손익 성격의 조정은 이익잉여금이 아닌 별도 자본항목입니다. 항목별 검토가 필요합니다."],
        ["주의", "재분류(조정액 0)와 전문가 검토 영역(복합금융상품·파생상품)의 평가 결과는 이 합계에 반영되어 있지 않습니다."],
    ]
    return rows


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
            # 전환일 자본 조정명세(K-IFRS 제1101호 문단 10): 조정을 재무제표 구분별로 집계해
            # 전환조정이 순자산(자본총계)에 미치는 영향을 요약한다. 코드 앞자리 = 구분.
            "05_전환조정요약",
            transition_summary_rows(entries),
        ),
        (
            "06_감사로그",
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
