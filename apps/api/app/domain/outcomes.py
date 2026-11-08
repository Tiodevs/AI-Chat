"""Desfechos da pergunta. Seções 7.1 e 10.1 do SDD.

Camada de domínio. `QaWorkflow` (`app/workflows/qa.py`) chama `gate_outcome` logo depois da
classificação (passo 2 da seção 7.1) e escolhe os outros desfechos pelo que acontece no
pipeline: busca vazia, fundamentação reprovada, falha do provedor ou circuito aberto.
`app/prompts/qa.py` tem o texto fixo de cada desfecho que não vem do modelo. O modelo `Message`
e a migração `0004_conversations` usam a restrição gerada daqui.

A seção 10.1 diz que este módulo escolhe o desfecho. No código, só `refused` e `off_topic`
saem daqui; os outros são escolhidos no workflow e no `ConversationService`.
"""

import math
from enum import StrEnum

# Confiança mínima da classificação para a busca rodar (passo 2 da seção 7.1).
MIN_PUBLIC_CONFIDENCE = 0.6


class Outcome(StrEnum):
    """Desfecho gravado em `messages.outcome` de cada resposta (seção 7.1).

    - `answered`: rascunho fundamentado, com pelo menos uma citação válida.
    - `abstained`: nenhum chunk alcançou `RETRIEVAL_MIN_SIMILARITY`.
    - `refused`: orientação médica.
    - `off_topic`: fora do tema, ou classificação com confiança baixa.
    - `grounding_failed`: sem citação válida, ou telefone fora do contexto.
    - `cancelled`: o navegador fechou o fluxo antes do fim.
    - `degraded`: orçamento estourado ou circuito aberto.
    - `error`: falha do provedor com o circuito fechado.

    `StrEnum` faz cada membro ser também um `str`: `Outcome.ANSWERED == "answered"`.
    """

    ANSWERED = "answered"
    ABSTAINED = "abstained"
    REFUSED = "refused"
    OFF_TOPIC = "off_topic"
    GROUNDING_FAILED = "grounding_failed"
    CANCELLED = "cancelled"
    DEGRADED = "degraded"
    ERROR = "error"


# Restrição CHECK de `messages.outcome`, gerada do enum. O modelo `Message` e a migração
# `0004_conversations` importam esta expressão. Um desfecho novo não muda um banco já migrado:
# ele pede uma migração que troque a restrição.
OUTCOME_CHECK_SQL = (
    "outcome IS NULL OR outcome IN ("
    + ", ".join(f"'{item.value}'" for item in Outcome)
    + ")"
)


def gate_outcome(intent: str, confidence: float) -> Outcome | None:
    """Recusa orientação médica. Fora de tema não chama o gerador.

    A recuperação só continua quando a intenção é informação pública e a
    confiança é pelo menos 0,6. Orientação médica vence a confiança baixa.

    Devolve o desfecho fixo, ou `None` para seguir para a busca. Uma confiança acima de 1, ou
    que não é um número finito, conta como baixa.
    """
    if intent == "medical_advice":
        return Outcome.REFUSED
    # `NaN < 0.6` é falso: sem `math.isfinite`, uma confiança `NaN` passaria no portão.
    if (
        intent != "public_info"
        or not math.isfinite(confidence)
        or confidence < MIN_PUBLIC_CONFIDENCE
        or confidence > 1
    ):
        return Outcome.OFF_TOPIC
    return None
