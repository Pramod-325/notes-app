"""
FastAPI dependency functions.

All dependencies are composable via Depends().
get_current_user is the standard auth gate — used on every protected route.
"""

from fastapi import Cookie, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories.user_repo import UserRepository


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract and validate the JWT from the Authorization header.

    Expected format: "Bearer <token>"

    Raises UnauthorizedError (→ 401) on:
      - Missing header
      - Malformed header
      - Invalid / expired JWT
      - User not found or inactive

    The user object is injected into route handlers via:
        current_user: User = Depends(get_current_user)
    """
    if not authorization:
        raise UnauthorizedError("Authorization header is missing.")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError(
            "Authorization header must be in the format: Bearer <token>"
        )

    token = parts[1]
    payload = decode_access_token(token)  # raises UnauthorizedError on failure

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Token payload is missing subject claim.")

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)

    if user is None or not user.is_active:
        raise UnauthorizedError("User account not found or inactive.")

    return user


async def get_refresh_token_from_cookie(
    refresh_token: str | None = Cookie(default=None, alias="refresh_token"),
) -> str:
    """
    Extract the refresh token from the HttpOnly cookie.
    Used only by the /auth/refresh and /auth/logout endpoints.
    """
    if not refresh_token:
        raise UnauthorizedError("Refresh token cookie is missing.")
    return refresh_token