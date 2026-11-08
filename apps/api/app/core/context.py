"""O `request_id` do pedido em curso, num `ContextVar`. Seção 18 do SDD (NFR-6).

Camada de núcleo, sem dependência. O `RequestIdMiddleware` grava o valor no começo de cada
pedido HTTP e o desfaz no fim. Quem lê: o envelope de erro (`app/core/errors.py` e o
`_send_error` de `app/core/middleware.py`), os spans (`app/core/telemetry.py`) e os
controladores `conversations.py` e `registration.py`, que passam o id ao serviço.

Um `ContextVar` acompanha a tarefa do asyncio: cada pedido vê o próprio valor, mesmo com
vários pedidos ao mesmo tempo no mesmo processo.
"""

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def current_request_id() -> str:
    """O `request_id` do pedido, ou `"missing"` fora de um pedido HTTP.

    Fora de um pedido, como num script ou num teste que chama a função direto, não há id. O
    texto fixo preenche o campo, que o envelope de erro da seção 12 exige.
    """
    request_id = request_id_var.get()
    if request_id is None:
        return "missing"
    return request_id
