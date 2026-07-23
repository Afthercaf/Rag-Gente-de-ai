import time
import threading
from typing import Any, Dict

from services.provider_service import provider_service


class LazyModelLoader:
    """Carga el modelo LLM solo cuando se necesita (lazy loading)."""

    def __init__(self):
        self._model = None
        self._lock = threading.Lock()

    @property
    def model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    print("🔄 Cargando modelo LLM bajo demanda...")
                    start = time.time()
                    self._model = provider_service.llm_provider
                    print(f"✅ Proveedor LLM listo en {time.time() - start:.2f}s")
        return self._model


# Estado global de la aplicación
state: Dict[str, Any] = {
    "db": None,
    "promo_documents": [],
    "model_loaded": False,
    "prompt_template": None,
    "ready": False,
    "loading_task": None,
    "embedding_model": None,
    "menu_loaded": False,
    "startup_time": time.time(),
    "model_loader": LazyModelLoader(),
}
