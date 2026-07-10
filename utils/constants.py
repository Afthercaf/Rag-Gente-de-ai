import os
import sys

from dotenv import load_dotenv

from config.models import CHAT_MODEL as REMOTE_CHAT_MODEL, EMBED_MODEL as REMOTE_EMBED_MODEL
from config.models_local import CHAT_MODEL_LOCAL, EMBED_MODEL_LOCAL

load_dotenv()

TOP_K = 5

USE_LOCAL_ENV = os.getenv("USE_LOCAL")
USE_GROQ = os.getenv("USE_GROQ", "False").lower() in {"1", "true", "yes", "on"}
USE_LOCAL = (
    USE_LOCAL_ENV.lower() in {"1", "true", "yes", "on"}
    if USE_LOCAL_ENV is not None
    else not USE_GROQ
)

CHAT_MODEL = CHAT_MODEL_LOCAL if USE_LOCAL else REMOTE_CHAT_MODEL
EMBED_MODEL = EMBED_MODEL_LOCAL if USE_LOCAL else REMOTE_EMBED_MODEL
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://killerexpert10.tail29c8ce.ts.net:11434")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
USE_HUGGINGFACE_EMBEDDINGS = os.getenv("USE_HUGGINGFACE_EMBEDDINGS", "False").lower() in {"1", "true", "yes", "on"}
HF_EMBEDDING_MODEL = os.getenv("HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
CACHE_TTL = 3600  # 1 hora

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:4173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:8000",
    "https://localhost:5173",
    "https://localhost:5173"
]

IS_WINDOWS = sys.platform == "win32"

NOISE_WORDS = [
    "dime", "busca", "me", "puedes", "cuanto", "que", "una", "un",
    "la", "las", "el", "los", "de", "del", "para", "con",
]
