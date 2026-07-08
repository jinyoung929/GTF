"""
RAG(임베딩 검색) 단위 테스트
============================

OpenAI 임베딩 호출을 결정론적 스텁으로 대체해 키 없이도 코사인 랭킹·폴백을 검증한다.

검증 범위:
  - _cosine_similarity 정합성
  - ensure_paragraph_embeddings가 embedding 컬럼에 벡터를 저장
  - semantic_search_paragraphs가 의미 유사도로 관련 문단을 상위에 랭크
  - 임베딩/키가 없을 때 키워드 검색으로 폴백
  - 검색 결과는 근거 표시일 뿐 조정 금액을 만들지 않음(경계 유지)

실행:
    python3 -m unittest tests.test_rag_standards -v
"""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
for _candidate in (_HERE, os.path.dirname(_HERE)):
    if os.path.exists(os.path.join(_candidate, "server.py")):
        sys.path.insert(0, _candidate)
        break

from sqlalchemy import func, select, update  # noqa: E402

import server  # noqa: E402
from gtf_app.models import StandardsParagraph  # noqa: E402

sys.path.insert(0, _HERE)
from reference_fixture import paragraph_session  # noqa: E402


# 결정론적 가짜 임베딩: 도메인 토큰의 등장 횟수를 벡터로 만들어 의미 유사도가 성립하게 한다.
_VOCAB = ["리스", "사용권", "현재가치", "할인율", "손상", "회수가능액", "이연법인세", "일시적차이", "퇴직급여", "확정급여", "정부보조금", "차입원가", "자본화", "재평가", "공정가치"]


def fake_embed(texts):
    vectors = []
    for text in texts:
        vectors.append([float(text.count(token)) for token in _VOCAB])
    return vectors


class RagStandardsTest(unittest.TestCase):
    def setUp(self):
        self.conn = paragraph_session()
        self._real_embed = server.openai_embed

    def tearDown(self):
        server.openai_embed = self._real_embed
        self.conn.close()

    def _seed_embeddings(self):
        server.openai_embed = fake_embed
        server.ensure_paragraph_embeddings(self.conn)

    def test_cosine_bounds(self):
        self.assertEqual(server._cosine_similarity([1, 2, 3], [1, 2, 3]), 1.0)
        self.assertEqual(server._cosine_similarity([1, 0], [0, 1]), 0.0)
        self.assertEqual(server._cosine_similarity([0, 0], [1, 1]), 0.0)

    def test_embeddings_are_stored(self):
        self._seed_embeddings()
        embedding = self.conn.scalar(
            select(StandardsParagraph.embedding).where(StandardsParagraph.embedding.is_not(None)).limit(1)
        )
        self.assertIsNotNone(embedding)
        self.assertTrue(embedding.startswith("["))

    def test_semantic_search_ranks_relevant_paragraph_first(self):
        self._seed_embeddings()
        server.openai_embed = fake_embed
        results = server.semantic_search_paragraphs(self.conn, "손상차손 회수가능액", k=3)
        self.assertTrue(results)
        self.assertEqual(results[0]["retrieval"], "semantic")
        self.assertIn("손상", results[0]["title"] + results[0]["content"])

    def test_semantic_search_lease_query(self):
        self._seed_embeddings()
        server.openai_embed = fake_embed
        results = server.semantic_search_paragraphs(self.conn, "사용권자산 리스부채 현재가치 할인율", k=3)
        self.assertEqual(results[0]["account_key"], "lease")

    def test_falls_back_to_keyword_without_embeddings(self):
        # 임베딩 미생성 + 임베딩 호출이 None → 키워드 폴백
        server.openai_embed = lambda texts: None
        results = server.semantic_search_paragraphs(self.conn, "리스부채", k=3)
        self.assertTrue(results)
        self.assertEqual(results[0]["retrieval"], "keyword")

    def test_embeddings_not_leaked_into_results(self):
        self._seed_embeddings()
        server.openai_embed = fake_embed
        results = server.semantic_search_paragraphs(self.conn, "이연법인세 일시적차이", k=2)
        for para in results:
            self.assertNotIn("embedding", para)


class ParagraphSeedIdempotencyTest(unittest.TestCase):
    """SQL 시드는 upsert(멱등)이며, content_hash가 바뀐 문단만 재임베딩한다."""

    def setUp(self):
        self.conn = paragraph_session()
        self._real_embed = server.openai_embed
        self.calls = []

        def counting_embed(texts):
            self.calls.append(list(texts))
            return [[float(len(t)), 1.0] for t in texts]

        server.openai_embed = counting_embed
        server.ensure_standards_paragraphs(self.conn)
        server.ensure_paragraph_embeddings(self.conn)

    def tearDown(self):
        server.openai_embed = self._real_embed
        self.conn.close()

    def count(self, only_missing_embedding=None):
        stmt = select(func.count()).select_from(StandardsParagraph)
        if only_missing_embedding is True:
            stmt = stmt.where(StandardsParagraph.embedding.is_(None))
        elif only_missing_embedding is False:
            stmt = stmt.where(StandardsParagraph.embedding.is_not(None))
        return self.conn.scalar(stmt)

    def test_first_seed_embeds_everything_once(self):
        self.assertEqual(len(self.calls), 1)
        self.assertGreater(self.count(), 0)
        self.assertEqual(self.count(only_missing_embedding=False), self.count())  # 전 문단 임베딩됨

    def test_restart_is_idempotent_and_does_not_reembed(self):
        before_rows, before_calls = self.count(), len(self.calls)
        server.ensure_standards_paragraphs(self.conn)
        server.ensure_paragraph_embeddings(self.conn)
        self.assertEqual(self.count(), before_rows)  # 행이 늘거나 줄지 않음 (멱등)
        self.assertEqual(len(self.calls), before_calls)  # OpenAI 호출 0회

    def test_only_changed_paragraph_is_reembedded(self):
        # 시드 SQL의 문단 내용이 개정되면 content_hash가 달라진다.
        # DB 쪽 해시를 옛 값으로 되돌려 '개정 배포' 상황을 재현한다.
        target_id = self.conn.scalar(select(StandardsParagraph.id).order_by(StandardsParagraph.id).limit(1))
        self.conn.execute(
            update(StandardsParagraph).where(StandardsParagraph.id == target_id).values(content_hash="개정전해시")
        )
        self.conn.commit()
        before_calls = len(self.calls)
        server.ensure_standards_paragraphs(self.conn)
        self.assertEqual(self.count(only_missing_embedding=True), 1)  # 바뀐 하나만 비워짐
        server.ensure_paragraph_embeddings(self.conn)
        self.assertEqual(len(self.calls) - before_calls, 1)
        self.assertEqual(len(self.calls[-1]), 1)  # 그 문단 하나만 임베딩 요청
        self.assertEqual(self.count(only_missing_embedding=True), 0)

    def test_content_hash_matches_content(self):
        # 시드가 넣은 content_hash는 실제 임베딩 대상 텍스트의 sha256과 일치해야 한다
        import hashlib

        row = self.conn.execute(
            select(
                StandardsParagraph.reference_code,
                StandardsParagraph.title,
                StandardsParagraph.content,
                StandardsParagraph.content_hash,
            ).order_by(StandardsParagraph.id).limit(1)
        ).first()
        text = f"{row.reference_code} {row.title} {row.content}"
        self.assertEqual(row.content_hash, hashlib.sha256(text.encode("utf-8")).hexdigest())


if __name__ == "__main__":
    unittest.main()
