"""
Schemas de entrada/saída para análises agendadas.
"""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Literal

# Tipos compartilhados
Resolution = Literal["low", "medium", "high"]


class AnalysisScheduleCreate(BaseModel):
    """Schema para criar uma nova análise agendada baseada em uma Área."""
    
    area_id: str = Field(..., description="ID da Área para a qual criar o agendamento")
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
    """Schema de resposta para histórico de análise (comparação de 2 imagens)."""
    
    id: str
    schedule_id: str
    execution_date: datetime
    scene_recent: Optional[SelectedSceneInfo] = None  # Imagem mais recente
    scene_previous: Optional[SelectedSceneInfo] = None  # Imagem anterior (para comparação)
    analysis: str = Field(..., description="Resultado da análise comparativa (relatório em texto do GPT-4o Vision)")
    processing_time: str
    status: str  # "success", "failed"
    error_message: Optional[str] = None
    created_at: datetime


class AnalysisMetricsResponse(BaseModel):
    """Schema para dados estruturados/numéricos extraídos da análise da IA."""
    
    health_status: Literal["saudável", "atenção", "crítico"] = Field(
        ..., 
        description="Classificação geral da saúde da vegetação"
    )
    health_score: float = Field(
        ..., 
        ge=0, 
        le=100, 
        description="Score de saúde geral (0-100)"
    )
    vegetation_coverage_percent: float = Field(
        default=None,
        description="% da área com cobertura vegetal"
    )
    problem_areas_percent: float = Field(
        default=None,
        description="% da área com problemas identificados"
    )
    trend: Literal["progredindo", "regredindo", "estável"] = Field(
        ..., 
        description="Tendência de mudança em relação à data anterior"
    )
    trend_magnitude: float = Field(
        ge=-100, 
        le=100, 
        description="Magnitude da mudança em % (negativo=piorou, positivo=melhorou)"
    )
    key_findings: list[str] = Field(
        default=[],
        description="Pontos principais extraídos da análise"
    )
    recommendations: list[str] = Field(
        default=[],
        description="Recomendações baseadas na análise"
    )
