from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
import re


class LocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    direccion_completa: str = Field(min_length=3, max_length=500)
    timestamp: Optional[str] = Field(default=None, max_length=64)


class OrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pedido: str = Field(min_length=1, max_length=2000)
    cliente_nombre: str = Field(min_length=2, max_length=120)
    telefono: str
    gmail: EmailStr
    direccion: str = Field(min_length=3, max_length=500)
    payment_method: Literal["efectivo", "mercado_pago"]
    ubicacion: Optional[LocationRequest] = None

    @field_validator("telefono")
    @classmethod
    def validate_telefono(cls, v: str) -> str:
        """Extrae solo dígitos y valida máximo 10 caracteres."""
        digits = re.sub(r"\D", "", v)
        if not 8 <= len(digits) <= 15:
            raise ValueError("El teléfono debe contener entre 8 y 15 dígitos.")
        return digits


class StatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal[
        "pendiente", "confirmado", "preparando", "listo", "entregado", "cancelado"
    ]
