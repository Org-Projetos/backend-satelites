from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.jwt_auth import get_current_user
from app.auth.users import user_store
from app.cache import image_cache
from app.config import get_settings
from app.db import init_db
from app.routes import cloud_cover, has_data, render, search, thumbnail, analysis
from app.routes.auth import router as auth_router
from app.routes.schedules import router as schedules_router
from app.scheduler import get_scheduler
from app.services.minio_client import get_minio_client

_OPENAPI_TAGS = [
    {
        "name": "Autenticação",
        "description": (
            "Login, registro e consulta de dados do usuário. "
            "Use **POST /auth/login** para obter o token JWT e clique em **Authorize** "
            "(cadeado) para autenticar todas as rotas protegidas."
        ),
    },
    {
        "name": "Busca de Cenas (STAC)",
        "description": (
            "Consulta o catálogo STAC do Copernicus Data Space (CDSE) "
            "e retorna metadados das cenas disponíveis para a bbox e período informados."
        ),
    },
    {
        "name": "Renderização (Process API)",
        "description": (
            "Gera imagens PNG a partir da Process API do CDSE ou via tiler COG (CBERS-4A). "
            "Suporta visualizações ópticas (truecolor, NDVI, EVI, SWIR…) e SAR (VV, VH, RVI)."
        ),
    },
    {
        "name": "Verificação de Dados",
        "description": "Verifica se há dados de satélite disponíveis para uma bbox e data.",
    },
    {
        "name": "Thumbnail (Proxy)",
        "description": (
            "Proxy autenticado para thumbnails do CDSE. "
            "Protegido contra SSRF — aceita apenas domínios `*.dataspace.copernicus.eu`."
        ),
    },
    {
        "name": "Cobertura de Nuvens",
        "description": (
            "Calcula a porcentagem de nuvens dentro da bbox usando a banda SCL "
            "(Scene Classification Layer) do Sentinel-2 L2A."
        ),
    },
    {
        "name": "Análise via IA",
        "description": (
            "Seleciona automaticamente a melhor cena disponível, renderiza imagens "
            "truecolor e NDVI e envia para o GPT-4o Vision para análise agrícola."
        ),
    },
    {
        "name": "Análises Agendadas",
        "description": (
            "Gerencia análises automáticas semanais. "
            "Salva configuração, imagens no MinIO e histórico de resultados."
        ),
    },
    {
        "name": "Health",
        "description": "Verificação de saúde do serviço.",
    },
]


@asynccontextmanager
async def _lifespan(app: FastAPI):  # noqa: ARG001
    """Inicializa o banco, MinIO e inicia o agendador."""
    settings = get_settings()
    init_db(settings.database_url)
    user_store.seed_admin(settings.admin_username, settings.admin_password)
    
    # Inicializa MinIO
    minio_client = get_minio_client()
    print("✅ MinIO inicializado")
    
    # Inicia agendador de análises
    scheduler = get_scheduler()
    scheduler.start()
    
    yield
    
    # Cleanup: para o agendador
    scheduler.stop()


def create_app() -> FastAPI:
    settings = get_settings()


    app = FastAPI(
        lifespan=_lifespan,
        title="Agro Satélite — Backend",
        description=(
            "Proxy seguro para o **Copernicus Data Space Ecosystem (CDSE)**.\n\n"
            "Gerencia autenticação JWT, busca de cenas STAC, renderização via Process API "
            "e verificação de cobertura de nuvens.\n\n"
            "### Como autenticar\n"
            "1. Chame **POST /auth/login** com `username` e `password`.\n"
            "2. Copie o `access_token` retornado.\n"
            "3. Clique em **Authorize** (cadeado) e cole o token no campo **Value** "
            "(sem o prefixo `Bearer`)."
        ),
        version="1.0.0",
        openapi_tags=_OPENAPI_TAGS,
        docs_url="/docs",
        redoc_url="/redoc",
        swagger_ui_parameters={"persistAuthorization": True},
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
    _err_401 = {"description": "Token ausente, inválido ou expirado"}
    _err_502 = {"description": "Erro ao comunicar com o serviço externo (CDSE / OpenAI)"}
    protected = {
        "dependencies": [Depends(get_current_user)],
        "responses": {401: _err_401, 502: _err_502},
    }
    app.include_router(search.router, prefix="/api", tags=["Busca de Cenas (STAC)"], **protected)
    app.include_router(render.router, prefix="/api", tags=["Renderização (Process API)"], **protected)
    app.include_router(has_data.router, prefix="/api", tags=["Verificação de Dados"], **protected)
    app.include_router(thumbnail.router, prefix="/api", tags=["Thumbnail (Proxy)"], **protected)
    app.include_router(cloud_cover.router, prefix="/api", tags=["Cobertura de Nuvens"], **protected)
    app.include_router(analysis.router, prefix="/api", tags=["Análise via IA"], **protected)
    app.include_router(schedules_router, prefix="/api", tags=["Análises Agendadas"], **protected)

    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
