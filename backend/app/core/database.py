"""
Async SQLAlchemy engine configured for NeonDB + PgBouncer.

Architecture (as discussed):
  App (SQLAlchemy NullPool) → Neon PgBouncer (transaction mode) → Neon Postgres

NullPool means SQLAlchemy never holds idle connections open. Each request
acquires a connection from PgBouncer's pool, uses it for the transaction,
and immediately releases it. This is the correct pattern for:
  - Serverless / sleep-wake backends (Render)
  - PgBouncer in transaction mode (which prohibits session-level features anyway)
  - Neon's connection-count billing model
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings


# ── Engine ─────────────────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.DATABASE_URL,
    # No app-side connection pool — Neon PgBouncer handles pooling server-side.
    poolclass=NullPool,
    # Echo SQL in development for visibility; never in production.
    echo=settings.DEBUG and not settings.is_production,
    # asyncpg-specific: ensure SSL is used for Neon connections.
    connect_args={"ssl": "require"} if settings.is_production else {},
)

# ── Session factory ────────────────────────────────────────────────────────────

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    # expire_on_commit=False is REQUIRED for async SQLAlchemy.
    # With True (the default), accessing any ORM attribute after commit()
    # triggers a lazy SQL load — which raises MissingGreenlet in async context
    # because there is no implicit IO loop to resume on.
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── ORM declarative base ───────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """
    Shared declarative base for all ORM models.
    All model classes inherit from this — Alembic autogenerate
    discovers them by scanning Base.metadata.
    """
    pass


# ── Dependency ─────────────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session per request.

    Transaction lifecycle:
        - commit()   on clean exit
        - rollback() on any exception (prevents partial writes)
        - session is always closed, releasing the PgBouncer slot

    Usage:
        @router.get("/")
        async def handler(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        # session.__aexit__ closes automatically — no explicit close needed