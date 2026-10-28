"""Pseudônimo HMAC do titular. Seção 11.6 do SDD."""

import hashlib
import hmac
from uuid import UUID


def subject_pseudonym(subject_id: UUID, key: str) -> str:
    """Hex do HMAC. A chave vazia não produz um pseudônimo fraco."""
    if not key:
        raise ValueError("pseudonym key is empty")
    return hmac.new(
        key.encode("utf-8"),
        str(subject_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
