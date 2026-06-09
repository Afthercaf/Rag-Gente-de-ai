import hashlib


def get_cache_key(query: str) -> str:
    """Genera una clave de caché a partir de la query."""
    query_hash = hashlib.md5(query.encode()).hexdigest()
    return f"chat:{query_hash}"
