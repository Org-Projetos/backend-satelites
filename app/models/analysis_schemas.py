"""
Modelos Pydantic para análise de imagens via IA.
"""

from typing import Optional

from pydantic import BaseModel, Field

from app.models.schemas import BBox, Resolution


class AIAnalysisRequest(BaseModel):
    """Request para análise de imagem via IA."""
    
    bbox: BBox
    date: str = Field(..., description="Data ISO 8601 (YYYY-MM-DD)")
    areaHectares: float = Field(..., gt=0, description="Área total em hectares")
    maxCloudCover: float = Field(20, ge=0, le=100, description="Máx. % de nuvens")
    resolution: Resolution = "medium"


class SelectedScene(BaseModel):
    """Cena selecionada para análise."""
    
    id: str
    date: str
    cloudCover: float
    satelliteType: str


class AIAnalysisResponse(BaseModel):
    """Response da análise via IA."""
    
    selectedScene: SelectedScene
    images: dict[str, str] = Field(
        description="Imagens em base64 que foram enviadas para a IA"
    )
    analysis: str = Field(description="Relatório gerado pela IA")
    metadata: dict = Field(description="Metadados do processamento")