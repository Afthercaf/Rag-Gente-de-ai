# chroma_db.py - VERSIÓN OPTIMIZADA
import os
import time
import shutil
import pickle
import hashlib
from pathlib import Path
from langchain_community.vectorstores import Chroma

CHROMA_PATH = "chroma"
CACHE_PATH = Path("cache")

def get_document_hash(chunks):
    """Genera hash único del contenido de documentos"""
    content = "".join([d.page_content for d in chunks])
    return hashlib.md5(content.encode()).hexdigest()

def save_to_chroma_db(chunks, embedding_model):
    """Guarda con caché para carga rápida"""
    
    # Crear directorio de caché
    CACHE_PATH.mkdir(exist_ok=True)
    
    # Verificar caché
    doc_hash = get_document_hash(chunks)
    cache_file = CACHE_PATH / f"chroma_{doc_hash}.pkl"
    
    if cache_file.exists():
        print("📦 Cargando Chroma desde caché...")
        try:
            with open(cache_file, 'rb') as f:
                db = pickle.load(f)
                print("✅ Base vectorial cargada desde caché")
                return db
        except Exception as e:
            print(f"⚠️ Error cargando caché: {e}")
    
    # Timeout para evitar bloqueos largos
    time.sleep(1)
    
    # Eliminar DB anterior
    if os.path.exists(CHROMA_PATH):
        try:
            shutil.rmtree(CHROMA_PATH, ignore_errors=True)
            print("Chroma anterior eliminado.")
        except Exception as e:
            print(f"No se pudo borrar Chroma: {e}")
    
    # Crear nueva DB
    print("🔄 Creando nueva base vectorial...")
    db = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_model,
        persist_directory=CHROMA_PATH
    )
    db.persist()
    
    # Guardar en caché
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(db, f)
        print("✅ Base vectorial cacheada para futuras cargas")
    except Exception as e:
        print(f"⚠️ No se pudo cachear: {e}")
    
    print("✅ Base vectorial creada.")
    return db