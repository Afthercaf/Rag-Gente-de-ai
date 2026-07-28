"""
Compatibilidad temporal para el flujo de pagos.

Este módulo no genera enlaces, códigos QR ni pagos simulados.
La creación real de pagos debe pasar por mercadopago_service.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class PaymentMethod(str, Enum):
    CASH = "cash"
    MERCADO_PAGO = "mercado_pago"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PaymentInfo:
    payment_method: PaymentMethod
    total: float
    amount_paid: float | None = None
    change: float | None = None
    raw_message: str = ""


def _to_amount(value: str | float | int) -> float:
    if isinstance(value, (int, float)):
        return float(value)

    normalized = re.sub(
        r"[^0-9.,]",
        "",
        str(value or ""),
    ).replace(",", ".")

    return float(normalized) if normalized else 0.0


def is_payment_question(text: str) -> bool:
    normalized = str(text or "").lower()
    return any(
        phrase in normalized
        for phrase in (
            "cómo puedo pagar",
            "como puedo pagar",
            "métodos de pago",
            "metodos de pago",
            "formas de pago",
            "pagar con",
            "pago en efectivo",
            "mercado pago",
        )
    )


def detect_payment_method(
    text: str,
) -> tuple[PaymentMethod, float, str]:
    normalized = str(text or "").lower()
    amount_match = re.search(
        r"(?:con|pago con)\s*\$?\s*(\d+(?:[.,]\d{1,2})?)",
        normalized,
    )
    amount = (
        float(amount_match.group(1).replace(",", "."))
        if amount_match
        else 0.0
    )

    if "efectivo" in normalized:
        return PaymentMethod.CASH, amount, normalized

    if "mercado pago" in normalized or "mercadopago" in normalized:
        return PaymentMethod.MERCADO_PAGO, amount, normalized

    return PaymentMethod.UNKNOWN, amount, normalized


def build_payment_directive(
    question: str,
    total: str,
    history: list[dict],
) -> str:
    del history
    method, amount, _ = detect_payment_method(question)
    total_amount = _to_amount(total)

    if method == PaymentMethod.CASH:
        if amount > 0:
            return (
                f"El total confirmado es ${total_amount:.2f} MXN. "
                f"El cliente pagará con ${amount:.2f} MXN en efectivo. "
                "Calcula el cambio únicamente con estos valores."
            )
        return (
            f"El total confirmado es ${total_amount:.2f} MXN. "
            "Pregunta con cuánto pagará en efectivo."
        )

    if method == PaymentMethod.MERCADO_PAGO:
        return (
            f"El total confirmado es ${total_amount:.2f} MXN. "
            "Indica que el enlace real se genera mediante el servicio "
            "oficial de Mercado Pago. No inventes URLs ni códigos QR."
        )

    return (
        f"El total confirmado es ${total_amount:.2f} MXN. "
        "Ofrece únicamente Efectivo o Mercado Pago."
    )


def process_payment(
    payment_method: PaymentMethod,
    total: str | float,
    amount_paid: float | None = None,
) -> PaymentInfo:
    total_amount = _to_amount(total)

    if total_amount <= 0:
        raise ValueError("El total debe ser positivo")

    if payment_method == PaymentMethod.CASH:
        if amount_paid is None or amount_paid <= 0:
            return PaymentInfo(
                payment_method=payment_method,
                total=total_amount,
                raw_message="Indica con cuánto pagarás en efectivo.",
            )

        change = amount_paid - total_amount
        if change < 0:
            return PaymentInfo(
                payment_method=payment_method,
                total=total_amount,
                amount_paid=amount_paid,
                raw_message=(
                    f"El pago es insuficiente. Faltan "
                    f"${abs(change):.2f} MXN."
                ),
            )

        return PaymentInfo(
            payment_method=payment_method,
            total=total_amount,
            amount_paid=amount_paid,
            change=change,
            raw_message=f"Cambio: ${change:.2f} MXN.",
        )

    if payment_method == PaymentMethod.MERCADO_PAGO:
        return PaymentInfo(
            payment_method=payment_method,
            total=total_amount,
            raw_message=(
                "El pago debe generarse mediante el servicio oficial "
                "de Mercado Pago."
            ),
        )

    raise ValueError("Método de pago no soportado")
