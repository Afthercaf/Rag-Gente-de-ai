import pdfplumber
import os
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

DOCUMENTS_PATH = "documents"

def load_pdfs_with_pdfplumber(path: str) -> list[Document]:
    documents = []

    for filename in os.listdir(path):
        if not filename.endswith(".pdf"):
            continue

        filepath = os.path.join(path, filename)
        full_text = ""

        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

        if full_text.strip():
            documents.append(Document(
                page_content=full_text,
                metadata={"source": filename}
            ))
            print(f"✓ Cargado: {filename} ({len(full_text)} caracteres)")
        else:
            print(f"✗ Sin texto: {filename}")

    return documents


def chunk_pdfs() -> list[Document]:
    documents = load_pdfs_with_pdfplumber(DOCUMENTS_PATH)
    print(f"PDFs cargados: {len(documents)}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,   # ← más grande para no cortar preguntas frecuentes
        chunk_overlap=300, # ← más overlap para no perder contexto entre chunks
        separators=["\n\n", "\n", ".", " ", ""], # ← respeta párrafos primero
        length_function=len,
        add_start_index=True,
    )

    chunks = splitter.split_documents(documents)
    print(f"Chunks generados: {len(chunks)}")

    return chunks