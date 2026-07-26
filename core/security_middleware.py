from __future__ import annotations

import asyncio
import os
import time
import uuid
from collections import defaultdict, deque
from typing import Deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.security import token_fingerprint


MAX_JSON_BYTES = int(
    os.getenv(
        "MAX_JSON_BYTES",
        str(64 * 1024),
    )
)

MAX_AUDIO_BYTES = int(
    os.getenv(
        "MAX_AUDIO_BYTES",
        str(10 * 1024 * 1024),
    )
)

ALLOWED_ORIGINS = {
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "https://rag-gente-de-ai.onrender.com",
    ).split(",")
    if origin.strip()
}


# Rutas que pueden usarse sin JWT.
PUBLIC_PATHS = {
    "/",
    "/health",
    "/ready",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/auth/login",
    "/auth/register",

    # Proxy de geocodificación y mapa.
    "/maps/reverse",
    "/maps/search",
    "/maps/static",
}


# Máximo de solicitudes y ventana en segundos.
RATE_RULES = {
    "/auth/login": (5, 60),
    "/auth/register": (3, 300),

    "/chat": (30, 60),
    "/order": (10, 60),
    "/payment": (10, 60),
    "/voice/transcribe": (5, 60),

    # Los mapas son públicos, pero deben limitarse
    # para evitar abuso de Nominatim y LocationIQ.
    "/maps/reverse": (20, 60),
    "/maps/search": (20, 60),
    "/maps/static": (30, 60),
}

DEFAULT_RATE_RULE = (60, 60)


_ALLOWED_JSON_TYPES = {
    "application/json",
    "application/merge-patch+json",
}


class InMemorySlidingWindow:
    """
    Rate limiter para una sola instancia.

    En producción con múltiples instancias debe sustituirse
    por Redis para compartir los contadores.
    """

    def __init__(self) -> None:
        self._events: dict[
            str,
            Deque[float],
        ] = defaultdict(deque)

        self._lock = asyncio.Lock()

    async def allow(
        self,
        key: str,
        *,
        maximum: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - window_seconds

        async with self._lock:
            events = self._events[key]

            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= maximum:
                retry_after = max(
                    1,
                    int(
                        window_seconds
                        - (now - events[0])
                    ),
                )

                return False, retry_after

            events.append(now)

            return True, 0


_rate_limiter = InMemorySlidingWindow()


def _rule_for(
    path: str,
) -> tuple[int, int]:
    """
    Obtiene la regla más específica para una ruta.
    """

    matches = [
        (prefix, rule)
        for prefix, rule in RATE_RULES.items()
        if (
            path == prefix
            or path.startswith(f"{prefix}/")
        )
    ]

    if not matches:
        return DEFAULT_RATE_RULE

    return max(
        matches,
        key=lambda item: len(item[0]),
    )[1]


def _error_response(
    *,
    status_code: int,
    detail: str,
    request_id: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """
    Genera errores consistentes y evita olvidar
    los encabezados básicos de seguridad.
    """

    response_headers = {
        "X-Request-ID": request_id,
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }

    if headers:
        response_headers.update(headers)

    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "detail": detail,
            "request_id": request_id,
        },
        headers=response_headers,
    )


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        request_id = request.headers.get(
            "x-request-id"
        )

        try:
            request_id = str(
                uuid.UUID(str(request_id))
            )
        except (TypeError, ValueError):
            request_id = str(uuid.uuid4())

        request.state.request_id = request_id

        path = request.url.path
        method = request.method.upper()

        origin = request.headers.get("origin")
        normalized_origin = (
            origin.rstrip("/")
            if origin
            else None
        )

        # Nunca reflejar orígenes arbitrarios.
        if (
            normalized_origin
            and normalized_origin
            not in ALLOWED_ORIGINS
        ):
            return _error_response(
                status_code=403,
                detail="Origen no permitido",
                request_id=request_id,
            )

        # Las solicitudes preflight deben pasar al
        # CORSMiddleware y no consumir rate limit.
        if method == "OPTIONS":
            response = await call_next(request)
            self._apply_security_headers(
                response=response,
                request_id=request_id,
                origin=normalized_origin,
            )
            return response

        # Validación de contenido antes de los routers.
        if method in {
            "POST",
            "PUT",
            "PATCH",
        }:
            content_type = (
                request.headers
                .get("content-type", "")
                .split(";", 1)[0]
                .strip()
                .lower()
            )

            content_length_raw = (
                request.headers.get(
                    "content-length",
                    "0",
                )
            )

            try:
                content_length = int(
                    content_length_raw
                )
            except ValueError:
                return _error_response(
                    status_code=400,
                    detail="Content-Length inválido",
                    request_id=request_id,
                )

            if content_length < 0:
                return _error_response(
                    status_code=400,
                    detail="Content-Length inválido",
                    request_id=request_id,
                )

            is_voice_upload = (
                path == "/voice/transcribe"
            )

            if is_voice_upload:
                if not content_type.startswith(
                    "multipart/form-data"
                ):
                    return _error_response(
                        status_code=415,
                        detail=(
                            "Se requiere "
                            "multipart/form-data"
                        ),
                        request_id=request_id,
                    )

                if content_length > MAX_AUDIO_BYTES:
                    return _error_response(
                        status_code=413,
                        detail=(
                            "Archivo demasiado grande"
                        ),
                        request_id=request_id,
                    )

            elif content_type not in _ALLOWED_JSON_TYPES:
                return _error_response(
                    status_code=415,
                    detail=(
                        "Solo se acepta "
                        "application/json"
                    ),
                    request_id=request_id,
                )

            elif content_length > MAX_JSON_BYTES:
                return _error_response(
                    status_code=413,
                    detail=(
                        "Solicitud demasiado grande"
                    ),
                    request_id=request_id,
                )

        # Rate limit por token y, sin token, por IP.
        maximum, window_seconds = _rule_for(
            path
        )

        identity = token_fingerprint(request)

        allowed, retry_after = (
            await _rate_limiter.allow(
                (
                    f"{identity}:"
                    f"{method}:"
                    f"{path}"
                ),
                maximum=maximum,
                window_seconds=window_seconds,
            )
        )

        if not allowed:
            return _error_response(
                status_code=429,
                detail="Demasiadas solicitudes",
                request_id=request_id,
                headers={
                    "Retry-After": str(
                        retry_after
                    ),
                },
            )

        response = await call_next(request)

        self._apply_security_headers(
            response=response,
            request_id=request_id,
            origin=normalized_origin,
        )

        return response

    @staticmethod
    def _apply_security_headers(
        *,
        response,
        request_id: str,
        origin: str | None,
    ) -> None:
        response.headers[
            "X-Request-ID"
        ] = request_id

        response.headers[
            "X-Content-Type-Options"
        ] = "nosniff"

        response.headers[
            "X-Frame-Options"
        ] = "DENY"

        response.headers[
            "Referrer-Policy"
        ] = "no-referrer"

        response.headers[
            "Permissions-Policy"
        ] = (
            "camera=(), "
            "geolocation=(self), "
            "microphone=(self)"
        )

        response.headers[
            "Content-Security-Policy"
        ] = (
            "default-src 'none'; "
            "frame-ancestors 'none'; "
            "base-uri 'none'"
        )

        # El mapa estático sí puede almacenarse brevemente.
        # Las demás respuestas permanecen sin caché.
        response.headers.setdefault(
            "Cache-Control",
            "no-store",
        )

        response.headers[
            "Strict-Transport-Security"
        ] = (
            "max-age=31536000; "
            "includeSubDomains"
        )

        if (
            origin
            and origin in ALLOWED_ORIGINS
        ):
            response.headers[
                "Access-Control-Allow-Origin"
            ] = origin

            response.headers[
                "Vary"
            ] = "Origin"