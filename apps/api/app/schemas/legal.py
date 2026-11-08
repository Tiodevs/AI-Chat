"""Versões dos documentos legais. Seções 11.11 e 12 do SDD.

Camada de schema (seção 6.2 do SDD). Resposta de `GET /v1/legal/versions`, montada pelo
controlador `legal`.
"""

from pydantic import BaseModel


# `terms` e `privacy_notice` são iguais a `LEGAL_DOCUMENT_VERSION`; o frontend manda essa
# versão no aceite. `privacy_contact_email` vem de `PRIVACY_CONTACT_EMAIL`, ou `null` com a
# variável vazia, e a página Privacy o mostra como contato do encarregado (seção 11.1).
class LegalVersionsResponse(BaseModel):
    terms: str
    privacy_notice: str
    privacy_contact_email: str | None
