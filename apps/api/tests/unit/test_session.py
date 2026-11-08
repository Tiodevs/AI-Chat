"""O `sslmode` da URL do banco vira o argumento `ssl` do asyncpg. Seção 17 do SDD.

A seção 17 diz que a API fala com o banco pelo asyncpg. `adapt_asyncpg_url`, de
`app/db/session.py`, tira o `sslmode` da query, porque o asyncpg recebe esse valor em `ssl`, e
devolve a URL sem ele junto com os `connect_args`. A função é pura: não abre conexão nem usa
rede.
"""

from app.db.session import adapt_asyncpg_url


def test_sslmode_is_passed_to_asyncpg_as_ssl() -> None:
    url, connect_args = adapt_asyncpg_url(
        "postgresql+asyncpg://user:secret@db.example:5432/atrium?sslmode=require"
    )
    assert connect_args == {"ssl": "require"}
    assert "sslmode" not in url
    assert url == "postgresql+asyncpg://user:secret@db.example:5432/atrium"


def test_url_without_sslmode_is_unchanged() -> None:
    original = "postgresql+asyncpg://localhost/atrium"
    url, connect_args = adapt_asyncpg_url(original)
    assert url == original
    assert connect_args == {}
