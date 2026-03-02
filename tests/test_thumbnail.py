"""Testes para o endpoint GET /api/thumbnail (proxy com auth CDSE)."""

import pytest
import respx
import httpx
from unittest.mock import AsyncMock, patch


THUMBNAIL_URL = "https://sh.dataspace.copernicus.eu/thumbnails/test.jpg"
BLOCKED_URL = "https://evil.com/steal.jpg"
LOCAL_URL = "http://localhost/internal"


@pytest.fixture(autouse=True)
def mock_token():
    with patch("app.auth.cdse.cdse_auth.get_token", new_callable=AsyncMock) as m:
        m.return_value = "mock-token"
        yield m


@respx.mock
def test_thumbnail_success(client):
    """Deve retornar a imagem com o Content-Type correto."""
    fake_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # header JPEG mínimo
    respx.get(THUMBNAIL_URL).mock(
        return_value=httpx.Response(
            200,
            content=fake_jpeg,
            headers={"content-type": "image/jpeg"},
        )
    )

    resp = client.get(f"/api/thumbnail?href={THUMBNAIL_URL}")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.content == fake_jpeg


@respx.mock
def test_thumbnail_sends_bearer_token(client):
    """Deve enviar o header Authorization com o token CDSE."""
    received_headers = {}

    def capture(request):
        received_headers.update(dict(request.headers))
        return httpx.Response(200, content=b"fake-image", headers={"content-type": "image/png"})

    respx.get(THUMBNAIL_URL).mock(side_effect=capture)

    resp = client.get(f"/api/thumbnail?href={THUMBNAIL_URL}")

    assert resp.status_code == 200
    assert received_headers.get("authorization") == "Bearer mock-token"


def test_thumbnail_blocked_domain(client):
    """Deve retornar 400 para domínio não autorizado (SSRF protection)."""
    resp = client.get(f"/api/thumbnail?href={BLOCKED_URL}")

    assert resp.status_code == 400
    assert "Domínio" in resp.json()["detail"]


def test_thumbnail_localhost_blocked(client):
    """Deve bloquear tentativa de SSRF para localhost."""
    resp = client.get(f"/api/thumbnail?href={LOCAL_URL}")

    assert resp.status_code == 400


@respx.mock
def test_thumbnail_cdse_404_propagates(client):
    """Deve propagar o status 404 do CDSE."""
    respx.get(THUMBNAIL_URL).mock(return_value=httpx.Response(404))

    resp = client.get(f"/api/thumbnail?href={THUMBNAIL_URL}")

    assert resp.status_code == 404


def test_thumbnail_missing_href(client):
    """Deve retornar 422 quando href não for fornecido."""
    resp = client.get("/api/thumbnail")

    assert resp.status_code == 422


@respx.mock
def test_thumbnail_subdomain_allowed(client):
    """Deve aceitar subdomínios de dataspace.copernicus.eu."""
    sub_url = "https://sh.dataspace.copernicus.eu/thumbnails/other.jpg"
    fake_img = b"PNG_DATA" * 50

    respx.get(sub_url).mock(
        return_value=httpx.Response(
            200, content=fake_img, headers={"content-type": "image/png"}
        )
    )

    resp = client.get(f"/api/thumbnail?href={sub_url}")

    assert resp.status_code == 200
