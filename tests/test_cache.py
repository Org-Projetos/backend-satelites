"""Testes unitários para TtlImageCache (cache de imagens em memória com TTL)."""

import threading
import time

import pytest

from app.cache import TtlImageCache


# ─── get / set básico ─────────────────────────────────────────────────────────


def test_set_and_get_returns_data():
    cache = TtlImageCache(ttl=60, max_size=10)
    cache.set("key1", b"image-data")
    assert cache.get("key1") == b"image-data"


def test_get_missing_key_returns_none():
    cache = TtlImageCache(ttl=60, max_size=10)
    assert cache.get("nonexistent") is None


def test_overwrite_existing_entry():
    cache = TtlImageCache(ttl=60, max_size=10)
    cache.set("key1", b"v1")
    cache.set("key1", b"v2")
    assert cache.get("key1") == b"v2"


# ─── TTL / expiração ──────────────────────────────────────────────────────────


def test_entry_expires_after_ttl():
    cache = TtlImageCache(ttl=1, max_size=10)
    cache.set("key1", b"data")
    time.sleep(1.1)
    assert cache.get("key1") is None


def test_entry_available_before_ttl():
    cache = TtlImageCache(ttl=60, max_size=10)
    cache.set("key1", b"data")
    assert cache.get("key1") == b"data"


# ─── Tamanho / evicção ────────────────────────────────────────────────────────


def test_size_property_empty():
    cache = TtlImageCache(ttl=60, max_size=10)
    assert cache.size == 0


def test_size_property_after_inserts():
    cache = TtlImageCache(ttl=60, max_size=10)
    cache.set("a", b"1")
    cache.set("b", b"2")
    assert cache.size == 2


def test_overwrite_does_not_increase_size():
    cache = TtlImageCache(ttl=60, max_size=10)
    cache.set("key1", b"v1")
    cache.set("key1", b"v2")
    assert cache.size == 1


def test_max_size_evicts_entry_when_full():
    cache = TtlImageCache(ttl=60, max_size=3)
    cache.set("a", b"1")
    time.sleep(0.01)
    cache.set("b", b"2")
    time.sleep(0.01)
    cache.set("c", b"3")
    assert cache.size == 3

    # Inserção do 4º item deve evocar o que expira primeiro ("a")
    cache.set("d", b"4")
    assert cache.size == 3
    assert cache.get("a") is None  # evicted


def test_max_size_one_keeps_latest():
    cache = TtlImageCache(ttl=60, max_size=1)
    cache.set("first", b"first-data")
    cache.set("second", b"second-data")
    assert cache.size == 1
    assert cache.get("second") == b"second-data"


# ─── make_key ─────────────────────────────────────────────────────────────────


def test_make_key_is_deterministic():
    cache = TtlImageCache()
    k1 = cache.make_key(bbox="-47,-23,-46,-22", date="2024-01-15", visual="ndvi")
    k2 = cache.make_key(date="2024-01-15", bbox="-47,-23,-46,-22", visual="ndvi")
    assert k1 == k2


def test_make_key_different_values_give_different_keys():
    cache = TtlImageCache()
    k1 = cache.make_key(date="2024-01-15", visual="ndvi")
    k2 = cache.make_key(date="2024-01-16", visual="ndvi")
    assert k1 != k2


def test_make_key_different_params_give_different_keys():
    cache = TtlImageCache()
    k1 = cache.make_key(date="2024-01-15", visual="ndvi")
    k2 = cache.make_key(date="2024-01-15", visual="truecolor")
    assert k1 != k2


# ─── reconfigure ──────────────────────────────────────────────────────────────


def test_reconfigure_updates_ttl():
    cache = TtlImageCache(ttl=3600, max_size=100)
    cache.reconfigure(ttl=10, max_size=100)
    assert cache._ttl == 10


def test_reconfigure_updates_max_size():
    cache = TtlImageCache(ttl=3600, max_size=100)
    cache.reconfigure(ttl=3600, max_size=5)
    assert cache._max_size == 5


# ─── Thread safety ────────────────────────────────────────────────────────────


def test_concurrent_writes_do_not_raise():
    cache = TtlImageCache(ttl=60, max_size=500)
    errors: list[Exception] = []

    def writer(n: int) -> None:
        try:
            for i in range(50):
                cache.set(f"key-{n}-{i}", b"x" * 100)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors


def test_concurrent_reads_do_not_raise():
    cache = TtlImageCache(ttl=60, max_size=100)
    for i in range(20):
        cache.set(f"k{i}", b"data")

    errors: list[Exception] = []

    def reader() -> None:
        try:
            for i in range(20):
                cache.get(f"k{i}")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=reader) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
