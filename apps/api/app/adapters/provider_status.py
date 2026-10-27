"""Lê o status HTTP de uma falha do provedor, sem o corpo da resposta."""

_RETRYABLE = frozenset({429, 503})


def http_status(exc: BaseException) -> int | None:
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        status = _status_of(current)
        if status is not None:
            return status
        current = current.__cause__ or current.__context__
    return None


def retryable_status(exc: BaseException) -> bool:
    return http_status(exc) in _RETRYABLE


def _status_of(exc: BaseException) -> int | None:
    for name in ("status_code", "code"):
        status = _as_status(getattr(exc, name, None))
        if status is not None:
            return status
    response = getattr(exc, "response", None)
    if response is None:
        return None
    return _as_status(getattr(response, "status_code", None))


def _as_status(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and 100 <= value <= 599:
        return value
    if isinstance(value, str) and value.isdigit():
        parsed = int(value)
        if 100 <= parsed <= 599:
            return parsed
    return None
