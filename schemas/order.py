from typing import Optional
from pydantic import BaseModel


class OrderRequest(BaseModel):
    user_id: int
    pedido: str
    cliente_nombre: str
    telefono: str
    gmail: str
    direccion: str
    payment_method: str
    ubicacion: Optional[dict] = None


class StatusUpdateRequest(BaseModel):
    status: str
