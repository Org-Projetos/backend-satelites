"""Testes para os endpoints de renderização de imagens (Process API)."""

import pytest
import respx
import httpx
from unittest.mock import AsyncMock, patch

from tests.conftest import SAMPLE_BBOX, make_png_bytes

PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"


@pytest.fixture(autouse=True)
def mock_token():
    with patch("app.auth.cdse.cdse_auth.get_token", new_callable=AsyncMock) as m:
        m.return_value = "mock-token"
        yield m


# ─── POST /api/render ─────────────────────────────────────────────────────────


@respx.mock
def test_render_optical_s2_truecolor(client):
    """Deve retornar PNG para S2 truecolor."""
    png = make_png_bytes()
    respx.post(PROCESS_URL).mock(
        return_value=httpx.Response(200, content=png, headers={"content-type": "image/png"})
    )

    resp = client.post(
        "/api/render",
        json={
            "bbox": SAMPLE_BBOX,
            "date": "2024-01-15",
            "visualType": "truecolor",
            "resolution": "medium",
            "maxCloudCover": 30,
            "satelliteType": "sentinel2",
        },
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert len(resp.content) > 0


@respx.mock
def test_render_optical_landsat_ndvi(client):
    """Deve retornar PNG para Landsat NDVI."""
    png = make_png_bytes()
    respx.post(PROCESS_URL).mock(
        return_value=httpx.Response(200, content=png, headers={"content-type": "image/png"})
    )

    resp = client.post(
        "/api/render",
        json={
            "bbox": SAMPLE_BBOX,
            "date": "2024-01-15",
            "visualType": "ndvi",
            "resolution": "low",
            "maxCloudCover": 80,
            "satelliteType": "landsat",
        },
    )

    assert resp.status_code == 200
    assert "image/png" in resp.headers["content-type"]


@respx.mock
def test_render_all_s2_visual_types(client):
    """Deve aceitar todos os visualTypes para Sentinel-2."""
    visual_types = ["truecolor", "falsecolor", "ndvi", "evi", "swir", "ndmi", "ndwi"]
    png = make_png_bytes()
    respx.post(PROCESS_URL).mock(
        return_value=httpx.Response(200, content=png, headers={"content-type": "image/png"})
    )

    for vt in visual_types:
        resp = client.post(
            "/api/render",
            json={
                "bbox": SAMPLE_BBOX,
                "date": "2024-01-15",
                "visualType": vt,
                "satelliteType": "sentinel2",
            },
        )
        assert resp.status_code == 200, f"Falhou para visualType={vt}"


def test_render_invalid_visual_type(client):
    """Deve retornar 422 para visualType inválido."""
    resp = client.post(
        "/api/render",
        json={
            "bbox": SAMPLE_BBOX,
            "date": "2024-01-15",
            "visualType": "invalid_type",
            "satelliteType": "sentinel2",
        },
    )
    assert resp.status_code == 422


def test_render_invalid_resolution(client):
    """Deve retornar 422 para resolution inválida."""
    resp = client.post(
        "/api/render",
        json={
            "bbox": SAMPLE_BBOX,
            "date": "2024-01-15",
            "resolution": "ultra",  # inválido
            "satelliteType": "sentinel2",
        },
    )
    assert resp.status_code == 422


@respx.mock
def test_render_process_api_error_returns_502(client):
    """Deve retornar 502 quando a Process API retornar erro."""
    respx.post(PROCESS_URL).mock(return_value=httpx.Response(500, text="Server Error"))

    resp = client.post(
        "/api/render",
        json={
            "bbox": SAMPLE_BBOX,
            "date": "2024-01-15",
            "satelliteType": "sentinel2",
        },
    )
    assert resp.status_code == 502


# ─── POST /api/render/s1 ──────────────────────────────────────────────────────


@respx.mock
def test_render_s1_rgb(client):
    """Deve retornar PNG para Sentinel-1 RGB."""
    png = make_png_bytes()
    respx.post(PROCESS_URL).mock(
        return_value=httpx.Response(200, content=png, headers={"content-type": "image/png"})
    )

    resp = client.post(
        "/api/render/s1",
        json={
            "bbox": SAMPLE_BBOX,
            "date": "2024-01-15",
            "visualType": "rgb",
            "resolution": "medium",
        },
    )

    assert resp.status_code == 200
    assert "image/png" in resp.headers["content-type"]


@respx.mock
def test_render_s1_all_visual_types(client):
    """Deve aceitar todos os visualTypes para Sentinel-1."""
    visual_types = ["vv", "vh", "rgb", "rvi"]
    png = make_png_bytes()
    respx.post(PROCESS_URL).mock(
        return_value=httpx.Response(200, content=png, headers={"content-type": "image/png"})
    )

    for vt in visual_types:
        resp = client.post(
            "/api/render/s1",
            json={
                "bbox": SAMPLE_BBOX,
                "date": "2024-01-15",
                "visualType": vt,
            },
        )
        assert resp.status_code == 200, f"Falhou para visualType S1={vt}"


@respx.mock
def test_render_s1_invalid_visual_type(client):
    """Deve retornar 422 para visualType Sentinel-1 inválido."""
    resp = client.post(
        "/api/render/s1",
        json={
            "bbox": SAMPLE_BBOX,
            "date": "2024-01-15",
            "visualType": "ndvi",  # só para óptico
        },
    )
    assert resp.status_code == 422


# ─── Cálculo de dimensões ─────────────────────────────────────────────────────


def test_compute_dimensions_medium():
    """Deve calcular dimensões corretas para resolução medium com bbox quadrada."""
    from app.services.process_api import compute_dimensions

    # bbox quadrada → width == height == 1024
    w, h = compute_dimensions([-47.0, -23.0, -46.0, -22.0], "medium")
    assert w == 1024
    assert h == 1024


def test_compute_dimensions_wide_bbox():
    """Deve limitar width a max_px e calcular height proporcional."""
    from app.services.process_api import compute_dimensions

    # bbox 2x mais larga que alta
    w, h = compute_dimensions([-47.0, -23.0, -45.0, -22.0], "medium")
    assert w == 1024
    assert h == 512


def test_compute_dimensions_low_high():
    """Deve respeitar os limites por resolução."""
    from app.services.process_api import compute_dimensions

    w_low, _ = compute_dimensions([-47.0, -23.0, -46.0, -22.0], "low")
    w_high, _ = compute_dimensions([-47.0, -23.0, -46.0, -22.0], "high")
    assert w_low == 512
    assert w_high == 2048


def test_compute_dimensions_native_clamps():
    """Deve limitar a 2500px em resolução native para bbox grande."""
    from app.services.process_api import compute_dimensions

    # Bbox grande (~10 graus)
    w, h = compute_dimensions([-60.0, -30.0, -50.0, -20.0], "native")
    assert max(w, h) <= 2500
    assert w >= 64 and h >= 64
