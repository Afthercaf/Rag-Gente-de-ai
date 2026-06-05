# api.py - FastAPI backend para Pizzería 220 AI
# Ejecutar con: uvicorn api:app --reload --port 8000

import re
import threading
import time
import json
from typing import Optional
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager

from src.file_processor import chunk_pdfs
from src.supabase_promos import load_promotions
from src.chroma_db import save_to_chroma_db
from src.telegram_sender import send_telegram_order
from src.telegram_bot import run_bot
from src.supabase_orders import create_order, update_order_status, get_order_status
from src.supabase_auth import register_user, login_user, get_user_by_gmail
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import OllamaEmbeddings, ChatOllama

# ==========================================
# CONSTANTES
# ==========================================
TOP_K        = 10
EMBED_MODEL  = "nomic-embed-text"
CHAT_MODEL   = "qwen2.5-coder:3b"

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:4173",
    "http://127.0.0.1:5173",
]

PROMPT_TEMPLATE = """
Eres el asistente oficial de Pizzería 220.

CAPACIDADES:
- Entender pedidos completos de pizza.
- Identificar cantidad, tamaño, ingredientes y extras.
- Conocer promociones y precios.
- Responder horarios y métodos de pago.
- Ubición de la pizzería y zonas de reparto.
REGLAS:

- Responde SOLO usando el contexto proporcionado.
- NO inventes información.
- Si existen promociones en el contexto, enuméralas claramente con precios.
- Si no existe información responde exactamente:
  "No hay datos disponibles."

- Si el cliente está realizando un pedido, al FINAL de tu respuesta agrega EXACTAMENTE este formato:

📝 PEDIDO:
Cantidad: [cantidad]
Producto: [producto]
Tamaño: [tamaño]
Extras: [extras o Ninguno]

- Considera como pedido ejemplos como:
  - Hawaiana mediana
  - Dos pepperoni familiares
  - La promo 3
  - Una mexicana con extra queso
  - Dos hawaianas y una coca

- Si el cliente solo pregunta información, menú, horarios o promociones,
  NO agregues la sección 📝 PEDIDO.

Responde siempre en español latino.

CONTEXTO:
{context}

PREGUNTA DEL CLIENTE:
{question}

RESPUESTA:
"""

PROMO_KEYWORDS = {"promo", "promocion", "oferta", "descuento", "combo"}

NOISE_WORDS = [
    "dime", "busca", "me", "puedes", "cuanto", "que", "una", "un",
    "la", "las", "el", "los", "de", "del", "para", "con",
]

# ==========================================
# ESTADO GLOBAL
# ==========================================
state: dict = {
    "db":              None,
    "promo_documents": [],
    "model":           None,
    "prompt_template": None,
    "ready":           False,
}

# ==========================================
# HELPERS
# ==========================================
def clean_query(text: str) -> str:
    text = text.lower()
    for w in NOISE_WORDS:
        text = re.sub(rf"\b{re.escape(w)}\b", " ", text)
    text = re.sub(r"[^a-zA-Z0-9áéíóúñ\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()

def format_promotions(promos) -> str:
    if not promos:
        return "No hay promociones activas actualmente."
    lines = ["📢 PROMOCIONES VIGENTES:\n"]
    for i, p in enumerate(promos, 1):
        lines.append(f"{i}. {p.page_content}\n")
    return "\n".join(lines)

# ==========================================
# LIFESPAN (startup / shutdown)
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Iniciando Pizzería 220 API...")

    def start_bot():
        try:
            run_bot()
        except Exception as e:
            print(f"⚠️ Telegram no disponible: {e}")

    threading.Thread(target=start_bot, daemon=True).start()
    time.sleep(1)

    pdf_documents             = chunk_pdfs()
    state["promo_documents"]  = load_promotions()

    embedding_model           = OllamaEmbeddings(model=EMBED_MODEL)
    state["db"]               = save_to_chroma_db(pdf_documents, embedding_model)
    state["model"]            = ChatOllama(model=CHAT_MODEL, temperature=0.2, num_ctx=4096)
    state["prompt_template"]  = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    state["ready"]            = True

    print("✅ API lista para recibir solicitudes")
    yield
    print("👋 Cerrando API...")

# ==========================================
# APP
# ==========================================
app = FastAPI(title="Pizzería 220 AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# SCHEMAS
# ==========================================
class ChatRequest(BaseModel):
    message: str

class OrderRequest(BaseModel):
    pedido:          str
    cliente_nombre:  str
    telefono:        str
    gmail:           str
    direccion:       str
    payment_method:  str
    ubicacion:       Optional[dict] = None  # {lat, lng, direccion_completa}

class StatusUpdateRequest(BaseModel):
    status: str

class RegisterRequest(BaseModel):
    nombre:    str
    telefono:  str
    gmail:     str
    direccion: str
    role:      str = "cliente"
    password:  str

class LoginRequest(BaseModel):
    gmail:    str
    password: str

# ==========================================
# ENDPOINTS
# ==========================================

@app.get("/health")
def health():
    return {"status": "ok", "ready": state["ready"]}

# ── Auth ─────────────────────────────────────────────────────────────────────
@app.post("/auth/register")
def register(req: RegisterRequest):
    gmail = req.gmail.strip().lower()

    if get_user_by_gmail(gmail):
        return {"success": False, "message": "El correo ya está registrado"}

    user = register_user(
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
def login(req: LoginRequest, response: Response):
    gmail = req.gmail.strip().lower()

    user = login_user(gmail=gmail, password_hash=req.password)

    if not user:
        return {"success": False, "message": "Correo o contraseña incorrectos"}

    response.set_cookie(
        key="session",
        value=str(user["id"]),
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 24 * 7
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
def logout(response: Response):
    response.delete_cookie(key="session", samesite="lax")
    return {"success": True}

# ── Chat ─────────────────────────────────────────────────────────────────────
@app.post("/chat")
def chat(req: ChatRequest):
    if not state["ready"]:
        return {"reply": "⏳ El sistema aún está cargando, intenta en unos segundos."}

    query = req.message.strip()
    if not query:
        return {"reply": ""}

    try:
        # Buscar en la base de conocimiento
        docs = state["db"].similarity_search(query, k=TOP_K)
        rag_context = "\n".join(doc.page_content for doc in docs)
        
        # Agregar promociones al contexto
        promos_text = "\n".join([p.page_content for p in state["promo_documents"]])
        full_context = f"{rag_context}\n\nPROMOCIONES VIGENTES:\n{promos_text}"

        # Generar respuesta con el LLM
        prompt = state["prompt_template"].format_messages(
            context=full_context, 
            question=query
        )
        response = state["model"].invoke(prompt)
        content = response.content
        
        # Detectar si es un pedido buscando la sección 📝 PEDIDO:
        is_order = "📝 PEDIDO:" in content
        
        order_details = None
        if is_order:
            # Extraer todo después de "📝 PEDIDO:"
            order_details = content.split("📝 PEDIDO:", 1)[1].strip()
        
        return {
            "reply": content,
            "is_order": is_order,
            "order_details": order_details
        }

    except Exception as e:
        print(f"❌ Error en /chat: {e}")
        return {"reply": "❌ Error interno del servidor."}

# ── Pedidos ───────────────────────────────────────────────────────────────────
@app.post("/order")
def order(req: OrderRequest):
    if not state["ready"]:
        return {"success": False, "message": "Sistema no listo"}

    # Guardar ubicación como JSON
    ubicacion_json = json.dumps(req.ubicacion) if req.ubicacion else None

    payload = {
        "cliente_nombre": req.cliente_nombre,
        "telefono":       req.telefono,
        "gmail":          req.gmail,
        "direccion":      req.direccion,
        "pedido":         req.pedido,
        "total":          "pendiente",
        "payment_method": req.payment_method,
        "estado":         "pendiente",
        "ubicacion_maps": ubicacion_json,
    }

    order_id = create_order(payload)
    if not order_id:
        return {"success": False, "message": "Error al crear el pedido en Supabase"}

    # Enviar a Telegram con la ubicación
    send_telegram_order(
        order_id       = order_id,
        cliente_nombre = req.cliente_nombre,
        telefono       = req.telefono,
        gmail          = req.gmail,
        direccion      = req.direccion,
        pedido         = req.pedido,
        payment_method = req.payment_method,
        ubicacion      = req.ubicacion,
    )

    return {"success": True, "order_id": order_id}

@app.patch("/order/{order_id}/status")
def patch_order_status(order_id: str, req: StatusUpdateRequest):
    valid_statuses = {"confirmado", "preparando", "en camino", "cancelado", "pendiente", "entregado"}
    if req.status not in valid_statuses:
        return {"success": False, "message": f"Estado inválido: {req.status}"}

    success = update_order_status(order_id, req.status)
    return {"success": success, "order_id": order_id, "status": req.status}

@app.get("/order/{order_id}/status")
def fetch_order_status(order_id: str):
    status = get_order_status(order_id)
    return {"order_id": order_id, "status": status}