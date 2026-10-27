"""Prefixos enviados ao modelo de embedding. Seção 8.3 do SDD."""


def document_embedding_text(title: str, heading: str | None, content: str) -> str:
    if heading:
        return f"title: {title} | text: {heading}\n{content}"
    return f"title: {title} | text: {content}"


def query_embedding_text(question: str) -> str:
    return f"task: question answering | query: {question}"
