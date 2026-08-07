"""업로드·추출·DART 연동 라우트.

server.py 마지막 줄의 register_routers()가 이 모듈을 import하므로, 이 시점에는
server의 모든 이름이 정의돼 있어 순환 import가 안전하다.
"""

from fastapi import APIRouter

# 주의: REFERENCE·UPLOAD_DIR처럼 server가 런타임에 재바인딩하는 전역은
# from-import(값 스냅샷)하면 안 된다 — 항상 server.<이름>으로 접근한다.
import server

from server import (  # noqa: E501
    AppUser,
    Body,
    Depends,
    Extraction,
    File,
    HTTPException,
    JSONResponse,
    Path,
    Project,
    Session,
    Upload,
    UploadFile,
    ai_classification_audit,
    attach_ai_classification,
    delete,
    extract_rows_from_upload,
    fetch_dart_available_reports,
    fetch_dart_statement_rows,
    func,
    get_db,
    get_owned_project,
    json,
    log_event,
    ocr_config,
    parse_json_field,
    re,
    require_user,
    require_write_user,
    row_to_dict,
    select,
    update,
    upload_public_dict,
    utc_now,
    uuid,
)

router = APIRouter()

# --- 업로드·추출 ---

@router.get("/api/projects/{project_id}/uploads")
def list_uploads(project_id: str, user: AppUser = Depends(require_user), session: Session = Depends(get_db), _owned: Project = Depends(get_owned_project)):
    uploads = session.scalars(
        select(Upload).where(Upload.project_id == project_id).order_by(Upload.created_at.desc())
    )
    return [upload_public_dict(upload) for upload in uploads]


@router.post("/api/projects/{project_id}/uploads", status_code=201)
def upload_file(
    project_id: str,
    file: UploadFile = File(...),
    user: AppUser = Depends(require_write_user),
    session: Session = Depends(get_db),
    _owned: Project = Depends(get_owned_project),
):

    original_name = file.filename or "upload.bin"
    content = file.file.read()
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(original_name).name).strip("._")
    stored_name = f"{project_id}_{uuid.uuid4()}_{safe_name or 'upload.bin'}"
    (server.UPLOAD_DIR / stored_name).write_bytes(content)

    upload = Upload(
        id=str(uuid.uuid4()),
        project_id=project_id,
        original_name=original_name,
        stored_name=stored_name,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        file_bytes=content,
        extraction_status="pending_ocr",
        created_at=utc_now(),
    )
    session.add(upload)
    session.execute(update(Project).where(Project.id == project_id).values(status="source_uploaded", updated_at=utc_now()))
    log_event(
        session,
        project_id,
        "source.uploaded",
        {
            "upload_id": upload.id,
            "original_name": original_name,
            "content_type": upload.content_type,
            "size_bytes": len(content),
            "next_step": "Gemini OCR extraction",
        },
    )
    public = upload_public_dict(upload)
    session.commit()
    return public


@router.delete("/api/projects/{project_id}/uploads/{upload_id}")
def delete_upload(
    project_id: str,
    upload_id: str,
    user: AppUser = Depends(require_write_user),
    session: Session = Depends(get_db),
    _owned: Project = Depends(get_owned_project),
):
    upload = session.scalar(select(Upload).where(Upload.id == upload_id, Upload.project_id == project_id))
    if not upload:
        raise HTTPException(404, {"error": "Upload not found"})
    stored_name = upload.stored_name
    original_name = upload.original_name

    session.execute(delete(Extraction).where(Extraction.upload_id == upload_id, Extraction.project_id == project_id))
    session.delete(upload)
    session.flush()
    remaining = session.scalar(select(func.count()).select_from(Upload).where(Upload.project_id == project_id))
    next_status = "created" if int(remaining or 0) == 0 else "source_uploaded"
    session.execute(update(Project).where(Project.id == project_id).values(status=next_status, updated_at=utc_now()))
    log_event(
        session,
        project_id,
        "source.deleted",
        {"upload_id": upload_id, "original_name": original_name, "remaining_uploads": remaining},
    )
    session.commit()
    if stored_name:
        try:
            (server.UPLOAD_DIR / stored_name).unlink(missing_ok=True)
        except OSError:
            pass
    return {"deleted": True, "upload_id": upload_id, "project_status": next_status}


@router.get("/api/projects/{project_id}/extractions")
def list_extractions(project_id: str, user: AppUser = Depends(require_user), session: Session = Depends(get_db), _owned: Project = Depends(get_owned_project)):
    extractions = session.scalars(
        select(Extraction).where(Extraction.project_id == project_id).order_by(Extraction.created_at.desc())
    )
    return [
        dict(
            row_to_dict(extraction),
            rows=parse_json_field(extraction.rows_json, []),
            issues=parse_json_field(extraction.issues_json, []),
        )
        for extraction in extractions
    ]


@router.post("/api/projects/{project_id}/uploads/{upload_id}/extract", status_code=201)
def extract_upload(
    project_id: str,
    upload_id: str,
    user: AppUser = Depends(require_write_user),
    session: Session = Depends(get_db),
    _owned: Project = Depends(get_owned_project),
):
    upload = session.scalar(select(Upload).where(Upload.id == upload_id, Upload.project_id == project_id))
    if not upload:
        raise HTTPException(404, {"error": "Upload not found"})

    config = ocr_config()
    rows, issues, provider = extract_rows_from_upload(row_to_dict(upload))
    rows, ai_classification = attach_ai_classification(rows, session)
    if ai_classification.get("status") != "skipped" and ai_classification.get("note"):
        issues = [*issues, ai_classification["note"]]
    status = "needs_review" if rows else "failed"
    extraction = Extraction(
        id=str(uuid.uuid4()),
        project_id=project_id,
        upload_id=upload_id,
        provider=provider,
        status=status,
        rows_json=json.dumps(rows, ensure_ascii=False),
        issues_json=json.dumps(issues, ensure_ascii=False),
        created_at=utc_now(),
    )
    session.add(extraction)
    upload.extraction_status = status
    session.execute(update(Project).where(Project.id == project_id).values(status="extracted", updated_at=utc_now()))
    log_event(
        session,
        project_id,
        "source.extracted",
        {
            "upload_id": upload_id,
            "extraction_id": extraction.id,
            "provider": provider,
            "ocr_config": config,
            "row_count": len(rows),
            "issues": issues,
            "ai_classification": ai_classification_audit(ai_classification),
        },
    )
    result = dict(row_to_dict(extraction), rows=rows, issues=issues)
    session.commit()
    return result


# --- DART 연동 ---

@router.post("/api/projects/{project_id}/dart/import")
def dart_import(
    project_id: str,
    payload: dict = Body(default={}),
    user: AppUser = Depends(require_write_user),
    session: Session = Depends(get_db),
    _owned: Project = Depends(get_owned_project),
):

    rows, issues, metadata = fetch_dart_statement_rows(payload, server.REFERENCE.aliases)
    rows, ai_classification = attach_ai_classification(rows, session)
    if ai_classification.get("status") != "skipped" and ai_classification.get("note"):
        issues = [*issues, ai_classification["note"]]
    raw_rows = metadata.pop("raw_rows", [])
    raw_payload = {"metadata": metadata, "raw_rows": raw_rows, "filtered_rows": rows, "issues": issues}
    raw_bytes = json.dumps(raw_payload, ensure_ascii=False).encode("utf-8")
    status = "needs_review" if rows else "failed"
    now = utc_now()

    upload = Upload(
        id=str(uuid.uuid4()),
        project_id=project_id,
        original_name=f"DART_API_{metadata.get('corp_code', 'unknown')}_{metadata.get('bsns_year', payload.get('bsns_year', 'unknown'))}.json",
        stored_name="",
        content_type="application/json",
        size_bytes=len(raw_bytes),
        file_bytes=raw_bytes,
        extraction_status=status,
        created_at=now,
    )
    session.add(upload)
    session.flush()
    extraction = Extraction(
        id=str(uuid.uuid4()),
        project_id=project_id,
        upload_id=upload.id,
        provider="dart_api",
        status=status,
        rows_json=json.dumps(rows, ensure_ascii=False),
        issues_json=json.dumps([*issues, json.dumps(metadata, ensure_ascii=False)], ensure_ascii=False),
        created_at=now,
    )
    session.add(extraction)
    next_status = "extracted" if rows else "source_import_failed"
    session.execute(update(Project).where(Project.id == project_id).values(status=next_status, updated_at=utc_now()))
    log_event(
        session,
        project_id,
        "dart.imported",
        {
            "upload_id": upload.id,
            "extraction_id": extraction.id,
            "row_count": len(rows),
            "raw_row_count": len(raw_rows),
            "issues": issues,
            "metadata": metadata,
            "ai_classification": ai_classification_audit(ai_classification),
        },
    )
    body = {
        **row_to_dict(extraction),
        "rows": rows,
        "issues": issues,
        "metadata": metadata,
        "upload": upload_public_dict(upload),
    }
    session.commit()
    return JSONResponse(status_code=201 if rows else 400, content=body)


@router.post("/api/projects/{project_id}/dart/reports")
def dart_reports(
    project_id: str,
    payload: dict = Body(default={}),
    user: AppUser = Depends(require_write_user),
    session: Session = Depends(get_db),
    _owned: Project = Depends(get_owned_project),
):
    reports, issues, metadata = fetch_dart_available_reports(payload)
    return {"reports": reports, "issues": issues, "metadata": metadata}


