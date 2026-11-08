"""Segredo de sessão de 256 bits. O banco guarda só o SHA-256. Seção 8.1.

Adaptador de infraestrutura: a única fonte de aleatoriedade dos cookies. Quem usa: o
`AuthService` (sessão de login), o `ConversationService` (chave de convidado) e o
`RegistrationService` (sessão aberta no fim do cadastro). O hash fica em
`app.domain.auth.hash_session_secret`.
"""

import secrets


def new_session_secret() -> str:
    """Um segredo novo para o cookie: 32 bytes aleatórios do módulo `secrets`, em base64 de URL.

    32 bytes são os 256 bits das seções 8.1 e 10.3. O cookie guarda este texto; o banco, só o
    SHA-256 dele.
    """
    return secrets.token_urlsafe(32)
