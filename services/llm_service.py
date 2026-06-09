import asyncio
import re

from core.state import state


async def generate_response(context: str, history: str, question: str) -> str:
    """Invoca el LLM con el prompt armado y retorna el contenido de la respuesta."""
    prompt = state["prompt_template"].format_messages(
        context=context,
        history=history,
        question=question,
    )

    model = state["model_loader"].model
    state["model_loaded"] = True

    response = await asyncio.to_thread(model.invoke, prompt)
    return response.content.strip()


def extract_order_details(content: str) -> tuple[bool, str | None]:
    """
    Detecta si la respuesta contiene un pedido y extrae sus detalles.

    Returns:
        (is_order, order_details)
    """
    is_order = "📝 PEDIDO:" in content
    order_details = None

    if is_order:
        match = re.search(r"📝 PEDIDO:\s*(.*)", content, re.DOTALL)
        if match:
            raw = match.group(1).strip()
            # Limpiar bloques que el modelo pueda agregar de más
            raw = raw.split("PROMOCIONES:", 1)[0]
            raw = raw.split("PEDIDOS:", 1)[0]
            order_details = raw.strip()

    return is_order, order_details
