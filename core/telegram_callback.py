from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
import uuid


_ACTION_CODES = {
    "confirm": "c",
    "preparing": "p",
    "delivery": "d",
    "delivered": "e",
    "cancel": "x",
}
_CODE_ACTIONS = {value: key for key, value in _ACTION_CODES.items()}
_MAX_AGE_SECONDS = 60 * 60


def _secret() -> bytes:
    value = os.getenv("TELEGRAM_BOT_TOKEN")
    if not value:
        raise RuntimeError("TELEGRAM_BOT_TOKEN no configurado.")
    return value.encode("utf-8")


def build_callback(action: str, order_id: str, *, now: int | None = None) -> str:
    code = _ACTION_CODES[action]
    order_uuid = uuid.UUID(str(order_id))
    compact_id = base64.urlsafe_b64encode(order_uuid.bytes).decode().rstrip("=")
    issued_at = int(now if now is not None else time.time())
    payload = f"{code}.{compact_id}.{issued_at:x}"
    signature = hmac.new(
        _secret(), payload.encode("ascii"), hashlib.sha256
    ).hexdigest()[:12]
    return f"{payload}.{signature}"


def verify_callback(
    value: str,
    *,
    now: int | None = None,
) -> tuple[str, str] | None:
    try:
        code, compact_id, issued_hex, supplied_signature = value.split(".", 3)
        payload = f"{code}.{compact_id}.{issued_hex}"
        expected_signature = hmac.new(
            _secret(), payload.encode("ascii"), hashlib.sha256
        ).hexdigest()[:12]
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None
        issued_at = int(issued_hex, 16)
        current_time = int(now if now is not None else time.time())
        if issued_at > current_time + 30 or current_time - issued_at > _MAX_AGE_SECONDS:
            return None
        padded_id = compact_id + "=" * (-len(compact_id) % 4)
        order_id = str(uuid.UUID(bytes=base64.urlsafe_b64decode(padded_id)))
        action = _CODE_ACTIONS.get(code)
        return (action, order_id) if action else None
    except (KeyError, TypeError, ValueError):
        return None
