"""
ExportService — generate a ZIP archive of a user's notes as plain text files.

Design:
  - Fully in-memory using io.BytesIO — no disk I/O, no temp files.
    Safe on Render's ephemeral filesystem and within free-tier RAM limits
    for typical note volumes.
  - Each note becomes a .txt file: sanitised_title.txt
  - Duplicate titles are disambiguated with a numeric suffix.
  - The ZIP is streamed back via FastAPI's StreamingResponse, so large
    archives don't buffer the entire response in memory before sending.

File naming algorithm:
  - Sanitise title: strip non-alphanumeric chars, replace spaces with '_',
    truncate to 80 chars.
  - Track used names in a set for O(1) collision detection.
  - Append _2, _3, ... until the name is unique.
"""

import io
import zipfile
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.note_repo import NoteRepository


class ExportService:

    def __init__(self, session: AsyncSession) -> None:
        self._note_repo = NoteRepository(session)

    async def export_notes_as_zip(self, user: User) -> bytes:
        """
        Fetch all active notes for `user` and package them as a ZIP.

        Returns raw ZIP bytes — the router wraps this in a StreamingResponse.
        Fetches all notes in one query (no pagination) since this is an export.
        Notes are sorted alphabetically by title for predictable archive order.
        """
        # Fetch all active notes for the user — large limit to get everything
        notes, _ = await self._note_repo.list_by_owner(
            owner_id=user.id,
            offset=0,
            limit=10_000,   # practical upper bound; revisit if users hit this
        )

        # Sort alphabetically by title for deterministic archive structure
        notes.sort(key=lambda n: n.title.lower())

        buffer = io.BytesIO()
        used_names: set[str] = set()

        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for note in notes:
                filename = self._make_filename(note.title, used_names)
                used_names.add(filename)
                content = self._format_note(note.title, note.content, note.updated_at)
                zf.writestr(filename, content.encode("utf-8"))

        buffer.seek(0)
        return buffer.read()

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _sanitise_title(title: str) -> str:
        """
        Convert a note title to a safe filename stem.
        - Strip leading/trailing whitespace
        - Replace runs of whitespace with '_'
        - Remove characters not safe in filenames (/ \\ : * ? " < > |)
        - Truncate to 80 chars to keep paths short
        - Fall back to 'untitled' if nothing remains
        """
        safe = re.sub(r"[\\/:*?\"<>|]", "", title.strip())
        safe = re.sub(r"\s+", "_", safe)
        safe = safe[:80].rstrip("_") or "untitled"
        return safe

    @classmethod
    def _make_filename(cls, title: str, used: set[str]) -> str:
        """
        Generate a unique .txt filename.
        Collision resolution: append _2, _3, ... until unique.
        O(1) per check via set lookup.
        """
        stem = cls._sanitise_title(title)
        candidate = f"{stem}.txt"

        if candidate not in used:
            return candidate

        # Disambiguation loop — O(k) where k = number of duplicate titles
        counter = 2
        while True:
            candidate = f"{stem}_{counter}.txt"
            if candidate not in used:
                return candidate
            counter += 1

    @staticmethod
    def _format_note(title: str, content: str, updated_at) -> str:
        """
        Format a note as a human-readable plain text file.
        Includes a header with title and last-updated timestamp.
        """
        separator = "=" * 60
        return (
            f"{separator}\n"
            f"Title   : {title}\n"
            f"Updated : {updated_at.strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"{separator}\n\n"
            f"{content}\n"
        )