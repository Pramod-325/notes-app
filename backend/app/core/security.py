"""
Security utilities — JWT encoding/decoding and password hashing.

Design decisions:
- Access tokens: short-lived (15 min), stateless JWT — not stored in DB.
- Refresh tokens: long-lived (7 days), stored as SHA-256 hash in DB.
- Passwords: Raw bcrypt (bypassing passlib due to modern bcrypt incompatibilities).
  Passwords over 72 bytes are pre-hashed with SHA-256 to prevent bcrypt crashes.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings
from app.core.exceptions import UnauthorizedError


# ── Password hashing ──────────────────────────────────────────────────────────

def _prepare_password(plain: str) -> bytes:
    """
    Bcrypt has a strict maximum length of 72 bytes.
    If a user provides a password longer than this (e.g., a long passphrase),
    we pre-hash it with SHA-256 to compress it into a fixed, safe length.
    """
    pwd_bytes = plain.encode("utf-8")
    if len(pwd_bytes) > 72:
        return hashlib.sha256(pwd_bytes).hexdigest().encode("ascii")
    return pwd_bytes

def hash_password(plain: str) -> str:
    """Return bcrypt hash of the password."""
    pwd_bytes = _prepare_password(plain)
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)
    return bcrypt.hashpw(pwd_bytes, salt).decode("ascii")

def verify_password(plain: str, hashed: str) -> bool:
    """
    Constant-time bcrypt verification.
    Returns False (never raises) so callers can handle failures uniformly.
    """
    try:
        pwd_bytes = _prepare_password(plain)
        return bcrypt.checkpw(pwd_bytes, hashed.encode("ascii"))
    except Exception:
        return False


# ── JWT (access token) ────────────────────────────────────────────────────────

def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    if extra_claims:
        claims.update(extra_claims)
    return jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise UnauthorizedError("Invalid or expired access token.") from exc

    if payload.get("type") != "access":
        raise UnauthorizedError("Token type mismatch.")

    return payload


# ── Refresh tokens ────────────────────────────────────────────────────────────

def generate_refresh_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    hashed = _hash_token(raw)
    return raw, hashed


def hash_refresh_token(raw: str) -> str:
    return _hash_token(raw)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def safe_str_compare(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode(), b.encode())