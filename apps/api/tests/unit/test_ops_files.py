"""Painéis, alertas e coleta versionados em ops/. Seção 18.3 do SDD."""

import json
import re
from pathlib import Path

import pytest

from app.core import metrics
from app.core.metrics import REGISTRY, DatabaseSnapshot, render_metrics

OPS = Path(__file__).resolve().parents[4] / "ops"
DASHBOARDS = sorted((OPS / "grafana" / "dashboards").glob("*.json"))
ALERTING = OPS / "grafana" / "provisioning" / "alerting" / "alerting.json"

DASHBOARD_TITLES = {
    "Atrium, saúde da API",
    "Atrium, qualidade de IA",
    "Atrium, cadastro",
    "Atrium, privacidade",
}
ALERT_TITLES = {
    "Erros da API",
    "Latência de IA",
    "Qualidade em queda",
    "Orçamento",
    "Circuito aberto",
    "Ingestão",
    "Pedido de titular atrasado",
    "Retenção parada",
}


@pytest.fixture(autouse=True)
def loaded_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        metrics,
        "SNAPSHOT",
        DatabaseSnapshot(
            dsr_open=2,
            dsr_overdue=1,
            retention_deleted={"auth_sessions": 4},
            retention_last_run_seconds=1_700_000_000.0,
            loaded=True,
        ),
    )


def _series_names() -> set[str]:
    names = {"up"}
    for family in REGISTRY.collect():
        if family.type == "counter":
            names.add(f"{family.name}_total")
        elif family.type == "histogram":
            names.update(f"{family.name}{suffix}" for suffix in ("_bucket", "_count", "_sum"))
        else:
            names.add(family.name)
    return names


def _expressions() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in DASHBOARDS:
        for panel in json.loads(path.read_text(encoding="utf-8"))["panels"]:
            found.extend((f"{path.name}:{panel['title']}", t["expr"]) for t in panel["targets"])
    alerting = json.loads(ALERTING.read_text(encoding="utf-8"))
    for rule in alerting["groups"][0]["rules"]:
        found.append((rule["title"], rule["data"][0]["model"]["expr"]))
    return found


def test_four_dashboards_with_unique_uids_and_panels() -> None:
    loaded = [json.loads(path.read_text(encoding="utf-8")) for path in DASHBOARDS]
    assert {item["title"] for item in loaded} == DASHBOARD_TITLES
    assert len({item["uid"] for item in loaded}) == 4
    for item in loaded:
        ids = [panel["id"] for panel in item["panels"]]
        assert ids and len(ids) == len(set(ids))
        assert all(panel["datasource"]["uid"] == "prometheus" for panel in item["panels"])


def test_eight_alerts_match_section_18_3() -> None:
    alerting = json.loads(ALERTING.read_text(encoding="utf-8"))
    rules = alerting["groups"][0]["rules"]
    assert {rule["title"] for rule in rules} == ALERT_TITLES
    assert len({rule["uid"] for rule in rules}) == 8
    for rule in rules:
        assert rule["condition"] == "C"
        assert [step["refId"] for step in rule["data"]] == ["A", "B", "C"]
        assert rule["data"][0]["datasourceUid"] == "prometheus"


def test_alerts_notify_a_discord_webhook_read_from_the_environment() -> None:
    text = ALERTING.read_text(encoding="utf-8")
    alerting = json.loads(text)
    (contact,) = alerting["contactPoints"]
    (receiver,) = contact["receivers"]
    assert receiver["type"] == "discord"
    assert receiver["settings"]["url"] == "${DISCORD_WEBHOOK_URL}"
    assert "discord.com/api/webhooks" not in text
    assert alerting["policies"][0]["receiver"] == contact["name"]


def test_the_old_email_integration_is_deleted_from_the_grafana_volume() -> None:
    """O Grafana guarda no volume a integração que sai do arquivo. `deleteContactPoints` apaga."""
    alerting = json.loads(ALERTING.read_text(encoding="utf-8"))
    deleted = {(entry["orgId"], entry["uid"]) for entry in alerting["deleteContactPoints"]}
    assert deleted == {(1, "atrium-operacao-email")}


def test_alert_thresholds_follow_the_sdd() -> None:
    alerting = json.loads(ALERTING.read_text(encoding="utf-8"))
    by_title = {rule["title"]: rule for rule in alerting["groups"][0]["rules"]}

    def limit(title: str) -> float:
        condition = by_title[title]["data"][2]["model"]["conditions"][0]["evaluator"]
        return float(condition["params"][0])

    assert limit("Erros da API") == 0.02
    assert by_title["Erros da API"]["for"] == "10m"
    assert limit("Latência de IA") == 3
    assert by_title["Latência de IA"]["for"] == "30m"
    assert limit("Qualidade em queda") == 0.25
    assert limit("Orçamento") == 0.8
    assert by_title["Circuito aberto"]["for"] == "5m"
    assert limit("Retenção parada") == 26 * 3600
    assert by_title["Retenção parada"]["noDataState"] == "Alerting"


@pytest.mark.parametrize(("where", "expr"), _expressions())
def test_every_query_uses_a_series_the_api_exposes(where: str, expr: str) -> None:
    used = set(re.findall(r"\batrium_[a-z0-9_]+", expr))
    assert used or expr.startswith("up{"), where
    assert used <= _series_names(), f"{where}: {sorted(used - _series_names())}"


def test_database_series_are_rendered() -> None:
    body = render_metrics().decode()
    assert 'atrium_dsr_open{overdue="true"} 1.0' in body
    assert 'atrium_retention_deleted_total{rule="auth_sessions"} 4.0' in body
    assert "atrium_retention_last_run_timestamp_seconds 1.7e+09" in body


def test_database_series_are_absent_before_the_first_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(metrics, "SNAPSHOT", DatabaseSnapshot())
    assert "atrium_dsr_open" not in render_metrics().decode()


def test_prometheus_scrapes_every_thirty_seconds() -> None:
    config = (OPS / "prometheus" / "prometheus.yml").read_text(encoding="utf-8")
    assert "scrape_interval: 30s" in config
    assert "/metrics" in config
    assert "${METRICS_TOKEN}" in config
