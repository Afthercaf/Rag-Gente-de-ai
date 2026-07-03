"""
Router para manejar endpoints relacionados con pagos.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.payment_service import (
    PaymentMethod,
    PaymentInfo,
    process_payment,
    detect_payment_method,
    build_payment_directive,
)

router = APIRouter(prefix="/payment", tags=["payment"])


class PaymentRequest(BaseModel):
    user_id: int
    total: str
    payment_method: Optional[str] = None
    amount_paid: Optional[float] = None


class PaymentResponse(BaseModel):
    success: bool
    message: str
    payment_info: Optional[dict] = None


@router.post("/process", response_model=PaymentResponse)
async def process_payment_endpoint(request: PaymentRequest):
    """
    Procesa un pago para un usuario.
    """
    try:
        # Determinar método de pago
        if request.payment_method:
            try:
                method = PaymentMethod(request.payment_method.lower())
            except ValueError:
                return PaymentResponse(
                    success=False,
                    message=f"Método de pago no soportado: {request.payment_method}",
                )
        else:
            # Si no se especifica, usar efectivo por defecto
            method = PaymentMethod.CASH
        
        # Procesar pago
        payment_info = process_payment(
            payment_method=method,
            total=request.total,
            amount_paid=request.amount_paid,
        )
        
        return PaymentResponse(
            success=True,
            message=payment_info.raw_message,
            payment_info={
                "method": payment_info.method.value,
                "total": payment_info.total,
                "change": payment_info.change,
                "payment_link": payment_info.payment_link,
            },
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/detect", response_model=dict)
async def detect_payment(text: str):
    """
    Detecta el método de pago en un texto.
    """
    method, amount, detail = detect_payment_method(text)
    return {
        "method": method.value,
        "amount": amount,
        "detail": detail,
    }


@router.post("/directive", response_model=dict)
async def get_payment_directive(question: str, total: str, history: list[dict]):
    """
    Genera una directiva para el LLM sobre pago.
    """
    directive = build_payment_directive(question, total, history)
    return {"directive": directive}