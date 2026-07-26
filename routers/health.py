from fastapi import APIRouter


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
    return {"ready": True}
