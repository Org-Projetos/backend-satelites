"""
Rotas de renderização de imagens via Sentinel Hub Process API.

POST /api/render     — imagem óptica (Sentinel-2 / Landsat) → PNG
POST /api/render/s1  — imagem SAR Sentinel-1 → PNG
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.models.schemas import RenderRequest, S1RenderRequest
from app.services import process_api

router = APIRouter()


@router.post(
    "/render",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
    summary="Renderiza imagem óptica (Sentinel-2 ou Landsat)",
)
async def render_optical(req: RenderRequest) -> Response:
    """
    Chama a Process API do CDSE e retorna um PNG renderizado para a bbox e data
    informadas.

    - **visualType**: truecolor | falsecolor | ndvi | evi | swir | ndmi | ndwi
    - **resolution**: low (512px) | medium (1024px) | high (2048px) | native (~10m/px)
    - **satelliteType**: sentinel2 | landsat
    """
    try:
        png_bytes = await process_api.render_optical(
            bbox=req.bbox,
            date=req.date,
            visual_type=req.visualType,
            resolution=req.resolution,
            max_cloud_cover=req.maxCloudCover,
            satellite_type=req.satelliteType,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Erro ao renderizar imagem óptica: {exc}"
        ) from exc

    return Response(content=png_bytes, media_type="image/png")


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

    return Response(content=png_bytes, media_type="image/png")
