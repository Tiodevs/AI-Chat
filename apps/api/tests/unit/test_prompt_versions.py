"""O hash trava o texto na versão. Seção 10.2 do SDD."""

import hashlib

from app.domain.outcomes import Outcome
from app.prompts.evals import versioned_eval_prompts
from app.prompts.qa import (
    ABSTENTION,
    MEDICAL_ADVICE,
    OFF_TOPIC,
    UNAVAILABLE,
    fixed_text,
    versioned_prompts,
)
from app.prompts.registration import versioned_registration_prompts

# Mudar o texto sem mudar PROMPT_VERSION quebra a igualdade abaixo.
_LOCKED_HASHES = {
    "qa-rewrite@2026-10-27.1": "d04cb4058b7319e772cf98a02bc9a63e3d1c7b95518fdb3b134871e65e70c5bf",
    "qa-generate@2026-10-27.1": "1a533c1e2534875ee07753b3b4c2cb759413d1af5334f0e9def67f75ae80bb33",
    "groundedness@2026-10-27.1": "be3d0615be6e9d8dcbd9cfaf39d9514ba2c4eb5a70c158fb680d4ebbe80fcb13",
    "registration-extract@2026-10-28.2": (
        "03cd33e663ce500186035ebba129850be9262c43c2eb67b496ef46f8875bbf85"
    ),
    "registration-phrase@2026-10-28.2": (
        "2cdce6a66414e1741a6b4dd94536d3b2c451bc8b57ecf07a0a57ca6a695a455a"
    ),
}


def test_prompt_hash_is_locked_to_its_version() -> None:
    found = {
        version: hashlib.sha256(text.encode()).hexdigest()
        for version, text in (
            *versioned_prompts(),
            *versioned_eval_prompts(),
            *versioned_registration_prompts(),
        )
    }
    assert found == _LOCKED_HASHES


def test_fixed_responses_match_section_10_1() -> None:
    assert MEDICAL_ADVICE == (
        "Não posso ajudar com sintomas, diagnóstico ou medicamento. Se for uma emergência, "
        "ligue para o número local de emergência. A entrada de emergência do Harborlight fica "
        "no lado oeste e funciona 24 horas. Para outras perguntas sobre o hospital, ligue "
        "(555) 014-2600."
    )
    assert OFF_TOPIC == (
        "Posso responder perguntas sobre como visitar e usar o Harborlight General Hospital."
    )
    assert ABSTENTION == (
        "Não encontrei isso nas informações publicadas do Harborlight. Você pode ligar para "
        "a mesa telefônica no (555) 014-2600."
    )
    assert UNAVAILABLE == (
        "O Atrium está temporariamente indisponível. Você pode ligar para a mesa telefônica "
        "no (555) 014-2600."
    )
    assert fixed_text(Outcome.ABSTAINED) == fixed_text(Outcome.GROUNDING_FAILED) == ABSTENTION
    assert fixed_text(Outcome.DEGRADED) == fixed_text(Outcome.ERROR) == UNAVAILABLE
    assert fixed_text(Outcome.REFUSED) == MEDICAL_ADVICE
    assert fixed_text(Outcome.OFF_TOPIC) == OFF_TOPIC
