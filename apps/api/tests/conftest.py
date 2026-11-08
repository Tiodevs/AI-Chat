"""Configuração comum das quatro suítes da API: nenhum teste chama o LangSmith. NFR-3, seção 21.1.

O pytest carrega este arquivo antes de qualquer teste de `unit`, `integration`, `architecture` e
`contract`. Ele desliga o `LANGSMITH_TRACING` na importação, antes de algum módulo ler a
configuração, e a fixture automática repete isso a cada teste. Não usa banco nem rede.
"""

import os
from collections.abc import Iterator

import pytest

from app.adapters.langsmith_tracing import reset_langsmith_runtime
from app.core.container import get_settings

# A suíte padrão não chama o LangSmith, mesmo com a chave no .env. NFR-3.
os.environ["LANGSMITH_TRACING"] = "false"


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> Iterator[None]:
    """Isola cada teste da configuração e dos clientes do LangSmith do teste anterior.

    `get_settings` guarda um `Settings` em cache (`lru_cache`), e `runtime_for` guarda os clientes
    do LangSmith montados para ele. Sem a limpeza, um teste que muda o ambiente com `monkeypatch`
    veria a configuração do teste anterior. A limpeza roda antes e depois de cada teste, e o
    `LANGSMITH_TRACING` volta a `false` mesmo que um teste o tenha ligado.
    """
    os.environ["LANGSMITH_TRACING"] = "false"
    get_settings.cache_clear()
    reset_langsmith_runtime()
    yield
    get_settings.cache_clear()
    reset_langsmith_runtime()
