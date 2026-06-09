import re
from utils.constants import NOISE_WORDS


def clean_query(text: str) -> str:
    """Limpia y normaliza la consulta del usuario."""
    text = text.lower()
    for w in NOISE_WORDS:
        text = re.sub(rf"\b{re.escape(w)}\b", " ", text)
    text = re.sub(r"[^a-zA-Z0-9áéíóúñ\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()
