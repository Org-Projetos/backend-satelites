"""
Modelos Pydantic para request/response da API.
"""

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field

# ─── Tipos compartilhados ────────────────────────────────────────────────────

BBox = Annotated[
    list[float],
    Field(min_length=4, max_length=4, description="[west, south, east, north] em WGS84"),
]

SatelliteType = Literal["sentinel2", "landsat", "sentinel1"]
OpticalSatelliteType = Literal["sentinel2", "landsat"]
VisualTypeOptical = Literal["truecolor", "falsecolor", "ndvi", "evi", "swir", "ndmi", "ndwi"]
VisualTypeS1 = Literal["vv", "vh", "rgb", "rvi"]
Resolution = Literal["low", "medium", "high", "native"]


# ─── Busca de cenas ──────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    bbox: BBox
    start: str = Field(..., description="Data inicial ISO 8601 (YYYY-MM-DD ou YYYY-MM-DDTHH:MM:SSZ)")
    end: str = Field(..., description="Data final ISO 8601")
    maxCloudCover: float = Field(80, ge=0, le=100, description="% máxima de nuvens (0-100)")
    satelliteType: SatelliteType


class OpticalSearchRequest(BaseModel):
    bbox: BBox
    start: str = Field(..., description="Data inicial ISO 8601")
    end: str = Field(..., description="Data final ISO 8601")
    maxCloudCover: float = Field(80, ge=0, le=100)


class Scene(BaseModel):
    id: str
    date: str
    cloudCover: float
    thumbnailHref: Optional[str]
    satelliteType: str


class ScenesResponse(BaseModel):
    scenes: list[Scene]


# ─── HasData ─────────────────────────────────────────────────────────────────

class HasDataRequest(BaseModel):
    bbox: BBox
    date: str = Field(..., description="Data central ISO 8601 (YYYY-MM-DD)")
    satelliteType: SatelliteType


# ─── Renderização ────────────────────────────────────────────────────────────

class RenderRequest(BaseModel):
    bbox: BBox
    date: str = Field(..., description="Data ISO 8601 (YYYY-MM-DD)")
    visualType: VisualTypeOptical = "truecolor"
    resolution: Resolution = "medium"
    maxCloudCover: float = Field(30, ge=0, le=100)
    satelliteType: OpticalSatelliteType = "sentinel2"


class S1RenderRequest(BaseModel):
    bbox: BBox
    date: str = Field(..., description="Data ISO 8601 (YYYY-MM-DD)")
    visualType: VisualTypeS1 = "rgb"
    resolution: Resolution = "medium"


# ─── Cloud Cover ─────────────────────────────────────────────────────────────

class CloudCoverRequest(BaseModel):
    sceneId: str = Field(..., description="ID da cena STAC retornado pelo endpoint search")
    bbox: BBox
    date: str = Field(..., description="Data ISO 8601 da cena (YYYY-MM-DD ou datetime completo)")


class CloudCoverResponse(BaseModel):
    cloudCover: float = Field(..., description="Porcentagem de nuvens (0-100) na bbox informada")
    sceneId: str
