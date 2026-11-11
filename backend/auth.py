"""Login with JWT and server-side role checks (P7-35; FR-004, UC-05, BR-003).

How a request is authenticated:
  1. POST /login checks the email and password against the users table (bcrypt hash) and,
     if they match, signs a JWT holding the user id, email and role, valid TOKEN_MINUTES.
  2. The token is sent back in an httpOnly cookie. The browser then sends it with every
     request, including <img src="/figures/..."> (an <img> cannot send an Authorization
     header), and page JavaScript cannot read it, so an XSS bug cannot steal it.
     Scripts and tests may send it instead as "Authorization: Bearer <token>".
  3. Protected routes depend on current_user (any logged-in user) or require_admin.
     The check happens HERE, on the server: hiding a button in React is not access control.
       no token, bad signature, expired or malformed token  -> 401 Not authenticated
       valid token but not an admin on an admin route        -> 403 Forbidden

Settings, from the environment or .env (same rule as the database settings):
  JWT_SECRET     required, the key that signs tokens. Long and random; never committed.
  COOKIE_SECURE  "true" when deployed over HTTPS (the cookie is then never sent over plain HTTP).

Known limitation: a token stays valid until it expires, even if the user is deleted or their
role changes in the meantime (the role is read from the token, not from the database, on each
request). TOKEN_MINUTES keeps that window short.
"""
import os
import sys
import time
from pathlib import Path

import bcrypt
import jwt
import psycopg
from fastapi import Depends, HTTPException, Request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ingestion"))
from migrate import connection_string, read_env_file  # noqa: E402

ALGORITHM = "HS256"
TOKEN_MINUTES = 8 * 60          # one working day
COOKIE_NAME = "p7_token"
ROLES = ("learner", "admin")

# Hash of a random password, compared against when the email is unknown, so a wrong email
# takes as long as a wrong password and the response time does not reveal which emails exist.
_DUMMY_HASH = bcrypt.hashpw(b"no-such-user", bcrypt.gensalt())


def _setting(name, default=None):
    """Read at call time (not import time), so tests can change it with monkeypatch.setenv."""
    return os.environ.get(name) or read_env_file(ROOT / ".env").get(name) or default


def jwt_secret():
    secret = _setting("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET is not set (environment or .env); see .env.example")
    return secret


def cookie_secure():
    return (_setting("COOKIE_SECURE", "false") or "").lower() == "true"


# --- passwords -----------------------------------------------------------------------------

# bcrypt only uses the first 72 bytes of a password (and recent versions refuse longer ones).
MAX_PASSWORD_BYTES = 72


def hash_password(password):
    data = password.encode("utf-8")
    if not 8 <= len(data) <= MAX_PASSWORD_BYTES:
        raise ValueError(f"password must be 8 to {MAX_PASSWORD_BYTES} bytes long")
    return bcrypt.hashpw(data, bcrypt.gensalt()).decode("ascii")


def check_password(password, password_hash):
    data = password.encode("utf-8")
    if len(data) > MAX_PASSWORD_BYTES:
        return False            # could never have been stored by hash_password
    return bcrypt.checkpw(data, password_hash.encode("ascii"))


# --- tokens --------------------------------------------------------------------------------

def make_token(user, now=None):
    """Signed JWT for a user dict with id, email, role. "exp" makes it expire."""
    now = int(now if now is not None else time.time())
    claims = {"sub": str(user["id"]), "email": user["email"], "role": user["role"],
              "iat": now, "exp": now + TOKEN_MINUTES * 60}
    return jwt.encode(claims, jwt_secret(), algorithm=ALGORITHM)


def read_token(token):
    """The user in a token, or None if the token is missing, forged, expired or malformed.

    algorithms=[ALGORITHM] is required: without it a forged token could choose its own
    algorithm (the classic "alg: none" attack)."""
    if not token:
        return None
    try:
        claims = jwt.decode(token, jwt_secret(), algorithms=[ALGORITHM],
                            options={"require": ["exp", "sub", "role"]})
    except jwt.PyJWTError:
        return None
    if claims["role"] not in ROLES:
        return None
    return {"id": int(claims["sub"]), "email": claims.get("email"), "role": claims["role"]}


# --- users table ---------------------------------------------------------------------------

def find_user(email):
    """The users row for an email (id, email, password_hash, role), or None."""
    with psycopg.connect(connection_string()) as conn, conn.cursor() as cur:
        cur.execute("SELECT id, email, password_hash, role FROM users WHERE email = %s",
                    (email.strip().lower(),))
        row = cur.fetchone()
    if row is None:
        return None
    return {"id": row[0], "email": row[1], "password_hash": row[2], "role": row[3]}


def authenticate(email, password):
    """The user if the email and password match, else None. Same work in both failure cases."""
    user = find_user(email)
    if user is None:
        check_password(password, _DUMMY_HASH.decode("ascii"))
        return None
    if not check_password(password, user["password_hash"]):
        return None
    return user


# --- FastAPI dependencies ------------------------------------------------------------------

def token_from_request(request: Request):
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.cookies.get(COOKIE_NAME)


def current_user(request: Request):
    """Any logged-in user (Learner or Admin), else 401."""
    user = read_token(token_from_request(request))
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


def require_admin(user=Depends(current_user)):
    """An Admin, else 403 (BR-003: only Admins load handbooks, correct figures, see analytics)."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user
