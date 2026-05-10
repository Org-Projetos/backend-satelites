"""
Testes unitários para funções de JWT e hashing de senhas.

Cobre:
  - create_access_token / decode_access_token
  - _hash_password / _verify_password (UserStore)
"""

import datetime as dt

import pytest

from app.auth.jwt_auth import create_access_token, decode_access_token
from app.config import Settings

# Settings mínimas para os testes (sem banco ou serviços externos)
_SETTINGS = Settings(
    cdse_client_id="test",
    cdse_client_secret="test",
    secret_key="test-secret-key-unit-tests",
    access_token_expire_minutes=60,
    database_url="sqlite://",
    rate_limit_enabled=False,
)


# ─── create_access_token / decode_access_token ────────────────────────────────


def test_create_and_decode_returns_correct_subject():
    token = create_access_token("testuser", _SETTINGS)
    subject, _ = decode_access_token(token, _SETTINGS)
    assert subject == "testuser"


def test_token_expiry_is_in_the_future():
    token = create_access_token("user1", _SETTINGS)
    _, expiry = decode_access_token(token, _SETTINGS)
    assert expiry > dt.datetime.now(dt.timezone.utc)


def test_default_expiry_respects_settings():
    token = create_access_token("user1", _SETTINGS)
    _, expiry = decode_access_token(token, _SETTINGS)
    expected_min = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=55)
    assert expiry > expected_min


def test_custom_expiry_delta():
    token = create_access_token("user1", _SETTINGS, expires_delta=dt.timedelta(hours=2))
    _, expiry = decode_access_token(token, _SETTINGS)
    expected = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1, minutes=55)
    assert expiry > expected


def test_expired_token_raises_value_error():
    token = create_access_token("user1", _SETTINGS, expires_delta=dt.timedelta(seconds=-1))
    with pytest.raises(ValueError, match="Token inválido"):
        decode_access_token(token, _SETTINGS)


def test_tampered_token_raises_value_error():
    token = create_access_token("user1", _SETTINGS)
    tampered = token[:-10] + "TAMPERED!!"
    with pytest.raises(ValueError):
        decode_access_token(tampered, _SETTINGS)


def test_wrong_secret_raises_value_error():
    token = create_access_token("user1", _SETTINGS)
    wrong_settings = Settings(
        cdse_client_id="test",
        cdse_client_secret="test",
        secret_key="COMPLETELY-DIFFERENT-SECRET",
        database_url="sqlite://",
        rate_limit_enabled=False,
    )
    with pytest.raises(ValueError):
        decode_access_token(token, wrong_settings)


def test_different_subjects_produce_different_tokens():
    t1 = create_access_token("admin", _SETTINGS)
    t2 = create_access_token("user1", _SETTINGS)
    assert t1 != t2


def test_each_subject_decodes_independently():
    t1 = create_access_token("admin", _SETTINGS)
    t2 = create_access_token("user1", _SETTINGS)
    s1, _ = decode_access_token(t1, _SETTINGS)
    s2, _ = decode_access_token(t2, _SETTINGS)
    assert s1 == "admin"
    assert s2 == "user1"


def test_completely_invalid_string_raises():
    with pytest.raises(ValueError):
        decode_access_token("not.a.jwt", _SETTINGS)


# ─── Hashing e verificação de senhas ─────────────────────────────────────────


def test_hash_password_is_not_plaintext():
    from app.auth.users import _hash_password

    plain = "minhasenha@2024"
    hashed = _hash_password(plain)
    assert plain not in hashed


def test_hash_contains_separator():
    from app.auth.users import _hash_password

    hashed = _hash_password("qualquersenha")
    assert "$" in hashed


def test_verify_password_correct():
    from app.auth.users import _hash_password, _verify_password

    plain = "correta123"
    hashed = _hash_password(plain)
    assert _verify_password(plain, hashed) is True


def test_verify_password_wrong():
    from app.auth.users import _hash_password, _verify_password

    hashed = _hash_password("correta")
    assert _verify_password("errada", hashed) is False


def test_different_calls_produce_different_hashes():
    from app.auth.users import _hash_password, _verify_password

    h1 = _hash_password("mesmasenha")
    h2 = _hash_password("mesmasenha")
    assert h1 != h2  # salt aleatório → hashes diferentes
    assert _verify_password("mesmasenha", h1) is True
    assert _verify_password("mesmasenha", h2) is True


def test_verify_malformed_stored_hash():
    from app.auth.users import _verify_password

    assert _verify_password("qualquer", "sem-separador") is False


def test_verify_empty_password():
    from app.auth.users import _hash_password, _verify_password

    hashed = _hash_password("")
    assert _verify_password("", hashed) is True
    assert _verify_password("naoVazio", hashed) is False
