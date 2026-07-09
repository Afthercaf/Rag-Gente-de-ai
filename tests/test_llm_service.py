import unittest

from services.intent_detector import (
    LITERAL_RESPONSE_PREFIX,
    _extract_beverage_from_text,
    _extract_order_quantity_from_text,
    build_directive,
)
from services.llm_service import strip_think_blocks


class StripThinkBlocksTest(unittest.TestCase):
    def test_removes_think_block_and_keeps_client_message(self) -> None:
        raw = "<think>internal reasoning</think>\n¡Hola! 😊 ¿Cómo te ayudo?"
        self.assertEqual(strip_think_blocks(raw), "¡Hola! 😊 ¿Cómo te ayudo?")

    def test_returns_text_unchanged_when_no_think_block(self) -> None:
        raw = "¡Hola! 😊 ¿Cómo te ayudo?"
        self.assertEqual(strip_think_blocks(raw), raw)

    def test_removes_instruction_echo_from_model_output(self) -> None:
        raw = (
            "El cliente respondió 'no' y no quiere quitar ingredientes. "
            "RESPONDE CON ESTE FORMATO EXACTO ...\n"
            "REGLAS OBLIGATORIAS:\n"
            "¡Entendido! 🍕 Estos son los extras disponibles para tu pizza:"
        )
        cleaned = strip_think_blocks(raw)
        self.assertNotIn("RESPONDE CON ESTE FORMATO EXACTO", cleaned)
        self.assertNotIn("REGLAS OBLIGATORIAS", cleaned)
        self.assertIn("¡Entendido! 🍕", cleaned)

    def test_extracts_quantity_and_beverage_from_order_text(self) -> None:
        quantity = _extract_order_quantity_from_text("2 Pizza Margarita y coca cola")
        beverage = _extract_beverage_from_text("2 Pizza Margarita y coca cola")
        self.assertEqual(quantity, 2)
        self.assertEqual(beverage, "Coca-Cola")

    def test_repeat_offer_negative_returns_literal_menu_response(self) -> None:
        history = [
            {"user": "hola", "assistant": "¿Te gustaría ordenar lo mismo o prefieres ver el menú completo?"},
            {"user": "no", "assistant": "¿Te gustaría ordenar lo mismo o prefieres ver el menú completo?"},
        ]
        directive = build_directive(
            question="no",
            pizza_names=["Pizza Margarita"],
            history=history,
            extras_context="",
            context="Menú completo",
        )
        self.assertTrue(directive.startswith(LITERAL_RESPONSE_PREFIX))
        self.assertIn("menú completo", directive.lower())
        self.assertIn("¿Cuál te llama la atención? 🍕", directive)

    def test_menu_request_overrides_active_order_flow(self) -> None:
        history = [
            {"user": "2 Pizza Margarita y coca cola", "assistant": "La Pizza Margarita incluye: queso Gouda y salsa pizzera. ¿Deseas quitar alguno? 🥗"},
            {"user": "no", "assistant": "¡Entendido! 🍕 Estos son los extras disponibles... ¿Te gustaría agregar alguno? ➕"},
        ]
        directive = build_directive(
            question="menu",
            pizza_names=["Pizza Margarita"],
            history=history,
            extras_context="",
            context="Menú completo",
        )
        self.assertTrue(directive.startswith(LITERAL_RESPONSE_PREFIX))
        self.assertIn("menú completo", directive.lower())


if __name__ == "__main__":
    unittest.main()
