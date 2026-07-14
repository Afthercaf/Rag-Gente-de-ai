import asyncio
from typing import Any, Dict, Optional

from src.supabase_auth import get_user_by_gmail, login_user, register_user


async def register(
    nombre: str,
    telefono: str,
    gmail: str,
    direccion: str,
    password: str,
) -> Dict[str, Any]:
    gmail = gmail.strip().lower()

    existing = await asyncio.to_thread(get_user_by_gmail, gmail)
    if existing:
        return {"success": False, "message": "El correo ya está registrado"}

    user = await asyncio.to_thread(
        register_user,
        nombre=nombre,
        telefono=telefono,
        gmail=gmail,
        direccion=direccion,
        role="cliente",
        password_hash=password,
    )

    if not user:
        return {"success": False, "message": "Error al crear el usuario"}

    return {"success": True, "user": user}


async def login(gmail: str, password: str) -> Optional[Dict[str, Any]]:
    gmail = gmail.strip().lower()
    return await asyncio.to_thread(login_user, gmail=gmail, password_hash=password)
