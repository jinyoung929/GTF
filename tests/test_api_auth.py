import os
import tempfile
import unittest
from http import HTTPStatus
from pathlib import Path

import server


class HandlerHarness(server.AppHandler):
    def __init__(self, payload=None, user=None, path="/api/projects"):
        self.payload = payload or {}
        self.user = user
        self.path = path
        self.responses = []
        self.project_created = False

    def read_json(self):
        return self.payload

    def current_user(self):
        return self.user

    def respond_json(self, payload, status=HTTPStatus.OK, headers=None):
        self.responses.append({"payload": payload, "status": status, "headers": headers or {}})

    def handle_create_project(self):
        self.project_created = True
        self.respond_json({"id": "created"})


class ApiAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.old_db_path = server.DB_PATH
        self.old_data_dir = server.DATA_DIR
        self.old_upload_dir = server.UPLOAD_DIR
        self.old_env = {
            key: os.environ.get(key)
            for key in ("ADMIN_EMAIL", "ADMIN_PASSWORD", "ADMIN_READ_ONLY", "DEMO_EMAIL", "DEMO_PASSWORD", "DEMO_LOGIN_ENABLED")
        }
        server.DATA_DIR = Path(self.tmpdir.name)
        server.UPLOAD_DIR = server.DATA_DIR / "uploads"
        server.DB_PATH = server.DATA_DIR / "gtf.sqlite3"
        os.environ["ADMIN_EMAIL"] = "demo@gtf.local"
        os.environ["ADMIN_PASSWORD"] = "change-this-demo-password"
        os.environ.pop("ADMIN_READ_ONLY", None)
        server.init_db()

    def tearDown(self):
        server.DB_PATH = self.old_db_path
        server.DATA_DIR = self.old_data_dir
        server.UPLOAD_DIR = self.old_upload_dir
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmpdir.cleanup()

    def test_login_seeds_demo_user_and_returns_read_only_flag(self):
        handler = HandlerHarness(
            payload={"email": "demo@gtf.local", "password": "change-this-demo-password"}
        )
        handler.handle_login()

        self.assertEqual(handler.responses[-1]["status"], HTTPStatus.OK)
        body = handler.responses[-1]["payload"]
        self.assertTrue(body["authenticated"])
        self.assertEqual(body["user"]["email"], "demo@gtf.local")
        self.assertTrue(body["user"]["is_read_only"])
        self.assertIn("Set-Cookie", handler.responses[-1]["headers"])

    def test_demo_login_returns_read_only_user_without_password_payload(self):
        handler = HandlerHarness(payload={})
        handler.handle_demo_login()

        self.assertEqual(handler.responses[-1]["status"], HTTPStatus.OK)
        body = handler.responses[-1]["payload"]
        self.assertTrue(body["authenticated"])
        self.assertTrue(body["demo"])
        self.assertEqual(body["user"]["email"], "demo@gtf.local")
        self.assertTrue(body["user"]["is_read_only"])
        self.assertIn("Set-Cookie", handler.responses[-1]["headers"])

    def test_login_rejects_wrong_password(self):
        handler = HandlerHarness(payload={"email": "demo@gtf.local", "password": "wrong"})
        handler.handle_login()

        self.assertEqual(handler.responses[-1]["status"], HTTPStatus.UNAUTHORIZED)
        self.assertIn("올바르지 않습니다", handler.responses[-1]["payload"]["error"])

    def test_read_only_user_cannot_create_project_route(self):
        handler = HandlerHarness(
            user={
                "id": "admin",
                "email": "demo@gtf.local",
                "is_read_only": True,
                "created_at": "2026-07-02T00:00:00+00:00",
            },
            path="/api/projects",
        )
        handler.do_POST()

        self.assertFalse(handler.project_created)
        self.assertEqual(handler.responses[-1]["status"], HTTPStatus.FORBIDDEN)
        self.assertTrue(handler.responses[-1]["payload"]["read_only"])

    def test_write_user_can_reach_create_project_route(self):
        handler = HandlerHarness(
            user={
                "id": "admin",
                "email": "admin@example.com",
                "is_read_only": False,
                "created_at": "2026-07-02T00:00:00+00:00",
            },
            path="/api/projects",
        )
        handler.do_POST()

        self.assertTrue(handler.project_created)
        self.assertEqual(handler.responses[-1]["payload"]["id"], "created")

    def test_sqlite_schema_is_loaded_from_separate_file(self):
        schema = server.SQLITE_SCHEMA_PATH.read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS app_users", schema)
        self.assertIn("is_read_only", schema)
        with server.connect() as conn:
            row = conn.execute("SELECT email, is_read_only FROM app_users WHERE id = ?", ("admin",)).fetchone()
        self.assertEqual(row["email"], "demo@gtf.local")
        self.assertEqual(int(row["is_read_only"]), 1)


if __name__ == "__main__":
    unittest.main()
