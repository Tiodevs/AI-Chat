"""Busca vetorial e por texto completo. Seções 8.2 e 8.4 do SDD.

Camada de repositório (seção 6.2 do SDD). Lê `chunks`, `document_versions` e `documents`. Quem
usa é o `RetrievalService`, que o `QaWorkflow` chama pela porta `HybridSearch` a cada pergunta
e o script `search` chama no terminal. A busca híbrida da seção 8.4, passo a passo:

1. `nearest` pega os 20 chunks pesquisáveis mais próximos do vetor da pergunta.
2. O serviço descarta os que ficam abaixo de `RETRIEVAL_MIN_SIMILARITY`.
3. `keyword` pega até 20 chunks pesquisáveis que casam com as palavras da pergunta, já com o
   mesmo piso de similaridade no SQL.
4. O domínio funde as duas listas com reciprocal rank fusion (`app.domain.ranking`).
5. O serviço passa os 6 primeiros ao gerador.

`RetrievedChunk` mora no domínio e é reexportado aqui, para o serviço importar o resultado de
quem o produz.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.retrieval import RetrievedChunk
from app.repositories.documents import vector_literal

__all__ = ["RetrievalRepository", "RetrievedChunk"]

# O predicado de chunk pesquisável da seção 8.2: documento ativo, versão igual à
# `active_version` do documento e chunk ativo. Arquivar um documento ou trocar a versão ativa
# tira os chunks da busca sem apagá-los. O `chunk.active` também casa com o `WHERE active` dos
# índices parciais, o que deixa o planejador usá-los.
_SEARCHABLE = """
document.status = 'active'
AND document.active_version = chunk.document_version_id
AND chunk.active
"""


class RetrievalRepository:
    """As duas metades da busca híbrida: por vetor e por palavra."""

    def __init__(self, session: AsyncSession) -> None:
        """Usa a sessão aberta pelo serviço, sem abrir transação própria."""
        self._session = session

    async def nearest(self, embedding: list[float], *, limit: int) -> list[RetrievedChunk]:
        """Os `limit` chunks pesquisáveis mais próximos do vetor, do mais perto ao mais longe.

        `<=>` é o operador de distância de cosseno do pgvector: 0 para vetores na mesma
        direção, até 2 para direções opostas. A similaridade é `1 - distância`, de 1 a -1
        (seção 8.3). `CAST(:embedding AS vector)` converte o texto de `vector_literal` no tipo
        do pgvector. `ORDER BY embedding <=> ... LIMIT` é a forma que o índice HNSW parcial
        `chunks_embedding_idx` serve; o HNSW é aproximado e troca um pouco de precisão por
        velocidade.

        Aqui não há piso: cada chunk volta com a similaridade, e quem descarta os de baixo é o
        serviço. A métrica `atrium_qa_top_similarity` só vê o que passou do piso; a Etapa 13.5
        passa a medir a melhor similaridade antes dele.
        """
        rows = await self._session.execute(
            text(
                "SELECT chunk.id AS chunk_id, document.slug AS document_slug, "
                "document.title AS document_title, chunk.heading AS heading, "
                "chunk.content AS content, "
                "1 - (chunk.embedding <=> CAST(:embedding AS vector)) AS similarity "
                "FROM chunks AS chunk "
                "JOIN document_versions AS version ON version.id = chunk.document_version_id "
                "JOIN documents AS document ON document.id = version.document_id "
                f"WHERE {_SEARCHABLE} "
                "ORDER BY chunk.embedding <=> CAST(:embedding AS vector) "
                "LIMIT :limit"
            ),
            {"embedding": vector_literal(embedding), "limit": limit},
        )
        return [_chunk(dict(row)) for row in rows.mappings()]

    async def keyword(
        self,
        question: str,
        embedding: list[float],
        *,
        minimum: float,
        limit: int,
    ) -> list[RetrievedChunk]:
        """Até `limit` chunks pesquisáveis que casam com as palavras da pergunta.

        `websearch_to_tsquery('portuguese', :question)` transforma o texto livre numa consulta
        de texto completo com o mesmo dicionário português do `tsv`: tira palavras vazias e
        reduz as palavras ao radical. Ela aceita a sintaxe de busca na web (aspas, `or`, `-`) e
        nunca levanta erro de sintaxe, então recebe o texto do visitante como veio. `@@` é o
        operador de casamento entre `tsvector` e `tsquery`, servido pelo índice GIN parcial
        `chunks_tsv_idx`. `ts_rank` ordena pela frequência dos termos no chunk.

        O piso de similaridade entra no próprio SQL: a lista por palavra não pode admitir um
        chunk que falhou no piso (seção 8.4). Por isso a consulta também recebe o vetor. O
        `QaWorkflow` manda a pergunta reescrita (`standalone_question`).
        """
        rows = await self._session.execute(
            text(
                "SELECT chunk.id AS chunk_id, document.slug AS document_slug, "
                "document.title AS document_title, chunk.heading AS heading, "
                "chunk.content AS content, "
                "1 - (chunk.embedding <=> CAST(:embedding AS vector)) AS similarity "
                "FROM chunks AS chunk "
                "JOIN document_versions AS version ON version.id = chunk.document_version_id "
                "JOIN documents AS document ON document.id = version.document_id "
                f"WHERE {_SEARCHABLE} "
                "AND chunk.tsv @@ websearch_to_tsquery('portuguese', :question) "
                "AND (1 - (chunk.embedding <=> CAST(:embedding AS vector))) >= :minimum "
                "ORDER BY ts_rank("
                "chunk.tsv, websearch_to_tsquery('portuguese', :question)"
                ") DESC "
                "LIMIT :limit"
            ),
            {
                "embedding": vector_literal(embedding),
                "question": question,
                "minimum": minimum,
                "limit": limit,
            },
        )
        return [_chunk(dict(row)) for row in rows.mappings()]


def _chunk(row: dict[str, Any]) -> RetrievedChunk:
    """Converte uma linha das duas consultas em `RetrievedChunk`."""
    heading = row["heading"]
    return RetrievedChunk(
        chunk_id=_uuid(row["chunk_id"]),
        document_slug=str(row["document_slug"]),
        document_title=str(row["document_title"]),
        heading=None if heading is None else str(heading),
        content=str(row["content"]),
        similarity=float(row["similarity"]),
    )


def _uuid(value: object) -> UUID:
    """Aceita o UUID que o driver devolve ou o texto dele."""
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
