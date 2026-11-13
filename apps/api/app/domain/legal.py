"""Versão vigente dos Termos e do Aviso. Seção 11.11 do SDD.

Camada de domínio. `GET /v1/legal/versions` (`app/controllers/legal.py`) publica a versão;
o cadastro e a conta gravam os consentimentos com ela; o login, `/v1/me` e a conclusão do
cadastro calculam `needs_legal_acceptance` com ela.
"""

# Termos de Uso e Aviso de Privacidade têm a mesma versão. Uma versão nova exige novo aceite
# na próxima entrada do membro (seção 11.11).
LEGAL_DOCUMENT_VERSION = "2026-11-12.1"

# Versão do compromisso de confidencialidade da equipe (seção 29.3). Uma versão nova pede o
# aceite de novo antes de assumir o próximo atendimento. O texto fica em `src/i18n/pt.ts`.
ATTENDANT_TERMS_VERSION = "2026-11-12.1"


def needs_legal_acceptance(accepted_version: str | None) -> bool:
    """Verdadeiro quando não há aceite da versão vigente.

    `accepted_version` é a versão do aceite de `terms_and_privacy_notice` ainda válido, ou
    `None` sem nenhum. A interface pede o aceite novo quando a resposta traz verdadeiro.
    """
    return accepted_version != LEGAL_DOCUMENT_VERSION
