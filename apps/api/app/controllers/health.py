from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.container import Container, get_container

router = APIRouter()


@router.get("/health")
async def health(_: Annotated[Container, Depends(get_container)]) -> dict[str, str]:
    """O processo está no ar. Esta rota não abre conexão com o banco."""
    return {"status": "ok"}
