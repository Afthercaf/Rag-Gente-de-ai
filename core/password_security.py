from __future__ import annotations
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

def hash_password(password: str) -> str:
    if not isinstance(password, str):
        raise TypeError("La contraseña debe ser texto")
    if len(password) < 10:
        raise ValueError("La contraseña debe tener al menos 10 caracteres")
    if len(password) > 128:
        raise ValueError("La contraseña no puede superar 128 caracteres")
    return _password_hasher.hash(password)

def verify_password(password: str, stored_hash: str) -> bool:
    if not password or not stored_hash:
        return False
    try:
        return _password_hasher.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError, TypeError):
        return False

def password_needs_rehash(stored_hash: str) -> bool:
    try:
        return _password_hasher.check_needs_rehash(stored_hash)
    except (InvalidHashError, TypeError):
        return True

def is_argon2_hash(value: str) -> bool:
    return isinstance(value, str) and value.startswith("$argon2")
