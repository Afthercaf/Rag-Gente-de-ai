import asyncio
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.state import state
from services.resource_loader import load_resources_background
from src.telegram_bot import run_bot


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Iniciando Pizzería 220 API...")
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

    print("✅ API iniciada (recursos cargando en background)")
    print("📍 API disponible en: http://localhost:8000")
    print("📖 Documentación: http://localhost:8000/docs")

    yield

    print("👋 Cerrando API...")
    if state.get("loading_task"):
        state["loading_task"].cancel()


def _start_bot() -> None:
    try:
        run_bot()
    except Exception as e:
        print(f"⚠️ Telegram no disponible: {e}")
