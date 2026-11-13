"""Regras puras do canal WhatsApp, sem banco, sem rede e sem modelo. Seção 30 do SDD.

Cobre a Etapa 18.1: assinatura, verificação, leitura do webhook, comandos, formato da resposta,
status de entrega, novas tentativas e destino do envio (ADR-018).
"""

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.handoff import CloseReason
from app.domain.whatsapp import (
    AI_PREFIX,
    MAX_TEXT_CHARS,
    Command,
    InboundKind,
    MessageType,
    OutboundStatus,
    button_titles_fit,
    can_fallback_to_phone,
    clean_question,
    is_new_conversation,
    is_retryable,
    markdown_to_whatsapp,
    next_attempt_delay,
    normalize_command,
    parse_webhook,
    recipient_for,
    status_advances,
    to_whatsapp_text,
    verify_challenge,
    verify_signature,
    within_service_window,
)
from app.prompts.whatsapp import BUTTON_TITLES, CLOSE_TEXTS

SECRET = "app-secret"
PHONE_ID = "1234567890"
TS = "1794495600"  # 2026-11-12T15:00:00Z


def _sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _payload(value: dict[str, object], phone_id: str = PHONE_ID) -> dict[str, object]:
    value = {"messaging_product": "whatsapp", "metadata": {"phone_number_id": phone_id}, **value}
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "waba", "changes": [{"field": "messages", "value": value}]}],
    }


def test_signature_is_checked_over_the_exact_bytes() -> None:
    # Etapa 18.1, CA-1: outro corpo, outro segredo ou cabeçalho ausente são recusados.
    body = json.dumps({"a": 1}).encode()
    assert verify_signature(body, _sign(body), SECRET)
    assert not verify_signature(body, _sign(body, "other"), SECRET)
    assert not verify_signature(body, None, SECRET)
    assert not verify_signature(body, _sign(body), "")
    reformatted = json.dumps({"a": 1}, indent=2).encode()
    assert not verify_signature(reformatted, _sign(body), SECRET)


def test_challenge_needs_subscribe_and_the_same_token() -> None:
    assert verify_challenge(mode="subscribe", token="t", challenge="42", verify_token="t") == "42"
    assert verify_challenge(mode="subscribe", token="x", challenge="42", verify_token="t") is None
    assert verify_challenge(mode="other", token="t", challenge="42", verify_token="t") is None
    assert verify_challenge(mode="subscribe", token="t", challenge="42", verify_token="") is None


def test_text_message_uses_the_bsuid_and_keeps_the_phone_as_secondary() -> None:
    # Etapa 18.1, CA-3 (NFR-23, D-12): o BSUID é a identidade; o telefone vem à parte.
    payload = _payload(
        {
            "contacts": [{"wa_id": "5511999990000", "user_id": "BR.123abc"}],
            "messages": [
                {
                    "from": "5511999990000",
                    "from_user_id": "BR.123abc",
                    "id": "wamid.1",
                    "timestamp": TS,
                    "type": "text",
                    "text": {"body": "Qual o horário de visita?"},
                }
            ],
        }
    )
    [event] = parse_webhook(payload, PHONE_ID)
    assert event.kind is InboundKind.MESSAGE
    assert event.identity == "BR.123abc"
    assert event.phone == "5511999990000"
    assert event.message_type is MessageType.TEXT
    assert event.body == "Qual o horário de visita?"
    assert event.event_key == "wamid.1"
    assert event.wa_timestamp == datetime(2026, 11, 12, 15, 0, tzinfo=UTC)


def test_message_without_phone_still_has_an_identity() -> None:
    payload = _payload(
        {
            "messages": [
                {
                    "from_user_id": "BR.999",
                    "id": "wamid.2",
                    "timestamp": TS,
                    "type": "text",
                    "text": {"body": "oi"},
                }
            ]
        }
    )
    [event] = parse_webhook(payload, PHONE_ID)
    assert event.identity == "BR.999" and event.phone is None


def test_without_bsuid_the_phone_becomes_the_reserve_identity() -> None:
    payload = _payload(
        {
            "messages": [
                {
                    "from": "5511",
                    "id": "wamid.3",
                    "timestamp": TS,
                    "type": "text",
                    "text": {"body": "x"},
                }
            ]
        }
    )
    [event] = parse_webhook(payload, PHONE_ID)
    assert event.identity == "phone:5511"


def test_buttons_media_status_and_system_are_typed() -> None:
    payload = _payload(
        {
            "messages": [
                {
                    "from_user_id": "BR.1",
                    "id": "wamid.b",
                    "timestamp": TS,
                    "type": "interactive",
                    "interactive": {
                        "type": "button_reply",
                        "button_reply": {"id": "handoff_offer_yes", "title": "Falar"},
                    },
                },
                {"from_user_id": "BR.1", "id": "wamid.m", "timestamp": TS, "type": "image"},
                {
                    "from_user_id": "BR.1",
                    "id": "wamid.s",
                    "timestamp": TS,
                    "type": "system",
                    "system": {
                        "type": "user_changed_user_id",
                        "user_id": "BR.2",
                        "previous_user_id": "BR.1",
                    },
                },
            ],
            "statuses": [
                {
                    "id": "wamid.out",
                    "status": "failed",
                    "timestamp": TS,
                    "errors": [{"code": 131047}],
                }
            ],
        }
    )
    button, media, system, status = parse_webhook(payload, PHONE_ID)
    assert button.message_type is MessageType.BUTTON and button.button_id == "handoff_offer_yes"
    assert media.message_type is MessageType.MEDIA and media.body is None
    assert system.kind is InboundKind.SYSTEM
    assert (system.previous_identity, system.identity) == ("BR.1", "BR.2")
    assert status.kind is InboundKind.STATUS
    assert status.status is OutboundStatus.FAILED and status.error_code == 131047
    assert status.event_key == "wamid.out:failed"


def test_other_numbers_and_other_fields_are_ignored() -> None:
    message = {
        "from_user_id": "BR.1",
        "id": "w",
        "timestamp": TS,
        "type": "text",
        "text": {"body": "x"},
    }
    assert parse_webhook(_payload({"messages": [message]}, phone_id="999"), PHONE_ID) == []
    assert parse_webhook({"object": "page"}, PHONE_ID) == []
    broken = _payload({"messages": [{"id": "w", "type": "text"}]})
    assert parse_webhook(broken, PHONE_ID) == []


def test_commands_ignore_case_spaces_and_punctuation() -> None:
    assert normalize_command("  Apagar   DADOS ") is Command.DELETE_DATA
    assert normalize_command("encerrar.") is Command.END
    assert normalize_command("quero encerrar") is None


def test_markdown_becomes_whatsapp_formatting() -> None:
    converted = markdown_to_whatsapp(
        "## Visitas\n**Horário**: das 10h às 20h, *todos* os dias.\n"
        "| Ala | Horário |\n|---|---|\n| UTI | 15h |\n[Mapa](https://example.com)"
    )
    assert "*Visitas*" in converted
    assert "*Horário*" in converted
    assert "_todos_" in converted
    assert "UTI — 15h" in converted
    assert "---" not in converted
    assert "Mapa (https://example.com)" in converted


def test_reply_has_the_prefix_and_the_sources_without_repeating() -> None:
    # Etapa 18.1, CA-2 (FR-27).
    reply = to_whatsapp_text(
        "Visitas das 10h às 20h.", ["Visitas", "Visitas", "Mapa"], prefix=AI_PREFIX
    )
    assert reply.startswith(AI_PREFIX)
    assert reply.endswith("Fontes:\n- Visitas\n- Mapa")


def test_long_reply_is_cut_at_a_sentence_and_keeps_the_sources() -> None:
    answer = "Frase curta. " * 600
    reply = to_whatsapp_text(answer, ["Documento"], prefix=AI_PREFIX)
    assert len(reply) <= MAX_TEXT_CHARS
    assert reply.endswith("Fontes:\n- Documento")
    body = reply.split("\n\nFontes:")[0]
    assert body.endswith(".")


def test_status_only_moves_forward() -> None:
    assert status_advances("sent", OutboundStatus.DELIVERED)
    assert status_advances("delivered", OutboundStatus.READ)
    assert not status_advances("read", OutboundStatus.DELIVERED)
    assert not status_advances("failed", OutboundStatus.READ)
    assert status_advances("sent", OutboundStatus.FAILED)
    assert not status_advances("read", OutboundStatus.FAILED)


@pytest.mark.parametrize(
    ("http_status", "code", "expected"),
    [
        (429, None, True),
        (503, None, True),
        (None, None, True),
        (400, 131047, False),
        (401, 190, False),
        (400, 130429, True),
        (400, 100, False),
    ],
)
def test_retry_rules(http_status: int | None, code: int | None, expected: bool) -> None:
    assert is_retryable(http_status=http_status, error_code=code) is expected


def test_retry_delay_grows_and_stops_at_twenty_minutes() -> None:
    assert next_attempt_delay(1) == timedelta(seconds=30)
    assert next_attempt_delay(2) == timedelta(minutes=1)
    assert next_attempt_delay(10) == timedelta(minutes=20)


def test_recipient_prefers_the_bsuid_and_falls_back_to_the_phone() -> None:
    # ADR-018 e D-12: o telefone só na segunda tentativa, depois de um parâmetro recusado.
    assert recipient_for("BR.1", "5511").bsuid == "BR.1"
    assert recipient_for("BR.1", "5511", use_phone=True).phone == "5511"
    assert recipient_for("phone:5511", None).phone == "5511"
    assert can_fallback_to_phone("BR.1", "5511", 100)
    assert not can_fallback_to_phone("BR.1", None, 100)
    assert not can_fallback_to_phone("BR.1", "5511", 131047)


def test_window_and_new_conversation_use_24_hours() -> None:
    now = datetime(2026, 11, 12, 15, 0, tzinfo=UTC)
    assert within_service_window(now - timedelta(hours=23), now)
    assert not within_service_window(now - timedelta(hours=25), now)
    assert not within_service_window(None, now)
    assert is_new_conversation(None, now)
    assert is_new_conversation(now - timedelta(hours=25), now)
    assert not is_new_conversation(now - timedelta(hours=2), now)


def test_question_is_cleaned_and_limited() -> None:
    assert clean_question("  \x00 ") is None
    assert clean_question("oi\x07 tudo bem") == "oi tudo bem"
    assert len(clean_question("a" * 2000) or "") == 1000


def test_button_titles_fit_the_meta_limit() -> None:
    assert all(button_titles_fit([title]) for title in BUTTON_TITLES.values())
    assert not button_titles_fit(["x" * 21])
    assert not button_titles_fit(["a", "b", "c", "d"])


def test_every_close_reason_has_a_whatsapp_text() -> None:
    assert set(CLOSE_TEXTS) == {reason.value for reason in CloseReason}
