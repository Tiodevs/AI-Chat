"""Pseudônimo HMAC do titular. Seção 11.6 do SDD.

Camada de domínio. `ConversationService` põe o pseudônimo no metadado `subject` dos rastros
do LangSmith (seção 18.4), e `InsightsService` mostra 8 caracteres dele no inspetor de
qualidade (seção 12). A chave é `PSEUDONYM_KEY`.

HMAC é um hash com chave secreta: sem a chave, ninguém recalcula o pseudônimo a partir do id.
Quando a conta é excluída, o pseudônimo nos rastros perde o vínculo com a pessoa (seção 11.6).
"""

import hashlib
import hmac
from uuid import UUID


def subject_pseudonym(subject_id: UUID, key: str) -> str:
    """Hex do HMAC. A chave vazia não produz um pseudônimo fraco.

    O sujeito é o id do usuário ou, numa conversa de convidado, o da chave de convidado. O
    resultado é o HMAC-SHA256 do id em texto, em hexadecimal. Levanta `ValueError` com a chave
    vazia; o `ConversationService` confere a chave antes e, sem ela, deixa o `subject` vazio.
    """
    if not key:
        raise ValueError("pseudonym key is empty")
    return hmac.new(
        key.encode("utf-8"),
        str(subject_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
