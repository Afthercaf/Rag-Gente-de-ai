# routers/voice.py
# Endpoint de transcripción de audio con faster-whisper
# Instalar: pip install faster-whisper
# Requiere: ffmpeg instalado en el sistema (winget install ffmpeg)

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
import tempfile
import os
import json
import subprocess
import logging
import re
from datetime import datetime
from typing import Optional
import uuid

from core.security import CurrentUser, get_current_user, require_roles
from core.transcription_store import (
    decrypt_transcription,
    encrypt_transcription,
)

router = APIRouter(prefix="/voice", tags=["voice"])
logger = logging.getLogger(__name__)
ALLOWED_LANGUAGES = {"es", "es-MX", "en", "en-US"}

# ── Configuración ────────────────────────────────────────────────
TRANSCRIPTIONS_FILE = "transcriptions.json"
MAX_HISTORY = 100  # Máximo de transcripciones a guardar

# ── Carga del modelo (una sola vez al arrancar) ────────────────
# Modelos disponibles por velocidad/precisión:
#   "tiny"  → más rápido, menos preciso  (~75MB)
#   "base"  → buen balance              (~150MB)  ← recomendado
#   "small" → más preciso, más lento    (~500MB)
_model = None

def get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        logger.info("Cargando modelo de transcripción")
        _model = WhisperModel("base", device="cpu", compute_type="int8")
        logger.info("Modelo de transcripción listo")
    return _model


# ── Funciones para manejar transcripciones ──────────────────────
def _load_raw_entries() -> list[dict]:
    """Carga las entradas crudas (posiblemente cifradas) del archivo JSON."""
    if os.path.exists(TRANSCRIPTIONS_FILE):
        try:
            with open(TRANSCRIPTIONS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except (json.JSONDecodeError, IOError):
            return []
    return []


def load_transcriptions() -> list[dict]:
    """Carga y descifra el historial de transcripciones."""
    raw_entries = _load_raw_entries()
    transcriptions: list[dict] = []
    for entry in raw_entries:
        encrypted = entry.get("encrypted")
        if not encrypted:
            # Compatibilidad: entrada en texto plano antigua (no debería existir).
            continue
        decrypted = decrypt_transcription(encrypted)
        if decrypted is not None:
            transcriptions.append(decrypted)
    return transcriptions


def save_transcription(text: str, language: str, user_id: str):
    """Cifra y guarda una transcripción en el archivo JSON."""
    transcriptions = _load_raw_entries()

    entry = {
        "id": str(uuid.uuid4()),
        "text": text,
        "language": language,
        "user_id": user_id,
        "timestamp": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    encrypted_entry = {"encrypted": encrypt_transcription(entry)}

    # Agregar al inicio (más reciente primero)
    transcriptions.insert(0, encrypted_entry)

    # Limitar historial
    if len(transcriptions) > MAX_HISTORY:
        transcriptions = transcriptions[:MAX_HISTORY]

    # Guardar archivo
    try:
        with open(TRANSCRIPTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(transcriptions, f, ensure_ascii=False, indent=2)
        logger.info("Transcripción cifrada guardada")
        return True
    except Exception as e:
        logger.exception("No fue posible guardar la transcripción cifrada")
        return False


def get_transcriptions(limit: int = 10) -> list[dict]:
    """Obtiene las últimas transcripciones descifradas."""
    transcriptions = load_transcriptions()
    return transcriptions[:limit]


# ── Endpoint de transcripción ────────────────────────────────────
@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = Form(default="es"),
    current_user: CurrentUser = Depends(get_current_user),
):
    audio_bytes = await audio.read()
    if language not in ALLOWED_LANGUAGES:
        raise HTTPException(status_code=422, detail="Idioma no válido")
    filename = os.path.basename(audio.filename or "")
    if not filename or len(filename) > 255:
        raise HTTPException(status_code=422, detail="Nombre de archivo no válido")

    logger.info("Audio recibido: tipo=%s bytes=%d idioma=%s",
                audio.content_type, len(audio_bytes), language)

    allowed_audio_types = {
        "audio/webm",
        "audio/webm;codecs=opus",
        "audio/ogg",
        "audio/ogg;codecs=opus",
        "audio/wav",
        "audio/mpeg",
        "audio/mp4",
        "audio/m4a",
        "audio/x-m4a",
    }
    normalized_content_type = (audio.content_type or "").lower()

    if normalized_content_type not in allowed_audio_types:
        raise HTTPException(
            status_code=415,
            detail="Tipo de audio no permitido",
        )

    if len(audio_bytes) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="El audio supera 10 MB",
        )

    if len(audio_bytes) < 100:
        return JSONResponse(
            content={"text": "", "success": False, "error": "Audio vacío o muy corto"},
            status_code=400,
        )

    # Determinar extensión según content_type
    ext_map = {
        "audio/webm": ".webm",
        "audio/webm;codecs=opus": ".webm",
        "audio/ogg": ".ogg",
        "audio/ogg;codecs=opus": ".ogg",
        "audio/wav": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".mp4",
        "audio/m4a": ".m4a",
    }
    content_type = (audio.content_type or "").lower()
    suffix = ext_map.get(content_type, ".webm")

    tmp_path = None
    wav_path = None
    text = ""
    success = False
    error = None
    
    try:
        # Guardar audio recibido en archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        # Convertir a WAV 16kHz mono con ffmpeg para garantizar compatibilidad
        wav_path = tmp_path.replace(suffix, ".wav")
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                tmp_path,
                "-ar",
                "16000",
                "-ac",
                "1",
                wav_path,
                "-loglevel",
                "error",
            ],
            capture_output=True,
            text=True,
        )
        ret = result.returncode
        if ret != 0:
            logger.warning("ffmpeg rechazó el audio; código=%d", ret)

        # Usar WAV si la conversión fue exitosa, si no intentar con el original
        input_path = wav_path if (ret == 0 and os.path.exists(wav_path)) else tmp_path

        # Transcribir
        model = get_model()
        segments, info = model.transcribe(
            input_path,
            language=language[:2],  # "es-ES" → "es"
            beam_size=5,
            vad_filter=False,       # desactivado para mayor tolerancia
        )

        text = " ".join(seg.text.strip() for seg in segments).strip()
        # VULN-16/17/18: no registrar el contenido de la transcripción.
        logger.info("Transcripción completada; idioma=%s", info.language)

        if not text:
            error = "No se detectó voz"
            success = False
        else:
            success = True
            # Guardar la transcripción
            save_transcription(
                text=text,
                language=language,
                user_id=str(current_user.public_id)
            )

        return JSONResponse(content={
            "text": text,
            "success": success,
            "error": error,
            "language_detected": info.language if success else None
        })

    except Exception as e:
        logger.exception("Error interno transcribiendo audio")
        raise HTTPException(
            status_code=500,
            detail="No fue posible transcribir el audio",
        ) from e

    finally:
        # Limpiar archivos temporales
        for p in [tmp_path, wav_path]:
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception as e:
                    logger.warning("No fue posible eliminar un archivo temporal")


# ── Endpoints para gestionar transcripciones guardadas ──────────
@router.get("/history")
async def get_transcription_history(
    limit: int = 10,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Obtiene el historial de transcripciones"""
    try:
        transcriptions = load_transcriptions()
        
        limit = max(1, min(limit, 50))
        transcriptions = [
            t for t in transcriptions
            if t.get("user_id") == str(current_user.public_id)
        ]
        
        return JSONResponse(content={
            "success": True,
            "count": len(transcriptions[:limit]),
            "transcriptions": transcriptions[:limit]
        })
    except Exception as e:
        logger.exception("Error obteniendo historial de transcripciones")
        return JSONResponse(
            content={"success": False, "error": "No fue posible procesar el audio."},
            status_code=500
        )

@router.delete("/history/{transcription_id}")
async def delete_transcription(
    transcription_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Elimina una transcripción específica"""
    try:
        raw_entries = _load_raw_entries()
        kept: list[dict] = []
        found = False

        for entry in raw_entries:
            encrypted = entry.get("encrypted")
            if not encrypted:
                continue
            decrypted = decrypt_transcription(encrypted)
            if decrypted is None:
                continue
            if (
                decrypted.get("id") == transcription_id
                and decrypted.get("user_id") == str(current_user.public_id)
            ):
                found = True
                continue
            kept.append(entry)

        if not found:
            return JSONResponse(
                content={"success": False, "error": "Transcripción no encontrada"},
                status_code=404
            )

        with open(TRANSCRIPTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(kept, f, ensure_ascii=False, indent=2)

        return JSONResponse(content={
            "success": True,
            "message": f"Transcripción #{transcription_id} eliminada"
        })
    except Exception as e:
        logger.exception("Error eliminando transcripción")
        return JSONResponse(
            content={"success": False, "error": "No fue posible procesar el audio."},
            status_code=500
        )

@router.delete("/history")
async def clear_transcription_history(
    current_user: CurrentUser = Depends(get_current_user),
):
    """Elimina todo el historial de transcripciones"""
    try:
        raw_entries = _load_raw_entries()
        remaining: list[dict] = []

        for entry in raw_entries:
            encrypted = entry.get("encrypted")
            if not encrypted:
                continue
            decrypted = decrypt_transcription(encrypted)
            if decrypted is None:
                continue
            if decrypted.get("user_id") != str(current_user.public_id):
                remaining.append(entry)

        with open(TRANSCRIPTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(remaining, f, ensure_ascii=False, indent=2)
        return JSONResponse(content={
            "success": True,
            "message": "Historial eliminado completamente"
        })
    except Exception as e:
        logger.exception("Error limpiando historial de transcripciones")
        return JSONResponse(
            content={"success": False, "error": "No fue posible consultar la transcripción."},
            status_code=500
        )


# ── Endpoint de estadísticas ─────────────────────────────────────
@router.get("/stats")
async def get_transcription_stats(
    current_user: CurrentUser = Depends(require_roles("admin")),
):
    """Obtiene estadísticas de las transcripciones"""
    try:
        transcriptions = load_transcriptions()
        
        if not transcriptions:
            return JSONResponse(content={
                "success": True,
                "total": 0,
                "languages": {},
                "last_24h": 0,
                "average_length": 0
            })
        
        # Calcular estadísticas
        total = len(transcriptions)
        
        # Idiomas
        languages = {}
        for t in transcriptions:
            lang = t.get('language', 'unknown')
            languages[lang] = languages.get(lang, 0) + 1
        
        # Últimas 24 horas
        last_24h = 0
        now = datetime.now()
        for t in transcriptions:
            try:
                timestamp = datetime.fromisoformat(t.get('timestamp', ''))
                if (now - timestamp).total_seconds() < 86400:  # 24 horas
                    last_24h += 1
            except (ValueError, TypeError):
                pass
        
        # Longitud promedio
        total_length = sum(len(t.get('text', '')) for t in transcriptions)
        avg_length = total_length / total if total > 0 else 0
        
        return JSONResponse(content={
            "success": True,
            "total": total,
            "languages": languages,
            "last_24h": last_24h,
            "average_length": round(avg_length, 1)
        })
    except Exception as e:
        logger.exception("Error calculando estadísticas de transcripción")
        return JSONResponse(
            content={"success": False, "error": "No fue posible eliminar la transcripción."},
            status_code=500
        )
