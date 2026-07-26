from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.security import CurrentUser, get_current_user
from services.payment_service import PaymentMethod, process_payment


router = APIRouter(prefix="/payment", tags=["payment"])


class PaymentRequestSecure(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # En producción debe recibirse order_id UUID y cargar el total del servidor.
    order_id: str = Field(min_length=36, max_length=36)
    payment_method: Literal["efectivo", "mercado_pago"]
    amount_paid: Optional[Decimal] = Field(default=None, ge=Decimal("0"))

    @field_validator("order_id")
    @classmethod
    def validate_uuid(cls, value: str) -> str:
        import uuid
        return str(uuid.UUID(value))


@router.post("/process")
async def process_payment_endpoint(
    request: PaymentRequestSecure,
    current_user: CurrentUser = Depends(get_current_user),
):
    # Nunca aceptar total ni user_id del cliente.
    # Debe cargarse el pedido con ownership y total desde DB.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Conecta order_service.get_owned_order(order_id, user_id) "
            "y calcula el total desde los productos del servidor."
        ),
    )
