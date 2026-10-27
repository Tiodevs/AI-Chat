from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.controllers.admin_probe import router as admin_probe_router
from app.controllers.auth import router as auth_router
from app.controllers.health import router as health_router
from app.controllers.legal import router as legal_router
from app.controllers.readiness import router as readiness_router
from app.core.container import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import ApiGuardMiddleware, RequestIdMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="Atrium", version=__version__)
    app.add_middleware(ApiGuardMiddleware, web_origin=settings.web_origin)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type"],
    )
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(readiness_router)
    app.include_router(legal_router)
    app.include_router(auth_router)
    app.include_router(admin_probe_router)
    return app


app = create_app()
