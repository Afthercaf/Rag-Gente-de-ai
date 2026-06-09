"""Service for persisting conversation history to JSON files."""
import json
import os
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime

# Data directory for storing user histories
DATA_DIR = Path("data/histories")
DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_history_file(user_id: int) -> Path:
    """Get the JSON file path for a user's history."""
    return DATA_DIR / f"user_{user_id}.json"


def load_history(user_id: int) -> List[Dict[str, str]]:
    """Load conversation history from disk for a user."""
    file_path = get_history_file(user_id)
    if not file_path.exists():
        return []
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("messages", [])
    except Exception as e:
        print(f"❌ Error al cargar historial para user {user_id}: {e}")
        return []


def save_history(user_id: int, history: List[Dict[str, str]]) -> None:
    """Save conversation history to disk for a user."""
    file_path = get_history_file(user_id)
    
    try:
        data = {
            "user_id": user_id,
            "messages": history,
            "last_updated": datetime.now().isoformat(),
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Error al guardar historial para user {user_id}: {e}")


def append_message(user_id: int, user_msg: str, assistant_msg: str, limit: int = 20) -> None:
    """Append a user-assistant exchange to history and save."""
    history = load_history(user_id)
    history.append({
        "user": user_msg,
        "assistant": assistant_msg,
        "timestamp": datetime.now().isoformat(),
    })
    
    # Keep only last N messages
    history = history[-limit:]
    save_history(user_id, history)


def clear_history(user_id: int) -> None:
    """Clear a user's conversation history."""
    file_path = get_history_file(user_id)
    if file_path.exists():
        file_path.unlink()
        print(f"✅ Historial del usuario {user_id} eliminado")


def get_all_user_ids() -> List[int]:
    """Get list of all user IDs with saved history."""
    user_ids = []
    for file in DATA_DIR.glob("user_*.json"):
        try:
            user_id = int(file.stem.split("_")[1])
            user_ids.append(user_id)
        except (ValueError, IndexError):
            pass
    return sorted(user_ids)
