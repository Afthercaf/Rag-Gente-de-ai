import asyncio
import time
from functools import wraps


def measure_time(func):
    """Mide el tiempo de ejecución de funciones síncronas y asíncronas."""

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        print(f"⏱️ {func.__name__} tomó {time.perf_counter() - start:.2f}s")
        return result

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        print(f"⏱️ {func.__name__} tomó {time.perf_counter() - start:.2f}s")
        return result

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
