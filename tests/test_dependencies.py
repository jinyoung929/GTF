"""
requirements.txt 완결성 가드
=============================

코드가 import하는 서드파티 패키지가 requirements.txt에 다 선언돼 있는지 검사한다.
로컬 환경엔 이미 설치돼 있어 import가 성공하므로, 선언 누락은 로컬에서 절대 안 잡히고
새로 설치하는 배포(`pip install -r requirements.txt`)의 import 단계에서만 터진다.
실제로 SQLAlchemy 선언 누락으로 배포가 죽은 적이 있어 이 가드를 둔다.

실행:
    python3 -m unittest tests.test_dependencies -v
"""

import ast
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

# 코드 파일 (테스트 자신은 제외 — 테스트 전용 의존성은 배포에 불필요)
SOURCE_FILES = ["server.py"] + [
    os.path.join("gtf_app", f) for f in os.listdir(os.path.join(_ROOT, "gtf_app")) if f.endswith(".py")
]

# import 이름 → 배포 패키지(distribution) 이름이 다른 경우만 매핑
IMPORT_TO_DIST = {"multipart": "python-multipart"}

LOCAL_MODULES = {"gtf_app", "server"}


def top_level_third_party_imports() -> set[str]:
    stdlib = set(sys.stdlib_module_names)
    found: set[str] = set()
    for rel in SOURCE_FILES:
        with open(os.path.join(_ROOT, rel), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                found.add(node.module.split(".")[0])
    return found - stdlib - LOCAL_MODULES


class RequirementsCoverImportsTest(unittest.TestCase):
    def test_every_third_party_import_is_declared(self):
        with open(os.path.join(_ROOT, "requirements.txt"), encoding="utf-8") as fh:
            declared = fh.read().lower()

        missing = []
        for module in sorted(top_level_third_party_imports()):
            dist = IMPORT_TO_DIST.get(module, module)
            if dist.lower() not in declared and module.lower() not in declared:
                missing.append(module)

        self.assertEqual(
            missing,
            [],
            f"코드가 import하지만 requirements.txt에 없는 패키지: {missing}. "
            "로컬은 설치돼 있어 통과하지만 새 배포는 import 단계에서 죽는다.",
        )


if __name__ == "__main__":
    unittest.main()
