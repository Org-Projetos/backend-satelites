"""Testes para o endpoint POST /api/hasData."""

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


@respx.mock
def test_has_data_true_for_large_png(client):
    """Deve retornar true quando o PNG de resposta for grande (> threshold)."""
    large_png = make_png_bytes(large=True)
    respx.post(PROCESS_URL).mock(
        return_value=httpx.Response(200, content=large_png)
    )

    resp = client.post(
        "/api/hasData",
        json={
            "bbox": SAMPLE_BBOX,
            "date": "2024-01-15",
            "satelliteType": "sentinel2",
        },
    )

    assert resp.status_code == 200
    assert resp.json() is True


@respx.mock
def test_has_data_false_for_small_png(client):
    """Deve retornar false quando o PNG de resposta for pequeno (≤ threshold)."""
    small_png = make_png_bytes(large=False)
    assert len(small_png) <= 1500, "PNG de teste deve ser pequeno"

    respx.post(PROCESS_URL).mock(
        return_value=httpx.Response(200, content=small_png)
    )

    resp = client.post(
        "/api/hasData",
        json={
            "bbox": SAMPLE_BBOX,
            "date": "2024-01-15",
            "satelliteType": "sentinel2",
        },
    )

    assert resp.status_code == 200
    assert resp.json() is False


@respx.mock
def test_has_data_false_on_process_api_error(client):
    """Deve retornar false quando a Process API retornar erro."""
    respx.post(PROCESS_URL).mock(return_value=httpx.Response(500, text="Error"))

    resp = client.post(
        "/api/hasData",
        json={
            "bbox": SAMPLE_BBOX,
            "date": "2024-01-15",
            "satelliteType": "sentinel2",
        },
    )

    assert resp.status_code == 200
    assert resp.json() is False


@respx.mock
def test_has_data_sentinel1(client):
    """Deve funcionar corretamente para Sentinel-1."""
    large_png = make_png_bytes(large=True)
    respx.post(PROCESS_URL).mock(
        return_value=httpx.Response(200, content=large_png)
    )

    resp = client.post(
        "/api/hasData",
        json={
            "bbox": SAMPLE_BBOX,
            "date": "2024-01-15",
            "satelliteType": "sentinel1",
        },
    )

    assert resp.status_code == 200
    assert resp.json() is True


@respx.mock
def test_has_data_landsat(client):
    """Deve funcionar corretamente para Landsat."""
    large_png = make_png_bytes(large=True)
    respx.post(PROCESS_URL).mock(
        return_value=httpx.Response(200, content=large_png)
    )

    resp = client.post(
        "/api/hasData",
        json={
            "bbox": SAMPLE_BBOX,
            "date": "2024-01-15",
            "satelliteType": "landsat",
        },
    )

    assert resp.status_code == 200
    assert resp.json() is True


def test_has_data_invalid_satellite_type(client):
    """Deve retornar 422 para satelliteType inválido."""
    resp = client.post(
        "/api/hasData",
        json={
            "bbox": SAMPLE_BBOX,
            "date": "2024-01-15",
            "satelliteType": "invalid",
        },
    )
    assert resp.status_code == 422


def test_has_data_missing_bbox(client):
    """Deve retornar 422 quando bbox não for fornecida."""
    resp = client.post(
        "/api/hasData",
        json={
            "date": "2024-01-15",
            "satelliteType": "sentinel2",
        },
    )
    assert resp.status_code == 422
