"""시스템 상태·설정 조회 라우트.

server.py 마지막 줄의 register_routers()가 이 모듈을 import하므로, 이 시점에는
server의 모든 이름이 정의돼 있어 순환 import가 안전하다.
"""

from fastapi import APIRouter

from server import (  # noqa: E501
    AppUser,
    Depends,
    ai_config,
    dart_config,
    database_config,
    database_ready,
    ocr_config,
    require_user,
    utc_now,
)

router = APIRouter()

# --- 헬스체크·설정 조회 ---

@router.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "service": "gtf-accounting-conversion",
        "time": utc_now(),
        "database": database_ready(),
        "database_config": database_config(),
        "ocr": ocr_config(),
        "ai": ai_config(),
        "dart": dart_config(),
    }


@router.get("/api/ocr-config")
def get_ocr_config(user: AppUser = Depends(require_user)):
    return ocr_config()


@router.get("/api/ai-config")
def get_ai_config(user: AppUser = Depends(require_user)):
    return ai_config()


@router.get("/api/dart-config")
def get_dart_config(user: AppUser = Depends(require_user)):
    return dart_config()


