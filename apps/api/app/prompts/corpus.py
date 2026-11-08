"""Mensagens do corpus para quem opera a implantação.

Camada de prompts. `IngestionService` grava os erros de ingestão em `document_versions.error`,
que a tela de documentos do admin mostra; `SeedService` e os scripts `seed` e `search` usam as
outras mensagens, que saem no terminal ou no log do pré-deploy. Seções 7.3 e 9 do SDD.
"""

# Erros gravados na versão que falhou (seção 7.3).
EMPTY_DOCUMENT = "O documento não tem texto."
EXTRACT_FAILED = "Não foi possível ler o texto do arquivo."
EMBED_FAILED = "Não foi possível embedar o documento."
# Versão presa em `processing` por mais de 15 minutos, marcada como `failed` na inicialização.
PROCESSING_TIMED_OUT = "A ingestão passou de 15 minutos."
# Resumo que o script de semente imprime, montado por `seed_message`.
NONE_EMBEDDED = "Nenhum documento foi embedado."
EMBEDDED_COUNT = "Documentos embedados:"
# A semente grava o admin como autor dos documentos, então precisa dele.
NO_ADMIN = "Não há admin. Rode bootstrap_admin antes da semente."
# A semente e a busca chamam o modelo de embedding.
MISSING_EMBEDDING_KEY = "Defina GEMINI_API_KEY ou use APP_AI_ADAPTER=fake."
# Primeiro deploy, antes de a chave existir: a semente adia em vez de embedar com um falso.
SEED_POSTPONED = (
    "Semente adiada: GEMINI_API_KEY não está definida. "
    "Defina a chave e faça um novo deploy para semear o corpus."
)
# Saída do script `search` sem resultado e o nome de um chunk sem título. `app/prompts/qa.py`
# tem um `NO_SECTION` igual, que vai ao modelo.
NO_SEARCH_RESULTS = "Nenhum chunk acima do piso de similaridade."
NO_SECTION = "sem seção"
CORPUS_MISSING = "A pasta do corpus não existe."


def seed_message(embedded: int) -> str:
    """Resumo da semente: quantos documentos foram embedados, ou o aviso de nenhum."""
    if embedded == 0:
        return NONE_EMBEDDED
    return f"{EMBEDDED_COUNT} {embedded}"
