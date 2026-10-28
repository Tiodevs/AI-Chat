"""trace_id do OpenTelemetry, quando o processo já o tem. Seção 18.2."""


def current_trace_id() -> str | None:
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        context = span.get_span_context()
        if not context.is_valid:
            return None
        return format(context.trace_id, "032x")
    except Exception:
        return None
