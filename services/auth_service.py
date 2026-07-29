from __future__ import annotations
import asyncio
from typing import Any, Dict, Optional

from core.password_security import hash_password, password_needs_rehash, verify_password
from src.supabase_auth import (
    get_user_by_gmail,
    get_user_by_id,
    register_user,
    update_user_password_hash,
)

_ALLOWED_USER_FIELDS = {
    "id", "public_id", "nombre", "telefono", "gmail",
    "direccion", "role", "created_at"
}

def _public_user(user: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in user.items() if k in _ALLOWED_USER_FIELDS}

async def register(nombre: str, telefono: str, gmail: str, direccion: str, password: str) -> Dict[str, Any]:
    gmail = gmail.strip().lower()

    existing = await asyncio.to_thread(get_user_by_gmail, gmail)
    if existing:
        return {"success": False, "message": "El correo ya está registrado"}

    try:
        password_hash = hash_password(password)
    except (TypeError, ValueError) as exc:
        return {"success": False, "message": "No fue posible registrar al usuario."}

    user = await asyncio.to_thread(
        register_user,
        nombre=nombre.strip(),
        telefono=telefono.strip(),
        gmail=gmail,
        direccion=direccion.strip(),
        role="cliente",
        password_hash=password_hash,
    )

    if not user:
        return {"success": False, "message": "Error al crear el usuario"}

    return {"success": True, "user": _public_user(user)}

async def login(gmail: str, password: str) -> Optional[Dict[str, Any]]:
    gmail = gmail.strip().lower()
    user = await asyncio.to_thread(get_user_by_gmail, gmail)

    if not user:
        return None

    stored_hash = str(user.get("password_hash") or "")
    if not verify_password(password, stored_hash):
        return None

    if password_needs_rehash(stored_hash):
        new_hash = hash_password(password)
        await asyncio.to_thread(update_user_password_hash, user["id"], new_hash)

    return _public_user(user)


async def get_profile(user_id: int) -> Optional[Dict[str, Any]]:
    user = await asyncio.to_thread(get_user_by_id, user_id)
    return _public_user(user) if user else None
