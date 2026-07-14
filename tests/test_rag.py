# test_rag.py
import asyncio
from services.rag_service import retrieve_context, get_pizza_names

async def test():
    # Probar búsqueda híbrida
    context = await retrieve_context("¿Qué pizzas tienen?")
    print(f"Contexto recuperado: {len(context)} caracteres")
    print(context[:500])
    
    # Probar nombres de pizzas
    pizzas = get_pizza_names()
    print(f"Pizzas encontradas: {pizzas}")

asyncio.run(test())