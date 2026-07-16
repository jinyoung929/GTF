from __future__ import annotations

import csv
import io
import re
import uuid
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── 계산 계약(contract) ─────────────────────────────────────────────────────
# 기준정보 데이터(계정·체크리스트·별칭·문단)는 전부 DB에서 온다. 하지만 변환 계산기는
# 특정 account_key로 분기하고(=함수 이름 같은 개념 식별자) 특정 체크리스트 item_key를 읽는다.
# 이 식별자들은 데이터가 아니라 로직이므로 코드에 남으며, 서버 시작 시 verify_reference_contract가
# "계산기가 요구하는 이 키들이 실제로 DB 기준정보에 존재하는가"를 검사해 SQL 시드 편집 실수를
# 조용한 오류(예: 조정액이 0으로 나옴)가 아니라 즉시 실패로 드러낸다.
CALC_ACCOUNT_KEYS = frozenset({
    "lease", "development", "revenue", "financial_instrument", "receivables",
    "provision", "retirement_benefit", "ppe", "investment_property",
    "deferred_tax_asset", "government_grant", "borrowing_cost",
    "goodwill", "preferred_shares", "held_for_sale",
    "compound_instrument", "derivative",
})
CALC_CHECKLIST_KEYS = {
    "lease": {"lease_term_months", "monthly_payment", "discount_rate"},
    "development": {"technical_feasibility", "intention_to_complete", "probable_future_benefits", "reliable_measurement"},
    "revenue": {"recognition_timing"},
    "provision": {"present_obligation", "probable_outflow", "reliable_estimate"},
    "retirement_benefit": {"dbo_amount", "plan_assets"},
    "ppe": {"measurement_model", "fair_value", "recoverable_amount"},
    "investment_property": {"measurement_model", "fair_value"},
    "deferred_tax_asset": {"temporary_difference", "tax_rate", "realizable"},
    "government_grant": {"grant_relation", "presentation_method"},
    "borrowing_cost": {"qualifying_asset", "expenditure", "capitalization_rate", "capitalization_months"},
    "goodwill": {"amortization_expense", "impairment_indicator", "recoverable_amount"},
    "preferred_shares": {"mandatory_redemption"},
    "held_for_sale": {"plan_committed", "sale_probable_12m", "fair_value_less_costs"},
    "compound_instrument": {"cash_settlement_possible"},
    "derivative": {"hedge_designated"},
}

# 선택가능 회계정책(K-IFRS가 복수 정책을 허용하는 곳)과 그 선택지.
# 계산기가 결정론이라 같은 재무제표를 선택지별로 계산해 영향을 비교 제시할 수 있다.
POLICY_SCENARIOS = {
    "ppe": ("measurement_model", ["원가모형", "재평가모형"]),
    "investment_property": ("measurement_model", ["원가모형", "공정가치모형"]),
    "government_grant": ("presentation_method", ["자산차감법", "이연수익법"]),
}


class ReferenceData:
    """DB에서 로드한 기준정보 묶음. domain 순수 함수에 주입되어 코드가 DB를 직접 모르게 한다.

    accounts   : {account_key: {code, label, ifrs, type, rule}}
    aliases    : {별칭: account_key}  — 매칭 우선순위(긴 별칭 먼저) 순서 유지
    checklists : {account_key: [{key, label, type, required}]}
    templates  : {account_key: {statement_type, section, line_item, basis, display_order}}
    paragraphs : {account_key: [{standard_set, reference_code, paragraph_label, title, content, ...}]}
    """

    __slots__ = ("accounts", "aliases", "checklists", "templates", "paragraphs")

    def __init__(self, accounts=None, aliases=None, checklists=None, templates=None, paragraphs=None):
        self.accounts = accounts or {}
        self.aliases = aliases or {}
        self.checklists = checklists or {}
        self.templates = templates or {}
        self.paragraphs = paragraphs or {}


def verify_reference_contract(reference: "ReferenceData") -> list[str]:
    """계산기가 요구하는 계정키·체크리스트 키가 DB 기준정보에 모두 있는지 검사.

    누락이 있으면 오류 메시지 목록을 반환한다(호출부에서 서버 시작을 실패시킨다).
    """
    errors: list[str] = []
    for account_key in sorted(CALC_ACCOUNT_KEYS):
        if account_key not in reference.accounts:
            errors.append(f"계산 대상 계정 '{account_key}'가 standard_accounts에 없습니다.")
    for account_key, required_keys in CALC_CHECKLIST_KEYS.items():
        present = {item["key"] for item in reference.checklists.get(account_key, [])}
        missing = required_keys - present
        if missing:
            errors.append(
                f"'{account_key}' 체크리스트에 계산기가 요구하는 항목이 없습니다: {', '.join(sorted(missing))}"
            )
    return errors

# 표시 순서는 개별 display_order를 손으로 매기지 않고 계정코드에서 도출한다.
# 코드 앞자리가 재무제표 구분(A 자산 → 부채 L → 자본 E → 손익 R), 뒷자리 숫자가
# 구분 내 표시 순서를 담고 있으므로, 계정을 추가할 때 적절한 코드만 부여하면 순서가
# 자동으로 결정된다. F(금융상품)는 재무상태표상 자산·부채 사이에 표시한다.
SECTION_ORDER = {"A": 1, "F": 2, "L": 3, "E": 4, "R": 5, "X": 9}


def account_presentation_order(code: str) -> int:
    prefix = (code or "")[:1]
    try:
        number = int((code or "")[1:])
    except ValueError:
        number = 9999
    return SECTION_ORDER.get(prefix, 8) * 100000 + number


def account_key_for_statement(item: dict, reference: "ReferenceData") -> str:
    """계정 행이 확정한 표준코드에서 계정키를 복원한다.

    담당자가 AI 제안을 승인해 재분류한 계정(예: 임차보증금 → F1000)은 계정명 키워드로는
    다시 찾을 수 없으므로, 저장된 standard_code를 우선하고 없을 때만 계정명 정규화로 보완한다.
    """
    code_to_key = {account["code"]: key for key, account in reference.accounts.items()}
    return code_to_key.get(str(item.get("standard_code") or "")) or normalize_account_name(item["account_name"], reference.aliases)


def alias_match_priority(alias: str) -> int:
    """부분 문자열 매칭 우선순위. 긴 별칭이 짧은 별칭보다 먼저 검사되도록 길이를 쓴다."""
    return len(alias or "")


def normalize_account_name(name: str, aliases: dict) -> str:
    """계정명을 내부 표준계정 키로 정규화한다.

    aliases(별칭 → 계정키)는 DB에서 로드해 주입받는다(코드에 하드코딩된 사전 없음).
    긴 별칭부터 검사해 '금융상품 ⊃ 상품', '퇴직급여충당부채 ⊃ 충당부채' 같은 부분 문자열
    충돌을 정확히 해결한다. domain.py가 DB를 직접 모르도록 맵을 인자로 주입받는다(순수 함수).
    """
    text = re.sub(r"\s+", " ", name.strip().lower())
    compact = text.replace(" ", "")
    for needle in sorted(aliases, key=alias_match_priority, reverse=True):
        if needle in compact or needle in text:
            return aliases[needle]
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

def build_statement_record(project_period: str, row: dict, reference: "ReferenceData") -> dict:
    account_key = normalize_account_name(row["account_name"], reference.aliases)
    mapping_source = "rule_based"
    ai_suggestion = row.get("ai_suggestion") or {}
    suggested_key = ai_suggestion.get("account_key")
    if account_key == "other" and suggested_key in reference.accounts and suggested_key != "other":
        # 키워드 매핑 실패 계정에 대한 AI 1차 분류 제안. 추출 결과를 담당자가
        # 확인하고 반영하는 시점에 적용되며, 확정 권한은 사람에게 있다.
        account_key = suggested_key
        mapping_source = "ai_suggested_human_accepted"
    standard = reference.accounts[account_key]
    checklist = reference.checklists.get(account_key, []) if standard["type"] == "judgment" else []
    rule_summary = standard["rule"]
    if mapping_source == "ai_suggested_human_accepted":
        rationale = str(ai_suggestion.get("rationale") or "").strip()
        rule_summary = (
            f"[AI 1차 분류 제안 → 반영 시 담당자 확정] {rationale + ' / ' if rationale else ''}{standard['rule']}"
        )
    return {
        "id": str(uuid.uuid4()),
        "account_name": row["account_name"],
        "normalized_account": standard["label"],
        "standard_code": standard["code"],
        "amount": row["amount"],
        "period": project_period,
        "mapping_type": standard["type"],
        "rule_summary": rule_summary,
        "checklist": checklist,
        "ifrs_account": standard["ifrs"],
        "mapping_source": mapping_source,
        "ai_suggestion": ai_suggestion if mapping_source == "ai_suggested_human_accepted" else None,
    }


def validate_statement_records(project: dict, statements: list[dict]) -> dict:
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

def generate_conversion(
    project: dict,
    statements: list[dict],
    responses: dict,
    reference: "ReferenceData",
) -> dict:
    templates = reference.templates
    standards_map = reference.paragraphs
    entries = []
    notes = []
    judgment_items = []

    for item in statements:
        account_key = account_key_for_statement(item, reference)
        standard = reference.accounts[account_key]
        checklist_response = responses.get(item["id"], {})
        paired_entry = None  # 리스처럼 한 판단이 분개 두 줄(차/대)을 만드는 경우
        entry = {
            "source_account": item["account_name"],
            "standard_code": item["standard_code"],
            "target_account": standard["ifrs"],
            "amount": item["amount"],
            "adjustment": 0,
            "mapping_type": item["mapping_type"],
            "basis": item["rule_summary"],
            # 표시 순서는 계정코드에서 도출한다 (A 자산 → F 금융상품 → L 부채 → E 자본 → R 손익).
            "presentation_order": account_presentation_order(item["standard_code"]),
        }
        template = templates.get(account_key)
        if template:
            entry["statement_type"] = template["statement_type"]
            entry["statement_section"] = template["section"]
            entry["statement_line_item"] = template["line_item"]
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
                entry["calculation"] = (
                    "리스료 현재가치에서 K-GAAP 장부금액을 차감해 사용권자산 조정액을 산출했습니다. "
                    "수정소급법(제1116호 경과규정)에 따라 사용권자산은 리스부채와 동액으로 인식합니다."
                )
                # 수정소급법: 사용권자산 = 리스부채 → 같은 현재가치로 부채 쪽 분개를 쌍으로 생성.
                # L2150은 표시 순서 도출용 코드(부채 구역)이며 별도 계정 시드는 필요 없다.
                paired_entry = {
                    "source_account": f"{item['account_name']} (리스부채 인식)",
                    "standard_code": "L2150",
                    "target_account": "리스부채",
                    "amount": 0,
                    "adjustment": round(pv, 2),
                    "mapping_type": item["mapping_type"],
                    "basis": "수정소급법에 따라 사용권자산과 동액의 리스부채를 인식합니다 (K-IFRS 제1116호).",
                    "calculation": f"리스부채 = 잔여 리스료의 현재가치 {pv:,.0f}. 1년 내 지급분의 유동 분류를 검토하세요.",
                    "presentation_order": account_presentation_order("L2150"),
                    "statement_type": "재무상태표",
                    "statement_section": "부채",
                    "statement_line_item": "리스부채 (유동성 구분 검토)",
                    "presentation_basis": "리스부채는 사용권자산과 별도로 부채에 표시합니다.",
                }
        elif account_key == "development":
            criteria = ["technical_feasibility", "intention_to_complete", "probable_future_benefits", "reliable_measurement"]
            qualifies = all(checklist_response.get(key) is True for key in criteria)
            entry["target_account"] = "무형자산" if qualifies else "연구개발비(비용)"
            entry["calculation"] = "K-IFRS 제1038호 개발단계 자산화 요건 충족 여부를 검토했습니다."
        elif account_key == "revenue":
            timing = checklist_response.get("recognition_timing") or "추가 검토 필요"
            entry["calculation"] = f"수익인식 시점을 '{timing}'로 문서화했습니다."
        elif account_key in {"financial_instrument", "receivables"}:
            entry["calculation"] = "K-IFRS 제1109호 분류 및 기대신용손실 검토가 필요합니다."
        elif account_key == "provision":
            recognized = all(
                checklist_response.get(key) is True
                for key in ["present_obligation", "probable_outflow", "reliable_estimate"]
            )
            entry["calculation"] = "충당부채 인식요건을 충족했습니다." if recognized else "충당부채 인식요건이 완전하지 않아 공시 또는 추가 검토가 필요합니다."
        elif account_key == "retirement_benefit":
            dbo = float(checklist_response.get("dbo_amount") or 0)
            plan_assets = float(checklist_response.get("plan_assets") or 0)
            if dbo > 0:
                net_liability = dbo - plan_assets
                entry["adjustment"] = round(net_liability - float(item["amount"]), 2)
                entry["calculation"] = (
                    f"순확정급여부채 = 확정급여채무 {dbo:,.0f} − 사외적립자산 {plan_assets:,.0f} = {net_liability:,.0f}. "
                    "K-GAAP 퇴직급여충당부채(추계액)와의 차이를 조정하며, 보험수리적 재측정요소는 기타포괄손익(OCI)으로 인식합니다."
                )
        elif account_key == "ppe":
            model = str(checklist_response.get("measurement_model") or "")
            book = float(item["amount"])
            fair_value = float(checklist_response.get("fair_value") or 0)
            recoverable = float(checklist_response.get("recoverable_amount") or 0)
            if "재평가" in model and fair_value > 0:
                entry["adjustment"] = round(fair_value - book, 2)
                direction = "증가분은 재평가잉여금(OCI)" if fair_value >= book else "감소분은 당기손익"
                entry["calculation"] = (
                    f"재평가모형: 공정가치 {fair_value:,.0f} − 장부금액 {book:,.0f} = {fair_value - book:,.0f}. {direction}으로 인식합니다."
                )
            elif 0 < recoverable < book:
                entry["adjustment"] = round(recoverable - book, 2)
                entry["calculation"] = (
                    f"손상: 회수가능액 {recoverable:,.0f} < 장부금액 {book:,.0f} → 손상차손 {book - recoverable:,.0f}을 당기손익으로 인식합니다."
                )
            else:
                entry["calculation"] = "원가모형 유지 또는 손상 징후 없음. 표시 라인만 매핑합니다."
        elif account_key == "investment_property":
            model = str(checklist_response.get("measurement_model") or "")
            fair_value = float(checklist_response.get("fair_value") or 0)
            book = float(item["amount"])
            if "공정가치" in model and fair_value > 0:
                entry["adjustment"] = round(fair_value - book, 2)
                entry["calculation"] = (
                    f"공정가치모형: 공정가치 {fair_value:,.0f} − 장부금액 {book:,.0f} = {fair_value - book:,.0f}을 당기손익으로 인식합니다."
                )
            else:
                entry["calculation"] = "원가모형 선택. 감가상각 후 원가로 표시하고 공정가치는 주석 공시합니다."
        elif account_key == "deferred_tax_asset":
            td = float(checklist_response.get("temporary_difference") or 0)
            rate = float(checklist_response.get("tax_rate") or 0) / 100
            realizable = checklist_response.get("realizable") is True
            dta = td * rate
            if td > 0 and rate > 0:
                if realizable:
                    entry["adjustment"] = round(dta - float(item["amount"]), 2)
                    entry["calculation"] = (
                        f"이연법인세자산 = 차감할 일시적차이 {td:,.0f} × 세율 {rate * 100:.1f}% = {dta:,.0f}. "
                        "총액법으로 자산·부채를 상계 없이 인식하며 K-GAAP 장부금액과의 차이를 조정합니다."
                    )
                else:
                    entry["target_account"] = "이연법인세자산(인식 제한)"
                    entry["calculation"] = (
                        f"산정 이연법인세자산 {dta:,.0f}이나 회수가능성이 높지 않아 인식을 제한합니다(미래 과세소득 검토 필요)."
                    )
        elif account_key == "government_grant":
            relation = str(checklist_response.get("grant_relation") or "미입력")
            method = str(checklist_response.get("presentation_method") or "미결정")
            entry["calculation"] = (
                f"정부보조금 성격: {relation} / 표시 방법: {method}. "
                "자산관련 보조금은 자산 차감법 또는 이연수익법 중 선택해 자산의 내용연수에 걸쳐 체계적으로 수익 인식합니다."
            )
        elif account_key == "borrowing_cost":
            qualifying = checklist_response.get("qualifying_asset") is True
            if qualifying:
                expenditure = float(checklist_response.get("expenditure") or 0)
                rate = float(checklist_response.get("capitalization_rate") or 0) / 100
                months = float(checklist_response.get("capitalization_months") or 0)
                capitalizable = expenditure * rate * (months / 12)
                entry["adjustment"] = round(capitalizable, 2)
                entry["target_account"] = "적격자산(유형자산 등) 자본화"
                entry["calculation"] = (
                    f"자본화 차입원가 = 평균지출액 {expenditure:,.0f} × 자본화이자율 {rate * 100:.1f}% × {months:.0f}/12 = {capitalizable:,.0f}. "
                    "적격자산 원가에 가산하고 동액을 금융원가에서 차감합니다."
                )
            else:
                entry["calculation"] = "적격자산이 아니므로 차입원가를 발생 기간의 비용으로 인식합니다(자본화 대상 아님)."
        elif account_key == "goodwill":
            amortization = float(checklist_response.get("amortization_expense") or 0)
            recoverable = float(checklist_response.get("recoverable_amount") or 0)
            book = float(item["amount"])
            restored = book + amortization  # 상각 환입 후 장부금액
            impaired = checklist_response.get("impairment_indicator") is True and 0 < recoverable < restored
            if impaired:
                entry["adjustment"] = round(recoverable - book, 2)
                entry["calculation"] = (
                    f"상각비 {amortization:,.0f} 환입 후 장부금액 {restored:,.0f} > 회수가능액 {recoverable:,.0f} → "
                    f"손상차손 {restored - recoverable:,.0f}을 인식합니다. K-IFRS는 영업권을 상각하지 않고 매년 손상검사하며, 영업권 손상차손은 환입할 수 없습니다."
                )
            elif amortization > 0:
                entry["adjustment"] = round(amortization, 2)
                entry["calculation"] = (
                    f"K-GAAP 영업권 상각비 {amortization:,.0f}을 환입합니다. "
                    "K-IFRS 제1103호는 영업권 상각을 금지하며 제1036호에 따라 매년 손상검사를 수행합니다."
                )
            else:
                entry["calculation"] = "당기 상각비가 없어 금액 조정은 없습니다. 매년 손상검사 수행 여부를 확인하세요."
        elif account_key == "preferred_shares":
            if checklist_response.get("mandatory_redemption") is True:
                entry["target_account"] = "상환우선주부채(금융부채)"
                entry["calculation"] = (
                    "의무상환 조항 또는 보유자 상환청구권이 있어 계약의 실질상 금융부채로 재분류합니다. "
                    "K-GAAP은 법적 형식에 따라 자본으로 분류하지만 K-IFRS 제1032호는 실질로 판단합니다."
                )
            else:
                entry["calculation"] = "상환 의무가 없어 지분상품(자본)으로 유지합니다. 배당 조건 등 그 밖의 계약 조건을 함께 검토하세요."
        elif account_key == "held_for_sale":
            qualifies = (
                checklist_response.get("plan_committed") is True
                and checklist_response.get("sale_probable_12m") is True
            )
            book = float(item["amount"])
            fair_value_less_costs = float(checklist_response.get("fair_value_less_costs") or 0)
            if qualifies:
                entry["target_account"] = "매각예정비유동자산"
                if 0 < fair_value_less_costs < book:
                    entry["adjustment"] = round(fair_value_less_costs - book, 2)
                    entry["calculation"] = (
                        f"저가 측정: 순공정가치 {fair_value_less_costs:,.0f} < 장부금액 {book:,.0f} → "
                        f"손상차손 {book - fair_value_less_costs:,.0f}을 인식하고 매각예정비유동자산으로 별도 표시합니다(감가상각 중지)."
                    )
                else:
                    entry["calculation"] = "매각예정 분류 요건을 충족합니다. 장부금액이 순공정가치 이하이므로 재분류만 수행합니다(감가상각 중지)."
            else:
                entry["calculation"] = "매각예정 분류 요건(매각계획 확약, 12개월 내 매각가능성)이 충족되지 않아 기존 분류를 유지합니다."
        # 아래 두 영역은 의도적으로 조정액을 계산하지 않는다: 부채·자본 분리와 공정가치 평가는
        # 전문가 판단 영역이라, 도구는 위험 신호 식별과 기준서 근거 첨부까지만 수행한다.
        elif account_key == "compound_instrument":
            risky = (
                checklist_response.get("cash_settlement_possible") is True
                or checklist_response.get("fx_or_adjustable") is True
            )
            entry["calculation"] = (
                ("현금결제 가능성·상환의무 또는 리픽싱/외화 조항이 확인되어, 전환권이 자본이 아닌 파생상품부채로 분류될 가능성이 높습니다. " if risky else "")
                + "부채요소·자본요소 분리와 공정가치 평가는 전문가 검토가 필요합니다 — 도구는 식별과 근거 제시까지만 수행합니다."
            )
        elif account_key == "derivative":
            designated = checklist_response.get("hedge_designated") is True
            entry["calculation"] = (
                ("위험회피관계로 지정되어 있습니다. 공식 문서화와 효과성 요건(K-IFRS 제1109호 6.4.1) 충족 여부를 검토하세요. " if designated else "위험회피 지정이 없으므로 공정가치 변동이 당기손익에 반영됩니다. ")
                + "공정가치 평가는 전문가 검토가 필요합니다 — 도구는 식별과 근거 제시까지만 수행합니다."
            )

        if item["mapping_type"] == "judgment":
            judgment_items.append(
                {
                    "statement_id": item["id"],
                    "account": item["account_name"],
                    "checklist_response": checklist_response,
                    "basis": item["rule_summary"],
                    "standards_paragraphs": [
                        {
                            "standard_set": para["standard_set"],
                            "reference_code": para["reference_code"],
                            "paragraph_label": para["paragraph_label"],
                            "title": para["title"],
                            "content": para["content"],
                        }
                        for para in standards_map.get(account_key, [])
                    ],
                }
            )
            notes.append(
                {
                    "account": item["account_name"],
                    "draft_note": f"{standard['ifrs']} 항목은 검토자 확인이 필요합니다. 표시 양식: {entry.get('statement_line_item', '검토 필요')}. 근거: {item['rule_summary']}",
                }
            )

        entries.append(entry)
        if paired_entry:
            entries.append(paired_entry)

    # 조정분개를 계정코드 기반 표시 순서(재무상태표 → 손익계산서)로 정렬한다.
    entries.sort(key=lambda e: (e.get("presentation_order", 800000), e.get("standard_code", "")))

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


def build_review_summary(statements: list[dict], conversion: dict | None, validation: dict | None) -> dict:
    """최종 검토(2차 승인) 화면용 요약.

    확인 필요(attention): 문제 상황 기반 — 미분류 잔존, 체크리스트 미입력, 검증 경고/오류.
    회계 판단(judgment): 계정 종류 기반 — 검토자가 값의 타당성을 확인할 judgment 항목.
    미분류(error 수준)가 남아 있으면 승인을 차단하고, 경고는 표시만 하고 승인을 허용한다.
    """
    attention = []
    responses_by_statement = {}
    paragraphs_by_statement = {}
    for item in (conversion or {}).get("judgment_items") or []:
        responses_by_statement[item.get("statement_id")] = item.get("checklist_response") or {}
        paragraphs_by_statement[item.get("statement_id")] = item.get("standards_paragraphs") or []

    unclassified = [row for row in statements if row.get("standard_code") == "X9999"]
    for row in unclassified:
        attention.append(
            {
                "type": "unclassified",
                "severity": "error",
                "account": row.get("account_name"),
                "message": "표준계정 미분류 상태입니다. 담당자 분류 또는 AI 제안 승인(1차 승인)이 필요합니다.",
                # action: 화면이 이 항목에 붙일 행동 버튼. 문자열 매칭 대신 서버가 행동을 내려준다.
                "action": "classify",
                "statement_id": row.get("id"),
            }
        )

    judgment = []
    for row in statements:
        if row.get("mapping_type") != "judgment" or row.get("standard_code") == "X9999":
            continue
        response = responses_by_statement.get(row.get("id")) or {}
        answered = bool(conversion) and bool(response)
        if not answered:
            attention.append(
                {
                    "type": "checklist_missing",
                    "severity": "warning",
                    "account": row.get("account_name"),
                    "message": "판단 체크리스트가 입력되지 않았습니다." if conversion else "변환 초안이 아직 생성되지 않아 체크리스트 응답이 없습니다.",
                    "action": "fill_checklist",
                    "statement_id": row.get("id"),
                }
            )
        judgment.append(
            {
                "statement_id": row.get("id"),
                "account": row.get("account_name"),
                "normalized_account": row.get("normalized_account"),
                "standard_code": row.get("standard_code"),
                "amount": row.get("amount"),
                "rule_summary": row.get("rule_summary"),
                "checklist_answered": answered,
                "checklist_response": response,
                "standards_paragraph_count": len(paragraphs_by_statement.get(row.get("id")) or []),
            }
        )

    for check in (validation or {}).get("checks") or []:
        if check.get("status") in {"warning", "error"}:
            attention.append(
                {
                    "type": "validation",
                    "severity": check.get("status"),
                    "account": check.get("name"),
                    "message": check.get("detail"),
                    # 손익 항목 누락은 행 추가로, 균형·중복류 문제는 계정 행 재확인으로 유도한다.
                    "action": "add_rows" if "손익" in str(check.get("name") or "") else "review_rows",
                }
            )

    blocking = [item for item in attention if item["severity"] == "error"]
    return {
        "attention": attention,
        "judgment": judgment,
        "counts": {
            "attention": len(attention),
            "attention_errors": len(blocking),
            "judgment": len(judgment),
            "unclassified": len(unclassified),
        },
        "has_conversion": conversion is not None,
        "can_approve": conversion is not None and not blocking,
        "approval_policy": "오류(미분류 등)가 남아 있으면 승인이 차단되고, 경고는 검토자 판단으로 승인할 수 있습니다.",
    }


def _net_equity_effect(entries: list[dict]) -> float:
    """조정분개들이 순자산(자본총계)에 미치는 영향. 자산·금융(+), 부채(−), 자본·손익(+)."""
    signs = {"A": 1, "F": 1, "L": -1, "E": 1, "R": 1}
    return sum(
        signs.get(str(entry.get("standard_code", ""))[:1], 0) * float(entry.get("adjustment") or 0)
        for entry in entries
    )


def compare_policy_scenarios(
    project: dict,
    statements: list[dict],
    responses: dict,
    reference: "ReferenceData",
) -> dict:
    """선택가능 회계정책의 영향 비교: 정책 선택지별로 같은 계산기를 돌려 조정액·순자산 영향을 나란히 제시.

    계산기가 결정론 순수 함수라서 가능한 기능 — 입력(정책 선택)만 바꿔 재계산하면 같은
    데이터에서 항상 같은 비교가 나온다. 결과는 정책 결정의 참고 자료이며 확정은 검토자가 한다
    (회계정책은 동일 유형 전체에 일관 적용해야 하므로 항목별 선택이 아니라 정책 차원의 결정).
    """
    comparisons = []
    for item in statements:
        account_key = account_key_for_statement(item, reference)
        scenario = POLICY_SCENARIOS.get(account_key)
        if not scenario:
            continue
        item_key, options = scenario
        base_response = dict(responses.get(item["id"], {}))
        option_results = []
        for option in options:
            variant = {item["id"]: {**base_response, item_key: option}}
            output = generate_conversion(project, [item], variant, reference)
            entries = output["entries"]
            main = entries[0]
            option_results.append(
                {
                    "option": option,
                    "adjustment": main.get("adjustment", 0),
                    "net_equity_effect": round(_net_equity_effect(entries), 2),
                    "target_account": main.get("target_account", ""),
                    "calculation": main.get("calculation", ""),
                }
            )
        checklist = reference.checklists.get(account_key, [])
        policy_label = next((entry["label"] for entry in checklist if entry["key"] == item_key), item_key)
        # 공정가치 입력이 없으면 재평가/공정가치 선택지의 조정이 0으로 나와 비교가 무의미하다.
        needs_fair_value = account_key in {"ppe", "investment_property"} and not float(base_response.get("fair_value") or 0)
        comparisons.append(
            {
                "statement_id": item["id"],
                "account": item["account_name"],
                "account_key": account_key,
                "policy_label": policy_label,
                "options": option_results,
                "equity_difference": round(
                    option_results[-1]["net_equity_effect"] - option_results[0]["net_equity_effect"], 2
                ),
                "insufficient_inputs": needs_fair_value,
            }
        )
    return {
        "comparisons": comparisons,
        "note": "정책 비교는 참고용 산출입니다. 회계정책은 동일 유형 전체에 일관 적용해야 하며, 선택과 승인은 검토자가 합니다.",
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
    """내보내기 셀용 None-안전 문자열화 (빈 값은 '-')."""
    return str(value or "-")

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
    lines.append("3. 판단 필요 항목 (K-GAAP/K-IFRS 기준서 문단 근거 포함)")
    lines.append("-" * 42)
    if not judgment_items:
        lines.append("- 없음")
    for item in judgment_items:
        lines.append(f"- {item.get('account', '-')}: {localize_export_text(item.get('basis'))}")
        for para in item.get("standards_paragraphs", []):
            lines.append(
                f"    [{para.get('standard_set', '-')}] {para.get('reference_code', '-')} "
                f"{para.get('paragraph_label', '-')}: {para.get('content', '-')}"
            )
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
