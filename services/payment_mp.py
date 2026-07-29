"""
Router para pagos con Mercado Pago
"""

import json
import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from services.mercadopago_service import mercadopago_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mp", tags=["mercadopago"])


class PaymentRequest(BaseModel):
    amount: float = Field(..., gt=0)
    description: str = Field(..., max_length=255)
    order_id: str = Field(..., description="ID del pedido al que pertenece este pago")
    # VULN-03: no usar email de ejemplo; se obtiene de la orden real.
    email: str = Field(..., min_length=5)
    name: str = Field(..., min_length=1)


class PaymentLinkRequest(BaseModel):
    amount: float = Field(..., gt=0)
    description: str = Field(..., max_length=255)
    order_id: str = Field(..., description="ID del pedido al que pertenece este pago")
    title: str = Field(default="Pago Pizzería 220")
    # VULN-03: no usar email de ejemplo; se obtiene de la orden real.
    email: str = Field(..., min_length=5)


@router.get("/test")
async def test_mercadopago():
    """Prueba la conexión con Mercado Pago"""
    logger.info("🧪 [test_mercadopago] Ejecutando prueba")
    
    if not mercadopago_service.is_available():
        return {
            "success": False,
            "message": "❌ Mercado Pago no configurado",
            "error": "Access Token no válido"
        }

    # Crear pago de prueba
    result = mercadopago_service.create_payment(
        amount=100.00,
        description="🍕 Pago de prueba",
        order_id="test-123",
        user_email="test@example.com",
        user_name="Prueba",
    )

    return {
        "success": result.success,
        "mode": "sandbox" if mercadopago_service.is_sandbox() else "production",
        "payment": {
            "id": result.payment_id,
            "status": result.status,
            "amount": result.transaction_amount,
            "qr_code": result.qr_code,
            "ticket_url": result.ticket_url,
        },
        "error": result.error_message,
    }


@router.post("/payment")
async def create_payment(request: PaymentRequest):
    """Crea un pago en Mercado Pago"""
    logger.info(f"💳 [create_payment] Creando pago: {request.amount} - {request.order_id}")
    
    if not mercadopago_service.is_available():
        raise HTTPException(status_code=503, detail="Servicio no disponible")

    result = mercadopago_service.create_payment(
        amount=request.amount,
        description=request.description,
        order_id=request.order_id,
        user_email=request.email,
        user_name=request.name,
        payment_method="mercadopago",
    )

    return {
        "success": result.success,
        "payment_id": result.payment_id,
        "status": result.status,
        "amount": result.transaction_amount,
        "qr_code": result.qr_code,
        "ticket_url": result.ticket_url,
        "error": result.error_message,
        "is_sandbox": mercadopago_service.is_sandbox(),
    }


@router.post("/payment/link")
async def create_payment_link(request: PaymentLinkRequest):
    """Crea un link de pago"""
    logger.info(f"🔗 [create_payment_link] Creando link: {request.amount} - {request.order_id}")
    
    if not mercadopago_service.is_available():
        raise HTTPException(status_code=503, detail="Servicio no disponible")

    link = mercadopago_service.create_payment_link(
        amount=request.amount,
        description=request.description,
        order_id=request.order_id,
        title=request.title,
        email=request.email,
    )

    if not link:
        return {"success": False, "error": "Error creando link de pago"}

    return {
        "success": True,
        "url": link.url,
        "payment_id": link.payment_id,
        "status": link.status,
        "is_sandbox": mercadopago_service.is_sandbox(),
    }


@router.get("/payment/{payment_id}/status")
async def get_payment_status(payment_id: str):
    """Obtiene el estado de un pago"""
    if not mercadopago_service.is_available():
        raise HTTPException(status_code=503, detail="Servicio no disponible")

    status = mercadopago_service.get_payment_status(payment_id)

    if not status:
        return {"success": False, "error": "Pago no encontrado"}

    return {
        "success": True,
        "payment_id": status.get("id"),
        "status": status.get("status"),
        "amount": status.get("amount"),
        "payment_method": status.get("payment_method"),
    }


@router.post("/callback")
async def payment_callback(request: Request):
    """Callback para notificaciones de Mercado Pago."""
    body = await request.body()
    signature = request.headers.get("x-signature") or request.headers.get("X-Signature")

    if not mercadopago_service.verify_webhook_signature(
        signature_header=signature,
        request_body=body,
    ):
        logger.warning("🚫 Webhook con firma inválida rechazado")
        raise HTTPException(status_code=401, detail="Firma inválida")

    try:
        data = json.loads(body.decode("utf-8"))
        logger.info("📨 Callback recibido: %s", data)
        return {"success": True}
    except Exception as e:
        logger.error(f"❌ Error procesando callback: {e}")
        return {"success": False, "error": "No fue posible procesar el callback."}
