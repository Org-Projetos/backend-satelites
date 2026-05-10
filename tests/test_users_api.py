"""
Testes de integração para os endpoints /api/users (gerenciamento de usuários pelo admin).

Cobre:
  - GET  /api/users        → lista usuários (admin)
  - DELETE /api/users/{u}  → remove usuário (admin)
  - PATCH  /api/users/{u}  → altera senha (admin)
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

os.environ["CDSE_CLIENT_ID"] = "test-client-id"
os.environ["CDSE_CLIENT_SECRET"] = "test-client-secret"
os.environ["SECRET_KEY"] = "test-secret-key-users-api"
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
    from app.auth.users import user_store
    from app.db import get_engine, users_table

    cdse_auth.invalidate()
    with get_engine().begin() as conn:
        conn.execute(users_table.delete())
    user_store.seed_admin("admin", "agro2024")
    yield
    cdse_auth.invalidate()


# ─── Helpers ─────────────────────────────────────────────────────────────────


def get_admin_token(client: TestClient) -> str:
    resp = client.post("/auth/login", json={"username": "admin", "password": "agro2024"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def create_user(client: TestClient, token: str, username: str, password: str = "senha123") -> dict:
    resp = client.post(
        "/auth/register",
        json={"username": username, "password": password},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def get_user_token(client: TestClient, username: str, password: str = "senha123") -> str:
    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


# ─── GET /api/users ──────────────────────────────────────────────────────────


def test_list_users_admin_sees_all(client):
    token = get_admin_token(client)
    create_user(client, token, "user1")
    create_user(client, token, "user2")

    resp = client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    usernames = [u["username"] for u in resp.json()]
    assert "admin" in usernames
    assert "user1" in usernames
    assert "user2" in usernames


def test_list_users_includes_is_admin_field(client):
    token = get_admin_token(client)
    create_user(client, token, "usuario_comum")

    resp = client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    by_name = {u["username"]: u for u in resp.json()}
    assert by_name["admin"]["is_admin"] is True
    assert by_name["usuario_comum"]["is_admin"] is False


def test_list_users_non_admin_returns_403(client):
    admin_token = get_admin_token(client)
    create_user(client, admin_token, "comum_user")
    user_token = get_user_token(client, "comum_user")

    resp = client.get("/api/users", headers={"Authorization": f"Bearer {user_token}"})
    assert resp.status_code == 403


def test_list_users_without_token_returns_401_or_403(client):
    resp = client.get("/api/users")
    assert resp.status_code in (401, 403)


# ─── DELETE /api/users/{username} ────────────────────────────────────────────


def test_delete_user_admin_success(client):
    token = get_admin_token(client)
    create_user(client, token, "to_delete")

    resp = client.delete("/api/users/to_delete", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204

    # Usuário removido não pode mais logar
    resp = client.post("/auth/login", json={"username": "to_delete", "password": "senha123"})
    assert resp.status_code == 401


def test_delete_user_not_found_returns_404(client):
    token = get_admin_token(client)
    resp = client.delete("/api/users/naoexiste", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_delete_self_returns_400(client):
    token = get_admin_token(client)
    resp = client.delete("/api/users/admin", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400


def test_delete_another_admin_returns_400(client):
    from app.db import get_engine, users_table

    with get_engine().begin() as conn:
        conn.execute(
            users_table.insert().values(
                username="second_admin",
                hashed_password="fakehash$fakehash",
                is_admin=True,
            )
        )

    token = get_admin_token(client)
    resp = client.delete("/api/users/second_admin", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400


def test_delete_user_non_admin_returns_403(client):
    admin_token = get_admin_token(client)
    create_user(client, admin_token, "target_del")
    create_user(client, admin_token, "requester_del")

    user_token = get_user_token(client, "requester_del")
    resp = client.delete("/api/users/target_del", headers={"Authorization": f"Bearer {user_token}"})
    assert resp.status_code == 403


# ─── PATCH /api/users/{username} ─────────────────────────────────────────────


def test_update_password_admin_success(client):
    token = get_admin_token(client)
    create_user(client, token, "user_pw_change", "senha_original")

    resp = client.patch(
        "/api/users/user_pw_change",
        json={"new_password": "nova_senha_segura!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "user_pw_change"


def test_updated_password_allows_login(client):
    token = get_admin_token(client)
    create_user(client, token, "user_login_after_change", "senha_velha")

    client.patch(
        "/api/users/user_login_after_change",
        json={"new_password": "senha_nova_2024"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Senha antiga não funciona mais
    resp = client.post("/auth/login", json={"username": "user_login_after_change", "password": "senha_velha"})
    assert resp.status_code == 401

    # Nova senha funciona
    resp = client.post("/auth/login", json={"username": "user_login_after_change", "password": "senha_nova_2024"})
    assert resp.status_code == 200


def test_update_password_user_not_found_returns_404(client):
    token = get_admin_token(client)
    resp = client.patch(
        "/api/users/fantasma",
        json={"new_password": "qualquer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_update_password_too_short_returns_422(client):
    token = get_admin_token(client)
    create_user(client, token, "user_short_pw")

    resp = client.patch(
        "/api/users/user_short_pw",
        json={"new_password": "ab"},  # min_length=4
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_update_password_non_admin_returns_403(client):
    admin_token = get_admin_token(client)
    create_user(client, admin_token, "target_pw")
    create_user(client, admin_token, "requester_pw")

    user_token = get_user_token(client, "requester_pw")
    resp = client.patch(
        "/api/users/target_pw",
        json={"new_password": "tentativa_hacker"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403


def test_update_password_without_token_returns_401_or_403(client):
    resp = client.patch("/api/users/admin", json={"new_password": "teste"})
    assert resp.status_code in (401, 403)
