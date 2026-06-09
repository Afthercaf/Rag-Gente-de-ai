from pydantic import BaseModel


class RegisterRequest(BaseModel):
    nombre: str
    telefono: str
    gmail: str
    direccion: str
    role: str = "cliente"
    password: str


class LoginRequest(BaseModel):
    gmail: str
    password: str
