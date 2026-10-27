"""Aplica o cookie de sessão sem atributo Domain. O path é / por causa do rewrite."""

from starlette.responses import Response

from app.domain.auth import SESSION_COOKIE_NAME, SessionCookie


def apply_session_cookie(response: Response, cookie: SessionCookie) -> None:
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
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=secure,
        httponly=True,
        samesite="lax",
    )
