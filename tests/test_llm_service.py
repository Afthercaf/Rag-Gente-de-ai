import unittest

from services.intent_detector import (
    LITERAL_RESPONSE_PREFIX,
    build_directive,
)



class TestLLMService(unittest.TestCase):
    def test_multiple_pizzas_preserve_each_product(self) -> None:
        directive = build_directive(
            question="1 Margarita, 3 Pepperoni y 2 Pastorera",
            pizza_names=["Margarita", "Pepperoni", "Pastorera"],
            history=[],
            extras_context="",
            context=(
                "Pizza Margarita — $105.00\n"
                "Pizza Pepperoni — $115.00\n"
                "Pizza Pastorera — $220.00\n"
            ),
        )
        self.assertTrue(directive.startswith(LITERAL_RESPONSE_PREFIX))
        self.assertIn("1 × Pizza Margarita", directive)
        self.assertIn("3 × Pizza Pepperoni", directive)
        self.assertIn("2 × Pizza Pastorera", directive)
        self.assertIn("Cantidad: 6", directive)
        self.assertIn("Total: $890.00", directive)

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

    def test_pizza_price_ignores_promotions(self) -> None:
        history = [
            {"user": "Quiero una Pizza Pepperoni", "assistant": "La Pizza Pepperoni incluye: queso Gouda y salsa. ¿Deseas quitar alguno? 🥗"},
            {"user": "no", "assistant": "¡Entendido! 🍕 Estos son los extras disponibles para tu pizza:\n• pepperoni  —  $ 45.00 MXN\n\n¿Te gustaría agregar alguno? ➕"}
        ]
        context = (
            "DOCUMENTOS:\n"
            "Pizza Pepperoni\n"
            "Descripción: Pizza grande de pepperoni.\n"
            "Costo: $115.00 MXN\n"
            "\n"
            "PROMOCIONES:\n"
            "PROMOCION:\n"
            "Promo Familiar\n"
            "INGREDIENTES:\n"
            "Pepperoni y hawaiana\n"
            "PRECIO:\n"
            "$399\n"
        )
        directive = build_directive(
            question="no",
            pizza_names=["Pepperoni"],
            history=history,
            extras_context="• queso extra  —  $ 45.00 MXN",
            context=context
        )
        self.assertTrue(directive.startswith(LITERAL_RESPONSE_PREFIX))
        self.assertIn("Producto: Pizza Pepperoni", directive)
        self.assertIn("Total: $115.00", directive)

    def test_pizza_price_does_not_use_matching_extra(self) -> None:
        history = [
            {"user": "Quiero una Pizza Pepperoni", "assistant": "La Pizza Pepperoni incluye queso. ¿Deseas quitar alguno?"},
            {"user": "no", "assistant": "Extras disponibles. ¿Te gustaría agregar alguno?"},
        ]
        context = (
            "EXTRAS\n"
            "• Pepperoni — $45.00 MXN\n"
            "\n"
            "Pizza Pepperoni\n"
            "Costo: $115.00 MXN\n"
        )
        directive = build_directive(
            question="no",
            pizza_names=["Pepperoni"],
            history=history,
            extras_context="• Pepperoni — $45.00 MXN",
            context=context,
        )
        self.assertTrue(directive.startswith(LITERAL_RESPONSE_PREFIX))
        self.assertIn("Total: $115.00", directive)
        self.assertNotIn("Total: $45.00", directive)

    def test_quantity_extraction_multiple_pizzas(self) -> None:
        history = [
            {"user": "Quiero 2 pizzas Pepperoni", "assistant": "La Pizza Pepperoni incluye: queso Gouda y salsa. ¿Deseas quitar alguno? 🥗"},
            {"user": "no", "assistant": "¡Entendido! 🍕 Estos son los extras disponibles para tu pizza:\n• pepperoni  —  $ 45.00 MXN\n\n¿Te gustaría agregar alguno? ➕"}
        ]
        context = (
            "DOCUMENTOS:\n"
            "Pizza Pepperoni\n"
            "Descripción: Pizza grande de pepperoni.\n"
            "Costo: $115.00 MXN\n"
            "\n"
            "PROMOCIONES:\n"
        )
        directive = build_directive(
            question="no",
            pizza_names=["Pepperoni"],
            history=history,
            extras_context="• queso extra  —  $ 45.00 MXN",
            context=context
        )
        self.assertTrue(directive.startswith(LITERAL_RESPONSE_PREFIX))
        self.assertIn("Cantidad: 2", directive)
        self.assertIn("Total: $230.00", directive)

    def test_single_pizza_no_extras(self) -> None:
        history = [
            {"user": "Quiero una Pizza Pepperoni", "assistant": "La Pizza Pepperoni incluye: queso Gouda y salsa. ¿Deseas quitar alguno? 🥗"},
            {"user": "no", "assistant": "¡Entendido! 🍕 Estos son los extras disponibles para tu pizza:\n• pepperoni  —  $ 45.00 MXN\n\n¿Te gustaría agregar alguno? ➕"}
        ]
        context = (
            "DOCUMENTOS:\n"
            "Pizza Pepperoni\n"
            "Descripción: Pizza grande de pepperoni.\n"
            "Costo: $115.00 MXN\n"
            "\n"
            "PROMOCIONES:\n"
        )
        directive = build_directive(
            question="no",
            pizza_names=["Pepperoni"],
            history=history,
            extras_context="• queso extra  —  $ 45.00 MXN",
            context=context
        )
        self.assertTrue(directive.startswith(LITERAL_RESPONSE_PREFIX))
        self.assertIn("Cantidad: 1", directive)
        self.assertIn("Producto: Pizza Pepperoni", directive)
        self.assertIn("Extras: Ninguno", directive)
        self.assertIn("Total: $115.00", directive)


if __name__ == "__main__":
    unittest.main()
