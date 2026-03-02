"""Testes para autenticação CDSE (cache e renovação de token)."""

import time

import pytest
import respx
import httpx

from app.auth.cdse import CDSEAuth
from app.config import Settings

SETTINGS = Settings(cdse_client_id="id", cdse_client_secret="secret")
TOKEN_URL = SETTINGS.token_url


@pytest.fixture()
def auth():
    a = CDSEAuth()
    return a


@respx.mock
@pytest.mark.asyncio
async def test_fetch_token_success(auth):
    """Deve obter token com sucesso e cacheá-lo."""
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "token-xyz", "expires_in": 3600},
        )
    )

    token = await auth.get_token(SETTINGS)
    assert token == "token-xyz"
    assert auth._token == "token-xyz"
    assert auth._expires_at > time.monotonic()


@respx.mock
@pytest.mark.asyncio
async def test_token_cached(auth):
    """Deve reutilizar o token cacheado sem chamar a API novamente."""
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "token-cached", "expires_in": 3600},
        )
    )

    t1 = await auth.get_token(SETTINGS)
    t2 = await auth.get_token(SETTINGS)

    assert t1 == t2 == "token-cached"
    # A API deve ter sido chamada apenas uma vez
    assert respx.calls.call_count == 1


@respx.mock
@pytest.mark.asyncio
async def test_token_renewed_when_expired(auth):
    """Deve renovar o token quando ele estiver expirado."""
    call_count = 0

    def side_effect(request, *_):
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            200,
            json={"access_token": f"token-{call_count}", "expires_in": 3600},
        )

    respx.post(TOKEN_URL).mock(side_effect=side_effect)

    t1 = await auth.get_token(SETTINGS)
    # Forçar expiração
    auth._expires_at = time.monotonic() - 1

    t2 = await auth.get_token(SETTINGS)

    assert t1 == "token-1"
    assert t2 == "token-2"
    assert call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_token_renewal_margin(auth):
    """Deve renovar antes de expirar (margem de segurança)."""
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "token-fresh", "expires_in": 100},
        )
    )

    await auth.get_token(SETTINGS)
    # expires_in=100, margin=120 → deve ter expirado imediatamente (já deveria renovar)
    # expires_at = now + 100 - 120 = now - 20 → menor que now
    assert auth._expires_at < time.monotonic()


@respx.mock
@pytest.mark.asyncio
async def test_token_fetch_error(auth):
    """Deve propagar exceção quando a API retorna erro."""
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(401, json={"error": "unauthorized"}))

    with pytest.raises(httpx.HTTPStatusError):
        await auth.get_token(SETTINGS)


def test_invalidate(auth):
    """Deve limpar o cache ao invalidar."""
    auth._token = "some-token"
    auth._expires_at = time.monotonic() + 3600

    auth.invalidate()

    assert auth._token is None
    assert auth._expires_at == 0.0
