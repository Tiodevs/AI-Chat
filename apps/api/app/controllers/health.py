from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.build import build_sha
from app.core.container import Container, get_container

router = APIRouter()


@router.get("/health")
async def health(_: Annotated[Container, Depends(get_container)]) -> dict[str, str | None]:
    """O processo está no ar, com o commit da imagem. Esta rota não abre conexão com o banco."""
    return {"status": "ok", "build": build_sha()}
