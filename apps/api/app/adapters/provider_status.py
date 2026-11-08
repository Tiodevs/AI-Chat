"""Lê o status HTTP de uma falha do provedor, sem o corpo da resposta.

Adaptador auxiliar do `GeminiChatProvider` (seção 17): decide se uma falha merece nova
tentativa e põe o status no log `chat.provider_failed`. Os SDKs guardam o status em lugares
diferentes (`status_code`, `code` ou `response.status_code`) e às vezes embrulham o erro HTTP
em outro, por isso a leitura procura em toda a cadeia de exceções. O corpo nunca é lido, porque
pode repetir o prompt.
"""

# Seção 17: nova tentativa só em 429 (muitos pedidos) e 503 (serviço indisponível).
_RETRYABLE = frozenset({429, 503})


def http_status(exc: BaseException) -> int | None:
    """O primeiro status HTTP achado na exceção ou nas causas dela, ou `None`.

    Segue `__cause__` (o `raise ... from`) e, na falta dele, `__context__` (a exceção que
    estava sendo tratada). O conjunto `seen` impede um laço infinito numa cadeia circular.
    """
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
    """Diz se a falha tem status 429 ou 503, os únicos que ganham nova tentativa."""
    return http_status(exc) in _RETRYABLE


def _status_of(exc: BaseException) -> int | None:
    """O status de uma exceção só, pelos atributos que os SDKs costumam usar."""
    for name in ("status_code", "code"):
        status = _as_status(getattr(exc, name, None))
        if status is not None:
            return status
    response = getattr(exc, "response", None)
    if response is None:
        return None
    return _as_status(getattr(response, "status_code", None))


def _as_status(value: object) -> int | None:
    """Um status HTTP válido, de 100 a 599, em `int` ou em texto de dígitos.

    `bool` é recusado antes, porque em Python ele é subclasse de `int`.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and 100 <= value <= 599:
        return value
    if isinstance(value, str) and value.isdigit():
        parsed = int(value)
        if 100 <= parsed <= 599:
            return parsed
    return None
