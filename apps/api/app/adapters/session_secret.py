"""Segredo de sessão de 256 bits. O banco guarda só o SHA-256. Seção 8.1."""

import secrets


def new_session_secret() -> str:
    return secrets.token_urlsafe(32)
