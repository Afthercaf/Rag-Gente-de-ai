from __future__ import annotations

from decimal import Decimal
from typing import Any

from services import rag_service
from services.intent_detector import (
    _formatted_menu_catalog,
    _menu_pizza_price,
    _normalize,
    _parse_priced_items,
)


_MAX_ITEMS = 20
_MAX_TOTAL = Decimal("100000")


def _money(value: Any) -> Decimal:
    amount = Decimal(str(value)).quantize(Decimal("0.01"))
    if amount <= 0 or amount > _MAX_TOTAL:
        raise ValueError("Precio fuera de rango.")
    return amount


def calculate_verified_cart_total(cart: dict[str, Any]) -> Decimal:
    """Recalcula el total exclusivamente desde el menú del servidor."""
    items = cart.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= _MAX_ITEMS:
        raise ValueError("El carrito no contiene ítems válidos.")

    menu_context = rag_service.get_menu_context() or ""
    if not menu_context:
        raise ValueError("El menú del servidor no está disponible.")
    _, _, beverages_catalog = _formatted_menu_catalog()
    beverage_prices = {
        _normalize(name): _money(price)
        for name, price in beverages_catalog.items()
    }

    total = Decimal("0")
    for item in items:
        pizza_name = str(item.get("pizza") or "").strip()
        catalog_price = _menu_pizza_price(pizza_name, menu_context)
        if catalog_price is None:
            raise ValueError("Pizza fuera del menú.")
        total += _money(catalog_price)

        extras_context = rag_service.get_available_extras_context(pizza_name)
        extra_prices = {
            _normalize(name): _money(price)
            for name, price in _parse_priced_items(extras_context)
        }
        for extra in item.get("extras", []):
            name = _normalize(str(extra.get("name") or ""))
            if name not in extra_prices:
                raise ValueError("Extra fuera del catálogo.")
            total += extra_prices[name]

        for beverage in item.get("beverages", []):
            total += _verified_beverage_total(beverage, beverage_prices)

    for beverage in cart.get("beverages", []):
        total += _verified_beverage_total(beverage, beverage_prices)

    if total <= 0 or total > _MAX_TOTAL:
        raise ValueError("Total fuera de rango.")
    return total.quantize(Decimal("0.01"))


def _verified_beverage_total(
    beverage: dict[str, Any],
    catalog: dict[str, Decimal],
) -> Decimal:
    name = _normalize(str(beverage.get("name") or ""))
    if name not in catalog:
        raise ValueError("Bebida fuera del catálogo.")
    quantity = int(beverage.get("quantity", 1))
    if not 1 <= quantity <= _MAX_ITEMS:
        raise ValueError("Cantidad de bebida inválida.")
    return catalog[name] * quantity
