import logging
import os
from typing import Any

from dotenv import load_dotenv

from config.models import CHAT_MODEL
from providers.base_provider import BaseProvider

load_dotenv()

logger = logging.getLogger(__name__)


class GroqProvider(BaseProvider):
    """Proveedor remoto basado en Groq para modelos LLM."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv("CHAT_MODEL", CHAT_MODEL)
        self.api_key = os.getenv("GROQ_API_KEY")
        self._model = None

    def get_model(self):
        if self._model is None:
            if not self.api_key:
                raise RuntimeError("GROQ_API_KEY no configurada")
            try:
                from langchain_groq import ChatGroq
            except ImportError as exc:
                raise RuntimeError("langchain-groq no está instalado. Instálalo con pip install langchain-groq") from exc
            logger.info("Usando proveedor Groq con modelo: %s", self.model_name)

            # ── FIX: modelos de razonamiento (DeepSeek-R1, QwQ, GPT-OSS, etc.) ──
            # Sin `reasoning_format`, Groq puede devolver el razonamiento crudo
            # (con etiquetas <think>) mezclado directamente en el content de la
            # respuesta. Forzamos "hidden" para que Groq nunca lo incluya en el
            # texto que llega al cliente — la limpieza de <think> en
            # llm_service.py queda como red de seguridad adicional, no como
            # única defensa.
            reasoning_format = os.getenv("GROQ_REASONING_FORMAT", "hidden")

            # ── FIX: sin límite de tokens, un modelo que entra en loop de
            # razonamiento puede seguir generando hasta el máximo del
            # contexto, gastando tokens/tiempo antes de cortarse.
            max_tokens = int(os.getenv("GROQ_MAX_TOKENS", "1024"))

            # Los modelos de razonamiento (ej. QwQ-32B) tienden a repetirse en
            # temperaturas muy bajas; permitimos override vía env var sin
            # cambiar el default para el resto de los modelos.
            temperature = float(os.getenv("GROQ_TEMPERATURE", "0.2"))

            self._model = ChatGroq(
                model=self.model_name,
                groq_api_key=self.api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                reasoning_format=reasoning_format,
            )
        return self._model

    def _get_model_without_reasoning_format(self):
        """
        Fallback para modelos Groq que no soportan `reasoning_format`
        (parámetro exclusivo de modelos de razonamiento). Se usa solo si
        una llamada falla explícitamente por ese motivo.
        """
        from langchain_groq import ChatGroq

        temperature = float(os.getenv("GROQ_TEMPERATURE", "0.2"))
        max_tokens = int(os.getenv("GROQ_MAX_TOKENS", "1024"))
        self._model = ChatGroq(
            model=self.model_name,
            groq_api_key=self.api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return self._model

    def _sanitize_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        sanitized = dict(kwargs)
        stop = sanitized.pop("stop", None)
        if stop is None:
            return sanitized

        if isinstance(stop, str):
            sanitized["stop"] = stop
            return sanitized

        if isinstance(stop, (list, tuple, set)):
            values = [str(item) for item in stop if str(item).strip()]
            if not values:
                return sanitized
            if len(values) == 1:
                sanitized["stop"] = values[0]
            else:
                sanitized["stop"] = values[:4]
            return sanitized

        sanitized["stop"] = str(stop)
        return sanitized

    def generate(self, prompt: Any, **kwargs: Any) -> Any:
        last_error = None
        for attempt in range(3):
            try:
                logger.info("Intento %s de Groq para el modelo %s", attempt + 1, self.model_name)
                return self.get_model().invoke(prompt, **self._sanitize_kwargs(kwargs))
            except Exception as exc:
                last_error = exc
                logger.warning("Groq falló en intento %s: %s", attempt + 1, exc)
                error_text = str(exc).lower()

                # Si el modelo no soporta reasoning_format (no es un modelo
                # de razonamiento), reintentamos sin ese parámetro en vez de
                # agotar los intentos con el mismo error garantizado.
                if "reasoning_format" in error_text:
                    logger.warning(
                        "El modelo %s no soporta reasoning_format; se reintenta sin él.",
                        self.model_name,
                    )
                    self._get_model_without_reasoning_format()
                    continue

                # ── FIX: no reintentar ante rate limit / payload demasiado
                # grande (413/429, "rate_limit_exceeded", "tokens per
                # minute"). El mismo request con el mismo tamaño va a fallar
                # exactamente igual las 3 veces — reintentar solo suma
                # latencia sin ninguna posibilidad de éxito. Cortamos de una.
                if any(
                    marker in error_text
                    for marker in ("rate_limit_exceeded", "tokens per minute", "413", "429", "request too large")
                ):
                    logger.warning(
                        "Groq rechazó la solicitud por límite de tokens/rate limit; "
                        "no tiene sentido reintentar con el mismo payload. Se aborta de inmediato."
                    )
                    raise RuntimeError(
                        "Groq rechazó la solicitud: se excedió el límite de tokens por minuto "
                        f"de la cuenta. Reduce el tamaño del historial/contexto enviado. Detalle: {exc}"
                    ) from exc
        raise RuntimeError(f"Groq no pudo responder tras reintentos: {last_error}")

    def embed(self, text: str, **kwargs: Any) -> list[float]:
        raise NotImplementedError("Los embeddings no se manejan desde Groq")

    def stream(self, prompt: Any, **kwargs: Any) -> Any:
        return self.get_model().stream(prompt, **self._sanitize_kwargs(kwargs))

    def invoke(self, prompt: Any, **kwargs: Any) -> Any:
        return self.generate(prompt, **kwargs)

    def health(self) -> bool:
        try:
            self.get_model()
            return True
        except Exception as exc:
            logger.warning("Groq provider no disponible: %s", exc)
            return False