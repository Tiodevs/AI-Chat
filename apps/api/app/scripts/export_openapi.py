"""Gera o OpenAPI e grava o contrato do frontend. Seção 6.6 do SDD."""

import json
from pathlib import Path


def main() -> None:
    from app.main import app

    destination = Path(__file__).resolve().parents[4] / "apps/web/src/lib/api/openapi.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    text = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
    destination.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
