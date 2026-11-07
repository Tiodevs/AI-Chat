"""Janela do histórico que vai ao modelo. Seção 7.1 do SDD."""

from collections.abc import Sequence
from typing import Protocol

HISTORY_MAX_EXCHANGES = 6
HISTORY_MAX_CHARS = 6_000


class HistoryTurn(Protocol):
    @property
    def role(self) -> str: ...

    @property
    def content(self) -> str: ...


def history_window[TurnT: HistoryTurn](
    turns: Sequence[TurnT],
    *,
    max_exchanges: int = HISTORY_MAX_EXCHANGES,
    max_chars: int = HISTORY_MAX_CHARS,
) -> tuple[TurnT, ...]:
    """As mensagens mais recentes que cabem nos dois limites, inteiras e na ordem da conversa.

    Uma troca é a pergunta e a resposta, então a janela tem até `2 * max_exchanges` mensagens
    e até `max_chars` caracteres somados. Ela começa sempre por uma pergunta do visitante,
    para o modelo não ler uma resposta sem a pergunta que a originou. Assim o custo de uma
    pergunta não cresce com o tamanho da conversa.
    """
    if max_exchanges <= 0 or max_chars <= 0:
        return ()
    kept: list[TurnT] = []
    total = 0
    for turn in reversed(turns[-2 * max_exchanges :]):
        total += len(turn.content)
        if total > max_chars:
            break
        kept.append(turn)
    while kept and kept[-1].role != "user":
        kept.pop()
    kept.reverse()
    return tuple(kept)
