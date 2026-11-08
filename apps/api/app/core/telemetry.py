"""Spans próprios do Atrium. Seção 18.2 do SDD.

Camada de núcleo. `traced_span` abre um span filho do span corrente, que no pedido HTTP é o
que o `opentelemetry-instrument` cria, e só grava os atributos da tabela da seção 18.2, mais
`request_id` e `langsmith.run_id`: texto de pergunta ou de documento não vira atributo
(NFR-7). Quem usa: `app/workflows/qa.py`, `app/workflows/registration.py`,
`app/services/ingestion.py` e `app/services/retention.py`. `span_ids` alimenta o log
(`app/core/logging.py`).

Sem o SDK configurado, a API do OpenTelemetry entrega spans que não gravam nada, e o código
roda igual. Os testes trocam `_tracer` por um tracer com exportador em memória.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

from app.core.context import request_id_var

# Atributos permitidos por span (tabela da seção 18.2). Qualquer outro é descartado.
SPAN_ATTRIBUTES: dict[str, frozenset[str]] = {
    "qa.rewrite": frozenset({"intent", "model", "prompt_version"}),
    "qa.embed_query": frozenset({"model", "dimensions"}),
    "qa.retrieve": frozenset({"candidate_count", "top_similarity"}),
    "qa.generate": frozenset({"model", "input_tokens", "output_tokens", "prompt_version"}),
    "qa.ground": frozenset({"outcome"}),
    "registration.extract": frozenset({"field_names", "model"}),
    "registration.decide": frozenset({"next_step"}),
    "ingestion.extract": frozenset({"media_type", "byte_size"}),
    "ingestion.embed": frozenset({"chunk_count", "model"}),
    "ingestion.publish": frozenset({"document_id", "version"}),
    "retention.run": frozenset({"rule", "deleted_count"}),
}
# Valem em qualquer span: ligam o span ao log e ao rastro do LangSmith (seção 18.2).
_COMMON = frozenset({"request_id", "langsmith.run_id"})
_tracer = trace.get_tracer("atrium")

# Tipos que um atributo aceita: ids, contagens, enums, durações e listas de nomes.
AttributeValue = str | int | float | bool | tuple[str, ...]


class SpanHandle:
    """Aplica a lista de atributos permitidos e recusa texto livre.

    A recusa é pelo nome: uma chave fora da lista do span some sem erro, e um valor `None`
    também. O conteúdo de um atributo permitido não é conferido.
    """

    def __init__(self, name: str, span: Span) -> None:
        self._allowed = SPAN_ATTRIBUTES[name] | _COMMON
        self._span = span

    def set(self, **attributes: AttributeValue | None) -> None:
        """Grava os atributos permitidos no span.

        `__` no nome vira `.`: `langsmith__run_id` chega como `langsmith.run_id`, que não
        cabe num argumento nomeado do Python.
        """
        for key, value in attributes.items():
            if value is None or key.replace("__", ".") not in self._allowed:
                continue
            self._span.set_attribute(key.replace("__", "."), value)


@contextmanager
def traced_span(
    name: str,
    *,
    run_id: object | None = None,
    **attributes: AttributeValue | None,
) -> Iterator[SpanHandle]:
    """Abre o span `name` como filho do span corrente e entrega um `SpanHandle`.

    Levanta `ValueError` para um nome fora da tabela da seção 18.2. Grava o `request_id` do
    pedido e, quando vier, o `run_id` em `langsmith.run_id`. Uma exceção no bloco grava o
    nome da classe em `error.type`, marca o span com erro e segue subindo. `BaseException`
    inclui o cancelamento, como quando o visitante fecha o fluxo.

    O `start_as_current_span` mantém o padrão do OpenTelemetry, que também grava no span um
    evento `exception` com a mensagem e a pilha do erro, fora da lista de atributos.
    """
    if name not in SPAN_ATTRIBUTES:
        raise ValueError(f"span desconhecido: {name}")
    with _tracer.start_as_current_span(name) as span:
        handle = SpanHandle(name, span)
        request_id = request_id_var.get()
        if request_id is not None:
            span.set_attribute("request_id", request_id)
        if run_id is not None:
            span.set_attribute("langsmith.run_id", str(run_id))
        handle.set(**attributes)
        try:
            yield handle
        except BaseException as error:
            span.set_attribute("error.type", type(error).__name__)
            span.set_status(Status(StatusCode.ERROR))
            raise


def span_ids() -> tuple[str | None, str | None]:
    """`trace_id` e `span_id` do span corrente, em hexadecimal, ou `(None, None)` sem span.

    O formato é o que o OpenTelemetry mostra: 32 dígitos para o rastro e 16 para o span.
    """
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return None, None
    return format(context.trace_id, "032x"), format(context.span_id, "016x")
