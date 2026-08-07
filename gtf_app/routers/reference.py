"""기준정보·기준서 검색 라우트.

server.py 마지막 줄의 register_routers()가 이 모듈을 import하므로, 이 시점에는
server의 모든 이름이 정의돼 있어 순환 import가 안전하다.
"""

from fastapi import APIRouter

from server import (  # noqa: E501
    AppUser,
    ChecklistItem,
    Depends,
    FinancialStatementTemplate,
    HTTPException,
    KgaapAccount,
    Session,
    StandardAccount,
    StandardsParagraph,
    find_standards_paragraphs,
    func,
    get_db,
    require_user,
    select,
    semantic_search_paragraphs,
)

router = APIRouter()

# --- 기준정보·기준서 검색 ---

REFERENCE_TABLE_LABELS = [
    (StandardAccount, "내부 표준계정코드 DB"),
    (KgaapAccount, "K-GAAP 계정명 DB"),
    (ChecklistItem, "판단 체크리스트 DB"),
    (StandardsParagraph, "K-GAAP/K-IFRS 기준서 문단 검색 DB"),
    (FinancialStatementTemplate, "재무제표 양식 DB"),
]


@router.get("/api/reference-data")
def reference_data(user: AppUser = Depends(require_user), session: Session = Depends(get_db)):
    summary = [
        {
            "table": model.__tablename__,
            "label": label,
            "count": session.scalar(select(func.count()).select_from(model)),
        }
        for model, label in REFERENCE_TABLE_LABELS
    ]
    accounts = [
        dict(row._mapping)
        for row in session.execute(
            select(
                StandardAccount.account_key,
                StandardAccount.standard_code,
                StandardAccount.internal_label,
                StandardAccount.ifrs_account,
                StandardAccount.mapping_type,
            ).order_by(StandardAccount.standard_code)
        ).all()
    ]
    templates = [
        dict(row._mapping)
        for row in session.execute(
            select(
                FinancialStatementTemplate.statement_type,
                FinancialStatementTemplate.section,
                FinancialStatementTemplate.line_item,
                FinancialStatementTemplate.account_key,
                FinancialStatementTemplate.display_order,
            )
            .where(FinancialStatementTemplate.standard_set == "IFRS", FinancialStatementTemplate.active.is_(True))
            .order_by(FinancialStatementTemplate.statement_type, FinancialStatementTemplate.display_order)
        ).all()
    ]
    return {"summary": summary, "accounts": accounts, "templates": templates}


@router.get("/api/standards/search")
def standards_search(
    q: str = "",
    account_key: str = "",
    standard_set: str = "",
    user: AppUser = Depends(require_user),
    session: Session = Depends(get_db),
):
    query, account_key, standard_set = q.strip(), account_key.strip(), standard_set.strip()
    if standard_set and standard_set not in {"K-GAAP", "K-IFRS"}:
        raise HTTPException(400, {"error": "standard_set은 K-GAAP 또는 K-IFRS여야 합니다."})
    if query:
        paragraphs = semantic_search_paragraphs(
            session, query, account_key=account_key or None, standard_set=standard_set or None, k=8
        )
    else:
        paragraphs = find_standards_paragraphs(
            session, account_key=account_key or None, query=None, standard_set=standard_set or None
        )
    return {
        "count": len(paragraphs),
        "retrieval": paragraphs[0].get("retrieval", "none") if paragraphs else "none",
        "standard_sets": ["K-GAAP", "K-IFRS"],
        "paragraphs": paragraphs,
        "note": "기준서 문단 요약 기준정보입니다. 최종 판단 시 기준서 원문을 확인하세요.",
    }


