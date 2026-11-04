"""Cópias da gestão de documentos do admin. Seções 7.3, 10.4 e 12 do SDD."""

from app.domain.documents import UploadIssue

UPLOAD_INVALID = "Não foi possível enviar o arquivo. Confira o arquivo e o título."
DOCUMENT_NOT_FOUND = "Documento não encontrado."
DOCUMENT_ARCHIVED = "O documento está arquivado."
STILL_PROCESSING = "Uma versão deste documento ainda está em processamento. Aguarde o fim."
NOTHING_TO_RETRY = "A última versão deste documento não falhou."
UPLOADS_LIMITED = "Você enviou muitos arquivos nesta hora. Tente de novo mais tarde."

_ISSUE_MESSAGES = {
    UploadIssue.EMPTY: "O arquivo está vazio.",
    UploadIssue.TOO_LARGE: "O arquivo passa de 10 MB.",
    UploadIssue.UNSUPPORTED_TYPE: "Envie um arquivo Markdown (.md), texto (.txt) ou PDF (.pdf).",
    UploadIssue.NOT_UTF8: "O arquivo de texto precisa estar em UTF-8.",
    UploadIssue.NOT_PDF: "O arquivo não é um PDF válido.",
    UploadIssue.TITLE_TOO_LONG: "Use um título de até 200 caracteres.",
}


def issue_message(issue: UploadIssue) -> str:
    return _ISSUE_MESSAGES[issue]
