import re
from pathlib import Path

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[4]

EXPECTED_DIRECTORIES = (
    "apps/api/app/core",
    "apps/api/app/controllers",
    "apps/api/app/schemas",
    "apps/api/app/domain",
    "apps/api/app/services",
    "apps/api/app/workflows",
    "apps/api/app/prompts",
    "apps/api/app/ports",
    "apps/api/app/adapters",
    "apps/api/app/models",
    "apps/api/app/repositories",
    "apps/api/app/db",
    "apps/api/app/scripts",
    "apps/api/tests/unit",
    "apps/api/tests/integration",
    "apps/api/tests/architecture",
    "apps/api/tests/contract",
    "apps/api/alembic",
    "apps/web/src/app",
    "apps/web/src/features/ask",
    "apps/web/src/features/registration",
    "apps/web/src/features/auth",
    "apps/web/src/features/account",
    "apps/web/src/features/privacy",
    "apps/web/src/features/admin",
    "apps/web/src/components/ui",
    "apps/web/src/components/patterns",
    "apps/web/src/motion",
    "apps/web/src/lib/api",
    "apps/web/src/i18n",
    "apps/web/src/styles",
    "apps/web/e2e",
    "apps/web/.storybook",
    "content/corpus",
    "evals",
    "docs/privacy",
    "docs/adr",
    "ops/grafana",
    "ops/prometheus",
    ".cursor/rules",
    ".github/workflows",
)

SECTION_17_ENV_NAMES = {name.upper() for name in Settings.model_fields}
EMPTY_SECRET_KEYS = {
    "GEMINI_API_KEY",
    "ADMIN_EMAIL",
    "ADMIN_PASSWORD",
    "METRICS_TOKEN",
    "RATE_LIMIT_HMAC_KEY",
    "PSEUDONYM_KEY",
    "PRIVACY_CONTACT_EMAIL",
    "LANGSMITH_API_KEY",
    "DATABASE_URL",
    "LANGSMITH_ENDPOINT",
}
ADR_HEADINGS = ("## Contexto", "## Decisão", "## Consequências", "## Alternativas")


def test_repository_directories_match_section_6_3() -> None:
    missing = [path for path in EXPECTED_DIRECTORIES if not (ROOT / path).is_dir()]
    assert missing == []


def test_twelve_adrs_have_the_four_sections() -> None:
    adrs = sorted((ROOT / "docs/adr").glob("[0-9][0-9][0-9]-*.md"))
    assert len(adrs) == 12
    for adr in adrs:
        text = adr.read_text(encoding="utf-8")
        for heading in ADR_HEADINGS:
            assert heading in text, adr.name


def test_cursor_rules_cite_their_sdd_sections() -> None:
    rules = ROOT / ".cursor/rules"
    assert "6.2" in (rules / "camadas.mdc").read_text(encoding="utf-8")
    assert "14.8" in (rules / "design-system.mdc").read_text(encoding="utf-8")
    assert "16.5" in (rules / "gsap.mdc").read_text(encoding="utf-8")


def test_env_example_lists_section_17_without_secrets() -> None:
    example = (ROOT / "apps/api/.env.example").read_text(encoding="utf-8")
    assignments = dict(re.findall(r"^([A-Z0-9_]+)=(.*)$", example, flags=re.MULTILINE))
    assert set(assignments) == SECTION_17_ENV_NAMES
    for key in EMPTY_SECRET_KEYS:
        assert assignments[key] == ""
