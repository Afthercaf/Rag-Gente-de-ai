# main.py - Versión completa y corregida

import threading
import re
import time
from src.file_processor import chunk_pdfs
from src.supabase_promos import load_promotions
from src.chroma_db import save_to_chroma_db
from src.telegram_sender import send_telegram_order
from src.telegram_bot import run_bot
from src.supabase_orders import create_order
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import OllamaEmbeddings, ChatOllama
from utils.constants import CHAT_MODEL, EMBED_MODEL, OLLAMA_BASE_URL

# ==========================================
# INICIAR BOT DE TELEGRAM (CON MANEJO DE ERRORES)
# ==========================================

def start_telegram_bot():
    """Inicia el bot de Telegram con manejo de errores"""
    try:
        print("🔄 Iniciando bot de Telegram...")
        run_bot()
    except Exception as e:
        print(f"⚠️ Bot de Telegram no disponible: {e}")
        print("✅ El chatbot funciona sin Telegram")

# Iniciar bot en hilo separado
try:
    telegram_thread = threading.Thread(target=start_telegram_bot, daemon=True)
    telegram_thread.start()
    time.sleep(2)  # Esperar a que intente conectar
    print("\n✅ BOT TELEGRAM INICIADO EN SEGUNDO PLANO\n")
except Exception as e:
    print(f"\n⚠️ No se pudo iniciar Telegram: {e}")
    print("✅ Continuando solo con chatbot\n")

# ==========================================
# CONFIGURACIÓN
# ==========================================

TOP_K = 10
EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "qwen2.5-coder:3b"

# ==========================================
# CARGAR DOCUMENTOS
# ==========================================
print("="*40)
print("CARGANDO DOCUMENTOS")
print("="*40)

print("\n📄 Cargando documentos PDF...")
pdf_documents = chunk_pdfs()
print(f"✅ PDFs: {len(pdf_documents)} documentos")

print("\n📢 Cargando promociones de Supabase...")
promo_documents = load_promotions()
print(f"✅ Promociones: {len(promo_documents)} activas")

# ==========================================
# EMBEDDINGS Y BASE VECTORIAL
# ==========================================
print("\n🔧 Generando embeddings... ")
embedding_model = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_BASE_URL)
db = save_to_chroma_db(pdf_documents, embedding_model)
print("✅ Base vectorial lista.\n")

# ==========================================
# PROMPT TEMPLATE
# ==========================================
PROMPT_TEMPLATE = """
Eres el asistente oficial de Pizzería 220.

Especialista en:
- promociones
- pizzas
- ingredientes
- horarios
- pedidos
- métodos de pago

REGLAS:
- Responde usando únicamente el contexto.
- NO inventes información.
- Si existen promociones en el contexto, enuméralas claramente con precios.
- Si no existe información, responde: "No hay datos disponibles."
- Responde en español latino.
- Sé claro y conciso.

CONTEXTO:
{context}

PREGUNTA:
{question}
"""

prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
model = ChatOllama(model=CHAT_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.2, num_ctx=4096)

# ==========================================
# FUNCIONES AUXILIARES
# ==========================================

def clean_query(text):
    """Limpia la consulta para búsqueda"""
    text = text.lower()
    noise_words = ["quiero", "dime", "busca", "me", "puedes", "cuanto", "que", "una", "un", "la", "las", "el", "los", "de", "del", "para", "con"]
    for word in noise_words:
        text = re.sub(rf"\b{re.escape(word)}\b", " ", text)
    text = re.sub(r"[^a-zA-Z0-9áéíóúñ\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def is_order_query(text):
    """Detecta si es un pedido"""
    keywords = ["quiero pedir", "pedido", "ordenar", "comprar", "pizza", "mandame", "envía", "quiero una", "quisiera"]
    return any(word in text.lower() for word in keywords)

def ask_order_data():
    """Solicita datos del cliente"""
    print("\n" + "="*40)
    print("📋 DATOS DEL PEDIDO")
    print("="*40)
    
    cliente_nombre = input("👤 Nombre completo: ").strip()
    telefono = input("📞 Teléfono: ").strip()
    gmail = input("📧 Gmail: ").strip()
    direccion = input("📍 Dirección completa: ").strip()
    payment_method = input("💳 Pago (efectivo/tarjeta): ").strip()
    total = input("💰 Total del pedido (ej. 150.00, 150 pesos, dejar vacío si no aplica): ").strip()
    
    while payment_method.lower() not in ["efectivo", "tarjeta"]:
        print("❌ Método inválido. Use 'efectivo' o 'tarjeta'")
        payment_method = input("💳 Pago (efectivo/tarjeta): ").strip()
    
    return {
        "cliente_nombre": cliente_nombre,
        "telefono": telefono,
        "gmail": gmail,
        "direccion": direccion,
        "payment_method": payment_method,
        "total": total or None
    }

def format_promotions(promo_documents):
    """Formatea las promociones para el contexto"""
    if not promo_documents:
        return "No hay promociones activas actualmente."
    
    promos_text = "📢 PROMOCIONES VIGENTES:\n\n"
    for i, promo in enumerate(promo_documents, 1):
        promos_text += f"{i}. {promo.page_content}\n\n"
    return promos_text

def is_telegram_status_update(text):
    """Detecta y filtra mensajes internos de Telegram"""
    # Filtrar JSON de Supabase
    if text.strip().startswith('[') and 'estado' in text:
        return True
    # Filtrar logs del bot
    if '[BOT]' in text or 'Pedido' in text and '->' in text:
        return True
    return False

# ==========================================
# CHAT PRINCIPAL
# ==========================================

print("="*40)
print("     🍕 PIZZERIA 220 AI")
print("="*40)
print(f"📚 Modelo: {CHAT_MODEL}")
print(f"🎯 Promociones cargadas: {len(promo_documents)}")
print("💬 Escribe 'salir' para terminar")
print("="*40 + "\n")

while True:
    try:
        query = input("👤 Tú: ").strip()
    except KeyboardInterrupt:
        print("\n\n🍕 ¡Gracias por usar Pizzería 220 AI! Hasta luego.\n")
        break
    except EOFError:
        continue
    
    if not query:
        continue
    
    # FILTRAR MENSAJES INTERNOS DE TELEGRAM
    if is_telegram_status_update(query):
        continue  # Ignorar y seguir
    
    # Salir
    if query.lower() in ["salir", "exit", "quit"]:
        print("\n🍕 ¡Gracias por usar Pizzería 220 AI! Hasta luego.\n")
        break
    
    # ======================================
    # PROCESAR PEDIDO
    # ======================================
    if is_order_query(query):
        order_data = ask_order_data()
        
        order_payload = {
            "cliente_nombre": order_data["cliente_nombre"],
            "telefono": order_data["telefono"],
            "gmail": order_data["gmail"],
            "direccion": order_data["direccion"],
            "pedido": query,
            "total": order_data.get("total") or "pendiente",
            "payment_method": order_data["payment_method"],
            "estado": "pendiente"
        }
        
        print("\n📝 Registrando pedido...")
        order_id = create_order(order_payload)
        
        if order_id:
            # Enviar a Telegram con botones
            print("📤 Enviando a Telegram...")
            send_telegram_order(
                order_id=order_id,
                cliente_nombre=order_data["cliente_nombre"],
                telefono=order_data["telefono"],
                gmail=order_data["gmail"],
                direccion=order_data["direccion"],
                pedido=query,
                payment_method=order_data["payment_method"],
                total=order_data.get("total") or "pendiente"
            )
            
            print("\n" + "="*40)
            print("🍕 PIZZERIA 220 AI")
            print("="*40)
            print(f"✅ Pedido registrado correctamente")
            print(f"🆔 ID DEL PEDIDO: {order_id}")
            if order_data.get("total"):
                print(f"💰 Total: {order_data['total']}")
            print(f"📦 Estado: PENDIENTE")
            print(f"🍕 Esperando confirmación en Telegram...")
            print("="*40 + "\n")
        else:
            print("\n" + "="*40)
            print("🍕 PIZZERIA 220 AI")
            print("="*40)
            print("❌ Error al crear el pedido")
            print("💡 Verifica tu conexión a Supabase")
            print("="*40 + "\n")
        continue
    
    # ======================================
    # CONSULTA NORMAL CON RAG + PROMOCIONES
    # ======================================
    
    try:
        # 1. Buscar en documentos PDF
        search_query = clean_query(query)
        docs = db.similarity_search_with_score(search_query, k=TOP_K)
        
        context_parts = []
        for doc, score in docs:
            context_parts.append(doc.page_content)
        
        rag_context = "\n".join(context_parts)
        
        # 2. Agregar promociones al contexto
        promos_context = format_promotions(promo_documents)
        
        # 3. Detectar si la pregunta es sobre promociones
        promo_keywords = ["promo", "promocion", "oferta", "descuento", "combo"]
        is_promo_query = any(keyword in query.lower() for keyword in promo_keywords)
        
        if is_promo_query:
            # Priorizar promociones en la respuesta
            full_context = f"""
{promos_context}

📄 INFORMACIÓN ADICIONAL DE LA PIZZERÍA:
{rag_context}
"""
        else:
            # Contexto normal
            full_context = f"""
📄 INFORMACIÓN DE LA PIZZERÍA:
{rag_context}

{promos_context}
"""
        
        # 4. Generar respuesta con IA
        prompt = prompt_template.format(context=full_context, question=query)
        response = model.invoke(prompt)
        
        print("\n" + "="*40)
        print("🍕 PIZZERIA 220 AI")
        print("="*40)
        print(response.content)
        print("="*40 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error al generar respuesta: {e}")
        print("💡 Intenta de nuevo o reformula tu pregunta\n")

print("Sistema cerrado.")