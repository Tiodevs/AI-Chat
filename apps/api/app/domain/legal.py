"""Versão vigente dos Termos e do Aviso. Seção 11.11 do SDD."""

LEGAL_DOCUMENT_VERSION = "2026-10-25.1"


def needs_legal_acceptance(accepted_version: str | None) -> bool:
    """Verdadeiro quando não há aceite da versão vigente."""
    return accepted_version != LEGAL_DOCUMENT_VERSION
