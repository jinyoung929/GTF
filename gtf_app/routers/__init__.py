"""도메인별 APIRouter 묶음.

register_routers()는 server.py 마지막 줄에서 호출된다 — 함수 안에서 import하므로
그 시점에는 server 모듈이 완전히 초기화돼 있어 순환 import가 안전하다.
등록 순서 중요: frontend의 catch-all(/{full_path:path})이 반드시 마지막이어야
API 경로를 가리지 않는다.
"""


def register_routers(app):
    from . import auth, conversion, frontend, projects, reference, sources, statements, system

    for module in (system, auth, reference, projects, sources, statements, conversion, frontend):
        app.include_router(module.router)
