from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets


def normalize_email(email: str) -> str:
    return re.sub(r"\s+", "", str(email or "")).lower()


def admin_config() -> dict:
    email = normalize_email(os.environ.get("ADMIN_EMAIL") or os.environ.get("GTF_ADMIN_EMAIL") or "")
    password = os.environ.get("ADMIN_PASSWORD") or os.environ.get("GTF_ADMIN_PASSWORD") or ""
    read_only_env = os.environ.get("ADMIN_READ_ONLY") or os.environ.get("GTF_ADMIN_READ_ONLY") or ""
    read_only = read_only_env.strip().lower() in {"1", "true", "yes", "on"} or email == "demo@gtf.local"
    return {
        "email": email,
        "password_ready": bool(password),
        "configured": bool(email and password),
        "read_only": read_only,
    }


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, salt, _digest = stored_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    return hmac.compare_digest(hash_password(password, salt), stored_hash)


def session_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def user_public_dict(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "is_read_only": bool(user.get("is_read_only")),
        "created_at": user["created_at"],
    }
