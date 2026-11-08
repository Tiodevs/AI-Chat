"""Sessões de cadastro. O serializador da transcrição não tem senha. Seção 8.1.

Camada de repositório (seção 6.2 do SDD). Lê e grava `registration_sessions`. Quem usa é o
`RegistrationService`, que carrega a sessão, roda a máquina de estados e o grafo fora da
transação, e grava o resultado com a linha travada (seção 7.2). Devolve `RegistrationRecord`,
uma cópia imutável, e não a entidade.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.registration_session import RegistrationSession


@dataclass(frozen=True, slots=True)
class RegistrationRecord:
    """O estado de uma sessão de cadastro, como está no banco.

    `fields` e `transcript` são os documentos JSONB; a máquina de estados os lê com
    `machine_from_document` e `load_transcript`.
    """

    id: UUID
    status: str
    path: str
    fields: dict[str, Any]
    password_hash: str | None
    transcript: list[Any]
    user_id: UUID | None
    expires_at: datetime


class RegistrationRepository:
    """Consultas de `registration_sessions`: criar, ler, travar e gravar."""

    def __init__(self, session: AsyncSession) -> None:
        """Usa a sessão aberta pelo serviço, sem abrir transação própria."""
        self._session = session

    async def insert(
        self,
        *,
        session_id: UUID,
        status: str,
        path: str,
        fields: dict[str, Any],
        password_hash: str | None,
        transcript: list[Any],
        user_id: UUID | None,
        expires_at: datetime,
    ) -> RegistrationRecord:
        """Grava uma sessão nova com o id que o serviço gerou.

        O formulário sem sessão também grava uma linha, já `completed`, e por isso ele entra
        no funil do admin.
        """
        row = RegistrationSession(
            id=session_id,
            status=status,
            path=path,
            fields=fields,
            password_hash=password_hash,
            transcript=transcript,
            user_id=user_id,
            expires_at=expires_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _record(row)

    async def get(self, session_id: UUID) -> RegistrationRecord | None:
        """Lê a sessão pela chave primária, sem trava. `None` quando não existe."""
        row = await self._session.get(RegistrationSession, session_id)
        if row is None:
            return None
        return _record(row)

    async def lock(self, session_id: UUID) -> RegistrationRecord | None:
        """Lê a sessão com `SELECT ... FOR UPDATE`, que trava a linha até o fim da transação.

        Dois pedidos na mesma sessão, como dois aceites, esperam um pelo outro aqui. O segundo
        lê o estado que o primeiro gravou, e o aceite repetido devolve o mesmo usuário. A trava
        só vale na transação da gravação: o serviço lê a sessão e chama o modelo antes, em
        outra transação. A Etapa 13.3 acrescenta a coluna `version` para recusar a gravação
        quando a sessão mudou nesse meio-tempo.
        """
        row = await self._session.scalar(
            select(RegistrationSession)
            .where(RegistrationSession.id == session_id)
            .with_for_update()
        )
        if row is None:
            return None
        return _record(row)

    async def save(self, record: RegistrationRecord) -> RegistrationRecord:
        """Grava o registro inteiro sobre a linha, num UPDATE só, e devolve o mesmo registro.

        Os documentos JSONB vão inteiros, nunca um item dentro deles. O UPDATE não confere se
        a linha existe nem se ela mudou desde a leitura.
        """
        await self._session.execute(
            update(RegistrationSession)
            .where(RegistrationSession.id == record.id)
            .values(
                status=record.status,
                path=record.path,
                fields=record.fields,
                password_hash=record.password_hash,
                transcript=record.transcript,
                user_id=record.user_id,
                expires_at=record.expires_at,
            )
        )
        return record


def _record(row: RegistrationSession) -> RegistrationRecord:
    """Copia a entidade num registro imutável.

    `dict(...)` e a lista nova copiam os documentos JSONB, para o registro não dividir objetos
    com a entidade da sessão. Um item da transcrição que não seja objeto JSON é descartado.
    """
    fields = dict(row.fields)
    transcript = [dict(item) for item in row.transcript if isinstance(item, dict)]
    return RegistrationRecord(
        id=row.id,
        status=row.status,
        path=row.path,
        fields=fields,
        password_hash=row.password_hash,
        transcript=transcript,
        user_id=row.user_id,
        expires_at=row.expires_at,
    )
