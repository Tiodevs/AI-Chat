"""Mensagens do corpus para quem opera a implantação."""

EMPTY_DOCUMENT = "O documento não tem texto."
EMBED_FAILED = "Não foi possível embedar o documento."
PROCESSING_TIMED_OUT = "A ingestão passou de 15 minutos."
NONE_EMBEDDED = "Nenhum documento foi embedado."
EMBEDDED_COUNT = "Documentos embedados:"
NO_ADMIN = "Não há admin. Rode bootstrap_admin antes da semente."
MISSING_EMBEDDING_KEY = "Defina GEMINI_API_KEY ou use APP_AI_ADAPTER=fake."
NO_SEARCH_RESULTS = "Nenhum chunk acima do piso de similaridade."
NO_SECTION = "sem seção"
CORPUS_MISSING = "A pasta do corpus não existe."


def seed_message(embedded: int) -> str:
    if embedded == 0:
        return NONE_EMBEDDED
    return f"{EMBEDDED_COUNT} {embedded}"
