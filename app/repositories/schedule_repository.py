"""
Repository para análises agendadas (CRUD).
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from sqlalchemy import select, update, delete, and_
from sqlalchemy.engine import Engine

from app.db import analysis_schedules_table, analysis_history_table, get_engine
from app.models.schedules_schemas import (
    AnalysisScheduleCreate,
    AnalysisScheduleResponse,
    AnalysisHistoryResponse,
)


class AnalysisScheduleRepository:
    """Repositório para gerenciar análises agendadas."""

    def __init__(self, engine: Engine | None = None):
        self.engine = engine or get_engine()

    def create(self, user_id: str, schedule: AnalysisScheduleCreate) -> AnalysisScheduleResponse:
        """Cria uma nova análise agendada."""
        schedule_id = str(uuid4())
        now = datetime.utcnow()

        stmt = analysis_schedules_table.insert().values(
            id=schedule_id,
            user_id=user_id,
            bbox=schedule.bbox,
            area_hectares=schedule.area_hectares,
            resolution=schedule.resolution,
            max_cloud_cover=schedule.max_cloud_cover,
            is_active=schedule.is_active,
            created_at=now,
            updated_at=now,
        )

        with self.engine.connect() as conn:
            conn.execute(stmt)
            conn.commit()

        return self.get(schedule_id)

    def get(self, schedule_id: str) -> AnalysisScheduleResponse | None:
        """Retorna uma análise agendada por ID."""
        stmt = select(analysis_schedules_table).where(
            analysis_schedules_table.c.id == schedule_id
        )

        with self.engine.connect() as conn:
            row = conn.execute(stmt).first()

        if not row:
            return None

        return self._row_to_response(row)

    def list_by_user(self, user_id: str) -> list[AnalysisScheduleResponse]:
        """Lista todas as análises agendadas de um usuário."""
        stmt = select(analysis_schedules_table).where(
            analysis_schedules_table.c.user_id == user_id
        )

        with self.engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()

        return [self._row_to_response(row) for row in rows]

    def list_active(self) -> list[AnalysisScheduleResponse]:
        """Lista todas as análises agendadas ativas (para jobs)."""
        stmt = select(analysis_schedules_table).where(
            analysis_schedules_table.c.is_active == True
        )

        with self.engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()

        return [self._row_to_response(row) for row in rows]

    def update(self, schedule_id: str, user_id: str, updates: dict) -> AnalysisScheduleResponse | None:
        """Atualiza uma análise agendada (valida ownership)."""
        # Verifica se pertence ao usuário
        existing = self.get(schedule_id)
        if not existing or existing.user_id != user_id:
            return None

        updates["updated_at"] = datetime.utcnow()

        stmt = (
            update(analysis_schedules_table)
            .where(analysis_schedules_table.c.id == schedule_id)
            .values(**updates)
        )

        with self.engine.connect() as conn:
            conn.execute(stmt)
            conn.commit()

        return self.get(schedule_id)

    def delete(self, schedule_id: str, user_id: str) -> bool:
        """Deleta uma análise agendada (valida ownership)."""
        # Verifica se pertence ao usuário
        existing = self.get(schedule_id)
        if not existing or existing.user_id != user_id:
            return False

        stmt = delete(analysis_schedules_table).where(
            analysis_schedules_table.c.id == schedule_id
        )

        with self.engine.connect() as conn:
            conn.execute(stmt)
            conn.commit()

        return True

    @staticmethod
    def _row_to_response(row) -> AnalysisScheduleResponse:
        """Converte uma linha do banco em resposta."""
        return AnalysisScheduleResponse(
            id=row.id,
            user_id=row.user_id,
            bbox=row.bbox,
            area_hectares=row.area_hectares,
            resolution=row.resolution,
            max_cloud_cover=row.max_cloud_cover,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class AnalysisHistoryRepository:
    """Repositório para gerenciar histórico de análises."""

    def __init__(self, engine: Engine | None = None):
        self.engine = engine or get_engine()

    def create(
        self,
        schedule_id: str,
        execution_date: datetime,
        scene_id: str,
        scene_date: str,
        scene_cloud_cover: float,
        scene_satellite_type: str,
        images: dict,
        analysis: dict,
        processing_time: str,
        status: str = "success",
        error_message: str | None = None,
    ) -> str:
        """Cria um novo registro de histórico de análise. Retorna o ID."""
        history_id = str(uuid4())

        stmt = analysis_history_table.insert().values(
            id=history_id,
            schedule_id=schedule_id,
            execution_date=execution_date,
            scene_id=scene_id,
            scene_date=scene_date,
            scene_cloud_cover=scene_cloud_cover,
            scene_satellite_type=scene_satellite_type,
            images=images,
            analysis=analysis,
            processing_time=processing_time,
            status=status,
            error_message=error_message,
            created_at=datetime.utcnow(),
        )

        with self.engine.connect() as conn:
            conn.execute(stmt)
            conn.commit()

        return history_id

    def get_latest_by_schedule(self, schedule_id: str) -> AnalysisHistoryResponse | None:
        """Retorna o histórico mais recente de uma análise agendada."""
        stmt = (
            select(analysis_history_table)
            .where(analysis_history_table.c.schedule_id == schedule_id)
            .order_by(analysis_history_table.c.created_at.desc())
            .limit(1)
        )

        with self.engine.connect() as conn:
            row = conn.execute(stmt).first()

        if not row:
            return None

        return self._row_to_response(row)

    def get_latest_n_by_schedule(self, schedule_id: str, n: int = 2) -> list[AnalysisHistoryResponse]:
        """Retorna os N históricos mais recentes de uma análise agendada."""
        stmt = (
            select(analysis_history_table)
            .where(analysis_history_table.c.schedule_id == schedule_id)
            .order_by(analysis_history_table.c.created_at.desc())
            .limit(n)
        )

        with self.engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()

        return [self._row_to_response(row) for row in rows]

    @staticmethod
    def _row_to_response(row) -> AnalysisHistoryResponse:
        """Converte uma linha do banco em resposta."""
        from app.models.schedules_schemas import SelectedSceneInfo

        # Se a análise falhou, scene_id pode ser None
        scene_info = None
        if row.scene_id:
            scene_info = SelectedSceneInfo(
                id=row.scene_id,
                date=row.scene_date or "",
                cloud_cover=row.scene_cloud_cover or 0.0,
                satellite_type=row.scene_satellite_type or "unknown",
            )

        return AnalysisHistoryResponse(
            id=row.id,
            schedule_id=row.schedule_id,
            execution_date=row.execution_date,
            scene=scene_info,
            images=row.images or {},
            analysis=row.analysis or "",
            processing_time=row.processing_time,
            status=row.status,
            error_message=row.error_message,
            created_at=row.created_at,
        )


# Singletons globais
_schedule_repo: AnalysisScheduleRepository | None = None
_history_repo: AnalysisHistoryRepository | None = None


def get_schedule_repository() -> AnalysisScheduleRepository:
    """Retorna a instância global do repositório de agendamentos."""
    global _schedule_repo
    if _schedule_repo is None:
        _schedule_repo = AnalysisScheduleRepository()
    return _schedule_repo


def get_history_repository() -> AnalysisHistoryRepository:
    """Retorna a instância global do repositório de histórico."""
    global _history_repo
    if _history_repo is None:
        _history_repo = AnalysisHistoryRepository()
    return _history_repo
