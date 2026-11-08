"""Pacote da API do Atrium. Define `__version__`, a versão instalada de `atrium-api`.

A versão vem dos metadados que o `uv sync` instala a partir do `pyproject.toml`. Sem o pacote
instalado, vale `0.1.0`. Quem usa: o OpenAPI em `app/main.py`, o campo `app_version` dos logs
em `app/core/logging.py` e os metadados dos rastros do LangSmith em
`app/services/conversations.py` e `app/workflows/qa.py`. Seções 18.1 e 18.4 do SDD.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("atrium-api")
except PackageNotFoundError:
    __version__ = "0.1.0"
