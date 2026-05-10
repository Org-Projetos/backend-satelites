"""
Testes de integração para os endpoints /api/areas (gerenciamento de áreas).

Utiliza mocks do repositório para evitar dependência de banco de dados
(as tabelas de áreas usam tipo ARRAY que é específico do PostgreSQL).
"""

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch  # noqa: patch used by test decorators and client fixture

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

# Variáveis de ambiente antes de qualquer import da aplicação
os.environ["CDSE_CLIENT_ID"] = "test-client-id"
os.environ["CDSE_CLIENT_SECRET"] = "test-client-secret"
os.environ["SECRET_KEY"] = "test-secret-key-areas-only"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "agro2024"
os.environ["RATE_LIMIT_ENABLED"] = "False"
os.environ["DATABASE_URL"] = "sqlite://"

# ─── Dados de exemplo ─────────────────────────────────────────────────────────

_NOW = datetime.now(timezone.utc).replace(tzinfo=None)

SAMPLE_AREA_DATA = {
    "id": "uuid-area-1",
    "name": "Fazenda São João",
    "description": "Área principal de monitoramento",
    "bbox": [-47.0, -23.0, -46.5, -22.5],
    "coordinates": None,
    "area_hectares": 150.0,
    "resolution": "medium",
    "max_cloud_cover": 30.0,
    "created_by": "admin",
    "created_at": _NOW,
    "updated_at": _NOW,
    "assigned_users": [],
}


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
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def get_user_token(client: TestClient, username: str = "usuario1", password: str = "pw123") -> str:
    client.post("/auth/signup", json={"username": username, "password": password})
    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _make_area_response():
    from app.models.area_schemas import AreaResponse
    return AreaResponse(**SAMPLE_AREA_DATA)


# ─── GET /api/areas ───────────────────────────────────────────────────────────


@patch("app.routes.areas.area_repository")
def test_list_areas_admin_sees_all(mock_repo, client):
    mock_repo.list_all_areas.return_value = [_make_area_response()]

    token = get_admin_token(client)
    resp = client.get("/api/areas", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Fazenda São João"
    mock_repo.list_all_areas.assert_called_once()


@patch("app.routes.areas.area_repository")
def test_list_areas_user_sees_only_assigned(mock_repo, client):
    mock_repo.list_user_areas.return_value = [_make_area_response()]

    token = get_user_token(client, "user_list")
    resp = client.get("/api/areas", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    mock_repo.list_user_areas.assert_called_once_with("user_list")


@patch("app.routes.areas.area_repository")
def test_list_areas_user_empty_when_none_assigned(mock_repo, client):
    mock_repo.list_user_areas.return_value = []

    token = get_user_token(client, "user_empty")
    resp = client.get("/api/areas", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert resp.json() == []


def test_list_areas_without_token_returns_401_or_403(client):
    resp = client.get("/api/areas")
    assert resp.status_code in (401, 403)


# ─── POST /api/areas ──────────────────────────────────────────────────────────


@patch("app.routes.areas.area_repository")
def test_create_area_admin_success(mock_repo, client):
    mock_repo.create_area.return_value = _make_area_response()

    token = get_admin_token(client)
    resp = client.post(
        "/api/areas",
        json={
            "name": "Fazenda São João",
            "description": "Área principal",
            "bbox": [-47.0, -23.0, -46.5, -22.5],
            "area_hectares": 150.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 201
    assert resp.json()["name"] == "Fazenda São João"
    mock_repo.create_area.assert_called_once()


@patch("app.routes.areas.area_repository")
def test_create_area_non_admin_returns_403(mock_repo, client):
    token = get_user_token(client, "not_admin_create")
    resp = client.post(
        "/api/areas",
        json={"name": "Nova Área", "bbox": [-47.0, -23.0, -46.5, -22.5]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_create_area_invalid_bbox_too_short(client):
    token = get_admin_token(client)
    resp = client.post(
        "/api/areas",
        json={"name": "Teste", "bbox": [-47.0, -23.0]},  # incompleta
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_create_area_missing_name(client):
    token = get_admin_token(client)
    resp = client.post(
        "/api/areas",
        json={"bbox": [-47.0, -23.0, -46.5, -22.5]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_create_area_without_token(client):
    resp = client.post(
        "/api/areas",
        json={"name": "Teste", "bbox": [-47.0, -23.0, -46.5, -22.5]},
    )
    assert resp.status_code in (401, 403)


# ─── GET /api/areas/{id} ──────────────────────────────────────────────────────


@patch("app.routes.areas.area_repository")
def test_get_area_by_id_admin(mock_repo, client):
    mock_repo.get_area.return_value = _make_area_response()

    token = get_admin_token(client)
    resp = client.get("/api/areas/uuid-area-1", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert resp.json()["id"] == "uuid-area-1"


@patch("app.routes.areas.area_repository")
def test_get_area_by_id_not_found(mock_repo, client):
    mock_repo.get_area.return_value = None

    token = get_admin_token(client)
    resp = client.get("/api/areas/nonexistent", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 404


@patch("app.routes.areas.area_repository")
def test_get_area_user_not_assigned_returns_403(mock_repo, client):
    mock_repo.is_user_assigned.return_value = False

    token = get_user_token(client, "not_assigned_user")
    resp = client.get("/api/areas/uuid-area-1", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 403


@patch("app.routes.areas.area_repository")
def test_get_area_user_assigned_can_see(mock_repo, client):
    mock_repo.is_user_assigned.return_value = True
    mock_repo.get_area.return_value = _make_area_response()

    token = get_user_token(client, "assigned_user")
    resp = client.get("/api/areas/uuid-area-1", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200


# ─── PATCH /api/areas/{id} ────────────────────────────────────────────────────


@patch("app.routes.areas.area_repository")
def test_update_area_admin_success(mock_repo, client):
    updated_data = {**SAMPLE_AREA_DATA, "name": "Fazenda Atualizada"}
    from app.models.area_schemas import AreaResponse
    mock_repo.update_area.return_value = AreaResponse(**updated_data)

    token = get_admin_token(client)
    resp = client.patch(
        "/api/areas/uuid-area-1",
        json={"name": "Fazenda Atualizada"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    assert resp.json()["name"] == "Fazenda Atualizada"


@patch("app.routes.areas.area_repository")
def test_update_area_not_found(mock_repo, client):
    mock_repo.update_area.return_value = None

    token = get_admin_token(client)
    resp = client.patch(
        "/api/areas/nonexistent",
        json={"name": "Novo Nome"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 404


@patch("app.routes.areas.area_repository")
def test_update_area_non_admin_returns_403(mock_repo, client):
    token = get_user_token(client, "non_admin_patch")
    resp = client.patch(
        "/api/areas/uuid-area-1",
        json={"name": "Hack"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


# ─── DELETE /api/areas/{id} ───────────────────────────────────────────────────


@patch("app.routes.areas.area_repository")
def test_delete_area_admin_success(mock_repo, client):
    mock_repo.delete_area.return_value = True

    token = get_admin_token(client)
    resp = client.delete("/api/areas/uuid-area-1", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 204


@patch("app.routes.areas.area_repository")
def test_delete_area_not_found(mock_repo, client):
    mock_repo.delete_area.return_value = False

    token = get_admin_token(client)
    resp = client.delete("/api/areas/nonexistent", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 404


@patch("app.routes.areas.area_repository")
def test_delete_area_non_admin_returns_403(mock_repo, client):
    token = get_user_token(client, "non_admin_delete")
    resp = client.delete("/api/areas/uuid-area-1", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


# ─── POST /api/areas/{id}/assign ─────────────────────────────────────────────


@patch("app.routes.areas.area_repository")
def test_assign_user_to_area_success(mock_repo, client):
    mock_repo.get_area.return_value = _make_area_response()
    mock_repo.assign_user.return_value = True

    token = get_admin_token(client)
    resp = client.post(
        "/api/areas/uuid-area-1/assign",
        json={"username": "usuario1"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 201
    assert "atribuído" in resp.json()["detail"].lower()


@patch("app.routes.areas.area_repository")
def test_assign_user_already_assigned_returns_409(mock_repo, client):
    mock_repo.get_area.return_value = _make_area_response()
    mock_repo.assign_user.return_value = False  # já atribuído

    token = get_admin_token(client)
    resp = client.post(
        "/api/areas/uuid-area-1/assign",
        json={"username": "usuario1"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 409


@patch("app.routes.areas.area_repository")
def test_assign_user_area_not_found(mock_repo, client):
    mock_repo.get_area.return_value = None

    token = get_admin_token(client)
    resp = client.post(
        "/api/areas/nonexistent/assign",
        json={"username": "usuario1"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 404


# ─── DELETE /api/areas/{id}/assign/{username} ─────────────────────────────────


@patch("app.routes.areas.area_repository")
def test_remove_assignment_success(mock_repo, client):
    mock_repo.remove_assignment.return_value = True

    token = get_admin_token(client)
    resp = client.delete(
        "/api/areas/uuid-area-1/assign/usuario1",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 204


@patch("app.routes.areas.area_repository")
def test_remove_assignment_not_found(mock_repo, client):
    mock_repo.remove_assignment.return_value = False

    token = get_admin_token(client)
    resp = client.delete(
        "/api/areas/uuid-area-1/assign/naoexiste",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 404
