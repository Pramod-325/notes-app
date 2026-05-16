import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import AbstractRepository


class UserRepository(AbstractRepository[User]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_by_id(self, record_id: uuid.UUID) -> User | None:
        result = await self._session.execute(
            select(User).where(User.id == record_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """
        Case-insensitive email lookup.
        The B-tree index on users.email covers this query.
        lower() ensures we don't miss 'User@Example.com' vs 'user@example.com'.
        """
        result = await self._session.execute(
            select(User).where(User.email == email.lower().strip())
        )
        return result.scalar_one_or_none()

    async def get_active_by_email(self, email: str) -> User | None:
        """
        Lookup restricted to active users — used in authentication paths.
        The partial index ix_users_email_active covers this exact query.
        """
        result = await self._session.execute(
            select(User).where(
                User.email == email.lower().strip(),
                User.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        filters: dict[str, Any] | None = None,
        offset: int = 0,
        limit: int = 20,
        order_by: Any | None = None,
    ) -> tuple[list[User], int]:
        stmt = select(User)
        if filters:
            for key, val in filters.items():
                stmt = stmt.where(getattr(User, key) == val)
        total = await self._count(
            *[getattr(User, k) == v for k, v in (filters or {}).items()]
        )
        stmt = stmt.offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all(), total

    async def create(self, data: dict[str, Any]) -> User:
        # Normalise email at persistence time — single source of truth
        if "email" in data:
            data["email"] = data["email"].lower().strip()
        user = User(**data)
        return await self._flush_and_refresh(user)

    async def update(self, record: User, data: dict[str, Any]) -> User:
        for key, value in data.items():
            setattr(record, key, value)
        return await self._flush_and_refresh(record)

    async def delete(self, record: User) -> None:
        await self._session.delete(record)
        await self._session.flush()

    async def email_exists(self, email: str) -> bool:
        """O(log n) existence check via the unique index — no row materialisation."""
        result = await self._session.execute(
            select(User.id).where(User.email == email.lower().strip()).limit(1)
        )
        return result.scalar_one_or_none() is not None