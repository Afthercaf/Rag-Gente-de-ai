from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from core.state import state
from core.session_store import session_store
from core.security import CurrentUser, require_roles
import os


router = APIRouter(tags=["health"])


@router.get("/")
async def root():
    return {
        "name": "Pizzería 220 AI API",
        "status": "running",
    }


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/ready")
async def readiness():
    ready, _ = await _dependency_status()
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"ready": ready},
    )


@router.get("/internal/diagnostics")
async def diagnostics(
    _: CurrentUser = Depends(require_roles("admin")),
):
    ready, dependencies = await _dependency_status()
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"ready": ready, "dependencies": dependencies},
    )


async def _dependency_status() -> tuple[bool, dict[str, bool]]:
    try:
        redis_ready = bool(await session_store.redis.ping())
    except Exception:
        redis_ready = False
    supabase_configured = bool(
        os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY")
    )
    resources_ready = bool(state.get("ready"))
    vector_store_ready = state.get("db") is not None
    ready = (
        resources_ready
        and vector_store_ready
        and redis_ready
        and supabase_configured
    )
    return ready, {
        "vector_store": vector_store_ready,
        "resources": resources_ready,
        "redis": redis_ready,
        "supabase": supabase_configured,
    }
