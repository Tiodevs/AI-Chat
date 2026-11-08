# architecture

Teste de arquitetura da API: confere, com `ast`, que cada camada importa só o que a [seção 6.2 do SDD](../../../../docs/sdd/arquitetura.md#62-mvc-com-as-camadas-de-que-um-sistema-de-ia-precisa) permite (NFR-1). Roda na suíte padrão do pytest, sem banco e sem rede.

## Arquivos

| Arquivo | O que prova ou faz | O que cobre |
|---|---|---|
| [`__init__.py`](__init__.py) | Vazio. Faz da pasta um pacote, para o teste importar `tests.architecture.layers` | |
| [`layers.py`](layers.py) | Helper sem testes. Lê cada arquivo de `app/` como texto, extrai os imports com `ast`, resolve os relativos e compara com as regras de cada camada | A tabela "Teste de arquitetura" da seção 6.2 |
| [`test_layers.py`](test_layers.py) | 24 testes. Um passa as regras por todo `app/`. Os outros provam que cada proibição é detectada (21 casos, inclusive um import relativo) e que o permitido passa (2 casos) | NFR-1, seção 6.2 |

## Como ler

1. Comece por `LAYERS` e `_FORBIDDEN` em `layers.py`: são a tabela da seção 6.2 escrita em Python. O domínio usa lista de permissão (biblioteca padrão, `pydantic` e o próprio `app.domain`). As outras cinco camadas usam lista de recusa por prefixo.
2. Siga `package_violations`, `import_violations`, `imported_modules` e `_from_import`, nessa ordem. É o caminho de um arquivo até a frase `"<módulo> imports <importado>"`.
3. Leia `test_layers.py`. O primeiro teste é o que protege o código. Os demais existem para que uma regra quebrada não deixe o primeiro verde em silêncio.

Conceitos que ajudam:

- **`ast`.** O módulo da biblioteca padrão que transforma código Python numa árvore sem executá-lo. Um import proibido aparece mesmo dentro de uma função ou de um bloco `if TYPE_CHECKING:`.
- **Import relativo.** `from ..repositories import X` dentro de `app.controllers.health` vira `app.repositories`. Cada ponto além do primeiro sobe um pacote.
- **Fora das camadas.** `app.core`, `app.ports`, `app.adapters`, `app.schemas`, `app.prompts`, `app.db` e `app.scripts` não são conferidos.

Limites que o código tem hoje:

- Num import absoluto conta só o módulo. `from app import repositories` num controlador vira `app` e passa; a forma relativa, `from .. import repositories`, é pega.
- Um workflow pode importar um adaptador. A [Etapa 13.2](../../../../docs/plano-de-acao.md#etapa-132--embedding-resiliente-atrás-da-porta) acrescenta `app.adapters` à recusa de `app.workflows`.

A regra equivalente do frontend é o `no-restricted-imports` do ESLint, provado em [`restrictions.test.ts`](../../../web/src/eslint/restrictions.test.ts).

## Testes

Em `apps/api`:

```bash
uv run pytest tests/architecture
```

O job `api` do `ci.yml` roda esta pasta junto com as outras suítes no `uv run pytest`.

## Leia também

- [SDD 6.2](../../../../docs/sdd/arquitetura.md#62-mvc-com-as-camadas-de-que-um-sistema-de-ia-precisa): as camadas, a direção da dependência e o teste de arquitetura.
- [SDD 21.1](../../../../docs/sdd/entrega.md#211-ci-padrão): o que a CI padrão prova.
- [`.claude/rules/camadas.md`](../../../../.claude/rules/camadas.md): as mesmas regras, escritas para agentes de código.
- [README das suítes](../README.md).
- [Guia, parte 3](../../../../docs/guia/03-api-por-dentro.md) e [parte 13](../../../../docs/guia/13-testes.md).
