# test_rag.py
import asyncio

from services.rag_service import get_pizza_names, retrieve_context


def test_rag_retrieval_contract():
    context = asyncio.run(retrieve_context("¿Qué pizzas tienen?"))
    pizzas = get_pizza_names()

    assert isinstance(context, str)
    assert isinstance(pizzas, list)
    assert all(isinstance(pizza, str) for pizza in pizzas)
