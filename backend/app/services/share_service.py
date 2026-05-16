"""
ShareService — note sharing business logic.

Rules enforced:
  - Only the note OWNER can share it (not share recipients).
  - Cannot share with yourself.
  - Cannot share a soft-deleted note.
  - Cannot share with a non-existent email.
  - Re-sharing the same note with the same user is idempotent (no error).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, GoneError, NotFoundError
from app.core.pagination import PageParams, PaginatedResponse
from app.models.user import User
from app.repositories.note_repo import NoteRepository
from app.repositories.share_repo import ShareRepository
from app.repositories.user_repo import UserRepository
from app.schemas.note import SharedNoteResponse
from app.schemas.share import ShareNoteRequest, ShareNoteResponse


class ShareService:

    def __init__(self, session: AsyncSession) -> None:
        self._note_repo = NoteRepository(session)
        self._share_repo = ShareRepository(session)
        self._user_repo = UserRepository(session)

    async def share_note(
        self,
        owner: User,
        note_id: uuid.UUID,
        payload: ShareNoteRequest,
    ) -> ShareNoteResponse:
        """
        Share a note with another user by email.
        Validates ownership, target user existence, and self-share prevention.
        Uses upsert_share for idempotency — re-sharing is a no-op.
        """
        # 1. Load note and confirm ownership
        note = await self._note_repo.get_by_id_and_owner(note_id, owner.id)
        if note is None:
            exists = await self._note_repo.get_by_id(note_id)
            if exists is None:
                raise NotFoundError("Note not found.")
            raise ForbiddenError("You can only share notes that you own.")

        if note.is_deleted:
            raise GoneError("Cannot share a deleted note.")

        # 2. Resolve target user
        target_email = payload.share_with_email.lower().strip()

        if target_email == owner.email.lower():
            raise ConflictError("You cannot share a note with yourself.")

        target_user = await self._user_repo.get_active_by_email(target_email)
        if target_user is None:
            raise NotFoundError(
                f"No active account found with email '{target_email}'."
            )

        # 3. Upsert share (idempotent — duplicate share is a no-op)
        share = await self._share_repo.upsert_share(
            note_id=note.id,
            shared_with_user_id=target_user.id,
            shared_by_user_id=owner.id,
            permission="read",
        )

        return ShareNoteResponse(
            message=f"Note successfully shared with {target_email}.",
            note_id=note.id,
            shared_with_email=target_email,
            permission=share.permission,
            shared_at=share.shared_at,
        )

    async def list_shared_with_me(
        self,
        user: User,
        page: PageParams,
    ) -> PaginatedResponse[SharedNoteResponse]:
        """
        Paginated list of notes shared WITH the authenticated user.
        Displayed on the 'Shared with me' tab — separate from owned notes.
        """
        rows, total = await self._share_repo.list_shared_notes_for_user(
            user_id=user.id,
            offset=page.offset,
            limit=page.limit,
        )

        items = [
            SharedNoteResponse(
                id=note.id,
                owner_id=note.owner_id,
                title=note.title,
                content=note.content,
                created_at=note.created_at,
                updated_at=note.updated_at,
                shared_by_email=sharer_email,
                permission=share.permission,
            )
            for note, share, sharer_email in rows
        ]
        return PaginatedResponse.build(items, total, page)

    async def revoke_share(
        self,
        owner: User,
        note_id: uuid.UUID,
        target_email: str,
    ) -> None:
        """
        Revoke a share — only the note owner can do this.
        Silently succeeds if the share doesn't exist (idempotent).
        """
        note = await self._note_repo.get_by_id_and_owner(note_id, owner.id)
        if note is None:
            raise ForbiddenError("You can only revoke shares on notes you own.")

        target_user = await self._user_repo.get_active_by_email(target_email)
        if target_user is None:
            return  # Nothing to revoke

        share = await self._share_repo.get_share(note_id, target_user.id)
        if share:
            await self._share_repo.delete(share)