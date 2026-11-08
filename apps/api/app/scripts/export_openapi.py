"""Gera o OpenAPI e grava o contrato do frontend. Seção 6.6 do SDD.

Uso: `python -m app.scripts.export_openapi`, em `apps/api`, sempre que a API mudar. Depois,
`pnpm openapi-types` em `apps/web` gera o `schema.ts` a partir do arquivo. O job `contract` da
CI roda os dois e falha se o resultado diferir do que está commitado (NFR-16).

Grava `apps/web/src/lib/api/openapi.json`. Não usa banco nem rede, mas importa `app.main`, que
monta a aplicação com a configuração do ambiente: com `APP_ENV` `development` ou `production`,
a montagem exige as proteções da seção 7.1, como o teto de tokens.
"""

import json
from pathlib import Path


def main() -> None:
    """Escreve o schema OpenAPI do FastAPI com indentação de 2 e quebra de linha no fim.

    `ensure_ascii=False` mantém os acentos legíveis no arquivo. O import de `app.main` fica
    aqui dentro, para importar este módulo não montar a aplicação.
    """
    from app.main import app

    # Quatro pastas acima de `apps/api/app/scripts` fica a raiz do repositório.
    destination = Path(__file__).resolve().parents[4] / "apps/web/src/lib/api/openapi.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    text = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
    destination.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
