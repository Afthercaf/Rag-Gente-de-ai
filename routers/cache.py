from fastapi import APIRouter, Depends

from core.cache import response_cache
from core.security import CurrentUser, require_roles


router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/stats")
async def cache_stats(
    current_user: CurrentUser = Depends(require_roles("admin")),
):
    # No exponer model_loaded/api_ready.
    return {"cache_size": response_cache.size()}


@router.post("/clear")
async def clear_cache(
    current_user: CurrentUser = Depends(require_roles("admin")),
):
    response_cache.clear()
    return {"success": True, "message": "Caché limpiada"}
