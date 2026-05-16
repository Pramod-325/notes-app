import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.note import Note
    from app.models.user import User


class NoteShare(BaseModel):
    __tablename__ = "note_shares"

    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False,
    )
    shared_with_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,   # GET /notes (shared tab) filters on this
    )
    shared_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Forward-looking: 'read' only for now; 'write' can be added later
    # without a schema change.
    permission: Mapped[str] = mapped_column(
        String(20), nullable=False, default="read"
    )
    shared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    note: Mapped["Note"] = relationship("Note", back_populates="shares", lazy="raise")
    shared_with_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[shared_with_user_id],
        back_populates="received_shares",
        lazy="raise",
    )
    shared_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[shared_by_user_id],
        lazy="raise",
    )

    __table_args__ = (
        # Idempotency guarantee: sharing the same note with the same user twice
        # is a no-op at the DB level, not a duplicate row.
        UniqueConstraint(
            "note_id",
            "shared_with_user_id",
            name="uq_note_shares_note_user",
        ),
        # Composite index for the shared notes list query:
        # WHERE shared_with_user_id = ? ORDER BY shared_at DESC
        Index("ix_note_shares_user_shared_at", "shared_with_user_id", "shared_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<NoteShare note_id={self.note_id} "
            f"shared_with={self.shared_with_user_id}>"
        )