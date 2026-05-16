import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.pagination import PageParams, PaginatedResponse
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.note import SharedNoteResponse
from app.schemas.share import ShareNoteRequest, ShareNoteResponse
from app.services.share_service import ShareService

router = APIRouter(tags=["Shares"])


@router.post(
    "/notes/{note_id}/share",
    response_model=ShareNoteResponse,
    status_code=status.HTTP_200_OK,
    summary="Share a note with another user by email",
)
async def share_note(
    note_id: uuid.UUID,
    payload: ShareNoteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShareNoteResponse:
    return await ShareService(db).share_note(current_user, note_id, payload)


@router.get(
    "/notes/shared",
    response_model=PaginatedResponse[SharedNoteResponse],
    status_code=status.HTTP_200_OK,
    summary="List notes shared with the authenticated user",
)
async def list_shared_with_me(
    page: PageParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[SharedNoteResponse]:
    return await ShareService(db).list_shared_with_me(current_user, page)


@router.delete(
    "/notes/{note_id}/share/{target_email}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke a share (owner only)",
)
async def revoke_share(
    note_id: uuid.UUID,
    target_email: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await ShareService(db).revoke_share(current_user, note_id, target_email)
    return MessageResponse(message="Share revoked successfully.")