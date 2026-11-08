"""Semente idempotente do corpus. Seções 6.4 e 7.3 do SDD.

Camada de serviço. `scripts/seed.py` chama `SeedService.run` no comando de pré-implantação
da Railway (seção 22.1), depois de `bootstrap_admin`, e nunca na subida da API. A semente
usa o mesmo pipeline do admin, `IngestionService`, de forma síncrona: cada arquivo é
extraído, dividido, embedado e publicado antes do próximo.

Concorrência: a semente pega `pg_advisory_lock`, um lock de sessão do PostgreSQL. Ele vale
enquanto a conexão que o pegou estiver aberta, atravessando várias transações, então duas
execuções simultâneas esperam uma pela outra em vez de criar versões duplicadas. Essa
conexão fica parada fora de transação durante a semente; a ingestão usa conexões próprias.
"""

import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import structlog

from app.db.session import make_engine, open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.chunking import markdown_title
from app.domain.errors import ValidationFailed
from app.prompts.corpus import CORPUS_MISSING, EMBED_FAILED, NO_ADMIN
from app.repositories.documents import DocumentRepository, SeedLock
from app.services.ingestion import IngestionService


@dataclass(frozen=True, slots=True)
class SeedReport:
    """Quantos arquivos foram embedados de novo e quantos já estavam iguais no banco."""

    embedded: int
    unchanged: int


class SeedService:
    """Semeia `content/corpus` (seção 9). `corpus_dir` vem de `scripts/seed.py`."""

    def __init__(
        self,
        database_url: str,
        ingestion: IngestionService,
        corpus_dir: Path,
    ) -> None:
        self._database_url = database_url
        self._ingestion = ingestion
        self._corpus_dir = corpus_dir

    async def run(self) -> SeedReport:
        """Ingere os arquivos novos ou mudados do corpus e pula os iguais.

        1. Exige a pasta do corpus.
        2. Pega o lock da semente.
        3. Usa o admin mais antigo como `created_by` dos documentos.
        4. Para cada `.md`, compara o SHA-256 dos bytes com o checksum da versão ativa
           `ready`. Igual, pula: é isso que deixa a semente idempotente e barata num novo
           deploy. Diferente, cria uma versão nova com o slug igual ao nome do arquivo.
        5. Registra `seed.finished` e, se algum arquivo falhou, levanta depois de tentar
           todos, para o pré-deploy falhar e o deploy parar.

        Erros: `ValidationFailed` com `CORPUS_MISSING`, `NO_ADMIN` ou `EMBED_FAILED`. O
        script imprime a mensagem e sai com código 1. Cada arquivo chama o embedding pela
        rede, fora de transação.
        """
        # 1. Sem a pasta, nada a semear.
        if not self._corpus_dir.is_dir():
            raise ValidationFailed(CORPUS_MISSING)
        # 2. Lock de sessão, solto no `finally` de `_locked`.
        async with self._locked():
            # 3. `bootstrap_admin` roda antes no pré-deploy e cria o primeiro admin.
            admin_id = await self._admin_id()
            if admin_id is None:
                raise ValidationFailed(NO_ADMIN)
            embedded = 0
            unchanged = 0
            failed = 0
            # 4. Um arquivo de cada vez, em ordem alfabética.
            for path in _markdown_files(self._corpus_dir):
                data = path.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                if await self._ready_checksum(path.stem) == digest:
                    unchanged += 1
                    structlog.get_logger("atrium").info("seed.unchanged", slug=path.stem)
                    continue
                # O título é o primeiro `#` do arquivo, ou o nome sem a extensão.
                title = markdown_title(data.decode("utf-8"), path.stem)
                outcome = await self._ingestion.ingest_new_version(
                    slug=path.stem,
                    title=title,
                    filename=path.name,
                    media_type="text/markdown",
                    data=data,
                    sha256=digest,
                    created_by=admin_id,
                )
                if outcome == "embedded":
                    embedded += 1
                    structlog.get_logger("atrium").info("seed.embedded", slug=path.stem)
                else:
                    failed += 1
            # 5. Uma falha não impede os outros arquivos, mas falha o comando no fim.
            structlog.get_logger("atrium").info(
                "seed.finished",
                embedded=embedded,
                unchanged=unchanged,
                failed=failed,
            )
            if failed:
                raise ValidationFailed(EMBED_FAILED)
            report = SeedReport(embedded=embedded, unchanged=unchanged)
        return report

    async def _admin_id(self) -> UUID | None:
        """Id do admin mais antigo, numa transação curta de leitura."""
        async with open_session(self._database_url) as session, UnitOfWork(session):
            admin_id = await DocumentRepository(session).admin_id()
        return admin_id

    async def _ready_checksum(self, slug: str) -> str | None:
        """SHA-256 da versão ativa do documento, só se ela estiver `ready`."""
        async with open_session(self._database_url) as session, UnitOfWork(session):
            checksum = await DocumentRepository(session).ready_checksum(slug)
        return checksum

    @asynccontextmanager
    async def _locked(self) -> AsyncIterator[None]:
        """Segura o `pg_advisory_lock` da semente durante o bloco.

        Abre um engine sem pool e uma conexão só para o lock, porque um lock de sessão é
        da conexão que o pegou. Solta o lock só se ele foi pego, e fecha a conexão e o
        engine mesmo quando a semente falha.
        """
        engine = make_engine(self._database_url)
        connection = await engine.connect()
        lock = SeedLock(connection)
        acquired = False
        try:
            # Espera aqui enquanto outra semente segura o lock.
            await lock.acquire()
            acquired = True
            yield
        finally:
            if acquired:
                await lock.release()
            await connection.close()
            await engine.dispose()


def _markdown_files(directory: Path) -> list[Path]:
    """Os `.md` do corpus em ordem estável. O `README.md` documenta a pasta, não é conteúdo."""
    return sorted(path for path in directory.glob("*.md") if path.name != "README.md")
