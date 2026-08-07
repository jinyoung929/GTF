"""React 정적 파일·SPA 진입점 라우트.

server.py 마지막 줄의 register_routers()가 이 모듈을 import하므로, 이 시점에는
server의 모든 이름이 정의돼 있어 순환 import가 안전하다.
"""

from fastapi import APIRouter

from server import (  # noqa: E501
    APP_JS,
    FileResponse,
    HTMLResponse,
    HTTPException,
    INDEX_HTML,
    PlainTextResponse,
    STYLES_CSS,
    figma_static_file,
    os,
    uvicorn,
)

router = APIRouter()

# --- 정적 파일(React 빌드)·SPA 진입점 — API 라우트보다 뒤에 두어야 catch-all이 API를 가리지 않는다 ---

@router.get("/styles.css")
def styles():
    return PlainTextResponse(STYLES_CSS, media_type="text/css")


@router.get("/app.js")
def script():
    return PlainTextResponse(APP_JS, media_type="application/javascript")


@router.get("/{full_path:path}")
def serve_frontend(full_path: str):
    """React 빌드 정적 파일을 서빙하고, 없으면 SPA 진입점(index.html)을 돌려준다."""
    static = figma_static_file("/" + full_path)
    if static is not None:
        cache = "no-cache" if static.name == "index.html" else "public, max-age=31536000, immutable"
        return FileResponse(static, headers={"Cache-Control": cache})
    if full_path.startswith("api/"):
        raise HTTPException(404, {"error": "Not found"})
    index = figma_static_file("/")
    return FileResponse(index, headers={"Cache-Control": "no-cache"}) if index else HTMLResponse(INDEX_HTML)


def main() -> None:
    port = int(os.environ.get("PORT", "4173"))
    host = os.environ.get("HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
