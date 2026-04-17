"""
Store de usuários persistido no PostgreSQL via SQLAlchemy Core.

O hashing usa hashlib.pbkdf2_hmac (builtin do Python) — sem dependências extras.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass

from sqlalchemy import select

from app.db import get_engine, users_table

_ITERATIONS = 260_000
_HASH_NAME = "sha256"


# ─── Hashing ──────────────────────────────────────────────────────────────────

def _hash_password(plain: str) -> str:
    """Retorna 'salt$hash' usando PBKDF2-HMAC-SHA256."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac(_HASH_NAME, plain.encode(), salt, _ITERATIONS)
    return salt.hex() + "$" + dk.hex()


def _verify_password(plain: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split("$", 1)
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac(_HASH_NAME, plain.encode(), salt, _ITERATIONS)
    return hmac.compare_digest(dk.hex(), dk_hex)


# ─── Modelo ───────────────────────────────────────────────────────────────────

@dataclass
class User:
    username: str
    hashed_password: str
    is_admin: bool = False


# ─── Store ────────────────────────────────────────────────────────────────────

class UserStore:
    """Acesso ao banco de dados para a tabela `users`."""

    def seed_admin(self, username: str, plain_password: str) -> None:
        """Insere o admin se não existir, ou atualiza a senha se já existir."""
        engine = get_engine()
        with engine.begin() as conn:
            row = conn.execute(
                select(users_table).where(users_table.c.username == username)
            ).fetchone()

            if row is None:
                conn.execute(
                    users_table.insert().values(
                        username=username,
                        hashed_password=_hash_password(plain_password),
                        is_admin=True,
                    )
                )
            else:
                # Garante que is_admin seja True caso o registro já exista
                conn.execute(
                    users_table.update()
                    .where(users_table.c.username == username)
                    .values(is_admin=True)
                )

    def get(self, username: str) -> User | None:
        engine = get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                select(users_table).where(users_table.c.username == username)
            ).fetchone()
        if row is None:
            return None
        return User(
            username=row.username,
            hashed_password=row.hashed_password,
            is_admin=row.is_admin,
        )

    def register(self, username: str, plain_password: str) -> User:
        """Registra um novo usuário. Levanta ValueError se já existir."""
        engine = get_engine()
        with engine.begin() as conn:
            existing = conn.execute(
                select(users_table).where(users_table.c.username == username)
            ).fetchone()
            if existing is not None:
                raise ValueError(f"Usuário '{username}' já existe.")
            conn.execute(
                users_table.insert().values(
                    username=username,
                    hashed_password=_hash_password(plain_password),
                    is_admin=False,
                )
            )
        return User(username=username, hashed_password="", is_admin=False)

    def authenticate(self, username: str, plain_password: str) -> User | None:
        user = self.get(username)
        if user is None:
            return None
        if not _verify_password(plain_password, user.hashed_password):
            return None
        return user

    def update_password(self, username: str, new_plain_password: str) -> bool:
        """Atualiza a senha do usuário. Retorna False se o usuário não existir."""
        engine = get_engine()
        with engine.begin() as conn:
            result = conn.execute(
                users_table.update()
                .where(users_table.c.username == username)
                .values(hashed_password=_hash_password(new_plain_password))
            )
        return result.rowcount > 0

    def delete(self, username: str) -> bool:
        """Remove o usuário. Retorna False se não existir."""
        engine = get_engine()
        with engine.begin() as conn:
            result = conn.execute(
                users_table.delete().where(users_table.c.username == username)
            )
        return result.rowcount > 0

    def list_all(self) -> list[User]:
        engine = get_engine()
        with engine.connect() as conn:
            rows = conn.execute(select(users_table)).fetchall()
        return [User(username=r.username, hashed_password=r.hashed_password, is_admin=r.is_admin) for r in rows]


# Instância global — usada em todo o app
user_store = UserStore()
