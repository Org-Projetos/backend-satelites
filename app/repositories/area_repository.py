"""
Repositório de áreas geográficas e atribuições a usuários.
Apenas admins podem modificar; usuários veem só o que lhes foi atribuído.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import delete, select

from app.db import get_engine, areas_table, area_assignments_table, users_table
from app.models.area_schemas import AreaCreate, AreaResponse, AreaUpdate, UserListResponse


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _row_to_response(row, assigned_users: List[str]) -> AreaResponse:
    return AreaResponse(
        id=row.id,
        name=row.name,
        description=row.description,
        bbox=list(row.bbox),
        coordinates=row.coordinates,
        area_hectares=row.area_hectares,
        resolution=row.resolution,
        max_cloud_cover=row.max_cloud_cover,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        assigned_users=assigned_users,
    )


def _get_assigned_users(conn, area_id: str) -> List[str]:
    rows = conn.execute(
        select(area_assignments_table.c.username).where(
            area_assignments_table.c.area_id == area_id
        )
    ).fetchall()
    return [r.username for r in rows]


# ── CRUD de áreas (admin) ──────────────────────────────────────────────────────

def create_area(data: AreaCreate, created_by: str) -> AreaResponse:
    engine = get_engine()
    area_id = str(uuid.uuid4())
    now = _now()
    with engine.begin() as conn:
        conn.execute(areas_table.insert().values(
            id=area_id,
            name=data.name,
            description=data.description,
            bbox=data.bbox,
            coordinates=data.coordinates,
            area_hectares=data.area_hectares,
            resolution=data.resolution,
            max_cloud_cover=data.max_cloud_cover,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        ))
        row = conn.execute(
            select(areas_table).where(areas_table.c.id == area_id)
        ).fetchone()
    return _row_to_response(row, [])


def list_all_areas() -> List[AreaResponse]:
    """Retorna todas as áreas (visão do admin)."""
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(select(areas_table)).fetchall()
        result = []
        for row in rows:
            assigned = _get_assigned_users(conn, row.id)
            result.append(_row_to_response(row, assigned))
    return result


def list_user_areas(username: str) -> List[AreaResponse]:
    """Retorna apenas as áreas atribuídas ao usuário."""
    engine = get_engine()
    with engine.connect() as conn:
        assigned_ids = conn.execute(
            select(area_assignments_table.c.area_id).where(
                area_assignments_table.c.username == username
            )
        ).fetchall()
        ids = [r.area_id for r in assigned_ids]
        if not ids:
            return []
        rows = conn.execute(
            select(areas_table).where(areas_table.c.id.in_(ids))
        ).fetchall()
        result = []
        for row in rows:
            assigned = _get_assigned_users(conn, row.id)
            result.append(_row_to_response(row, assigned))
    return result


def get_area(area_id: str) -> Optional[AreaResponse]:
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            select(areas_table).where(areas_table.c.id == area_id)
        ).fetchone()
        if row is None:
            return None
        assigned = _get_assigned_users(conn, area_id)
    return _row_to_response(row, assigned)


def update_area(area_id: str, data: AreaUpdate) -> Optional[AreaResponse]:
    engine = get_engine()
    updates = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if not updates:
        return get_area(area_id)
    updates["updated_at"] = _now()
    with engine.begin() as conn:
        result = conn.execute(
            areas_table.update().where(areas_table.c.id == area_id).values(**updates)
        )
        if result.rowcount == 0:
            return None
        row = conn.execute(
            select(areas_table).where(areas_table.c.id == area_id)
        ).fetchone()
        assigned = _get_assigned_users(conn, area_id)
    return _row_to_response(row, assigned)


def delete_area(area_id: str) -> bool:
    engine = get_engine()
    with engine.begin() as conn:
        result = conn.execute(
            areas_table.delete().where(areas_table.c.id == area_id)
        )
    return result.rowcount > 0


# ── Atribuições de usuários (admin) ───────────────────────────────────────────

def assign_user(area_id: str, username: str) -> bool:
    """Atribui um usuário a uma área. Retorna False se já estava atribuído."""
    engine = get_engine()
    with engine.begin() as conn:
        existing = conn.execute(
            select(area_assignments_table).where(
                area_assignments_table.c.area_id == area_id,
                area_assignments_table.c.username == username,
            )
        ).fetchone()
        if existing:
            return False
        conn.execute(area_assignments_table.insert().values(
            area_id=area_id,
            username=username,
            assigned_at=_now(),
        ))
    return True


def remove_assignment(area_id: str, username: str) -> bool:
    engine = get_engine()
    with engine.begin() as conn:
        result = conn.execute(
            area_assignments_table.delete().where(
                area_assignments_table.c.area_id == area_id,
                area_assignments_table.c.username == username,
            )
        )
    return result.rowcount > 0


def is_user_assigned(area_id: str, username: str) -> bool:
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            select(area_assignments_table).where(
                area_assignments_table.c.area_id == area_id,
                area_assignments_table.c.username == username,
            )
        ).fetchone()
    return row is not None


# ── Lista de usuários (admin) ──────────────────────────────────────────────────

def list_users() -> List[UserListResponse]:
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(select(users_table)).fetchall()
    return [UserListResponse(username=r.username, is_admin=r.is_admin) for r in rows]
