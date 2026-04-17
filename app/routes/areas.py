"""
Rotas de gerenciamento de áreas geográficas.

Admin:
  GET    /api/areas                         → lista todas as áreas
  POST   /api/areas                         → cria área
  GET    /api/areas/{id}                    → detalhe da área
  PATCH  /api/areas/{id}                    → atualiza área
  DELETE /api/areas/{id}                    → remove área
  POST   /api/areas/{id}/assign             → atribui usuário à área
  DELETE /api/areas/{id}/assign/{username}  → remove atribuição

Usuário:
  GET    /api/areas                         → lista só as áreas atribuídas a ele
  GET    /api/areas/{id}                    → detalhe (se atribuído)
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.jwt_auth import get_current_user
from app.auth.users import User
from app.models.area_schemas import (
    AreaCreate,
    AreaResponse,
    AreaUpdate,
    AssignUserRequest,
)
from app.repositories import area_repository

router = APIRouter()


def _require_admin(user: User) -> None:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente administradores podem realizar esta ação.",
        )


def _require_area_access(area_id: str, user: User) -> None:
    """Garante que o usuário é admin ou está atribuído à área."""
    if user.is_admin:
        return
    if not area_repository.is_user_assigned(area_id, user.username):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem acesso a esta área.",
        )


# ── Listagem e criação ─────────────────────────────────────────────────────────

@router.get(
    "/areas",
    response_model=list[AreaResponse],
    summary="Listar áreas",
    tags=["Áreas"],
)
def list_areas(current_user: User = Depends(get_current_user)) -> list[AreaResponse]:
    """Admin vê todas as áreas; usuário vê apenas as que foram atribuídas a ele."""
    if current_user.is_admin:
        return area_repository.list_all_areas()
    return area_repository.list_user_areas(current_user.username)


@router.post(
    "/areas",
    response_model=AreaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar área (admin)",
    tags=["Áreas"],
)
def create_area(
    body: AreaCreate,
    current_user: User = Depends(get_current_user),
) -> AreaResponse:
    _require_admin(current_user)
    return area_repository.create_area(body, current_user.username)


# ── Detalhe, atualização e remoção ────────────────────────────────────────────

@router.get(
    "/areas/{area_id}",
    response_model=AreaResponse,
    summary="Detalhe da área",
    tags=["Áreas"],
)
def get_area(
    area_id: str,
    current_user: User = Depends(get_current_user),
) -> AreaResponse:
    _require_area_access(area_id, current_user)
    area = area_repository.get_area(area_id)
    if area is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Área não encontrada.")
    return area


@router.patch(
    "/areas/{area_id}",
    response_model=AreaResponse,
    summary="Atualizar área (admin)",
    tags=["Áreas"],
)
def update_area(
    area_id: str,
    body: AreaUpdate,
    current_user: User = Depends(get_current_user),
) -> AreaResponse:
    _require_admin(current_user)
    area = area_repository.update_area(area_id, body)
    if area is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Área não encontrada.")
    return area


@router.delete(
    "/areas/{area_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover área (admin)",
    tags=["Áreas"],
)
def delete_area(
    area_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    _require_admin(current_user)
    if not area_repository.delete_area(area_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Área não encontrada.")


# ── Atribuições de usuários ────────────────────────────────────────────────────

@router.post(
    "/areas/{area_id}/assign",
    status_code=status.HTTP_201_CREATED,
    summary="Atribuir usuário à área (admin)",
    tags=["Áreas"],
)
def assign_user(
    area_id: str,
    body: AssignUserRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    _require_admin(current_user)
    if area_repository.get_area(area_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Área não encontrada.")
    assigned = area_repository.assign_user(area_id, body.username)
    if not assigned:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Usuário já está atribuído a esta área.",
        )
    return {"detail": f"Usuário '{body.username}' atribuído com sucesso."}


@router.delete(
    "/areas/{area_id}/assign/{username}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover atribuição de usuário (admin)",
    tags=["Áreas"],
)
def remove_assignment(
    area_id: str,
    username: str,
    current_user: User = Depends(get_current_user),
) -> None:
    _require_admin(current_user)
    if not area_repository.remove_assignment(area_id, username):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Atribuição não encontrada.",
        )


