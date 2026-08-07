"""인증(로그인·데모·로그아웃) 라우트.

server.py 마지막 줄의 register_routers()가 이 모듈을 import하므로, 이 시점에는
server의 모든 이름이 정의돼 있어 순환 import가 안전하다.
"""

from fastapi import APIRouter

from server import (  # noqa: E501
    AppUser,
    Depends,
    HTTPException,
    LoginRequest,
    Request,
    Response,
    SESSION_COOKIE,
    Session,
    UserSession,
    admin_config,
    create_login_session,
    current_user,
    delete,
    ensure_admin_user,
    ensure_demo_user,
    get_db,
    normalize_email,
    request_is_https,
    row_to_dict,
    select,
    session_token_hash,
    set_session_cookie,
    user_public_dict,
    verify_password,
)

router = APIRouter()

# --- 인증 ---

@router.get("/api/auth/session")
def auth_session(user: AppUser | None = Depends(current_user)):
    return {
        "authenticated": bool(user),
        "user": user_public_dict(row_to_dict(user)) if user else None,
        "admin_configured": admin_config()["configured"],
    }


@router.post("/api/auth/login")
def login(payload: LoginRequest, request: Request, response: Response, session: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    if not email or not payload.password:
        raise HTTPException(400, {"error": "이메일과 비밀번호를 입력하세요."})
    ensure_admin_user(session)
    user = session.scalar(select(AppUser).where(AppUser.email == email))
    if not user and not admin_config()["configured"]:
        raise HTTPException(503, {"error": "관리자 계정이 설정되지 않았습니다. ADMIN_EMAIL과 ADMIN_PASSWORD를 서버 환경변수에 설정하세요."})
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, {"error": "이메일 또는 비밀번호가 올바르지 않습니다."})
    token = create_login_session(session, user.id)
    set_session_cookie(response, token, secure=request_is_https(request))
    return {"authenticated": True, "user": user_public_dict(row_to_dict(user))}


@router.post("/api/auth/demo")
def demo_login(request: Request, response: Response, session: Session = Depends(get_db)):
    ensure_admin_user(session)
    user = ensure_demo_user(session)
    if not user:
        raise HTTPException(403, {"error": "데모 로그인이 비활성화되어 있습니다."})
    token = create_login_session(session, user["id"])
    set_session_cookie(response, token, secure=request_is_https(request))
    return {"authenticated": True, "user": user_public_dict(user), "demo": True}


@router.post("/api/auth/logout")
def logout(request: Request, response: Response, session: Session = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE, "")
    if token:
        session.execute(delete(UserSession).where(UserSession.token_hash == session_token_hash(token)))
        session.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"authenticated": False, "user": None}


