"""
Rotas de busca de cenas via catálogo STAC do CDSE.

POST /api/search          — busca por tipo de satélite
POST /api/search/optical  — busca mesclada Sentinel-2 + Landsat
"""

from fastapi import APIRouter, HTTPException

from app.models.schemas import OpticalSearchRequest, ScenesResponse, SearchRequest
from app.services import stac

router = APIRouter()


@router.post("/search", response_model=ScenesResponse, summary="Busca por tipo de satélite")
async def search(req: SearchRequest) -> ScenesResponse:
    """
    Consulta o catálogo STAC do CDSE para o satélite especificado.

    - **sentinel2**: ordenado por cobertura de nuvens (menor primeiro)
    - **landsat**: ordenado por cobertura de nuvens (menor primeiro)
    - **sentinel1**: ordenado por data (mais recente primeiro)
    """
    try:
        scenes = await stac.search_scenes(
            bbox=req.bbox,
            start=req.start,
            end=req.end,
            satellite_type=req.satelliteType,
            max_cloud_cover=req.maxCloudCover,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar STAC: {exc}") from exc

    return ScenesResponse(scenes=scenes)


@router.post(
    "/search/optical",
    response_model=ScenesResponse,
    summary="Busca óptica mesclada (Sentinel-2 + Landsat)",
)
async def search_optical(req: OpticalSearchRequest) -> ScenesResponse:
    """
    Realiza duas buscas em paralelo (Sentinel-2 e Landsat) e mescla os resultados.

    Ordenação: data decrescente; dentro do mesmo dia, menor cobertura de nuvens primeiro.
    Se o Landsat falhar (coleção indisponível), retorna apenas cenas Sentinel-2.
    """
    try:
        scenes = await stac.search_optical(
            bbox=req.bbox,
            start=req.start,
            end=req.end,
            max_cloud_cover=req.maxCloudCover,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Erro ao consultar STAC óptico: {exc}"
        ) from exc

    return ScenesResponse(scenes=scenes)
