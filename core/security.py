from __future__ import annotations

import hashlib
import os
import secrets
import time
import uuid
import threading
from dataclasses import dataclass
from typing import Any, Optional

import jwt
import redis.asyncio as redis
from fastapi import Depends, HTTPException, Request, status

from core.config import require_env
from core.client_ip import get_client_ip

JWT_SECRET = require_env("JWT_SECRET", min_length=32)
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = max(60, int(os.getenv("ACCESS_TOKEN_MINUTES", "60")))

_public_id_namespace_raw = require_env("PUBLIC_ID_NAMESPACE")

ENVIRONMENT = os.getenv("ENV", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"
ACCESS_COOKIE_NAME = "__Host-access_token" if IS_PRODUCTION else "access_token"
_revoked_tokens: dict[str, int] = {}
_revocation_lock = threading.Lock()
_revocation_redis = redis.from_url(
    os.getenv("REDIS_URL")
    or (
        "redis://"
        + f":{require_env('REDIS_PASSWORD')}@"
        + f"{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}"
        + f"/{os.getenv('REDIS_DB', '0')}"
    ),
    decode_responses=True,
)


def _public_id_namespace() -> uuid.UUID:
    """Devuelve el namespace para UUID públicos (lazy validation)."""
    raw = os.getenv("PUBLIC_ID_NAMESPACE", _public_id_namespace_raw or "")
    if not raw:
        raise RuntimeError(
            "PUBLIC_ID_NAMESPACE debe estar configurada en el entorno."
        )
    return uuid.UUID(raw)


@dataclass(frozen=True)
class CurrentUser:
    """Identidad confiable derivada exclusivamente del token."""

    internal_id: int
    public_id: uuid.UUID
    role: str
    token_id: str


def _require_secret() -> str:
    return JWT_SECRET


def public_user_uuid(internal_id: int) -> uuid.UUID:
    """Convierte el ID legado interno en un UUID público no enumerable."""
    return uuid.uuid5(_public_id_namespace(), f"user:{int(internal_id)}")


def create_access_token(
    *,
    internal_user_id: int,
    role: str = "cliente",
    expires_minutes: Optional[int] = None,
) -> str:
    now = int(time.time())
    ttl = (expires_minutes or ACCESS_TOKEN_MINUTES) * 60
    public_id = public_user_uuid(internal_user_id)

    payload = {
        "sub": str(public_id),
        "uid": int(internal_user_id),  # Solo vive dentro del token firmado.
        "role": role or "cliente",
        "jti": secrets.token_urlsafe(18),
        "iat": now,
        "nbf": now,
        "exp": now + ttl,
        "iss": "pizzeria220-api",
        "aud": "pizzeria220-client",
    }

    return jwt.encode(
        payload,
        _require_secret(),
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            _require_secret(),
            algorithms=[JWT_ALGORITHM],
            audience="pizzeria220-client",
            issuer="pizzeria220-api",
            options={
                "require": ["sub", "uid", "jti", "iat", "nbf", "exp"],
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    try:
        uuid.UUID(str(payload["sub"]))
        int(payload["uid"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token mal formado",
        ) from exc

    return payload


async def get_current_user(request: Request) -> CurrentUser:
    token = request.cookies.get(ACCESS_COOKIE_NAME)

    # Compatibilidad temporal con clientes antiguos que todavía usen Bearer.
    if not token:
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere una sesión válida",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    token_id = str(payload["jti"])
    now = int(time.time())
    revoked = False
    try:
        revoked = bool(await _revocation_redis.exists(f"revoked:jti:{token_id}"))
    except Exception:
        revoked = False
    with _revocation_lock:
        expired = [jti for jti, expiry in _revoked_tokens.items() if expiry <= now]
        for jti in expired:
            _revoked_tokens.pop(jti, None)
        if revoked or token_id in _revoked_tokens:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión revocada",
            )

    return CurrentUser(
        internal_id=int(payload["uid"]),
        public_id=uuid.UUID(str(payload["sub"])),
        role=str(payload.get("role") or "cliente"),
        token_id=token_id,
    )


async def revoke_access_token(token_id: str, expires_at: int | None = None) -> None:
    """Revoca un JWT hasta su expiración sin almacenar el token completo."""
    expiry = expires_at or int(time.time()) + ACCESS_TOKEN_MINUTES * 60
    with _revocation_lock:
        _revoked_tokens[str(token_id)] = expiry
    try:
        await _revocation_redis.setex(
            f"revoked:jti:{token_id}",
            max(1, expiry - int(time.time())),
            "1",
        )
    except Exception:
        # El fallback local mantiene segura una sola instancia.
        pass


def require_roles(*allowed_roles: str):
    allowed = {role.lower() for role in allowed_roles}

    async def dependency(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if current_user.role.lower() not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para esta operación",
            )
        return current_user

    return dependency


def token_fingerprint(request: Request) -> str:
    """Clave estable para rate limiting sin almacenar el token completo."""
    raw_token = request.cookies.get(ACCESS_COOKIE_NAME, "")

    if not raw_token:
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            raw_token = authorization[7:].strip()

    if raw_token:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()[:24]

    client_host = get_client_ip(request)
    return f"ip:{client_host}"
