import os
import logging
from decimal import Decimal, InvalidOperation
import requests
import time
from core.config import require_env, supabase_server_key
from langchain_core.documents import Document

SUPABASE_URL = require_env("SUPABASE_URL")
SUPABASE_KEY = supabase_server_key()
logger = logging.getLogger(__name__)


def _safe_text(value: object, *, max_length: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > max_length:
        raise ValueError("Campo de promoción demasiado largo.")
    lowered = text.lower()
    forbidden = (
        "ignore previous",
        "ignora las instrucciones",
        "system prompt",
        "developer message",
        "actúa como",
        "jailbreak",
    )
    if any(marker in lowered for marker in forbidden):
        raise ValueError("Contenido de promoción no confiable.")
    return text

def load_promotions() -> list[Document]:
    """Carga promociones con timeout alto y reintentos"""
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase no configurado.")
        return []
    
    url = f"{SUPABASE_URL}/rest/v1/promociones?activa=eq.true"
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info("Cargando promociones; intento=%s", attempt + 1)
            
            # Timeout de 30 segundos para conexión lenta
            response = requests.get(
                url,
                headers=headers,
                timeout=(10, 30)  # (connect timeout, read timeout)
            )
            
            if response.status_code == 200:
                data = response.json()
                docs = []
                
                for promo in data:
                    try:
                        nombre = _safe_text(promo.get("nombre"), max_length=120)
                        descripcion = _safe_text(
                            promo.get("descripcion"), max_length=500
                        )
                        ingredientes = _safe_text(
                            promo.get("ingredientes"), max_length=500
                        )
                        refresco = _safe_text(
                            promo.get("refresco"), max_length=120
                        )
                        precio = Decimal(str(promo.get("precio")))
                        if not Decimal("0") < precio <= Decimal("100000"):
                            raise ValueError("Precio fuera de rango.")
                    except (InvalidOperation, TypeError, ValueError):
                        logger.warning("Promoción inválida omitida.")
                        continue
                    content = f"""
PROMOCION:
{nombre}

DESCRIPCION:
{descripcion}

INGREDIENTES:
{ingredientes}

REFRESCO:
{refresco}

PRECIO:
{precio}
"""
                    docs.append(
                        Document(
                            page_content=content,
                            metadata={
                                "source": "supabase",
                                "promo_id": promo["id"]
                            }
                        )
                    )
                
                logger.info("Promociones válidas cargadas: %s", len(docs))
                return docs
                
            else:
                logger.warning("Supabase promociones respondió status=%s", response.status_code)
                
        except requests.exceptions.Timeout:
            logger.warning("Timeout cargando promociones; intento=%s", attempt + 1)
            if attempt < max_retries - 1:
                time.sleep(3)
                
        except Exception:
            logger.exception("Error cargando promociones.")
            if attempt < max_retries - 1:
                time.sleep(3)
    
    logger.warning("Usando lista vacía de promociones.")
    return []
