import time
import threading
from typing import Any, Dict

from langchain_ollama import ChatOllama
from utils.constants import CHAT_MODEL


class LazyModelLoader:
    """Carga el modelo LLM solo cuando se necesita (lazy loading)."""

    def __init__(self):
        self._model = None
        self._lock = threading.Lock()

    @property
    def model(self) -> ChatOllama:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    print("🔄 Cargando modelo LLM bajo demanda...")
                    start = time.time()
                    self._model = ChatOllama(
                        model=CHAT_MODEL,
                        temperature=0.2,
                        num_ctx=4096,
                        num_predict=512,
                        repeat_penalty=1.1,
                        top_k=40,
                        top_p=0.9,
                    )
                    print(f"✅ Modelo cargado en {time.time() - start:.2f}s")
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
    "startup_time": time.time(),
    "model_loader": LazyModelLoader(),
}
