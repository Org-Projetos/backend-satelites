"""
Proxy de thumbnail com autenticação CDSE.

GET /api/thumbnail?href=<url>
"""

from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.auth.cdse import cdse_auth
from app.config import get_settings

router = APIRouter()


def _is_allowed_domain(href: str, allowed_domains: list[str]) -> bool:
    """Verifica se o domínio do href está na lista de permitidos (SSRF protection)."""
    try:
        parsed = urlparse(href)
        hostname = parsed.hostname or ""
        return any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in allowed_domains
        )
    except Exception:
        return False


@router.get(
    "/thumbnail",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {}, "image/png": {}}}},
    summary="Proxy de thumbnail com autenticação CDSE",
)
async def get_thumbnail(
    href: str = Query(..., description="URL do thumbnail CDSE (assets.thumbnail.href)"),
) -> Response:
    """
    Faz um GET autenticado no `href` informado e devolve os bytes da imagem.

    Protegido contra SSRF: aceita apenas domínios configurados em
    `ALLOWED_THUMBNAIL_DOMAINS` (padrão: `*.dataspace.copernicus.eu`).
    """
    settings = get_settings()

    if not _is_allowed_domain(href, settings.allowed_thumbnail_domains):
        raise HTTPException(
            status_code=400,
            detail=(
                "Domínio do href não é permitido. "
                f"Domínios aceitos: {settings.allowed_thumbnail_domains}"
            ),
        )

    token = await cdse_auth.get_token(settings)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            href,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
            follow_redirects=True,
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"CDSE retornou {resp.status_code} ao obter thumbnail",
        )

    content_type = resp.headers.get("content-type", "image/jpeg")
    return Response(content=resp.content, media_type=content_type)
