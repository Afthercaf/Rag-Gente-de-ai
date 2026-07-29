from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import require_env
from core.client_ip import get_client_ip
from core.security import IS_PRODUCTION, token_fingerprint


logger = logging.getLogger(__name__)


def _redis_url() -> str:
    """Construye la URL de Redis sin exponer la contraseña en un solo lugar.

    VULN-04: Preferir variables separadas; REDIS_URL solo como override.
    """
    if os.getenv("REDIS_URL"):
        return os.getenv("REDIS_URL")
    host = os.getenv("REDIS_HOST", "redis")
    port = int(os.getenv("REDIS_PORT", "6379"))
    db = int(os.getenv("REDIS_DB", "0"))
    password = require_env("REDIS_PASSWORD")
    return f"redis://:{password}@{host}:{port}/{db}"



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

_allowed_origins_raw = os.getenv("ALLOWED_ORIGINS")
if not _allowed_origins_raw:
    raise RuntimeError(
        "ALLOWED_ORIGINS debe estar configurada en el entorno."
    )
ALLOWED_ORIGINS = {
    origin.strip().rstrip("/")
    for origin in _allowed_origins_raw.split(",")
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
    "/auth/logout",
    "/mp/callback",

    # Proxy de geocodificación y mapa.
}


# Patrones de rutas que nunca deben ser servidas por la aplicación.
# Protegen contra fugas accidentales de archivos sensibles como .env
_SENSITIVE_PATH_PATTERNS = {
    ".env",
    ".env.",
    ".git",
    ".gitignore",
    ".dockerignore",
    "config.json",
    "secrets.json",
    "id_rsa",
    "id_ed25519",
    "private.key",
    "docker-compose.override.yml",
}


def _is_sensitive_path(path: str) -> bool:
    """
    Determina si una ruta intenta acceder a archivos sensibles.

    Se usa para bloquear solicitudes como GET /.env, GET /.env.local,
    GET /.git/config, etc., incluso si el servidor no las sirve
    directamente.
    """

    lower_path = path.lower()

    # Normalizar: asegurar que empiece con /.
    if not lower_path.startswith("/"):
        lower_path = f"/{lower_path}"

    for pattern in _SENSITIVE_PATH_PATTERNS:
        if pattern in lower_path:
            return True

    return False


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


class RedisSlidingWindow:
    """
    Rate limiter distribuido basado en Redis Sorted Sets.

    VULN-10: comparte contadores entre instancias para evitar bypass
    del rate limit en despliegues con múltiples réplicas.
    """

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis = None
        self._lock = asyncio.Lock()

    @property
    def redis(self):
        if self._redis is None:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )
        return self._redis

    async def allow(
        self,
        key: str,
        *,
        maximum: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        now = time.time()
        cutoff = now - window_seconds

        try:
            r = self.redis
            async with self._lock:
                pipe = r.pipeline()
                pipe.zremrangebyscore(key, "-inf", cutoff)
                pipe.zcard(key)
                pipe.zadd(key, {str(now): now})
                pipe.expire(key, window_seconds)
                _, current_count, _, _ = await pipe.execute()

            if current_count >= maximum:
                # Calcular retry_after basado en el evento más antiguo.
                oldest = await r.zrange(key, 0, 0, withscores=True)
                if oldest:
                    retry_after = max(
                        1,
                        int(window_seconds - (now - oldest[0][1])),
                    )
                else:
                    retry_after = window_seconds
                return False, retry_after

            return True, 0
        except Exception as exc:
            # En caso de fallo de Redis, no bloquear tráfico legítimo.
            # Se registra la incidencia para monitoreo.
            logger.warning(
                "Redis rate limiter no disponible, permitiendo solicitud: %s",
                exc,
            )
            return True, 0


_rate_limiter = RedisSlidingWindow(_redis_url())


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

        # Bloquear explícitamente cualquier intento de acceso a
        # archivos sensibles (.env, .git, claves privadas, etc.).
        if _is_sensitive_path(path):
            logger.warning(
                "Intento de acceso a recurso sensible bloqueado | "
                "path=%s | ip=%s | request_id=%s",
                path,
                get_client_ip(request),
                request_id,
            )
            return _error_response(
                status_code=404,
                detail="Recurso no encontrado",
                request_id=request_id,
                headers={"Cache-Control": "no-store"},
            )

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
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

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

        # VULN-26/27/28: HSTS solo en producción; X-XSS-Protection desactivado
        # (los navegadores modernos usan CSP como defensa principal).
        if IS_PRODUCTION:
            response.headers[
                "Strict-Transport-Security"
            ] = (
                "max-age=31536000; "
                "includeSubDomains"
            )

        response.headers["X-XSS-Protection"] = "0"

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
