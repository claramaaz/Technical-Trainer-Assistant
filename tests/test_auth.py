"""Login and role checks (P7-35; FR-004, UC-05, BR-003).   python -m pytest -q tests/test_auth.py

These tests use the REAL auth dependencies: the "real_auth" marker turns off the automatic
Learner login that conftest.py gives the other API tests. The users table is replaced by a
dict (fake_users), so no database is needed.
"""
import time

import jwt
import pytest
from fastapi.testclient import TestClient

from backend import auth
from backend.app import app

pytestmark = pytest.mark.real_auth

LEARNER = {"id": 1, "email": "learner@test.com", "role": "learner"}
ADMIN = {"id": 2, "email": "admin@test.com", "role": "admin"}


@pytest.fixture
def fake_users(monkeypatch):
    users = {u["email"]: dict(u, password_hash=auth.hash_password("correct-horse"))
             for u in (LEARNER, ADMIN)}
    monkeypatch.setattr(auth, "find_user", lambda email: users.get(email.strip().lower()))
    return users


@pytest.fixture
def client():
    return TestClient(app)


def bearer(user):
    return {"Authorization": f"Bearer {auth.make_token(user)}"}


# --- the 403 the ticket asks for, and the 401/200 around it --------------------------------

def test_learner_on_admin_route_is_403(client):
    r = client.get("/admin/ping", headers=bearer(LEARNER))
    assert r.status_code == 403
    assert "status" not in r.json()            # UC-05 A2: no admin data in the refusal


def test_admin_on_admin_route_is_200(client):
    r = client.get("/admin/ping", headers=bearer(ADMIN))
    assert r.status_code == 200 and r.json()["role"] == "admin"


@pytest.mark.parametrize("path", ["/search?q=inner+ear", "/answer?q=inner+ear", "/me", "/admin/ping",
                                  "/figures/1/image", "/figures/1/thumbnail", "/figures/1/page-image"])
def test_protected_routes_without_token_are_401(client, path):
    # 401 comes from the dependency, before retrieval or the database is touched.
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("path", ["/health"])
def test_public_routes_need_no_token(client, path):
    assert client.get(path).status_code == 200


# --- login ---------------------------------------------------------------------------------

def test_login_sets_an_httponly_cookie_that_works(client, fake_users):
    r = client.post("/login", json={"email": "Learner@Test.com ", "password": "correct-horse"})
    assert r.status_code == 200 and r.json()["role"] == "learner"
    cookie = r.headers["set-cookie"].lower()
    assert "p7_token=" in cookie and "httponly" in cookie and "samesite=strict" in cookie
    # The TestClient keeps the cookie, as a browser would: no header needed afterwards.
    assert client.get("/me").json() == {"email": "learner@test.com", "role": "learner"}
    assert client.get("/admin/ping").status_code == 403


def test_wrong_password_and_unknown_email_give_the_same_answer(client, fake_users):
    wrong_password = client.post("/login", json={"email": "learner@test.com", "password": "nope"})
    unknown_email = client.post("/login", json={"email": "nobody@test.com", "password": "nope"})
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()        # UC-05 A1: generic error
    assert "set-cookie" not in wrong_password.headers


def test_logout_clears_the_cookie(client, fake_users):
    client.post("/login", json={"email": "admin@test.com", "password": "correct-horse"})
    assert client.get("/me").status_code == 200
    client.post("/logout")
    assert client.get("/me").status_code == 401


# --- tokens that must be refused -----------------------------------------------------------

def test_expired_token_is_401(client):
    old = auth.make_token(ADMIN, now=time.time() - auth.TOKEN_MINUTES * 60 - 5)
    assert client.get("/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401


def test_token_signed_with_another_key_is_401(client):
    forged = jwt.encode({"sub": "2", "role": "admin", "exp": time.time() + 600}, "a-different-key-that-is-not-ours-0123456789",
                        algorithm="HS256")
    assert client.get("/admin/ping", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_learner_cannot_promote_itself_by_editing_the_token(client):
    # Change "learner" to "admin" in the payload and keep the old signature.
    header, payload, signature = auth.make_token(LEARNER).split(".")
    claims = jwt.decode(auth.make_token(LEARNER), options={"verify_signature": False})
    claims["role"] = "admin"
    new_payload = jwt.encode(claims, "any-other-key-only-the-payload-is-kept-0123", algorithm="HS256").split(".")[1]
    tampered = ".".join([header, new_payload, signature])
    assert client.get("/admin/ping", headers={"Authorization": f"Bearer {tampered}"}).status_code == 401


def test_unsigned_alg_none_token_is_401(client):
    unsigned = jwt.encode({"sub": "2", "role": "admin", "exp": time.time() + 600}, None, algorithm="none")
    assert client.get("/admin/ping", headers={"Authorization": f"Bearer {unsigned}"}).status_code == 401


# --- passwords -----------------------------------------------------------------------------

def test_password_is_stored_hashed_not_in_clear():
    stored = auth.hash_password("correct-horse")
    assert "correct-horse" not in stored and stored.startswith("$2")
    assert auth.check_password("correct-horse", stored)
    assert not auth.check_password("correct-hors", stored)


def test_too_short_password_is_refused():
    with pytest.raises(ValueError):
        auth.hash_password("short")
