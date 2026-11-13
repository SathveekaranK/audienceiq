import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

import models  # noqa: F401  (register model metadata)
from database import init_db
from routes.api import router as api_router
from routes.insights import router as insights_router
from routes.videos import router as videos_router

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ENVIRONMENT = os.getenv("ENV", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"

# Exact origins only. The old `allow_origin_regex` matched every port on
# localhost, which - combined with `allow_credentials=True` - let any local
# process make credentialed cross-origin calls to the API.
DEFAULT_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def allowed_origins() -> list:
    """Origins the API accepts, from the ALLOWED_ORIGINS env variable."""
    raw = os.getenv("ALLOWED_ORIGINS", "")
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or DEFAULT_ORIGINS


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Make sure the database schema exists before serving traffic."""
    init_db()
    yield


app = FastAPI(
    title="AudienceIQ API",
    description="AI-Powered Social Media Audience Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan,
    # The interactive docs publish the full endpoint inventory - only serve
    # them outside production.
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

# CORS middleware - exact origin allow-list, no credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add the standard hardening headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
        response.headers.setdefault("Cache-Control", "no-store")
        return response


app.add_middleware(SecurityHeadersMiddleware)

# Include API routes
# api_router is registered first so that literal paths like /creators/search
# win over parameterised ones like /creators/{creator_id}.
app.include_router(api_router)
app.include_router(insights_router)
app.include_router(videos_router)


@app.get("/")
async def root():
    return {"message": "AudienceIQ API is running", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=not IS_PRODUCTION,
    )
