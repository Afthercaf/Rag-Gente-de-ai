import unittest

from services.intent_detector import (
    LITERAL_RESPONSE_PREFIX,
    build_directive,
)



class TestLLMService(unittest.TestCase):
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
        self.assertIn("menú completo", directive.lower())

    def test_extras_negative_response_returns_summary(self) -> None:
        history = [
            {"user": "Quiero una Pizza Margarita", "assistant": "La Pizza Margarita incluye: queso y salsa. ¿Deseas quitar alguno? 🥗"},
            {"user": "no", "assistant": "¡Entendido! 🍕 Estos son los extras disponibles para tu pizza:\n• pepperoni  —  $ 45.00 MXN\n\n¿Te gustaría agregar alguno? ➕"}
        ]
        
        for negative_ans in ["no", "ninguna", "ninguno", "nada"]:
            directive = build_directive(
                question=negative_ans,
                pizza_names=["Pizza Margarita"],
                history=history,
                extras_context="• pepperoni  —  $ 45.00 MXN",
                context="La Pizza Margarita cuesta $150.00 MXN"
            )
            self.assertTrue(directive.startswith(LITERAL_RESPONSE_PREFIX))
            self.assertIn("PEDIDO:", directive)
            self.assertIn("Extras: Ninguno", directive)
            self.assertIn("Total: $150.00", directive)


if __name__ == "__main__":
    unittest.main()
