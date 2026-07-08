from __future__ import annotations

import io
import json
import os
import re
import ssl
import zipfile
from datetime import date
import xml.etree.ElementTree as ET
from urllib import error as url_error
from urllib import request as url_request
from urllib.parse import quote

from gtf_app.domain import normalize_account_name, parse_amount


DART_API_ENDPOINT = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
DART_CORP_CODE_ENDPOINT = "https://opendart.fss.or.kr/api/corpCode.xml"
DART_DISCLOSURE_LIST_ENDPOINT = "https://opendart.fss.or.kr/api/list.json"

REPORT_LABELS = {
    "11013": "1분기보고서",
    "11012": "반기보고서",
    "11014": "3분기보고서",
    "11011": "사업보고서",
}


def dart_report_code(value: str) -> str:
    aliases = {
        "q1": "11013",
        "1q": "11013",
        "1분기": "11013",
        "quarter1": "11013",
        "half": "11012",
        "h1": "11012",
        "반기": "11012",
        "q3": "11014",
        "3q": "11014",
        "3분기": "11014",
        "annual": "11011",
        "year": "11011",
        "사업보고서": "11011",
    }
    text = re.sub(r"\s+", "", str(value or "")).lower()
    if text in {"11013", "11012", "11014", "11011"}:
        return text
    return aliases.get(text, "11011")


def dart_report_code_from_name(report_name: str) -> str:
    compact = re.sub(r"\s+", "", str(report_name or ""))
    period_match = re.search(r"\((\d{4})[./-]?(\d{2})\)", str(report_name or ""))
    period_month = period_match.group(2) if period_match else ""
    if "1분기" in compact:
        return "11013"
    if "반기" in compact:
        return "11012"
    if "3분기" in compact:
        return "11014"
    if "분기보고서" in compact:
        return "11013" if period_month == "03" else "11014"
    if "사업보고서" in compact:
        return "11011"
    return ""


def dart_business_year_from_report(report_name: str, receipt_date: str) -> str:
    text = str(report_name or "")
    match = re.search(r"\((\d{4})[./-]?\d{0,2}\)", text)
    if match:
        return match.group(1)
    receipt_year = str(receipt_date or "")[:4]
    if re.fullmatch(r"\d{4}", receipt_year):
        return str(int(receipt_year) - 1) if "사업보고서" in text else receipt_year
    return ""


def dart_fs_div(value: str) -> str:
    text = re.sub(r"\s+", "", str(value or "")).upper()
    aliases = {
        "CFS": "CFS",
        "연결": "CFS",
        "CONSOLIDATED": "CFS",
        "OFS": "OFS",
        "별도": "OFS",
        "SEPARATE": "OFS",
    }
    return aliases.get(text, "CFS")


def dart_ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def dart_json_request(url: str, params: dict[str, str], timeout: int = 30) -> dict:
    query = "&".join(f"{key}={quote(str(value))}" for key, value in params.items() if value is not None)
    request = url_request.Request(f"{url}?{query}", headers={"Accept": "application/json"})
    with url_request.urlopen(request, timeout=timeout, context=dart_ssl_context()) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_dart_amount(value) -> float:
    text = str(value or "").strip()
    if text in {"", "-"}:
        return 0.0
    return parse_amount(text)


def dart_structural_exclusion_reason(name: str) -> str:
    compact = re.sub(r"\s+", "", str(name or ""))
    exclusions = {
        "자산총계",
        "부채총계",
        "자본총계",
        "부채와자본총계",
        "유동자산",
        "비유동자산",
        "유동부채",
        "비유동부채",
        "지배기업소유주지분",
        "비지배지분",
        "자본금",
        "자본잉여금",
        "기타자본항목",
        "기타포괄손익누계액",
        "이익잉여금",
        "매출총이익",
        "영업이익",
        "법인세비용차감전순이익",
        "당기순이익",
        "총포괄손익",
        "기본주당이익",
        "희석주당이익",
    }
    structural_tokens = ("총계", "총포괄", "주당", "영업활동", "투자활동", "재무활동")
    if compact in exclusions or any(token in compact for token in structural_tokens):
        return "합계/소계/성과지표/현금흐름표 활동 항목"
    return ""


def dart_reference_only_reason(name: str) -> str:
    compact = re.sub(r"\s+", "", str(name or ""))
    reference_tokens = (
        "매출원가",
        "판매비와관리비",
        "법인세",
        "기타수익",
        "기타비용",
        "금융수익",
        "금융비용",
        "이자수익",
        "이자비용",
        "배당금수익",
        "평가손익",
        "처분손익",
        "위험회피",
        "기타포괄손익",
    )
    if any(token in compact for token in reference_tokens):
        return "현재 MVP 변환 후보에서는 제외하지만 검토 참고로 보존할 수 있는 항목"
    return ""


def dart_account_key(name: str, aliases: dict) -> str:
    compact = re.sub(r"\s+", "", str(name or ""))
    if not compact:
        return "other"
    if dart_structural_exclusion_reason(name) or dart_reference_only_reason(name):
        return "other"
    return normalize_account_name(name, aliases)


def dart_account_filter_reason(item: dict, aliases: dict) -> str:
    name = str(item.get("account_nm") or "").strip()
    if not name:
        return "계정명 없음"
    structural_reason = dart_structural_exclusion_reason(name)
    if structural_reason:
        return structural_reason
    reference_reason = dart_reference_only_reason(name)
    if reference_reason:
        return reference_reason
    account_key = normalize_account_name(name, aliases)
    if account_key == "other":
        return "현재 표준계정 사전에 없는 계정"
    amount = normalize_dart_amount(item.get("thstrm_amount"))
    if amount == 0 and account_key not in {"cash", "receivables", "inventory", "revenue"}:
        return "금액 0인 판단형 계정"
    statement = str(item.get("sj_div") or item.get("sj_nm") or "")
    if "CF" in statement.upper() or "현금흐름" in statement:
        return "현금흐름표 항목"
    return ""


def should_keep_dart_account(item: dict, aliases: dict) -> bool:
    return not dart_account_filter_reason(item, aliases)


def summarize_filter_reasons(reasons: dict[str, int]) -> str:
    if not reasons:
        return ""
    parts = [f"{reason} {count}개" for reason, count in sorted(reasons.items(), key=lambda item: (-item[1], item[0]))]
    return "제외 사유: " + ", ".join(parts)


def dart_raw_statement_rows(payload: dict, aliases: dict) -> list[dict]:
    rows: list[dict] = []
    for item in payload.get("list") or []:
        account_name = str(item.get("account_nm") or "").strip()
        if not account_name:
            continue
        filter_reason = dart_account_filter_reason(item, aliases)
        rows.append(
            {
                "account_name": account_name,
                "amount": normalize_dart_amount(item.get("thstrm_amount")),
                "statement_type": item.get("sj_nm") or item.get("sj_div") or "",
                "currency": item.get("currency") or "KRW",
                "dart_account_id": item.get("account_id") or "",
                "account_key": dart_account_key(account_name, aliases),
                "conversion_candidate": not bool(filter_reason),
                "filter_reason": filter_reason,
                "source": "dart_api_raw",
            }
        )
    return rows


def dart_statement_rows(payload: dict, aliases: dict) -> tuple[list[dict], list[str]]:
    status = str(payload.get("status") or "")
    message = str(payload.get("message") or "").strip()
    if status and status != "000":
        return [], [f"DART API 오류 {status}: {message or '상세 메시지 없음'}"]

    rows: list[dict] = []
    issues: list[str] = []
    seen: set[tuple[str, str]] = set()
    total_count = 0
    skipped_count = 0
    skip_reasons: dict[str, int] = {}
    for item in payload.get("list") or []:
        total_count += 1
        account_name = str(item.get("account_nm") or "").strip()
        amount = normalize_dart_amount(item.get("thstrm_amount"))
        if not account_name:
            skipped_count += 1
            skip_reasons["계정명 없음"] = skip_reasons.get("계정명 없음", 0) + 1
            continue
        account_key = dart_account_key(account_name, aliases)
        filter_reason = dart_account_filter_reason(item, aliases)
        if filter_reason:
            skipped_count += 1
            skip_reasons[filter_reason] = skip_reasons.get(filter_reason, 0) + 1
            continue
        key = (account_name, str(item.get("sj_div") or item.get("sj_nm") or ""))
        if key in seen:
            skipped_count += 1
            skip_reasons["중복 계정"] = skip_reasons.get("중복 계정", 0) + 1
            continue
        seen.add(key)
        rows.append(
            {
                "account_name": account_name,
                "amount": amount,
                "statement_type": item.get("sj_nm") or item.get("sj_div") or "",
                "currency": item.get("currency") or "KRW",
                "dart_account_id": item.get("account_id") or "",
                "account_key": account_key,
                "source": "dart_api",
            }
        )

    if total_count:
        issues.append(f"DART 원본 {total_count}개 계정 중 변환 대상 핵심 계정 {len(rows)}개를 선별했습니다. 제외 {skipped_count}개.")
        reason_summary = summarize_filter_reasons(skip_reasons)
        if reason_summary:
            issues.append(reason_summary)
    if not rows:
        issues.append(message or "DART API 응답에서 계정 행을 찾지 못했습니다.")
    return rows, issues


def parse_dart_corp_codes(zip_bytes: bytes) -> list[dict]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        xml_name = next((name for name in archive.namelist() if name.lower().endswith(".xml")), "")
        if not xml_name:
            return []
        root = ET.fromstring(archive.read(xml_name))
    companies = []
    for item in root.findall(".//list"):
        company = {
            "corp_code": (item.findtext("corp_code") or "").strip(),
            "corp_name": (item.findtext("corp_name") or "").strip(),
            "stock_code": (item.findtext("stock_code") or "").strip(),
            "modify_date": (item.findtext("modify_date") or "").strip(),
        }
        if company["corp_code"]:
            companies.append(company)
    return companies


def lookup_dart_corp_code(api_key: str, company_name: str = "", stock_code: str = "") -> tuple[str, list[str]]:
    try:
        request = url_request.Request(f"{DART_CORP_CODE_ENDPOINT}?crtfc_key={quote(api_key)}")
        with url_request.urlopen(request, timeout=30, context=dart_ssl_context()) as response:
            companies = parse_dart_corp_codes(response.read())
    except url_error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")[:300]
        return "", [f"DART 고유번호 조회 실패: HTTP {exc.code}", message]
    except (url_error.URLError, TimeoutError, zipfile.BadZipFile, ET.ParseError) as exc:
        return "", [f"DART 고유번호 조회 실패: {exc}"]

    normalized_stock = re.sub(r"\D+", "", stock_code or "")
    normalized_name = re.sub(r"\s+", "", company_name or "").lower()
    for company in companies:
        if normalized_stock and company["stock_code"] == normalized_stock:
            return company["corp_code"], []
    for company in companies:
        if normalized_name and re.sub(r"\s+", "", company["corp_name"]).lower() == normalized_name:
            return company["corp_code"], []
    for company in companies:
        if normalized_name and normalized_name in re.sub(r"\s+", "", company["corp_name"]).lower():
            return company["corp_code"], []
    return "", ["회사명 또는 종목코드에 해당하는 DART 고유번호를 찾지 못했습니다."]


def fetch_dart_available_reports(payload: dict) -> tuple[list[dict], list[str], dict]:
    api_key = os.environ.get("DART_API_KEY", "").strip()
    if not api_key:
        return [], ["DART_API_KEY가 서버 환경변수에 설정되지 않았습니다."], {"api_key_ready": False}

    corp_code = str(payload.get("corp_code") or "").strip()
    company_name = str(payload.get("company_name") or "").strip()
    stock_code = str(payload.get("stock_code") or "").strip()
    lookup_issues: list[str] = []
    if not corp_code:
        corp_code, lookup_issues = lookup_dart_corp_code(api_key, company_name=company_name, stock_code=stock_code)
    if not corp_code:
        return [], lookup_issues or ["DART 고유번호 corp_code가 필요합니다."], {"api_key_ready": True}

    from_year = str(payload.get("from_year") or payload.get("bgn_year") or "")
    to_year = str(payload.get("to_year") or payload.get("end_year") or "")
    current_year = date.today().year
    if not re.fullmatch(r"\d{4}", from_year):
        from_year = str(current_year - 2)
    if not re.fullmatch(r"\d{4}", to_year):
        to_year = str(current_year)

    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": f"{from_year}0101",
        "end_de": f"{to_year}1231",
        "page_no": "1",
        "page_count": "100",
    }
    try:
        response_payload = dart_json_request(DART_DISCLOSURE_LIST_ENDPOINT, params)
    except url_error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")[:300]
        return [], [f"DART 보고서 목록 조회 실패: HTTP {exc.code}", message], {"api_key_ready": True, "corp_code": corp_code}
    except (url_error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return [], [f"DART 보고서 목록 조회 실패: {exc}"], {"api_key_ready": True, "corp_code": corp_code}

    status = str(response_payload.get("status") or "")
    message = str(response_payload.get("message") or "").strip()
    if status and status != "000":
        return [], [f"DART API 오류 {status}: {message or '보고서 목록을 찾지 못했습니다.'}"], {"api_key_ready": True, "corp_code": corp_code}

    reports: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in response_payload.get("list") or []:
        report_name = str(item.get("report_nm") or "").strip()
        report_code = dart_report_code_from_name(report_name)
        if not report_code:
            continue
        receipt_date = str(item.get("rcept_dt") or "").strip()
        business_year = dart_business_year_from_report(report_name, receipt_date)
        if not business_year:
            continue
        key = (business_year, report_code)
        if key in seen:
            continue
        seen.add(key)
        reports.append(
            {
                "corp_code": corp_code,
                "corp_name": item.get("corp_name") or company_name,
                "stock_code": stock_code,
                "bsns_year": business_year,
                "reprt_code": report_code,
                "reprt_name": REPORT_LABELS[report_code],
                "report_name": report_name,
                "receipt_no": item.get("rcept_no") or "",
                "receipt_date": receipt_date,
            }
        )

    reports.sort(key=lambda report: (report["bsns_year"], report["reprt_code"], report["receipt_date"]), reverse=True)
    issues = [*lookup_issues]
    if not reports:
        issues.append("조회 가능한 사업보고서/분기보고서/반기보고서를 찾지 못했습니다.")
    return reports, issues, {"api_key_ready": True, "corp_code": corp_code, "from_year": from_year, "to_year": to_year}


def fetch_dart_statement_rows(payload: dict, aliases: dict) -> tuple[list[dict], list[str], dict]:
    api_key = os.environ.get("DART_API_KEY", "").strip()
    if not api_key:
        return [], ["DART_API_KEY가 서버 환경변수에 설정되지 않았습니다."], {"api_key_ready": False}

    corp_code = str(payload.get("corp_code") or "").strip()
    company_name = str(payload.get("company_name") or "").strip()
    stock_code = str(payload.get("stock_code") or "").strip()
    lookup_issues: list[str] = []
    if not corp_code:
        corp_code, lookup_issues = lookup_dart_corp_code(api_key, company_name=company_name, stock_code=stock_code)
    if not corp_code:
        return [], lookup_issues or ["DART 고유번호 corp_code가 필요합니다."], {"api_key_ready": True}

    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bsns_year": str(payload.get("bsns_year") or payload.get("business_year") or payload.get("period") or ""),
        "reprt_code": dart_report_code(str(payload.get("reprt_code") or payload.get("report_code") or "11011")),
        "fs_div": dart_fs_div(str(payload.get("fs_div") or payload.get("statement_scope") or "CFS")),
    }
    if not re.fullmatch(r"\d{4}", params["bsns_year"]):
        return [], ["사업연도 bsns_year는 4자리 연도여야 합니다."], {"api_key_ready": True, "corp_code": corp_code}

    try:
        response_payload = dart_json_request(DART_API_ENDPOINT, params)
    except url_error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")[:300]
        return [], [f"DART 재무제표 조회 실패: HTTP {exc.code}", message], {"api_key_ready": True, "corp_code": corp_code, **params}
    except (url_error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return [], [f"DART 재무제표 조회 실패: {exc}"], {"api_key_ready": True, "corp_code": corp_code, **params}

    raw_rows = dart_raw_statement_rows(response_payload, aliases)
    rows, issues = dart_statement_rows(response_payload, aliases)
    metadata = {
        "api_key_ready": True,
        "corp_code": corp_code,
        "company_name": company_name,
        "stock_code": stock_code,
        "bsns_year": params["bsns_year"],
        "reprt_code": params["reprt_code"],
        "fs_div": params["fs_div"],
        "dart_status": response_payload.get("status"),
        "dart_message": response_payload.get("message"),
        "raw_row_count": len(raw_rows),
        "filtered_row_count": len(rows),
        "raw_rows": raw_rows,
    }
    return rows, [*lookup_issues, *issues], metadata


def dart_raw_rows_from_upload(upload: dict | None) -> list[dict]:
    if not upload:
        return []
    file_bytes = upload.get("file_bytes")
    if isinstance(file_bytes, memoryview):
        file_bytes = file_bytes.tobytes()
    if not isinstance(file_bytes, bytes):
        return []
    try:
        payload = json.loads(file_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    raw_rows = payload.get("raw_rows")
    return raw_rows if isinstance(raw_rows, list) else []
