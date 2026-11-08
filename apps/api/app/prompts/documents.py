"""Cópias da gestão de documentos do admin. Seções 7.3, 10.4 e 12 do SDD.

Camada de prompts. `DocumentAdminService` (`app/services/documents.py`) usa estas mensagens
nos erros das rotas de documentos; `issue_message` traduz cada `UploadIssue` de
`app/domain/documents.py` no texto que a tela mostra em `field_errors.file` ou
`field_errors.title`.
"""

from app.domain.documents import UploadIssue

# `message` do 422 do upload; o detalhe de cada campo vem de `issue_message`.
UPLOAD_INVALID = "Não foi possível enviar o arquivo. Confira o arquivo e o título."
# 404 de um documento inexistente.
DOCUMENT_NOT_FOUND = "Documento não encontrado."
# 409 de substituir ou tentar de novo um documento arquivado.
DOCUMENT_ARCHIVED = "O documento está arquivado."
# 409 enquanto uma versão está em `processing` há menos de 15 minutos (seção 7.3).
STILL_PROCESSING = "Uma versão deste documento ainda está em processamento. Aguarde o fim."
# 409 de tentar de novo quando a última versão não falhou.
NOTHING_TO_RETRY = "A última versão deste documento não falhou."
# 429 do 31º envio do admin na hora (seção 10.4).
UPLOADS_LIMITED = "Você enviou muitos arquivos nesta hora. Tente de novo mais tarde."

# Um texto por `UploadIssue`. Os números repetem os limites de `app/domain/documents.py`:
# mudar um lado pede mudar o outro.
_ISSUE_MESSAGES = {
    UploadIssue.EMPTY: "O arquivo está vazio.",
    UploadIssue.TOO_LARGE: "O arquivo passa de 10 MB.",
    UploadIssue.UNSUPPORTED_TYPE: "Envie um arquivo Markdown (.md), texto (.txt) ou PDF (.pdf).",
    UploadIssue.NOT_UTF8: "O arquivo de texto precisa estar em UTF-8.",
    UploadIssue.NOT_PDF: "O arquivo não é um PDF válido.",
    UploadIssue.TITLE_TOO_LONG: "Use um título de até 200 caracteres.",
}


def issue_message(issue: UploadIssue) -> str:
    """Texto do campo para um `UploadIssue`. Um motivo sem texto aqui levanta `KeyError`."""
    return _ISSUE_MESSAGES[issue]
