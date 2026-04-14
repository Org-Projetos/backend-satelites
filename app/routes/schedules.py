"""
Endpoints para gerenciar análises agendadas e seu histórico.

GET  /schedules              → listar minhas análises agendadas
POST /schedules              → criar nova análise agendada
GET  /schedules/{id}         → ver detalhes de uma análise
PATCH /schedules/{id}        → editar uma análise
DELETE /schedules/{id}       → deletar uma análise
GET  /schedules/{id}/history → ver histórico (últimas 2)
POST /schedules/test/run     → (TESTE) forçar execução do scheduler agora
"""

import asyncio
import threading
from fastapi import APIRouter, Depends, HTTPException, status
from app.auth.jwt_auth import get_current_user
from app.auth.users import User, user_store
from app.models.schedules_schemas import (
    AnalysisScheduleCreate,
    AnalysisScheduleUpdate,
    AnalysisScheduleResponse,
    AnalysisHistoryResponse,
)
from app.repositories.schedule_repository import (
    get_schedule_repository,
    get_history_repository,
)
from app.scheduler import get_scheduler

router = APIRouter(prefix="/schedules", tags=["Análises Agendadas"])


@router.get("", response_model=list[AnalysisScheduleResponse])
async def list_schedules(current_user: User = Depends(get_current_user)):
    """Lista todas as análises agendadas do usuário autenticado."""
    repo = get_schedule_repository()
    schedules = repo.list_by_user(current_user.username)
    return schedules


@router.post(
    "",
    response_model=AnalysisScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar análise agendada",
)
async def create_schedule(
    body: AnalysisScheduleCreate,
    current_user: User = Depends(get_current_user),
):
    """Cria uma nova análise agendada semanal e executa a primeira análise imediatamente."""
    repo = get_schedule_repository()
    schedule = repo.create(current_user.username, body)
    
    # 🚀 Dispara análise inicial em background (não bloqueia a resposta HTTP)
    def run_initial_analysis():
        try:
            print(f"\n🚀 [NOVA ANÁLISE] Iniciando primeira análise para schedule {schedule.id}...")
            scheduler = get_scheduler()
            asyncio.run(scheduler._process_schedule(schedule))
            print(f"✅ [NOVA ANÁLISE] Primeira análise concluída para {schedule.id}")
        except Exception as e:
            print(f"❌ [NOVA ANÁLISE] Erro na primeira análise: {e}")
            import traceback
            traceback.print_exc()
    
    # Inicia em thread separada para não bloquear a resposta HTTP
    thread = threading.Thread(target=run_initial_analysis, daemon=True)
    thread.start()
    
    return schedule


@router.get("/{schedule_id}", response_model=AnalysisScheduleResponse)
async def get_schedule(
    schedule_id: str,
    current_user: User = Depends(get_current_user),
):
    """Retorna detalhes de uma análise agendada."""
    repo = get_schedule_repository()
    schedule = repo.get(schedule_id)

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Análise não encontrada",
        )

    if schedule.user_id != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para acessar esta análise",
        )

    return schedule


@router.patch("/{schedule_id}", response_model=AnalysisScheduleResponse)
async def update_schedule(
    schedule_id: str,
    body: AnalysisScheduleUpdate,
    current_user: User = Depends(get_current_user),
):
    """Atualiza uma análise agendada (apenas campos fornecidos)."""
    repo = get_schedule_repository()

    # Filtra apenas campos não-None
    updates = {k: v for k, v in body.model_dump().items() if v is not None}

    if not updates:
        schedule = repo.get(schedule_id)
        if not schedule:
            raise HTTPException(status_code=404, detail="Análise não encontrada")
        return schedule

    schedule = repo.update(schedule_id, current_user.username, updates)

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Análise não encontrada ou sem permissão",
        )

    return schedule


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: str,
    current_user: User = Depends(get_current_user),
):
    """Deleta uma análise agendada."""
    repo = get_schedule_repository()
    success = repo.delete(schedule_id, current_user.username)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Análise não encontrada ou sem permissão",
        )


@router.get("/{schedule_id}/history", response_model=list[AnalysisHistoryResponse])
async def get_schedule_history(
    schedule_id: str,
    current_user: User = Depends(get_current_user),
):
    """Retorna o histórico das últimas 2 análises executadas."""
    schedule_repo = get_schedule_repository()
    history_repo = get_history_repository()

    # Verifica permissão
    schedule = schedule_repo.get(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Análise não encontrada",
        )

    if schedule.user_id != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para acessar esta análise",
        )

    # Retorna histórico (últimas 2)
    history = history_repo.get_latest_n_by_schedule(schedule_id, n=2)
    return history


@router.post("/test/run", status_code=status.HTTP_200_OK, summary="[TESTE] Forçar execução do scheduler agora")
async def test_run_scheduler(current_user: User = Depends(get_current_user)):
    """
    ⚠️ APENAS PARA TESTE E DEBUG
    
    Força a execução do scheduler imediatamente, sem esperar pelo domingo.
    Requer ser admin.
    """
    # Verifica se é admin
    user = user_store.get(current_user.username)
    if not user or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem forçar execução do scheduler",
        )
    
    # Força execução (em background, não bloqueia a resposta)
    scheduler = get_scheduler()
    
    # Executa em thread separada para não bloquear a resposta HTTP
    def run_scheduler():
        try:
            print(f"\n🧪 [TESTE] Forçando execução do scheduler via endpoint...")
            scheduler._run_weekly_analyses()
            print(f"🧪 [TESTE] Execução do scheduler finalizada!")
        except Exception as e:
            print(f"❌ [TESTE] Erro ao executar scheduler: {e}")
            import traceback
            traceback.print_exc()
    
    # Inicia em thread separada
    thread = threading.Thread(target=run_scheduler, daemon=True)
    thread.start()
    
    return {
        "status": "scheduled",
        "message": "Scheduler iniciado em background",
        "note": "Verifique os logs do container para detalhes em tempo real"
    }
