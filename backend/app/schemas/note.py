import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings


def _check_content_size(v: str) -> str:
    """
    Validate content byte size before it reaches the DB.
    Returns a 413 (via PayloadTooLargeError in the service) if exceeded.
    We measure bytes, not characters, because multi-byte Unicode chars
    would slip under a character-count limit but still blow the DB row budget.
    """
    size = len(v.encode("utf-8"))
    if size > settings.MAX_NOTE_CONTENT_BYTES:
        limit_kb = settings.MAX_NOTE_CONTENT_BYTES // 1024
        raise ValueError(
            f"Note content exceeds the {limit_kb} KB limit "
            f"({size:,} bytes received)."
        )
    return v


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(default="", max_length=2_000_000)

    _validate_content = field_validator("content")(_check_content_size)


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    content: str | None = Field(default=None, max_length=2_000_000)

    _validate_content = field_validator("content")(_check_content_size)


class NoteResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    title: str
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SharedNoteResponse(NoteResponse):
    """
    Extended note response for the shared-notes tab.
    Includes who shared it and what permission was granted.
    """
    shared_by_email: str
    permission: str