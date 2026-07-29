from __future__ import annotations

import logging
import os
import re

from dotenv import load_dotenv

# Único punto de carga para desarrollo local. En Docker, ``env_file`` ya
# inyecta el entorno y ``override=False`` impide reemplazarlo.
load_dotenv(override=False)


def require_env(name: str, *, min_length: int = 1) -> str:
    """Obtiene una variable obligatoria sin aceptar fallbacks inseguros."""
    value = os.getenv(name)
    if value is None or len(value.strip()) < min_length:
        suffix = (
            f" y contener al menos {min_length} caracteres."
            if min_length > 1
            else "."
        )
        raise RuntimeError(f"{name} debe estar configurada en el entorno{suffix}")
    return value.strip()


def supabase_server_key() -> str:
    """Prefiere la credencial secreta exclusiva del backend."""
    return (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or require_env("SUPABASE_KEY")
    )


# Nombres de variables de entorno que pueden contener secretos.
# Se usan para sanitizar logs y evitar fugas accidentales.
_SECRET_ENV_NAMES = {
    "JWT_SECRET",
    "REFRESH_TOKEN_SECRET",
    "SESSION_ENCRYPTION_KEY",
    "TRANSCRIPTION_ENCRYPTION_KEY",
    "SUPABASE_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "GROQ_API_KEY",
    "QDRANT_API_KEY",
    "MERCADO_PAGO_ACCESS_TOKEN",
    "MERCADO_PAGO_PUBLIC_KEY",
    "MERCADO_PAGO_APP_ID",
    "MERCADO_PAGO_USER_ID",
    "MERCADO_PAGO_TEST_PASSWORD",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_SERVICE_TOKEN",
    "TELEGRAM_CHAT_ID",
    "REDIS_PASSWORD",
    "REDIS_URL",
    "LOCATIONIQ_API_KEY",
    "TS_AUTHKEY",
    "CLOUDFLARE_TUNNEL_TOKEN",
    "DATABASE_URL",
}


class SecretRedactingFilter(logging.Filter):
    """
    Filtro de logging que reemplaza valores secretos y PII por [REDACTED].

    VULN-16/17/18: además de secretos, enmascara correos, teléfonos y direcciones
    para evitar fugas accidentales de datos personales.
    """

    def __init__(self) -> None:
        super().__init__()
        self._patterns: list[tuple[re.Pattern[str], str]] = []

        for name in _SECRET_ENV_NAMES:
            value = os.getenv(name, "")
            if not value or len(value) < 4:
                continue

            # Escapar caracteres especiales de regex.
            escaped = re.escape(value)
            pattern = re.compile(escaped)
            self._patterns.append(
                (pattern, "[REDACTED]"),
            )

        # PII patterns
        self._patterns.append(
            (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "[EMAIL]"))
        self._patterns.append(
            (re.compile(r"\b(?:\+?\d[\d ()-]{7,}\d)\b"), "[PHONE]"))
        self._patterns.append(
            (re.compile(r"\b\d{4,}\s+\d{4,}\b|\b\d{6,}\b"), "[NUMBER]"))

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()

        for pattern, replacement in self._patterns:
            message = pattern.sub(replacement, message)

        record.msg = message
        record.args = ()
        return True


# Instalar el filtro en el logger raíz lo antes posible.
_root_logger = logging.getLogger()
_root_logger.addFilter(SecretRedactingFilter())


# ─────────────────────────────────────────────────────────────
# Carga de variables de entorno local
# ─────────────────────────────────────────────────────────────
