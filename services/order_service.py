import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional

from src.supabase_orders import create_order, get_order_status, update_order_status
from src.telegram_sender import send_telegram_order


async def place_order(
    user_id: int,
    cliente_nombre: str,
    telefono: str,
    gmail: str,
    direccion: str,
    pedido: str,
    payment_method: str,
    total: Optional[str],
    ubicacion: Optional[dict],
) -> Dict[str, Any]:
    ubicacion_json = json.dumps(ubicacion) if ubicacion else None

    # Sanitizar total: preferir número. Si no se puede, dejar 'pendiente' para evitar errores en Supabase.
    sanitized_total: Any = None
    if total:
        import re

        m = re.search(r"([0-9]+(?:[.,][0-9]{1,2})?)", str(total))
        if m:
            # Normalizar coma a punto
            try:
                sanitized_total = float(m.group(1).replace(",", "."))
            except Exception:
                sanitized_total = None

    payload = {
        "user_id": user_id,
        "cliente_nombre": cliente_nombre,
        "telefono": telefono,
        "gmail": gmail,
        "direccion": direccion,
        "pedido": pedido,
        "total": sanitized_total if sanitized_total is not None else "pendiente",
        "payment_method": payment_method,
        "estado": "pendiente",
        "ubicacion_maps": ubicacion_json,
        "created_at": datetime.utcnow().isoformat(),
    }

    order_id = await asyncio.to_thread(create_order, payload)

    if not order_id:
        return {"success": False, "message": "Error al crear el pedido"}

    return {"success": True, "order_id": order_id, "total": payload["total"]}


async def notify_telegram(
    order_id: str,
    cliente_nombre: str,
    telefono: str,
    gmail: str,
    direccion: str,
    pedido: str,
    payment_method: str,
    total: Optional[str],
    ubicacion: Optional[dict],
) -> None:
    """Envía notificación por Telegram (pensada para ejecutarse como background task)."""
    await asyncio.to_thread(
        send_telegram_order,
        order_id=order_id,
        cliente_nombre=cliente_nombre,
        telefono=telefono,
        gmail=gmail,
        direccion=direccion,
        pedido=pedido,
        payment_method=payment_method,
        total=total,
        ubicacion=ubicacion,
    )


async def patch_status(order_id: str, status: str) -> Dict[str, Any]:
    print(f"🔄 Actualizando pedido {order_id} -> {status}")
    success = await asyncio.to_thread(update_order_status, order_id, status)
    print(f"📦 Resultado Supabase: {success}")
    return {"success": success, "order_id": order_id, "status": status}


async def fetch_status(order_id: str) -> Dict[str, Any]:
    status = await asyncio.to_thread(get_order_status, order_id)
    return {"order_id": order_id, "status": status}
