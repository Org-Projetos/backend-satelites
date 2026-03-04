"""
Endpoint de análise de imagens via IA.

POST /api/analyze — analisa imagem de satélite usando GPT-4o Vision
"""

import time
from fastapi import APIRouter, HTTPException

from app.models.analysis_schemas import AIAnalysisRequest, AIAnalysisResponse, SelectedScene
from app.services import process_api, image_selector, ai_vision

router = APIRouter()


@router.post(
    "/analyze",
    response_model=AIAnalysisResponse,
    summary="Análise de imagem via GPT-4o Vision"
)
async def analyze_satellite_image(req: AIAnalysisRequest) -> AIAnalysisResponse:
    """
    Analisa automaticamente uma imagem de satélite usando GPT-4o Vision.
    
    Processo:
    1. Seleciona automaticamente a melhor cena disponível próxima à data informada
    2. Renderiza imagem de cor natural e NDVI
    3. Envia para GPT-4o Vision para análise agrícola
    4. Retorna relatório operacional para o produtor
    
    A análise considera:
    - Condição geral da vegetação
    - Áreas que precisam de atenção
    - Prioridade de vistoria
    - Localização aproximada de problemas
    """
    start_time = time.time()
    
    try:
        # 1. Seleção automática da melhor cena
        print(f"📐 Área requisitada: {req.bbox}")
        print(f"🔍 Resolução: {req.resolution}")
        
        scene = await image_selector.select_best_scene(
            bbox=req.bbox,
            date=req.date,
            max_cloud_cover=req.maxCloudCover
        )
        
        if not scene:
            raise HTTPException(
                status_code=404,
                detail=f"Nenhuma imagem encontrada para a data {req.date} "
                       f"na área especificada (±15 dias da data alvo)"
            )
        
        # 2. Renderização das imagens necessárias
        # Imagem de cor natural (RGB)
        truecolor_bytes = await process_api.render_optical(
            bbox=req.bbox,
            date=scene.date,
            visual_type="truecolor",
            resolution=req.resolution,
            max_cloud_cover=req.maxCloudCover,
            satellite_type="sentinel2"
        )
        
        # Imagem NDVI
        ndvi_bytes = await process_api.render_optical(
            bbox=req.bbox,
            date=scene.date,
            visual_type="ndvi",
            resolution=req.resolution,
            max_cloud_cover=req.maxCloudCover,
            satellite_type="sentinel2"
        )
        
        # 3. Conversão para base64
        print(f"📸 Renderização concluída:")
        print(f"  🎨 Truecolor: {len(truecolor_bytes)} bytes")
        print(f"  🌱 NDVI: {len(ndvi_bytes)} bytes")
        
        truecolor_b64 = ai_vision.encode_image_to_base64(truecolor_bytes)
        ndvi_b64 = ai_vision.encode_image_to_base64(ndvi_bytes)
        
        print(f"  📋 Base64 Truecolor: {len(truecolor_b64)} chars")
        print(f"  📋 Base64 NDVI: {len(ndvi_b64)} chars")
        
        # 4. Análise via GPT-4o Vision
        ai_report = await ai_vision.analyze_with_gpt4o_vision(
            truecolor_b64=truecolor_b64,
            ndvi_b64=ndvi_b64,
            area_hectares=req.areaHectares,
            date=scene.date,
            bbox=req.bbox
        )
        
        # 5. Prepara resposta
        processing_time = round(time.time() - start_time, 2)
        
        return AIAnalysisResponse(
            selectedScene=SelectedScene(
                id=scene.id,
                date=scene.date,
                cloudCover=scene.cloudCover,
                satelliteType=scene.satelliteType
            ),
            images={
                "truecolor": truecolor_b64,
                "ndvi": ndvi_b64
            },
            analysis=ai_report,
            metadata={
                "processingTime": f"{processing_time}s",
                "gptModel": "gpt-4o",
                "resolution": req.resolution,
                "areaHectares": req.areaHectares
            }
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Erro durante análise: {exc}"
        ) from exc