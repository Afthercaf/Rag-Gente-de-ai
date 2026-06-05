import time

from src.file_processor import chunk_pdfs
from src.supabase_promos import load_promotions
from src.chroma_db import save_to_chroma_db

from langchain_ollama import OllamaEmbeddings


EMBED_MODEL = "nomic-embed-text"

embedding_model = OllamaEmbeddings(
    model=EMBED_MODEL
)

last_total = 0

while True:

    print("Verificando promociones...")

    pdf_docs = chunk_pdfs()

    promo_docs = load_promotions()

    all_docs = (
        pdf_docs +
        promo_docs
    )

    current_total = len(all_docs)

    if current_total != last_total:

        print("Cambios detectados.")

        save_to_chroma_db(
            all_docs,
            embedding_model
        )

        last_total = current_total

        print("Base vectorial sincronizada.")

    else:
        print("Sin cambios.")

    time.sleep(15)