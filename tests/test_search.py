"""Testes para os endpoints de busca de cenas STAC."""

import pytest
import respx
import httpx
from unittest.mock import AsyncMock, patch

from tests.conftest import (
    SAMPLE_BBOX,
    STAC_RESPONSE_LANDSAT,
    STAC_RESPONSE_S1,
    STAC_RESPONSE_S2,
    TOKEN_RESPONSE,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_token():
    with patch("app.auth.cdse.cdse_auth.get_token", new_callable=AsyncMock) as m:
        m.return_value = "mock-token"
        yield m


# ─── POST /api/search ─────────────────────────────────────────────────────────


@respx.mock
def test_search_sentinel2(client):
    """Deve retornar cenas S2 ordenadas por cloudCover crescente."""
    respx.post("https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search").mock(
        return_value=httpx.Response(200, json=STAC_RESPONSE_S2)
    )

    resp = client.post(
        "/api/search",
        json={
            "bbox": SAMPLE_BBOX,
            "start": "2024-01-01",
            "end": "2024-01-31",
            "maxCloudCover": 80,
            "satelliteType": "sentinel2",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "scenes" in data
    scenes = data["scenes"]
    assert len(scenes) == 2
    # Ordenadas por cloudCover crescente
    assert scenes[0]["cloudCover"] <= scenes[1]["cloudCover"]
    assert scenes[0]["satelliteType"] == "sentinel2"
    assert scenes[0]["id"] == "S2A_MSIL2A_20240115T130259_N0510_R090_T22KCD"


@respx.mock
def test_search_sentinel1_sorted_by_date(client):
    """Deve retornar cenas S1 ordenadas por data decrescente."""
    respx.post("https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search").mock(
        return_value=httpx.Response(200, json=STAC_RESPONSE_S1)
    )

    resp = client.post(
        "/api/search",
        json={
            "bbox": SAMPLE_BBOX,
            "start": "2024-01-01",
            "end": "2024-01-31",
            "maxCloudCover": 80,
            "satelliteType": "sentinel1",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    scenes = data["scenes"]
    assert len(scenes) == 1
    assert scenes[0]["satelliteType"] == "sentinel1"
    assert scenes[0]["cloudCover"] == 0.0  # ausente → 0


@respx.mock
def test_search_missing_thumbnail(client):
    """Cenas sem thumbnail devem ter thumbnailHref = null."""
    no_thumb = {
        "type": "FeatureCollection",
        "features": [
            {
                "id": "S1A_IW_GRDH_20240120",
                "properties": {"datetime": "2024-01-20T09:00:00Z"},
                "assets": {},
            }
        ],
    }
    respx.post("https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search").mock(
        return_value=httpx.Response(200, json=no_thumb)
    )

    resp = client.post(
        "/api/search",
        json={
            "bbox": SAMPLE_BBOX,
            "start": "2024-01-01",
            "end": "2024-01-31",
            "satelliteType": "sentinel1",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["scenes"][0]["thumbnailHref"] is None


def test_search_invalid_bbox(client):
    """Deve retornar 422 para bbox com menos de 4 elementos."""
    resp = client.post(
        "/api/search",
        json={
            "bbox": [-47.0, -23.0],  # inválido
            "start": "2024-01-01",
            "end": "2024-01-31",
            "satelliteType": "sentinel2",
        },
    )
    assert resp.status_code == 422


def test_search_invalid_satellite_type(client):
    """Deve retornar 422 para satelliteType inválido."""
    resp = client.post(
        "/api/search",
        json={
            "bbox": SAMPLE_BBOX,
            "start": "2024-01-01",
            "end": "2024-01-31",
            "satelliteType": "cbers4a",  # não suportado aqui
        },
    )
    assert resp.status_code == 422


@respx.mock
def test_search_stac_error_returns_502(client):
    """Deve retornar 502 quando o STAC retornar erro."""
    respx.post("https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    resp = client.post(
        "/api/search",
        json={
            "bbox": SAMPLE_BBOX,
            "start": "2024-01-01",
            "end": "2024-01-31",
            "satelliteType": "sentinel2",
        },
    )
    assert resp.status_code == 502


# ─── POST /api/search/optical ─────────────────────────────────────────────────


@respx.mock
def test_search_optical_merges_s2_and_landsat(client):
    """Deve mesclar S2 e Landsat ordenados por data decrescente."""
    # Ambas as chamadas STAC são mockadas para o mesmo endpoint
    stac_url = "https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search"
    call_count = 0

    def stac_handler(request):
        nonlocal call_count
        call_count += 1
        body = request.content.decode()
        if "sentinel-2-l2a" in body:
            return httpx.Response(200, json=STAC_RESPONSE_S2)
        return httpx.Response(200, json=STAC_RESPONSE_LANDSAT)

    respx.post(stac_url).mock(side_effect=stac_handler)

    resp = client.post(
        "/api/search/optical",
        json={
            "bbox": SAMPLE_BBOX,
            "start": "2024-01-01",
            "end": "2024-01-31",
            "maxCloudCover": 80,
        },
    )

    assert resp.status_code == 200
    scenes = resp.json()["scenes"]
    # 2 S2 + 1 Landsat = 3 cenas
    assert len(scenes) == 3
    # Ordenadas por data decrescente
    dates = [s["date"] for s in scenes]
    assert dates == sorted(dates, reverse=True)


@respx.mock
def test_search_optical_landsat_failure_returns_s2_only(client):
    """Se o Landsat falhar, deve retornar apenas cenas S2."""
    stac_url = "https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search"

    def stac_handler(request):
        body = request.content.decode()
        if "sentinel-2-l2a" in body:
            return httpx.Response(200, json=STAC_RESPONSE_S2)
        # Landsat falha
        return httpx.Response(503, text="Service Unavailable")

    respx.post(stac_url).mock(side_effect=stac_handler)

    resp = client.post(
        "/api/search/optical",
        json={
            "bbox": SAMPLE_BBOX,
            "start": "2024-01-01",
            "end": "2024-01-31",
        },
    )

    assert resp.status_code == 200
    scenes = resp.json()["scenes"]
    assert len(scenes) == 2
    assert all(s["satelliteType"] == "sentinel2" for s in scenes)
