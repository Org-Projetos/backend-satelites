"""
Fixtures e configurações globais para os testes.

Usa:
  - pytest-asyncio para testes assíncronos
  - respx para mockar chamadas httpx
  - TestClient do FastAPI para testes de integração
"""

import io
import os

import pytest
import respx
from fastapi.testclient import TestClient
from PIL import Image

# Garante que variáveis de ambiente de teste estejam definidas antes de importar o app
os.environ.setdefault("CDSE_CLIENT_ID", "test-client-id")
os.environ.setdefault("CDSE_CLIENT_SECRET", "test-client-secret")


@pytest.fixture(scope="session")
def app():
    from app.main import create_app

    return create_app()


@pytest.fixture(scope="session")
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_token_cache():
    """Limpa o cache de token antes de cada teste para garantir isolamento."""
    from app.auth.cdse import cdse_auth

    cdse_auth.invalidate()
    yield
    cdse_auth.invalidate()


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
    """Gera bytes de um PNG de teste (grande = tem dados, pequeno = sem dados)."""
    img = Image.new("RGB", (width, height), color=(34, 100, 34) if large else (0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    content = buf.getvalue()
    if not large:
        # Retorna apenas os primeiros bytes para simular PNG "vazio"
        return content[:100]
    return content


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
