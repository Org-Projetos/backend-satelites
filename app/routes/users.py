"""
Gerenciamento de usuários pelo administrador.

GET    /api/users                  → lista todos os usuários (admin)
DELETE /api/users/{username}       → remove usuário (admin, não pode remover a si mesmo nem outro admin)
PATCH  /api/users/{username}       → altera senha do usuário (admin)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.jwt_auth import get_current_user
from app.auth.users import User, user_store
from app.models.area_schemas import UserListResponse

router = APIRouter()


class UpdatePasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=4)


def _require_admin(user: User) -> None:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente administradores podem realizar esta ação.",
        )


@router.get(
    "/users",
    response_model=list[UserListResponse],
    summary="Listar usuários (admin)",
    tags=["Usuários"],
)
def list_users(current_user: User = Depends(get_current_user)) -> list[UserListResponse]:
    _require_admin(current_user)
    users = user_store.list_all()
    return [UserListResponse(username=u.username, is_admin=u.is_admin) for u in users]


@router.delete(
    "/users/{username}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover usuário (admin)",
    tags=["Usuários"],
)
def delete_user(
    username: str,
    current_user: User = Depends(get_current_user),
) -> None:
    _require_admin(current_user)
    if username == current_user.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível remover o próprio usuário.",
        )
    target = user_store.get(username)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")
    if target.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível remover outro administrador.",
        )
    user_store.delete(username)


@router.patch(
    "/users/{username}",
    response_model=UserListResponse,
    summary="Alterar senha do usuário (admin)",
    tags=["Usuários"],
)
def update_user(
    username: str,
    body: UpdatePasswordRequest,
    current_user: User = Depends(get_current_user),
) -> UserListResponse:
    _require_admin(current_user)
    target = user_store.get(username)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")
    user_store.update_password(username, body.new_password)
    return UserListResponse(username=username, is_admin=target.is_admin)
