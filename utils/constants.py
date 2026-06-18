import sys

TOP_K = 5
EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "qwen2.5-coder:3b"
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
