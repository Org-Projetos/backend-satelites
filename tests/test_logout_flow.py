"""
Testes de integração para o fluxo de logout (POST /auth/logout).

Cobre:
  - Logout invalida o token via blacklist
  - Token na blacklist é rejeitado em rotas protegidas
  - Novo login após logout gera token válido
  - Logout sem token → 401/403
  - Logout com token inválido → 401
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

os.environ["CDSE_CLIENT_ID"] = "test-client-id"
os.environ["CDSE_CLIENT_SECRET"] = "test-client-secret"
os.environ["SECRET_KEY"] = "test-secret-key-logout-flow"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "agro2024"
os.environ["RATE_LIMIT_ENABLED"] = "False"
os.environ["DATABASE_URL"] = "sqlite://"


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def app():
    from app.config import get_settings
    get_settings.cache_clear()

    import app.db as db_module
    from app.db import users_table

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    users_table.create(test_engine)
    db_module._engine = test_engine
    db_module.init_db = lambda url: test_engine

    from app.main import create_app
    return create_app()


@pytest.fixture(scope="module")
def client(app):
    _sched = MagicMock()
    with (
        patch("app.main.get_minio_client", return_value=MagicMock()),
        patch("app.main.get_scheduler", return_value=_sched),
    ):
        with TestClient(app) as c:
            yield c


@pytest.fixture(autouse=True)
def reset_state():
    from app.auth.cdse import cdse_auth
    from app.auth.token_blacklist import token_blacklist
    from app.auth.users import user_store
    from app.db import get_engine, users_table

    cdse_auth.invalidate()
    with get_engine().begin() as conn:
        conn.execute(users_table.delete())
    user_store.seed_admin("admin", "agro2024")
    with token_blacklist._lock:
        token_blacklist._store.clear()
    yield
    cdse_auth.invalidate()


# ─── Helpers ─────────────────────────────────────────────────────────────────


def login(client: TestClient, username: str = "admin", password: str = "agro2024") -> str:
    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ─── Testes de logout ─────────────────────────────────────────────────────────


def test_logout_returns_204(client):
    token = login(client)
    resp = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204


def test_logout_invalidates_token_for_me_endpoint(client):
    token = login(client)

    # Confirma que token é válido antes do logout
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    # Faz logout
    resp = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204

    # Token deve ser rejeitado
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_blacklisted_token_detail_message(client):
    token = login(client)
    client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    detail = resp.json()["detail"].lower()
    assert "invalidado" in detail or "blacklist" in detail or "token" in detail


def test_new_login_after_logout_provides_valid_token(client):
    import time

    token1 = login(client)
    client.post("/auth/logout", headers={"Authorization": f"Bearer {token1}"})

    # Aguarda 1s para garantir exp diferente (e portanto token diferente)
    time.sleep(1)
    token2 = login(client)

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token2}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


def test_logout_without_token_returns_401_or_403(client):
    resp = client.post("/auth/logout")
    assert resp.status_code in (401, 403)


def test_logout_with_invalid_token_returns_401(client):
    resp = client.post(
        "/auth/logout",
        headers={"Authorization": "Bearer token-completamente-invalido"},
    )
    assert resp.status_code == 401


def test_multiple_sessions_first_logout_does_not_affect_second(client):
    """Dois tokens diferentes — o logout do primeiro não afeta o segundo."""
    import time

    token1 = login(client)
    time.sleep(1)  # garante exp diferente → token diferente
    token2 = login(client)

    # Faz logout apenas do token1
    client.post("/auth/logout", headers={"Authorization": f"Bearer {token1}"})

    # Token1 inválido
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token1}"})
    assert resp.status_code == 401

    # Token2 ainda válido
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token2}"})
    assert resp.status_code == 200


def test_second_logout_with_same_token_also_returns_401(client):
    """Token na blacklist deve ser rejeitado mesmo no endpoint de logout."""
    token = login(client)
    client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})

    # Segunda tentativa de logout com o mesmo token
    resp = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
