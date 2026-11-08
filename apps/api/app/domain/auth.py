"""Regras puras de sessão, cookie, origem, segredo da borda e limite de taxa.

Camada de domínio (seção 6.2 do SDD). Quem usa: `AuthService` e os outros serviços que abrem
sessão ou contam pedidos (`app/services`), o `ApiGuardMiddleware` (`app/core/middleware.py`),
`app/core/cookies.py` e os controladores que leem o cookie. Os módulos `documents`, `privacy`,
`questions` e `registration` deste pacote reaproveitam a janela fixa e o `RateDecision` daqui.
Só a biblioteca padrão. Seções 8.1, 10.3, 10.4 e 11.8 do SDD.

Um limite de taxa conta pedidos em janelas fixas: cada balde é uma linha de
`rate_limit_windows` com a chave de `bucket_key` e o começo da janela de `fixed_window_start`.
O repositório soma 1 e devolve a contagem já com o pedido atual, e a regra decide o 429.
"""

import hashlib
import hmac
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal

# Nome do cookie de sessão e validade de 14 dias, a mesma da sessão gravada (seção 10.3).
SESSION_COOKIE_NAME = "atrium_session"
SESSION_MAX_AGE_SECONDS = 14 * 24 * 60 * 60
# Login: 10 tentativas por e-mail a cada 15 minutos e 30 por IP a cada hora (seção 10.4).
LOGIN_EMAIL_LIMIT = 10
LOGIN_EMAIL_WINDOW = timedelta(minutes=15)
LOGIN_IP_LIMIT = 30
LOGIN_IP_WINDOW = timedelta(hours=1)
# Tamanho da senha da seção 8.5.
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 72
# Métodos que mudam estado e por isso exigem `Origin` igual a `WEB_ORIGIN` (seção 10.3).
_STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


@dataclass(frozen=True, slots=True)
class SessionCookie:
    """Atributos de um cookie, prontos para `apply_session_cookie` (`app/core/cookies.py`).

    Serve aos dois cookies da seção 10.3: `atrium_session` (`session_cookie`) e
    `atrium_guest` (`questions.guest_cookie`). Os dois são `HttpOnly`, `SameSite=Lax`, sem
    atributo `Domain` e `Secure` fora do ambiente `local`. O `path` é `/` por causa do rewrite
    de `/backend`.
    """

    name: str
    # O segredo cru, de 256 bits. Só o cookie o guarda: o banco guarda o SHA-256 (seção 8.1).
    value: str
    http_only: bool
    same_site: Literal["lax"]
    secure: bool
    path: str
    max_age: int


@dataclass(frozen=True, slots=True)
class RateDecision:
    """Resultado de uma regra de limite de taxa.

    `limited` pede o 429. `retry_after_seconds` vai no envelope do erro (seção 12) e vale 0
    quando o pedido passa.
    """

    limited: bool
    retry_after_seconds: int


def normalize_email(email: str) -> str:
    """Tira os espaços das pontas e passa para minúsculas.

    O e-mail é gravado e comparado assim (seção 8), então `Ana@X.com` e `ana@x.com` são a
    mesma conta.
    """
    return email.strip().lower()


def email_is_valid(email: str) -> bool:
    """Conferência simples de formato, sem consultar DNS nem seguir a RFC inteira.

    Exige: nenhum espaço, um `@` só, parte local não vazia e domínio com ponto que não começa
    nem termina em ponto.
    """
    if " " in email or email.count("@") != 1:
        return False
    local, domain = email.split("@")
    return bool(local) and "." in domain and not domain.startswith(".") and not domain.endswith(".")


def password_length_is_valid(password: str) -> bool:
    """Regra para criar a senha: de 12 a 72 caracteres (seção 8.5)."""
    return MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH


def password_is_checkable(password: str) -> bool:
    """Senhas fora de 1 a 72 caracteres não vão ao argon2.

    Fora dessa faixa, `AuthService` responde credenciais inválidas sem calcular hash. O mínimo
    é 1, não 12: o login confere a senha que vier, e a regra de 12 a 72 de
    `password_length_is_valid` vale para criar a senha.
    """
    return 1 <= len(password) <= MAX_PASSWORD_LENGTH


def hash_session_secret(secret: str) -> str:
    """SHA-256 em hexadecimal do segredo de um cookie.

    O banco guarda só este hash, nunca o segredo (seção 8.1, `auth_sessions` e `guest_keys`).
    Para achar a sessão de um pedido, o serviço calcula o hash do cookie e procura por ele.
    """
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def clean_user_agent(value: str) -> str:
    """Prepara o `User-Agent` para `auth_sessions.user_agent`.

    Tira o caractere nulo, que o PostgreSQL não grava em texto, e corta em 512 caracteres.
    """
    return value.replace("\x00", "")[:512]


def session_cookie_is_secure(app_env: str) -> bool:
    """`Secure` em todo ambiente menos `local` (seção 10.3). Em `test` também é `Secure`."""
    return app_env != "local"


def session_cookie(*, secret: str, app_env: str) -> SessionCookie:
    """Monta o cookie `atrium_session` com o segredo recém-criado, válido por 14 dias."""
    return SessionCookie(
        name=SESSION_COOKIE_NAME,
        value=secret,
        http_only=True,
        same_site="lax",
        secure=session_cookie_is_secure(app_env),
        path="/",
        max_age=SESSION_MAX_AGE_SECONDS,
    )


def origin_is_allowed(*, method: str, origin: str | None, web_origin: str) -> bool:
    """Proteção contra CSRF da seção 10.3, que complementa o `SameSite=Lax`.

    Métodos que não mudam estado, como `GET`, passam sempre. `POST`, `PUT`, `PATCH` e `DELETE`
    precisam de `Origin` igual a `WEB_ORIGIN`; sem o cabeçalho, o pedido é recusado. O
    `ApiGuardMiddleware` aplica a regra a todas as rotas e responde 403 `bad_origin`.
    """
    if method.upper() not in _STATE_CHANGING_METHODS:
        return True
    return bool(origin) and origin == web_origin


# Cabeçalho que a Vercel põe com o `EDGE_SECRET` na rota de `/backend`, trocando qualquer valor
# que o visitante mande (seção 10.3).
EDGE_HEADER = "x-atrium-edge"


def edge_is_trusted(*, presented: str | None, secret: str) -> bool:
    """O pedido veio pela Vercel quando traz o segredo da borda. Seção 10.3 do SDD.

    Sem segredo, o portão fica aberto: é o caso de `local` e `test`, em que o Vite faz o proxy
    sem o cabeçalho. A comparação leva o mesmo tempo para qualquer valor errado.

    `hmac.compare_digest` compara em tempo constante: o tempo da resposta não revela quantos
    caracteres do segredo acertaram. O `ApiGuardMiddleware` chama esta regra só em `/v1`.
    """
    if not secret:
        return True
    if not presented:
        return False
    return hmac.compare_digest(presented.encode("utf-8"), secret.encode("utf-8"))


def fixed_window_start(now: datetime, window: timedelta) -> datetime:
    """Começo, em UTC, da janela fixa que contém `now`.

    As janelas são alinhadas à época Unix: uma de 1 hora começa na hora cheia, uma de 1 dia à
    meia-noite UTC. Como 15 minutos, 1 hora e 1 dia dividem o dia, nenhuma janela usada aqui
    cruza a meia-noite UTC, quando o sal diário de `bucket_key` muda.

    Levanta `ValueError` para `now` sem fuso ou janela que não é positiva.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    size = int(window.total_seconds())
    if size <= 0:
        raise ValueError("window must be positive")
    moment = now.astimezone(UTC)
    epoch = int(moment.timestamp())
    return datetime.fromtimestamp(epoch - (epoch % size), tz=UTC)


def retry_after_seconds(now: datetime, window_start: datetime, window: timedelta) -> int:
    """Segundos até a janela acabar, arredondados para cima e nunca menos de 1.

    Vai no `retry_after_seconds` do 429 (seção 10.4).
    """
    remaining = (window_start + window - now.astimezone(UTC)).total_seconds()
    return max(1, math.ceil(remaining))


def bucket_key(*, purpose: str, subject: str, day: date, key: str) -> str:
    """HMAC com sal do dia. O IP cru e o e-mail não entram na chave gravada.

    A chave é `purpose:` mais o HMAC-SHA256 de `purpose|dia|subject` com
    `RATE_LIMIT_HMAC_KEY`. HMAC é um hash com chave secreta: sem a chave, ninguém recalcula a
    chave a partir de um IP. O dia funciona como o sal rotativo da seção 8.1: o mesmo IP gera
    outra chave no dia seguinte. O prefixo legível só diz de que balde é a linha.

    Levanta `ValueError` com a chave vazia, para não gravar um HMAC fraco.
    """
    if not key:
        raise ValueError("hmac key is empty")
    digest = hmac.new(
        key.encode("utf-8"),
        f"{purpose}|{day.isoformat()}|{subject}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{purpose}:{digest}"


def login_rate_decision(
    *,
    email_count: int,
    ip_count: int,
    now: datetime,
    email_window_start: datetime,
    ip_window_start: datetime,
) -> RateDecision:
    """Decide o 429 do login, pelos baldes de e-mail e de IP (seção 10.4).

    As contagens já incluem a tentativa atual, então a 11ª tentativa por e-mail e a 31ª por IP
    são recusadas. Com os dois baldes estourados, vale a espera maior. O serviço responde o 429
    com a mesma mensagem de credenciais inválidas.
    """
    retries: list[int] = []
    if email_count > LOGIN_EMAIL_LIMIT:
        retries.append(retry_after_seconds(now, email_window_start, LOGIN_EMAIL_WINDOW))
    if ip_count > LOGIN_IP_LIMIT:
        retries.append(retry_after_seconds(now, ip_window_start, LOGIN_IP_WINDOW))
    if not retries:
        return RateDecision(limited=False, retry_after_seconds=0)
    return RateDecision(limited=True, retry_after_seconds=max(retries))
