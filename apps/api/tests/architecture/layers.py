"""Regras de importação da seção 6.2 do SDD, lidas com ast. NFR-1.

Helper do `test_layers.py`, sem testes próprios. Lê o código-fonte de `app/` como texto e
analisa a árvore com `ast`, sem importar nenhum módulo, então um import proibido aparece mesmo
que nunca rode. Só as seis camadas de `LAYERS` são conferidas; `app.core`, `app.ports`,
`app.adapters`, `app.schemas`, `app.prompts`, `app.db` e `app.scripts` ficam fora. A regra
equivalente do frontend é o `no-restricted-imports` do ESLint, provado em
`apps/web/src/eslint/restrictions.test.ts`. Não usa banco nem rede.
"""

import ast
import sys
from pathlib import Path

# As camadas conferidas, na ordem da tabela "Teste de arquitetura" da seção 6.2.
LAYERS = (
    "app.domain",
    "app.controllers",
    "app.services",
    "app.workflows",
    "app.repositories",
    "app.models",
)

# Lista de recusa por prefixo de cada camada, copiada da seção 6.2. O domínio não está aqui
# porque usa lista de permissão (`_domain_allows`). A Etapa 13.2 acrescenta `app.adapters` em
# `app.workflows`; hoje um workflow pode importar um adaptador.
_FORBIDDEN: dict[str, tuple[str, ...]] = {
    "app.controllers": ("langchain", "langgraph", "langsmith", "sqlalchemy", "app.repositories"),
    "app.services": ("fastapi", "langchain", "langgraph", "langsmith"),
    "app.workflows": ("fastapi", "sqlalchemy"),
    "app.repositories": ("langchain", "langgraph", "langsmith", "fastapi"),
    "app.models": ("fastapi", "langchain"),
}

# `apps/api`, a pasta que contém `app/`.
API_ROOT = Path(__file__).resolve().parents[2]


def layer_of(module: str) -> str | None:
    """A camada de `LAYERS` a que o módulo pertence, ou `None` se ele fica fora das seis."""
    for layer in LAYERS:
        if module == layer or module.startswith(f"{layer}."):
            return layer
    return None


def import_violations(module: str, source: str, *, is_package: bool = False) -> list[str]:
    """As importações proibidas de um módulo, como frases `"<módulo> imports <importado>"`.

    `source` é o código do módulo. `is_package` diz se ele é um `__init__.py`, o que muda a
    base dos imports relativos. Um módulo fora das camadas devolve a lista vazia.
    """
    layer = layer_of(module)
    if layer is None:
        return []
    tree = ast.parse(source)
    return [
        f"{module} imports {imported}"
        for imported in imported_modules(module, tree, is_package=is_package)
        if not import_allowed(layer, imported)
    ]


def package_violations(api_root: Path = API_ROOT) -> list[str]:
    """Todas as violações de `app/**/*.py`, em ordem de caminho. Vazia quando as camadas batem."""
    violations: list[str] = []
    for path in sorted((api_root / "app").rglob("*.py")):
        module = _module_name(path, api_root)
        violations.extend(
            import_violations(
                module,
                path.read_text(encoding="utf-8"),
                is_package=path.name == "__init__.py",
            )
        )
    return violations


def import_allowed(layer: str, imported: str) -> bool:
    """Se a camada pode importar o módulo: permissão no domínio, recusa por prefixo nas demais.

    O prefixo casa o nome inteiro ou seguido de ponto, então `sqlalchemy.orm` cai na recusa de
    `sqlalchemy`, mas `sqlalchemyx` não.
    """
    if layer == "app.domain":
        return _domain_allows(imported)
    forbidden = _FORBIDDEN[layer]
    return not any(imported == item or imported.startswith(f"{item}.") for item in forbidden)


def imported_modules(module: str, tree: ast.AST, *, is_package: bool) -> list[str]:
    """Os nomes absolutos de tudo o que a árvore importa, com os relativos já resolvidos.

    `ast.walk` percorre a árvore inteira, então entram também os imports dentro de funções e de
    blocos `if TYPE_CHECKING:`.
    """
    package = module if is_package else _parent(module)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.extend(_from_import(package, node))
    return found


def _domain_allows(imported: str) -> bool:
    """Lista de permissão do domínio: o próprio `app.domain`, o `pydantic` e a biblioteca padrão.

    A biblioteca padrão vem de `sys.stdlib_module_names`, pelo primeiro nome do módulo.
    """
    if imported == "app.domain" or imported.startswith("app.domain."):
        return True
    if imported == "pydantic" or imported.startswith("pydantic."):
        return True
    return imported.split(".", 1)[0] in sys.stdlib_module_names


def _from_import(package: str, node: ast.ImportFrom) -> list[str]:
    """Os nomes absolutos de um `from ... import ...`.

    1. Absoluto (`level == 0`): devolve só o módulo, sem os nomes importados dele.
    2. Relativo: cada ponto além do primeiro sobe um pacote a partir de `package`.
    3. Com módulo (`from ..repositories import X`): devolve o módulo resolvido.
    4. Sem módulo (`from .. import repositories`): devolve um nome por item importado.
    """
    # 1.
    if node.level == 0:
        if node.module is None:
            return []
        return [node.module]
    # 2.
    parts = package.split(".")
    drop = node.level - 1
    if drop:
        parts = parts[:-drop]
    # 3.
    if node.module:
        return [".".join([*parts, *node.module.split(".")])]
    # 4.
    return [".".join([*parts, alias.name]) for alias in node.names]


def _module_name(path: Path, api_root: Path) -> str:
    """O nome pontuado do arquivo, como `app.domain.grounding`; um `__init__.py` vira o pacote."""
    parts = list(path.relative_to(api_root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _parent(module: str) -> str:
    """O pacote que contém o módulo, base de um import relativo de nível 1."""
    parent, separator, _name = module.rpartition(".")
    if not separator:
        return module
    return parent
