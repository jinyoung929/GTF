from __future__ import annotations

import csv
import io
import re
import uuid
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

STANDARD_ACCOUNTS = {
    "cash": {
        "code": "A1000",
        "label": "현금및현금성자산",
        "ifrs": "Cash and cash equivalents",
        "type": "simple",
        "rule": "사용 제한 여부를 확인한 뒤 현금및현금성자산으로 단순 매핑합니다.",
    },
    "receivables": {
        "code": "A1100",
        "label": "매출채권",
        "ifrs": "Trade and other receivables",
        "type": "judgment",
        "rule": "IFRS 9 기준에 따라 매출채권 분류와 기대신용손실 충당금을 검토합니다.",
    },
    "inventory": {
        "code": "A1200",
        "label": "재고자산",
        "ifrs": "Inventories",
        "type": "simple",
        "rule": "IAS 2 재고자산으로 매핑하고 원가와 순실현가능가치 비교를 검토합니다.",
    },
    "lease": {
        "code": "A2100",
        "label": "리스",
        "ifrs": "Right-of-use asset and lease liability",
        "type": "judgment",
        "rule": "IFRS 16 측정을 위해 리스기간, 지급액, 선택권, 할인율을 추가 확인합니다.",
    },
    "development": {
        "code": "A3100",
        "label": "개발비",
        "ifrs": "Intangible assets or R&D expense",
        "type": "judgment",
        "rule": "IAS 38 개발단계 자산화 요건 충족 여부를 검토합니다.",
    },
    "revenue": {
        "code": "R1000",
        "label": "수익",
        "ifrs": "Revenue from contracts with customers",
        "type": "judgment",
        "rule": "IFRS 15 기준에 따라 수행의무와 수익인식 시점을 확인합니다.",
    },
    "financial_instrument": {
        "code": "F1000",
        "label": "금융상품",
        "ifrs": "Financial assets/liabilities",
        "type": "judgment",
        "rule": "IFRS 9 기준에 따라 사업모형과 계약상 현금흐름 특성을 검토합니다.",
    },
    "provision": {
        "code": "L2200",
        "label": "충당부채",
        "ifrs": "Provisions and contingencies",
        "type": "judgment",
        "rule": "IAS 37 기준에 따라 현재의무, 유출가능성, 신뢰성 있는 추정 여부를 검토합니다.",
    },
    "other": {
        "code": "X9999",
        "label": "미분류 계정",
        "ifrs": "Review required",
        "type": "judgment",
        "rule": "자동 매핑 신뢰도가 낮아 담당자 분류 검토가 필요합니다.",
    },
}


FINANCIAL_STATEMENT_TEMPLATES = [
    {
        "id": "ifrs_bs_cash",
        "standard_set": "IFRS",
        "statement_type": "재무상태표",
        "section": "유동자산",
        "line_item": "현금및현금성자산",
        "account_key": "cash",
        "display_order": 10,
        "basis": "IAS 7 표시 목적의 현금및현금성자산 라인입니다.",
    },
    {
        "id": "ifrs_bs_receivables",
        "standard_set": "IFRS",
        "statement_type": "재무상태표",
        "section": "유동자산",
        "line_item": "매출채권 및 기타채권",
        "account_key": "receivables",
        "display_order": 20,
        "basis": "IFRS 9 기대신용손실 검토 후 채권 라인에 표시합니다.",
    },
    {
        "id": "ifrs_bs_inventory",
        "standard_set": "IFRS",
        "statement_type": "재무상태표",
        "section": "유동자산",
        "line_item": "재고자산",
        "account_key": "inventory",
        "display_order": 30,
        "basis": "IAS 2에 따라 원가와 순실현가능가치를 검토한 뒤 표시합니다.",
    },
    {
        "id": "ifrs_bs_lease_asset",
        "standard_set": "IFRS",
        "statement_type": "재무상태표",
        "section": "비유동자산/부채",
        "line_item": "사용권자산 및 리스부채",
        "account_key": "lease",
        "display_order": 90,
        "basis": "IFRS 16에 따라 사용권자산과 리스부채 표시를 검토합니다.",
    },
    {
        "id": "ifrs_bs_development",
        "standard_set": "IFRS",
        "statement_type": "재무상태표 또는 손익계산서",
        "section": "무형자산/비용",
        "line_item": "무형자산 또는 연구개발비",
        "account_key": "development",
        "display_order": 100,
        "basis": "IAS 38 개발단계 자산화 요건에 따라 표시 라인이 달라집니다.",
    },
    {
        "id": "ifrs_bs_financial_instrument",
        "standard_set": "IFRS",
        "statement_type": "재무상태표",
        "section": "금융자산/금융부채",
        "line_item": "금융자산 또는 금융부채",
        "account_key": "financial_instrument",
        "display_order": 110,
        "basis": "IFRS 9 분류 결과에 따라 금융자산 또는 금융부채로 표시합니다.",
    },
    {
        "id": "ifrs_bs_provision",
        "standard_set": "IFRS",
        "statement_type": "재무상태표",
        "section": "부채",
        "line_item": "충당부채",
        "account_key": "provision",
        "display_order": 120,
        "basis": "IAS 37 인식요건을 충족하면 충당부채로 표시합니다.",
    },
    {
        "id": "ifrs_pl_revenue",
        "standard_set": "IFRS",
        "statement_type": "손익계산서",
        "section": "수익",
        "line_item": "고객과의 계약에서 생기는 수익",
        "account_key": "revenue",
        "display_order": 10,
        "basis": "IFRS 15 수행의무와 인식시점 검토 후 수익 라인에 표시합니다.",
    },
    {
        "id": "ifrs_review_required",
        "standard_set": "IFRS",
        "statement_type": "검토 필요",
        "section": "미분류",
        "line_item": "검토자 분류 필요",
        "account_key": "other",
        "display_order": 999,
        "basis": "내부 표준계정 매핑 신뢰도가 낮아 사람이 표시 라인을 확정합니다.",
    },
]


CHECKLISTS = {
    "lease": [
        {"key": "lease_term_months", "label": "리스기간(개월)", "type": "number", "required": True},
        {"key": "monthly_payment", "label": "월 리스료", "type": "number", "required": True},
        {"key": "discount_rate", "label": "증분차입이자율(%)", "type": "number", "required": True},
        {"key": "renewal_option", "label": "연장선택권 행사가 상당히 확실한가?", "type": "boolean", "required": False},
    ],
    "development": [
        {"key": "technical_feasibility", "label": "기술적 실현가능성이 입증되었는가?", "type": "boolean", "required": True},
        {"key": "intention_to_complete", "label": "완성 의도와 능력이 있는가?", "type": "boolean", "required": True},
        {"key": "probable_future_benefits", "label": "미래경제적효익이 개연적인가?", "type": "boolean", "required": True},
        {"key": "reliable_measurement", "label": "원가를 신뢰성 있게 측정할 수 있는가?", "type": "boolean", "required": True},
    ],
    "revenue": [
        {"key": "contract_type", "label": "계약 유형", "type": "text", "required": True},
        {"key": "performance_obligations", "label": "수행의무", "type": "text", "required": True},
        {"key": "recognition_timing", "label": "한 시점 또는 기간에 걸친 인식", "type": "text", "required": True},
        {"key": "variable_consideration", "label": "변동대가가 있는가?", "type": "boolean", "required": False},
    ],
    "financial_instrument": [
        {"key": "instrument_terms", "label": "주요 계약조건", "type": "text", "required": True},
        {"key": "business_model", "label": "보유 사업모형", "type": "text", "required": True},
        {"key": "sppi_passed", "label": "원금과 이자 지급만으로 구성된 현금흐름(SPPI) 요건을 충족하는가?", "type": "boolean", "required": True},
    ],
    "provision": [
        {"key": "present_obligation", "label": "현재의무가 존재하는가?", "type": "boolean", "required": True},
        {"key": "probable_outflow", "label": "자원 유출 가능성이 높은가?", "type": "boolean", "required": True},
        {"key": "reliable_estimate", "label": "금액을 신뢰성 있게 추정할 수 있는가?", "type": "boolean", "required": True},
    ],
    "receivables": [
        {"key": "credit_risk_method", "label": "기대신용손실 산정 방식", "type": "text", "required": True},
        {"key": "aging_available", "label": "연령분석표가 있는가?", "type": "boolean", "required": True},
    ],
    "other": [
        {"key": "management_memo", "label": "경영진 분류 메모", "type": "text", "required": True},
    ],
}

def normalize_account_name(name: str) -> str:
    text = re.sub(r"\s+", " ", name.strip().lower())
    replacements = {
        "현금및현금성자산": "cash",
        "현금": "cash",
        "cash": "cash",
        "매출채권": "receivables",
        "대손충당금": "receivables",
        "미수금": "receivables",
        "미수수익": "receivables",
        "계약자산": "receivables",
        "trade receivable": "receivables",
        "금융자산": "financial_instrument",
        "금융부채": "financial_instrument",
        "금융상품": "financial_instrument",
        "파생상품": "financial_instrument",
        "전환사채": "financial_instrument",
        "장기차입금": "financial_instrument",
        "단기차입금": "financial_instrument",
        "차입금": "financial_instrument",
        "사채상환할증금": "financial_instrument",
        "전환권조정": "financial_instrument",
        "재고자산": "inventory",
        "상품": "inventory",
        "제품": "inventory",
        "원재료": "inventory",
        "inventory": "inventory",
        "리스": "lease",
        "사용권자산": "lease",
        "리스부채": "lease",
        "lease": "lease",
        "개발비": "development",
        "무형자산": "development",
        "development": "development",
        "매출액": "revenue",
        "매출": "revenue",
        "영업수익": "revenue",
        "수익": "revenue",
        "revenue": "revenue",
        "충당부채": "provision",
        "provision": "provision",
    }
    compact = text.replace(" ", "")
    for needle, account_key in replacements.items():
        if needle in compact or needle in text:
            return account_key
    return "other"


def parse_statement_rows(payload: dict) -> list[dict]:
    rows = []
    if isinstance(payload.get("rows"), list):
        rows = payload["rows"]
    elif payload.get("csv_text"):
        reader = csv.DictReader(io.StringIO(payload["csv_text"]))
        rows = list(reader)

    parsed = []
    for raw in rows:
        name = str(raw.get("account_name") or raw.get("account") or raw.get("계정명") or "").strip()
        if not name:
            continue
        amount = parse_amount(raw.get("amount") or raw.get("금액") or 0)
        parsed.append({"account_name": name, "amount": amount})
    return parsed


def parse_amount(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "0").strip()
    is_negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if cleaned in {"", "-", ".", "-."}:
        return 0.0
    amount = float(cleaned)
    return -abs(amount) if is_negative else amount


def looks_numeric(value) -> bool:
    if isinstance(value, (int, float)):
        return True
    text = str(value or "").strip()
    if not text:
        return False
    return bool(re.fullmatch(r"\(?-?[\d,]+(?:\.\d+)?\)?", text.replace(" ", "")))

def build_statement_record(project_period: str, row: dict) -> dict:
    account_key = normalize_account_name(row["account_name"])
    standard = STANDARD_ACCOUNTS[account_key]
    checklist = CHECKLISTS.get(account_key, []) if standard["type"] == "judgment" else []
    return {
        "id": str(uuid.uuid4()),
        "account_name": row["account_name"],
        "normalized_account": standard["label"],
        "standard_code": standard["code"],
        "amount": row["amount"],
        "period": project_period,
        "mapping_type": standard["type"],
        "rule_summary": standard["rule"],
        "checklist": checklist,
        "ifrs_account": standard["ifrs"],
    }


def validate_statement_records(project: dict, statements: list[sqlite3.Row]) -> dict:
    total = sum(float(row["amount"]) for row in statements)
    judgment_count = sum(1 for row in statements if row["mapping_type"] == "judgment")
    simple_count = sum(1 for row in statements if row["mapping_type"] == "simple")
    issues = []
    warnings = []
    checks = []

    def add_check(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    def account_text(row) -> str:
        return re.sub(r"\s+", "", str(row["account_name"] or "")).lower()

    def amount(row) -> float:
        return float(row["amount"] or 0)

    if not statements:
        issues.append("업로드되거나 매핑된 계정 행이 없습니다.")
        add_check("계정 행", "error", "검증할 계정 데이터가 없습니다.")
        return {
            "row_count": 0,
            "total_amount": 0,
            "judgment_count": 0,
            "simple_count": 0,
            "issues": issues,
            "warnings": warnings,
            "checks": checks,
            "status": "failed",
        }

    add_check("계정 행", "pass", f"{len(statements)}개 계정 행을 확인했습니다.")

    zero_rows = [row["account_name"] for row in statements if abs(float(row["amount"])) < 1]
    if zero_rows:
        warnings.append(f"금액이 0인 계정이 있습니다: {', '.join(zero_rows[:5])}")
        add_check("금액 누락", "warning", f"{len(zero_rows)}개 계정의 금액이 0입니다.")
    else:
        add_check("금액 누락", "pass", "0 또는 빈 금액으로 보이는 계정이 없습니다.")

    normalized_names = [row["normalized_account"] for row in statements]
    duplicate_names = sorted({name for name in normalized_names if normalized_names.count(name) > 1})
    if duplicate_names:
        warnings.append(f"동일 표준계정으로 중복 매핑된 항목이 있습니다: {', '.join(duplicate_names[:5])}")
        add_check("중복 매핑", "warning", f"{len(duplicate_names)}개 표준계정에 복수 행이 매핑되었습니다.")
    else:
        add_check("중복 매핑", "pass", "동일 표준계정 중복 매핑이 없습니다.")

    original_names = [str(row["account_name"]).strip() for row in statements]
    duplicate_originals = sorted({name for name in original_names if original_names.count(name) > 1})
    if duplicate_originals:
        warnings.append(f"동일 계정명이 여러 번 추출되었습니다: {', '.join(duplicate_originals[:5])}")
        add_check("중복 계정명", "warning", f"{len(duplicate_originals)}개 계정명이 반복됩니다. 주석/세부내역 중복 추출 여부를 확인하세요.")
    else:
        add_check("중복 계정명", "pass", "동일 계정명 반복 추출이 없습니다.")

    unmapped = [row["account_name"] for row in statements if row["standard_code"] == "X9999"]
    if unmapped:
        issues.append(f"미분류 계정이 있습니다: {', '.join(unmapped[:5])}")
        add_check("미분류 계정", "error", f"{len(unmapped)}개 계정은 담당자 분류가 필요합니다.")
    else:
        add_check("미분류 계정", "pass", "모든 계정이 내부 표준코드에 연결되었습니다.")

    mismatched_periods = sorted({row["period"] for row in statements if row["period"] != project["period"]})
    if mismatched_periods:
        warnings.append(f"프로젝트 기간과 다른 계정 기간이 있습니다: {', '.join(mismatched_periods)}")
        add_check("기간 일치", "warning", "일부 계정 기간이 프로젝트 기간과 다릅니다.")
    else:
        add_check("기간 일치", "pass", f"모든 계정 기간이 {project['period']}로 일치합니다.")

    if abs(total) < 1:
        warnings.append("합계가 0에 가깝습니다. 차변/대변 부호가 유지되었는지 확인하세요.")
        add_check("합계 검토", "warning", "전체 합계가 0에 가깝습니다.")
    else:
        largest = max(statements, key=lambda row: abs(float(row["amount"])))
        ratio = abs(float(largest["amount"])) / abs(total) if total else 0
        detail = f"합계 {total:,.0f}, 최대 계정 {largest['account_name']} {float(largest['amount']):,.0f}"
        if ratio > 0.8 and len(statements) > 1:
            warnings.append(f"단일 계정이 전체 합계의 {ratio:.0%}를 차지합니다: {largest['account_name']}")
            add_check("큰 금액 비중", "warning", detail)
        else:
            add_check("큰 금액 비중", "pass", detail)

    max_abs_amount = max(abs(amount(row)) for row in statements)
    if max_abs_amount < 10_000:
        warnings.append("전체 금액 규모가 작습니다. 원/천원/백만원 단위가 누락되었는지 확인하세요.")
        add_check("단위 검토", "warning", f"최대 금액이 {max_abs_amount:,.0f}입니다. 표시 단위를 확인하세요.")
    elif max_abs_amount > 1_000_000_000_000_000:
        warnings.append("비정상적으로 큰 금액이 있습니다. OCR 숫자 인식 오류 가능성을 확인하세요.")
        add_check("단위 검토", "warning", f"최대 금액이 {max_abs_amount:,.0f}입니다. 숫자 자릿수를 확인하세요.")
    else:
        add_check("단위 검토", "pass", f"최대 금액 {max_abs_amount:,.0f} 기준으로 극단적 단위 오류는 보이지 않습니다.")

    negative_rows = [
        row["account_name"]
        for row in statements
        if amount(row) < 0 and not any(token in account_text(row) for token in ("충당금", "상각", "평가손실", "차감", "환입", "조정"))
    ]
    if negative_rows:
        warnings.append(f"음수 금액 계정이 있습니다: {', '.join(negative_rows[:5])}")
        add_check("음수 금액", "warning", f"{len(negative_rows)}개 계정의 음수 금액이 정상 표시인지 확인하세요.")
    else:
        add_check("음수 금액", "pass", "설명이 필요한 음수 금액 계정은 보이지 않습니다.")

    asset_tokens = ("현금", "매출채권", "미수", "재고", "상품", "제품", "원재료", "사용권자산", "개발비", "무형자산", "금융자산", "자산")
    liability_tokens = ("매입채무", "미지급", "차입", "사채", "리스부채", "충당부채", "금융부채", "부채")
    equity_tokens = ("자본금", "자본잉여금", "기타자본", "이익잉여금", "결손금", "자본")
    assets = sum(amount(row) for row in statements if any(token in account_text(row) for token in asset_tokens) and not any(token in account_text(row) for token in liability_tokens))
    liabilities = sum(amount(row) for row in statements if any(token in account_text(row) for token in liability_tokens))
    equity = sum(amount(row) for row in statements if any(token in account_text(row) for token in equity_tokens))
    balance_basis = max(abs(assets), abs(liabilities + equity), 1)
    balance_gap = assets - liabilities - equity
    if equity and assets and liabilities:
        if abs(balance_gap) / balance_basis > 0.05:
            warnings.append(f"재무상태표 균형이 맞지 않을 수 있습니다. 자산 {assets:,.0f}, 부채+자본 {(liabilities + equity):,.0f}")
            add_check("자산=부채+자본", "warning", f"차이 {balance_gap:,.0f}. OCR 중복/누락 또는 표시 단위를 확인하세요.")
        else:
            add_check("자산=부채+자본", "pass", f"자산 {assets:,.0f}, 부채+자본 {(liabilities + equity):,.0f}로 큰 차이가 없습니다.")
    else:
        warnings.append("자산=부채+자본 검증에 필요한 자산/부채/자본 항목이 충분하지 않습니다.")
        add_check("자산=부채+자본", "warning", "자산, 부채, 자본 항목이 모두 있어야 균형 검증이 가능합니다.")

    has_revenue = any(any(token in account_text(row) for token in ("매출", "영업수익", "수익")) for row in statements)
    has_expense = any(any(token in account_text(row) for token in ("매출원가", "판매비", "관리비", "영업비용", "비용", "원가")) for row in statements)
    has_profit = any(any(token in account_text(row) for token in ("영업이익", "당기순이익", "손실", "이익")) for row in statements)
    if has_revenue and (has_expense or has_profit):
        add_check("손익계산서 필수 항목", "pass", "수익 항목과 비용 또는 손익 항목이 함께 확인됩니다.")
    elif has_revenue:
        warnings.append("수익 항목은 있으나 비용/손익 항목이 부족합니다. 손익계산서 추출 범위를 확인하세요.")
        add_check("손익계산서 필수 항목", "warning", "수익은 있으나 비용 또는 이익 항목이 부족합니다.")
    else:
        warnings.append("손익계산서 수익 항목이 확인되지 않습니다. 손익계산서가 누락되었는지 확인하세요.")
        add_check("손익계산서 필수 항목", "warning", "매출/수익 항목이 확인되지 않았습니다.")

    status = "failed" if issues else "warning" if warnings else "passed"
    return {
        "row_count": len(statements),
        "total_amount": total,
        "judgment_count": judgment_count,
        "simple_count": simple_count,
        "issues": issues,
        "warnings": warnings,
        "checks": checks,
        "status": status,
    }

def generate_conversion(project: dict, statements: list[dict], responses: dict, templates: dict | None = None) -> dict:
    templates = templates or {}
    entries = []
    notes = []
    judgment_items = []

    for item in statements:
        account_key = normalize_account_name(item["account_name"])
        standard = STANDARD_ACCOUNTS[account_key]
        checklist_response = responses.get(item["id"], {})
        entry = {
            "source_account": item["account_name"],
            "standard_code": item["standard_code"],
            "target_account": standard["ifrs"],
            "amount": item["amount"],
            "adjustment": 0,
            "mapping_type": item["mapping_type"],
            "basis": item["rule_summary"],
        }
        template = templates.get(account_key)
        if template:
            entry["statement_type"] = template["statement_type"]
            entry["statement_section"] = template["section"]
            entry["statement_line_item"] = template["line_item"]
            entry["presentation_order"] = template["display_order"]
            entry["presentation_basis"] = template["basis"]

        if account_key == "lease":
            months = float(checklist_response.get("lease_term_months") or 0)
            payment = float(checklist_response.get("monthly_payment") or 0)
            discount_rate = float(checklist_response.get("discount_rate") or 0) / 100 / 12
            if months > 0 and payment > 0:
                if discount_rate > 0:
                    pv = payment * (1 - (1 + discount_rate) ** (-months)) / discount_rate
                else:
                    pv = payment * months
                entry["adjustment"] = round(pv - float(item["amount"]), 2)
                entry["calculation"] = "리스료 현재가치에서 K-GAAP 장부금액을 차감해 조정액을 산출했습니다."
        elif account_key == "development":
            criteria = ["technical_feasibility", "intention_to_complete", "probable_future_benefits", "reliable_measurement"]
            qualifies = all(checklist_response.get(key) is True for key in criteria)
            entry["target_account"] = "Intangible assets" if qualifies else "Research and development expense"
            entry["calculation"] = "IAS 38 개발단계 자산화 요건 충족 여부를 검토했습니다."
        elif account_key == "revenue":
            timing = checklist_response.get("recognition_timing") or "추가 검토 필요"
            entry["calculation"] = f"수익인식 시점을 '{timing}'로 문서화했습니다."
        elif account_key in {"financial_instrument", "receivables"}:
            entry["calculation"] = "IFRS 9 분류 및 기대신용손실 검토가 필요합니다."
        elif account_key == "provision":
            recognized = all(
                checklist_response.get(key) is True
                for key in ["present_obligation", "probable_outflow", "reliable_estimate"]
            )
            entry["calculation"] = "충당부채 인식요건을 충족했습니다." if recognized else "충당부채 인식요건이 완전하지 않아 공시 또는 추가 검토가 필요합니다."

        if item["mapping_type"] == "judgment":
            judgment_items.append(
                {
                    "statement_id": item["id"],
                    "account": item["account_name"],
                    "checklist_response": checklist_response,
                    "basis": item["rule_summary"],
                }
            )
            notes.append(
                {
                    "account": item["account_name"],
                    "draft_note": f"{standard['ifrs']} 항목은 검토자 확인이 필요합니다. 표시 양식: {entry.get('statement_line_item', '검토 필요')}. 근거: {item['rule_summary']}",
                }
            )

        entries.append(entry)

    return {
        "project": {
            "id": project["id"],
            "company_name": project["company_name"],
            "period": project["period"],
            "source_standard": project["source_standard"],
            "target_standard": project["target_standard"],
        },
        "statement_template": "IFRS 내부 재무제표 양식 DB",
        "entries": entries,
        "judgment_items": judgment_items,
        "draft_notes": notes,
        "review_status": "사람 검토 필요",
        "generated_at": utc_now(),
    }


def conversion_adjustments_csv(conversion: dict) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["원 계정", "내부 코드", "IFRS 계정", "표시 재무제표", "표시 라인", "금액", "조정액", "유형", "계산/근거"])
    for entry in conversion.get("entries", []):
        writer.writerow(
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
        )
    return buffer.getvalue()


def label_backend(value: str) -> str:
    labels = {
        "simple": "단순 매핑",
        "judgment": "판단 필요",
        "approved": "승인 완료",
        "changes_requested": "수정 요청",
        "draft_generated": "초안 생성",
        "connected": "연결 완료",
        "not_configured": "키 미설정",
        "failed": "실패",
        "skipped": "건너뜀",
    }
    return labels.get(value, value or "-")


def localize_export_text(value) -> str:
    return str(value or "-").replace("review required", "추가 검토 필요").replace("Human review required", "사람 검토 필요")

def conversion_basis_report(conversion: dict) -> str:
    project = conversion.get("project", {})
    entries = conversion.get("entries", [])
    judgment_items = conversion.get("judgment_items", [])
    ai_assistance = conversion.get("ai_assistance") or {}
    notes = conversion.get("draft_notes", [])
    lines = [
        "GTF 회계기준 변환 검토 리포트",
        "=" * 42,
        f"회사명: {project.get('company_name', '-')}",
        f"기간: {project.get('period', '-')}",
        f"변환 기준: {project.get('source_standard', 'K-GAAP')} -> {project.get('target_standard', 'IFRS')}",
        f"표시 양식: {conversion.get('statement_template', '-')}",
        f"검토 상태: {conversion.get('review_status', '-')}",
        f"생성 시각: {conversion.get('generated_at', '-')}",
        "",
        "1. 요약",
        "-" * 42,
        f"- 조정분개 후보: {len(entries):,}건",
        f"- 판단 필요 항목: {len(judgment_items):,}건",
        f"- OpenAI 판단 보조 상태: {label_backend(ai_assistance.get('status', '-'))}",
        "",
        "2. 조정분개 후보",
        "-" * 42,
        "No | K-GAAP 계정 | 내부코드 | IFRS 표시 | 금액 | 조정액 | 근거",
    ]
    if not entries:
        lines.append("- 생성된 조정분개 후보가 없습니다.")
    for index, entry in enumerate(entries, start=1):
        display = f"{entry.get('statement_type', '-')} / {entry.get('statement_line_item', '-')}"
        basis = localize_export_text(entry.get("calculation") or entry.get("basis"))
        lines.append(
            " | ".join(
                [
                    str(index),
                    str(entry.get("source_account", "-")),
                    str(entry.get("standard_code", "-")),
                    display,
                    f"{float(entry.get('amount') or 0):,.0f}",
                    f"{float(entry.get('adjustment') or 0):,.0f}",
                    basis,
                ]
            )
        )
    lines.append("")
    lines.append("3. 판단 필요 항목")
    lines.append("-" * 42)
    if not judgment_items:
        lines.append("- 없음")
    for item in judgment_items:
        lines.append(f"- {item.get('account', '-')}: {localize_export_text(item.get('basis'))}")
    lines.append("")
    lines.append("4. OpenAI 판단 보조")
    lines.append("-" * 42)
    lines.append(f"상태: {label_backend(ai_assistance.get('status', '-'))}")
    lines.append(f"모델: {ai_assistance.get('model', '-')}")
    if ai_assistance.get("overall_note"):
        lines.append(f"전체 메모: {localize_export_text(ai_assistance.get('overall_note'))}")
    ai_issues = ai_assistance.get("issues") or []
    if ai_issues:
        lines.append("실패/주의 사항:")
        for issue in ai_issues:
            lines.append(f"  - {localize_export_text(issue)}")
    ai_items = ai_assistance.get("items") or []
    if not ai_items:
        lines.append("- 없음")
    for item in ai_items:
        questions = ", ".join(str(question) for question in item.get("additional_questions", []) if str(question).strip())
        lines.extend(
            [
                f"- {item.get('account', '-')}: {item.get('risk_level', '-')}",
                f"  분류 힌트: {localize_export_text(item.get('classification_hint'))}",
                f"  추가 질문: {questions or '-'}",
                f"  검토 메모: {localize_export_text(item.get('review_note'))}",
                f"  근거 요약: {localize_export_text(item.get('basis_summary'))}",
            ]
        )
    lines.append("")
    lines.append("5. 주석 초안")
    lines.append("-" * 42)
    if not notes:
        lines.append("- 없음")
    for note in notes:
        lines.append(f"- {note.get('account', '-')}: {localize_export_text(note.get('draft_note'))}")
    lines.extend(
        [
            "",
            "6. 최종 검토 체크포인트",
            "-" * 42,
            "- 계약 조건, 할인율, 자산화 요건, 수익인식 방식 등 입력값의 근거 문서를 확인하세요.",
            "- 본 리포트는 변환 초안과 감사추적 보조 자료이며 최종 회계정책 판단은 회사 담당자 또는 회계 전문가가 수행해야 합니다.",
            "- 감사인 검토 시 입력값, 적용 룰, 체크리스트 응답, 수정 이력을 함께 제시하세요.",
        ]
    )
    return "\n".join(lines) + "\n"
