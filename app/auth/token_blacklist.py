"""
Blacklist de tokens JWT invalidados pelo logout.

Usa um dict em memória {token: expiry}. Tokens expirados são limpos
automaticamente na verificação, mantendo o consumo de memória mínimo.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone


class TokenBlacklist:
    def __init__(self) -> None:
        self._store: dict[str, datetime] = {}
        self._lock = threading.Lock()

    def add(self, token: str, expires_at: datetime) -> None:
        """Adiciona um token à blacklist até sua expiração."""
        with self._lock:
            self._store[token] = expires_at
            self._purge_expired()

    def is_blocked(self, token: str) -> bool:
        """Retorna True se o token está na blacklist e ainda não expirou."""
        with self._lock:
            expiry = self._store.get(token)
            if expiry is None:
                return False
            if datetime.now(timezone.utc) >= expiry:
                del self._store[token]
                return False
            return True

    def _purge_expired(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [t for t, exp in self._store.items() if now >= exp]
        for t in expired:
            del self._store[t]


# Instância global compartilhada por toda a aplicação
token_blacklist = TokenBlacklist()
