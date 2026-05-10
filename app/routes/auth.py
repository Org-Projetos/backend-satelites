"""
Endpoints de autenticação de usuários.

POST /auth/login    → recebe username/password, retorna JWT
POST /auth/register → registra novo usuário (requer token de admin)
POST /auth/logout   → invalida o token atual (blacklist)
GET  /auth/me       → retorna dados do usuário autenticado
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.jwt_auth import create_access_token, get_current_user, get_token_and_expiry
from app.auth.token_blacklist import token_blacklist
from app.auth.users import User, user_store
from app.config import Settings, get_settings

router = APIRouter(prefix="/auth", tags=["Autenticação"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    username: str
    is_admin: bool


class RegisterRequest(BaseModel):
    username: str
    password: str


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse, summary="Fazer login")
def login(
    body: LoginRequest,
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """Autentica o usuário e retorna um token JWT Bearer."""
    user = user_store.authenticate(body.username, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=user.username, settings=settings)
    return TokenResponse(access_token=token)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar novo usuário (apenas admin)",
)
def register(
    body: RegisterRequest,
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Registra um novo usuário. Requer token de administrador."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente administradores podem registrar novos usuários.",
        )
    try:
        new_user = user_store.register(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return UserResponse(username=new_user.username, is_admin=new_user.is_admin)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout — invalida o token atual",
)
def logout(
    token_info: tuple[str, datetime] = Depends(get_token_and_expiry),
    _current_user: User = Depends(get_current_user),
) -> None:
    """
    Adiciona o token à blacklist. Qualquer requisição futura com este token
    recebe 401, mesmo antes de ele expirar naturalmente.
    """
    token, expiry = token_info
    token_blacklist.add(token, expiry)


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Auto-cadastro público (sem autenticação)",
)
def signup(body: RegisterRequest) -> UserResponse:
    """Permite que qualquer pessoa crie uma conta sem precisar de token de admin."""
    try:
        new_user = user_store.register(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return UserResponse(username=new_user.username, is_admin=new_user.is_admin)


@router.get("/me", response_model=UserResponse, summary="Dados do usuário atual")
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Retorna as informações do usuário autenticado."""
    return UserResponse(username=current_user.username, is_admin=current_user.is_admin)
