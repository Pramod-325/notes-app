"""
ShareRepository — note sharing data access.

Access-check design:
    get_shared_note_ids_for_user() returns a Python set[UUID].
    Checking membership is O(1) vs O(n) list scan.
    The service uses this set to answer "can this user see this note?"
    in constant time, regardless of how many notes have been shared with them.
"""
from __future__ import annotations
import uuid
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.share import NoteShare
from app.models.note import Note
from app.models.user import User
from app.repositories.base import AbstractRepository


class ShareRepository(AbstractRepository[NoteShare]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, NoteShare)

    async def get_by_id(self, record_id: uuid.UUID) -> NoteShare | None:
        result = await self._session.execute(
            select(NoteShare).where(NoteShare.id == record_id)
        )
        return result.scalar_one_or_none()

    async def get_share(
        self, note_id: uuid.UUID, shared_with_user_id: uuid.UUID
    ) -> NoteShare | None:
        """Fetch a specific share record by note + recipient."""
        result = await self._session.execute(
            select(NoteShare).where(
                NoteShare.note_id == note_id,
                NoteShare.shared_with_user_id == shared_with_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_share(
        self,
        note_id: uuid.UUID,
        shared_with_user_id: uuid.UUID,
        shared_by_user_id: uuid.UUID,
        permission: str = "read",
    ) -> NoteShare:
        """
        Idempotent share creation using PostgreSQL INSERT ... ON CONFLICT DO NOTHING.

        If the share already exists, we return the existing record without error.
        This directly handles the 'duplicate share' edge case — re-sharing a note
        with the same user is a no-op, not a 409 Conflict.
        """
        import uuid as _uuid

        stmt = (
            pg_insert(NoteShare)
            .values(
                id=_uuid.uuid4(),
                note_id=note_id,
                shared_with_user_id=shared_with_user_id,
                shared_by_user_id=shared_by_user_id,
                permission=permission,
            )
            .on_conflict_do_nothing(
                index_elements=["note_id", "shared_with_user_id"]
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

        # Fetch the share (whether newly inserted or pre-existing)
        return await self.get_share(note_id, shared_with_user_id)

    async def list(
        self,
        filters: dict[str, Any] | None = None,
        offset: int = 0,
        limit: int = 20,
        order_by: Any | None = None,
    ) -> tuple[list[NoteShare], int]:
        stmt = select(NoteShare)
        if filters:
            for key, val in filters.items():
                stmt = stmt.where(getattr(NoteShare, key) == val)
        total = await self._count()
        result = await self._session.execute(stmt.offset(offset).limit(limit))
        return list(result.scalars().all()), total

    async def list_shared_notes_for_user(
        self,
        user_id: uuid.UUID,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[tuple[Note, NoteShare, str]], int]:
        """
        Fetch paginated shared notes for the 'Shared with me' tab.

        Returns list of (Note, NoteShare, sharer_email) tuples — everything
        the frontend needs in a single query (no N+1 sharer-email lookups).

        Excludes soft-deleted notes — a deleted note should disappear from
        the recipient's view too.
        """
        sharer = User.__table__.alias("sharer")

        base_where = and_(
            NoteShare.shared_with_user_id == user_id,
            Note.is_deleted.is_(False),
        )

        total_stmt = (
            select(NoteShare)
            .join(Note, Note.id == NoteShare.note_id)
            .where(base_where)
        )
        total = await self._count_stmt(total_stmt)

        stmt = (
            select(Note, NoteShare, sharer.c.email)
            .join(NoteShare, NoteShare.note_id == Note.id)
            .join(sharer, sharer.c.id == NoteShare.shared_by_user_id)
            .where(base_where)
            .order_by(NoteShare.shared_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = result.all()
        return [(row[0], row[1], row[2]) for row in rows], total

    async def get_shared_note_ids_for_user(
        self, user_id: uuid.UUID
    ) -> set[uuid.UUID]:
        """
        Return the set of note IDs shared with this user.

        Returns set[UUID] — O(1) membership test (vs O(n) list.index()).
        Used by note_service to quickly answer 'can user access this note?'
        without a separate DB query per access check.

        Only fetches the ID column — minimal data transfer from DB.
        """
        result = await self._session.execute(
            select(NoteShare.note_id).where(
                NoteShare.shared_with_user_id == user_id
            )
        )
        return {row[0] for row in result.all()}

    async def create(self, data: dict[str, Any]) -> NoteShare:
        share = NoteShare(**data)
        return await self._flush_and_refresh(share)

    async def update(self, record: NoteShare, data: dict[str, Any]) -> NoteShare:
        for key, value in data.items():
            setattr(record, key, value)
        return await self._flush_and_refresh(record)

    async def delete(self, record: NoteShare) -> None:
        await self._session.delete(record)
        await self._session.flush()

    async def _count_stmt(self, stmt) -> int:
        """Count rows from a subquery."""
        from sqlalchemy import func, select as sa_select
        count_stmt = sa_select(func.count()).select_from(stmt.subquery())
        result = await self._session.execute(count_stmt)
        return result.scalar_one()