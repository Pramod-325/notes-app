import uuid

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.pagination import PageParams, PaginatedResponse
from app.models.user import User
from app.schemas.note import NoteCreate, NoteResponse, NoteUpdate
from app.schemas.common import MessageResponse
from app.services.export_service import ExportService
from app.services.note_service import NoteService

router = APIRouter(prefix="/notes", tags=["Notes"])


@router.get(
    "",
    response_model=PaginatedResponse[NoteResponse],
    status_code=status.HTTP_200_OK,
    summary="List all notes for the authenticated user (paginated)",
)
async def list_notes(
    page: PageParams = Depends(),
    search: str | None = Query(default=None, max_length=200, description="Search in title and content"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[NoteResponse]:
    return await NoteService(db).list_notes(current_user, page, search)


@router.post(
    "",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new note",
)
async def create_note(
    payload: NoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    return await NoteService(db).create_note(current_user, payload)


@router.get(
    "/export",
    status_code=status.HTTP_200_OK,
    summary="Export all notes as a ZIP of .txt files",
    response_class=StreamingResponse,
)
async def export_notes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Download all active notes as organised plain text files in a ZIP archive.
    Each note → one .txt file with a sanitised filename.
    Duplicate titles are disambiguated with a numeric suffix.
    """
    zip_bytes = await ExportService(db).export_notes_as_zip(current_user)
    filename = f"notes_export_{current_user.id}.zip"
    return StreamingResponse(
        iter([zip_bytes]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{note_id}",
    response_model=NoteResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a specific note by ID",
)
async def get_note(
    note_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    return await NoteService(db).get_note(current_user, note_id)


@router.put(
    "/{note_id}",
    response_model=NoteResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a note (owner only)",
)
async def update_note(
    note_id: uuid.UUID,
    payload: NoteUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    return await NoteService(db).update_note(current_user, note_id, payload)


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a note (soft delete, owner only)",
)
async def delete_note(
    note_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await NoteService(db).delete_note(current_user, note_id)