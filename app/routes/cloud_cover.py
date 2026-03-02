"""
Endpoint de cobertura de nuvens na bbox do usuário (melhoria: seção 9 da spec).

POST /api/cloudCover — porcentagem de nuvens na bbox (SCL Sentinel-2)
GET  /api/cloudCover — idem via query params
"""

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import CloudCoverRequest, CloudCoverResponse
from app.services import process_api

router = APIRouter()


@router.post(
    "/cloudCover",
    response_model=CloudCoverResponse,
    summary="Porcentagem de nuvens na bbox (Sentinel-2 SCL)",
)
async def cloud_cover_post(req: CloudCoverRequest) -> CloudCoverResponse:
    """
    Calcula a porcentagem de cobertura de nuvens **dentro da bbox informada**
    para uma cena Sentinel-2 L2A, usando a banda SCL (Scene Classification Layer).

    Valores SCL considerados nuvem: **8** (Cloud medium probability) e **9**
    (Cloud high probability).

    Retorna um valor de 0–100 representando a % de pixels com nuvem na bbox.
    """
    try:
        cc = await process_api.cloud_cover_in_bbox(
            bbox=req.bbox,
            date=req.date,
            scene_id=req.sceneId,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Erro ao calcular cobertura de nuvens: {exc}"
        ) from exc

    return CloudCoverResponse(cloudCover=cc, sceneId=req.sceneId)


@router.get(
    "/cloudCover",
    response_model=CloudCoverResponse,
    summary="Porcentagem de nuvens na bbox via GET (query params)",
)
async def cloud_cover_get(
    scene_id: str = Query(..., alias="sceneId", description="ID da cena STAC"),
    bbox: str = Query(
        ...,
        description="Bbox em formato 'west,south,east,north'",
        example="-47.0,-23.0,-46.5,-22.5",
    ),
    date: str = Query(..., description="Data ISO 8601 (YYYY-MM-DD) da cena"),
) -> CloudCoverResponse:
    """
    Versão GET do endpoint de cobertura de nuvens (conveniente para uso direto em browser).
    """
    try:
        bbox_list = [float(v) for v in bbox.split(",")]
        if len(bbox_list) != 4:
            raise ValueError("bbox deve ter 4 valores")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"bbox inválida: {exc}") from exc

    try:
        cc = await process_api.cloud_cover_in_bbox(
            bbox=bbox_list,
            date=date,
            scene_id=scene_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Erro ao calcular cobertura de nuvens: {exc}"
        ) from exc

    return CloudCoverResponse(cloudCover=cc, sceneId=scene_id)
