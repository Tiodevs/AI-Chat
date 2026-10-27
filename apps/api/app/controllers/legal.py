"""Versão vigente dos Termos e do Aviso. Seção 11.11 do SDD."""

from fastapi import APIRouter

from app.domain.legal import LEGAL_DOCUMENT_VERSION
from app.schemas.legal import LegalVersionsResponse

router = APIRouter()


@router.get("/v1/legal/versions", operation_id="getLegalVersions")
async def legal_versions() -> LegalVersionsResponse:
    """Versão vigente dos Termos e do Aviso de Privacidade."""
    return LegalVersionsResponse(
        terms=LEGAL_DOCUMENT_VERSION,
        privacy_notice=LEGAL_DOCUMENT_VERSION,
    )
