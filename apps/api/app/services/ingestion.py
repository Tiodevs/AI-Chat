"""Ingestão de uma versão de documento: extrair, dividir, embedar e publicar. Seção 7.3.

Camada de serviço. Dois caminhos usam `IngestionService`:

- o admin, por `DocumentAdminService.process` (`documents.py`), numa tarefa de fundo do
  FastAPI que roda depois da resposta, para uma versão já gravada em `processing`;
- a semente, por `SeedService.run` (`seed.py`), que chama `ingest_new_version` e espera o
  fim de cada arquivo.

`fail_stale_processing_versions` roda no `lifespan` de `main.py`, na subida da API.

Usa as portas `TextExtractor` (`adapters/text_extractor.py` lê PDF e UTF-8 num threadpool),
`EmbeddingProvider` (um texto por pedido, no máximo 4 simultâneos, seção 17) e
`TraceRecorder` (LangSmith com a política `full`, seção 18.4), o `DocumentRepository` e as
funções puras de `domain/chunking.py` e `domain/embedding_text.py`.

Transações: abrir a versão, publicar e marcar falha são transações curtas e separadas. A
extração e os embeddings rodam fora de qualquer transação. Observabilidade: spans
`ingestion.extract`, `ingestion.embed` e `ingestion.publish` (seção 18.2), contador
`atrium_ingestion_versions{status}` com `embedded` ou `failed` (seção 18.3) e logs
`ingestion.failed`, `ingestion.ready` e `ingestion.trace_failed`, com o slug e sem o texto.

Divergência: a seção 6.4 põe o divisor de chunks num threadpool, mas `split_markdown` roda
no loop de eventos. A Etapa 13.1 o move para `asyncio.to_thread`.
"""

from datetime import timedelta
from uuid import UUID, uuid4

import structlog

from app.core.metrics import INGESTION_VERSIONS
from app.core.telemetry import traced_span
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.chunking import split_markdown
from app.domain.embedding_text import document_embedding_text
from app.domain.trace_policy import ingestion_event
from app.ports.clock import Clock
from app.ports.embedding import EmbeddingProvider
from app.ports.text_extractor import TextExtractor
from app.ports.tracing import NullTracer, TraceRecorder
from app.prompts.corpus import (
    EMBED_FAILED,
    EMPTY_DOCUMENT,
    EXTRACT_FAILED,
    PROCESSING_TIMED_OUT,
)
from app.repositories.documents import DocumentRepository, NewChunk

# Seção 7.3: uma versão em `processing` há mais tempo que isso ficou presa. É o mesmo prazo
# de `domain/documents.py:PROCESSING_GRACE`, que bloqueia uma versão nova enquanto isso.
STALE_PROCESSING_AFTER = timedelta(minutes=15)


class IngestionService:
    """Os passos 2 a 6 da seção 7.3 para uma versão de documento.

    `tracer` é o `NullTracer` quando o LangSmith está desligado.
    """

    def __init__(
        self,
        database_url: str,
        embeddings: EmbeddingProvider,
        extractor: TextExtractor,
        tracer: TraceRecorder | None = None,
    ) -> None:
        self._database_url = database_url
        self._embeddings = embeddings
        self._extractor = extractor
        self._tracer = tracer or NullTracer()

    async def ingest_new_version(
        self,
        *,
        slug: str,
        title: str,
        filename: str,
        media_type: str,
        data: bytes,
        sha256: str,
        created_by: UUID,
    ) -> str:
        """Grava uma versão nova em `processing` e a processa na mesma chamada.

        É o caminho da semente. O documento nasce se o slug ainda não existe. Devolve
        `"embedded"` ou `"failed"`, como `process_version`.
        """
        version_id = await self._open_version(
            slug=slug,
            title=title,
            filename=filename,
            media_type=media_type,
            sha256=sha256,
            data=data,
            created_by=created_by,
        )
        return await self.process_version(
            version_id=version_id,
            slug=slug,
            title=title,
            media_type=media_type,
            data=data,
        )

    async def process_version(
        self,
        *,
        version_id: UUID,
        slug: str,
        title: str,
        media_type: str,
        data: bytes,
    ) -> str:
        """Passos 2 a 6 da seção 7.3 para uma versão já gravada em processing.

        1. Extrai o texto pela porta. Qualquer exceção marca a versão `failed` com
           `EXTRACT_FAILED`, sem chegar ao embedding.
        2. Divide pelos títulos Markdown e em blocos de 1.000 caracteres com sobreposição de
           150. Texto vazio ou nenhum chunk marca `failed` com `EMPTY_DOCUMENT`.
        3. Monta o texto de cada chunk com o prefixo de documento da seção 8.3 e embeda.
        4. Um número de vetores diferente do de chunks marca `failed` com `EMBED_FAILED`.
        5. Publica numa transação: chunks novos, versão `ready`, `active_version` apontando
           para ela, chunks antigos desativados e novos ativados. Quem busca nunca vê o
           documento pela metade.
        6. Qualquer exceção dos passos 2 a 5 marca `failed` com `EMBED_FAILED`. A versão
           ativa anterior continua no lugar (FR-11).
        7. Manda o rastro ao LangSmith. Uma falha aqui só vai para o log.

        Marcar falha só muda uma versão ainda em `processing` e guarda o texto extraído,
        se houver. Devolve `"embedded"` ou `"failed"`.
        """
        body = ""
        # 1. Extração, num threadpool dentro do adaptador.
        try:
            with traced_span("ingestion.extract", media_type=media_type, byte_size=len(data)):
                body = await self._extractor.extract(data, media_type)
        except Exception:
            _log("warning", "ingestion.failed", slug=slug, error_type="extract")
            await self._fail(version_id, EXTRACT_FAILED, body)
            INGESTION_VERSIONS.labels(status="failed").inc()
            return "failed"
        try:
            # 2. Divisão em chunks, ainda no loop de eventos (Etapa 13.1).
            drafts = split_markdown(body)
            if not body.strip() or not drafts:
                await self._fail(version_id, EMPTY_DOCUMENT, body)
                INGESTION_VERSIONS.labels(status="failed").inc()
                return "failed"
            # 3. O prefixo vai só na chamada de embedding, não no corpo gravado (seção 8.3).
            texts = [
                document_embedding_text(title, draft.heading, draft.content) for draft in drafts
            ]
            with traced_span(
                "ingestion.embed",
                chunk_count=len(texts),
                model=self._embeddings.model_name,
            ):
                vectors = await self._embeddings.embed_documents(texts)
            # 4. Um vetor por chunk, ou nada é publicado.
            if len(vectors) != len(drafts):
                await self._fail(version_id, EMBED_FAILED, body)
                INGESTION_VERSIONS.labels(status="failed").inc()
                return "failed"
            chunks = [
                NewChunk(index, draft.heading, draft.content, vector)
                for index, (draft, vector) in enumerate(zip(drafts, vectors, strict=True))
            ]
            # 5. A seção 18.2 pede `document_id` e `version` neste span. O código passa o
            # slug como `document_id` e não passa a versão.
            with traced_span("ingestion.publish", document_id=slug):
                await self._publish(
                    slug=slug,
                    version_id=version_id,
                    title=title,
                    body_text=body,
                    chunks=chunks,
                )
        except Exception:
            # 6. A falha atinge só a versão nova.
            _log("warning", "ingestion.failed", slug=slug, error_type="embedding")
            await self._fail(version_id, EMBED_FAILED, body)
            INGESTION_VERSIONS.labels(status="failed").inc()
            return "failed"
        INGESTION_VERSIONS.labels(status="embedded").inc()
        # 7. Corpus público e fictício: a política `full` envia o texto, depois do
        # anonimizador (seção 18.4).
        try:
            self._tracer.record_many(
                (
                    ingestion_event(
                        run_id=uuid4(),
                        slug=slug,
                        body=body,
                    ),
                )
            )
        except Exception:
            _log("warning", "ingestion.trace_failed", slug=slug)
        _log("info", "ingestion.ready", slug=slug, chunks=len(chunks))
        return "embedded"

    async def _open_version(
        self,
        *,
        slug: str,
        title: str,
        filename: str,
        media_type: str,
        sha256: str,
        data: bytes,
        created_by: UUID,
    ) -> UUID:
        """Garante o documento e grava a versão seguinte em `processing`, numa transação.

        Guarda os bytes originais e o checksum, que a semente compara no próximo deploy.
        """
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = DocumentRepository(session)
            document_id = await repository.ensure_document(
                slug=slug,
                title=title,
                created_by=created_by,
            )
            number = await repository.next_version(document_id)
            version_id = await repository.insert_version(
                document_id=document_id,
                version=number,
                filename=filename,
                media_type=media_type,
                sha256=sha256,
                original_bytes=data,
            )
        return version_id

    async def _publish(
        self,
        *,
        slug: str,
        version_id: UUID,
        title: str,
        body_text: str,
        chunks: list[NewChunk],
    ) -> None:
        """Passo 5 da seção 7.3, numa transação só.

        Um documento que sumiu no meio levanta `RuntimeError`, e `process_version` marca a
        versão como `failed`.
        """
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = DocumentRepository(session)
            document_id = await repository.id_for_slug(slug)
            if document_id is None:
                raise RuntimeError(slug)
            await repository.publish(
                document_id=document_id,
                version_id=version_id,
                title=title,
                body_text=body_text,
                chunks=chunks,
            )

    async def _fail(self, version_id: UUID, error: str, body_text: str) -> None:
        """Marca a versão como `failed` com a mensagem de `prompts/corpus.py`.

        Transação própria, porque a falha pode vir no meio de outra que foi desfeita.
        """
        async with open_session(self._database_url) as session, UnitOfWork(session):
            await DocumentRepository(session).mark_failed(version_id, error, body_text)


async def fail_stale_processing_versions(database_url: str, clock: Clock) -> int:
    """Marca como `failed` as versões presas em `processing` há mais de 15 minutos.

    Um processo que cai no meio de uma ingestão deixa a versão nesse estado (seção 7.3).
    Roda na subida da API, e o `lifespan` só registra `ingestion.stale_check_failed` se ela
    falhar. Devolve quantas versões mudaram. A Etapa 13.5 também a roda no `retention-job`.
    """
    deadline = clock.now() - STALE_PROCESSING_AFTER
    async with open_session(database_url) as session, UnitOfWork(session):
        changed = await DocumentRepository(session).fail_stale(deadline, PROCESSING_TIMED_OUT)
    return changed


def _log(level: str, event: str, **fields: object) -> None:
    """Registra no log `atrium`. Um erro do próprio log não interrompe a ingestão."""
    try:
        getattr(structlog.get_logger("atrium"), level)(event, **fields)
    except Exception:
        return
