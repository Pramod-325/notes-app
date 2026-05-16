from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_refresh_token_from_cookie
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.token import TokenResponse
from app.schemas.user import LoginRequest, UserCreate, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])

# ── Helpers ────────────────────────────────────────────────────────────────────

def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    """
    Set the refresh token as an HttpOnly, Secure, SameSite=Lax cookie.

    HttpOnly  → inaccessible to JavaScript (prevents XSS theft)
    Secure    → transmitted only over HTTPS (enforced in production)
    SameSite  → Lax prevents CSRF while allowing top-level navigations
    max_age   → matches the DB token expiry
    """
    response.set_cookie(
        key="refresh_token",
        value=raw_token,
        httponly=True,
        secure=settings.is_production,   # Secure only in prod (allows localhost dev)
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86_400,
        path="/api/v1/auth",             # scoped to auth routes only
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    return await AuthService(db).register(payload)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and receive an access token",
)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    svc = AuthService(db)
    token_response, raw_refresh = await svc.login(payload.email, payload.password)
    _set_refresh_cookie(response, raw_refresh)
    return token_response


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Exchange a refresh token for a new access token",
)
async def refresh_token(
    response: Response,
    raw_refresh: str = Depends(get_refresh_token_from_cookie),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    svc = AuthService(db)
    token_response, new_raw_refresh = await svc.refresh(raw_refresh)
    _set_refresh_cookie(response, new_raw_refresh)
    return token_response


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke all sessions for the current user",
)
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await AuthService(db).logout(current_user)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Logged out successfully.")