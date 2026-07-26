# api2.py - Pizzería 220 AI
# Ejecutar con:
# uvicorn api2:app --reload --port 8000

from __future__ import annotations

import logging
import os
import uuid

import core.config  # Carga las variables de entorno antes que los demás módulos.

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from core.lifespan import lifespan
from core.security_middleware import (
    ALLOWED_ORIGINS,
    SecurityMiddleware,
)
from routers import (
    auth,
    cache,
    chat,
    health,
    maps,
    orders,
    payment,
    voice,
)

logger = logging.getLogger(__name__)

ENVIRONMENT = os.getenv(
    "ENV",
    "development",
).strip().lower()

IS_PRODUCTION = ENVIRONMENT == "production"


app = FastAPI(
    title="Pizzería 220 AI",
    version="2.1.0",
    lifespan=lifespan,

    # Swagger y ReDoc no deben quedar públicos en producción.
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)


# ─────────────────────────────────────────────────────────────
# Manejador seguro de errores de validación
# ─────────────────────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    Evita que FastAPI/Pydantic devuelva el contenido original
    recibido en el body.

    Esto impide exponer contraseñas, tokens u otros datos
    sensibles dentro del campo "input" de los errores 422.
    """

    safe_errors = [
        {
            "type": error.get("type"),
            "loc": error.get("loc"),
            "msg": error.get("msg"),
        }
        for error in exc.errors()
    ]

    request_id = getattr(
        request.state,
        "request_id",
        None,
    )

    if not request_id:
        request_id = request.headers.get(
            "x-request-id"
        )

    try:
        request_id = str(
            uuid.UUID(str(request_id))
        )
    except (TypeError, ValueError):
        request_id = str(uuid.uuid4())

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "detail": safe_errors,
            "request_id": request_id,
        },
        headers={
            "X-Request-ID": request_id,
            "Cache-Control": "no-store",
        },
    )


# ─────────────────────────────────────────────────────────────
# Middlewares
# ─────────────────────────────────────────────────────────────

app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_ORIGINS),
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
    ],
    expose_headers=[
        "X-Request-ID",
        "Retry-After",
    ],
    max_age=3600,
)


app.add_middleware(SecurityMiddleware)


# ─────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────

# Endpoints públicos básicos.
app.include_router(health.router)
app.include_router(auth.router)

# Mapas y geocodificación.
app.include_router(maps.router)

# Endpoints protegidos.
app.include_router(chat.router)
app.include_router(orders.router)
app.include_router(payment.router)
app.include_router(voice.router)
app.include_router(cache.router)


# ─────────────────────────────────────────────────────────────
# Manejador global
# ─────────────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Evita exponer stack traces o detalles internos al cliente.
    """

    request_id = getattr(
        request.state,
        "request_id",
        None,
    )

    if not request_id:
        request_id = request.headers.get(
            "x-request-id"
        )

    try:
        request_id = str(
            uuid.UUID(str(request_id))
        )
    except (TypeError, ValueError):
        request_id = str(uuid.uuid4())

    logger.exception(
        "Error no manejado | request_id=%s | method=%s | path=%s",
        request_id,
        request.method,
        request.url.path,
        exc_info=exc,
    )

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Error interno del servidor",
            "request_id": request_id,
        },
        headers={
            "X-Request-ID": request_id,
            "Cache-Control": "no-store",
        },
    )


# ─────────────────────────────────────────────────────────────
# Dev entry point
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    logger.info("Pizzería 220 AI API")
    logger.info(
        "Entorno: %s",
        ENVIRONMENT,
    )
    logger.info(
        "Documentación activa: %s",
        not IS_PRODUCTION,
    )

    uvicorn.run(
        "api2:app",
        host="0.0.0.0",
        port=int(
            os.getenv("PORT", "8000")
        ),
        reload=not IS_PRODUCTION,
        log_level=os.getenv(
            "LOG_LEVEL",
            "info",
        ).lower(),

        server_header=False,
        date_header=False,

        limit_concurrency=int(
            os.getenv(
                "UVICORN_LIMIT_CONCURRENCY",
                "100",
            )
        ),

        limit_max_requests=int(
            os.getenv(
                "UVICORN_LIMIT_MAX_REQUESTS",
                "1000",
            )
        ),

        timeout_keep_alive=int(
            os.getenv(
                "UVICORN_KEEP_ALIVE",
                "5",
            )
        ),
    )