"""A janela do histórico que vai ao modelo: 6 trocas e 6.000 caracteres. Seção 7.1, NFR-13.

Testa a função pura `history_window`, de `app/domain/history.py`, entregue na Etapa 12.3. As
conversas são listas de `_Turn` com rótulos curtos, como `p5` e `r5`, completados com pontos
até o tamanho pedido. O uso da janela no `QaWorkflow` fica em `test_qa.py`. Testa também o
filtro `ai_messages`, que tira as mensagens do atendimento humano (FR-21). Não usa banco nem
rede.
"""

from dataclasses import dataclass
from uuid import UUID

from app.domain.history import (
    HISTORY_MAX_CHARS,
    HISTORY_MAX_EXCHANGES,
    ai_messages,
    history_window,
)


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


@dataclass(frozen=True)
class _Stored:
    role: str
    content: str
    handoff_id: UUID | None = None


def test_handoff_messages_never_enter_the_model_history() -> None:
    # CA-4 da Etapa 17.1 (FR-21): nem a mensagem do visitante no atendimento, nem a da equipe.
    handoff = UUID("00000000-0000-4000-8000-0000000000a1")
    stored = [
        _Stored("user", "Quais são os horários?"),
        _Stored("assistant", "Não encontrei."),
        _Stored("user", "Meu CPF é [CPF removido]", handoff),
        _Stored("attendant", "Pode ligar para a mesa.", handoff),
        _Stored("user", "E o estacionamento?"),
    ]
    kept = ai_messages(stored)
    assert [message.content for message in kept] == [
        "Quais são os horários?",
        "Não encontrei.",
        "E o estacionamento?",
    ]
    assert all(message.handoff_id is None for message in kept)
    window = history_window(kept)
    assert all(turn.content not in {"Pode ligar para a mesa."} for turn in window)
