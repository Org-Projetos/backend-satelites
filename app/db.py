"""
Camada de banco de dados (SQLAlchemy Core).

Gerencia o engine, define as tabelas e expõe `init_db` para ser
chamado no startup da aplicação.
"""

from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    MetaData,
    String,
    Table,
    Float,
    Integer,
    ARRAY,
    DateTime,
    JSON,
    ForeignKey,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.engine import Engine

metadata = MetaData()

users_table = Table(
    "users",
    metadata,
    Column("username", String(64), primary_key=True),
    Column("hashed_password", String(256), nullable=False),
    Column("is_admin", Boolean, nullable=False, server_default="false"),
)

analysis_schedules_table = Table(
    "analysis_schedules",
    metadata,
    Column("id", String(36), primary_key=True),  # UUID
    Column("user_id", String(64), ForeignKey("users.username"), nullable=False),
    Column("bbox", ARRAY(Float), nullable=False),  # [min_lon, min_lat, max_lon, max_lat]
    Column("area_hectares", Float, nullable=False),
    Column("resolution", String(20), nullable=False, server_default="medium"),  # "low", "medium", "high"
    Column("max_cloud_cover", Float, nullable=False, server_default="30"),
    Column("is_active", Boolean, nullable=False, server_default="true"),
    Column("created_at", DateTime, nullable=False, server_default="now()"),
    Column("updated_at", DateTime, nullable=False, server_default="now()"),
)

analysis_history_table = Table(
    "analysis_history",
    metadata,
    Column("id", String(36), primary_key=True),  # UUID
    Column("schedule_id", String(36), ForeignKey("analysis_schedules.id"), nullable=False),
    Column("execution_date", DateTime, nullable=False),
    Column("scene_id", String(256), nullable=True),
    Column("scene_date", String(256), nullable=True),  # ISO timestamp (aumentado de 10)
    Column("scene_cloud_cover", Float, nullable=True),
    Column("scene_satellite_type", String(64), nullable=True),
    Column("images", JSON, nullable=False),  # {"truecolor": "url/path", "ndvi": "url/path"}
    Column("analysis", JSON, nullable=False),  # Resultado da análise
    Column("processing_time", String(256), nullable=False),  # Ex: "45.23s" (aumentado de 100)
    Column("status", String(20), nullable=False, server_default="success"),  # "success" ou "failed"
    Column("error_message", String(65535), nullable=True),  # Erros podem ser muito longos com stack trace
    Column("created_at", DateTime, nullable=False, server_default="now()"),
)

# Áreas geográficas definidas pelo admin. Cada área tem um bbox e coordenadas GeoJSON.
areas_table = Table(
    "areas",
    metadata,
    Column("id", String(36), primary_key=True),  # UUID
    Column("name", String(128), nullable=False),
    Column("description", String(512), nullable=True),
    Column("bbox", ARRAY(Float), nullable=False),  # [min_lon, min_lat, max_lon, max_lat]
    Column("coordinates", JSON, nullable=True),  # GeoJSON polygon [[lon, lat], ...]
    Column("area_hectares", Float, nullable=True),
    Column("created_by", String(64), ForeignKey("users.username"), nullable=False),
    Column("created_at", DateTime, nullable=False, server_default="now()"),
    Column("updated_at", DateTime, nullable=False, server_default="now()"),
)

# Atribuições: quais usuários podem acessar qual área (definido pelo admin).
area_assignments_table = Table(
    "area_assignments",
    metadata,
    Column("area_id", String(36), ForeignKey("areas.id", ondelete="CASCADE"), nullable=False),
    Column("username", String(64), ForeignKey("users.username", ondelete="CASCADE"), nullable=False),
    Column("assigned_at", DateTime, nullable=False, server_default="now()"),
    UniqueConstraint("area_id", "username", name="uq_area_user"),
)

_engine: Engine | None = None


def init_db(database_url: str) -> Engine:
    """
    Cria o engine e garante que as tabelas existem (CREATE TABLE IF NOT EXISTS).
    Deve ser chamado uma única vez no startup da aplicação.
    """
    global _engine
    _engine = create_engine(database_url, pool_pre_ping=True)
    metadata.create_all(_engine)
    return _engine


def get_engine() -> Engine:
    """Retorna o engine já inicializado. Levanta RuntimeError se init_db não foi chamado."""
    if _engine is None:
        raise RuntimeError("Banco de dados não inicializado. Chame init_db() primeiro.")
    return _engine

