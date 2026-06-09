# api.py - Pizzería 220 AI
# Ejecutar con: uvicorn api:app --reload --port 8000

import core.config  # carga .env primero

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from core.lifespan import lifespan
from routers import auth, cache, chat, health, orders
from utils.constants import ALLOWED_ORIGINS

app = FastAPI(
    title="Pizzería 220 AI",
    version="2.0.0",
    lifespan=lifespan,
)

# ── Middlewares ────────────────────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,
)

# ── Routers ────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(auth.router)
app.include_router(orders.router)
app.include_router(cache.router)

# ── Global error handler ───────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    print(f"❌ Error no manejado: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"error": "Error interno del servidor"},
    )

# ── Dev entry point ────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    print("🍕 Pizzería 220 AI API - Versión Modular")
    print("=" * 50)
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
