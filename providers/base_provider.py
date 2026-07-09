from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List


class BaseProvider(ABC):
    """Interfaz base para proveedores de IA."""

    @abstractmethod
    def generate(self, prompt: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    def embed(self, text: str, **kwargs: Any) -> List[float]:
        raise NotImplementedError

    @abstractmethod
    def stream(self, prompt: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    def health(self) -> bool:
        raise NotImplementedError

    def invoke(self, prompt: Any, **kwargs: Any) -> Any:
        return self.generate(prompt, **kwargs)
