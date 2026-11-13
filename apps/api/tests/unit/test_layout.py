"""As pastas, os ADRs, as regras, o `.env.example` e os documentos de privacidade do repositório.

Seções 6.3, 10.6, 11.11, 17, 20 e 24 do SDD. Lê só arquivos do repositório, a partir de
`ROOT`: as pastas da seção 6.3 existem, cada ADR tem as quatro seções e está na tabela da
seção 24, as regras de `.claude/rules` citam a sua seção, o `.env.example` lista exatamente os
campos de `Settings` com os segredos vazios, e os quatro documentos de `docs/privacy` existem
com o conteúdo que a seção 11.11 pede. Não usa banco nem rede.
"""

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
    ".claude/rules",
    ".github/workflows",
)

SECTION_17_ENV_NAMES = {name.upper() for name in Settings.model_fields}
# Segredos e valores de cada ambiente: o exemplo os deixa vazios (seção 10.6).
EMPTY_SECRET_KEYS = {
    "GEMINI_API_KEY",
    "ADMIN_EMAIL",
    "ADMIN_PASSWORD",
    "METRICS_TOKEN",
    "RATE_LIMIT_HMAC_KEY",
    "PSEUDONYM_KEY",
    "EDGE_SECRET",
    "PRIVACY_CONTACT_EMAIL",
    "LANGSMITH_API_KEY",
    "DATABASE_URL",
    "LANGSMITH_ENDPOINT",
    "WHATSAPP_PHONE_NUMBER_ID",
    "WHATSAPP_BUSINESS_ACCOUNT_ID",
    "WHATSAPP_APP_SECRET",
    "WHATSAPP_ACCESS_TOKEN",
    "WHATSAPP_VERIFY_TOKEN",
}
ADR_HEADINGS = ("## Contexto", "## Decisão", "## Consequências", "## Alternativas")


def test_repository_directories_match_section_6_3() -> None:
    missing = [path for path in EXPECTED_DIRECTORIES if not (ROOT / path).is_dir()]
    assert missing == []


def test_every_adr_has_the_four_sections_and_is_in_section_24() -> None:
    adrs = sorted((ROOT / "docs/adr").glob("[0-9][0-9][0-9]-*.md"))
    assert len(adrs) >= 12
    for adr in adrs:
        text = adr.read_text(encoding="utf-8")
        for heading in ADR_HEADINGS:
            assert heading in text, adr.name
    table = (ROOT / "docs/sdd/entrega.md").read_text(encoding="utf-8")
    listed = re.findall(r"^\| ADR-(\d{3}) \|", table, flags=re.MULTILINE)
    assert listed == [adr.name[:3] for adr in adrs]


def test_claude_rules_cite_their_sdd_sections() -> None:
    rules = ROOT / ".claude/rules"
    assert "6.2" in (rules / "camadas.md").read_text(encoding="utf-8")
    assert "14.8" in (rules / "design-system.md").read_text(encoding="utf-8")
    assert "16.5" in (rules / "gsap.md").read_text(encoding="utf-8")
    assert "29.8" in (rules / "atendimento.md").read_text(encoding="utf-8")


def test_env_example_lists_section_17_without_secrets() -> None:
    example = (ROOT / "apps/api/.env.example").read_text(encoding="utf-8")
    assignments = dict(re.findall(r"^([A-Z0-9_]+)=(.*)$", example, flags=re.MULTILINE))
    assert set(assignments) == SECTION_17_ENV_NAMES
    for key in EMPTY_SECRET_KEYS:
        assert assignments[key] == ""


def test_the_four_privacy_documents_of_section_11_11_exist() -> None:
    privacy = ROOT / "docs/privacy"
    for name in ("ropa.md", "ripd.md", "lia.md", "incident-playbook.md"):
        assert (privacy / name).is_file(), name
    ropa = (privacy / "ropa.md").read_text(encoding="utf-8")
    for processor in ("Railway", "Vercel", "Google", "LangChain"):
        assert processor in ropa
    playbook = (privacy / "incident-playbook.md").read_text(encoding="utf-8")
    assert "3 dias úteis" in playbook
    assert "5 anos" in playbook
