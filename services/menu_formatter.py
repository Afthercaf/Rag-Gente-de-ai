"""
MenuFormatter — genera un menú limpio y estructurado para el cliente.

El RAG context (chunks del PDF, FAQ, reglas, recomendaciones) NUNCA se
muestra al usuario. Este formateador toma los bloques crudos del menú
extraídos por rag_service.get_menu_context() y los convierte en un
formato profesional con categorías: Pizzas, Bebidas, Extras.

Uso:
    from services.menu_formatter import MenuFormatter
    formatter = MenuFormatter()
    menu_text = formatter.format()
"""

import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"\$\s*(\d+(?:[.,]\d{1,2})?)")


class MenuFormatter:
    """Formatea el menú de la pizzería en un texto limpio para el cliente.

    Toma los bloques crudos de get_menu_context() y los estructura en:
      - Pizzas (nombre + precio)
      - Bebidas (nombre + precio)
      - Extras (nombre + precio c/u)

    Nunca incluye: FAQ, reglas del asistente, recomendaciones, información
    general de pizzerías, metadatos del documento, ni ningún otro contenido
    interno del RAG.
    """

    # Nombres de pizzas conocidas (para identificación)
    PIZZA_NAMES = {
        "margarita", "pepperoni", "mexicana", "pastorera", "campirana",
    }

    def __init__(self, raw_blocks: Optional[List[str]] = None):
        """
        Args:
            raw_blocks: Lista de strings con bloques del menú (cada bloque
                        es una línea o multi-línea con nombre y precio).
                        Si es None, se obtiene de rag_service.get_menu_context().
        """
        self._raw_blocks = raw_blocks

    def _get_blocks(self) -> List[str]:
        """Obtiene los bloques del menú, desde cache o desde rag_service."""
        if self._raw_blocks is not None:
            return self._raw_blocks

        from services.rag_service import get_menu_context
        raw = get_menu_context()
        if not raw:
            return []
        return [ln.strip() for ln in raw.split("\n") if ln.strip()]

    def _is_pizza_block_start(self, line: str) -> bool:
        """Detecta si una línea es el inicio de un bloque de pizza (nombre de pizza)."""
        lower = line.lower().strip()
        for pname in self.PIZZA_NAMES:
            if lower == f"pizza {pname}" or lower.startswith(f"pizza {pname}"):
                return True
        return False

    def _is_beverage_line(self, line: str) -> bool:
        """Detecta si una línea describe una bebida con precio.

        Solo detecta líneas que EXPLÍCITAMENTE mencionen una bebida
        del menú (Coca-Cola, refresco, bebida) con precio. Filtra
        ruido como FAQ del RAG, respuestas, etc.
        """
        lower = line.lower()
        has_price = bool(_PRICE_RE.search(line))
        # Excluir líneas de FAQ o respuestas
        if lower.startswith("respuesta:") or lower.startswith("pregunta:"):
            return False
        # Excluir líneas que hablan de pizzas (pero permitir "bebida")
        if "pizza" in lower and "bebida" not in lower:
            return False
        # Excluir líneas con "incluye refresco" (son descripciones de pizza)
        if lower.startswith("incluye refresco"):
            return False
        # Debe mencionar explícitamente una bebida o refresco
        is_beverage = (
            "coca" in lower
            or "cola" in lower
            or "bebida" in lower
            or lower.startswith("refresco")
        )
        return has_price and is_beverage

    def _is_extra_line(self, line: str) -> bool:
        """Detecta si una línea describe un extra/adicional con precio.

        Solo detecta líneas que EXPLÍCITAMENTE nombren un extra
        del menú seguido de su precio (formato "Nombre: $precio").
        """
        lower = line.lower()
        has_price = bool(_PRICE_RE.search(line))
        # Debe tener formato "Nombre: $precio" o "Nombre $precio"
        has_format = bool(re.search(r"(?:extra|adicional|orilla)\s*[:$]", lower))
        # O debe empezar con nombre de extra conocido
        starts_with_extra = any(
            lower.startswith(kw) for kw in ["queso extra", "orilla de queso", "ingrediente extra"]
        )
        # Excluir líneas que son listas de ingredientes (tienen comas y muchas palabras)
        if lower.count(",") > 2:
            return False
        return has_price and (has_format or starts_with_extra)

    def _extract_price_from_block(self, block: str) -> str:
        """Extrae el precio de un bloque multi-línea de pizza."""
        for line in block.split("\n"):
            m = _PRICE_RE.search(line)
            if m and ("costo" in line.lower() or "precio" in line.lower() or "$" in line):
                return f"${m.group(1)} MXN"
        m = _PRICE_RE.search(block)
        if m:
            return f"${m.group(1)} MXN"
        return ""

    def _extract_ingredients_from_block(self, block: str) -> str:
        """Extrae los ingredientes de un bloque multi-línea de pizza."""
        for line in block.split("\n"):
            if "ingredientes" in line.lower() and ":" in line:
                parts = line.split(":", 1)
                if len(parts) > 1:
                    return parts[1].strip().rstrip(".")
        return ""

    def _parse_pizza_blocks(self, blocks: List[str]) -> List[Dict[str, str]]:
        """Parsea bloques multi-línea de pizza en una lista ordenada."""
        pizzas: Dict[str, Dict[str, str]] = {}
        current_block: List[str] = []
        current_name = ""

        for line in blocks:
            if self._is_pizza_block_start(line):
                if current_block and current_name:
                    block_text = "\n".join(current_block)
                    price = self._extract_price_from_block(block_text)
                    ingredients = self._extract_ingredients_from_block(block_text)
                    name_key = current_name.lower().strip()
                    pizzas[name_key] = {
                        "name": current_name,
                        "price": price,
                        "ingredients": ingredients,
                    }
                current_name = line.strip()
                current_block = [line]
            elif current_block:
                current_block.append(line)

        if current_block and current_name:
            block_text = "\n".join(current_block)
            price = self._extract_price_from_block(block_text)
            ingredients = self._extract_ingredients_from_block(block_text)
            name_key = current_name.lower().strip()
            pizzas[name_key] = {
                "name": current_name,
                "price": price,
                "ingredients": ingredients,
            }

        result = list(pizzas.values())
        def _price_sort_key(p: dict) -> float:
            m = _PRICE_RE.search(p["price"])
            if m:
                return float(m.group(1).replace(",", "."))
            return 999999
        result.sort(key=_price_sort_key)
        return result

    def _parse_beverages(self, blocks: List[str]) -> List[Dict[str, str]]:
        """Parsea las líneas de bebidas.

        La única bebida en el menú es Coca-Cola 1.35L a $45.00 MXN.
        """
        bebidas = []
        seen = set()

        for line in blocks:
            if not self._is_beverage_line(line):
                continue

            m = _PRICE_RE.search(line)
            price = f"${m.group(1)} MXN" if m else ""

            # La única bebida del menú es Coca-Cola 1.35L
            name = "Coca-Cola 1.35L"

            key = name.lower().strip()
            if key in seen:
                continue
            seen.add(key)

            bebidas.append({"name": name, "price": price})

        return bebidas

    def _parse_extras(self, blocks: List[str]) -> List[Dict[str, str]]:
        """Parsea las líneas de extras/adicionales."""
        extras = []
        seen = set()

        for line in blocks:
            if not self._is_extra_line(line):
                continue

            m = _PRICE_RE.search(line)
            price = f"${m.group(1)} MXN" if m else ""

            name = line
            if m:
                name = line[:m.start()].strip()
            name = re.sub(r"^[•\-*\s]+", "", name).strip()
            name = re.sub(r"[:\-–—]+$", "", name).strip()

            if not name:
                continue

            key = name.lower().strip()
            if key in seen:
                continue
            seen.add(key)

            extras.append({"name": name, "price": price})

        return extras


    def _parse_runtime_extras(self) -> List[Dict[str, str]]:
        """Obtiene extras concretos desde el contexto dinámico de extras.

        Evita mostrar únicamente el concepto genérico "Ingrediente extra".
        También deduplica nombres repetidos provenientes de varios chunks RAG.
        """
        try:
            from services.rag_service import get_available_extras_context
            raw = get_available_extras_context()
        except Exception:
            raw = ""

        if not raw:
            return []

        extras: List[Dict[str, str]] = []
        seen = set()

        pattern = re.compile(
            r"^[\s•\-*]+(.+?)\s*(?:—|-|:)\s*\$\s*(\d+(?:[.,]\d{1,2})?)",
            re.IGNORECASE,
        )

        for line in raw.splitlines():
            match = pattern.search(line.strip())
            if not match:
                continue

            name = re.sub(r"\s+", " ", match.group(1)).strip()
            key = name.lower()

            if not name or key == "ingrediente extra" or key in seen:
                continue

            seen.add(key)
            extras.append({
                "name": name,
                "price": f"${match.group(2)} MXN",
            })

        return extras

    def _merge_extras(
        self,
        menu_extras: List[Dict[str, str]],
        runtime_extras: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        """Fusiona extras del menú y extras concretos, sin duplicados.

        "Ingrediente extra" es una categoría genérica, no un producto
        seleccionable, por eso se elimina cuando existen extras concretos.
        """
        merged: List[Dict[str, str]] = []
        seen = set()

        concrete_available = bool(runtime_extras)

        for item in [*menu_extras, *runtime_extras]:
            name = (item.get("name") or "").strip()
            key = name.lower()

            if not name:
                continue
            if concrete_available and key == "ingrediente extra":
                continue
            if key in seen:
                continue

            seen.add(key)
            merged.append(item)

        return merged

    def format(self) -> str:
        """Genera el menú completo formateado para mostrar al cliente.

        Returns:
            str: Texto del menú limpio y estructurado, o cadena vacía si
                 no hay datos disponibles.
        """
        blocks = self._get_blocks()
        if not blocks:
            return ""

        pizzas = self._parse_pizza_blocks(blocks)
        bebidas = self._parse_beverages(blocks)
        extras = self._merge_extras(
            self._parse_extras(blocks),
            self._parse_runtime_extras(),
        )

        lines: List[str] = []
        lines.append("🍕 **Menú**")
        lines.append("")

        if pizzas:
            lines.append("**Pizzas**")
            lines.append("")
            for p in pizzas:
                line = f"• {p['name']}"
                if p['price']:
                    line += f" — {p['price']}"
                lines.append(line)
            lines.append("")

        if bebidas:
            lines.append("🥤 **Bebidas**")
            lines.append("")
            for b in bebidas:
                line = f"• {b['name']}"
                if b['price']:
                    line += f" — {b['price']}"
                lines.append(line)
            lines.append("")

        if extras:
            prices = set()
            for e in extras:
                if e['price']:
                    prices.add(e['price'])
            common_price = prices.pop() if len(prices) == 1 else None

            if common_price:
                lines.append(f"➕ **Extras ({common_price} c/u)**")
            else:
                lines.append("➕ **Extras**")
            lines.append("")
            for e in extras:
                if e['price']:
                    lines.append(f"• {e['name']} — {e['price']}")
                else:
                    lines.append(f"• {e['name']}")
            lines.append("")

        # ── PROMOCIONES desde Supabase ───────────────────────────────
        try:
            from core.state import state
            promos = state.get("promo_documents", [])
            if promos:
                promo_texts = [p.page_content for p in promos if p and p.page_content]
                if promo_texts:
                    lines.append("🎉 **Promociones vigentes**")
                    lines.append("")
                    for pt in promo_texts:
                        for pt_line in pt.split("\n"):
                            pt_line = pt_line.strip()
                            if pt_line:
                                lines.append(f"• {pt_line}")
                    lines.append("")
        except Exception:
            pass

        lines.append("¿Cuál te gustaría ordenar? 🍕")

        return "\n".join(lines)

    def format_pizza_list(self) -> str:
        """Genera solo la lista de pizzas con precios (sin bebidas ni extras)."""
        blocks = self._get_blocks()
        if not blocks:
            return ""

        pizzas = self._parse_pizza_blocks(blocks)
        if not pizzas:
            return ""

        lines = ["**Pizzas**", ""]
        for p in pizzas:
            line = f"• {p['name']}"
            if p['price']:
                line += f" — {p['price']}"
            lines.append(line)

        return "\n".join(lines)
        
        