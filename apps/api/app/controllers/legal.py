"""Versão vigente dos Termos e do Aviso e o contato do encarregado. Seções 11.1 e 11.11.

Camada de controle, sem serviço: `GET /v1/legal/versions` lê a constante
`LEGAL_DOCUMENT_VERSION` do domínio e `PRIVACY_CONTACT_EMAIL` da configuração. Aberta a
qualquer um. A fumaça do deploy chama esta rota para conferir o `no-store` pela Vercel
(seção 22.3).

O `operation_id` nomeia a operação no OpenAPI e no `schema.ts` gerado para o frontend, e a
docstring da rota vira a `description` dela (seção 6.6). Mudar qualquer um dos dois muda o
contrato que o job `contract` confere; a explicação a mais fica em comentários.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings
from app.core.container import get_settings
from app.domain.legal import LEGAL_DOCUMENT_VERSION
from app.schemas.legal import LegalVersionsResponse

router = APIRouter()


@router.get("/v1/legal/versions", operation_id="getLegalVersions")
async def legal_versions(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LegalVersionsResponse:
    """Versão vigente dos Termos e do Aviso de Privacidade e o contato do encarregado."""
    # As duas versões são a mesma constante. `privacy_contact_email` sai `null` quando a
    # variável está vazia (seção 12).
    return LegalVersionsResponse(
        terms=LEGAL_DOCUMENT_VERSION,
        privacy_notice=LEGAL_DOCUMENT_VERSION,
        privacy_contact_email=settings.privacy_contact_email or None,
    )
