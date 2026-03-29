"""
Camada de banco de dados (SQLAlchemy Core).

Gerencia o engine, define a tabela `users` e expõe `init_db` para ser
chamado no startup da aplicação.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, MetaData, String, Table, create_engine
from sqlalchemy.engine import Engine

metadata = MetaData()

users_table = Table(
    "users",
    metadata,
    Column("username", String(64), primary_key=True),
    Column("hashed_password", String(256), nullable=False),
    Column("is_admin", Boolean, nullable=False, server_default="false"),
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
