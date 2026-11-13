from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import models  # noqa: F401  (register model metadata)
from database import init_db
from routes.api import router as api_router
from routes.insights import router as insights_router
from routes.videos import router as videos_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Make sure the database schema exists before serving traffic."""
    try:
        init_db()
    except Exception as exc:  # noqa: BLE001
        print(f"[main] Database init failed: {exc}")
    yield


app = FastAPI(
    title="AudienceIQ API",
    description="AI-Powered Social Media Audience Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
