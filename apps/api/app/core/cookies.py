"""Aplica o cookie de sessão sem atributo Domain. O path é / por causa do rewrite.

Camada de núcleo. Seção 10.3 do SDD. O domínio decide nome, valor, validade e atributos
(`session_cookie` em `app/domain/auth.py` e `guest_cookie` em `app/domain/questions.py`);
este módulo só os copia para o `Set-Cookie` da resposta do Starlette. Quem usa: os
controladores `auth.py`, `account.py`, `conversations.py` e `registration.py`.

Sem `Domain`, o navegador guarda o cookie na origem do frontend, porque o rewrite da Vercel é
de mesma origem. O navegador vê `/backend/v1/...`, e a API, `/v1/...`: com `Path=/`, o cookie
vai nos dois.
"""

from starlette.responses import Response

from app.domain.auth import SESSION_COOKIE_NAME, SessionCookie
from app.domain.questions import GUEST_COOKIE_NAME


def apply_session_cookie(response: Response, cookie: SessionCookie) -> None:
    """Põe o `Set-Cookie` de `cookie` na resposta.

    Serve à sessão (`atrium_session`, 14 dias) e ao convidado (`atrium_guest`, 30 dias), que
    usam o mesmo `SessionCookie`. Os dois saem `HttpOnly` e `SameSite=Lax`, e `Secure` fora de
    `local`.
    """
    response.set_cookie(
        key=cookie.name,
        value=cookie.value,
        max_age=cookie.max_age,
        path=cookie.path,
        secure=cookie.secure,
        httponly=cookie.http_only,
        samesite=cookie.same_site,
    )


def clear_session_cookie(response: Response, *, secure: bool) -> None:
    """Apaga `atrium_session` com o mesmo path e os mesmos atributos com que foi gravado.

    O navegador só troca o cookie que casa com o nome e o path.
    """
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=secure,
        httponly=True,
        samesite="lax",
    )


def clear_guest_cookie(response: Response, *, secure: bool) -> None:
    """Apaga `atrium_guest` no login, no fim do cadastro e no logout. Etapa 15.1, seção 10.3.

    Depois de entrar ou de sair, a chave de convidado não serve mais a ninguém naquele
    navegador: as conversas dela já são do membro, ou ficam para a retenção de 30 dias.
    """
    response.delete_cookie(
        key=GUEST_COOKIE_NAME,
        path="/",
        secure=secure,
        httponly=True,
        samesite="lax",
    )
