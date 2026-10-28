"""Nota do visitante no LangSmith. Seção 18.4 do SDD."""

USER_HELPFUL = "user_helpful"


def user_helpful_score(rating: int) -> float:
    """1 vira 1. -1 vira 0. O banco guarda -1 ou 1."""
    if rating == 1:
        return 1.0
    if rating == -1:
        return 0.0
    raise ValueError("rating must be 1 or -1")
