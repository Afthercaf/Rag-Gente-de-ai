import time

from fastapi import APIRouter

from core.state import state

router = APIRouter(tags=["health"])


@router.get("/")
async def root():
    return {
        "name": "Pizzería 220 AI API",
        "version": "2.0.0",
        "status": "running",
        "ready": state["ready"],
        "docs": "/docs",
    }


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "ready": state["ready"],
        "model_loaded": state["model_loaded"],
        "uptime_seconds": round(time.time() - state["startup_time"], 2),
    }


@router.get("/ready")
async def readiness():
    from core.cache import response_cache

    return {
        "ready": state["ready"],
        "cache_size": response_cache.size(),
        "model_loaded": state["model_loaded"],
    }
