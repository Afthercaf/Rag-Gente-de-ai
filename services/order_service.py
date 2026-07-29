"""
Servicio de órdenes - Integración con Supabase, Telegram y Mercado Pago
"""

import asyncio
import json
import re
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from src.supabase_orders import (
    create_order,
    get_order_status,
    update_order_status,
    update_payment_info,
    get_order_by_id,
    get_order_by_id_and_owner,
)
from src.telegram_sender import send_telegram_order
from services.mercadopago_service import mercadopago_service

logger = logging.getLogger(__name__)

# Palabras que indican que el cliente quiere pagar con tarjeta / Mercado Pago
_CARD_PAYMENT_KEYWORDS = {
    "mercado_pago", "mercadopago", "mercado pago", "mercado libre",
    "mercadolibre", "tarjeta", "credito", "crédito", "debito", "débito",
    "qr", "card", "mp", "mercadopago",
}


def _wants_card_payment(payment_method: Optional[str]) -> bool:
    """Detecta si el método de pago elegido corresponde a tarjeta/Mercado Pago."""
    if not payment_method:
        return False
    normalized = payment_method.strip().lower()
    # Log para debugging
    logger.info(f"🔍 Verificando método de pago: '{payment_method}' -> normalizado: '{normalized}'")
    
    # Verificar coincidencia exacta primero
    if normalized in ["mercado_pago", "mercadopago", "mercado pago"]:
        logger.info(f"✅ Método de pago detectado como Mercado Pago (coincidencia exacta)")
        return True
    
    # Verificar palabras clave
    result = any(kw in normalized for kw in _CARD_PAYMENT_KEYWORDS)
    logger.info(f"🔍 Resultado de detección: {result}")
    return result


def _sanitize_total(total: Optional[str]) -> Optional[float]:
    """
    Sanitiza el total extrayendo el número de la cadena.
    
    Args:
        total: Cadena con el total (ej. "$180.00", "180", "180.50")
        
    Returns:
        Total como float, o None si no se pudo extraer
    """
    if not total:
        return None
    
    # Buscar números en la cadena
    m = re.search(r"([0-9]+(?:[.,][0-9]{1,2})?)", str(total))
    if m:
        try:
            # Normalizar coma a punto
            return float(m.group(1).replace(",", "."))
        except Exception:
            return None
    return None


async def place_order(
    user_id: int,
    cliente_nombre: str,
    telefono: str,
    gmail: str,
    direccion: str,
    pedido: str,
    payment_method: str,
    total: str,
    ubicacion: Optional[dict],
) -> Dict[str, Any]:
    """
    Crea un nuevo pedido y genera link de pago si es necesario.
    """
    logger.info(f"📝 [place_order] Iniciando creación de orden")
    logger.info(f"   - user_id: {user_id}")
    logger.info(f"   - payment_method: '{payment_method}'")
    # VULN-16/17/18: no registrar PII (nombre, email, dirección, teléfono).
    
    # Preparar datos
    ubicacion_json = json.dumps(ubicacion) if ubicacion else None
    sanitized_total = _sanitize_total(total)
    if sanitized_total is None or sanitized_total <= 0:
        raise ValueError("El total calculado por el servidor no es válido")
    logger.info(f"💰 Total sanitizado: {sanitized_total}")

    # Construir payload
    payload = {
        "user_id": user_id,
        "cliente_nombre": cliente_nombre,
        "telefono": telefono,
        "gmail": gmail,
        "direccion": direccion,
        "pedido": pedido,
        "total": sanitized_total if sanitized_total is not None else None,
        "payment_method": payment_method,
        "estado": "pendiente",
        "ubicacion_maps": ubicacion_json,
        "created_at": datetime.utcnow().isoformat(),
        "payment_id": None,
        "payment_url": None,
        "payment_status": None,
    }

    # Crear orden en Supabase
    logger.info("💾 Creando orden en Supabase...")
    order_id = await asyncio.to_thread(create_order, payload)

    if not order_id:
        logger.error("❌ Error al crear la orden en Supabase")
        return {"success": False, "message": "Error al crear el pedido"}

    logger.info(f"✅ Orden creada con ID: {order_id}")

    # Preparar respuesta base
    result: Dict[str, Any] = {
        "success": True,
        "order_id": order_id,
        "total": payload["total"],
    }

    # ─────────────────────────────────────────────────────────────
    # GENERAR PAGO CON MERCADO PAGO
    # ─────────────────────────────────────────────────────────────
    wants_card = _wants_card_payment(payment_method)
    logger.info(f"💳 ¿Quiere pagar con tarjeta/Mercado Pago? {wants_card}")
    
    if wants_card and payload["total"]:
        logger.info(f"💳 Generando link de Mercado Pago para orden {order_id}")
        logger.info(f"   - Monto: {payload['total']}")
        # VULN-16/17/18: no registrar email ni nombre en logs.
        
        try:
            # Verificar que el servicio esté disponible
            if not mercadopago_service.is_available():
                logger.error("❌ Servicio de Mercado Pago NO disponible")
                result["payment"] = {
                    "method": "mercadopago",
                    "success": False,
                    "error": "Servicio de Mercado Pago no disponible"
                }
            else:
                # Generar link de pago
                link = await asyncio.to_thread(
                    mercadopago_service.create_payment_link,
                    amount=float(payload["total"]),
                    description=f"Pedido {order_id} - Pizzería 220",
                    order_id=str(order_id),
                    title=f"Pedido {order_id} - Pizzería 220",
                    # VULN-03: evitar datos de ejemplo; usar datos reales de la orden.
                    email=gmail,
                    name=cliente_nombre,
                    expires_in_minutes=30,
                    user_id=user_id,
                )

                if link:
                    logger.info(f"✅ Link de pago generado exitosamente")
                    logger.info(f"   - URL: {link.url}")
                    logger.info(f"   - Payment ID: {link.payment_id}")
                    
                    # Guardar información de pago en Supabase
                    payment_saved = await asyncio.to_thread(
                        update_payment_info,
                        order_id=order_id,
                        payment_id=link.payment_id,
                        payment_url=link.url,
                        payment_status=link.status,
                        preference_id=link.payment_id,
                    )

                    if payment_saved:
                        logger.info(f"✅ Información de pago guardada para orden {order_id}")
                    else:
                        logger.warning(f"⚠️ No se pudo guardar información de pago para orden {order_id}")

                    result["payment"] = {
                        "method": "mercadopago",
                        "payment_id": link.payment_id,
                        "preference_id": link.payment_id,
                        "status": link.status,
                        "url": link.url,
                        "short_url": link.short_url,
                        "expires_at": link.expires_at,
                        "is_sandbox": mercadopago_service.is_sandbox(),
                        "success": True,
                    }
                else:
                    logger.error(f"❌ No se pudo generar link de pago para orden {order_id}")
                    result["payment"] = {
                        "method": "mercadopago",
                        "success": False,
                        "error": "No se pudo generar el link de pago",
                    }
        except Exception as e:
            logger.error(f"❌ Error generando link de pago para orden {order_id}: {e}", exc_info=True)
            result["payment"] = {
                "method": "mercadopago",
                "success": False,
                "error": "No se pudo generar el enlace de pago.",
            }
    else:
        logger.info(f"ℹ️ No se generará pago con Mercado Pago")
        logger.info(f"   - wants_card: {wants_card}")
        logger.info(f"   - total: {payload['total']}")

    return result


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
    """
    Envía notificación por Telegram (pensada para ejecutarse como background task).
    """
    try:
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
    except Exception as e:
        logger.error(f"❌ Error enviando notificación Telegram para orden {order_id}: {e}")


async def patch_status(
    order_id: str,
    status: str,
    owner_user_id: int | None = None,
) -> Dict[str, Any]:
    """
    Actualiza el estado de una orden.

    Si owner_user_id se proporciona, solo se actualiza si el pedido
    pertenece a ese usuario (VULN-08/09).
    """
    logger.info(f"🔄 Actualizando pedido {order_id} -> {status}")
    success = await asyncio.to_thread(
        update_order_status, order_id, status, owner_user_id
    )
    logger.info(f"📦 Resultado Supabase: {success}")
    return {"success": success, "order_id": order_id, "status": status}


async def fetch_status(
    order_id: str,
    owner_user_id: int,
) -> Dict[str, Any]:
    """
    Obtiene el estado de una orden.

    owner_user_id es obligatorio para garantizar que solo el
    dueño de la orden pueda consultar su estado (VULN-10).
    """
    order = await asyncio.to_thread(
        get_order_by_id_and_owner, order_id, owner_user_id
    )
    if not order:
        return {"order_id": order_id, "status": "no_encontrado"}
    return {"order_id": order_id, "status": order.get("estado", "desconocido")}


async def get_order_details(
    order_id: str,
    owner_user_id: int | None = None,
) -> Optional[Dict[str, Any]]:
    """
    Obtiene todos los detalles de una orden.

    Si owner_user_id se proporciona, solo devuelve la orden si pertenece
    a ese usuario (VULN-08/09).
    """
    if owner_user_id is not None:
        return await asyncio.to_thread(
            get_order_by_id_and_owner, order_id, owner_user_id
        )
    return await asyncio.to_thread(get_order_by_id, order_id)


async def update_payment_status_from_webhook(order_id: str, new_status: str) -> Dict[str, Any]:
    """
    Actualiza el estado del pago desde un webhook de Mercado Pago.
    """
    try:
        order = await get_order_details(order_id)
        if not order:
            return {
                "success": False,
                "order_id": order_id,
                "error": "Orden no encontrada",
            }
        
        payment_updated = await asyncio.to_thread(
            update_payment_info,
            order_id=order_id,
            payment_id=order.get("payment_id") or "pending",
            payment_url=order.get("payment_url") or "",
            payment_status=new_status,
            preference_id=order.get("preference_id") or "pending",
        )
        
        if not payment_updated:
            return {
                "success": False,
                "order_id": order_id,
                "error": "Error actualizando estado del pago",
            }
        
        if new_status == "approved":
            await patch_status(order_id, "confirmado")
        
        logger.info(f"✅ Estado de pago actualizado para orden {order_id}: {new_status}")
        
        return {
            "success": True,
            "order_id": order_id,
            "payment_status": new_status,
        }
    except Exception as e:
        logger.error(f"❌ Error actualizando estado de pago para orden {order_id}: {e}")
        return {
            "success": False,
            "order_id": order_id,
            "error": "No se pudo actualizar el estado de pago.",
        }


async def has_active_payment(order_id: str) -> bool:
    """
    Verifica si una orden tiene un pago activo pendiente.
    """
    order = await get_order_details(order_id)
    if not order:
        return False
    
    payment_status = order.get("payment_status")
    return payment_status in ["pending", "in_process", "on_hold"]
