import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.note import Note
    from app.models.token import RefreshToken
    from app.models.share import NoteShare


class User(BaseModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,       # B-tree index — every auth lookup hits this
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Relationships ──────────────────────────────────────────────────────────
    notes: Mapped[list["Note"]] = relationship(
        "Note",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="raise",     # prevent accidental N+1: must be explicitly loaded
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    # Notes shared WITH this user by others
    received_shares: Mapped[list["NoteShare"]] = relationship(
        "NoteShare",
        foreign_keys="NoteShare.shared_with_user_id",
        back_populates="shared_with_user",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    # ── Composite indexes ──────────────────────────────────────────────────────
    __table_args__ = (
        # Partial index: only active users — lookup is cheaper as inactive
        # users accumulate over time.
        Index("ix_users_email_active", "email", postgresql_where=mapped_column("is_active")),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"