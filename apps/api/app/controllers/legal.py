"""Versão vigente dos Termos e do Aviso e o contato do encarregado. Seções 11.1 e 11.11."""

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
    return LegalVersionsResponse(
        terms=LEGAL_DOCUMENT_VERSION,
        privacy_notice=LEGAL_DOCUMENT_VERSION,
        privacy_contact_email=settings.privacy_contact_email or None,
    )
