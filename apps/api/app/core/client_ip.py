"""O IP vem de x-forwarded-for e só entra no HMAC do limite. Seção 10.3."""


def client_ip(forwarded_for: str | None, fallback: str | None) -> str:
    if forwarded_for:
        first = forwarded_for.split(",", 1)[0].strip()
        if first:
            return first
    if fallback:
        return fallback
    return "unknown"
