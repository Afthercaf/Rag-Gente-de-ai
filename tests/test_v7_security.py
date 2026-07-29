from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from core.telegram_callback import build_callback, verify_callback
from providers.ollama_provider import _validated_ollama_url
from schemas.order import OrderRequest


def test_ollama_rejects_unlisted_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "OLLAMA_ALLOWED_HOSTS",
        "killerexpert10.tail29c8ce.ts.net",
    )
    assert _validated_ollama_url(
        "http://killerexpert10.tail29c8ce.ts.net:11434"
    ) == "http://killerexpert10.tail29c8ce.ts.net:11434"
    with pytest.raises(RuntimeError):
        _validated_ollama_url("http://127.0.0.1:11434")
    with pytest.raises(RuntimeError):
        _validated_ollama_url(
            "https://killerexpert10.tail29c8ce.ts.net@evil.example"
        )


def test_telegram_callbacks_are_signed_and_expire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-secret-token")
    order_id = str(uuid.uuid4())
    callback = build_callback("confirm", order_id, now=1_000)
    assert len(callback.encode("utf-8")) <= 64
    assert verify_callback(callback, now=1_001) == ("confirm", order_id)
    assert verify_callback(callback + "0", now=1_001) is None
    assert verify_callback(callback, now=5_000) is None


def test_order_rejects_invalid_phone_and_email() -> None:
    base = {
        "pedido": "Pizza",
        "cliente_nombre": "Cliente",
        "telefono": "5512345678",
        "gmail": "cliente@example.com",
        "direccion": "Dirección válida",
        "payment_method": "efectivo",
    }
    assert OrderRequest(**base).telefono == "5512345678"
    with pytest.raises(ValidationError):
        OrderRequest(**{**base, "telefono": "1234567890123456"})
    with pytest.raises(ValidationError):
        OrderRequest(**{**base, "gmail": "correo-invalido"})
