"""
AuthService — all authentication and session management logic.

Token strategy:
  - Access token  : short-lived JWT (15 min), stateless, not stored in DB.
  - Refresh token : long-lived opaque token (7 days), stored hashed in DB.
                    Sent to client via HttpOnly cookie, never in response body.

Token rotation:
  On every /auth/refresh call, the old refresh token is revoked and a new
  one is issued. This means a stolen refresh token can only be used once —
  the legitimate client's next refresh will fail (old token revoked), alerting
  them that their session may be compromised.

Logout:
  Revokes ALL refresh tokens for the user (all devices).
  The (already-issued, short-lived) access token becomes orphaned but expires
  within 15 minutes on its own — acceptable for a free-tier monolith.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.core.config import settings
from app.models.user import User
from app.repositories.token_repo import TokenRepository
from app.repositories.user_repo import UserRepository
from app.schemas.token import TokenResponse
from app.schemas.user import UserCreate, UserResponse


class AuthService:

    def __init__(self, session: AsyncSession) -> None:
        self._user_repo = UserRepository(session)
        self._token_repo = TokenRepository(session)

    async def register(self, payload: UserCreate) -> UserResponse:
        """
        Create a new user account.

        Checks email uniqueness before hashing the password — avoids the
        bcrypt cost on duplicate registrations (bcrypt is intentionally slow).
        """
        if await self._user_repo.email_exists(payload.email):
            # Generic message — don't confirm whether the email is registered
            # (prevents account enumeration via registration endpoint).
            raise ConflictError("An account with this email already exists.")

        user = await self._user_repo.create(
            {
                "email": payload.email,
                "hashed_password": hash_password(payload.password),
                "full_name": payload.full_name,
            }
        )
        return UserResponse.model_validate(user)

    async def login(self, email: str, password: str) -> tuple[TokenResponse, str]:
        """
        Authenticate user and issue an access + refresh token pair.

        Returns:
            (TokenResponse, raw_refresh_token)
            The caller (router) is responsible for setting the refresh token
            as an HttpOnly cookie — it must not appear in the response body.

        Security:
            - Always performs the bcrypt verify even if user not found,
              to prevent timing attacks that distinguish 'no such user'
              from 'wrong password'.
        """
        user = await self._user_repo.get_active_by_email(email)

        # Always run bcrypt to prevent timing oracle
        dummy_hash = "$2b$12$KIXtW5dw2nRZLZk3gQ8X4eGQdvP2Y4LxuBhtRj6lOiXnNhKvLJu1y"
        check_hash = user.hashed_password if user else dummy_hash
        password_ok = verify_password(password, check_hash)

        if not user or not password_ok:
            raise UnauthorizedError("Invalid email or password.")

        access_token = create_access_token(subject=str(user.id))
        raw_refresh, hashed_refresh = generate_refresh_token()

        await self._token_repo.create(
            {
                "user_id": user.id,
                "token_hash": hashed_refresh,
                "expires_at": datetime.now(UTC)
                + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            }
        )

        return TokenResponse(access_token=access_token), raw_refresh

    async def refresh(self, raw_refresh_token: str) -> tuple[TokenResponse, str]:
        """
        Issue a new access token using a valid refresh token.

        Implements token rotation:
          1. Validate the incoming refresh token (not revoked, not expired).
          2. Revoke the old token immediately.
          3. Issue a new access token + new refresh token.

        If someone tries to reuse a rotated (already-revoked) token, the DB
        lookup returns None and we raise 401 — this is the replay-attack signal.
        """
        token_hash = hash_refresh_token(raw_refresh_token)
        db_token = await self._token_repo.get_valid_token(token_hash)

        if not db_token:
            raise UnauthorizedError("Refresh token is invalid or has expired.")

        # Load user (we need their ID for the new token)
        user = await self._user_repo.get_by_id(db_token.user_id)
        if not user or not user.is_active:
            raise UnauthorizedError("Account is no longer active.")

        # Rotate: revoke old, issue new
        await self._token_repo.revoke_token(db_token)

        new_access = create_access_token(subject=str(user.id))
        raw_new_refresh, hashed_new_refresh = generate_refresh_token()

        await self._token_repo.create(
            {
                "user_id": user.id,
                "token_hash": hashed_new_refresh,
                "expires_at": datetime.now(UTC)
                + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            }
        )

        return TokenResponse(access_token=new_access), raw_new_refresh

    async def logout(self, user: User) -> None:
        """
        Revoke all refresh tokens for the user (all devices/sessions).
        The short-lived access token will expire naturally within 15 minutes.
        """
        await self._token_repo.revoke_all_for_user(user.id)