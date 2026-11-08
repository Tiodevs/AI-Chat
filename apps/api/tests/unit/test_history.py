"""A janela do histórico que vai ao modelo: 6 trocas e 6.000 caracteres. Seção 7.1, NFR-13.

Testa a função pura `history_window`, de `app/domain/history.py`, entregue na Etapa 12.3. As
conversas são listas de `_Turn` com rótulos curtos, como `p5` e `r5`, completados com pontos
até o tamanho pedido. O uso da janela no `QaWorkflow` fica em `test_qa.py`. Não usa banco nem
rede.
"""

from dataclasses import dataclass

from app.domain.history import HISTORY_MAX_CHARS, HISTORY_MAX_EXCHANGES, history_window


@dataclass(frozen=True, slots=True)
class _Turn:
    """Uma mensagem da conversa com o `role` e o `content` que `history_window` lê."""

    role: str
    content: str


def _conversation(exchanges: int, *, size: int = 10) -> list[_Turn]:
    """Monta `exchanges` trocas `pN`/`rN`, cada mensagem com `size` caracteres."""
    turns: list[_Turn] = []
    for number in range(1, exchanges + 1):
        turns.append(_Turn("user", f"p{number}".ljust(size, ".")))
        turns.append(_Turn("assistant", f"r{number}".ljust(size, ".")))
    return turns


def _labels(turns: tuple[_Turn, ...]) -> list[str]:
    """Devolve os rótulos `pN`/`rN` da janela, sem os pontos de enchimento."""
    return [turn.content.rstrip(".") for turn in turns]


def test_limits_are_six_exchanges_and_six_thousand_characters() -> None:
    assert HISTORY_MAX_EXCHANGES == 6
    assert HISTORY_MAX_CHARS == 6_000


def test_short_history_goes_whole() -> None:
    turns = _conversation(3)
    assert history_window(turns) == tuple(turns)


def test_empty_history_stays_empty() -> None:
    assert history_window([]) == ()


def test_keeps_only_the_last_six_exchanges() -> None:
    window = history_window(_conversation(10))
    assert len(window) == 12
    assert _labels(window)[:2] == ["p5", "r5"]
    assert _labels(window)[-2:] == ["p10", "r10"]


def test_older_turns_beyond_the_character_limit_are_left_out() -> None:
    window = history_window(_conversation(6, size=1_000), max_chars=4_000)
    assert _labels(window) == ["p5", "r5", "p6", "r6"]
    assert sum(len(turn.content) for turn in window) <= 4_000


def test_window_starts_with_a_visitor_question() -> None:
    turns = _conversation(3, size=1_000)
    window = history_window(turns, max_chars=3_000)
    assert _labels(window) == ["p3", "r3"]
    assert window[0].role == "user"


def test_a_turn_longer_than_the_limit_is_left_out_whole() -> None:
    turns = [_Turn("user", "pergunta"), _Turn("assistant", "x" * 7_000)]
    assert history_window(turns) == ()


def test_zero_limits_send_no_history() -> None:
    turns = _conversation(2)
    assert history_window(turns, max_exchanges=0) == ()
    assert history_window(turns, max_chars=0) == ()
