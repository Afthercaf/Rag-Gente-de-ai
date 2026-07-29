import asyncio
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.state import state
from services.resource_loader import load_resources_background
from src.telegram_bot import run_bot

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando Pizzería 220 API.")
    state["ready"] = False

    # Telegram bot en hilo daemon
    bot_thread = threading.Thread(
        target=_start_bot,
        daemon=True,
    )
    bot_thread.start()

    # Carga de recursos en background
    loading_task = asyncio.create_task(load_resources_background())
    state["loading_task"] = loading_task

    logger.info("API iniciada; recursos cargando en background.")

    yield

    logger.info("Cerrando API.")
    if state.get("loading_task"):
        state["loading_task"].cancel()


def _start_bot() -> None:
    try:
        asyncio.run(run_bot())
    except Exception:
        logger.exception("Telegram no disponible.")
