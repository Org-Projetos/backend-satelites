"""
Fixtures e configurações globais para os testes.

Usa:
  - pytest-asyncio para testes assíncronos
  - respx para mockar chamadas httpx
  - TestClient do FastAPI para testes de integração
  - SQLite em memória (sem PostgreSQL, MinIO ou APScheduler reais)
"""

import io
import os
from unittest.mock import MagicMock, patch

import pytest
import respx
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

# ─── Variáveis de ambiente mínimas (antes de qualquer import da app) ──────────
os.environ.setdefault("CDSE_CLIENT_ID", "test-client-id")
os.environ.setdefault("CDSE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("RATE_LIMIT_ENABLED", "False")
os.environ.setdefault("SECRET_KEY", "test-secret-key-conftest-only")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "agro2024")


# ─── App com escopo de sessão ─────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    """
    Cria a aplicação FastAPI com banco SQLite em memória.
    Sobrescreve `get_current_user` para que testes STAC/render
    não precisem fornecer tokens JWT.
    """
    from app.config import get_settings
    get_settings.cache_clear()

    import app.db as db_module
    from app.db import users_table

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    users_table.create(test_engine)
    db_module._engine = test_engine
    db_module.init_db = lambda url: test_engine

    # Importar create_app aqui garante que app.main está no sys.modules
    from app.main import create_app
    application = create_app()

    # Bypass JWT para o client de sessão (testes de satélite não enviam tokens)
    from app.auth.jwt_auth import get_current_user
    from app.auth.users import User

    application.dependency_overrides[get_current_user] = lambda: User(
        username="admin", hashed_password="", is_admin=True
    )

    return application


@pytest.fixture(scope="session")
def client(app):
    """Client de sessão com patches para MinIO e APScheduler."""
    _sched_mock = MagicMock()
    with (
        patch("app.main.get_minio_client", return_value=MagicMock()),
        patch("app.main.get_scheduler", return_value=_sched_mock),
    ):
        with TestClient(app) as c:
            yield c


@pytest.fixture(autouse=True)
def reset_token_cache():
    """Limpa o cache de token CDSE antes de cada teste para garantir isolamento."""
    from app.auth.cdse import cdse_auth

    cdse_auth.invalidate()
    yield
    cdse_auth.invalidate()


@pytest.fixture(autouse=True)
def reset_image_cache():
    """Limpa o cache de imagens entre testes para evitar poluição entre cenários."""
    from app.cache import image_cache

    with image_cache._lock:
        image_cache._store.clear()
    yield
    with image_cache._lock:
        image_cache._store.clear()


# ─── Payloads CDSE mock ───────────────────────────────────────────────────────

TOKEN_RESPONSE = {
    "access_token": "mock-access-token-abc123",
    "expires_in": 3600,
    "token_type": "Bearer",
}

STAC_RESPONSE_S2 = {
    "type": "FeatureCollection",
    "features": [
        {
            "id": "S2A_MSIL2A_20240115T130259_N0510_R090_T22KCD",
            "properties": {
                "datetime": "2024-01-15T13:02:59Z",
                "eo:cloud_cover": 5.2,
            },
            "assets": {
                "thumbnail": {
                    "href": "https://sh.dataspace.copernicus.eu/thumb1.jpg"
                }
            },
        },
        {
            "id": "S2B_MSIL2A_20240120T130259_N0510_R090_T22KCD",
            "properties": {
                "datetime": "2024-01-20T13:02:59Z",
                "eo:cloud_cover": 12.8,
            },
            "assets": {
                "thumbnail": {
                    "href": "https://sh.dataspace.copernicus.eu/thumb2.jpg"
                }
            },
        },
    ],
}

STAC_RESPONSE_LANDSAT = {
    "type": "FeatureCollection",
    "features": [
        {
            "id": "LC09_L1TP_221075_20240118_20240119_02_T1",
            "properties": {
                "datetime": "2024-01-18T13:00:00Z",
                "eo:cloud_cover": 8.0,
            },
            "assets": {
                "thumbnail": {
                    "href": "https://sh.dataspace.copernicus.eu/thumb3.jpg"
                }
            },
        },
    ],
}

STAC_RESPONSE_S1 = {
    "type": "FeatureCollection",
    "features": [
        {
            "id": "S1A_IW_GRDH_20240120T090000",
            "properties": {
                "datetime": "2024-01-20T09:00:00Z",
            },
            "assets": {},
        },
    ],
}


def make_png_bytes(width: int = 64, height: int = 64, large: bool = True) -> bytes:
    """Gera bytes de um PNG de teste (grande = tem dados, pequeno = sem dados).

    Para large=True usa compress_level=0 para garantir arquivo > has_data_threshold_bytes (1500 B).
    Cores sólidas comprimem para centenas de bytes — abaixo do threshold — sem essa opção.
    """
    color = (34, 100, 34) if large else (0, 0, 0)
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    if large:
        img.save(buf, format="PNG", compress_level=0)
    else:
        img.save(buf, format="PNG")
        return buf.getvalue()[:100]
    return buf.getvalue()


def make_cloud_mask_png(cloud_fraction: float = 0.3, size: int = 256) -> bytes:
    """Gera PNG de máscara de nuvem (255 = nuvem, 0 = sem nuvem)."""
    cloud_pixels = int(size * size * cloud_fraction)
    data = [255 if i < cloud_pixels else 0 for i in range(size * size)]
    img = Image.new("L", (size, size))
    img.putdata(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


SAMPLE_BBOX = [-47.0, -23.0, -46.5, -22.5]
