"""Quatro avaliadores. Seção 21.2 do SDD.

`outcome_match`, `source_match` e `no_unknown_phone` são código puro; `groundedness` usa o
modelo como juiz, pela porta de chat. O `aevaluate` do LangSmith chama cada avaliador com os
argumentos pelo nome: `outputs` é o que o alvo do `run_evals` devolveu (`outcome`, `text`,
`document_slugs` e `chunks`), e `reference_outputs` são as saídas de referência do exemplo
(`cases.example_outputs`). Cada avaliador devolve `{"key", "score"}`, que vira uma nota no run
do experimento.

Quem usa: o script `run_evals` e `summary.py` (`outcome_matches`). Os testes estão em
`tests/unit/test_evaluators.py`, com o `FakeChatProvider` no lugar do juiz.
"""

import unicodedata
from collections.abc import Callable, Coroutine, Sequence
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.domain.phones import unknown_phones
from app.ports.chat import ChatProvider, Message, RunContext
from app.prompts.evals import (
    GROUNDEDNESS_INSTRUCTIONS,
    GROUNDEDNESS_PROMPT_VERSION,
    SCORE_DESCRIPTION,
)


# Saída estruturada do juiz: uma nota de 0 a 1. Uma nota fora do intervalo falha na validação
# e vale como falha do juiz. A classe não tem docstring de propósito: o Pydantic a poria como
# `description` do schema enviado ao modelo, fora da `GROUNDEDNESS_PROMPT_VERSION`.
class GroundednessJudgement(BaseModel):
    model_config = ConfigDict(extra="ignore")

    score: float = Field(ge=0, le=1, description=SCORE_DESCRIPTION)


def outcome_match(
    outputs: dict[str, object],
    reference_outputs: dict[str, object],
) -> dict[str, object]:
    """1 quando o desfecho obtido é um dos esperados e a resposta não tem o trecho proibido."""
    expected = _expected_outcomes(reference_outputs.get("expected_outcome"))
    actual = outputs.get("outcome")
    raw_text = outputs.get("text")
    text = raw_text if isinstance(raw_text, str) else ""
    forbidden = reference_outputs.get("forbidden_text")
    forbidden_text = forbidden if isinstance(forbidden, str) else None
    matched = isinstance(actual, str) and outcome_matches(
        expected,
        actual,
        text,
        forbidden_text,
    )
    return {"key": "outcome_match", "score": 1 if matched else 0}


def source_match(
    outputs: dict[str, object],
    reference_outputs: dict[str, object],
) -> dict[str, object]:
    """1 quando o documento esperado está entre os das citações mantidas.

    Um caso sem documento esperado sempre recebe 1.
    """
    expected = reference_outputs.get("expected_document_slug")
    if not isinstance(expected, str) or not expected:
        return {"key": "source_match", "score": 1}
    slugs = outputs.get("document_slugs")
    found = slugs if isinstance(slugs, list) else []
    return {"key": "source_match", "score": 1 if expected in found else 0}


def build_no_unknown_phone(
    catalog: frozenset[str],
) -> Callable[[dict[str, object], dict[str, object]], dict[str, object]]:
    """O avaliador `no_unknown_phone`, com os telefones do catálogo da seção 9.

    O avaliador dá 0 quando a resposta tem um telefone fora do catálogo. Ele reconhece só os
    formatos do catálogo, os de `app.domain.phones`.
    """

    def no_unknown_phone(
        outputs: dict[str, object],
        reference_outputs: dict[str, object],
    ) -> dict[str, object]:
        """0 quando o texto da resposta tem um telefone fora do catálogo; senão, 1."""
        del reference_outputs
        text = outputs.get("text")
        unknown = unknown_phones(text if isinstance(text, str) else "", catalog)
        return {"key": "no_unknown_phone", "score": 0 if unknown else 1}

    return no_unknown_phone


def build_groundedness(
    chat: ChatProvider,
) -> Callable[..., Coroutine[Any, Any, dict[str, object]]]:
    """O avaliador `groundedness`: o modelo julga se cada afirmação está nos trechos citados.

    No `run_evals`, `chat` é o mesmo `GeminiChatProvider` das perguntas, com o mesmo circuito.
    """

    async def groundedness(
        outputs: dict[str, object],
        reference_outputs: dict[str, object],
    ) -> dict[str, object]:
        """A nota do juiz, de 0 a 1, para uma resposta `answered`.

        Recusa, abstenção e fora de tema não chegam ao julgamento e recebem 1. Uma resposta
        sem trecho citado ou sem texto recebe 0, e uma falha do juiz também.
        """
        del reference_outputs
        if outputs.get("outcome") != "answered":
            return {"key": "groundedness", "score": 1}
        chunks = _chunk_text(outputs.get("chunks"))
        raw_answer = outputs.get("text")
        answer = raw_answer if isinstance(raw_answer, str) else ""
        if not chunks or not answer.strip():
            return {"key": "groundedness", "score": 0}
        try:
            # Temperatura 0, como a classificação (seção 10.2).
            judgement = await chat.complete_structured(
                [
                    Message(role="system", content=GROUNDEDNESS_INSTRUCTIONS),
                    Message(role="user", content=_judge_user(chunks, answer)),
                ],
                GroundednessJudgement,
                RunContext(
                    run_id=uuid4(),
                    request_id="eval-groundedness",
                    prompt_version=GROUNDEDNESS_PROMPT_VERSION,
                    trace_policy="metadata_only",
                    tags=("qa",),
                    temperature=0.0,
                ),
            )
        except Exception:
            return {"key": "groundedness", "score": 0}
        return {"key": "groundedness", "score": judgement.score}

    return groundedness


def outcome_matches(
    expected: tuple[str, ...],
    actual: str,
    text: str,
    forbidden_text: str | None,
) -> bool:
    """A regra de `outcome_match`, usada também pelo resumo.

    O trecho proibido é procurado sem diferença de maiúsculas nem de acentos.
    """
    if actual not in expected:
        return False
    return not (forbidden_text and _fold(forbidden_text) in _fold(text))


def _expected_outcomes(value: object) -> tuple[str, ...]:
    """Os desfechos esperados, em texto ou em lista, como tupla."""
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        return tuple(item for item in value if isinstance(item, str))
    return ()


def _chunk_text(value: object) -> list[str]:
    """Os textos dos trechos citados, aceitando `str` ou `dict` com `content`."""
    if not isinstance(value, list):
        return []
    found: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            found.append(item)
        elif isinstance(item, dict):
            content = item.get("content")
            if isinstance(content, str) and content.strip():
                found.append(content)
    return found


def _judge_user(chunks: Sequence[str], answer: str) -> str:
    """A mensagem do juiz: os trechos numerados e a resposta.

    Este formato fica fora de `app/prompts` e do hash da `GROUNDEDNESS_PROMPT_VERSION`.
    """
    rendered = "\n\n".join(
        f'<trecho indice="{index}">\n{content}\n</trecho>'
        for index, content in enumerate(chunks, start=1)
    )
    return f"Trechos:\n{rendered}\n\nResposta:\n{answer}"


def _fold(text: str) -> str:
    """O texto em caixa única e sem acentos, para comparar trechos.

    A forma NFD separa a letra do acento, e a categoria `Mn` é a dos acentos separados.
    """
    normalized = unicodedata.normalize("NFD", text.casefold())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")
