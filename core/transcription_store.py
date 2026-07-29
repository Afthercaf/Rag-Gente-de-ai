"""
Almacén cifrado de transcripciones de voz.

Cada transcripción se guarda como un blob JSON encriptado con AES-256-GCM.
La clave se deriva de TRANSCRIPTION_ENCRYPTION_KEY mediante HKDF con un
dominio distinto al de sesiones, garantizando aislamiento de claves.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from core.crypto import derive_aes_key, encrypt_json, decrypt_json
from core.config import require_env

TRANSCRIPTION_ENCRYPTION_KEY = require_env(
    "TRANSCRIPTION_ENCRYPTION_KEY",
    min_length=32,
)

_TRANSCRIPTION_DOMAIN = b"pizzeria220-transcription-v1"
_AES_KEY = derive_aes_key(TRANSCRIPTION_ENCRYPTION_KEY, _TRANSCRIPTION_DOMAIN)


def encrypt_transcription(data: dict[str, Any]) -> str:
    """Cifra una transcripción individual."""
    return encrypt_json(data, _AES_KEY)


def decrypt_transcription(payload: str) -> Optional[dict[str, Any]]:
    """Descifra una transcripción individual."""
    return decrypt_json(payload, _AES_KEY)
