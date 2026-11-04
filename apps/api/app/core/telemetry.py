"""Spans próprios do Atrium. Seção 18.2 do SDD."""

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
_COMMON = frozenset({"request_id", "langsmith.run_id"})
_tracer = trace.get_tracer("atrium")

AttributeValue = str | int | float | bool | tuple[str, ...]


class SpanHandle:
    """Aplica a lista de atributos permitidos e recusa texto livre."""

    def __init__(self, name: str, span: Span) -> None:
        self._allowed = SPAN_ATTRIBUTES[name] | _COMMON
        self._span = span

    def set(self, **attributes: AttributeValue | None) -> None:
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
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return None, None
    return format(context.trace_id, "032x"), format(context.span_id, "016x")
