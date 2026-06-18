# routers/voice.py
# Endpoint de transcripción de audio con faster-whisper
# Instalar: pip install faster-whisper
# Requiere: ffmpeg instalado en el sistema (winget install ffmpeg)

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import tempfile
import os
import json
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/voice", tags=["voice"])

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
        print("🔊 Cargando modelo Whisper 'base'...")
        _model = WhisperModel("base", device="cpu", compute_type="int8")
        print("✅ Modelo Whisper listo")
    return _model


# ── Funciones para manejar transcripciones ──────────────────────
def load_transcriptions() -> list:
    """Carga el historial de transcripciones desde el archivo JSON"""
    if os.path.exists(TRANSCRIPTIONS_FILE):
        try:
            with open(TRANSCRIPTIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []

def save_transcription(text: str, language: str, user_id: Optional[str] = None):
    """Guarda una transcripción en el archivo JSON"""
    transcriptions = load_transcriptions()
    
    # Crear entrada
    entry = {
        "id": len(transcriptions) + 1,
        "text": text,
        "language": language,
        "user_id": user_id,
        "timestamp": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Agregar al inicio (más reciente primero)
    transcriptions.insert(0, entry)
    
    # Limitar historial
    if len(transcriptions) > MAX_HISTORY:
        transcriptions = transcriptions[:MAX_HISTORY]
    
    # Guardar archivo
    try:
        with open(TRANSCRIPTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(transcriptions, f, ensure_ascii=False, indent=2)
        print(f"💾 Transcripción guardada: '{text[:50]}...'")
        return True
    except Exception as e:
        print(f"❌ Error al guardar transcripción: {e}")
        return False

def get_transcriptions(limit: int = 10) -> list:
    """Obtiene las últimas transcripciones guardadas"""
    transcriptions = load_transcriptions()
    return transcriptions[:limit]


# ── Endpoint de transcripción ────────────────────────────────────
@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = Form(default="es"),
    user_id: Optional[str] = Form(default=None),
):
    audio_bytes = await audio.read()

    print(f"📦 content_type: {audio.content_type}")
    print(f"📦 filename: {audio.filename}")
    print(f"📦 tamaño: {len(audio_bytes)} bytes")
    print(f"📦 language: {language}")
    print(f"📦 user_id: {user_id}")

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
        print(f"💾 Audio temporal: {tmp_path}")

        # Convertir a WAV 16kHz mono con ffmpeg para garantizar compatibilidad
        wav_path = tmp_path.replace(suffix, ".wav")
        ret = os.system(
            f'ffmpeg -y -i "{tmp_path}" -ar 16000 -ac 1 "{wav_path}" -loglevel error'
        )
        print(f"🔄 Conversión ffmpeg: código {ret}, wav existe: {os.path.exists(wav_path)}")

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
        print(f"🎤 Transcripción: '{text}' (idioma detectado: {info.language})")

        if not text:
            error = "No se detectó voz"
            success = False
        else:
            success = True
            # Guardar la transcripción
            save_transcription(
                text=text,
                language=language,
                user_id=user_id
            )

        return JSONResponse(content={
            "text": text,
            "success": success,
            "error": error,
            "language_detected": info.language if success else None
        })

    except Exception as e:
        print(f"❌ Error en transcripción: {e}")
        error_msg = f"Error al transcribir: {str(e)}"
        raise HTTPException(status_code=500, detail=error_msg)

    finally:
        # Limpiar archivos temporales
        for p in [tmp_path, wav_path]:
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception as e:
                    print(f"⚠️ Error al eliminar archivo temporal {p}: {e}")


# ── Endpoints para gestionar transcripciones guardadas ──────────
@router.get("/history")
async def get_transcription_history(limit: int = 10, user_id: Optional[str] = None):
    """Obtiene el historial de transcripciones"""
    try:
        transcriptions = load_transcriptions()
        
        # Filtrar por user_id si se proporciona
        if user_id:
            transcriptions = [t for t in transcriptions if t.get('user_id') == user_id]
        
        return JSONResponse(content={
            "success": True,
            "count": len(transcriptions[:limit]),
            "transcriptions": transcriptions[:limit]
        })
    except Exception as e:
        print(f"❌ Error al obtener historial: {e}")
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500
        )

@router.delete("/history/{transcription_id}")
async def delete_transcription(transcription_id: int):
    """Elimina una transcripción específica"""
    try:
        transcriptions = load_transcriptions()
        original_count = len(transcriptions)
        
        # Filtrar por id
        transcriptions = [t for t in transcriptions if t.get('id') != transcription_id]
        
        if len(transcriptions) == original_count:
            return JSONResponse(
                content={"success": False, "error": "Transcripción no encontrada"},
                status_code=404
            )
        
        # Guardar cambios
        with open(TRANSCRIPTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(transcriptions, f, ensure_ascii=False, indent=2)
        
        return JSONResponse(content={
            "success": True,
            "message": f"Transcripción #{transcription_id} eliminada"
        })
    except Exception as e:
        print(f"❌ Error al eliminar transcripción: {e}")
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500
        )

@router.delete("/history")
async def clear_transcription_history():
    """Elimina todo el historial de transcripciones"""
    try:
        if os.path.exists(TRANSCRIPTIONS_FILE):
            os.remove(TRANSCRIPTIONS_FILE)
            print("🗑️ Historial de transcripciones eliminado")
        return JSONResponse(content={
            "success": True,
            "message": "Historial eliminado completamente"
        })
    except Exception as e:
        print(f"❌ Error al limpiar historial: {e}")
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500
        )


# ── Endpoint de estadísticas ─────────────────────────────────────
@router.get("/stats")
async def get_transcription_stats():
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
        print(f"❌ Error al obtener estadísticas: {e}")
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500
        )