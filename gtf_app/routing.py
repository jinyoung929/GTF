from __future__ import annotations

import re
from dataclasses import dataclass


PUBLIC_PATHS = {
    "/",
    "/styles.css",
    "/app.js",
    "/healthz",
    "/api/access-config",
    "/api/auth/session",
    "/api/auth/login",
    "/api/auth/demo",
    "/api/auth/logout",
}


@dataclass(frozen=True)
class RouteMatch:
    name: str
    args: tuple[str, ...] = ()


def resolve_get(path: str) -> RouteMatch | None:
    exact = {
        "/": "index",
        "/healthz": "healthz",
        "/styles.css": "styles",
        "/app.js": "script",
        "/api/projects": "projects.list",
        "/api/ocr-config": "ocr.config",
        "/api/ai-config": "ai.config",
        "/api/dart-config": "dart.config",
        "/api/access-config": "access.config",
        "/api/auth/session": "auth.session",
        "/api/reference-data": "reference.data",
        "/api/standards/search": "standards.search",
    }
    if path in exact:
        return RouteMatch(exact[path])
    if re.match(r"^/api/projects/[^/]+$", path):
        return RouteMatch("projects.get", (path.split("/")[-1],))
    if re.match(r"^/api/projects/[^/]+/uploads$", path):
        return RouteMatch("uploads.list", (path.split("/")[-2],))
    if re.match(r"^/api/projects/[^/]+/extractions$", path):
        return RouteMatch("extractions.list", (path.split("/")[-2],))
    if re.match(r"^/api/projects/[^/]+/audit$", path):
        return RouteMatch("audit.list", (path.split("/")[-2],))
    if re.match(r"^/api/projects/[^/]+/exports/[^/]+$", path):
        parts = path.split("/")
        return RouteMatch("exports.get", (parts[3], parts[5]))
    return None


def resolve_post(path: str) -> RouteMatch | None:
    exact = {
        "/api/projects": "projects.create",
        "/api/auth/login": "auth.login",
        "/api/auth/demo": "auth.demo",
        "/api/auth/logout": "auth.logout",
    }
    if path in exact:
        return RouteMatch(exact[path])
    if re.match(r"^/api/projects/[^/]+/uploads$", path):
        return RouteMatch("uploads.create", (path.split("/")[-2],))
    if re.match(r"^/api/projects/[^/]+/uploads/[^/]+/extract$", path):
        parts = path.split("/")
        return RouteMatch("uploads.extract", (parts[3], parts[5]))
    if re.match(r"^/api/projects/[^/]+/dart/import$", path):
        return RouteMatch("dart.import", (path.split("/")[-3],))
    if re.match(r"^/api/projects/[^/]+/dart/reports$", path):
        return RouteMatch("dart.reports", (path.split("/")[-3],))
    if re.match(r"^/api/projects/[^/]+/extractions/[^/]+/accept$", path):
        parts = path.split("/")
        return RouteMatch("extractions.accept", (parts[-4], parts[-2]))
    if re.match(r"^/api/projects/[^/]+/statements$", path):
        return RouteMatch("statements.add", (path.split("/")[-2],))
    if re.match(r"^/api/projects/[^/]+/validate$", path):
        return RouteMatch("statements.validate", (path.split("/")[-2],))
    if re.match(r"^/api/projects/[^/]+/convert$", path):
        return RouteMatch("conversion.create", (path.split("/")[-2],))
    if re.match(r"^/api/projects/[^/]+/review$", path):
        return RouteMatch("reviews.create", (path.split("/")[-2],))
    return None


def resolve_delete(path: str) -> RouteMatch | None:
    if re.match(r"^/api/projects/[^/]+$", path):
        return RouteMatch("projects.delete", (path.split("/")[-1],))
    if re.match(r"^/api/projects/[^/]+/uploads/[^/]+$", path):
        parts = path.split("/")
        return RouteMatch("uploads.delete", (parts[3], parts[5]))
    return None
