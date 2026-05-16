"""
Security utilities — JWT encoding/decoding and password hashing.

Design decisions:
- Access tokens: short-lived (15 min), stateless JWT — not stored in DB.
- Refresh tokens: long-lived (7 days), stored as SHA-256 hash in DB.
  The raw token is only ever sent to the client once; we never store it
  in plaintext, so a DB breach cannot be used to forge sessions.
- Passwords: bcrypt with configurable rounds (default 12).
  passlib's CryptContext handles algorithm migration transparently.
- Token comparison: uses hmac.compare_digest (via secrets) to prevent
  timing-side-channel attacks on token validation.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import UnauthorizedError

# ── Password hashing ──────────────────────────────────────────────────────────

_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.BCRYPT_ROUNDS,
)


def hash_password(plain: str) -> str:
    """Return bcrypt hash of the password."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Constant-time bcrypt verification.
    Returns False (never raises) so callers can handle failures uniformly.
    """
    try:
        return _pwd_context.verify(plain, hashed)
    except Exception:
        return False


# ── JWT (access token) ────────────────────────────────────────────────────────

def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """
    Encode a short-lived JWT access token.

    `subject` is the user's UUID string.
    `extra_claims` can carry non-sensitive metadata (e.g. email, is_active).

    We deliberately do NOT embed sensitive data (roles, permissions) here
    because JWTs are client-readable. Any authorisation check that matters
    must be verified against the DB, not trusted from the token alone.
    """
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
    """
    Decode and validate a JWT access token.
    Raises UnauthorizedError on any failure — expired, tampered, wrong type.
    """
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
    """
    Generate a cryptographically secure refresh token.

    Returns:
        (raw_token, hashed_token)
        - raw_token  → sent to the client once, stored in HttpOnly cookie.
        - hashed_token → stored in the database. We never store raw tokens.

    Uses SHA-256 for hashing (not bcrypt) because:
    - The raw token is already 32 bytes of CSPRNG entropy — no need for
      the key-stretching that bcrypt provides against weak passwords.
    - SHA-256 is O(1) vs bcrypt's intentionally slow O(2^rounds), which
      matters when validating on every authenticated request that uses refresh.
    """
    raw = secrets.token_urlsafe(32)
    hashed = _hash_token(raw)
    return raw, hashed


def hash_refresh_token(raw: str) -> str:
    """Hash a raw refresh token for DB lookup."""
    return _hash_token(raw)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def safe_str_compare(a: str, b: str) -> bool:
    """
    Constant-time string comparison.
    Prevents timing-oracle attacks when comparing token values.
    """
    return secrets.compare_digest(a.encode(), b.encode())