from __future__ import annotations

import hashlib
import os
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))
PUBLIC_ID_NAMESPACE = uuid.UUID(
    os.getenv(
        "PUBLIC_ID_NAMESPACE",
        "89c89d59-e115-4897-82fd-e6f5e4f56d11",
    )
)

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    """Identidad confiable derivada exclusivamente del token."""

    internal_id: int
    public_id: uuid.UUID
    role: str
    token_id: str


def _require_secret() -> str:
    if len(JWT_SECRET) < 32:
        raise RuntimeError(
            "JWT_SECRET debe existir y contener al menos 32 caracteres."
        )
    return JWT_SECRET


def public_user_uuid(internal_id: int) -> uuid.UUID:
    """Convierte el ID legado interno en un UUID público no enumerable."""
    return uuid.uuid5(PUBLIC_ID_NAMESPACE, f"user:{int(internal_id)}")


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


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere token Bearer",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)

    return CurrentUser(
        internal_id=int(payload["uid"]),
        public_id=uuid.UUID(str(payload["sub"])),
        role=str(payload.get("role") or "cliente"),
        token_id=str(payload["jti"]),
    )


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
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        raw_token = authorization[7:].strip()
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()[:24]

    client_host = request.client.host if request.client else "unknown"
    return f"ip:{client_host}"
