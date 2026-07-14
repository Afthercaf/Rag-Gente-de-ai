from typing import Any, Dict, Optional
from agents.base import BaseAgent
from services import rag_service, llm_service
from services.intent_detector import build_directive
from services.session_service import build_history_text

class RAGAgent(BaseAgent):
    """
    Agente Especialista en RAG - Busca información en documentos estáticos.
    """
    
    def __init__(self):
        super().__init__(
            name="RAG_AGENT",
            description="Especialista en información del menú, promociones, precios e ingredientes."
        )
    
    def can_handle(self, query: str, history: list[dict]) -> bool:
        """
        Determina si esta consulta es de tipo RAG.
        """
        # Palabras clave de información
        rag_keywords = {
            "menú", "menu", "pizza", "ingrediente", "precio", "costo", 
            "promoción", "promo", "tamaño", "grande", "mediana", "personal",
            "refresco", "bebida", "horario", "ubicación", "direccion",
            "telefono", "contacto", "qué tienen", "que tienen",
            "qué hay", "que hay", "cómo", "como", "cuándo", "cuando"
        }
        
        query_lower = query.lower()
        
        # Si contiene palabras clave de RAG
        if any(kw in query_lower for kw in rag_keywords):
            return True
        
        # Si es un saludo simple
        saludos = {"hola", "buenas", "hey", "saludos"}
        if any(s in query_lower for s in saludos) and len(query.split()) <= 3:
            return True
        
        return False
    
    async def process(self, query: str, history: list[dict], **kwargs) -> Dict[str, Any]:
        """
        Procesa la consulta usando el pipeline RAG.
        """
        print(f"📚 [RAG_AGENT] Procesando: '{query}'")
        
        user_id = kwargs.get("user_id", 0)
        
        # 1. Obtener contexto del RAG (con búsqueda híbrida + reranker)
        pizza_names = rag_service.get_pizza_names()
        rag_context = await rag_service.retrieve_context(query)
        promos_text = rag_service.get_promos_text()
        full_context = rag_service.build_full_context(rag_context, promos_text)
        
        # 2. Obtener extras
        extras_context = rag_service.get_available_extras_context()
        
        # 3. Construir directiva
        directive = build_directive(
            query,
            pizza_names,
            history,
            extras_context=extras_context,
            context=full_context,
        )
        
        # 4. Generar respuesta
        response = await llm_service.generate_response(
            context=full_context,
            history_text=build_history_text({"history": history}),
            question=query,
            history=history,
        )
        
        # Si la respuesta es un dict, extraer el reply
        if isinstance(response, dict):
            reply = response.get("reply", str(response))
            is_order = response.get("is_order", False)
            order_details = response.get("order_details")
        else:
            reply = response
            is_order = False
            order_details = None
        
        return {
            "reply": reply,
            "is_order": is_order,
            "order_details": order_details,
            "rag_used": True,
        }