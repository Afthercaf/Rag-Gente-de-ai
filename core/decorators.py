import asyncio
import logging
import time
from functools import wraps


def measure_time(func):
    """Mide el tiempo de ejecución de funciones síncronas y asíncronas."""

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        logger.info("%s tomó %.2fs", func.__name__, time.perf_counter() - start)
        return result

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        logger.info("%s tomó %.2fs", func.__name__, time.perf_counter() - start)
        return result

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
logger = logging.getLogger(__name__)
