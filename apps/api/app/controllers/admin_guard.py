"""Exige a sessão de um admin nas rotas de /v1/admin. Seções 10.5 e 12 do SDD.

Camada de controle. `require_admin` não é uma dependência do FastAPI: cada rota de admin a
chama na primeira linha, quando o FastAPI já leu o corpo do pedido. A Etapa 15.2 a torna uma
dependência e põe um limite de `content-length` no upload, para um pedido sem sessão receber
401 antes de o corpo ser lido. Quem usa: `admin_documents.py`, `admin_insights.py` e
`admin_privacy.py`. Cria o `AuthService` aqui, sem passar pela raiz de composição.
"""

from fastapi import Request

from app.adapters.password_hasher import get_password_hasher
from app.core.config import Settings
from app.domain.auth import SESSION_COOKIE_NAME
from app.domain.profile import Profile
from app.ports.clock import Clock


async def require_admin(request: Request, settings: Settings, clock: Clock) -> Profile:
    """Sem sessão, 401. Membro, 403.

    Devolve o `Profile` do admin dono do cookie `atrium_session`. Sem sessão válida, o
    serviço levanta `Unauthenticated`; com a sessão de um membro, `Forbidden`. Os dois viram o
    envelope da seção 12 em `app.core.errors`. Cada chamada lê a sessão no banco numa
    transação curta.
    """
    from app.services.auth import AuthService

    return await AuthService(
        database_url=settings.database_url,
        clock=clock,
        hasher=get_password_hasher(),
        hmac_key=settings.rate_limit_hmac_key,
        app_env=settings.app_env,
    ).require_admin(request.cookies.get(SESSION_COOKIE_NAME))
