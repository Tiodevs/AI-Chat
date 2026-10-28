import os
from collections.abc import Iterator

import pytest

from app.adapters.langsmith_tracing import reset_langsmith_runtime
from app.core.container import get_settings

# A suíte padrão não chama o LangSmith, mesmo com a chave no .env. NFR-3.
os.environ["LANGSMITH_TRACING"] = "false"


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> Iterator[None]:
    os.environ["LANGSMITH_TRACING"] = "false"
    get_settings.cache_clear()
    reset_langsmith_runtime()
    yield
    get_settings.cache_clear()
    reset_langsmith_runtime()
