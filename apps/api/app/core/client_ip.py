"""O IP vem de x-forwarded-for e só entra no HMAC do limite. Seção 10.3.

Camada de núcleo, sem dependência. Quem usa: os controladores `auth.py`, `conversations.py`,
`privacy.py` e `registration.py`, que passam o resultado ao serviço. O serviço só o usa em
`bucket_key`, o HMAC com sal do dia (seção 10.4), e o banco nunca recebe o IP cru.

Na Railway, o `ApiGuardMiddleware` só deixa passar em `/v1` o pedido que veio pela Vercel, e a
Vercel sobrescreve o `x-forwarded-for` com o IP de quem a chamou. Assim o primeiro item não é
forjado por quem chama a API direto (seção 10.3).
"""


def client_ip(forwarded_for: str | None, fallback: str | None) -> str:
    """Primeiro item de `x-forwarded-for`, ou `fallback`, ou `"unknown"`.

    `fallback` é o `request.client.host` que o Uvicorn entrega. Sem os dois, todos os pedidos
    nessa condição dividem o mesmo balde de limite, `"unknown"`.
    """
    if forwarded_for:
        first = forwarded_for.split(",", 1)[0].strip()
        if first:
            return first
    if fallback:
        return fallback
    return "unknown"
