"""프로젝트 CRUD 라우트.

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
    Depends,
    Extraction,
    Project,
    ProjectCreateRequest,
    Review,
    Session,
    Statement,
    Upload,
    delete,
    get_db,
    get_project_or_404,
    load_project_statements,
    log_event,
    parse_json_field,
    require_user,
    require_write_user,
    row_to_dict,
    select,
    upload_public_dict,
    utc_now,
    uuid,
)

router = APIRouter()

# --- 프로젝트 ---

@router.get("/api/projects")
def list_projects(user: AppUser = Depends(require_user), session: Session = Depends(get_db)):
    projects = session.scalars(
        select(Project).where(Project.owner_user_id == user.id).order_by(Project.created_at.desc())
    )
    return [row_to_dict(project) for project in projects]


@router.post("/api/projects", status_code=201)
def create_project(
    payload: ProjectCreateRequest,
    user: AppUser = Depends(require_write_user),
    session: Session = Depends(get_db),
):
    now = utc_now()
    project = Project(
        id=str(uuid.uuid4()),
        owner_user_id=user.id,
        is_test=False,
        company_name=payload.company_name or "Untitled company",
        source_standard=payload.source_standard or "K-GAAP",
        target_standard=payload.target_standard or "IFRS",
        period=payload.period or "2026",
        status="created",
        created_at=now,
        updated_at=now,
    )
    session.add(project)
    session.flush()  # audit_logs의 project_id 외래키가 유효하도록 먼저 반영
    payload_dict = row_to_dict(project)
    log_event(session, project.id, "project.created", payload_dict)
    session.commit()
    return payload_dict


@router.get("/api/projects/{project_id}")
def get_project(project_id: str, user: AppUser = Depends(require_user), session: Session = Depends(get_db)):
    project = get_project_or_404(session, project_id, owner_user_id=user.id)
    statements = load_project_statements(session, project_id)
    uploads = [
        upload_public_dict(upload)
        for upload in session.scalars(
            select(Upload).where(Upload.project_id == project_id).order_by(Upload.created_at.desc())
        )
    ]
    extractions = [
        dict(
            row_to_dict(extraction),
            rows=parse_json_field(extraction.rows_json, []),
            issues=parse_json_field(extraction.issues_json, []),
        )
        for extraction in session.scalars(
            select(Extraction).where(Extraction.project_id == project_id).order_by(Extraction.created_at.desc())
        )
    ]
    conversion = session.scalar(
        select(Conversion).where(Conversion.project_id == project_id).order_by(Conversion.created_at.desc()).limit(1)
    )
    review = session.scalar(
        select(Review).where(Review.project_id == project_id).order_by(Review.created_at.desc()).limit(1)
    )
    return {
        "project": row_to_dict(project),
        "statements": statements,
        "uploads": uploads,
        "extractions": extractions,
        "conversion": parse_json_field(conversion.output_json, None) if conversion else None,
        "review": row_to_dict(review) if review else None,
    }


@router.delete("/api/projects/{project_id}")
def delete_project(project_id: str, user: AppUser = Depends(require_write_user), session: Session = Depends(get_db)):
    get_project_or_404(session, project_id, owner_user_id=user.id)
    stored_names = list(session.scalars(select(Upload.stored_name).where(Upload.project_id == project_id)))
    # 외래키 순서: 자식 테이블부터 지우고 마지막에 프로젝트를 지운다.
    for model in (Extraction, Upload, Statement, Conversion, Review, AuditLog):
        session.execute(delete(model).where(model.project_id == project_id))
    session.execute(delete(Project).where(Project.id == project_id, Project.owner_user_id == user.id))
    session.commit()
    for stored_name in stored_names:
        if stored_name:
            try:
                (server.UPLOAD_DIR / stored_name).unlink(missing_ok=True)
            except OSError:
                pass
    return {"deleted": True, "project_id": project_id}


