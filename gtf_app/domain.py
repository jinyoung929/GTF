from __future__ import annotations

import csv
import io
import re
import uuid
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

# ifrs 필드는 변환 결과의 target_account(K-IFRS 표시 계정명)로 쓰이며, 한국 회사가
# K-IFRS로 작성하는 재무제표 산출물에 맞춰 한국어 공식 표시명으로 둔다.
# rule 필드의 기준서 번호는 국제 번호(IFRS 16 등) 대신 K-IFRS 체계(제1116호 등)를 사용한다.
STANDARD_ACCOUNTS = {
    "cash": {
        "code": "A1000",
        "label": "현금및현금성자산",
        "ifrs": "현금및현금성자산",
        "type": "simple",
        "rule": "사용 제한 여부를 확인한 뒤 현금및현금성자산으로 단순 매핑합니다.",
    },
    "receivables": {
        "code": "A1100",
        "label": "매출채권",
        "ifrs": "매출채권및기타채권",
        "type": "judgment",
        "rule": "K-IFRS 제1109호에 따라 매출채권 분류와 기대신용손실 충당금을 검토합니다.",
    },
    "inventory": {
        "code": "A1200",
        "label": "재고자산",
        "ifrs": "재고자산",
        "type": "simple",
        "rule": "K-IFRS 제1002호에 따라 재고자산으로 매핑하고 원가와 순실현가능가치 비교를 검토합니다.",
    },
    "lease": {
        "code": "A2100",
        "label": "리스",
        "ifrs": "사용권자산 및 리스부채",
        "type": "judgment",
        "rule": "K-IFRS 제1116호 측정을 위해 리스기간, 지급액, 선택권, 할인율을 추가 확인합니다.",
    },
    "development": {
        "code": "A3100",
        "label": "개발비",
        "ifrs": "무형자산 또는 연구개발비",
        "type": "judgment",
        "rule": "K-IFRS 제1038호 개발단계 자산화 요건 충족 여부를 검토합니다.",
    },
    "revenue": {
        "code": "R1000",
        "label": "수익",
        "ifrs": "고객과의 계약에서 생기는 수익",
        "type": "judgment",
        "rule": "K-IFRS 제1115호에 따라 수행의무와 수익인식 시점을 확인합니다.",
    },
    "financial_instrument": {
        "code": "F1000",
        "label": "금융상품",
        "ifrs": "금융자산·금융부채",
        "type": "judgment",
        "rule": "K-IFRS 제1109호에 따라 사업모형과 계약상 현금흐름 특성을 검토합니다.",
    },
    "provision": {
        "code": "L2200",
        "label": "충당부채",
        "ifrs": "충당부채",
        "type": "judgment",
        "rule": "K-IFRS 제1037호에 따라 현재의무, 유출가능성, 신뢰성 있는 추정 여부를 검토합니다.",
    },
    # 아래는 판단 체크리스트가 필요 없는 표시 매핑 계정으로, 키워드 사전에는 없지만
    # AI 1차 분류가 미분류 계정을 K-IFRS 표시 라인으로 제안할 때 후보로 사용된다.
    "ppe": {
        "code": "A1500",
        "label": "유형자산",
        "ifrs": "유형자산",
        "type": "judgment",
        "rule": "K-IFRS 제1016·1036호에 따라 원가모형과 재평가모형 중 선택하고 손상 징후가 있으면 회수가능액과 비교해 손상차손을 인식합니다.",
    },
    "prepaid_expense": {
        "code": "A1300",
        "label": "선급비용",
        "ifrs": "선급비용",
        "type": "simple",
        "rule": "선급비용을 K-IFRS 선급비용 라인으로 매핑합니다.",
    },
    "deposits": {
        "code": "A1400",
        "label": "보증금",
        "ifrs": "장기보증금(금융자산)",
        "type": "simple",
        "rule": "임차보증금 등 반환 예정 보증금을 금융자산 성격의 예치금으로 매핑합니다.",
    },
    "deferred_tax_asset": {
        "code": "A1600",
        "label": "이연법인세자산",
        "ifrs": "이연법인세자산",
        "type": "judgment",
        "rule": "K-IFRS 제1012호에 따라 일시적차이에 세율을 적용해 총액법으로 이연법인세자산을 인식하고 회수가능성을 검토합니다.",
    },
    "trade_payables": {
        "code": "L1000",
        "label": "매입채무",
        "ifrs": "매입채무및기타채무",
        "type": "simple",
        "rule": "매입채무와 미지급금을 K-IFRS 매입채무 라인으로 매핑합니다.",
    },
    "other_payables": {
        "code": "L1100",
        "label": "미지급금",
        "ifrs": "기타채무 및 미지급비용",
        "type": "simple",
        "rule": "미지급금, 미지급비용을 기타채무 라인으로 매핑합니다.",
    },
    "current_tax_liability": {
        "code": "L1200",
        "label": "미지급법인세",
        "ifrs": "당기법인세부채",
        "type": "simple",
        "rule": "미지급법인세를 K-IFRS 제1012호 당기법인세부채로 매핑합니다.",
    },
    "deferred_tax_liability": {
        "code": "L2100",
        "label": "이연법인세부채",
        "ifrs": "이연법인세부채",
        "type": "simple",
        "rule": "K-IFRS 제1012호 이연법인세부채로 매핑합니다.",
    },
    "share_capital": {
        "code": "E1000",
        "label": "자본금",
        "ifrs": "자본금",
        "type": "simple",
        "rule": "자본금을 K-IFRS 자본금 라인으로 매핑합니다.",
    },
    "capital_surplus": {
        "code": "E1100",
        "label": "자본잉여금",
        "ifrs": "자본잉여금",
        "type": "simple",
        "rule": "자본잉여금을 주식발행초과금 등 자본잉여 라인으로 매핑합니다.",
    },
    "retained_earnings": {
        "code": "E1200",
        "label": "이익잉여금",
        "ifrs": "이익잉여금",
        "type": "simple",
        "rule": "이익잉여금 또는 결손금을 K-IFRS 이익잉여금 라인으로 매핑합니다.",
    },
    "cost_of_sales": {
        "code": "R2000",
        "label": "매출원가",
        "ifrs": "매출원가",
        "type": "simple",
        "rule": "매출원가를 K-IFRS 매출원가 라인으로 매핑합니다.",
    },
    "operating_expense": {
        "code": "R3000",
        "label": "판매비와관리비",
        "ifrs": "판매비와관리비",
        "type": "simple",
        "rule": "판매비와관리비, 영업비용을 K-IFRS 판매비와관리비 라인으로 매핑합니다.",
    },
    # K-GAAP↔K-IFRS 차이가 큰 판단 필요 영역 (측정·인식 조정 발생)
    "retirement_benefit": {
        "code": "L2300",
        "label": "퇴직급여충당부채",
        "ifrs": "순확정급여부채",
        "type": "judgment",
        "rule": "K-IFRS 제1019호에 따라 확정급여채무를 보험수리적으로 평가하고 사외적립자산을 차감해 순확정급여부채를 측정하며, 재측정요소는 기타포괄손익으로 인식합니다.",
    },
    "investment_property": {
        "code": "A1700",
        "label": "투자부동산",
        "ifrs": "투자부동산",
        "type": "judgment",
        "rule": "K-IFRS 제1040호에 따라 원가모형과 공정가치모형 중 회계정책을 선택하고, 공정가치모형이면 평가손익을 당기손익에 반영합니다.",
    },
    "government_grant": {
        "code": "L2400",
        "label": "정부보조금",
        "ifrs": "이연정부보조금수익",
        "type": "judgment",
        "rule": "K-IFRS 제1020호에 따라 자산관련 보조금의 표시 방법(자산 차감법 또는 이연수익법)을 결정하고 체계적으로 수익 인식합니다.",
    },
    "borrowing_cost": {
        "code": "R4000",
        "label": "차입원가",
        "ifrs": "금융원가(차입원가 자본화 조정)",
        "type": "judgment",
        "rule": "K-IFRS 제1023호에 따라 적격자산 취득에 직접 관련된 차입원가를 자본화 대상으로 판단합니다.",
    },
    "other": {
        "code": "X9999",
        "label": "미분류 계정",
        "ifrs": "검토 필요",
        "type": "judgment",
        "rule": "자동 매핑 신뢰도가 낮아 담당자 분류 검토가 필요합니다.",
    },
}


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


def account_key_for_statement(item: dict) -> str:
    """계정 행이 확정한 표준코드에서 계정키를 복원한다.

    담당자가 AI 제안을 승인해 재분류한 계정(예: 임차보증금 → F1000)은 계정명 키워드로는
    다시 찾을 수 없으므로, 저장된 standard_code를 우선하고 없을 때만 계정명 정규화로 보완한다.
    """
    code_to_key = {account["code"]: key for key, account in STANDARD_ACCOUNTS.items()}
    return code_to_key.get(str(item.get("standard_code") or "")) or normalize_account_name(item["account_name"])


# 표준 재무제표 양식 라인(계정 → 표시 라인 매핑)은 seeds/financial_statement_templates.sql이
# 단일 출처이며, 서버 시작 시 financial_statement_templates 테이블로 upsert된다.
# 런타임 조회는 server.load_statement_template_map이 DB에서 수행한다.


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
    "ppe": [
        {"key": "measurement_model", "label": "측정모형 (원가모형 / 재평가모형)", "type": "text", "required": True},
        {"key": "fair_value", "label": "재평가모형 선택 시 공정가치", "type": "number", "required": False},
        {"key": "recoverable_amount", "label": "회수가능액 (손상검토용, 없으면 0)", "type": "number", "required": False},
    ],
    "deferred_tax_asset": [
        {"key": "temporary_difference", "label": "차감할 일시적차이 총액", "type": "number", "required": True},
        {"key": "tax_rate", "label": "적용 세율(%)", "type": "number", "required": True},
        {"key": "realizable", "label": "미래 과세소득으로 회수 가능성이 높은가?", "type": "boolean", "required": True},
    ],
    "retirement_benefit": [
        {"key": "dbo_amount", "label": "확정급여채무 현재가치(보험수리적 평가액)", "type": "number", "required": True},
        {"key": "plan_assets", "label": "사외적립자산 공정가치", "type": "number", "required": False},
        {"key": "discount_rate", "label": "할인율(%)", "type": "number", "required": False},
    ],
    "investment_property": [
        {"key": "measurement_model", "label": "측정모형 (원가모형 / 공정가치모형)", "type": "text", "required": True},
        {"key": "fair_value", "label": "공정가치모형 선택 시 공정가치", "type": "number", "required": False},
    ],
    "government_grant": [
        {"key": "grant_relation", "label": "보조금 성격 (자산관련 / 수익관련)", "type": "text", "required": True},
        {"key": "presentation_method", "label": "자산관련 표시 방법 (자산차감법 / 이연수익법)", "type": "text", "required": True},
    ],
    "borrowing_cost": [
        {"key": "qualifying_asset", "label": "적격자산(취득에 상당한 기간 소요)인가?", "type": "boolean", "required": True},
        {"key": "expenditure", "label": "적격자산에 대한 평균 지출액", "type": "number", "required": False},
        {"key": "capitalization_rate", "label": "자본화이자율(%)", "type": "number", "required": False},
        {"key": "capitalization_months", "label": "자본화 기간(개월)", "type": "number", "required": False},
    ],
    "other": [
        {"key": "management_memo", "label": "경영진 분류 메모", "type": "text", "required": True},
    ],
}


# K-GAAP(일반기업회계기준)과 K-IFRS 기준서 문단을 standard_set으로 분리해 보관하는
# 검색용 기준정보. 서버 시작 시 standards_paragraphs 테이블에 시드되고,
# 판단 필요 항목의 검토 근거로 함께 제시된다. 문단 내용은 기준서 원문의 요약이며
# 최종 판단 시에는 기준서 원문을 확인해야 한다.
STANDARDS_PARAGRAPHS = [
    {
        "id": "kifrs_1116_p22",
        "standard_set": "K-IFRS",
        "reference_code": "K-IFRS 제1116호 리스",
        "paragraph_label": "문단 22",
        "account_key": "lease",
        "title": "사용권자산과 리스부채의 인식",
        "content": "리스이용자는 리스개시일에 사용권자산과 리스부채를 인식한다.",
        "keywords": "리스,사용권자산,리스부채,인식,리스개시일",
    },
    {
        "id": "kifrs_1116_p26",
        "standard_set": "K-IFRS",
        "reference_code": "K-IFRS 제1116호 리스",
        "paragraph_label": "문단 26",
        "account_key": "lease",
        "title": "리스부채의 최초 측정",
        "content": "리스개시일에 리스부채는 그날 현재 지급되지 않은 리스료의 현재가치로 측정한다. 리스의 내재이자율을 쉽게 산정할 수 있으면 그 이자율로, 산정할 수 없으면 리스이용자의 증분차입이자율로 할인한다.",
        "keywords": "리스부채,현재가치,할인율,내재이자율,증분차입이자율",
    },
    {
        "id": "kifrs_1116_p18",
        "standard_set": "K-IFRS",
        "reference_code": "K-IFRS 제1116호 리스",
        "paragraph_label": "문단 18",
        "account_key": "lease",
        "title": "리스기간의 산정",
        "content": "리스기간은 리스의 해지불능기간에, 연장선택권을 행사할 것이 상당히 확실한 경우 그 대상 기간과 종료선택권을 행사하지 않을 것이 상당히 확실한 경우 그 대상 기간을 포함하여 산정한다.",
        "keywords": "리스기간,연장선택권,종료선택권,해지불능기간",
    },
    {
        "id": "kifrs_1038_p57",
        "standard_set": "K-IFRS",
        "reference_code": "K-IFRS 제1038호 무형자산",
        "paragraph_label": "문단 57",
        "account_key": "development",
        "title": "개발활동 지출의 자산 인식 요건",
        "content": "개발활동에서 발생한 무형자산은 기술적 실현가능성, 완성하여 사용하거나 판매하려는 의도와 능력, 미래경제적효익을 창출하는 방법, 개발을 완료하는 데 필요한 자원의 입수가능성, 관련 지출의 신뢰성 있는 측정을 모두 제시할 수 있는 경우에만 인식한다.",
        "keywords": "개발비,무형자산,자산화,기술적 실현가능성,미래경제적효익",
    },
    {
        "id": "kifrs_1038_p54",
        "standard_set": "K-IFRS",
        "reference_code": "K-IFRS 제1038호 무형자산",
        "paragraph_label": "문단 54",
        "account_key": "development",
        "title": "연구단계 지출의 비용 처리",
        "content": "연구(또는 내부 프로젝트의 연구단계)에 대한 지출은 무형자산으로 인식하지 않고 발생시점에 비용으로 인식한다.",
        "keywords": "연구비,연구단계,비용,연구개발",
    },
    {
        "id": "kifrs_1115_p31",
        "standard_set": "K-IFRS",
        "reference_code": "K-IFRS 제1115호 고객과의 계약에서 생기는 수익",
        "paragraph_label": "문단 31",
        "account_key": "revenue",
        "title": "수행의무 이행 시 수익 인식",
        "content": "기업이 고객에게 약속한 재화나 용역, 즉 자산을 이전하여 수행의무를 이행할 때 또는 이행하는 대로 수익을 인식한다. 자산은 고객이 그 자산을 통제할 때 이전된다.",
        "keywords": "수익,수행의무,통제 이전,수익인식 시점",
    },
    {
        "id": "kifrs_1115_p50",
        "standard_set": "K-IFRS",
        "reference_code": "K-IFRS 제1115호 고객과의 계약에서 생기는 수익",
        "paragraph_label": "문단 50",
        "account_key": "revenue",
        "title": "변동대가의 추정",
        "content": "계약에서 약속한 대가에 변동금액이 포함된 경우, 고객에게 약속한 재화나 용역을 이전하고 그 대가로 받을 권리를 갖게 될 금액을 추정한다.",
        "keywords": "변동대가,대가 추정,리베이트,할인",
    },
    {
        "id": "kifrs_1109_p411",
        "standard_set": "K-IFRS",
        "reference_code": "K-IFRS 제1109호 금융상품",
        "paragraph_label": "문단 4.1.1",
        "account_key": "financial_instrument",
        "title": "금융자산의 분류 기준",
        "content": "금융자산은 금융자산의 관리를 위한 사업모형과 금융자산의 계약상 현금흐름 특성에 근거하여 상각후원가, 기타포괄손익-공정가치, 당기손익-공정가치 측정 범주로 분류한다.",
        "keywords": "금융자산,분류,사업모형,SPPI,계약상 현금흐름",
    },
    {
        "id": "kifrs_1109_p5515",
        "standard_set": "K-IFRS",
        "reference_code": "K-IFRS 제1109호 금융상품",
        "paragraph_label": "문단 5.5.15",
        "account_key": "receivables",
        "title": "매출채권 기대신용손실 간편법",
        "content": "매출채권과 계약자산 등에 대해서는 전체기간 기대신용손실에 해당하는 금액으로 손실충당금을 측정하는 간편법을 적용할 수 있다.",
        "keywords": "매출채권,기대신용손실,ECL,손실충당금,간편법",
    },
    {
        "id": "kifrs_1037_p14",
        "standard_set": "K-IFRS",
        "reference_code": "K-IFRS 제1037호 충당부채, 우발부채 및 우발자산",
        "paragraph_label": "문단 14",
        "account_key": "provision",
        "title": "충당부채의 인식 요건",
        "content": "충당부채는 과거사건의 결과로 현재의무(법적의무 또는 의제의무)가 존재하고, 그 의무를 이행하기 위해 경제적효익이 있는 자원의 유출 가능성이 높으며, 의무 금액을 신뢰성 있게 추정할 수 있는 경우에 인식한다.",
        "keywords": "충당부채,현재의무,자원 유출,신뢰성 있는 추정",
    },
    {
        "id": "kifrs_1002_p9",
        "standard_set": "K-IFRS",
        "reference_code": "K-IFRS 제1002호 재고자산",
        "paragraph_label": "문단 9",
        "account_key": "inventory",
        "title": "재고자산의 저가 측정",
        "content": "재고자산은 취득원가와 순실현가능가치 중 낮은 금액으로 측정한다.",
        "keywords": "재고자산,저가법,순실현가능가치,취득원가",
    },
    {
        "id": "kifrs_1007_p6",
        "standard_set": "K-IFRS",
        "reference_code": "K-IFRS 제1007호 현금흐름표",
        "paragraph_label": "문단 6",
        "account_key": "cash",
        "title": "현금성자산의 정의",
        "content": "현금성자산은 유동성이 매우 높은 단기 투자자산으로서, 확정된 금액의 현금으로 전환이 용이하고 가치변동의 위험이 경미한 자산을 말한다.",
        "keywords": "현금성자산,현금,단기투자,유동성",
    },
    {
        "id": "kgaap_ch13_lease",
        "standard_set": "K-GAAP",
        "reference_code": "일반기업회계기준 제13장 리스",
        "paragraph_label": "리스의 분류",
        "account_key": "lease",
        "title": "금융리스와 운용리스의 분류",
        "content": "리스는 소유에 따른 위험과 보상의 대부분이 이전되는지에 따라 금융리스와 운용리스로 분류한다. 운용리스의 리스이용자는 리스료를 리스기간에 걸쳐 비용으로 인식하며 리스부채를 계상하지 않는다. K-IFRS 전환 시 사용권자산과 리스부채 계상 여부를 검토해야 한다.",
        "keywords": "리스,운용리스,금융리스,비용 인식,부외",
    },
    {
        "id": "kgaap_ch11_development",
        "standard_set": "K-GAAP",
        "reference_code": "일반기업회계기준 제11장 무형자산",
        "paragraph_label": "개발비의 인식",
        "account_key": "development",
        "title": "개발단계 지출의 자산 인식",
        "content": "개발단계에서 발생한 지출은 기술적 실현가능성, 사용·판매 의도와 능력, 미래경제적효익 창출 가능성, 신뢰성 있는 측정 등 자산 인식요건을 모두 충족하는 경우 개발비의 과목으로 무형자산으로 인식하고, 그 외에는 발생한 기간의 비용으로 처리한다.",
        "keywords": "개발비,무형자산,자산화,경상개발비",
    },
    {
        "id": "kgaap_ch16_revenue",
        "standard_set": "K-GAAP",
        "reference_code": "일반기업회계기준 제16장 수익",
        "paragraph_label": "재화 판매 수익의 인식",
        "account_key": "revenue",
        "title": "위험과 보상 이전에 따른 수익 인식",
        "content": "재화의 판매 수익은 재화 소유에 따른 유의적인 위험과 보상이 구매자에게 이전되고, 수익금액을 신뢰성 있게 측정할 수 있으며, 경제적 효익의 유입 가능성이 매우 높은 경우 등에 인식한다. K-IFRS 제1115호의 수행의무·통제 이전 모형과 접근 방식이 다르다.",
        "keywords": "수익,위험과 보상,재화 판매,인도기준",
    },
    {
        "id": "kgaap_ch6_securities",
        "standard_set": "K-GAAP",
        "reference_code": "일반기업회계기준 제6장 금융자산·금융부채",
        "paragraph_label": "유가증권의 분류",
        "account_key": "financial_instrument",
        "title": "보유 목적에 따른 유가증권 분류",
        "content": "유가증권은 취득 목적과 보유 의도에 따라 단기매매증권, 매도가능증권, 만기보유증권 등으로 분류한다. K-IFRS 제1109호의 사업모형·계약상 현금흐름 특성 기준과 분류 체계가 다르므로 전환 시 재분류를 검토해야 한다.",
        "keywords": "유가증권,단기매매증권,매도가능증권,만기보유증권,분류",
    },
    {
        "id": "kgaap_ch6_receivables",
        "standard_set": "K-GAAP",
        "reference_code": "일반기업회계기준 제6장 금융자산·금융부채",
        "paragraph_label": "대손충당금",
        "account_key": "receivables",
        "title": "대손충당금의 설정",
        "content": "매출채권 등 수취채권은 회수가 불확실한 금액을 합리적이고 객관적인 기준에 따라 산출한 대손추산액을 대손충당금으로 설정한다. 발생손실에 기초한 접근으로, K-IFRS 제1109호의 기대신용손실 모형과 차이가 있다.",
        "keywords": "매출채권,대손충당금,대손추산액,발생손실",
    },
    {
        "id": "kgaap_ch14_provision",
        "standard_set": "K-GAAP",
        "reference_code": "일반기업회계기준 제14장 충당부채",
        "paragraph_label": "충당부채의 인식",
        "account_key": "provision",
        "title": "충당부채의 인식 요건",
        "content": "충당부채는 과거사건의 결과로 현재의무가 존재하고, 그 의무를 이행하기 위해 자원이 유출될 가능성이 매우 높으며, 의무 금액을 신뢰성 있게 추정할 수 있을 때 인식한다.",
        "keywords": "충당부채,현재의무,자원 유출,추정",
    },
    {
        "id": "kgaap_ch7_inventory",
        "standard_set": "K-GAAP",
        "reference_code": "일반기업회계기준 제7장 재고자산",
        "paragraph_label": "재고자산의 평가",
        "account_key": "inventory",
        "title": "저가법 평가",
        "content": "재고자산은 취득원가로 측정하되, 시가가 취득원가보다 낮은 경우에는 시가를 장부금액으로 하는 저가법으로 평가한다.",
        "keywords": "재고자산,저가법,시가,평가손실",
    },
    {
        "id": "kgaap_ch2_cash",
        "standard_set": "K-GAAP",
        "reference_code": "일반기업회계기준 제2장 재무제표의 작성과 표시",
        "paragraph_label": "현금및현금성자산",
        "account_key": "cash",
        "title": "현금및현금성자산의 범위",
        "content": "현금및현금성자산은 통화 및 통화대용증권과 취득 당시 만기가 3개월 이내에 도래하는 유동성이 높은 금융상품 등을 포함한다.",
        "keywords": "현금,현금성자산,통화대용증권,만기 3개월",
    },
    {
        "id": "kifrs_1019_p57",
        "standard_set": "K-IFRS",
        "reference_code": "K-IFRS 제1019호 종업원급여",
        "paragraph_label": "문단 57",
        "account_key": "retirement_benefit",
        "title": "순확정급여부채(자산)의 인식",
        "content": "확정급여제도의 순확정급여부채(자산)는 확정급여채무의 현재가치에서 사외적립자산의 공정가치를 차감하여 결정한다. 확정급여채무는 예측단위적립방식으로 보험수리적 평가하며, 순확정급여부채(자산)의 재측정요소는 기타포괄손익으로 인식한다.",
        "keywords": "퇴직급여,확정급여채무,사외적립자산,순확정급여부채,보험수리적,재측정,OCI",
    },
    {
        "id": "kgaap_ch21_severance",
        "standard_set": "K-GAAP",
        "reference_code": "일반기업회계기준 제21장 종업원급여",
        "paragraph_label": "퇴직급여충당부채",
        "account_key": "retirement_benefit",
        "title": "퇴직금추계액 기준 충당부채",
        "content": "확정급여형 퇴직급여제도의 퇴직급여충당부채는 보고기간말 현재 전 종업원이 일시에 퇴직할 경우 지급하여야 할 퇴직금추계액을 기준으로 인식한다(보험수리적 평가를 요구하지 않음).",
        "keywords": "퇴직급여충당부채,퇴직금추계액,확정급여형",
    },
    {
        "id": "kifrs_1016_p31",
        "standard_set": "K-IFRS",
        "reference_code": "K-IFRS 제1016호 유형자산",
        "paragraph_label": "문단 31",
        "account_key": "ppe",
        "title": "재평가모형",
        "content": "재평가모형을 선택한 경우 공정가치를 신뢰성 있게 측정할 수 있는 유형자산은 재평가일의 공정가치에서 이후의 감가상각누계액과 손상차손누계액을 차감한 재평가금액을 장부금액으로 한다. 재평가로 증가한 금액은 기타포괄손익으로, 감소한 금액은 당기손익으로 인식한다.",
        "keywords": "유형자산,재평가모형,공정가치,재평가잉여금,OCI",
    },
    {
        "id": "kifrs_1036_p59",
        "standard_set": "K-IFRS",
        "reference_code": "K-IFRS 제1036호 자산손상",
        "paragraph_label": "문단 59",
        "account_key": "ppe",
        "title": "손상차손의 인식",
        "content": "자산의 회수가능액이 장부금액에 미달하면 장부금액을 회수가능액으로 감액하고 그 차액을 손상차손으로 당기손익에 인식한다. 회수가능액은 순공정가치와 사용가치 중 큰 금액이다.",
        "keywords": "손상,회수가능액,손상차손,사용가치,순공정가치",
    },
    {
        "id": "kifrs_1040_p33",
        "standard_set": "K-IFRS",
        "reference_code": "K-IFRS 제1040호 투자부동산",
        "paragraph_label": "문단 33",
        "account_key": "investment_property",
        "title": "공정가치모형",
        "content": "공정가치모형을 선택한 경우 투자부동산을 공정가치로 측정하고, 공정가치 변동으로 발생하는 손익은 발생한 기간의 당기손익에 반영한다. 공정가치모형에서는 감가상각을 하지 않는다.",
        "keywords": "투자부동산,공정가치모형,평가손익,당기손익",
    },
    {
        "id": "kifrs_1012_p24",
        "standard_set": "K-IFRS",
        "reference_code": "K-IFRS 제1012호 법인세",
        "paragraph_label": "문단 24",
        "account_key": "deferred_tax_asset",
        "title": "이연법인세자산의 인식",
        "content": "차감할 일시적차이가 사용될 수 있는 미래 과세소득의 발생가능성이 높은 경우 그 차이에 대하여 이연법인세자산을 인식한다. 이연법인세자산과 부채는 상계하지 않고 총액으로 인식하며 할인하지 않는다.",
        "keywords": "이연법인세자산,일시적차이,총액법,회수가능성,과세소득",
    },
    {
        "id": "kifrs_1020_p24",
        "standard_set": "K-IFRS",
        "reference_code": "K-IFRS 제1020호 정부보조금",
        "paragraph_label": "문단 24",
        "account_key": "government_grant",
        "title": "자산관련 보조금의 표시",
        "content": "자산관련 정부보조금은 이연수익으로 표시하거나 자산의 장부금액에서 차감하여 표시한다. 어느 방법을 선택하든 관련 자산의 내용연수에 걸쳐 체계적인 기준으로 당기손익에 인식한다.",
        "keywords": "정부보조금,자산관련,이연수익,자산차감법",
    },
    {
        "id": "kifrs_1023_p8",
        "standard_set": "K-IFRS",
        "reference_code": "K-IFRS 제1023호 차입원가",
        "paragraph_label": "문단 8",
        "account_key": "borrowing_cost",
        "title": "적격자산 차입원가의 자본화",
        "content": "적격자산의 취득, 건설 또는 생산과 직접 관련된 차입원가는 해당 자산 원가의 일부로 자본화한다. 적격자산은 의도된 용도로 사용하거나 판매할 수 있는 상태가 되는 데 상당한 기간을 필요로 하는 자산이다. 그 밖의 차입원가는 발생 기간의 비용으로 인식한다.",
        "keywords": "차입원가,적격자산,자본화,자본화이자율",
    },
]


def standards_paragraphs_for_accounts(account_keys) -> dict:
    """계정키별로 K-GAAP과 K-IFRS 문단을 함께 묶어 반환한다 (DB 미사용 폴백)."""
    keys = set(account_keys)
    grouped: dict[str, list[dict]] = {}
    for para in STANDARDS_PARAGRAPHS:
        if para["account_key"] in keys:
            grouped.setdefault(para["account_key"], []).append(para)
    return grouped


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
        "퇴직급여충당부채": "retirement_benefit",
        "확정급여채무": "retirement_benefit",
        "순확정급여부채": "retirement_benefit",
        "퇴직급여": "retirement_benefit",
        "충당부채": "provision",
        "provision": "provision",
        "투자부동산": "investment_property",
        "정부보조금": "government_grant",
        "국고보조금": "government_grant",
        "차입원가": "borrowing_cost",
        "유형자산": "ppe",
        "토지": "ppe",
        "건물": "ppe",
        "기계장치": "ppe",
        "이연법인세자산": "deferred_tax_asset",
        "이연법인세부채": "deferred_tax_liability",
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
    mapping_source = "rule_based"
    ai_suggestion = row.get("ai_suggestion") or {}
    suggested_key = ai_suggestion.get("account_key")
    if account_key == "other" and suggested_key in STANDARD_ACCOUNTS and suggested_key != "other":
        # 키워드 매핑 실패 계정에 대한 AI 1차 분류 제안. 추출 결과를 담당자가
        # 확인하고 반영하는 시점에 적용되며, 확정 권한은 사람에게 있다.
        account_key = suggested_key
        mapping_source = "ai_suggested_human_accepted"
    standard = STANDARD_ACCOUNTS[account_key]
    checklist = CHECKLISTS.get(account_key, []) if standard["type"] == "judgment" else []
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

def generate_conversion(
    project: dict,
    statements: list[dict],
    responses: dict,
    templates: dict | None = None,
    standards_map: dict | None = None,
) -> dict:
    templates = templates or {}
    if standards_map is None:
        standards_map = standards_paragraphs_for_accounts(
            account_key_for_statement(item) for item in statements
        )
    entries = []
    notes = []
    judgment_items = []

    for item in statements:
        account_key = account_key_for_statement(item)
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
                entry["calculation"] = "리스료 현재가치에서 K-GAAP 장부금액을 차감해 조정액을 산출했습니다."
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
