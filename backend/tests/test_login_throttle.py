"""Brute-force protection on /auth/login."""

import pytest
from fastapi.testclient import TestClient

from app.core import login_throttle
from app.main import app
from tests.conftest import TEST_PASSWORD, ensure_account

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_throttle():
    login_throttle.reset()
    yield
    login_throttle.reset()


def _login(username, password):
    return client.post(
        "/auth/login", json={"username": username, "password": password}
    )


def test_ten_wrong_passwords_are_401_then_429_with_retry_after():
    ensure_account("throttle_user")

    for _ in range(10):
        assert _login("throttle_user", "wrong-password").status_code == 401

    blocked = _login("throttle_user", "wrong-password")

    assert blocked.status_code == 429
    assert 0 < int(blocked.headers["Retry-After"]) <= 300


def test_correct_password_is_also_refused_during_lockout():
    ensure_account("throttle_user")

    for _ in range(10):
        _login("throttle_user", "wrong-password")

    assert _login("throttle_user", TEST_PASSWORD).status_code == 429


def test_login_works_again_after_the_window_passes(monkeypatch):
    ensure_account("throttle_user")
    clock = {"now": 1000.0}
    monkeypatch.setattr(login_throttle.time, "monotonic", lambda: clock["now"])

    for _ in range(10):
        _login("throttle_user", "wrong-password")

    assert _login("throttle_user", TEST_PASSWORD).status_code == 429

    clock["now"] += 301

    assert _login("throttle_user", TEST_PASSWORD).status_code == 200
    # A success clears the history: a fresh run of failures starts from zero.
    for _ in range(10):
        assert _login("throttle_user", "wrong-password").status_code == 401


def test_username_is_case_insensitive():
    ensure_account("throttle_user")

    for i in range(10):
        _login("Throttle_User" if i % 2 else "throttle_user", "wrong-password")

    assert _login("THROTTLE_USER", "wrong-password").status_code == 429


def test_failures_are_counted_for_unknown_usernames_too():
    for _ in range(10):
        assert _login("no_such_user", "x").status_code == 401

    assert _login("no_such_user", "x").status_code == 429


def test_one_users_lockout_does_not_block_another_user():
    ensure_account("throttle_user")
    ensure_account("throttle_other")

    for _ in range(10):
        _login("throttle_user", "wrong-password")

    assert _login("throttle_other", TEST_PASSWORD).status_code == 200


def test_one_ip_guessing_many_usernames_is_eventually_blocked():
    codes = [_login(f"spray_{i}", "x").status_code for i in range(40)]

    assert 429 in codes
    assert codes[:30] == [401] * 30
