"""Testes unitários para TokenBlacklist (blacklist de tokens JWT invalidados)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.auth.token_blacklist import TokenBlacklist


@pytest.fixture
def blacklist() -> TokenBlacklist:
    return TokenBlacklist()


# ─── Comportamento padrão ─────────────────────────────────────────────────────


def test_token_not_blocked_by_default(blacklist: TokenBlacklist):
    assert blacklist.is_blocked("any-random-token") is False


# ─── Adição de tokens ─────────────────────────────────────────────────────────


def test_add_and_block_valid_token(blacklist: TokenBlacklist):
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    blacklist.add("token-abc", future)
    assert blacklist.is_blocked("token-abc") is True


def test_token_not_affected_by_other_tokens(blacklist: TokenBlacklist):
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    blacklist.add("token-x", future)
    assert blacklist.is_blocked("token-y") is False


# ─── Expiração ────────────────────────────────────────────────────────────────


def test_expired_token_not_blocked(blacklist: TokenBlacklist):
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    blacklist.add("old-token", past)
    assert blacklist.is_blocked("old-token") is False


def test_expired_token_removed_from_store_on_check(blacklist: TokenBlacklist):
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    blacklist.add("expired-token", past)
    blacklist.is_blocked("expired-token")
    with blacklist._lock:
        assert "expired-token" not in blacklist._store


def test_expired_tokens_purged_on_add(blacklist: TokenBlacklist):
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    blacklist.add("expired", past)
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    blacklist.add("new-token", future)
    with blacklist._lock:
        assert "expired" not in blacklist._store


# ─── Múltiplos tokens ─────────────────────────────────────────────────────────


def test_multiple_tokens_all_blocked(blacklist: TokenBlacklist):
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    tokens = [f"token-{i}" for i in range(10)]
    for t in tokens:
        blacklist.add(t, future)
    assert all(blacklist.is_blocked(t) for t in tokens)


def test_mix_of_valid_and_expired(blacklist: TokenBlacklist):
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    blacklist.add("valid-token", future)
    blacklist.add("expired-token", past)
    assert blacklist.is_blocked("valid-token") is True
    assert blacklist.is_blocked("expired-token") is False


# ─── Isolamento entre instâncias ──────────────────────────────────────────────


def test_separate_instances_are_independent():
    bl1 = TokenBlacklist()
    bl2 = TokenBlacklist()
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    bl1.add("only-in-bl1", future)
    assert bl2.is_blocked("only-in-bl1") is False
