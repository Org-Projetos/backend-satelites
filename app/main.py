from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.jwt_auth import get_current_user
from app.auth.users import user_store
from app.cache import image_cache
from app.config import get_settings
from app.db import init_db
from app.routes import cloud_cover, has_data, render, search, thumbnail, analysis
from app.routes.auth import router as auth_router


def create_app() -> FastAPI:
    settings = get_settings()

    # Inicializa o banco (CREATE TABLE IF NOT EXISTS) e semeia o admin
    init_db(settings.database_url)
    user_store.seed_admin(settings.admin_username, settings.admin_password)

    app = FastAPI(
        title="Agro Satélite — Backend",
        description=(
            "Proxy seguro para o Copernicus Data Space Ecosystem (CDSE). "
            "Gerencia autenticação, busca de cenas STAC, renderização via Process API "
            "e verificação de cobertura de nuvens."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Rate limiting por IP
    if settings.rate_limit_enabled:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded
        from slowapi.middleware import SlowAPIMiddleware
        from slowapi.util import get_remote_address

        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=[settings.rate_limit_default],
        )
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.add_middleware(SlowAPIMiddleware)

    # Cache de imagens — reconfigura TTL e tamanho com valores do .env
    image_cache.reconfigure(
        ttl=settings.image_cache_ttl_seconds,
        max_size=settings.image_cache_max_size,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rotas públicas: autenticação
    app.include_router(auth_router)

    # Rotas protegidas: todas as rotas /api/* exigem JWT válido
    protected = {"dependencies": [Depends(get_current_user)]}
    app.include_router(search.router, prefix="/api", tags=["Busca de Cenas (STAC)"], **protected)
    app.include_router(render.router, prefix="/api", tags=["Renderização (Process API)"], **protected)
    app.include_router(has_data.router, prefix="/api", tags=["Verificação de Dados"], **protected)
    app.include_router(thumbnail.router, prefix="/api", tags=["Thumbnail (Proxy)"], **protected)
    app.include_router(cloud_cover.router, prefix="/api", tags=["Cobertura de Nuvens"], **protected)
    app.include_router(analysis.router, prefix="/api", tags=["Análise via IA"], **protected)

    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
