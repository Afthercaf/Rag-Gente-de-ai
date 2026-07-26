# routers/orders.py - Versión corregida
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from typing import Optional
from datetime import datetime
import logging

from core.state import state
from schemas.order import OrderRequest, StatusUpdateRequest
from services import order_service
from services.session_service import get_user_session, clear_current_cart
from core.decorators import measure_time
from core.security import CurrentUser, get_current_user, require_roles

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/order", tags=["orders"])


@router.post("")
@measure_time
async def create_new_order(
    req: OrderRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Crea una nueva orden.
    """
    logger.info(f"📝 [create_new_order] Recibiendo solicitud")
    logger.info("   - user_uuid: %s", current_user.public_id)
    logger.info(f"   - payment_method: '{req.payment_method}'")
    logger.info(f"   - total: '{req.total}'")
    
    if not state.get("ready", False):
        return {"success": False, "message": "Sistema no listo"}

    try:
        result = await order_service.place_order(
            user_id=current_user.internal_id,
            cliente_nombre=req.cliente_nombre,
            telefono=req.telefono,
            gmail=req.gmail,
            direccion=req.direccion,
            pedido=req.pedido,
            payment_method=req.payment_method,
            total=req.total,
            ubicacion=req.ubicacion,
        )

        logger.info(f"📦 [create_new_order] Resultado de place_order: {result}")

        if result["success"]:
            # La orden ya quedó persistida: cerrar el flujo conversacional.
            # Así una pregunta posterior no reutiliza el carrito anterior.
            try:
                session = get_user_session(current_user.internal_id)
                clear_current_cart(session, current_user.internal_id)
                logger.info(
                    "🧹 [create_new_order] Carrito conversacional limpiado para user_id=%s",
                    current_user.internal_id,
                )
            except Exception as session_error:
                logger.warning(
                    "No se pudo limpiar el carrito del usuario %s: %s",
                    current_user.internal_id,
                    session_error,
                )

            # Enviar notificación por Telegram en segundo plano
            background_tasks.add_task(
                order_service.notify_telegram,
                order_id=result["order_id"],
                cliente_nombre=req.cliente_nombre,
                telefono=req.telefono,
                gmail=req.gmail,
                direccion=req.direccion,
                pedido=req.pedido,
                payment_method=req.payment_method,
                total=req.total,
                ubicacion=req.ubicacion,
            )

        return result
        
    except Exception as e:
        logger.error(f"❌ Error creando orden: {e}", exc_info=True)
        return {"success": False, "message": f"Error al crear la orden: {str(e)}"}


@router.patch("/{order_id}/status")
@measure_time
async def patch_order_status(
    order_id: str,
    req: StatusUpdateRequest,
    current_user: CurrentUser = Depends(require_roles("admin")),
):
    """
    Actualiza el estado de una orden.
    """
    if not state.get("ready", False):
        return {"success": False, "message": "Sistema no listo"}

    try:
        valid_statuses = ["pendiente", "confirmado", "preparando", "listo", "entregado", "cancelado"]
        if req.status not in valid_statuses:
            return {
                "success": False, 
                "message": f"Estado inválido. Estados válidos: {', '.join(valid_statuses)}"
            }
        
        result = await order_service.patch_status(order_id, req.status)
        return result
        
    except Exception as e:
        logger.error(f"Error actualizando orden {order_id}: {e}")
        return {"success": False, "message": f"Error al actualizar la orden: {str(e)}"}


@router.get("/{order_id}/status")
@measure_time
async def fetch_order_status(
    order_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Obtiene el estado de una orden.
    """
    if not state.get("ready", False):
        return {"success": False, "message": "Sistema no listo"}

    try:
        import uuid
        uuid.UUID(order_id)
        result = await order_service.fetch_status(order_id)
        return result
        
    except Exception as e:
        logger.error(f"Error obteniendo orden {order_id}: {e}")
        return {"success": False, "message": f"Error al obtener la orden: {str(e)}"}


@router.get("/mine")
@measure_time
async def get_my_orders(
    limit: int = 10,
    offset: int = 0,
    current_user: CurrentUser = Depends(get_current_user),
):
    limit = max(1, min(limit, 50))
    offset = max(0, offset)

    # Sustituir por order_service.list_by_user cuando exista.
    return {
        "success": True,
        "user_id": str(current_user.public_id),
        "orders": [],
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": 0,
        },
    }


@router.post("/{order_id}/cancel")
@measure_time
async def cancel_order(
    order_id: str,
    reason: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Cancela una orden.
    """
    if not state.get("ready", False):
        return {"success": False, "message": "Sistema no listo"}

    try:
        import uuid
        uuid.UUID(order_id)

        # IMPORTANTE: order_service.patch_status debe comprobar que
        # order_id pertenece a current_user.internal_id.
        result = await order_service.patch_status(
            order_id,
            "cancelado",
            owner_user_id=current_user.internal_id,
        )
        
        if result["success"]:
            return {
                "success": True,
                "order_id": order_id,
                "message": f"Orden {order_id} cancelada exitosamente",
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
            
    except Exception as e:
        logger.error(f"Error cancelando orden {order_id}: {e}")
        return {"success": False, "message": f"Error al cancelar la orden: {str(e)}"}