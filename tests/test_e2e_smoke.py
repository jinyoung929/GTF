import http.cookiejar
import json
import os
import subprocess
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PORT = 4191
BASE_URL = f"http://127.0.0.1:{PORT}"


def read_env_value(name: str) -> str:
    for env_path in (ROOT / ".env", ROOT / ".env.local"):
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == name:
                return value.strip().strip('"').strip("'")
    return ""


class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))

    def request(self, method: str, path: str, payload: dict | None = None) -> tuple[int, bytes, str]:
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=45) as response:
                return response.status, response.read(), response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(), exc.headers.get("Content-Type", "")

    def json(self, method: str, path: str, payload: dict | None = None, expected_status: int = 200) -> dict:
        status, body, _content_type = self.request(method, path, payload)
        if status != expected_status:
            raise AssertionError(f"{method} {path} returned {status}: {body.decode('utf-8', errors='replace')[:500]}")
        return json.loads(body.decode("utf-8"))


class EndToEndSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dart_key = os.environ.get("DART_API_KEY") or read_env_value("DART_API_KEY")
        if not dart_key:
            raise unittest.SkipTest("DART_API_KEY is required for live E2E smoke test.")

        env = {
            **os.environ,
            "ADMIN_EMAIL": "admin@example.com",
            "ADMIN_PASSWORD": "test-admin-pass",
            "DART_API_KEY": dart_key,
            "PORT": str(PORT),
        }
        cls.server = subprocess.Popen(
            ["python3", "server.py"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        cls.client = ApiClient(BASE_URL)
        deadline = time.time() + 60
        while time.time() < deadline:
            if cls.server.poll() is not None:
                output = cls.server.stdout.read() if cls.server.stdout else ""
                raise RuntimeError(f"Server exited during startup:\n{output}")
            try:
                status, body, _content_type = cls.client.request("GET", "/healthz")
                if status == 200 and b'"status": "ok"' in body:
                    return
            except OSError:
                pass
            time.sleep(1)
        raise TimeoutError("Server did not become ready within 60 seconds.")

    @classmethod
    def tearDownClass(cls):
        server = getattr(cls, "server", None)
        if server and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()

    def test_dart_to_excel_review_workbook_flow(self):
        status, body, content_type = self.client.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn(b"root", body)

        login = self.client.json(
            "POST",
            "/api/auth/login",
            {"email": "admin@example.com", "password": "test-admin-pass"},
        )
        self.assertTrue(login["authenticated"])

        project = self.client.json(
            "POST",
            "/api/projects",
            {
                "company_name": "삼성전자",
                "period": "2024",
                "source_standard": "K-GAAP",
                "target_standard": "K-IFRS",
            },
            expected_status=201,
        )
        project_id = project["id"]

        extraction = self.client.json(
            "POST",
            f"/api/projects/{project_id}/dart/import",
            {"corp_code": "00126380", "bsns_year": "2024", "reprt_code": "11011", "fs_div": "CFS"},
            expected_status=201,
        )
        self.assertEqual(extraction["provider"], "dart_api")
        self.assertEqual(extraction["metadata"]["raw_row_count"], 213)
        self.assertEqual(extraction["metadata"]["filtered_row_count"], 13)
        self.assertEqual(len(extraction["rows"]), 13)
        self.assertEqual(
            next(row for row in extraction["rows"] if row["account_name"] == "단기금융상품")["account_key"],
            "financial_instrument",
        )

        accepted = self.client.json(
            "POST",
            f"/api/projects/{project_id}/extractions/{extraction['id']}/accept",
            {},
        )
        self.assertEqual(len(accepted["statements"]), 13)
        financial_product = next(row for row in accepted["statements"] if row["account_name"] == "단기금융상품")
        self.assertEqual(financial_product["standard_code"], "F1000")

        conversion = self.client.json("POST", f"/api/projects/{project_id}/convert", {"responses": {}})
        self.assertEqual(len(conversion["entries"]), 13)
        self.assertIn("단기금융상품", [entry["source_account"] for entry in conversion["entries"]])

        status, workbook_bytes, content_type = self.client.request(
            "GET", f"/api/projects/{project_id}/exports/review-workbook.xlsx"
        )
        self.assertEqual(status, 200)
        self.assertIn("spreadsheetml.sheet", content_type)

        workbook_path = ROOT / "data" / "e2e_review_workbook.xlsx"
        workbook_path.write_bytes(workbook_bytes)
        with zipfile.ZipFile(workbook_path) as archive:
            sheet1 = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
            sheet2 = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")
        self.assertEqual(sheet1.count("<row "), 217)
        self.assertEqual(sheet2.count("<row "), 14)
        self.assertIn("자산총계", sheet1)
        self.assertIn("제외사유", sheet1)
        self.assertIn("단기금융상품", sheet2)
        self.assertIn("F1000", sheet2)


if __name__ == "__main__":
    unittest.main()
