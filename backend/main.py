"""
 FastAPI Application Entry Point
"""

import os
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
# Load environment variables
load_dotenv()
from app import models  # noqa: F401
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Try to create tables on startup; warn if DB is unavailable."""
    try:
        Base.metadata.create_all(bind=engine)
        print("✓ Database connected and tables created.")
    except Exception as e:
        print(f"⚠ Database not available: {e}")
        print("  The API will start, but DB-dependent routes will fail.")
        print("  Make sure PostgreSQL is running and .env is configured.")
    yield


# FastAPI application instance
app = FastAPI(
    title="Multi-Factor Digital ID",
    description=(
        "3-Factor Authentication: Password → Liveness Detection → "
        "Face Recognition → Cognitive Behavioral Verification"
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# CORS  allow the Vite dev server to reach the API

frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
local_ip_url = os.getenv("LOCAL_IP_URL", "http://127.0.0.1:5173")

origins = [
    frontend_url,
    local_ip_url,
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Healthcheck route (useful for quick verification)

@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "message": "Multi-Factor Digital ID API is running"}

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}

# API Routers
from app.routes.auth import router as auth_router
app.include_router(auth_router)

# Run with: python main.py
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
    )
