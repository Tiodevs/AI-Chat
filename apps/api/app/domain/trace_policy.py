"""O que cada política de rastro deixa sair. Seção 18.4 e ADR-006.

Camada de domínio. Três políticas, por passo (seção 18.4):

- `full`: entradas e saídas inteiras, depois do anonimizador. Só a ingestão, porque o corpus
  é público e fictício.
- `masked`: só as chaves de `_MASKED_KEYS`, depois do anonimizador. A pergunta de informação
  pública.
- `metadata_only`: nenhuma entrada nem saída, só metadados. A reescrita, a orientação médica,
  o fora de tema e o cadastro, porque ali pode haver dado de saúde ou dado pessoal.

Quem usa: `QaWorkflow` (`question_traces`), `RegistrationWorkflow`
(`registration_event_from_record`) e `IngestionService` (`ingestion_event`) montam os
`TraceEvent`. `LangSmithTracer` (`app/adapters/langsmith_tracing.py`) os envia, e os clientes
do LangSmith aplicam de novo `outgoing` e `anonymize_payload` na saída. O script `run_evals`
usa o anonimizador nos experimentos.

O anonimizador troca e-mail, telefone e sequências de seis ou mais dígitos. Nomes próprios não
são marcados: a Etapa 15.3 do plano decide o que fazer com nomes na política `masked`.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

# `app/ports/chat.py` declara o mesmo `Literal` para o `RunContext`.
TracePolicy = Literal["full", "masked", "metadata_only"]

# Marcadores da seção 18.4.
EMAIL_MARKER = "[redacted-email]"
PHONE_MARKER = "[redacted-phone]"
DIGITS_MARKER = "[redacted-digits]"

# A mesma expressão de e-mail da redação de logs (`app/core/logging.py`).
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# A mesma expressão de telefone de `grounding.py`.
_PHONE_RE = re.compile(
    r"(?<!\w)(?:\(\d{3}\)\s*\d{3}-\d{4}|\+\d[\d\s().-]{7,}\d|\d{3}[-.\s]\d{3}[-.\s]\d{4})(?!\w)"
)
# Seis ou mais dígitos seguidos (seção 18.4).
_LONG_DIGITS_RE = re.compile(r"(?<!\d)\d{6,}(?!\d)")
# UUID e hash hexadecimal com pelo menos uma letra ficam intactos (seção 18.4). Sem essa
# proteção, os dígitos de um id virariam `[redacted-digits]` e o rastro perderia a ligação com o
# banco. Um hexadecimal só de dígitos não é protegido: ele é um número longo.
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_HEX_TOKEN_RE = re.compile(r"\b(?=[0-9a-fA-F]*[a-fA-F])[0-9a-fA-F]{16,}\b")
# Marcador temporário com os caracteres U+E000 e U+E001, da área de uso privado do Unicode, que
# não aparecem em texto comum.
_SHIELD_RE = re.compile("\ue000(\\d+)\ue001")

# Chaves que a política `masked` deixa sair: o fluxo de `public_info` da seção 18.4.
_MASKED_KEYS = frozenset({"standalone_question", "chunks", "answer", "citations", "outcome"})
# Metadados que podem sair em qualquer política: ids, contagens, enums e versões, nunca texto
# livre. `subject` é o pseudônimo HMAC, não o id.
_METADATA_KEYS = frozenset(
    {
        "request_id",
        "trace_id",
        "app_version",
        "prompt_version",
        "outcome",
        "environment",
        "conversation_id",
        "subject",
        "intent",
        "confidence",
        "input_tokens",
        "output_tokens",
        "next_step",
        "field_names",
    }
)


@dataclass(frozen=True, slots=True)
class TraceMetadata:
    """Metadados do pedido que vão em todo rastro da pergunta (seção 18.4).

    Ambiente, versão da aplicação, conversa, pseudônimo do titular e o `trace_id` do
    OpenTelemetry, que liga o rastro do LangSmith ao rastro de sistema.
    """

    environment: str
    app_version: str
    conversation_id: str | None = None
    subject: str | None = None
    trace_id: str | None = None


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """Um run do LangSmith já filtrado pela política.

    Numa lista, o primeiro evento é a raiz e os outros são filhos dela (`parent_run_id`).
    `inputs` e `outputs` já passaram por `outgoing`, e `metadata` por `selected_metadata`.
    """

    name: str
    policy: TracePolicy
    run_id: UUID
    parent_run_id: UUID | None
    inputs: dict[str, object]
    outputs: dict[str, object]
    metadata: dict[str, object]
    tags: tuple[str, ...]


def anonymize_text(value: str) -> str:
    """Troca e-mail, telefone e dígitos longos. Preserva UUID e hash.

    1. Esconde UUIDs e hashes atrás de marcadores temporários numerados.
    2. Troca e-mails, depois telefones, depois sequências de seis ou mais dígitos. O telefone
       vem antes dos dígitos longos para ganhar o marcador mais específico.
    3. Devolve cada UUID e hash escondido ao seu lugar.
    """
    shields: list[str] = []

    def shield(match: re.Match[str]) -> str:
        """Guarda o trecho e devolve o marcador com a posição dele em `shields`."""
        shields.append(match.group(0))
        return f"\ue000{len(shields) - 1}\ue001"

    # 1.
    shielded = _UUID_RE.sub(shield, value)
    shielded = _HEX_TOKEN_RE.sub(shield, shielded)
    # 2.
    shielded = _EMAIL_RE.sub(EMAIL_MARKER, shielded)
    shielded = _PHONE_RE.sub(PHONE_MARKER, shielded)
    shielded = _LONG_DIGITS_RE.sub(DIGITS_MARKER, shielded)
    # 3.
    return _SHIELD_RE.sub(lambda match: shields[int(match.group(1))], shielded)


def anonymize_payload(payload: dict[str, object]) -> dict[str, object]:
    """Aplica `anonymize_text` a todo texto do dicionário, inclusive em listas aninhadas.

    É o `anonymizer` dos clientes do LangSmith e do script de avaliações.
    """
    walked = _walk(payload)
    if isinstance(walked, dict):
        return walked
    return {}


def outgoing(policy: TracePolicy, payload: dict[str, object]) -> dict[str, object]:
    """O que sairia como entrada ou saída dessa política.

    `metadata_only` não deixa sair nada. `masked` mantém só as chaves de `_MASKED_KEYS`.
    `full` mantém tudo. O que sai passa pelo anonimizador.
    """
    if policy == "metadata_only":
        return {}
    visible = payload
    if policy == "masked":
        visible = {key: payload[key] for key in _MASKED_KEYS if key in payload}
    return anonymize_payload(visible)


def selected_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    """Só os metadados permitidos e não nulos, depois do anonimizador."""
    selected = {
        key: value for key, value in metadata.items() if key in _METADATA_KEYS and value is not None
    }
    return anonymize_payload(selected)


def question_traces(
    *,
    run_id: UUID,
    intent: str | None,
    confidence: float | None,
    outcome: str,
    standalone_question: str | None,
    chunks: Sequence[Mapping[str, object]],
    answer: str,
    citations: Sequence[Mapping[str, object]],
    prompt_version: str | None,
    input_tokens: int,
    output_tokens: int,
    classified: bool,
    rewrite_prompt_version: str | None,
    rewrite_input_tokens: int,
    rewrite_output_tokens: int,
    request_id: str,
    trace: TraceMetadata,
) -> tuple[TraceEvent, ...]:
    """Raiz da pergunta e, se houve classificação, o passo qa.rewrite.

    A raiz `qa` usa `masked` só quando a intenção é `public_info`: aí saem a pergunta
    autônoma, os chunks, a resposta, as citações e o desfecho. Em qualquer outro caso,
    inclusive orientação médica, a raiz é `metadata_only` e leva só os metadados. O filho
    `qa.rewrite` é sempre `metadata_only`, com intenção, confiança, versão do prompt e tokens
    da reescrita: a pergunta original pode ter dado de saúde e nunca sai (seção 11.4).

    O `run_id` da raiz é o id da mensagem do assistente, então o feedback do visitante chega ao
    run certo (seção 18.4). O filho recebe um `uuid4` novo. Gerar um id aleatório aqui destoa
    da seção 6.2, que deixa a aleatoriedade fora do domínio.
    """
    public = intent == "public_info"
    policy: TracePolicy = "masked" if public else "metadata_only"
    shared = _shared_metadata(
        request_id=request_id,
        trace=trace,
        prompt_version=prompt_version,
        outcome=outcome,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    if public:
        inputs = outgoing(
            "masked",
            {
                "standalone_question": standalone_question or "",
                "chunks": [dict(chunk) for chunk in chunks],
            },
        )
        outputs = outgoing(
            "masked",
            {
                "answer": answer,
                "citations": [dict(citation) for citation in citations],
                "outcome": outcome,
            },
        )
    else:
        inputs = {}
        outputs = {}
    events = [
        TraceEvent(
            name="qa",
            policy=policy,
            run_id=run_id,
            parent_run_id=None,
            inputs=inputs,
            outputs=outputs,
            metadata=selected_metadata(shared),
            tags=("qa",),
        )
    ]
    if classified and intent is not None:
        events.append(
            TraceEvent(
                name="qa.rewrite",
                policy="metadata_only",
                run_id=uuid4(),
                parent_run_id=run_id,
                inputs={},
                outputs={},
                metadata=selected_metadata(
                    {
                        **shared,
                        "intent": intent,
                        "confidence": confidence,
                        "prompt_version": rewrite_prompt_version,
                        "input_tokens": rewrite_input_tokens,
                        "output_tokens": rewrite_output_tokens,
                    }
                ),
                tags=("qa",),
            )
        )
    return tuple(events)


def registration_event_from_record(
    record: Mapping[str, object],
    *,
    run_id: UUID,
) -> TraceEvent:
    """Só nomes de campos, próximo passo e tokens. Valores não entram.

    O `record` vem do `RegistrationWorkflow`, com `field_names`, `next_step` e os tokens do
    turno. Um valor de tipo errado vira lista vazia, `None` ou zero.
    """
    names = record.get("field_names")
    field_names = (
        [item for item in names if isinstance(item, str)] if isinstance(names, list) else []
    )
    next_step = record.get("next_step")
    return TraceEvent(
        name="registration",
        policy="metadata_only",
        run_id=run_id,
        parent_run_id=None,
        inputs={},
        outputs={},
        metadata=selected_metadata(
            {
                "field_names": field_names,
                "next_step": next_step if isinstance(next_step, str) else None,
                "input_tokens": _count(record.get("input_tokens")),
                "output_tokens": _count(record.get("output_tokens")),
            }
        ),
        tags=("registration",),
    )


def ingestion_event(*, run_id: UUID, slug: str, body: str) -> TraceEvent:
    """Corpus público, depois do anonimizador. Política full.

    O texto do documento sai inteiro, com o slug, e a saída registra a versão como `ready`.
    """
    return TraceEvent(
        name="ingestion",
        policy="full",
        run_id=run_id,
        parent_run_id=None,
        inputs=outgoing("full", {"slug": slug, "body": body}),
        outputs=outgoing("full", {"status": "ready"}),
        metadata=selected_metadata({"outcome": "ready"}),
        tags=("ingestion",),
    )


def _shared_metadata(
    *,
    request_id: str,
    trace: TraceMetadata,
    prompt_version: str | None,
    outcome: str,
    input_tokens: int,
    output_tokens: int,
) -> dict[str, object]:
    """Metadados comuns à raiz e ao filho da pergunta (seção 18.4)."""
    return {
        "request_id": request_id,
        "trace_id": trace.trace_id,
        "app_version": trace.app_version,
        "prompt_version": prompt_version,
        "outcome": outcome,
        "environment": trace.environment,
        "conversation_id": trace.conversation_id,
        "subject": trace.subject,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def _walk(value: object) -> object:
    """Percorre o valor e anonimiza cada texto. Números, booleanos e `None` ficam iguais."""
    if isinstance(value, str):
        return anonymize_text(value)
    if isinstance(value, dict):
        return {str(key): _walk(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_walk(item) for item in value]
    return value


def _count(value: object) -> int:
    """Contagem de tokens: só um `int` de verdade. `bool` é subclasse de `int` e vira 0."""
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value
