"""Fusão de rankings. Os ranks começam em 1. Seção 8.4 do SDD."""

from collections.abc import Sequence

RRF_K = 60
VECTOR_CANDIDATES = 20
KEYWORD_CANDIDATES = 20
RESULT_LIMIT = 6


def reciprocal_rank_fusion[T](rankings: Sequence[Sequence[T]], *, k: int = RRF_K) -> list[T]:
    scores: dict[T, float] = {}
    first_seen: dict[T, int] = {}
    seen_count = 0
    for ranking in rankings:
        seen_in_list: set[T] = set()
        rank = 0
        for item in ranking:
            if item in seen_in_list:
                continue
            seen_in_list.add(item)
            rank += 1
            if item not in first_seen:
                first_seen[item] = seen_count
                seen_count += 1
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda item: (-scores[item], first_seen[item]))
