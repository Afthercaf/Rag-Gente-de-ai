import os

from src.file_processor import chunk_pdfs
from src.chroma_db import save_to_chroma_db

from langchain_core.prompts import ChatPromptTemplate

from langchain_ollama import OllamaEmbeddings
from langchain_ollama import ChatOllama


# =========================
# CONFIG
# =========================
TOP_K = 5

EMBED_MODEL = "nomic-embed-text"

CHAT_MODEL = "qwen2.5-coder:3b"


# =========================
# Procesar PDFs
# =========================
print("\nCargando PDFs...\n")

processed_documents = chunk_pdfs()

print(f"Chunks creados: {len(processed_documents)}")


# =========================
# Embeddings
# =========================
print("\nInicializando embeddings...\n")

embedding_model = OllamaEmbeddings(
    model=EMBED_MODEL
)


# =========================
# ChromaDB
# =========================
print("\nCreando base vectorial...\n")

db = save_to_chroma_db(
    processed_documents,
    embedding_model
)

print("\nBase vectorial lista.\n")


# =========================
# Prompt
# =========================
PROMPT_TEMPLATE = """
Eres un asistente experto en manuales de motocicletas.

Debes responder SOLO usando el contexto proporcionado.

Cada fragmento contiene:
- nombre del archivo PDF
- contenido del manual

CONTEXTO:
{context}

PREGUNTA:
{question}

REGLAS:
- Responde completamente en español.
- Indica de qué archivo proviene la información.
- No mezcles motos diferentes.
- No inventes información.
- Si no existe en el contexto, dilo claramente.
- Usa listas cuando sea útil.
- Explica de forma técnica pero fácil de entender.
"""


prompt_template = ChatPromptTemplate.from_template(
    PROMPT_TEMPLATE
)


# =========================
# Modelo
# =========================
print(f"\nCargando modelo {CHAT_MODEL}...\n")

model = ChatOllama(
    model=CHAT_MODEL,
    temperature=0.2,
    num_ctx=4096,
)


# =========================
# Chat infinito
# =========================
print("\n===================================")
print("         CHAT RAG MOTOS")
print("===================================")
print("Escribe 'salir' para terminar.\n")


while True:

    query = input("Tú: ").strip()

    if query.lower() in ["salir", "exit", "quit"]:
        print("\nCerrando chat...\n")
        break

    if not query:
        continue


    # =========================
    # Buscar documentos similares
    # =========================
    docs = db.similarity_search_with_score(
        query,
        k=TOP_K
    )


    # =========================
    # Construir contexto
    # =========================
    context_parts = []

    for doc, score in docs:

        source = os.path.basename(
            doc.metadata.get(
                "source",
                "Desconocido"
            )
        )

        page = doc.metadata.get(
            "page",
            "N/A"
        )

        context_parts.append(
            f"""
ARCHIVO: {source}
PÁGINA: {page}
SIMILITUD: {score}

CONTENIDO:
{doc.page_content}
"""
        )

    context = "\n\n---\n\n".join(
        context_parts
    )


    # =========================
    # Crear prompt
    # =========================
    prompt = prompt_template.format(
        context=context,
        question=query
    )


    # =========================
    # Generar respuesta
    # =========================
    print("\nBuscando información...\n")

    response = model.invoke(prompt)


    # =========================
    # Mostrar respuesta
    # =========================
    print("===================================")
    print("MotoRAG:\n")
    print(response.content)
    print("===================================\n")