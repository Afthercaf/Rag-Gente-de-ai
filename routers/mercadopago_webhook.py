from __future__ import annotations

import json
import logging
import asyncio
import uuid

from fastapi import APIRouter, HTTPException, Request, status

from services.mercadopago_service import mercadopago_service
from services.order_service import update_payment_status_from_webhook


logger = logging.getLogger(__name__)
router = APIRouter(tags=["mercadopago"])


@router.post("/mp/callback", status_code=status.HTTP_202_ACCEPTED)
async def mercado_pago_callback(request: Request) -> dict[str, bool]:
    body = await request.body()
    signature = request.headers.get("x-signature")
    if not mercadopago_service.verify_webhook_signature(
        signature_header=signature,
        request_body=body,
    ):
        logger.warning("Webhook Mercado Pago con firma inválida rechazado.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma inválida.",
        )
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload inválido.",
        )
    data = payload.get("data") if isinstance(payload, dict) else None
    notification_id = (
        payload.get("id") if isinstance(payload, dict) else None
    ) or (data.get("id") if isinstance(data, dict) else None)
    if not notification_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notificación incompleta.",
        )
    payment = await asyncio.to_thread(
        mercadopago_service.get_payment_status,
        str(notification_id),
    )
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No fue posible verificar el pago.",
        )
    try:
        order_id = str(uuid.UUID(str(payment.get("external_reference"))))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Referencia de orden inválida.",
        )
    result = await update_payment_status_from_webhook(
        order_id,
        str(payment.get("status") or "pending"),
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible actualizar la orden.",
        )
    logger.info("Webhook Mercado Pago aplicado; order_id=%s", order_id)
    return {"accepted": True}
