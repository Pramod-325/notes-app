import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.share import NoteShare


class Note(BaseModel):
    __tablename__ = "notes"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,       # nearly every note query filters on owner_id
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    # Text (unbounded in Postgres) — content size is enforced at the service
    # layer via MAX_NOTE_CONTENT_BYTES, not at the DB column level, so we
    # can return a 413 with a helpful message rather than a DB error.
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # ── Soft delete ────────────────────────────────────────────────────────────
    # is_deleted=True means logically removed. The row is retained so that:
    #   1. A concurrent offline EDIT that arrives after a DELETE gets a 410 Gone
    #      instead of a silent overwrite (Delete/Update collision edge case).
    #   2. Accidental deletions can be recovered (future feature).
    # Hard deletion is handled by a periodic cleanup job (not in this monolith).
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    owner: Mapped["User"] = relationship("User", back_populates="notes", lazy="raise")
    shares: Mapped[list["NoteShare"]] = relationship(
        "NoteShare",
        back_populates="note",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    # ── Indexes ───────────────────────────────────────────────────────────────
    __table_args__ = (
        # Partial index: exclude soft-deleted rows — the vast majority of queries
        # filter WHERE is_deleted = false. This keeps the index small and fast.
        Index(
            "ix_notes_owner_active",
            "owner_id",
            "updated_at",           # secondary sort for pagination by recent
            postgresql_where=~mapped_column("is_deleted"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Note id={self.id} owner_id={self.owner_id} title={self.title!r}>"