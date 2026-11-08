"""Perfil devolvido por /v1/me e pelo login. Sem hash de senha. Seção 12 do SDD.

Camada de domínio. `AuthService`, `AccountService` e `RegistrationService` montam o `Profile`;
os controladores de conta, de autenticação e de cadastro o convertem no schema de resposta, e
a guarda de admin (`app/controllers/admin_guard.py`) devolve o perfil do admin às rotas. O
tipo nem tem campo para o hash da senha, então nenhuma resposta montada a partir dele pode
vazar o hash.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Profile:
    """Dados do membro ou do admin que a interface pode ver.

    `role` é `member` ou `admin`. `needs_legal_acceptance` é verdadeiro quando o aceite de
    `terms_and_privacy_notice` não é o da `LEGAL_DOCUMENT_VERSION` vigente (seção 12); a
    interface pede o aceite novo.
    """

    id: UUID
    email: str
    full_name: str
    phone: str | None
    visitor_type: str | None
    visit_reason: str | None
    role: str
    needs_legal_acceptance: bool
