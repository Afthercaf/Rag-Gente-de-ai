import asyncio
import re
from typing import Any

from core.state import state
from services import rag_service
from services.intent_detector import build_directive


async def generate_response(
    context: str,
    history_text: str,
    question: str,
    history: list[dict] | None = None,
) -> str:

    if history is None:
        history = []

    pizza_names = rag_service.get_pizza_names()

    directive = build_directive(
        question,
        pizza_names,
        history,
    )

    prompt = state["prompt_template"].format_messages(
        context=context,
        history=history_text,
        question=question,
        directive=directive,
    )

    model = state["model_loader"].model
    state["model_loaded"] = True

    response = await asyncio.to_thread(
        model.invoke,
        prompt,
    )

    return response.content.strip()


def _extract_field(raw: str, name: str) -> str | None:
    pattern = rf"(?im)^{re.escape(name)}\s*:\s*(.*?)(?=\n^[A-ZÁÉÍÓÚÑ][^\n]*?:|\Z)"
    match = re.search(pattern, raw, re.DOTALL | re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else None


def _extract_total(raw: str) -> str | None:
    # Primera opción: campo explícito Total/Importe/Monto
    match = re.search(
        r"(?im)^(?:total|importe|precio total|monto|subtotal)\s*[:=-]?\s*(?:\$|usd|mxn)?\s*([0-9]+(?:[.,][0-9]{1,2})?)\b",
        raw,
        re.MULTILINE,
    )
    if match:
        return match.group(1).replace(",", ".")

    # Segunda opción: línea de precio genérico con símbolo
    match = re.search(
        r"(?im)^(?:precio|costo|valor)\s*[:=-]?\s*(?:\$|usd|mxn)?\s*([0-9]+(?:[.,][0-9]{1,2})?)\b",
        raw,
        re.MULTILINE,
    )
    if match:
        return match.group(1).replace(",", ".")

    return None


def _parse_order_section(raw: str) -> dict[str, Any]:
    cantidad = _extract_field(raw, "Cantidad")
    producto = _extract_field(raw, "Producto")
    tamaño = _extract_field(raw, "Tamaño")
    extras = _extract_field(raw, "Extras")
    removidos = _extract_field(raw, "Ingredientes removidos")
    # Prefer explicit numeric extraction to avoid trailing assistant text
    total = _extract_total(raw) or _extract_field(raw, "Total")

    parsed_extras = None
    if extras:
        parsed_extras = [item.strip() for item in re.split(r",| y ", extras) if item.strip()]

    parsed_removidos = None
    if removidos:
        parsed_removidos = [item.strip() for item in re.split(r",| y ", removidos) if item.strip()]

    return {
        "cantidad": cantidad,
        "producto": producto,
        "tamaño": tamaño,
        "extras": parsed_extras,
        "ingredientes_removidos": parsed_removidos,
        "total": total,
    }


def extract_order_details(content: str) -> tuple[bool, dict[str, Any] | None]:
    is_order = "📝 PEDIDO:" in content
    order_details = None

    if is_order:
        match = re.search(
            r"📝\s*PEDIDO:\s*(.*)",
            content,
            re.DOTALL,
        )

        if match:
            raw = match.group(1).strip()
            raw = re.split(r"\n\s*(?:PROMOCIONES:|PEDIDOS:)\b", raw, maxsplit=1)[0].strip()
            parsed = _parse_order_section(raw)
            parsed["raw"] = raw
            order_details = parsed

    return is_order, order_details