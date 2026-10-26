from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def get_container(settings: Annotated[Settings, Depends(get_settings)]) -> Container:
    return Container(settings=settings)
