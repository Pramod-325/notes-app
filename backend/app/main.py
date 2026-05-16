from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import about, auth, notes, shares
from app.core.config import settings
from app.core.exceptions import AppException

# Initialize the FastAPI app
# We configure OpenAPI schema to meet the documentation requirements.
app = FastAPI(
    title="Notes API",
    description="A robust, offline-first ready monolith API for a basic note-taking application.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# ── CORS Configuration ────────────────────────────────────────────────────────
# Allowing frontend origins (e.g., localhost, Github Pages, Vercel)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception Handling ────────────────────────────────────────────────────────
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """
    Global exception handler for all application-level errors.
    Catches NotFoundError, ForbiddenError, etc., and formats them gracefully.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )

# ── Routers ───────────────────────────────────────────────────────────────────
# Include all endpoints under the /api/v1 prefix
app.include_router(auth.router, prefix="/api/v1")
app.include_router(notes.router, prefix="/api/v1")
app.include_router(shares.router, prefix="/api/v1")
app.include_router(about.router, prefix="/api/v1")

# ── Root Endpoint ─────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "online",
        "message": "Welcome to the Notes API. Visit /docs for the API documentation.",
        "environment": settings.APP_ENV
    }