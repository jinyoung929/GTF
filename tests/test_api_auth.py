"""
인증·권한 API 테스트 (FastAPI TestClient)
==========================================

HTTP 계층을 그대로 통과시켜 검증한다: 세션 쿠키 로그인, 데모 계정 읽기 전용 플래그,
잘못된 비밀번호 거절, 읽기 전용 계정의 쓰기 차단(403), 미로그인 401.

실행:
    python3 -m unittest tests.test_api_auth -v
"""

import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import server
from gtf_app.models import AppUser, Base


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
        # lifespan(init_db)은 위에서 임시 DB로 이미 실행했으므로 TestClient는 앱만 감싼다.
        self.client = TestClient(server.app)

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

    def login(self, email="demo@gtf.local", password="change-this-demo-password"):
        return self.client.post("/api/auth/login", json={"email": email, "password": password})

    def test_login_seeds_demo_user_and_returns_read_only_flag(self):
        response = self.login()

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["authenticated"])
        self.assertEqual(body["user"]["email"], "demo@gtf.local")
        self.assertTrue(body["user"]["is_read_only"])
        self.assertIn(server.SESSION_COOKIE, response.cookies)

    def test_demo_login_returns_read_only_user_without_password_payload(self):
        response = self.client.post("/api/auth/demo")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["authenticated"])
        self.assertTrue(body["demo"])
        self.assertEqual(body["user"]["email"], "demo@gtf.local")
        self.assertTrue(body["user"]["is_read_only"])
        self.assertIn(server.SESSION_COOKIE, response.cookies)

    def test_login_rejects_wrong_password(self):
        response = self.login(password="wrong")

        self.assertEqual(response.status_code, 401)
        self.assertIn("올바르지 않습니다", response.json()["error"])

    def test_read_only_user_cannot_create_project(self):
        self.login()  # 시드된 데모 관리자 = 읽기 전용
        response = self.client.post("/api/projects", json={"company_name": "테스트"})

        self.assertEqual(response.status_code, 403)
        self.assertTrue(response.json()["read_only"])

    def test_write_user_can_create_project(self):
        # demo@gtf.local은 admin_config가 항상 읽기 전용으로 강제하므로 별도 관리자로 재시드한다.
        os.environ["ADMIN_EMAIL"] = "admin@example.com"
        os.environ["ADMIN_PASSWORD"] = "write-pass"
        with server.get_session() as session:
            server.ensure_admin_user(session)
        self.login(email="admin@example.com", password="write-pass")
        response = self.client.post("/api/projects", json={"company_name": "테스트", "period": "2024"})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["company_name"], "테스트")
        self.assertEqual(response.json()["period"], "2024")

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get("/api/projects")

        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.json()["login_required"])

    def test_healthz_is_public(self):
        response = self.client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_logout_clears_session(self):
        self.login()
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.get("/api/projects").status_code, 401)


    def test_reclassify_statement_updates_row_and_logs(self):
        # 검토 요약의 '분류하러 가기'가 도착하는 곳: 미분류 행을 담당자가 재분류하고 감사 로그가 남는다.
        # demo@gtf.local은 읽기 전용으로 강제되므로 쓰기 관리자를 재시드한다.
        os.environ["ADMIN_EMAIL"] = "admin@example.com"
        os.environ["ADMIN_PASSWORD"] = "write-pass"
        with server.get_session() as session:
            server.ensure_admin_user(session)
        self.login(email="admin@example.com", password="write-pass")
        project = self.client.post("/api/projects", json={"company_name": "재분류", "period": "2024"}).json()
        added = self.client.post(
            f"/api/projects/{project['id']}/statements",
            json={"rows": [{"account_name": "권리금", "amount": 100}]},
        ).json()
        self.client.post(f"/api/projects/{project['id']}/extractions/{added['extraction_id']}/accept", json={})
        bundle = self.client.get(f"/api/projects/{project['id']}").json()
        row = bundle["statements"][0]
        self.assertEqual(row["standard_code"], "X9999")  # 권리금은 별칭 사전에 없어 미분류

        patched = self.client.patch(
            f"/api/projects/{project['id']}/statements/{row['id']}/classify",
            json={"account_key": "goodwill"},
        )
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["standard_code"], "A3200")
        self.assertEqual(patched.json()["mapping_type"], "judgment")

        rejected = self.client.patch(
            f"/api/projects/{project['id']}/statements/{row['id']}/classify",
            json={"account_key": "other"},
        )
        self.assertEqual(rejected.status_code, 400)

        logs = self.client.get(f"/api/projects/{project['id']}/audit").json()
        events = {log["event_type"] for log in logs}
        self.assertIn("statement.reclassified", events)

    def test_add_judgment_account_creates_blank_row_and_calculates(self):
        # 원본에 없는 판단 계정(리스)을 검토자가 소환하면, 판단 행이 생기고 체크리스트로
        # 입력받아 변환 시 결정론 계산기가 조정을 산출한다. 억지 탐지 없이 신규 인식.
        os.environ["ADMIN_EMAIL"] = "admin@example.com"
        os.environ["ADMIN_PASSWORD"] = "write-pass"
        with server.get_session() as session:
            server.ensure_admin_user(session)
        self.login(email="admin@example.com", password="write-pass")
        project = self.client.post("/api/projects", json={"company_name": "신규인식", "period": "2024"}).json()

        added = self.client.post(
            f"/api/projects/{project['id']}/statements/judgment",
            json={"account_key": "lease", "amount": 0},
        )
        self.assertEqual(added.status_code, 201)
        row = added.json()
        self.assertEqual(row["standard_code"], "A2100")
        self.assertEqual(row["mapping_type"], "judgment")
        self.assertIn("신규 인식", row["account_name"])

        # 단순 매핑 계정·미분류는 신규 추가 불가
        rejected = self.client.post(
            f"/api/projects/{project['id']}/statements/judgment",
            json={"account_key": "cash"},
        )
        self.assertEqual(rejected.status_code, 400)

        # 체크리스트 입력 → 변환 시 리스 현재가치 조정이 산출된다
        conversion = self.client.post(
            f"/api/projects/{project['id']}/convert",
            json={"responses": {row["id"]: {"lease_term_months": 12, "monthly_payment": 1000000, "discount_rate": 0}}},
        ).json()
        lease_entry = next(e for e in conversion["entries"] if e["standard_code"] == "A2100")
        self.assertEqual(lease_entry["adjustment"], 12000000)  # 할인율 0 → 12개월 × 100만

        logs = self.client.get(f"/api/projects/{project['id']}/audit").json()
        self.assertIn("statement.judgment_added", {log["event_type"] for log in logs})



    def test_schema_comes_from_orm_models_and_admin_is_seeded(self):
        # 스키마의 단일 출처는 ORM 모델(Base.metadata)이며, init_db가 create_all로 만든다.
        self.assertIn("app_users", Base.metadata.tables)
        self.assertIn("is_read_only", Base.metadata.tables["app_users"].columns)
        with server.get_session() as session:
            admin = session.get(AppUser, "admin")
        self.assertEqual(admin.email, "demo@gtf.local")
        self.assertTrue(admin.is_read_only)


if __name__ == "__main__":
    unittest.main()
