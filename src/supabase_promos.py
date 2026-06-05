import os
import requests
import time
from dotenv import load_dotenv
from langchain_core.documents import Document

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def load_promotions() -> list[Document]:
    """Carga promociones con timeout alto y reintentos"""
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("⚠️ Supabase no configurado")
        return []
    
    url = f"{SUPABASE_URL}/rest/v1/promociones?activa=eq.true"
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"🔄 Cargando promociones (intento {attempt + 1})...")
            
            # Timeout de 30 segundos para conexión lenta
            response = requests.get(
                url,
                headers=headers,
                timeout=(10, 30)  # (connect timeout, read timeout)
            )
            
            if response.status_code == 200:
                data = response.json()
                docs = []
                
                for promo in data:
                    content = f"""
PROMOCION:
{promo['nombre']}

DESCRIPCION:
{promo['descripcion']}

INGREDIENTES:
{promo['ingredientes']}

REFRESCO:
{promo['refresco']}

PRECIO:
{promo['precio']}
"""
                    docs.append(
                        Document(
                            page_content=content,
                            metadata={
                                "source": "supabase",
                                "promo_id": promo["id"]
                            }
                        )
                    )
                
                print(f"✅ Promociones cargadas: {len(docs)}")
                return docs
                
            else:
                print(f"❌ Error {response.status_code}: {response.text[:100]}")
                
        except requests.exceptions.Timeout:
            print(f"⚠️ Timeout (intento {attempt + 1})")
            if attempt < max_retries - 1:
                time.sleep(3)
                
        except Exception as e:
            print(f"❌ Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(3)
    
    print("⚠️ Usando lista vacía de promociones")
    return []