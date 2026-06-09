from fastapi import APIRouter, Response

from schemas.auth import LoginRequest, RegisterRequest
from services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
async def register(req: RegisterRequest):
    return await auth_service.register(
        nombre=req.nombre,
        telefono=req.telefono,
        gmail=req.gmail,
        direccion=req.direccion,
        role=req.role,
        password=req.password,
    )


@router.post("/login")
async def login(req: LoginRequest, response: Response):
    user = await auth_service.login(gmail=req.gmail, password=req.password)

    if not user:
        return {"success": False, "message": "Correo o contraseña incorrectos"}

    response.set_cookie(
        key="session",
        value=str(user["id"]),
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )

    return {
        "success": True,
        "user": {
            "id": user.get("id"),
            "nombre": user.get("nombre"),
            "gmail": user.get("gmail"),
            "telefono": user.get("telefono"),
            "direccion": user.get("direccion"),
            "role": user.get("role"),
        },
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="session")
    return {"success": True}
