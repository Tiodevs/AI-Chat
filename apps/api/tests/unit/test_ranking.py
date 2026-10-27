"""A fusão é pura e os ranks começam em 1. Seção 8.4."""

from app.domain.ranking import RRF_K, reciprocal_rank_fusion


def test_fusion_ranks_start_at_one() -> None:
    # Com k=1, ranks a partir de 0 ordenariam d, a, c, b.
    fused = reciprocal_rank_fusion([["a", "b", "c", "d"], ["d", "c"]], k=1)
    assert fused == ["d", "c", "a", "b"]


def test_fusion_uses_constant_60_and_ranks_from_one() -> None:
    fused = reciprocal_rank_fusion([["a", "b"], ["b", "c"]])
    assert RRF_K == 60
    assert fused == ["b", "a", "c"]
    scores = {
        "a": 1 / 61,
        "b": 1 / 62 + 1 / 61,
        "c": 1 / 62,
    }
    assert scores["b"] > scores["a"] > scores["c"]
