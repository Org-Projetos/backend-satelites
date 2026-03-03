"""
Rotas de renderização de imagens.

POST /api/render     — imagem óptica (Sentinel-2 / Landsat / CBERS-4A) → PNG
POST /api/render/s1  — imagem SAR Sentinel-1 → PNG
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.config import get_settings
from app.models.schemas import RenderRequest, S1RenderRequest
from app.services import process_api, tiler

router = APIRouter()


@router.post(
    "/render",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
    summary="Renderiza imagem óptica (Sentinel-2, Landsat ou CBERS-4A)",
)
async def render_optical(req: RenderRequest) -> Response:
    """
    Retorna um PNG renderizado para a bbox e data informadas.

    - **satelliteType**: `sentinel2` | `landsat` → Process API CDSE;
      `cbers4a` → tiler (STAC + COG via rio-tiler)
    - **visualType**: truecolor | falsecolor | ndvi | evi | swir | ndmi | ndwi
      (evi / swir / ndmi / ndwi não disponíveis para cbers4a)
    - **resolution**: low (512px) | medium (1024px) | high (2048px) | native (~10m/px)
    """
    try:
        if req.satelliteType == "cbers4a":
            png_bytes = await tiler.render_cbers4a(
                bbox=req.bbox,
                date=req.date,
                visual_type=req.visualType,
                resolution=req.resolution,
            )
        else:
            png_bytes = await process_api.render_optical(
                bbox=req.bbox,
                date=req.date,
                visual_type=req.visualType,
                resolution=req.resolution,
                max_cloud_cover=req.maxCloudCover,
                satellite_type=req.satelliteType,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Erro ao renderizar imagem: {exc}"
        ) from exc

    settings = get_settings()
    headers: dict[str, str] = {}
    if settings.image_cache_enabled:
        headers["Cache-Control"] = f"public, max-age={settings.image_cache_ttl_seconds}"

    return Response(content=png_bytes, media_type="image/png", headers=headers)


@router.post(
    "/render/s1",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
    summary="Renderiza imagem SAR Sentinel-1",
)
async def render_sentinel1(req: S1RenderRequest) -> Response:
    """
    Chama a Process API do CDSE para dados SAR Sentinel-1 GRD e retorna PNG.

    - **visualType**: vv | vh | rgb | rvi
    - **resolution**: low | medium | high | native
    """
    try:
        png_bytes = await process_api.render_sentinel1(
            bbox=req.bbox,
            date=req.date,
            visual_type=req.visualType,
            resolution=req.resolution,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Erro ao renderizar imagem Sentinel-1: {exc}"
        ) from exc

    settings = get_settings()
    headers: dict[str, str] = {}
    if settings.image_cache_enabled:
        headers["Cache-Control"] = f"public, max-age={settings.image_cache_ttl_seconds}"

    return Response(content=png_bytes, media_type="image/png", headers=headers)
