"""
Cache de imagens em memória com TTL (Time-To-Live).

Singleton `image_cache` compartilhado pela aplicação. Thread-safe via threading.Lock,
compatível com uvicorn rodando com múltiplos workers ou threadpool.
"""

import threading
import time
from typing import Optional


class TtlImageCache:
    """Cache de bytes (imagens PNG) com TTL e tamanho máximo configurável."""

    def __init__(self, ttl: int = 86400, max_size: int = 200) -> None:
        self._ttl = ttl
        self._max_size = max_size
        # Valor: (dados, timestamp de expiração em monotonic seconds)
        self._store: dict[str, tuple[bytes, float]] = {}
        self._lock = threading.Lock()

    def reconfigure(self, ttl: int, max_size: int) -> None:
        """Reconfigura TTL e tamanho máximo (chamado no startup da app)."""
        with self._lock:
            self._ttl = ttl
            self._max_size = max_size

    def get(self, key: str) -> Optional[bytes]:
        """Retorna bytes cacheados ou None se ausente/expirado."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            data, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return None
            return data

    def set(self, key: str, data: bytes) -> None:
        """Armazena bytes no cache. Evita overflow removendo a entrada que expira primeiro."""
        with self._lock:
            if key in self._store:
                # Atualiza entrada existente sem incrementar tamanho
                self._store[key] = (data, time.monotonic() + self._ttl)
                return
            if len(self._store) >= self._max_size:
                # Evicta a entrada com menor tempo de vida restante
                oldest = min(self._store, key=lambda k: self._store[k][1])
                del self._store[oldest]
            self._store[key] = (data, time.monotonic() + self._ttl)

    def make_key(self, **kwargs: object) -> str:
        """Gera chave determinística a partir de pares keyword=value ordenados."""
        parts = [f"{k}={v}" for k, v in sorted(kwargs.items())]
        return ":".join(parts)

    @property
    def size(self) -> int:
        """Número de entradas atualmente no cache (inclui possíveis expiradas)."""
        with self._lock:
            return len(self._store)


# Instância global compartilhada pela aplicação
image_cache = TtlImageCache()
