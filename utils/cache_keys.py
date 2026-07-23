import hashlib


def get_cache_key(query: str, user_id: int = 0) -> str:
    """Genera una clave de caché a partir de la query y el user_id.
    
    Incluye el user_id para evitar que dos usuarios distintos reciban
    respuestas cacheadas de otro (multi-user isolation).
    """
    query_hash = hashlib.md5(query.encode()).hexdigest()
    return f"chat:{user_id}:{query_hash}"
