"""Desfechos da pergunta. Seções 7.1 e 10.1 do SDD."""

import math
from enum import StrEnum

MIN_PUBLIC_CONFIDENCE = 0.6


class Outcome(StrEnum):
    ANSWERED = "answered"
    ABSTAINED = "abstained"
    REFUSED = "refused"
    OFF_TOPIC = "off_topic"
    GROUNDING_FAILED = "grounding_failed"
    CANCELLED = "cancelled"
    DEGRADED = "degraded"
    ERROR = "error"


def gate_outcome(intent: str, confidence: float) -> Outcome | None:
    """Recusa orientação médica. Fora de tema não chama o gerador.

    A recuperação só continua quando a intenção é informação pública e a
    confiança é pelo menos 0,6. Orientação médica vence a confiança baixa.
    """
    if intent == "medical_advice":
        return Outcome.REFUSED
    if (
        intent != "public_info"
        or not math.isfinite(confidence)
        or confidence < MIN_PUBLIC_CONFIDENCE
        or confidence > 1
    ):
        return Outcome.OFF_TOPIC
    return None
