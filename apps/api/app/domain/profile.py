"""Perfil devolvido por /v1/me e pelo login. Sem hash de senha. Seção 12 do SDD."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Profile:
    id: UUID
    email: str
    full_name: str
    phone: str | None
    visitor_type: str | None
    visit_reason: str | None
    role: str
    needs_legal_acceptance: bool
