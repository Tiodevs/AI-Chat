"""Janela do histórico que vai ao modelo. Seção 7.1 do SDD.

Camada de domínio. `QaWorkflow.run` aplica `history_window` antes da reescrita e da geração.
O histórico vem do banco, então uma pergunta de saúde de um turno anterior já está trocada
pelo marcador `[health-related message not stored]` (seção 11.4).
"""

from collections.abc import Sequence
from typing import Protocol

# Até 6 trocas e 6.000 caracteres somados: o custo de uma pergunta não cresce com a conversa
# (seção 7.1).
HISTORY_MAX_EXCHANGES = 6
HISTORY_MAX_CHARS = 6_000


class HistoryTurn(Protocol):
    """O que a janela precisa de uma mensagem: o papel e o texto.

    É um `Protocol`: qualquer objeto com esses dois atributos serve, sem herdar desta classe.
    O `ConversationTurn` do workflow é um deles. Assim o domínio não importa o workflow.
    """

    @property
    def role(self) -> str:
        """`user` para o visitante e `assistant` para o Atrium."""
        ...

    @property
    def content(self) -> str:
        """Texto da mensagem, como foi gravado."""
        ...


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

    1. Toma as últimas `2 * max_exchanges` mensagens.
    2. Da mais nova para a mais antiga, soma os caracteres e para na primeira que estoura
       `max_chars`. Ela e todas as mais antigas ficam de fora, mesmo que alguma coubesse.
    3. Tira do começo da janela as respostas sem pergunta, até ela começar por `user`.
    4. Devolve na ordem da conversa.

    `[TurnT: HistoryTurn]` é a sintaxe de tipo genérico do Python 3.12 (PEP 695): a função
    devolve o mesmo tipo de mensagem que recebeu. Limites zero ou negativos devolvem a janela
    vazia.
    """
    if max_exchanges <= 0 or max_chars <= 0:
        return ()
    kept: list[TurnT] = []
    total = 0
    # 1. e 2. `kept` fica da mais nova para a mais antiga.
    for turn in reversed(turns[-2 * max_exchanges :]):
        total += len(turn.content)
        if total > max_chars:
            break
        kept.append(turn)
    # 3. `kept[-1]` é a mensagem mais antiga da janela.
    while kept and kept[-1].role != "user":
        kept.pop()
    # 4.
    kept.reverse()
    return tuple(kept)
