from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class BaseAgent(ABC):
    """Clase base para todos los agentes especializados."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    async def process(self, query: str, history: list[dict], **kwargs) -> Dict[str, Any]:
        """
        Procesa una consulta y devuelve una respuesta.
        
        Args:
            query: Mensaje del usuario
            history: Historial de conversación
            **kwargs: Argumentos adicionales (user_id, context, etc.)
            
        Returns:
            Dict con: reply, is_order, order_details, agent
        """
        pass
    
    @abstractmethod
    def can_handle(self, query: str, history: list[dict]) -> bool:
        """
        Determina si este agente puede manejar la consulta.
        
        Args:
            query: Mensaje del usuario
            history: Historial de conversación
            
        Returns:
            True si el agente puede manejar la consulta
        """
        pass