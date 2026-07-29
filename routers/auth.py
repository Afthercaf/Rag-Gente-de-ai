from __future__ import annotations

import hashlib
import threading
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from core.security import (
    ACCESS_COOKIE_NAME,
    ACCESS_TOKEN_MINUTES,
    IS_PRODUCTION,
    CurrentUser,
    create_access_token,
    get_current_user,
    public_user_uuid,
    revoke_access_token,
)
from core.client_ip import get_client_ip
from core.refresh_token import (
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
    validate_refresh_token,
)
from services import auth_service


router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_SAMESITE = "none" if IS_PRODUCTION else "lax"
COOKIE_MAX_AGE = ACCESS_TOKEN_MINUTES * 60
REFRESH_COOKIE_MAX_AGE = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
REFRESH_COOKIE_NAME = (
    "__Host-refresh_token"
    if IS_PRODUCTION
    else "refresh_token"
)
MAX_LOGIN_FAILURES = 5
LOGIN_LOCK_SECONDS = 15 * 60
_login_failures: dict[str, tuple[int, float]] = {}
_login_lock = threading.Lock()


def _login_key(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def _assert_not_locked(email: str) -> None:
    key = _login_key(email)
    now = time.monotonic()
    with _login_lock:
        count, locked_until = _login_failures.get(key, (0, 0.0))
        if locked_until > now:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Cuenta bloqueada temporalmente por intentos fallidos",
                headers={"Retry-After": str(max(1, int(locked_until - now)))},
            )
        if locked_until:
            _login_failures.pop(key, None)


def _record_login_failure(email: str) -> None:
    key = _login_key(email)
    with _login_lock:
        count, _ = _login_failures.get(key, (0, 0.0))
        count += 1
        locked_until = (
            time.monotonic() + LOGIN_LOCK_SECONDS
            if count >= MAX_LOGIN_FAILURES
            else 0.0
        )
        _login_failures[key] = (count, locked_until)


def _clear_login_failures(email: str) -> None:
    with _login_lock:
        _login_failures.pop(_login_key(email), None)


class RegisterRequestSecure(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nombre: str = Field(min_length=2, max_length=80)
    telefono: str = Field(pattern=r"^\+?[0-9 ()-]{8,20}$")
    gmail: EmailStr
    direccion: str = Field(min_length=3, max_length=240)
    password: str = Field(min_length=10, max_length=128)


class LoginRequestSecure(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    gmail: EmailStr
    password: str = Field(min_length=1, max_length=128)


class SessionResponse(BaseModel):
    success: Literal[True] = True
    expires_in: int
    user: dict


def _mark_cookie_partitioned(response: Response, cookie_name: str) -> None:
    """Añade CHIPS a cookies cross-site sin depender de Python 3.14."""
    if not IS_PRODUCTION:
        return
    prefix = f"{cookie_name}=".encode("latin-1")
    for index in range(len(response.raw_headers) - 1, -1, -1):
        name, value = response.raw_headers[index]
        if name.lower() == b"set-cookie" and value.startswith(prefix):
            if b"partitioned" not in value.lower():
                response.raw_headers[index] = (name, value + b"; Partitioned")
            return


def _set_auth_cookie(
    response: Response,
    *,
    key: str,
    value: str,
    max_age: int,
) -> None:
    response.set_cookie(
        key=key,
        value=value,
        max_age=max_age,
        httponly=True,
        secure=IS_PRODUCTION,
        samesite=COOKIE_SAMESITE,
        path="/",
    )
    _mark_cookie_partitioned(response, key)


def _set_access_cookie(response: Response, token: str) -> None:
    _set_auth_cookie(
        response,
        key=ACCESS_COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    _set_auth_cookie(
        response,
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=REFRESH_COOKIE_MAX_AGE,
    )


def _delete_auth_cookies(response: Response) -> None:
    for cookie_name in (ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME):
        response.delete_cookie(
            key=cookie_name,
            path="/",
            secure=IS_PRODUCTION,
            httponly=True,
            samesite=COOKIE_SAMESITE,
        )
        _mark_cookie_partitioned(response, cookie_name)
    response.delete_cookie(key="session", path="/")


def _public_user(user: dict, internal_id: int, role: str) -> dict:
    return {
        "id": str(public_user_uuid(internal_id)),
        "nombre": user.get("nombre"),
        "gmail": user.get("gmail"),
        "telefono": user.get("telefono"),
        "direccion": user.get("direccion"),
        "role": role,
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequestSecure):
    result = await auth_service.register(
        nombre=req.nombre,
        telefono=req.telefono,
        gmail=str(req.gmail),
        direccion=req.direccion,
        password=req.password,
    )

    if isinstance(result, dict):
        user = result.get("user")
        if isinstance(user, dict):
            user.pop("password", None)
            user.pop("password_hash", None)

    return result


@router.post("/login", response_model=SessionResponse)
async def login(
    req: LoginRequestSecure,
    response: Response,
    request: Request,
):
    email = str(req.gmail)
    _assert_not_locked(email)
    user = await auth_service.login(
        gmail=email,
        password=req.password,
    )

    if not user:
        _record_login_failure(email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
        )

    _clear_login_failures(email)
    internal_id = int(user["id"])
    role = str(user.get("role") or "cliente")
    token = create_access_token(
        internal_user_id=internal_id,
        role=role,
    )

    _delete_auth_cookies(response)
    _set_access_cookie(response, token)
    _set_refresh_cookie(
        response,
        create_refresh_token(
            internal_id,
            get_client_ip(request),
        ),
    )

    return SessionResponse(
        expires_in=COOKIE_MAX_AGE,
        user=_public_user(user, internal_id, role),
    )


@router.get("/me")
async def me(current_user: CurrentUser = Depends(get_current_user)):
    user = await auth_service.get_profile(current_user.internal_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return _public_user(user, current_user.internal_id, current_user.role)


@router.post("/refresh", response_model=SessionResponse)
async def refresh(
    response: Response,
    request: Request,
):
    current_refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    record = (
        validate_refresh_token(current_refresh_token)
        if current_refresh_token
        else None
    )
    if record is None:
        _delete_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión no puede renovarse",
        )

    rotated_token = rotate_refresh_token(
        current_refresh_token,
        get_client_ip(request),
    )
    if rotated_token is None:
        _delete_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión no puede renovarse",
        )

    internal_id = int(record["user_id"])
    user = await auth_service.get_profile(internal_id)
    if not user:
        revoke_refresh_token(rotated_token)
        _delete_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
        )

    role = str(user.get("role") or "cliente")
    token = create_access_token(
        internal_user_id=internal_id,
        role=role,
    )
    _set_access_cookie(response, token)
    _set_refresh_cookie(response, rotated_token)

    return SessionResponse(
        expires_in=COOKIE_MAX_AGE,
        user=_public_user(user, internal_id, role),
    )


@router.post("/logout")
async def logout(
    response: Response,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
):
    await revoke_access_token(current_user.token_id)
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token:
        revoke_refresh_token(refresh_token)
    _delete_auth_cookies(response)
    return {
        "success": True,
        "message": "Sesión cerrada correctamente",
    }
