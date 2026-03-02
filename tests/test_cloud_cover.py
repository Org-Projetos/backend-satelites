"""Testes para os endpoints de cobertura de nuvens (/api/cloudCover)."""

import pytest
import respx
import httpx
from unittest.mock import AsyncMock, patch

from tests.conftest import SAMPLE_BBOX, make_cloud_mask_png

PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"

SCENE_ID = "S2A_MSIL2A_20240115T130259_N0510_R090_T22KCD"


@pytest.fixture(autouse=True)
def mock_token():
    with patch("app.auth.cdse.cdse_auth.get_token", new_callable=AsyncMock) as m:
        m.return_value = "mock-token"
        yield m


# ─── POST /api/cloudCover ─────────────────────────────────────────────────────


@respx.mock
def test_cloud_cover_post_30_percent(client):
    """Deve calcular corretamente 30% de cobertura de nuvens."""
    mask_png = make_cloud_mask_png(cloud_fraction=0.30)
    respx.post(PROCESS_URL).mock(
        return_value=httpx.Response(200, content=mask_png)
    )

    resp = client.post(
        "/api/cloudCover",
        json={
            "sceneId": SCENE_ID,
            "bbox": SAMPLE_BBOX,
            "date": "2024-01-15",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["sceneId"] == SCENE_ID
    # Tolerância de ±2% por arredondamentos de pixel
    assert abs(data["cloudCover"] - 30.0) < 2.0


@respx.mock
def test_cloud_cover_post_zero_clouds(client):
    """Deve retornar 0% quando não há pixels de nuvem."""
    mask_png = make_cloud_mask_png(cloud_fraction=0.0)
    respx.post(PROCESS_URL).mock(
        return_value=httpx.Response(200, content=mask_png)
    )

    resp = client.post(
        "/api/cloudCover",
        json={
            "sceneId": SCENE_ID,
            "bbox": SAMPLE_BBOX,
            "date": "2024-01-15",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["cloudCover"] == 0.0


@respx.mock
def test_cloud_cover_post_full_clouds(client):
    """Deve retornar ~100% quando todos os pixels são nuvem."""
    mask_png = make_cloud_mask_png(cloud_fraction=1.0)
    respx.post(PROCESS_URL).mock(
        return_value=httpx.Response(200, content=mask_png)
    )

    resp = client.post(
        "/api/cloudCover",
        json={
            "sceneId": SCENE_ID,
            "bbox": SAMPLE_BBOX,
            "date": "2024-01-15",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["cloudCover"] > 95.0


@respx.mock
def test_cloud_cover_post_process_api_error(client):
    """Deve retornar 502 quando a Process API falhar."""
    respx.post(PROCESS_URL).mock(return_value=httpx.Response(500, text="Error"))

    resp = client.post(
        "/api/cloudCover",
        json={
            "sceneId": SCENE_ID,
            "bbox": SAMPLE_BBOX,
            "date": "2024-01-15",
        },
    )

    assert resp.status_code == 502


def test_cloud_cover_post_missing_date(client):
    """Deve retornar 422 quando date não for fornecida."""
    resp = client.post(
        "/api/cloudCover",
        json={
            "sceneId": SCENE_ID,
            "bbox": SAMPLE_BBOX,
            # date ausente
        },
    )
    assert resp.status_code == 422


# ─── GET /api/cloudCover ──────────────────────────────────────────────────────


@respx.mock
def test_cloud_cover_get(client):
    """Deve funcionar via GET com query params."""
    mask_png = make_cloud_mask_png(cloud_fraction=0.20)
    respx.post(PROCESS_URL).mock(
        return_value=httpx.Response(200, content=mask_png)
    )

    bbox_str = ",".join(map(str, SAMPLE_BBOX))
    resp = client.get(
        f"/api/cloudCover?sceneId={SCENE_ID}&bbox={bbox_str}&date=2024-01-15"
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "cloudCover" in data
    assert data["sceneId"] == SCENE_ID


def test_cloud_cover_get_invalid_bbox(client):
    """Deve retornar 422 para bbox mal formatada no GET."""
    resp = client.get(
        f"/api/cloudCover?sceneId={SCENE_ID}&bbox=invalid&date=2024-01-15"
    )
    assert resp.status_code == 422


def test_cloud_cover_get_bbox_wrong_count(client):
    """Deve retornar 422 para bbox com número incorreto de valores."""
    resp = client.get(
        f"/api/cloudCover?sceneId={SCENE_ID}&bbox=-47.0,-23.0&date=2024-01-15"
    )
    assert resp.status_code == 422
