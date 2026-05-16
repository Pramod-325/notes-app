"""
AbstractRepository[T] — the data-access interface.

Every concrete repository implements this contract. The service layer
depends on the interface, not the implementation. Swapping the storage
backend (e.g. to a remote gRPC service) means replacing only the
repository class, not the service logic.

Pattern: Repository + Unit-of-Work (the AsyncSession acts as the UoW).
The session is injected into each repository — it is NOT managed here.
Transaction boundaries live in the service layer and the get_db dependency.
"""

import uuid
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import BaseModel as OrmBaseModel

T = TypeVar("T", bound=OrmBaseModel)


class AbstractRepository(ABC, Generic[T]):
    """
    Generic CRUD interface.
    Subclasses receive a concrete ORM model class at init time.
    """

    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        self._session = session
        self._model = model

    # ── Abstract interface ─────────────────────────────────────────────────────

    @abstractmethod
    async def get_by_id(self, record_id: uuid.UUID) -> T | None:
        """Fetch a single record by primary key. Returns None if not found."""
        ...

    @abstractmethod
    async def list(
        self,
        filters: dict[str, Any] | None = None,
        offset: int = 0,
        limit: int = 20,
        order_by: Any | None = None,
    ) -> tuple[list[T], int]:
        """
        Return a page of records and the total count matching the filters.
        Returns (items, total) — total drives pagination math.
        """
        ...

    @abstractmethod
    async def create(self, data: dict[str, Any]) -> T:
        """Insert a new record. Returns the fully populated ORM instance."""
        ...

    @abstractmethod
    async def update(self, record: T, data: dict[str, Any]) -> T:
        """Apply a partial update dict to an existing record. Returns the updated instance."""
        ...

    @abstractmethod
    async def delete(self, record: T) -> None:
        """Permanently remove a record from the database."""
        ...

    # ── Shared helpers ─────────────────────────────────────────────────────────

    async def _count(self, *where_clauses) -> int:
        """
        Efficient COUNT query with optional WHERE clauses.

        Uses COUNT(*) rather than len(SELECT *) — the DB counts without
        materialising all rows, which is O(index scan) vs O(full scan).
        """
        stmt = select(func.count()).select_from(self._model)
        for clause in where_clauses:
            stmt = stmt.where(clause)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def _flush_and_refresh(self, instance: T) -> T:
        """
        Flush pending changes to the DB (within the transaction) and refresh
        the instance so server-generated values (timestamps, sequences) are
        populated on the Python object before returning.
        """
        self._session.add(instance)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance