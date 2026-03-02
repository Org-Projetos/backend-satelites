"""
Rota de verificação de dados.

POST /api/hasData — verifica se há dados reais na bbox/data; retorna true/false
"""

from fastapi import APIRouter, HTTPException

from app.models.schemas import HasDataRequest
from app.services import process_api

router = APIRouter()


@router.post("/hasData", summary="Verifica se há dados para a bbox e data informadas")
async def has_data(req: HasDataRequest) -> bool:
    """
    Faz uma chamada à Process API com um tile 64×64 e aplica heurística de tamanho
    de resposta para determinar se há dados reais na região.

    Retorna `true` se o PNG retornado for maior que o threshold configurado
    (`HAS_DATA_THRESHOLD_BYTES`); `false` caso contrário ou em caso de erro.
    """
    try:
        result = await process_api.check_has_data(
            bbox=req.bbox,
            date=req.date,
            satellite_type=req.satelliteType,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Erro ao verificar dados: {exc}"
        ) from exc

    return result
