from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from core.security import CurrentUser, create_access_token, get_current_user
from services import auth_service


router = APIRouter(prefix="/auth", tags=["auth"])


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


class TokenResponse(BaseModel):
    success: Literal[True] = True
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: dict


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequestSecure):
    result = await auth_service.register(
        nombre=req.nombre,
        telefono=req.telefono,
        gmail=str(req.gmail),
        direccion=req.direccion,
        password=req.password,
    )

    # Nunca devolver password/password_hash aunque el servicio legado lo haga.
    if isinstance(result, dict):
        user = result.get("user")
        if isinstance(user, dict):
            user.pop("password", None)
            user.pop("password_hash", None)

    return result


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequestSecure, response: Response):
    user = await auth_service.login(
        gmail=str(req.gmail),
        password=req.password,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
        )

    internal_id = int(user["id"])
    role = str(user.get("role") or "cliente")
    token = create_access_token(
        internal_user_id=internal_id,
        role=role,
    )

    # Se elimina la cookie insegura con ID entero.
    response.delete_cookie(key="session")

    return TokenResponse(
        access_token=token,
        expires_in=60 * 60,
        user={
            "id": str(__import__("core.security", fromlist=["public_user_uuid"])
                      .public_user_uuid(internal_id)),
            "nombre": user.get("nombre"),
            "gmail": user.get("gmail"),
            "telefono": user.get("telefono"),
            "direccion": user.get("direccion"),
            "role": role,
        },
    )


@router.get("/me")
async def me(current_user: CurrentUser = Depends(get_current_user)):
    return {
        "id": str(current_user.public_id),
        "role": current_user.role,
    }


@router.post("/logout")
async def logout(
    response: Response,
    current_user: CurrentUser = Depends(get_current_user),
):
    # JWT stateless: el cliente debe borrar el token.
    # Para revocación inmediata, almacenar jti en Redis hasta exp.
    response.delete_cookie(key="session")
    return {
        "success": True,
        "message": "Token eliminado en el cliente",
    }
