"""
Abstract ORM base model.

Every table inherits:
    id          — UUID v4 primary key (generated server-side, not DB-side)
    created_at  — set on INSERT, never updated
    updated_at  — updated automatically on every UPDATE via onupdate hook

Using UUIDs instead of serial integers:
    - Safe to generate client-side (no round-trip needed for the PK value)
    - No information leakage about row count or insertion order
    - Safe to merge data across DB instances if we ever need to
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TimestampMixin:
    """
    Provides created_at / updated_at columns.
    Kept as a separate mixin so it can be applied selectively if needed.

    server_default=func.now()  → DB sets the value on INSERT (no Python round-trip)
    onupdate=func.now()        → DB sets the value on every UPDATE automatically
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class BaseModel(TimestampMixin, Base):
    """
    Abstract base for all application tables.
    Provides: id (UUID PK), created_at, updated_at.
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        # Generate UUID in Python (not the DB) so we know the PK
        # before flushing — useful for building response objects immediately.
        default=uuid.uuid4,
        nullable=False,
    )