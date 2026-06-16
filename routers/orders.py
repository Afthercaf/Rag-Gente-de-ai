from fastapi import APIRouter, BackgroundTasks

from core.state import state
from schemas.order import OrderRequest, StatusUpdateRequest
from services import order_service
from core.decorators import measure_time

router = APIRouter(prefix="/order", tags=["orders"])


@router.post("")
@measure_time
async def create_new_order(req: OrderRequest, background_tasks: BackgroundTasks):
    if not state["ready"]:
        return {"success": False, "message": "Sistema no listo"}

    result = await order_service.place_order(
        user_id=req.user_id,
        cliente_nombre=req.cliente_nombre,
        telefono=req.telefono,
        gmail=req.gmail,
        direccion=req.direccion,
        pedido=req.pedido,
        payment_method=req.payment_method,
        total=req.total,
        ubicacion=req.ubicacion,
    )

    if result["success"]:
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


@router.patch("/{order_id}/status")
async def patch_order_status(order_id: str, req: StatusUpdateRequest):
    return await order_service.patch_status(order_id, req.status)


@router.get("/{order_id}/status")
async def fetch_order_status(order_id: str):
    return await order_service.fetch_status(order_id)
