from fastapi import APIRouter

router = APIRouter(tags=["Meta"])


@router.get("/about", summary="About this API")
async def about() -> dict:
    return {
        "name": "Notes API",
        "email": "scivjoy7@gmail.com",
        "my_features": {
            "paginated_notes": (
                "GET /notes returns paginated results with page/size query params. "
                "Uses a SQL window function to fetch items + total count in one DB round-trip."
            ),
            "soft_delete": (
                "Notes are soft-deleted (is_deleted flag) rather than hard-removed. "
                "Handles the Delete/Update collision edge case: a concurrent offline edit "
                "receives 410 Gone instead of silently overwriting a deletion."
            ),
            "token_rotation": (
                "Refresh tokens are rotated on every use — the old token is revoked "
                "immediately. Prevents replay attacks and stolen-token reuse."
            ),
            "idempotent_sharing": (
                "Sharing a note with the same user twice is a no-op (PostgreSQL "
                "INSERT ... ON CONFLICT DO NOTHING). No duplicate shares, no errors."
            ),
            "zip_export": (
                "GET /notes/export streams a ZIP archive of all notes as .txt files. "
                "Fully in-memory — no disk I/O. Duplicate titles are disambiguated."
            ),
            "search": (
                "GET /notes?search=keyword performs case-insensitive ILIKE on title "
                "and content. Pagination is fully supported alongside search."
            ),
            "content_size_limit": (
                "Note content is capped at 1 MB. Validated at both the Pydantic schema "
                "layer and the service layer (defence in depth), returning 413."
            ),
            "refresh_token_cookie": (
                "Refresh tokens are stored in HttpOnly, Secure, SameSite=Lax cookies — "
                "inaccessible to JavaScript, preventing XSS-based session hijacking."
            ),
        },
    }