from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes import cloud_cover, has_data, render, search, thumbnail


def create_app() -> FastAPI:
    settings = get_settings()

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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(search.router, prefix="/api", tags=["Busca de Cenas (STAC)"])
    app.include_router(render.router, prefix="/api", tags=["Renderização (Process API)"])
    app.include_router(has_data.router, prefix="/api", tags=["Verificação de Dados"])
    app.include_router(thumbnail.router, prefix="/api", tags=["Thumbnail (Proxy)"])
    app.include_router(cloud_cover.router, prefix="/api", tags=["Cobertura de Nuvens"])

    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
