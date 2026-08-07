"""변환·검토·감사로그·내보내기 라우트.

server.py 마지막 줄의 register_routers()가 이 모듈을 import하므로, 이 시점에는
server의 모든 이름이 정의돼 있어 순환 import가 안전하다.
"""

from fastapi import APIRouter

# 주의: REFERENCE·UPLOAD_DIR처럼 server가 런타임에 재바인딩하는 전역은
# from-import(값 스냅샷)하면 안 된다 — 항상 server.<이름>으로 접근한다.
import server

from server import (  # noqa: E501
    AppUser,
    AuditLog,
    Conversion,
    ConvertRequest,
    Depends,
    Extraction,
    HTTPException,
    Project,
    Response,
    Review,
    ReviewRequest,
    Session,
    Statement,
    Upload,
    build_review_summary,
    call_ai_judgment,
    compare_policy_scenarios,
    conversion_adjustments_csv,
    conversion_basis_report,
    dart_raw_rows_from_upload,
    func,
    generate_conversion,
    get_db,
    get_owned_project,
    json,
    load_project_statements,
    log_event,
    parse_json_field,
    require_user,
    require_write_user,
    review_workbook_bytes,
    row_to_dict,
    select,
    select_supplementary_paragraphs,
    semantic_search_paragraphs,
    sort_statements_by_code,
    update,
    utc_now,
    uuid,
    validate_statement_records,
)

router = APIRouter()

# --- 변환·검토 ---

@router.post("/api/projects/{project_id}/policy-comparison")
def policy_comparison(
    project_id: str,
    payload: ConvertRequest,
    user: AppUser = Depends(require_user),
    session: Session = Depends(get_db),
    project: Project = Depends(get_owned_project),
):
    """선택가능 회계정책(원가/재평가, 원가/공정가치, 자산차감/이연수익)의 영향 비교.

    결정론 계산기를 선택지별 입력으로 재실행하는 조회성 산출 — 저장·확정 없음(읽기 전용도 허용).
    """
    statements = load_project_statements(session, project_id)
    return compare_policy_scenarios(row_to_dict(project), statements, payload.responses or {}, server.REFERENCE)


@router.post("/api/projects/{project_id}/convert")
def convert_project(
    project_id: str,
    payload: ConvertRequest,
    user: AppUser = Depends(require_write_user),
    session: Session = Depends(get_db),
    project_row: Project = Depends(get_owned_project),
):
    responses = payload.responses or {}
    project = row_to_dict(project_row)
    statement_rows = load_project_statements(session, project_id)
    output = generate_conversion(project, statement_rows, responses, server.REFERENCE)
    # RAG: 판단 필요 항목마다 계정명·근거를 질의로 관련 기준서 문단을 시맨틱 검색해
    # AI 판단 보조의 근거(context)로 주입한다. 검색 결과는 조정 금액이 아니라 근거 설명에만 쓰인다.
    retrieved_context = []
    for jitem in output["judgment_items"]:
        query = f"{jitem.get('account', '')} {jitem.get('basis', '')}".strip()
        paras = semantic_search_paragraphs(session, query, k=5) if query else []
        paras = select_supplementary_paragraphs(paras)
        retrieved_context.append(
            {
                "account": jitem.get("account"),
                "paragraphs": [
                    {
                        "standard_set": p.get("standard_set"),
                        "reference_code": p.get("reference_code"),
                        "title": p.get("title"),
                        "content": p.get("content"),
                        "retrieval": p.get("retrieval"),
                        "similarity": p.get("similarity"),
                    }
                    for p in paras
                ],
            }
        )
    output["ai_assistance"] = call_ai_judgment(project, output["entries"], output["judgment_items"], retrieved_context)
    output["retrieved_context"] = retrieved_context

    session.add(
        Conversion(
            id=str(uuid.uuid4()),
            project_id=project_id,
            output_json=json.dumps(output, ensure_ascii=False),
            created_at=utc_now(),
        )
    )
    session.execute(update(Project).where(Project.id == project_id).values(status="draft_generated", updated_at=utc_now()))
    log_event(
        session,
        project_id,
        "conversion.generated",
        {
            "responses": responses,
            "entry_count": len(output["entries"]),
            "template": output["statement_template"],
            "ai_status": output["ai_assistance"].get("status"),
        },
    )
    session.commit()
    return output


@router.get("/api/projects/{project_id}/review-summary")
def review_summary(project_id: str, user: AppUser = Depends(require_user), session: Session = Depends(get_db), project: Project = Depends(get_owned_project)):
    statements = sort_statements_by_code([
        row_to_dict(statement)
        for statement in session.scalars(select(Statement).where(Statement.project_id == project_id))
    ])
    conversion_row = session.scalar(
        select(Conversion).where(Conversion.project_id == project_id).order_by(Conversion.created_at.desc()).limit(1)
    )
    validation = validate_statement_records(row_to_dict(project), statements) if statements else None
    conversion = parse_json_field(conversion_row.output_json, {}) if conversion_row else None
    return build_review_summary(statements, conversion, validation)


@router.post("/api/projects/{project_id}/review", status_code=201)
def record_review(
    project_id: str,
    payload: ReviewRequest,
    user: AppUser = Depends(require_write_user),
    session: Session = Depends(get_db),
    _owned: Project = Depends(get_owned_project),
):
    if payload.decision not in {"approved", "changes_requested"}:
        raise HTTPException(400, {"error": "Decision must be approved or changes_requested."})

    reviewer_name = payload.reviewer_name.strip() or "Unassigned reviewer"
    memo = payload.memo.strip()
    conversion = session.scalar(
        select(Conversion).where(Conversion.project_id == project_id).order_by(Conversion.created_at.desc()).limit(1)
    )
    if not conversion:
        raise HTTPException(400, {"error": "Generate a conversion draft before review."})
    if payload.decision == "approved":
        # 2차 승인 게이트: 오류 수준(미분류 잔존)은 승인을 차단, 경고는 검토자 판단에 맡긴다.
        unclassified = session.scalar(
            select(func.count())
            .select_from(Statement)
            .where(Statement.project_id == project_id, Statement.standard_code == "X9999")
        )
        if unclassified:
            raise HTTPException(
                409,
                {
                    "error": f"미분류 계정 {unclassified}건이 남아 있어 승인할 수 없습니다. 담당자 분류 또는 AI 제안 승인(1차 승인) 후 다시 시도하세요.",
                    "unclassified_count": unclassified,
                },
            )
    review = Review(
        id=str(uuid.uuid4()),
        project_id=project_id,
        reviewer_name=reviewer_name,
        decision=payload.decision,
        memo=memo,
        created_at=utc_now(),
    )
    session.add(review)
    session.execute(update(Project).where(Project.id == project_id).values(status=payload.decision, updated_at=utc_now()))
    log_event(
        session,
        project_id,
        "review.recorded",
        {"review_id": review.id, "decision": payload.decision, "memo": memo, "conversion_id": conversion.id},
        actor=reviewer_name,
    )
    body = row_to_dict(review)
    session.commit()
    return body


@router.get("/api/projects/{project_id}/audit")
def list_audit(project_id: str, user: AppUser = Depends(require_user), session: Session = Depends(get_db), _owned: Project = Depends(get_owned_project)):
    logs = session.scalars(
        select(AuditLog).where(AuditLog.project_id == project_id).order_by(AuditLog.created_at.desc())
    )
    return [dict(row_to_dict(log), detail=parse_json_field(log.detail_json, {})) for log in logs]


# --- 내보내기 ---

@router.get("/api/projects/{project_id}/exports/{export_name}")
def export_project(
    project_id: str,
    export_name: str,
    user: AppUser = Depends(require_user),
    session: Session = Depends(get_db),
    _owned: Project = Depends(get_owned_project),
):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, {"error": "Project not found"})
    conversion = session.scalar(
        select(Conversion).where(Conversion.project_id == project_id).order_by(Conversion.created_at.desc()).limit(1)
    )
    if not conversion:
        raise HTTPException(400, {"error": "Generate a conversion draft before export."})

    output = parse_json_field(conversion.output_json, {})
    if export_name == "adjustments.csv":
        return Response(
            content=conversion_adjustments_csv(output).encode("utf-8-sig"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="gtf_adjustments.csv"'},
        )
    if export_name == "basis-report.txt":
        return Response(
            content=conversion_basis_report(output),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="gtf_basis_report.txt"'},
        )
    if export_name == "review-workbook.xlsx":
        statements = load_project_statements(session, project_id)
        latest = session.execute(
            select(Extraction.rows_json, Upload.file_bytes)
            .join(Upload, Upload.id == Extraction.upload_id, isouter=True)
            .where(Extraction.project_id == project_id)
            .order_by(Extraction.created_at.desc())
            .limit(1)
        ).first()
        audit_rows = [
            dict(row_to_dict(log), detail=parse_json_field(log.detail_json, {}))
            for log in session.scalars(
                select(AuditLog).where(AuditLog.project_id == project_id).order_by(AuditLog.created_at)
            )
        ]
        extraction_rows = dart_raw_rows_from_upload(dict(latest._mapping) if latest else None)
        if not extraction_rows and latest:
            extraction_rows = parse_json_field(latest.rows_json, [])
        workbook = review_workbook_bytes(row_to_dict(project), extraction_rows, statements, output, audit_rows)
        return Response(
            content=workbook,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="gtf_review_workbook.xlsx"'},
        )
    raise HTTPException(404, {"error": "Unknown export type"})


