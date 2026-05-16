"""
NoteService — core note business logic.

Access model:
  - A user can CRUD their OWN notes freely.
  - A shared note can be READ via GET /notes/{id} (service checks the
    shared_note_ids set). The shared copy appears on a separate tab.
  - Only the OWNER can update or delete a note — sharing grants read-only.

Soft-delete handling:
  - is_deleted=True → 410 Gone (not 404) on access by owner.
  - is_deleted notes are invisible to share recipients immediately.
  - This handles the Delete/Update collision edge case from the design doc.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenError, GoneError, NotFoundError, PayloadTooLargeError
from app.core.pagination import PageParams, PaginatedResponse
from app.models.note import Note
from app.models.user import User
from app.repositories.note_repo import NoteRepository
from app.repositories.share_repo import ShareRepository
from app.schemas.note import NoteCreate, NoteResponse, NoteUpdate


class NoteService:

    def __init__(self, session: AsyncSession) -> None:
        self._note_repo = NoteRepository(session)
        self._share_repo = ShareRepository(session)

    async def create_note(self, user: User, payload: NoteCreate) -> NoteResponse:
        self._check_content_size(payload.content)
        note = await self._note_repo.create(
            {
                "owner_id": user.id,
                "title": payload.title,
                "content": payload.content,
            }
        )
        return NoteResponse.model_validate(note)

    async def list_notes(
        self,
        user: User,
        page: PageParams,
        search: str | None = None,
    ) -> PaginatedResponse[NoteResponse]:
        """
        List the authenticated user's own (non-deleted) notes.
        Single DB round-trip using window function (see NoteRepository).
        Shared notes are NOT included here — they appear on a separate endpoint.
        """
        notes, total = await self._note_repo.list_by_owner(
            owner_id=user.id,
            offset=page.offset,
            limit=page.limit,
            search=search,
        )
        items = [NoteResponse.model_validate(n) for n in notes]
        return PaginatedResponse.build(items, total, page)

    async def get_note(self, user: User, note_id: uuid.UUID) -> NoteResponse:
        """
        Fetch a single note.

        Access rules (in order):
          1. Owner can access their own note (unless soft-deleted → 410).
          2. If not owner, check shared_note_ids (O(1) set membership).
          3. Otherwise → 403 (not 404 — resource exists but access denied).

        We return 403 instead of 404 for non-owned non-shared notes because:
          - The note EXISTS — returning 404 would lie about reality.
          - 403 is more actionable: the user knows to ask for access.
          - It does NOT leak content — just existence — which is acceptable.
        """
        note = await self._note_repo.get_by_id(note_id)

        if note is None:
            raise NotFoundError("Note not found.")

        if note.owner_id == user.id:
            if note.is_deleted:
                raise GoneError("This note has been deleted.")
            return NoteResponse.model_validate(note)

        # Not the owner — check if it's shared with this user
        # get_shared_note_ids_for_user returns set[UUID] → O(1) lookup
        shared_ids = await self._share_repo.get_shared_note_ids_for_user(user.id)
        if note_id not in shared_ids:
            raise ForbiddenError("You do not have access to this note.")

        if note.is_deleted:
            # Shared note was deleted by owner — remove from recipient's view
            raise GoneError("This note is no longer available.")

        return NoteResponse.model_validate(note)

    async def update_note(
        self, user: User, note_id: uuid.UUID, payload: NoteUpdate
    ) -> NoteResponse:
        """
        Update title and/or content of a note.

        Only the OWNER can update. Shared recipients get 403.
        Updating a soft-deleted note returns 410 Gone — this is the
        Delete/Update collision handling: the edit is rejected cleanly.
        """
        if payload.content is not None:
            self._check_content_size(payload.content)

        note = await self._note_repo.get_by_id_and_owner(note_id, user.id)

        if note is None:
            # Could be not found OR belongs to someone else.
            # Check if the note exists at all to give a meaningful response:
            exists = await self._note_repo.get_by_id(note_id)
            if exists is None:
                raise NotFoundError("Note not found.")
            raise ForbiddenError("You can only edit your own notes.")

        if note.is_deleted:
            raise GoneError(
                "Cannot update a deleted note. "
                "The note was deleted (possibly from another device)."
            )

        update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
        updated = await self._note_repo.update(note, update_data)
        return NoteResponse.model_validate(updated)

    async def delete_note(self, user: User, note_id: uuid.UUID) -> None:
        """
        Soft-delete a note. Only the owner can delete.

        The row is retained with is_deleted=True so that:
          - Concurrent offline edits receive 410 Gone, not a silent overwrite.
          - The share records remain (NoteShare.note_id FK still resolves).
          - Recipients see the note disappear from their shared tab cleanly.
        """
        note = await self._note_repo.get_by_id_and_owner(note_id, user.id)

        if note is None:
            exists = await self._note_repo.get_by_id(note_id)
            if exists is None:
                raise NotFoundError("Note not found.")
            raise ForbiddenError("You can only delete your own notes.")

        if note.is_deleted:
            # Idempotent: deleting an already-deleted note is a no-op (200/204 OK)
            return

        await self._note_repo.soft_delete(note)

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _check_content_size(content: str) -> None:
        """
        Double-check content size at the service layer (Pydantic validator is
        the first gate; this is the defence-in-depth second gate).
        Raises PayloadTooLargeError with a 413 status.
        """
        size = len(content.encode("utf-8"))
        if size > settings.MAX_NOTE_CONTENT_BYTES:
            limit_kb = settings.MAX_NOTE_CONTENT_BYTES // 1024
            raise PayloadTooLargeError(
                f"Note content is {size:,} bytes — exceeds the {limit_kb} KB limit."
            )