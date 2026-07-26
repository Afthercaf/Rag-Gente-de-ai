from __future__ import annotations
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nombre: str = Field(min_length=2, max_length=80)
    telefono: str = Field(min_length=8, max_length=20, pattern=r"^\+?[0-9 ()-]+$")
    gmail: EmailStr
    direccion: str = Field(min_length=3, max_length=240)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not any(c.islower() for c in value):
            raise ValueError("La contraseña debe incluir una minúscula")
        if not any(c.isupper() for c in value):
            raise ValueError("La contraseña debe incluir una mayúscula")
        if not any(c.isdigit() for c in value):
            raise ValueError("La contraseña debe incluir un número")
        return value

class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    gmail: EmailStr
    password: str = Field(min_length=1, max_length=128)
