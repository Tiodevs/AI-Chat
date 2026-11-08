"""Registros de consentimento. Revogar grava revoked_at. Seção 8.1.

Camada de repositório (seção 6.2 do SDD). Lê e grava `consent_records`. O `RegistrationService`
grava os aceites da conclusão, o `AccountService` concede, revoga e lista, e o `AuthService`
confere se os Termos vigentes foram aceitos. Todas as consultas filtram por `user_id`, com o
índice `consent_records_user_id_idx`. Seções 7.2, 11.5 e 12 do SDD.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.registration import ConsentGrant, Purpose
from app.models.consent_record import ConsentRecord


class ConsentRepository:
    """Consultas do histórico de consentimentos, que só cresce."""

    def __init__(self, session: AsyncSession) -> None:
        """Usa a sessão aberta pelo serviço, sem abrir transação própria."""
        self._session = session

    async def has_current_terms(self, user_id: UUID, version: str) -> bool:
        """Diz se há aceite não revogado dos Termos e do Aviso na `version` pedida.

        É o que decide `needs_legal_acceptance` no perfil: sem aceite da versão vigente, o
        membro precisa aceitar de novo (seção 11.11).
        """
        found = await self._session.scalar(
            select(ConsentRecord.id).where(
                ConsentRecord.user_id == user_id,
                ConsentRecord.purpose == Purpose.TERMS.value,
                ConsentRecord.document_version == version,
                ConsentRecord.revoked_at.is_(None),
            )
        )
        return found is not None

    async def insert_grants(
        self,
        *,
        user_id: UUID,
        grants: tuple[ConsentGrant, ...],
        source: str,
        granted_at: datetime,
    ) -> None:
        """Grava uma linha por concessão, todas com a mesma origem e o mesmo horário.

        Conceder de novo cria linha nova, e a antiga fica no histórico (seção 8.1). O
        `flush()` envia os INSERTs dentro da transação do serviço.
        """
        for grant in grants:
            self._session.add(
                ConsentRecord(
                    id=uuid4(),
                    user_id=user_id,
                    purpose=grant.purpose,
                    document_version=grant.document_version,
                    granted_at=granted_at,
                    revoked_at=None,
                    source=source,
                )
            )
        await self._session.flush()

    async def list_for_user(self, user_id: UUID) -> list[ConsentRecord]:
        """Todas as linhas do usuário, da mais antiga para a mais nova.

        A conta monta daqui o estado atual e o histórico, e a exportação copia as linhas. O
        `id` desempata duas linhas do mesmo instante, para a ordem não variar.
        """
        rows = await self._session.scalars(
            select(ConsentRecord)
            .where(ConsentRecord.user_id == user_id)
            .order_by(ConsentRecord.granted_at.asc(), ConsentRecord.id.asc())
        )
        return list(rows)

    async def has_active(self, user_id: UUID, purpose: str, version: str | None = None) -> bool:
        """Diz se há concessão não revogada da finalidade.

        Sem `version`, qualquer versão vale, como na conferência da personalização antes de
        gravar `visitor_type`. Com `version`, só ela conta, como ao conceder de novo pela
        conta. `limit(1)` para a consulta no primeiro achado.
        """
        query = select(ConsentRecord.id).where(
            ConsentRecord.user_id == user_id,
            ConsentRecord.purpose == purpose,
            ConsentRecord.revoked_at.is_(None),
        )
        if version is not None:
            query = query.where(ConsentRecord.document_version == version)
        return await self._session.scalar(query.limit(1)) is not None

    async def revoke(self, user_id: UUID, purpose: str, revoked_at: datetime) -> bool:
        """Revoga todas as concessões vigentes do propósito. Devolve se alguma mudou.

        A linha não é apagada: só ganha `revoked_at`. `RETURNING id` diz se alguma linha
        mudou, e o serviço só grava `consent.change` quando mudou.
        """
        result = await self._session.execute(
            update(ConsentRecord)
            .where(
                ConsentRecord.user_id == user_id,
                ConsentRecord.purpose == purpose,
                ConsentRecord.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
            .returning(ConsentRecord.id)
        )
        return result.first() is not None
