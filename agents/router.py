import re
from typing import List, Optional, Dict, Any
from agents.base import BaseAgent
from agents.rag_agent import RAGAgent
from agents.transaction_agent import TransactionAgent

class RouterAgent:
    """
    Agente Orquestador - Decide a qué especialista delegar.
    """
    
    def __init__(self):
        self.agents: List[BaseAgent] = []
        self._register_agents()
    
    def _register_agents(self):
        """Registra todos los agentes disponibles."""
        self.agents.append(RAGAgent())
        self.agents.append(TransactionAgent())
    
    async def route(self, query: str, history: list[dict], **kwargs) -> Dict[str, Any]:
        """
        Analiza la consulta y la delega al agente correcto.
        """
        print(f"\n🚀 [ROUTER] Analizando consulta: '{query}'")
        print(f"📝 [ROUTER] Historial: {len(history)} mensajes")
        
        # 1. Detectar off-topic primero
        if self._is_off_topic(query):
            print("⚠️ [ROUTER] Consulta fuera del dominio")
            return {
                "agent": "off_topic",
                "reply": "Lo siento, solo puedo ayudarte con temas relacionados con la pizzería 220. 🍕",
                "is_order": False,
                "order_details": None
            }
        
        # 2. Intentar encontrar el agente correcto
        for agent in self.agents:
            if agent.can_handle(query, history):
                print(f"✅ [ROUTER] Delegando a: {agent.name}")
                result = await agent.process(query, history, **kwargs)
                result["agent"] = agent.name
                return result
        
        # 3. Fallback al agente RAG
        print("⚠️ [ROUTER] Fallback al agente RAG")
        result = await self.agents[0].process(query, history, **kwargs)
        result["agent"] = self.agents[0].name
        return result
    
    def _is_off_topic(self, query: str) -> bool:
        """Detecta consultas fuera del dominio de la pizzería."""
        # Si el mensaje es muy corto, no considerarlo off-topic
        if len(query.split()) < 2:
            return False
        
        # Palabras clave del dominio
        domain_keywords = {
            "pizza", "pizzeria", "pizzería", "pedido", "orden", "menú", "menu",
            "promoción", "promo", "precio", "costo", "ingrediente", "extra",
            "tamaño", "grande", "mediana", "personal", "refresco", "bebida",
            "pago", "efectivo", "tarjeta", "ubicación", "direccion", "horario",
            "telefono", "contacto", "delivery", "domicilio", "reparto",
            "quiero", "dame", "me das", "ordenar", "comprar"
        }
        
        query_lower = query.lower()
        
        # Saludos válidos
        saludos = {"hola", "buenas", "hey", "saludos", "qué tal", "que tal"}
        if any(s in query_lower for s in saludos):
            # Si solo es un saludo, no es off-topic
            if len(query.split()) <= 3:
                return False
        
        # Contar palabras clave del dominio
        matches = sum(1 for kw in domain_keywords if kw in query_lower)
        
        # Si tiene al menos 1 palabra clave del dominio, es válido
        if matches >= 1:
            return False
        
        # Si no tiene palabras del dominio, es off-topic
        return True