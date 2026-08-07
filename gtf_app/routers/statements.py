"""계정 행 반영·분류·검증 라우트.

server.py 마지막 줄의 register_routers()가 이 모듈을 import하므로, 이 시점에는
server의 모든 이름이 정의돼 있어 순환 import가 안전하다.
"""

from fastapi import APIRouter

# 주의: REFERENCE·UPLOAD_DIR처럼 server가 런타임에 재바인딩하는 전역은
# from-import(값 스냅샷)하면 안 된다 — 항상 server.<이름>으로 접근한다.
import server

from server import (  # noqa: E501
    AcceptExtractionRequest,
    AddJudgmentAccountRequest,
    AppUser,
    ClassifyStatementRequest,
    Depends,
    Extraction,
    HTTPException,
    Project,
    Session,
    Statement,
    StatementsAddRequest,
    Upload,
    ai_classification_audit,
    apply_ai_decisions,
    attach_ai_classification,
    build_statement_record,
    get_db,
    get_owned_project,
    json,
    log_event,
    parse_json_field,
    parse_statement_rows,
    require_write_user,
    row_to_dict,
    select,
    update,
    utc_now,
    uuid,
    validate_statement_records,
)

router = APIRouter()

# --- 추출 반영(1차 승인)·수동 입력·검증 ---

@router.post("/api/projects/{project_id}/extractions/{extraction_id}/accept")
def accept_extraction(
    project_id: str,
    extraction_id: str,
    payload: AcceptExtractionRequest | None = None,
    user: AppUser = Depends(require_write_user),
    session: Session = Depends(get_db),
    _owned: Project = Depends(get_owned_project),
):
    ai_decisions = payload.ai_decisions if payload else None
    project = session.get(Project, project_id)
    extraction = session.scalar(
        select(Extraction).where(Extraction.id == extraction_id, Extraction.project_id == project_id)
    )
    if not project or not extraction:
        raise HTTPException(404, {"error": "Extraction not found"})

    rows = parse_json_field(extraction.rows_json, [])
    rows, decision_summary = apply_ai_decisions(rows, ai_decisions)
    records = [build_statement_record(project.period, row, server.REFERENCE) for row in rows]
    for record in records:
        session.add(
            Statement(
                id=record["id"],
                project_id=project_id,
                account_name=record["account_name"],
                normalized_account=record["normalized_account"],
                standard_code=record["standard_code"],
                amount=record["amount"],
                period=record["period"],
                mapping_type=record["mapping_type"],
                rule_summary=record["rule_summary"],
                checklist_json=json.dumps(record["checklist"], ensure_ascii=False),
                created_at=utc_now(),
            )
        )
    extraction.status = "accepted"
    project.status = "mapped"
    project.updated_at = utc_now()
    ai_confirmed = [
        {
            "account_name": record["account_name"],
            "suggested_account": record["normalized_account"],
            "confidence": (record.get("ai_suggestion") or {}).get("confidence"),
            "rationale": (record.get("ai_suggestion") or {}).get("rationale"),
        }
        for record in records
        if record.get("mapping_source") == "ai_suggested_human_accepted"
    ]
    log_event(
        session,
        project_id,
        "extraction.accepted",
        {
            "extraction_id": extraction_id,
            "statement_count": len(records),
            "ai_classified_count": len(ai_confirmed),
            "ai_classified_accounts": ai_confirmed,
            "ai_decision_summary": decision_summary,
            "ai_classification_note": (
                "AI 1차 분류 제안을 담당자가 계정별로 승인/거절하며 확정했습니다."
                if decision_summary["per_account_review"] and (ai_confirmed or decision_summary["rejected"])
                else "AI 1차 분류 제안을 담당자가 반영하며 확정했습니다." if ai_confirmed else None
            ),
        },
        actor=user.email or "system",
    )
    session.commit()
    return {"statements": records, "extraction_id": extraction_id, "ai_decision_summary": decision_summary}


@router.post("/api/projects/{project_id}/statements", status_code=201)
def add_statements(
    project_id: str,
    payload: StatementsAddRequest,
    user: AppUser = Depends(require_write_user),
    session: Session = Depends(get_db),
    _owned: Project = Depends(get_owned_project),
):
    raw_rows = parse_statement_rows(payload.model_dump())
    # 수동 입력도 파일/DART 경로와 동일하게 추출(extraction)로 만들어, 미분류 계정에
    # AI 1차 분류 제안을 붙이고 담당자가 추출 미리보기에서 계정별로 승인하도록 통일한다.
    raw_rows, ai_classification = attach_ai_classification(raw_rows, session)
    issues = []
    if ai_classification.get("status") != "skipped" and ai_classification.get("note"):
        issues.append(ai_classification["note"])
    status = "needs_review" if raw_rows else "failed"
    now = utc_now()

    upload = Upload(
        id=str(uuid.uuid4()),
        project_id=project_id,
        original_name="수동입력.csv",
        stored_name="",
        content_type="text/csv",
        size_bytes=0,
        extraction_status=status,
        created_at=now,
    )
    session.add(upload)
    session.flush()
    extraction = Extraction(
        id=str(uuid.uuid4()),
        project_id=project_id,
        upload_id=upload.id,
        provider="manual_input",
        status=status,
        rows_json=json.dumps(raw_rows, ensure_ascii=False),
        issues_json=json.dumps(issues, ensure_ascii=False),
        created_at=now,
    )
    session.add(extraction)
    session.execute(update(Project).where(Project.id == project_id).values(status="extracted", updated_at=now))
    log_event(
        session,
        project_id,
        "source.manual_entered",
        {
            "extraction_id": extraction.id,
            "row_count": len(raw_rows),
            "source": payload.source,
            "ai_classification": ai_classification_audit(ai_classification),
        },
    )
    extraction_id = extraction.id
    session.commit()
    return {
        "extraction_id": extraction_id,
        "rows": raw_rows,
        "issues": issues,
        "ai_classification_status": ai_classification.get("status"),
    }


@router.patch("/api/projects/{project_id}/statements/{statement_id}/classify")
def classify_statement(
    project_id: str,
    statement_id: str,
    payload: ClassifyStatementRequest,
    user: AppUser = Depends(require_write_user),
    session: Session = Depends(get_db),
    _owned: Project = Depends(get_owned_project),
):
    """반영된 계정 행을 담당자가 표준계정으로 재분류한다.

    검토 요약의 '미분류(X9999)' 오류 항목이 유도하는 행동. 재분류 전/후가 감사 로그에 남아
    'AI 제안 → 사람 확정'과 같은 원칙(분류 확정 권한은 사람, 과정은 기록)을 따른다.
    """
    statement = session.get(Statement, statement_id)
    if not statement or statement.project_id != project_id:
        raise HTTPException(404, {"error": "계정 행을 찾지 못했습니다."})
    account_key = payload.account_key.strip()
    if account_key == "out_of_scope":
        # 31개 표준계정 어디에도 해당하지 않는 계정의 정직한 출구. 억지 분류 대신
        # '범위 밖 · 별도 검토'로 확인하면 승인 차단이 풀리고, 확인 사실이 기록에 남는다.
        before = {"standard_code": statement.standard_code, "scope_status": statement.scope_status}
        statement.scope_status = "out_of_scope"
        statement.normalized_account = "범위 밖(별도 검토)"
        statement.rule_summary = "[범위 밖 확인] 이 도구의 표준계정 범위에 해당하지 않아 별도 검토 대상으로 확인되었습니다."
        log_event(
            session,
            project_id,
            "statement.scope_confirmed",
            {"statement_id": statement_id, "account_name": statement.account_name, "before": before},
            actor=user.email,
        )
        session.commit()
        return row_to_dict(statement)
    account = server.REFERENCE.accounts.get(account_key)
    if not account or account_key == "other":
        raise HTTPException(400, {"error": "유효한 표준계정 키가 아닙니다. 분류 가능한 계정 목록에서 선택하세요."})
    before = {"standard_code": statement.standard_code, "normalized_account": statement.normalized_account}
    statement.scope_status = ""  # 범위 밖으로 확인했던 행을 표준계정으로 재분류하면 확인을 해제한다
    checklist = server.REFERENCE.checklists.get(account_key, []) if account["type"] == "judgment" else []
    statement.normalized_account = account["label"]
    statement.standard_code = account["code"]
    statement.mapping_type = account["type"]
    statement.rule_summary = f"[담당자 재분류] {account['rule']}"
    statement.checklist_json = json.dumps(checklist, ensure_ascii=False)
    log_event(
        session,
        project_id,
        "statement.reclassified",
        {
            "statement_id": statement_id,
            "account_name": statement.account_name,
            "before": before,
            "after": {"standard_code": account["code"], "normalized_account": account["label"]},
        },
        actor=user.email,
    )
    session.commit()
    return row_to_dict(statement)


@router.post("/api/projects/{project_id}/statements/judgment", status_code=201)
def add_judgment_account(
    project_id: str,
    payload: AddJudgmentAccountRequest,
    user: AppUser = Depends(require_write_user),
    session: Session = Depends(get_db),
    _owned: Project = Depends(get_owned_project),
):
    """원본 재무제표에 행이 없는 판단 계정을 빈 상태로 추가한다(순수 신규 인식).

    운용리스처럼 K-GAAP 본문에 숫자가 없는 계정은 계정 데이터만 받는 흐름으로는 시작할
    입구가 없다. 검토자가 판단 계정 카탈로그에서 골라 추가하면 해당 체크리스트가 뜨고,
    변환 시 기존 결정론 계산기가 그대로 조정을 산출한다(리스 PV, 복구충당부채 등).
    억지 탐지 대신 '사람이 인지→입력, 시스템은 계산·근거'라는 경계를 지킨다.

    주의: 이미 본문에 있는 계정을 분리해야 하는 경우(전환사채 등)는 이 경로가 아니라
    기존 행 재분류로 처리한다. 이 엔드포인트는 '원본에 없던 계정의 신규 추가'만 담당한다.
    """
    account_key = payload.account_key.strip()
    account = server.REFERENCE.accounts.get(account_key)
    if not account or account_key in {"other", "out_of_scope"} or account["type"] != "judgment":
        raise HTTPException(400, {"error": "판단이 필요한 표준계정만 신규 추가할 수 있습니다."})
    project = session.get(Project, project_id)
    checklist = server.REFERENCE.checklists.get(account_key, [])
    statement = Statement(
        id=str(uuid.uuid4()),
        project_id=project_id,
        account_name=f"[신규 인식] {account['label']}",
        normalized_account=account["label"],
        standard_code=account["code"],
        amount=float(payload.amount),
        period=project.period,
        mapping_type="judgment",
        rule_summary=f"[신규 인식] 원본에 없어 검토자가 추가한 판단 계정입니다. {account['rule']}",
        checklist_json=json.dumps(checklist, ensure_ascii=False),
        created_at=utc_now(),
    )
    session.add(statement)
    if project.status == "draft":
        project.status = "mapped"
    project.updated_at = utc_now()
    log_event(
        session,
        project_id,
        "statement.judgment_added",
        {"statement_id": statement.id, "account_key": account_key, "label": account["label"], "amount": float(payload.amount)},
        actor=user.email,
    )
    session.commit()
    return row_to_dict(statement)


@router.post("/api/projects/{project_id}/validate")
def validate_project(project_id: str, user: AppUser = Depends(require_write_user), session: Session = Depends(get_db), project: Project = Depends(get_owned_project)):
    statements = [row_to_dict(s) for s in session.scalars(select(Statement).where(Statement.project_id == project_id))]
    result = validate_statement_records(row_to_dict(project), statements)
    log_event(session, project_id, "validation.completed", result)
    session.commit()
    return result


