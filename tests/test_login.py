"""
Testes do sistema de login JWT.

Cobre:
  - Login com credenciais corretas → retorna token
  - Login com senha errada → 401
  - Login com usuário inexistente → 401
  - GET /auth/me com token válido → dados do usuário
  - GET /auth/me sem token → 403
  - GET /auth/me com token inválido → 401
  - Rota /api/* sem token → 401
  - Rota /api/* com token válido → prossegue normalmente (mock)
  - Registro de usuário por admin → 201
  - Registro por não-admin → 403
  - Registro de usuário duplicado → 409
  - Token expirado → 401
"""

import os
import time
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
import respx
import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

# Variáveis de ambiente mínimas para os testes
os.environ["CDSE_CLIENT_ID"] = "test-client-id"
os.environ["CDSE_CLIENT_SECRET"] = "test-client-secret"
os.environ["SECRET_KEY"] = "test-secret-key-for-tests-only"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "agro2024"
os.environ["RATE_LIMIT_ENABLED"] = "False"
# SQLite em memória para testes — sem necessidade do Docker
os.environ["DATABASE_URL"] = "sqlite://"


@pytest.fixture(scope="module")
def app():
    from app.config import get_settings
    get_settings.cache_clear()

    import app.db as db_module
    from app.db import users_table

    # Engine SQLite in-memory com StaticPool (todas as conexões compartilham o mesmo banco)
    # Apenas users_table é criada (as demais usam ARRAY, tipo exclusivo do PostgreSQL)
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    users_table.create(test_engine)
    db_module._engine = test_engine

    # Patch init_db para não recriar o engine ao chamar create_app()
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
def reset_auth_state(app):
    """Limpa usuários da tabela e re-semeia o admin entre testes."""
    from app.auth.cdse import cdse_auth
    from app.auth.users import user_store
    from app.db import get_engine, users_table

    cdse_auth.invalidate()

    # Limpa todos os usuários e insere apenas o admin
    with get_engine().begin() as conn:
        conn.execute(users_table.delete())

    user_store.seed_admin("admin", "agro2024")
    yield
    cdse_auth.invalidate()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_admin_token(client: TestClient) -> str:
    resp = client.post("/auth/login", json={"username": "admin", "password": "agro2024"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ─── Login ────────────────────────────────────────────────────────────────────

def test_login_success(client):
    resp = client.post("/auth/login", json={"username": "admin", "password": "agro2024"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 20


def test_login_wrong_password(client):
    resp = client.post("/auth/login", json={"username": "admin", "password": "errada"})
    assert resp.status_code == 401
    assert "incorretos" in resp.json()["detail"].lower()


def test_login_unknown_user(client):
    resp = client.post("/auth/login", json={"username": "naoexiste", "password": "qualquer"})
    assert resp.status_code == 401


def test_login_missing_fields(client):
    resp = client.post("/auth/login", json={"username": "admin"})
    assert resp.status_code == 422


# ─── /auth/me ────────────────────────────────────────────────────────────────

def test_me_with_valid_token(client):
    token = get_admin_token(client)
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "admin"
    assert data["is_admin"] is True


def test_me_without_token(client):
    resp = client.get("/auth/me")
    assert resp.status_code in (401, 403)


def test_me_with_invalid_token(client):
    resp = client.get("/auth/me", headers={"Authorization": "Bearer token-invalido"})
    assert resp.status_code == 401


def test_me_with_malformed_header(client):
    resp = client.get("/auth/me", headers={"Authorization": "NotBearer abc"})
    assert resp.status_code in (401, 403)


# ─── Token expirado ───────────────────────────────────────────────────────────

def test_expired_token_rejected(client):
    from app.auth.jwt_auth import create_access_token
    from app.config import get_settings

    settings = get_settings()
    token = create_access_token(
        subject="admin",
        settings=settings,
        expires_delta=timedelta(seconds=-1),  # já expirado
    )
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


# ─── Proteção de rotas /api/* ─────────────────────────────────────────────────

def test_api_route_without_token_returns_401(client):
    resp = client.get("/health")
    assert resp.status_code == 200  # rota pública

    resp = client.post("/api/hasData", json={})
    # Sem token: 403 (HTTPBearer retorna 403 quando o header está ausente)
    assert resp.status_code in (401, 403)


@respx.mock
def test_api_route_with_valid_token_proceeds(client):
    """Com token válido, a requisição passa pela autenticação e chega ao handler."""
    token = get_admin_token(client)

    # Mock do endpoint CDSE de token (necessário para qualquer rota /api/*)
    respx.post(
        "https://identity.dataspace.copernicus.eu"
        "/auth/realms/CDSE/protocol/openid-connect/token"
    ).mock(
        return_value=httpx.Response(
            200, json={"access_token": "cdse-token", "expires_in": 3600}
        )
    )

    # A requisição deve superar a barreira de autenticação (o erro agora é de negócio,
    # não de autenticação — 422 de payload inválido é aceitável aqui)
    resp = client.post(
        "/api/hasData",
        json={"bbox": [-47.0, -23.0, -46.5, -22.5], "date": "2024-01-15", "satelliteType": "sentinel2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code != 401
    assert resp.status_code != 403


# ─── Registro de usuários ─────────────────────────────────────────────────────

def test_register_by_admin_success(client):
    token = get_admin_token(client)
    resp = client.post(
        "/auth/register",
        json={"username": "fazendeiro1", "password": "senha123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "fazendeiro1"
    assert data["is_admin"] is False


def test_register_duplicate_user(client):
    token = get_admin_token(client)
    client.post(
        "/auth/register",
        json={"username": "repetido", "password": "abc123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.post(
        "/auth/register",
        json={"username": "repetido", "password": "abc123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


def test_register_by_non_admin_forbidden(client):
    # Registra um usuário comum
    admin_token = get_admin_token(client)
    client.post(
        "/auth/register",
        json={"username": "comum1", "password": "senha456"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Loga como usuário comum
    resp = client.post("/auth/login", json={"username": "comum1", "password": "senha456"})
    assert resp.status_code == 200
    user_token = resp.json()["access_token"]

    # Tenta registrar outro usuário → proibido
    resp = client.post(
        "/auth/register",
        json={"username": "novouser", "password": "abc"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403


def test_register_without_token(client):
    resp = client.post(
        "/auth/register",
        json={"username": "sem_token", "password": "abc"},
    )
    assert resp.status_code in (401, 403)


# ─── Novo usuário pode logar após registro ────────────────────────────────────

def test_registered_user_can_login(client):
    admin_token = get_admin_token(client)
    client.post(
        "/auth/register",
        json={"username": "produtor_rural", "password": "minha_senha_2024"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    resp = client.post(
        "/auth/login",
        json={"username": "produtor_rural", "password": "minha_senha_2024"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


# ─── Auto-cadastro (/auth/signup) ────────────────────────────────────────────

def test_signup_success(client):
    resp = client.post("/auth/signup", json={"username": "novo_usuario", "password": "senha123"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "novo_usuario"
    assert data["is_admin"] is False


def test_signup_and_login(client):
    client.post("/auth/signup", json={"username": "produtor_novo", "password": "minhasenha"})
    resp = client.post("/auth/login", json={"username": "produtor_novo", "password": "minhasenha"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_signup_duplicate_username(client):
    client.post("/auth/signup", json={"username": "duplicado", "password": "abc123"})
    resp = client.post("/auth/signup", json={"username": "duplicado", "password": "outrasenha"})
    assert resp.status_code == 409


def test_signup_no_auth_required(client):
    """Signup não deve exigir token."""
    resp = client.post("/auth/signup", json={"username": "livre", "password": "livre123"})
    assert resp.status_code == 201


def test_signup_missing_fields(client):
    resp = client.post("/auth/signup", json={"username": "semsenha"})
    assert resp.status_code == 422


def test_registered_user_me(client):
    admin_token = get_admin_token(client)
    client.post(
        "/auth/register",
        json={"username": "tecnico_agro", "password": "tech2024"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = client.post("/auth/login", json={"username": "tecnico_agro", "password": "tech2024"})
    token = resp.json()["access_token"]

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "tecnico_agro"
    assert resp.json()["is_admin"] is False
