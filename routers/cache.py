from fastapi import APIRouter

from core.cache import response_cache
from core.state import state

router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/stats")
async def cache_stats():
    return {
        "cache_size": response_cache.size(),
        "model_loaded": state["model_loaded"],
        "api_ready": state["ready"],
    }


@router.post("/clear")
async def clear_cache():
    response_cache.clear()
    return {"success": True, "message": "Caché limpiada"}
