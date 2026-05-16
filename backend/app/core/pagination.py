"""
Generic pagination primitives.

PaginatedResponse[T] is a typed Pydantic model that wraps any list
of items with standard envelope fields. All paginated endpoints return
this structure — consistent, predictable, and type-safe.

PageParams is a reusable FastAPI dependency for parsing ?page= & ?size=
query parameters with sane defaults and upper bounds.
"""

import math
from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

T = TypeVar("T")

# Maximum page size — prevents a single request from fetching unbounded rows.
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


class PageParams:
    """
    FastAPI dependency class for pagination query params.

    Usage:
        @router.get("/notes")
        async def list_notes(page: PageParams = Depends()):
            offset = page.offset
            limit  = page.size
    """

    def __init__(
        self,
        page: int = Query(default=1, ge=1, description="1-based page number"),
        size: int = Query(
            default=DEFAULT_PAGE_SIZE,
            ge=1,
            le=MAX_PAGE_SIZE,
            description=f"Items per page (max {MAX_PAGE_SIZE})",
        ),
    ) -> None:
        self.page = page
        self.size = size

    @property
    def offset(self) -> int:
        """SQL OFFSET — zero-based."""
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        return self.size


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Standard pagination envelope returned by all list endpoints.

    Generic over T so the OpenAPI schema reflects the actual item type:
        PaginatedResponse[NoteResponse]  →  items: list[NoteResponse]
    """

    items: list[T]
    total: int = Field(description="Total matching records across all pages")
    page: int = Field(description="Current page (1-based)")
    size: int = Field(description="Page size used for this response")
    pages: int = Field(description="Total number of pages")

    @classmethod
    def build(cls, items: list[T], total: int, params: PageParams) -> "PaginatedResponse[T]":
        pages = max(1, math.ceil(total / params.size)) if total else 1
        return cls(
            items=items,
            total=total,
            page=params.page,
            size=params.size,
            pages=pages,
        )