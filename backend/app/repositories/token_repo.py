import uuid
from typing import Any
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token import RefreshToken
from app.repositories.base import AbstractRepository


class TokenRepository(AbstractRepository[RefreshToken]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, RefreshToken)

    # ── Abstract Base Methods ──────────────────────────────────────────────────
    async def get_by_id(self, record_id: uuid.UUID) -> RefreshToken | None:
        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.id == record_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        filters: dict[str, Any] | None = None,
        offset: int = 0,
        limit: int = 20,
        order_by: Any | None = None,
    ) -> tuple[list[RefreshToken], int]:
        stmt = select(RefreshToken)
        if filters:
            for key, val in filters.items():
                stmt = stmt.where(getattr(RefreshToken, key) == val)
        total = await self._count(*[getattr(RefreshToken, k) == v for k, v in (filters or {}).items()])
        result = await self._session.execute(stmt.offset(offset).limit(limit))
        return list(result.scalars().all()), total

    async def create(self, data: dict[str, Any]) -> RefreshToken:
        token = RefreshToken(**data)
        return await self._flush_and_refresh(token)

    async def update(self, record: RefreshToken, data: dict[str, Any]) -> RefreshToken:
        for key, value in data.items():
            setattr(record, key, value)
        return await self._flush_and_refresh(record)

    async def delete(self, record: RefreshToken) -> None:
        await self._session.delete(record)
        await self._session.flush()

    # ── Token-Specific Methods ─────────────────────────────────────────────────
    async def get_valid_token(self, token_hash: str) -> RefreshToken | None:
        """
        Fetch a token by its hash, ensuring it is not revoked and not expired.
        """
        result = await self._session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked.is_(False),
                RefreshToken.expires_at > datetime.now(UTC)
            )
        )
        return result.scalar_one_or_none()

    async def revoke_token(self, token: RefreshToken) -> None:
        """Mark a single token as revoked."""
        token.revoked = True
        self._session.add(token)
        await self._session.flush()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        """
        Revoke all active refresh tokens for a given user (Logout from all devices).
        """
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
            .values(revoked=True)
        )
        await self._session.execute(stmt)
        await self._session.flush()