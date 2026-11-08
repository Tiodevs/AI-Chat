"""Documentos, versões e chunks. Seções 7.3 e 8.1 do SDD.

Camada de repositório (seção 6.2 do SDD). Lê e grava `documents`, `document_versions` e
`chunks` com SQL escrito à mão, por `text(...)`: os valores vão em parâmetros nomeados
(`:slug`), separados do SQL. Quem usa: o `DocumentAdminService` (upload, substituição, nova
tentativa, arquivamento e lista do admin), o `IngestionService` (versão nova, publicação e
falha), o `SeedService` (semente do corpus e o `SeedLock`) e o `RetrievalRepository`, que
reaproveita `vector_literal`. Seções 6.4 e 12 do SDD.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.domain.documents import DocumentView, StoredVersion, VersionView

# Número do advisory lock da semente. O valor não significa nada: basta ser o mesmo em toda
# execução e diferente de `BOOTSTRAP_LOCK_KEY`.
SEED_LOCK_KEY = 32032026


@dataclass(frozen=True, slots=True)
class NewChunk:
    """Um chunk pronto para gravar: posição, título de seção, texto e vetor."""

    ordinal: int
    heading: str | None
    content: str
    embedding: list[float]


def vector_literal(values: list[float]) -> str:
    """Escreve o vetor como texto `[0.1, 0.2, ...]`, o formato de entrada do pgvector.

    O SQL converte o texto com `CAST(:embedding AS vector)`, porque o tipo `Vector` não
    converte valores (veja `app.models.vector`).
    """
    return json.dumps(values)


class SeedLock:
    """Lock de sessão. A semente atravessa várias transações. Seção 6.4.

    Usa uma conexão própria, aberta pelo `SeedService`, e não a sessão de um serviço.
    `pg_advisory_lock` pega um lock do PostgreSQL sobre um número, e não sobre uma linha. Na
    variante de sessão, o lock pertence à conexão e sobrevive aos commits: ele vale enquanto a
    semente grava várias versões, cada uma na própria transação. Uma segunda execução espera
    no `acquire` até a primeira chamar `release`, e por isso não duplica nada. Se o processo
    morrer, a conexão cai e o PostgreSQL solta o lock.
    """

    def __init__(self, connection: AsyncConnection) -> None:
        """Guarda a conexão dedicada que vai segurar o lock."""
        self._connection = connection

    async def acquire(self) -> None:
        """Espera o lock e o pega.

        O `commit()` fecha a transação que o `execute` abriu sozinho. O lock continua, porque
        é da sessão, e a conexão não fica parada com uma transação aberta durante a semente.
        """
        await self._connection.execute(
            text("SELECT pg_advisory_lock(:key)"),
            {"key": SEED_LOCK_KEY},
        )
        await self._connection.commit()

    async def release(self) -> None:
        """Solta o lock com `pg_advisory_unlock`, na mesma conexão que o pegou."""
        await self._connection.execute(
            text("SELECT pg_advisory_unlock(:key)"),
            {"key": SEED_LOCK_KEY},
        )
        await self._connection.commit()


class DocumentRepository:
    """Consultas do corpus: documentos, versões, chunks e a lista do admin."""

    def __init__(self, session: AsyncSession) -> None:
        """Usa a sessão aberta pelo serviço, sem abrir transação própria."""
        self._session = session

    async def admin_id(self) -> UUID | None:
        """O admin mais antigo, que a semente grava como `created_by`. `None` sem admin."""
        value = await self._session.scalar(
            text(
                "SELECT id FROM users WHERE role = 'admin' "
                "ORDER BY created_at LIMIT 1"
            )
        )
        if value is None:
            return None
        return _uuid(value)

    async def ready_checksum(self, slug: str) -> str | None:
        """SHA-256 da versão ativa do documento, se ela estiver `ready`.

        A semente compara com o hash do arquivo e pula o que não mudou. O JOIN liga o
        documento à versão apontada por `active_version`.
        """
        value = await self._session.scalar(
            text(
                "SELECT version.sha256 "
                "FROM documents AS document "
                "JOIN document_versions AS version ON version.id = document.active_version "
                "WHERE document.slug = :slug AND version.ingestion_status = 'ready'"
            ),
            {"slug": slug},
        )
        if value is None:
            return None
        return str(value)

    async def ensure_document(self, *, slug: str, title: str, created_by: UUID) -> UUID:
        """Id do documento com este slug, criado como `active` se ainda não existe.

        Usado pela semente, que roda sob o `SeedLock`: sem outra semente ao mesmo tempo, ler e
        depois inserir não duplica o documento.
        """
        existing = await self._session.scalar(
            text("SELECT id FROM documents WHERE slug = :slug"),
            {"slug": slug},
        )
        if existing is not None:
            return _uuid(existing)
        created = await self._session.scalar(
            text(
                "INSERT INTO documents (title, slug, status, created_by) "
                "VALUES (:title, :slug, 'active', :created_by) RETURNING id"
            ),
            {"title": title, "slug": slug, "created_by": created_by},
        )
        return _uuid(created)

    async def next_version(self, document_id: UUID) -> int:
        """Próximo número de versão do documento: o maior mais 1, ou 1 na primeira.

        Na substituição e na nova tentativa, o documento já está travado por `lock`. No
        upload, ele acabou de nascer na mesma transação, e a semente roda sob o `SeedLock`.
        Assim duas versões não calculam o mesmo número, e a restrição única
        `(document_id, version)` barra o caso que escapar.
        """
        value = await self._session.scalar(
            text(
                "SELECT coalesce(max(version), 0) + 1 "
                "FROM document_versions WHERE document_id = :document_id"
            ),
            {"document_id": document_id},
        )
        return int(value or 1)

    async def insert_version(
        self,
        *,
        document_id: UUID,
        version: int,
        filename: str,
        media_type: str,
        sha256: str,
        original_bytes: bytes,
    ) -> UUID:
        """Grava a versão nova em `processing`, com o texto vazio. Passo 1 da seção 7.3.

        Os bytes originais ficam na versão para uma nova tentativa. A versão ativa do
        documento não muda aqui: só a publicação troca. Devolve o id da versão.
        """
        created = await self._session.scalar(
            text(
                "INSERT INTO document_versions ("
                "document_id, version, filename, media_type, sha256, body_text, "
                "original_bytes, byte_size, ingestion_status"
                ") VALUES ("
                ":document_id, :version, :filename, :media_type, :sha256, '', "
                ":original_bytes, :byte_size, 'processing'"
                ") RETURNING id"
            ),
            {
                "document_id": document_id,
                "version": version,
                "filename": filename,
                "media_type": media_type,
                "sha256": sha256,
                "original_bytes": original_bytes,
                "byte_size": len(original_bytes),
            },
        )
        return _uuid(created)

    async def publish(
        self,
        *,
        document_id: UUID,
        version_id: UUID,
        title: str,
        body_text: str,
        chunks: list[NewChunk],
    ) -> None:
        """Grava os chunks e troca a versão ativa. Passos 4 e 5 da seção 7.3.

        Tudo roda na transação única do `IngestionService._publish`. Uma consulta de fora vê a
        versão antiga até o commit e a nova depois dele, nunca as duas pela metade (FR-11).

        1. Insere os chunks da versão nova com `active = false`, um INSERT por chunk.
        2. Marca a versão como `ready`, com o texto extraído e sem erro.
        3. Aponta `documents.active_version` para ela e grava o título.
        4. Desativa os chunks das outras versões do documento.
        5. Ativa os chunks da versão nova.
        """
        # 1. O `tsv` não aparece no INSERT: é coluna gerada, e o banco o calcula.
        for chunk in chunks:
            await self._session.execute(
                text(
                    "INSERT INTO chunks ("
                    "document_version_id, ordinal, heading, content, embedding, active"
                    ") VALUES ("
                    ":version_id, :ordinal, :heading, :content, "
                    "CAST(:embedding AS vector), false"
                    ")"
                ),
                {
                    "version_id": version_id,
                    "ordinal": chunk.ordinal,
                    "heading": chunk.heading,
                    "content": chunk.content,
                    "embedding": vector_literal(chunk.embedding),
                },
            )
        # 2.
        await self._session.execute(
            text(
                "UPDATE document_versions "
                "SET ingestion_status = 'ready', body_text = :body_text, error = NULL "
                "WHERE id = :version_id"
            ),
            {"version_id": version_id, "body_text": body_text},
        )
        # 3.
        await self._session.execute(
            text(
                "UPDATE documents "
                "SET active_version = :version_id, title = :title, updated_at = now() "
                "WHERE id = :document_id"
            ),
            {"version_id": version_id, "title": title, "document_id": document_id},
        )
        # 4. A subconsulta acha as outras versões do mesmo documento.
        await self._session.execute(
            text(
                "UPDATE chunks SET active = false "
                "WHERE document_version_id IN ("
                "SELECT id FROM document_versions "
                "WHERE document_id = :document_id AND id <> :version_id"
                ")"
            ),
            {"document_id": document_id, "version_id": version_id},
        )
        # 5.
        await self._session.execute(
            text("UPDATE chunks SET active = true WHERE document_version_id = :version_id"),
            {"version_id": version_id},
        )

    async def mark_failed(self, version_id: UUID, error: str, body_text: str) -> None:
        """Marca a versão como `failed` com a mensagem de erro. Passo 6 da seção 7.3.

        Só muda uma versão ainda em `processing`: não rebaixa uma versão `ready` nem troca o
        erro de uma que já falhou. O `CASE` mantém o texto gravado quando `body_text` chega
        vazio, como numa falha de extração. A versão ativa do documento continua a mesma.
        """
        await self._session.execute(
            text(
                "UPDATE document_versions "
                "SET ingestion_status = 'failed', error = :error, "
                "body_text = CASE WHEN :body_text = '' THEN body_text ELSE :body_text END "
                "WHERE id = :version_id AND ingestion_status = 'processing'"
            ),
            {"version_id": version_id, "error": error, "body_text": body_text},
        )

    async def fail_stale(self, deadline: datetime, error: str) -> int:
        """Passa a `failed` as versões em `processing` criadas antes de `deadline`.

        A subida da API chama com o prazo de 15 minutos (seção 7.3); a Etapa 13.5 leva a
        mesma checagem ao `retention-job`. Devolve quantas versões mudaram: o `rowcount` do
        UPDATE.
        """
        result = await self._session.execute(
            text(
                "UPDATE document_versions "
                "SET ingestion_status = 'failed', error = :error "
                "WHERE ingestion_status = 'processing' AND created_at < :deadline"
            ),
            {"deadline": deadline, "error": error},
        )
        return int(getattr(result, "rowcount", 0) or 0)

    async def archive(self, document_id: UUID) -> None:
        """Marca o documento como `archived`, o que o tira da busca (FR-12).

        Os chunks continuam `active`; quem os esconde é o predicado da seção 8.2, que exige
        documento `active`.
        """
        await self._session.execute(
            text(
                "UPDATE documents SET status = 'archived', updated_at = now() "
                "WHERE id = :document_id"
            ),
            {"document_id": document_id},
        )

    async def list_views(self) -> list[DocumentView]:
        """Ativos primeiro, depois os arquivados, do mais recente ao mais antigo."""
        result = await self._session.execute(text(_VIEW_SQL + _VIEW_ORDER))
        return [_view(row) for row in result.mappings()]

    async def view(self, document_id: UUID) -> DocumentView | None:
        """Um documento com a versão ativa e a última versão, ou `None`."""
        result = await self._session.execute(
            text(_VIEW_SQL + " WHERE document.id = :document_id"),
            {"document_id": document_id},
        )
        row = result.mappings().first()
        return None if row is None else _view(row)

    async def lock(self, document_id: UUID) -> tuple[str, str, str] | None:
        """Trava o documento para a ação do admin. Devolve slug, título e status.

        `SELECT ... FOR UPDATE` trava a linha até o fim da transação. Outra substituição, nova
        tentativa ou arquivamento do mesmo documento espera aqui. Assim a conferência de
        versão em `processing` e a criação da versão nova acontecem sem outra ação no meio
        (seção 7.3). `None` quando o documento não existe.
        """
        result = await self._session.execute(
            text(
                "SELECT slug, title, status FROM documents "
                "WHERE id = :document_id FOR UPDATE"
            ),
            {"document_id": document_id},
        )
        row = result.first()
        if row is None:
            return None
        return str(row[0]), str(row[1]), str(row[2])

    async def taken_slugs(self, base: str) -> set[str]:
        """O slug vem de slugify, então só tem letras, dígitos e hífens.

        Devolve os slugs iguais a `base` ou começados por `base-`, para o domínio escolher o
        primeiro livre entre `base`, `base-2`, `base-3`. Sem `_` nem `%` na base, o `LIKE` não
        tem curinga escondido. Não há trava: dois uploads simultâneos podem escolher o mesmo
        slug, e a restrição única recusa o segundo.
        """
        result = await self._session.execute(
            text("SELECT slug FROM documents WHERE slug = :base OR slug LIKE :pattern"),
            {"base": base, "pattern": base + "-%"},
        )
        return {str(value) for value in result.scalars()}

    async def create_document(self, *, slug: str, title: str, created_by: UUID) -> UUID:
        """Cria o documento do upload do admin, ainda sem versão ativa. Devolve o id."""
        created = await self._session.scalar(
            text(
                "INSERT INTO documents (title, slug, status, created_by) "
                "VALUES (:title, :slug, 'active', :created_by) RETURNING id"
            ),
            {"title": title, "slug": slug, "created_by": created_by},
        )
        return _uuid(created)

    async def touch(self, document_id: UUID) -> None:
        """Grava `updated_at = now()`, para o documento com versão nova subir na lista."""
        await self._session.execute(
            text("UPDATE documents SET updated_at = now() WHERE id = :document_id"),
            {"document_id": document_id},
        )

    async def latest_stored(self, document_id: UUID) -> StoredVersion | None:
        """A última versão do documento, com os bytes originais, para tentar de novo.

        `ORDER BY version DESC LIMIT 1` pega o maior número de versão.
        """
        result = await self._session.execute(
            text(
                "SELECT id, filename, media_type, sha256, ingestion_status, created_at, "
                "original_bytes FROM document_versions "
                "WHERE document_id = :document_id ORDER BY version DESC LIMIT 1"
            ),
            {"document_id": document_id},
        )
        row = result.mappings().first()
        if row is None:
            return None
        return StoredVersion(
            id=_uuid(row["id"]),
            filename=str(row["filename"]),
            media_type=str(row["media_type"]),
            sha256=str(row["sha256"]),
            ingestion_status=str(row["ingestion_status"]),
            created_at=row["created_at"],
            original_bytes=bytes(row["original_bytes"]),
        )

    async def processing_since(self, document_id: UUID) -> list[datetime]:
        """Criação de cada versão do documento ainda em `processing`.

        O serviço responde 409 se alguma tem menos de 15 minutos (seção 7.3).
        """
        result = await self._session.execute(
            text(
                "SELECT created_at FROM document_versions "
                "WHERE document_id = :document_id AND ingestion_status = 'processing'"
            ),
            {"document_id": document_id},
        )
        return list(result.scalars())

    async def id_for_slug(self, slug: str) -> UUID | None:
        """Id do documento com este slug, ou `None`. A publicação acha o documento por aqui."""
        value = await self._session.scalar(
            text("SELECT id FROM documents WHERE slug = :slug"),
            {"slug": slug},
        )
        if value is None:
            return None
        return _uuid(value)


# Colunas de versão que a lista do admin mostra. `original_bytes` fica de fora.
_VERSION_COLUMNS = (
    "id", "version", "filename", "media_type", "byte_size",
    "ingestion_status", "error", "created_at",
)


def _version_select(alias: str, prefix: str) -> str:
    """Lista as colunas de versão de `alias` com o prefixo, como `active.id AS active_id`."""
    return ", ".join(f"{alias}.{column} AS {prefix}_{column}" for column in _VERSION_COLUMNS)


# O documento com duas versões na mesma linha. `active` é a versão apontada por
# `active_version`. `latest` é a de maior número: o `LEFT JOIN LATERAL` roda a subconsulta uma
# vez por documento, e ela pode citar `document.id` da linha de fora. Os dois são `LEFT`, então
# um documento sem versão ativa ou sem versão alguma ainda aparece, com as colunas nulas.
_VIEW_SQL = (
    "SELECT document.id, document.title, document.slug, document.status, "
    "document.created_at, document.updated_at, "
    + _version_select("active", "active")
    + ", "
    + _version_select("latest", "latest")
    + " FROM documents AS document "
    "LEFT JOIN document_versions AS active ON active.id = document.active_version "
    "LEFT JOIN LATERAL ("
    "SELECT * FROM document_versions AS candidate "
    "WHERE candidate.document_id = document.id "
    "ORDER BY candidate.version DESC LIMIT 1"
    ") AS latest ON true"
)
# `status = 'archived'` é falso para os ativos, e falso vem antes de verdadeiro na ordem
# crescente: os ativos ficam primeiro. Depois, o mais atualizado e o título.
_VIEW_ORDER = " ORDER BY document.status = 'archived', document.updated_at DESC, document.title"


def _version(row: RowMapping, prefix: str) -> VersionView | None:
    """Monta a versão com o prefixo dado, ou `None` quando o LEFT JOIN não achou versão."""
    if row[f"{prefix}_id"] is None:
        return None
    error = row[f"{prefix}_error"]
    return VersionView(
        id=_uuid(row[f"{prefix}_id"]),
        version=int(row[f"{prefix}_version"]),
        filename=str(row[f"{prefix}_filename"]),
        media_type=str(row[f"{prefix}_media_type"]),
        byte_size=int(row[f"{prefix}_byte_size"]),
        ingestion_status=str(row[f"{prefix}_ingestion_status"]),
        error=None if error is None else str(error),
        created_at=row[f"{prefix}_created_at"],
    )


def _view(row: RowMapping) -> DocumentView:
    """Monta a visão do documento a partir de uma linha de `_VIEW_SQL`."""
    return DocumentView(
        id=_uuid(row["id"]),
        title=str(row["title"]),
        slug=str(row["slug"]),
        status=str(row["status"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        active_version=_version(row, "active"),
        latest_version=_version(row, "latest"),
    )


def _uuid(value: object) -> UUID:
    """Aceita o UUID que o driver devolve ou o texto dele."""
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
