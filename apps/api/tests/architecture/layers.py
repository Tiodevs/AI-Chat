"""Regras de importação da seção 6.2 do SDD, lidas com ast."""

import ast
import sys
from pathlib import Path

LAYERS = (
    "app.domain",
    "app.controllers",
    "app.services",
    "app.workflows",
    "app.repositories",
    "app.models",
)

_FORBIDDEN: dict[str, tuple[str, ...]] = {
    "app.controllers": ("langchain", "langgraph", "langsmith", "sqlalchemy", "app.repositories"),
    "app.services": ("fastapi", "langchain", "langgraph", "langsmith"),
    "app.workflows": ("fastapi", "sqlalchemy"),
    "app.repositories": ("langchain", "langgraph", "langsmith", "fastapi"),
    "app.models": ("fastapi", "langchain"),
}

API_ROOT = Path(__file__).resolve().parents[2]


def layer_of(module: str) -> str | None:
    for layer in LAYERS:
        if module == layer or module.startswith(f"{layer}."):
            return layer
    return None


def import_violations(module: str, source: str, *, is_package: bool = False) -> list[str]:
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
    if layer == "app.domain":
        return _domain_allows(imported)
    forbidden = _FORBIDDEN[layer]
    return not any(imported == item or imported.startswith(f"{item}.") for item in forbidden)


def imported_modules(module: str, tree: ast.AST, *, is_package: bool) -> list[str]:
    package = module if is_package else _parent(module)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.extend(_from_import(package, node))
    return found


def _domain_allows(imported: str) -> bool:
    if imported == "app.domain" or imported.startswith("app.domain."):
        return True
    if imported == "pydantic" or imported.startswith("pydantic."):
        return True
    return imported.split(".", 1)[0] in sys.stdlib_module_names


def _from_import(package: str, node: ast.ImportFrom) -> list[str]:
    if node.level == 0:
        if node.module is None:
            return []
        return [node.module]
    parts = package.split(".")
    drop = node.level - 1
    if drop:
        parts = parts[:-drop]
    if node.module:
        return [".".join([*parts, *node.module.split(".")])]
    return [".".join([*parts, alias.name]) for alias in node.names]


def _module_name(path: Path, api_root: Path) -> str:
    parts = list(path.relative_to(api_root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _parent(module: str) -> str:
    parent, separator, _name = module.rpartition(".")
    if not separator:
        return module
    return parent
