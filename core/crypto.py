"""
Cifrado simétrico genérico con AES-256-GCM + HKDF.

Se usa tanto para sesiones en Redis como para transcripciones de voz.
La misma clave maestra no se utiliza directamente; se deriva una clave
AES-256 por dominio mediante HKDF-SHA256.
"""

from __future__ import annotations

import json
import os
import logging
from base64 import b64decode, b64encode
from typing import Any, Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)


def derive_aes_key(master_key: str, domain: bytes) -> bytes:
    """Deriva una clave AES-256 de 32 bytes a partir de la clave maestra."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=domain,
    )
    return hkdf.derive(master_key.encode("utf-8"))


def encrypt_json(data: dict[str, Any], key: bytes) -> str:
    """Encripta un dict como JSON con AES-256-GCM.

    Returns: nonce_base64 || ciphertext_base64
    """
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    plaintext = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return b64encode(nonce + ciphertext).decode("ascii")


def decrypt_json(payload: str, key: bytes) -> Optional[dict[str, Any]]:
    """Desencripta un payload AES-256-GCM.

    Args:
        payload: nonce_base64 || ciphertext_base64

    Returns: dict original o None si falla.
    """
    try:
        raw = b64decode(payload)
        nonce = raw[:12]
        ciphertext = raw[12:]
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode("utf-8"))
    except Exception as exc:
        logger.error("Error desencriptando payload: %s", exc)
        return None
