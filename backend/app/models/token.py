import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class RefreshToken(BaseModel):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # SHA-256 hex digest of the raw token (64 chars).
    # We never store the raw token — a DB breach cannot be used to hijack sessions.
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,     # B-tree unique index for O(log n) lookup by hash
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Soft-revoke: set to True on logout or when a new refresh token is issued
    # (token rotation). Revoked tokens are rejected even before their expiry.
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Relationship ───────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(
        "User", back_populates="refresh_tokens", lazy="raise"
    )

    __table_args__ = (
        # Partial index: only non-revoked, non-expired tokens need fast lookup.
        # Revoked tokens are historical — they don't need index coverage.
        Index(
            "ix_refresh_tokens_hash_active",
            "token_hash",
            postgresql_where=~mapped_column("revoked"),
        ),
    )

    def __repr__(self) -> str:
        return f"<RefreshToken user_id={self.user_id} revoked={self.revoked}>"