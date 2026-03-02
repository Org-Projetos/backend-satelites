"""
Serviço de busca de cenas via catálogo STAC do CDSE.
"""

import asyncio

import httpx

from app.auth.cdse import cdse_auth
from app.config import get_settings
from app.models.schemas import Scene

COLLECTION_MAP = {
    "sentinel2": "sentinel-2-l2a",
    "landsat": "landsat-ot-l1",
    "sentinel1": "sentinel-1-grd",
}

CRS84 = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"


def _normalize_date(date_str: str, end_of_day: bool = False) -> str:
    """Garante que a data esteja em formato ISO 8601 com hora."""
    if "T" in date_str:
        return date_str
    suffix = "T23:59:59Z" if end_of_day else "T00:00:00Z"
    return f"{date_str}{suffix}"


def _parse_features(features: list[dict], satellite_type: str) -> list[Scene]:
    scenes: list[Scene] = []
    for f in features:
        props = f.get("properties", {})
        assets = f.get("assets", {})
        thumbnail = assets.get("thumbnail", {}).get("href") or None
        cloud_cover = props.get("eo:cloud_cover") or 0.0

        scenes.append(
            Scene(
                id=f["id"],
                date=props.get("datetime", ""),
                cloudCover=float(cloud_cover),
                thumbnailHref=thumbnail,
                satelliteType=satellite_type,
            )
        )
    return scenes


async def search_scenes(
    bbox: list[float],
    start: str,
    end: str,
    satellite_type: str,
    max_cloud_cover: float = 80,
) -> list[Scene]:
    """Busca cenas STAC para um único tipo de satélite."""
    settings = get_settings()
    token = await cdse_auth.get_token(settings)

    collection = COLLECTION_MAP[satellite_type]
    start_iso = _normalize_date(start)
    end_iso = _normalize_date(end, end_of_day=True)

    body: dict = {
        "collections": [collection],
        "bbox": bbox,
        "datetime": f"{start_iso}/{end_iso}",
        "limit": 50,
    }

    if satellite_type in ("sentinel2", "landsat"):
        body["filter"] = f"eo:cloud_cover <= {max_cloud_cover}"
        body["filter-lang"] = "cql2-text"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            settings.stac_url,
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

    scenes = _parse_features(data.get("features", []), satellite_type)

    if satellite_type in ("sentinel2", "landsat"):
        scenes.sort(key=lambda s: s.cloudCover)
    else:
        scenes.sort(key=lambda s: s.date, reverse=True)

    return scenes


async def search_optical(
    bbox: list[float],
    start: str,
    end: str,
    max_cloud_cover: float = 80,
) -> list[Scene]:
    """
    Busca óptica mesclada: Sentinel-2 + Landsat em paralelo.
    Se o Landsat falhar, devolve apenas as cenas S2.
    Ordenação: data decrescente; no mesmo dia, cloudCover crescente.
    """
    s2_task = asyncio.create_task(
        search_scenes(bbox, start, end, "sentinel2", max_cloud_cover)
    )
    landsat_task = asyncio.create_task(
        search_scenes(bbox, start, end, "landsat", max_cloud_cover)
    )

    s2_scenes, landsat_result = await asyncio.gather(s2_task, landsat_task, return_exceptions=True)

    if isinstance(s2_scenes, Exception):
        raise s2_scenes

    landsat_scenes: list[Scene] = (
        landsat_result if not isinstance(landsat_result, Exception) else []
    )

    merged = s2_scenes + landsat_scenes
    merged.sort(key=lambda s: (s.date, s.cloudCover), reverse=False)
    # Ordena: data decrescente, dentro da mesma data cloudCover crescente
    merged.sort(key=lambda s: s.date, reverse=True)
    # Estabilidade garante que dentro do mesmo dia a ordem por cloudCover seja mantida

    return merged
