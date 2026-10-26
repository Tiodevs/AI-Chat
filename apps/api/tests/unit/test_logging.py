import json

import pytest
import structlog

from app.core.logging import configure_logging, redact_sensitive


def test_processor_drops_denied_keys_and_masks_email_and_phone() -> None:
    event = redact_sensitive(
        None,
        "info",
        {
            "event": "contact",
            "password": "segredo",
            "email": "ana@example.com",
            "phone": "(555) 014-2600",
            "text": "não guardar",
            "content": "não guardar",
            "body": "não guardar",
            "authorization": "Bearer token",
            "cookie": "atrium_session=abc",
            "ip": "203.0.113.10",
            "message": "Ligue (555) 014-2600 ou ana@example.com",
            "request_id": "01J00000000000000000000000",
            "nested": {"email": "ana@example.com", "name": "Ana"},
            "phones": ["+55 11 98888-7777"],
            "timestamp": "2026-10-25T23:04:00.000000Z",
        },
    )

    for key in (
        "password",
        "email",
        "phone",
        "text",
        "content",
        "body",
        "authorization",
        "cookie",
        "ip",
    ):
        assert key not in event

    rendered = json.dumps(event)
    assert "segredo" not in rendered
    assert "ana@example.com" not in rendered
    assert "(555) 014-2600" not in rendered
    assert "203.0.113.10" not in rendered
    assert "Bearer token" not in rendered
    assert "[redacted-email]" in event["message"]
    assert "[redacted-phone]" in event["message"]
    assert event["request_id"] == "01J00000000000000000000000"
    assert event["nested"] == {"name": "Ana"}
    assert event["phones"] == ["[redacted-phone]"]
    assert event["timestamp"] == "2026-10-25T23:04:00.000000Z"


def test_configured_logger_redacts_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    structlog.get_logger("atrium").info(
        "note",
        detail="ana@example.com",
        password="segredo",
    )
    output = capsys.readouterr().out
    assert "ana@example.com" not in output
    assert "segredo" not in output
    assert "[redacted-email]" in output
    line = json.loads(output.strip().splitlines()[-1])
    for field in (
        "timestamp",
        "level",
        "event",
        "request_id",
        "trace_id",
        "span_id",
        "route",
        "status_code",
        "duration_ms",
        "app_version",
    ):
        assert field in line
