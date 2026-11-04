import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST

from app.core.container import Container, get_clock, get_container
from app.core.metrics import render_metrics
from app.ports.clock import Clock

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
async def metrics(
    container: Annotated[Container, Depends(get_container)],
    clock: Annotated[Clock, Depends(get_clock)],
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    """Métricas do Prometheus. Desligada sem METRICS_TOKEN. Seção 18.3."""
    expected = container.settings.metrics_token
    if not expected:
        raise HTTPException(status_code=404)
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Bearer"})
    # Import tardio: subir a API para /health não carrega o SQLAlchemy.
    from app.services.ops_metrics import refresh_database_metrics

    await refresh_database_metrics(container.settings.database_url, clock)
    return Response(render_metrics(), media_type=CONTENT_TYPE_LATEST)
