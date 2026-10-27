"""Semente idempotente do corpus. Seções 6.4 e 7.3 do SDD."""

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
    embedded: int
    unchanged: int


class SeedService:
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
        if not self._corpus_dir.is_dir():
            raise ValidationFailed(CORPUS_MISSING)
        async with self._locked():
            admin_id = await self._admin_id()
            if admin_id is None:
                raise ValidationFailed(NO_ADMIN)
            embedded = 0
            unchanged = 0
            failed = 0
            for path in _markdown_files(self._corpus_dir):
                data = path.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                if await self._ready_checksum(path.stem) == digest:
                    unchanged += 1
                    structlog.get_logger("atrium").info("seed.unchanged", slug=path.stem)
                    continue
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
        async with open_session(self._database_url) as session, UnitOfWork(session):
            admin_id = await DocumentRepository(session).admin_id()
        return admin_id

    async def _ready_checksum(self, slug: str) -> str | None:
        async with open_session(self._database_url) as session, UnitOfWork(session):
            checksum = await DocumentRepository(session).ready_checksum(slug)
        return checksum

    @asynccontextmanager
    async def _locked(self) -> AsyncIterator[None]:
        engine = make_engine(self._database_url)
        connection = await engine.connect()
        lock = SeedLock(connection)
        acquired = False
        try:
            await lock.acquire()
            acquired = True
            yield
        finally:
            if acquired:
                await lock.release()
            await connection.close()
            await engine.dispose()


def _markdown_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*.md") if path.name != "README.md")
