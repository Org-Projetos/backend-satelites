"""
Geração e validação de tokens JWT.
Fornece a dependência FastAPI `get_current_user` para proteger rotas.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.auth.token_blacklist import token_blacklist
from app.auth.users import User, user_store
from app.config import Settings, get_settings

ALGORITHM = "HS256"

_bearer_scheme = HTTPBearer()


def create_access_token(
    subject: str,
    settings: Settings,
    expires_delta: timedelta | None = None,
) -> str:
    """Gera um JWT assinado com o subject (username)."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> tuple[str, datetime]:
    """Decodifica e valida o JWT. Retorna (subject, expiry)."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        subject: str | None = payload.get("sub")
        exp: int | None = payload.get("exp")
        if subject is None or exp is None:
            raise ValueError("Token sem subject ou expiração")
        expiry = datetime.fromtimestamp(exp, tz=timezone.utc)
        return subject, expiry
    except JWTError as exc:
        raise ValueError(f"Token inválido: {exc}") from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> User:
    """
    Dependência FastAPI: extrai e valida o JWT do header Authorization.
    Rejeita tokens na blacklist (logout realizado) ou expirados.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou token expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials

    if token_blacklist.is_blocked(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalidado. Faça login novamente.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        username, _ = decode_access_token(token, settings)
    except ValueError:
        raise credentials_exception

    user = user_store.get(username)
    if user is None:
        raise credentials_exception

    return user


def get_token_and_expiry(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> tuple[str, datetime]:
    """Dependência auxiliar usada pelo endpoint de logout."""
    try:
        _, expiry = decode_access_token(credentials.credentials, settings)
        return credentials.credentials, expiry
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        )
