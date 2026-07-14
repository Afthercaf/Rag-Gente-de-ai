from typing import Any, Dict, Optional
from agents.base import BaseAgent
from services import order_service, llm_service
from services.intent_detector import (
    build_directive, 
    is_order_flow_active, 
    get_active_order_step
)
from services.rag_service import get_pizza_names, get_available_extras_context
from services.session_service import build_history_text, get_user_session

class TransactionAgent(BaseAgent):
    """
    Agente Especialista Transaccional - Maneja pedidos, pagos y operaciones.
    """
    
    def __init__(self):
        super().__init__(
            name="TRANSACTION_AGENT",
            description="Especialista en pedidos, pagos y transacciones."
        )
    
    def can_handle(self, query: str, history: list[dict]) -> bool:
        """
        Determina si esta consulta es transaccional.
        """
        # Palabras clave de transacciones
        trans_keywords = {
            "pedir", "ordenar", "quiero", "dame", "comprar", "pagar",
            "efectivo", "tarjeta", "mercado pago", "confirmar", "ubicación",
            "dirección", "domicilio", "reparto", "entrega", "pedido",
            "orden", "costo", "total", "precio", "me das", "me puedes dar"
        }
        
        query_lower = query.lower()
        
        # Si hay un flujo activo, es transaccional
        if is_order_flow_active(history):
            return True
        
        # Si contiene palabras clave de transacción
        if any(kw in query_lower for kw in trans_keywords):
            return True
        
        # Si menciona una pizza y tiene intención de orden
        pizza_names = get_pizza_names()
        if pizza_names:
            for pizza in pizza_names:
                if pizza.lower() in query_lower:
                    # Verificar que no sea una pregunta
                    question_keywords = {"cuánto", "cuanto", "precio", "cuesta", "qué", "que"}
                    if not any(kw in query_lower for kw in question_keywords):
                        return True
        
        return False
    
    async def process(self, query: str, history: list[dict], **kwargs) -> Dict[str, Any]:
        """
        Procesa la consulta transaccional.
        """
        print(f"💳 [TRANSACTION_AGENT] Procesando: '{query}'")
        
        user_id = kwargs.get("user_id", 0)
        session = get_user_session(user_id)
        
        # Verificar si hay flujo activo
        active_step = get_active_order_step(history)
        
        if active_step:
            print(f"🔄 [TRANSACTION_AGENT] Flujo activo - Paso {active_step}")
        
        # Obtener contexto para transacciones
        pizza_names = get_pizza_names()
        extras_context = get_available_extras_context()
        context = ""  # Se puede obtener del RAG si es necesario
        
        # Construir directiva transaccional
        directive = build_directive(
            query,
            pizza_names,
            history,
            extras_context=extras_context,
            context=context,
        )
        
        # Generar respuesta transaccional
        response = await llm_service.generate_response(
            context=context,
            history_text=build_history_text(session),
            question=query,
            history=history,
        )
        
        # Si la respuesta es un dict, extraer el reply
        if isinstance(response, dict):
            reply = response.get("reply", str(response))
            is_order = response.get("is_order", True)
            order_details = response.get("order_details")
        else:
            reply = response
            is_order = True
            order_details = None
        
        return {
            "reply": reply,
            "is_order": is_order,
            "order_details": order_details,
            "rag_used": False,
        }