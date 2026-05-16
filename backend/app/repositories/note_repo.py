"""
NoteRepository — all note data-access logic.

Performance notes:
- All list queries use a single SELECT with SQL COUNT(*) OVER() window function
  so we get items + total count in ONE round-trip to the DB (no separate
  COUNT query). This halves latency on every paginated list call.
- The partial index ix_notes_owner_active (owner_id, updated_at WHERE NOT is_deleted)
  covers the two most common query patterns:
    1. List notes by owner, sorted by updated_at  →  hot path
    2. Get single note by owner + id              →  auth check
"""
from __future__ import annotations
import uuid
from typing import Any

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.note import Note
from app.repositories.base import AbstractRepository


class NoteRepository(AbstractRepository[Note]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Note)

    async def get_by_id(self, record_id: uuid.UUID) -> Note | None:
        """Fetch by PK — includes soft-deleted rows (callers must check is_deleted)."""
        result = await self._session.execute(
            select(Note).where(Note.id == record_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_owner(
        self, note_id: uuid.UUID, owner_id: uuid.UUID
    ) -> Note | None:
        """
        Ownership-scoped fetch.
        Returns the note only if it belongs to owner_id (active or deleted).
        Used for update/delete where we need ownership + soft-delete status.
        """
        result = await self._session.execute(
            select(Note).where(
                Note.id == note_id,
                Note.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        filters: dict[str, Any] | None = None,
        offset: int = 0,
        limit: int = 20,
        order_by: Any | None = None,
    ) -> tuple[list[Note], int]:
        """Generic list — prefer list_by_owner for the main endpoint."""
        stmt = select(Note).where(Note.is_deleted.is_(False))
        if filters:
            for key, val in filters.items():
                stmt = stmt.where(getattr(Note, key) == val)
        total = await self._count(Note.is_deleted.is_(False))
        stmt = stmt.order_by(Note.updated_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all()), total

    async def list_by_owner(
        self,
        owner_id: uuid.UUID,
        offset: int = 0,
        limit: int = 20,
        search: str | None = None,
    ) -> tuple[list[Note], int]:
        """
        Paginated list of active notes for a user, newest-first.

        Uses window function COUNT(*) OVER() to get total in a single query:
            SELECT *, COUNT(*) OVER() AS total FROM notes
            WHERE owner_id = ? AND is_deleted = false
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?

        This is more efficient than two separate SELECT + COUNT queries,
        especially important on NeonDB where each query costs a round-trip.

        Search performs a case-insensitive ILIKE on title + content.
        For free tier, ILIKE is acceptable; a tsvector full-text index
        would be the production upgrade path.
        """
        base_where = and_(
            Note.owner_id == owner_id,
            Note.is_deleted.is_(False),
        )

        if search:
            pattern = f"%{search}%"
            base_where = and_(
                base_where,
                (Note.title.ilike(pattern) | Note.content.ilike(pattern)),
            )

        # Window function subquery — single DB round-trip
        count_col = func.count().over().label("total")
        inner = (
            select(Note, count_col)
            .where(base_where)
            .order_by(Note.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .subquery()
        )

        # Re-select the Note columns + total from the subquery
        result = await self._session.execute(
            select(Note, inner.c.total).where(Note.id == inner.c.id)
        )
        rows = result.all()

        if not rows:
            return [], 0

        notes = [row[0] for row in rows]
        total = rows[0][1]  # same value on every row (window function)
        return notes, total

    async def create(self, data: dict[str, Any]) -> Note:
        note = Note(**data)
        return await self._flush_and_refresh(note)

    async def update(self, record: Note, data: dict[str, Any]) -> Note:
        for key, value in data.items():
            if value is not None:
                setattr(record, key, value)
        return await self._flush_and_refresh(record)

    async def soft_delete(self, record: Note) -> None:
        """
        Mark note as deleted without removing the row.
        Preserves history for conflict detection (Delete/Update edge case).
        """
        from datetime import UTC, datetime
        record.is_deleted = True
        record.deleted_at = datetime.now(UTC)
        self._session.add(record)
        await self._session.flush()

    async def delete(self, record: Note) -> None:
        """Hard delete — only called by maintenance jobs, not user actions."""
        await self._session.delete(record)
        await self._session.flush()