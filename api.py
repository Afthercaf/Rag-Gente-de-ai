# api.py - FastAPI backend para Pizzería 220 AI (VERSIÓN CORREGIDA)
# Ejecutar con: uvicorn api:app --reload --port 8000

import re
import threading
import time
import json
import asyncio
import hashlib
import sys
from typing import Optional, Dict, Any
from pathlib import Path
from contextlib import asynccontextmanager
from functools import wraps
from datetime import datetime

from fastapi import FastAPI, Response, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from requests import session

from src.file_processor import chunk_pdfs
from src.supabase_promos import load_promotions
from src.chroma_db import save_to_chroma_db
from src.telegram_sender import send_telegram_order
from src.telegram_bot import run_bot
from src.supabase_orders import create_order, update_order_status, get_order_status
from src.supabase_auth import register_user, login_user, get_user_by_gmail
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import OllamaEmbeddings, ChatOllama

load_dotenv()

# ==========================================
# CONSTANTES OPTIMIZADAS
# ==========================================
TOP_K = 5
EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "qwen2.5-coder:3b"
CACHE_TTL = 3600  # 1 hora de caché

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:4173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://localhost:8080",
]

# Detectar si estamos en Windows
IS_WINDOWS = sys.platform == "win32"

# ==========================================
# CACHE EN MEMORIA CORREGIDO
# ==========================================
class MemoryCache:
    def __init__(self, ttl_seconds: int = 3600):  # Cambiado de 'ttl' a 'ttl_seconds'
        self.cache = {}
        self.ttl = ttl_seconds
        self.lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            if key in self.cache:
                data, timestamp = self.cache[key]
                if time.time() - timestamp < self.ttl:
                    return data
                else:
                    del self.cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: int = None):
        with self.lock:
            ttl_value = ttl if ttl is not None else self.ttl
            self.cache[key] = (value, time.time())
    
    def clear(self):
        with self.lock:
            self.cache.clear()

# Inicializar caché - AHORA CON EL NOMBRE CORRECTO
response_cache = MemoryCache(ttl_seconds=CACHE_TTL)  # Cambiado de 'ttl' a 'ttl_seconds'

# Rate limiting
# Memoria de conversación por usuario
USER_SESSIONS: Dict[int, Dict[str, Any]] = {}

# ==========================================
# PROMPT TEMPLATE
# ==========================================
PROMPT_TEMPLATE = """
Eres el asistente oficial de Pizzería 220.

CAPACIDADES:
- Entender pedidos completos de pizza.
- Identificar cantidad, tamaño, ingredientes y extras.
- Conocer promociones y precios.
- Responder horarios y métodos de pago.
- Ubicación de la pizzería y zonas de reparto.

REGLAS:
- Responde SOLO usando el contexto proporcionado.
- NO inventes información.
- Si existen promociones en el contexto, enuméralas claramente con precios.
- Si no existe información responde exactamente: "No hay datos disponibles."
- Si el cliente está realizando un pedido, al FINAL de tu respuesta agrega EXACTAMENTE este formato:

PEDIDOS:

- Si el mensaje del cliente contiene el nombre de una pizza,
  promoción o producto existente en el CONTEXTO,
  considéralo una intención de compra.

- Ejemplos:
  "pepperoni"
  "quiero una mexicana"
  "una pastorera"
  "la promo 2"
  "dos campiranas"

- En esos casos agrega:

📝 PEDIDO:
Cantidad: [cantidad]
Producto: [producto]
Tamaño: [tamaño]
Extras: [extras o Ninguno]

- Si el cliente solamente pregunta información,
  NO agregues la sección 📝 PEDIDO.

IMPORTANTE:

- Utiliza únicamente productos encontrados en CONTEXTO.
- Nunca inventes pizzas.
- Nunca inventes promociones.
- Nunca inventes precios.

Responde siempre en español latino.

CONTEXTO:
{context}

HISTORIAL DE LA CONVERSACIÓN:
{history}

PREGUNTA DEL CLIENTE:
{question}

RESPUESTA:
"""

NOISE_WORDS = [
    "dime", "busca", "me", "puedes", "cuanto", "que", "una", "un",
    "la", "las", "el", "los", "de", "del", "para", "con",
]

# ==========================================
# DECORADORES
# ==========================================

def measure_time(func):
    """Mide el tiempo de ejecución de funciones"""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"⏱️ {func.__name__} tomó {elapsed:.2f}s")
        return result
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"⏱️ {func.__name__} tomó {elapsed:.2f}s")
        return result
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

# ==========================================
# ESTADO GLOBAL
# ==========================================
state: Dict[str, Any] = {
    "db": None,
    "promo_documents": [],
    "model": None,
    "model_loaded": False,
    "prompt_template": None,
    "ready": False,
    "loading_task": None,
    "embedding_model": None,
    "startup_time": time.time(),
}

class LazyModelLoader:
    """Carga el modelo LLM solo cuando se necesita"""
    def __init__(self):
        self._model = None
        self._lock = threading.Lock()
    
    @property
    def model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    print("🔄 Cargando modelo LLM bajo demanda...")
                    start = time.time()
                    try:
                        self._model = ChatOllama(
                            model=CHAT_MODEL,
                            temperature=0.2,
                            num_ctx=4096,
                            num_predict=512,
                            repeat_penalty=1.1,
                            top_k=40,
                            top_p=0.9,
                        )
                        print(f"✅ Modelo cargado en {time.time() - start:.2f}s")
                    except Exception as e:
                        print(f"❌ Error cargando modelo: {e}")
                        raise
        return self._model

state["model_loader"] = LazyModelLoader()

# ==========================================
# HELPERS
# ==========================================

def clean_query(text: str) -> str:
    """Limpia y normaliza la consulta del usuario"""
    text = text.lower()
    for w in NOISE_WORDS:
        text = re.sub(rf"\b{re.escape(w)}\b", " ", text)
    text = re.sub(r"[^a-zA-Z0-9áéíóúñ\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()

def get_cache_key(query: str) -> str:
    """Genera clave de caché para respuestas"""
    query_hash = hashlib.md5(query.encode()).hexdigest()
    return f"chat:{query_hash}"

def get_user_session(user_id: int):
    if user_id not in USER_SESSIONS:
        USER_SESSIONS[user_id] = {
            "history": []
        }

    return USER_SESSIONS[user_id]

async def load_resources_background():
    """Carga todos los recursos en segundo plano"""
    print("🔄 Iniciando carga de recursos en background...")
    start_time = time.time()
    
    try:
        # 1. Cargar promociones
        print("📢 Cargando promociones...")
        state["promo_documents"] = await asyncio.to_thread(load_promotions)
        print(f"✅ Promociones cargadas: {len(state['promo_documents'])}")
        
        # 2. Cargar embedding model
        print("🔤 Cargando modelo de embeddings...")
        state["embedding_model"] = await asyncio.to_thread(
            OllamaEmbeddings, 
            model=EMBED_MODEL
        )
        print("✅ Modelo de embeddings cargado")
        
        # 3. Procesar PDFs y crear Chroma DB
        print("📄 Procesando documentos...")
        pdf_documents = await asyncio.to_thread(chunk_pdfs)
        state["db"] = await asyncio.to_thread(
            save_to_chroma_db, 
            pdf_documents, 
            state["embedding_model"]
        )
        
        # 4. Preparar template
        state["prompt_template"] = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        
        # 5. NO cargar el modelo LLM aquí (lazy loading)
        state["ready"] = True
        elapsed = time.time() - start_time
        print(f"✅ API completamente cargada en {elapsed:.2f}s")
        
    except Exception as e:
        print(f"❌ Error cargando recursos: {e}")
        import traceback
        traceback.print_exc()
        state["ready"] = False

# ==========================================
# LIFESPAN
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Iniciando Pizzería 220 API...")
    
    # Marcar como no ready
    state["ready"] = False
    
    # Iniciar bot de Telegram en background
    def start_bot():
        try:
            run_bot()
        except Exception as e:
            print(f"⚠️ Telegram no disponible: {e}")
    
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    
    # Iniciar carga de recursos en background
    loading_task = asyncio.create_task(load_resources_background())
    state["loading_task"] = loading_task
    
    print("✅ API iniciada (recursos cargando en background)")
    print("📍 API disponible en: http://localhost:8000")
    print("📖 Documentación: http://localhost:8000/docs")
    
    yield
    
    print("👋 Cerrando API...")
    if state.get("loading_task"):
        state["loading_task"].cancel()

# ==========================================
# APP
# ==========================================

app = FastAPI(
    title="Pizzería 220 AI",
    version="2.0.0",
    lifespan=lifespan
)

# Middlewares
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,
)

# ==========================================
# SCHEMAS
# ==========================================
class ChatRequest(BaseModel):
    user_id: int
    message: str = Field(..., min_length=1, max_length=500)
    use_cache: bool = Field(default=True)

class OrderRequest(BaseModel):
    user_id: int
    pedido: str
    cliente_nombre: str
    telefono: str
    gmail: str
    direccion: str
    payment_method: str
    total: Optional[str] = None
    ubicacion: Optional[dict] = None

class StatusUpdateRequest(BaseModel):
    status: str

class RegisterRequest(BaseModel):
    nombre: str
    telefono: str
    gmail: str
    direccion: str
    role: str = "cliente"
    password: str

class LoginRequest(BaseModel):
    gmail: str
    password: str

class QuickReplyRequest(BaseModel):
    message: str

# ==========================================
# ENDPOINTS
# ==========================================

@app.get("/")
async def root():
    return {
        "name": "Pizzería 220 AI API",
        "version": "2.0.0",
        "status": "running",
        "ready": state["ready"],
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    uptime = time.time() - state["startup_time"]
    return {
        "status": "ok",
        "ready": state["ready"],
        "model_loaded": state["model_loaded"],
        "uptime_seconds": round(uptime, 2)
    }

@app.get("/ready")
async def readiness():
    return {
        "ready": state["ready"],
        "cache_size": len(response_cache.cache),
        "model_loaded": state["model_loaded"]
    }

@app.post("/chat")
@measure_time
async def chat(req: ChatRequest):
    """Chat con memoria por usuario + RAG contextual"""

    if not state["ready"]:
        return JSONResponse(
            content={
                "reply": "⏳ Sistema inicializando... Por favor espera unos segundos.",
                "is_order": False
            }
        )

    query = req.message.strip()

    if not query:
        return JSONResponse(content={"reply": ""})

    user_id = req.user_id

    # =========================
    # SESIÓN DEL USUARIO
    # =========================

    session = get_user_session(user_id)

    print(f"👤 Usuario: {user_id}")
    print(f"🧠 Historial: {len(session['history'])} mensajes")

    # =========================
    # CACHE POR USUARIO
    # =========================

    if req.use_cache:
        cache_key = get_cache_key(
            f"{user_id}:{query}"
        )

        cached = response_cache.get(cache_key)

        if cached:
            print("📦 Respuesta desde caché")
            return JSONResponse(content=cached)

    try:

        # =========================
        # HISTORIAL PARA EL MODELO
        # =========================

        history_text = "\n".join(
            [
                f"Cliente: {msg['user']}\nAsistente: {msg['assistant']}"
                for msg in session["history"][-10:]
            ]
        )

        # =========================
        # QUERY ENRIQUECIDA PARA RAG
        # =========================

        search_query = query

        if session["history"]:
            ultimos_mensajes = " ".join(
                [
                    item["user"]
                    for item in session["history"][-3:]
                ]
            )

            search_query = (
                f"{ultimos_mensajes} {query}"
            )

        print(f"🔍 Búsqueda RAG: {search_query}")

        # =========================
        # BÚSQUEDA EN CHROMA
        # =========================

        docs = await asyncio.to_thread(
            state["db"].similarity_search,
            search_query,
            k=TOP_K
        )

        rag_context = "\n".join(
            doc.page_content
            for doc in docs
        )

        # =========================
        # PROMOCIONES PDF
        # =========================

        promos_text = "\n".join(
            p.page_content
            for p in state["promo_documents"]
        )

        # =========================
        # CONTEXTO COMPLETO
        # =========================

        full_context = f"""
DOCUMENTOS:
{rag_context}

PROMOCIONES:
{promos_text}
"""

        # =========================
        # PROMPT
        # =========================

        prompt = state["prompt_template"].format_messages(
            context=full_context,
            history=history_text,
            question=query
        )

        # =========================
        # MODELO
        # =========================

        model = state["model_loader"].model

        state["model_loaded"] = True

        response = await asyncio.to_thread(
            model.invoke,
            prompt
        )

        content = response.content.strip()

        # =========================
        # GUARDAR MEMORIA
        # =========================

        session["history"].append(
            {
                "user": query,
                "assistant": content
            }
        )

        # Mantener últimos 20 mensajes
        session["history"] = session["history"][-20:]

        # =========================
        # DETECTAR PEDIDO
        # =========================

        is_order = "📝 PEDIDO:" in content

        order_details = None

        if is_order:
            match = re.search(
                r"📝 PEDIDO:\s*(.*)",
                content,
                re.DOTALL
            )

            if match:
                order_details = match.group(1).strip()

                # eliminar promociones si el modelo las agregó
                order_details = order_details.split(
                    "PROMOCIONES:",
                    1
                )[0]

                # eliminar bloques repetidos
                order_details = order_details.split(
                    "PEDIDOS:",
                    1
                )[0]

                order_details = order_details.strip()

        result = {
            "reply": content,
            "is_order": is_order,
            "order_details": order_details,
            "user_id": user_id
        }

        # =========================
        # CACHE
        # =========================

        if req.use_cache:
            response_cache.set(
                cache_key,
                result
            )

        return JSONResponse(
            content=result
        )

    except Exception as e:

        print(f"❌ Error en /chat: {e}")

        import traceback
        traceback.print_exc()

        return JSONResponse(
            status_code=500,
            content={
                "reply": "❌ Error interno del servidor. Por favor intenta nuevamente.",
                "is_order": False
            }
        )

@app.post("/chat/quick")
async def quick_reply(req: QuickReplyRequest):
    """Respuestas rápidas predefinidas"""
    query = req.message.lower().strip()

    # Detectar consultas relacionadas con el menú
    menu_keywords = [
        "menu",
        "menú",
        "que pizzas tienen",
        "qué pizzas tienen",
        "pizzas",
        "carta",
        "que venden",
        "qué venden",
        "productos"
    ]

    if any(keyword in query for keyword in menu_keywords):
        return {
            "reply": "🍕 Claro, aquí tienes nuestro menú. ¿Qué pizza te gustaría ordenar?",
            "is_order": False,
            "quick": True
        }

    quick_responses = {
        "horario": "🕒 Nuestro horario es de Lunes a Domingo de 6 PM a 12 AM.",
        "telefono": "📞 Puedes contactarnos al: 555-123-4567",
        "direccion": "📍 Estamos en: Calle Principal #220, Centro",
        "ubicación": "📍 Estamos en: Calle Principal #220, Centro",
        "pago": "💳 Aceptamos: Efectivo, Tarjeta y Transferencia",
    }

    for key, response in quick_responses.items():
        if key in query:
            return {"reply": response, "is_order": False, "quick": True}

    # Si no hay respuesta rápida, usar chat normal
    return await chat(ChatRequest(message=req.message))

# ── Auth Endpoints ─────────────────────────────────────────────

@app.post("/auth/register")
async def register(req: RegisterRequest):
    gmail = req.gmail.strip().lower()
    
    existing_user = await asyncio.to_thread(get_user_by_gmail, gmail)
    if existing_user:
        return {"success": False, "message": "El correo ya está registrado"}
    
    user = await asyncio.to_thread(
        register_user,
        nombre=req.nombre,
        telefono=req.telefono,
        gmail=gmail,
        direccion=req.direccion,
        role=req.role,
        password_hash=req.password,
    )
    
    if not user:
        return {"success": False, "message": "Error al crear el usuario"}
    
    return {"success": True, "user": user}

@app.post("/auth/login")
async def login(req: LoginRequest, response: Response):
    gmail = req.gmail.strip().lower()
    
    user = await asyncio.to_thread(login_user, gmail=gmail, password_hash=req.password)
    
    if not user:
        return {"success": False, "message": "Correo o contraseña incorrectos"}
    
    response.set_cookie(
        key="session",
        value=str(user["id"]),
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    
    return {
        "success": True,
        "user": {
            "id": user.get("id"),
            "nombre": user.get("nombre"),
            "gmail": user.get("gmail"),
            "telefono": user.get("telefono"),
            "direccion": user.get("direccion"),
            "role": user.get("role")
        }
    }

@app.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie(key="session")
    return {"success": True}

# ── Order Endpoints ───────────────────────────────────────────

@app.post("/order")
@measure_time
async def create_new_order(req: OrderRequest, background_tasks: BackgroundTasks):
    if not state["ready"]:
        return {"success": False, "message": "Sistema no listo"}
    
    ubicacion_json = json.dumps(req.ubicacion) if req.ubicacion else None
    
    payload = {
        "user_id": req.user_id,
        "cliente_nombre": req.cliente_nombre,
        "telefono": req.telefono,
        "gmail": req.gmail,
        "direccion": req.direccion,
        "pedido": req.pedido,
        "total": req.total or "pendiente",
        "payment_method": req.payment_method,
        "estado": "pendiente",
        "ubicacion_maps": ubicacion_json,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    order_id = await asyncio.to_thread(create_order, payload)
    
    if not order_id:
        return {"success": False, "message": "Error al crear el pedido"}
    
    background_tasks.add_task(
        send_telegram_order,
        order_id=order_id,
        cliente_nombre=req.cliente_nombre,
        telefono=req.telefono,
        gmail=req.gmail,
        direccion=req.direccion,
        pedido=req.pedido,
        payment_method=req.payment_method,
        total=req.total,
        ubicacion=req.ubicacion,
    )
    
    return {"success": True, "order_id": order_id, "total": req.total or "pendiente"}

@app.patch("/order/{order_id}/status")
async def patch_order_status(order_id: str, req: StatusUpdateRequest):

    print(
        f"🔄 Actualizando pedido {order_id} -> {req.status}"
    )

    success = await asyncio.to_thread(
        update_order_status,
        order_id,
        req.status
    )

    print(
        f"📦 Resultado Supabase: {success}"
    )

    return {
        "success": success,
        "order_id": order_id,
        "status": req.status
    }

@app.get("/order/{order_id}/status")
async def fetch_order_status(order_id: str):

    status = await asyncio.to_thread(
        get_order_status,
        order_id
    )

    return {
        "order_id": order_id,
        "status": status
    }
# ── Utilidades ─────────────────────────────────────────────────

@app.get("/cache/stats")
async def cache_stats():
    return {
        "cache_size": len(response_cache.cache),
        "model_loaded": state["model_loaded"],
        "api_ready": state["ready"]
    }

@app.post("/cache/clear")
async def clear_cache():
    response_cache.clear()
    return {"success": True, "message": "Caché limpiada"}

# ==========================================
# MANEJADOR DE ERRORES
# ==========================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"❌ Error no manejado: {exc}")
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"error": "Error interno del servidor"}
    )

# ==========================================
# PUNTO DE ENTRADA
# ==========================================

if __name__ == "__main__":
    import uvicorn
    
    print("🍕 Pizzería 220 AI API - Versión Optimizada")
    print("=" * 50)
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )