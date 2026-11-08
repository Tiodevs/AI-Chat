"""Prefixos enviados ao modelo de embedding. Seção 8.3 do SDD.

Camada de domínio. `IngestionService` usa `document_embedding_text` em cada chunk;
`QaWorkflow` e `RetrievalService.search` usam `query_embedding_text` na pergunta. Os prefixos
`title:`, `text:` e `task: question answering | query:` são instruções do
`gemini-embedding-2` e ficam em inglês; o título e o conteúdo ficam em português. Os prefixos
entram só na chamada de embedding: não são gravados no chunk nem vão ao gerador.
"""


def document_embedding_text(title: str, heading: str | None, content: str) -> str:
    """Texto de um chunk: título do documento, título da seção, quebra de linha e conteúdo.

    Sem título de seção, o texto é só `title: {título} | text: {conteúdo}`.
    """
    if heading:
        return f"title: {title} | text: {heading}\n{content}"
    return f"title: {title} | text: {content}"


def query_embedding_text(question: str) -> str:
    """Texto de uma pergunta. No pipeline, é a pergunta autônoma do passo 1 da seção 7.1."""
    return f"task: question answering | query: {question}"
