"""trace_id do OpenTelemetry, quando o processo já o tem. Seção 18.2.

Camada de núcleo. Quem usa: `app/services/conversations.py`, que põe o id nos metadados do
rastro do LangSmith, para navegar entre os dois rastros (seções 18.2 e 18.4). Faz o mesmo
cálculo de `app.core.telemetry.span_ids`, só para o rastro.
"""


def current_trace_id() -> str | None:
    """`trace_id` do span corrente em 32 dígitos hexadecimais, ou `None` sem span.

    Qualquer erro também devolve `None`: o id é só um metadado do rastro, e a falta dele não
    interrompe a pergunta. O import fica dentro do `try`, então até a falta do pacote cai aí.
    """
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        context = span.get_span_context()
        if not context.is_valid:
            return None
        return format(context.trace_id, "032x")
    except Exception:
        return None
