"""
Schemas de entrada/saída para análises agendadas.
"""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Literal

# Tipos compartilhados
Resolution = Literal["low", "medium", "high"]


class AnalysisScheduleCreate(BaseModel):
    """Schema para criar uma nova análise agendada."""
    
    bbox: list[float] = Field(..., description="Bounding box [min_lon, min_lat, max_lon, max_lat]")
    area_hectares: float = Field(..., description="Área em hectares")
    resolution: Resolution = Field(default="medium", description="Resolução: low (512px), medium (1024px), high (2048px)")
    max_cloud_cover: float = Field(default=30, description="Cobertura máxima de nuvens em %")
    is_active: bool = Field(default=True, description="Se a análise está ativa")


class AnalysisScheduleUpdate(BaseModel):
    """Schema para atualizar uma análise agendada."""
    
    bbox: Optional[list[float]] = None
    area_hectares: Optional[float] = None
    resolution: Optional[Resolution] = None
    max_cloud_cover: Optional[float] = None
    is_active: Optional[bool] = None


class AnalysisScheduleResponse(BaseModel):
    """Schema de resposta para uma análise agendada."""
    
    id: str
    user_id: str
    bbox: list[float]
    area_hectares: float
    resolution: Resolution
    max_cloud_cover: float
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SelectedSceneInfo(BaseModel):
    """Informações da cena selecionada."""
    
    id: str
    date: str
    cloud_cover: float
    satellite_type: str


class AnalysisHistoryResponse(BaseModel):
    """Schema de resposta para histórico de análise."""
    
    id: str
    schedule_id: str
    execution_date: datetime
    scene: SelectedSceneInfo
    images: dict[str, str] = Field(..., description="Mapeamento de tipo para URL: {'truecolor': 'url', 'ndvi': 'url'}")
    analysis: dict = Field(..., description="Resultado da análise JSON")
    processing_time: str
    status: str  # "success", "failed"
    error_message: Optional[str] = None
    created_at: datetime
