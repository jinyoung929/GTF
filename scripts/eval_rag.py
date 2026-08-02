"""RAG 검색 정확도 체계 평가 스크립트.

기준서 문단 106개를 실제 OpenAI 임베딩으로 임베딩한 뒤, 세 종류의 질의로
검색 품질을 측정한다. 정답 라벨은 문단의 account_key(계정 매핑)를 그대로 쓴다.

질의 종류:
  A. 계정명 단독            — AI 1차 분류가 쓰는 질의 (call_ai_classification, k=3)
  B. 계정명 + rule_summary  — AI 판단보조가 쓰는 질의 (/convert, k=5)
  C. 자연어 검토 질의       — 검토자 직접 검색을 흉내낸 수기 질의 (k=8)

지표:
  - hit@1 / hit@3 / hit@5: 상위 k개 안에 정답 계정 문단이 있는가
  - MRR: 첫 정답 문단 순위의 역수 평균
  - 유사도 분포: 정답 문단 vs 무관 문단의 유사도 통계 → SUPPLEMENTARY_SIMILARITY_FLOOR(0.3) 검증

실행 (OPENAI_API_KEY 필요 — .env.local에서 자동 로드):
    python3 scripts/eval_rag.py
"""

import os
import statistics
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "tests"))

import server  # noqa: E402
from reference_fixture import load_reference, seeded_session  # noqa: E402

# 검토자 자연어 질의 흉내: (질의, 정답 account_key). 계정명을 직접 쓰지 않은 표현을 골랐다.
NATURAL_QUERIES = [
    ("사무실 임차 계약의 월세를 자산으로 잡아야 하나", "lease"),
    ("연구소에서 개발한 기술의 지출을 자산 처리할 수 있는지", "development"),
    ("소송에서 질 것 같은데 부채로 잡아야 하는지", "provision"),
    ("건물 가치가 올라서 장부에 반영하고 싶다", "ppe"),
    ("영업권을 매년 상각해도 되는지", "goodwill"),
    ("세무상 이월결손금으로 자산을 인식할 수 있는지", "deferred_tax_asset"),
    ("공장 짓는 동안 발생한 이자 처리", "borrowing_cost"),
    ("퇴직금 부채를 어떻게 평가해야 하는지", "retirement_benefit"),
    ("임대 목적으로 보유한 건물의 평가 방법", "investment_property"),
    ("창고 재고를 어떤 원가로 평가해야 하는지", "inventory"),
]


def evaluate(session, queries, k):
    hits1 = hits3 = hitsk = 0
    reciprocal_ranks = []
    relevant_sims, irrelevant_sims = [], []
    misses = []
    for query, expected_key in queries:
        results = server.semantic_search_paragraphs(session, query, k=k)
        rank = None
        for idx, para in enumerate(results, start=1):
            sim = para.get("similarity")
            if para.get("account_key") == expected_key:
                if rank is None:
                    rank = idx
                if sim is not None:
                    relevant_sims.append(sim)
            elif sim is not None:
                irrelevant_sims.append(sim)
        if rank == 1:
            hits1 += 1
        if rank is not None and rank <= 3:
            hits3 += 1
        if rank is not None:
            hitsk += 1
            reciprocal_ranks.append(1 / rank)
        else:
            reciprocal_ranks.append(0)
            misses.append((query, expected_key, [(p.get("account_key"), p.get("similarity")) for p in results[:3]]))
    n = len(queries)
    return {
        "n": n, "hit@1": hits1 / n, "hit@3": hits3 / n, f"hit@{k}": hitsk / n,
        "mrr": sum(reciprocal_ranks) / n,
        "relevant_sims": relevant_sims, "irrelevant_sims": irrelevant_sims, "misses": misses,
    }


def describe(name, values):
    if not values:
        return f"  {name}: (없음)"
    return (
        f"  {name}: n={len(values)} min={min(values):.3f} p25={statistics.quantiles(values, n=4)[0]:.3f} "
        f"중앙값={statistics.median(values):.3f} max={max(values):.3f}"
    )


def main():
    server.load_local_env()
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        print("OPENAI_API_KEY가 없습니다. .env.local에 키를 넣으면 실제 임베딩으로 평가합니다.")
        print("키 없이 실행하면 키워드 폴백 경로만 측정되어 임베딩 품질 평가가 아닙니다. 중단합니다.")
        sys.exit(1)

    session = seeded_session()
    reference = load_reference()
    print("문단 임베딩 준비 중 (신규·변경 문단만 OpenAI 호출)...")
    server.ensure_paragraph_embeddings(session)

    label_by_key = {key: account["label"] for key, account in reference.accounts.items()}
    keys_with_paragraphs = sorted({
        row["account_key"] for row in server.find_standards_paragraphs(session) if row["account_key"] in label_by_key
    })
    queries_a = [(label_by_key[key], key) for key in keys_with_paragraphs]
    queries_b = [(f"{label_by_key[key]} {reference.accounts[key]['rule']}", key) for key in keys_with_paragraphs]

    for title, queries, k in (
        ("A. 계정명 단독 (분류 질의, k=3)", queries_a, 3),
        ("B. 계정명+rule_summary (판단보조 질의, k=5)", queries_b, 5),
        ("C. 자연어 검토 질의 (검토자 검색, k=8)", NATURAL_QUERIES, 8),
    ):
        r = evaluate(session, queries, k)
        print(f"\n=== {title} ===")
        print(f"  질의 {r['n']}건 | hit@1 {r['hit@1']:.0%} | hit@3 {r['hit@3']:.0%} | hit@{k} {r[f'hit@{k}']:.0%} | MRR {r['mrr']:.3f}")
        print(describe("정답 문단 유사도", r["relevant_sims"]))
        print(describe("무관 문단 유사도", r["irrelevant_sims"]))
        floor = server.SUPPLEMENTARY_SIMILARITY_FLOOR
        below = [s for s in r["relevant_sims"] if s < floor]
        above = [s for s in r["irrelevant_sims"] if s >= floor]
        print(f"  바닥값 {floor} 검증: 정답인데 컷 아래 {len(below)}건 / 무관인데 컷 위 {len(above)}건")
        for query, expected, top in r["misses"]:
            print(f"  [미탐] '{query}' (정답 {expected}) → 상위: {top}")


if __name__ == "__main__":
    main()
