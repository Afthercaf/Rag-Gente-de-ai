from typing import Optional
from pydantic import BaseModel, field_validator
import re


class OrderRequest(BaseModel):
    user_id: int
    pedido: str
    cliente_nombre: str
    telefono: str
    gmail: str
    direccion: str
    payment_method: str
    total: Optional[str] = None
    ubicacion: Optional[dict] = None

    @field_validator("telefono")
    @classmethod
    def validate_telefono(cls, v: str) -> str:
        """Extrae solo dígitos y valida máximo 10 caracteres."""
        digits = re.sub(r"\D", "", v)
        if len(digits) > 10:
            digits = digits[:10]
        return digits


class StatusUpdateRequest(BaseModel):
    status: str
