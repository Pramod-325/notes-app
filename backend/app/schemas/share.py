import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class ShareNoteRequest(BaseModel):
    share_with_email: EmailStr


class ShareNoteResponse(BaseModel):
    message: str
    note_id: uuid.UUID
    shared_with_email: str
    permission: str
    shared_at: datetime