"""
Gerenciamento de token OAuth2 (client_credentials) para o CDSE.

O token é cacheado em memória e renovado automaticamente com uma margem
de segurança configurável (padrão: 2 minutos antes de expirar).
"""

import asyncio
import time
from typing import Optional

import httpx

from app.config import Settings, get_settings


class CDSEAuth:
    """Obtém e cacheia o token de acesso do Copernicus Data Space."""

    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._expires_at: float = 0.0
        self._lock: Optional[asyncio.Lock] = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def get_token(self, settings: Optional[Settings] = None) -> str:
        """Retorna um token válido, renovando se necessário."""
        if settings is None:
            settings = get_settings()

        async with self._get_lock():
            now = time.monotonic()
            if self._token and now < self._expires_at:
                return self._token

            token, expires_in = await self._fetch_token(settings)
            self._token = token
            self._expires_at = now + expires_in - settings.token_renewal_margin_seconds
            return self._token

    async def _fetch_token(self, settings: Settings) -> tuple[str, int]:
        """Faz o POST ao endpoint de token CDSE e retorna (access_token, expires_in)."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                settings.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.cdse_client_id,
                    "client_secret": settings.cdse_client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

        return data["access_token"], int(data.get("expires_in", 3600))

    def invalidate(self) -> None:
        """Invalida o token cacheado (útil em testes ou após 401)."""
        self._token = None
        self._expires_at = 0.0


# Instância global compartilhada pela aplicação
cdse_auth = CDSEAuth()
