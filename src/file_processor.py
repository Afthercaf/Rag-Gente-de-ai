import pdfplumber
import os
import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

DOCUMENTS_PATH = "documents"
MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 200
logger = logging.getLogger(__name__)

def load_pdfs_with_pdfplumber(path: str) -> list[Document]:
    documents = []

    for filename in os.listdir(path):
        if not filename.endswith(".pdf"):
            continue

        filepath = os.path.join(path, filename)
        if os.path.getsize(filepath) > MAX_PDF_BYTES:
            logger.warning("PDF omitido por tamaño excesivo")
            continue
        with open(filepath, "rb") as source:
            if source.read(5) != b"%PDF-":
                logger.warning("Archivo .pdf omitido por firma inválida")
                continue
        full_text = ""

        with pdfplumber.open(filepath) as pdf:
            if len(pdf.pages) > MAX_PDF_PAGES:
                logger.warning("PDF omitido por exceso de páginas")
                continue
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

        if full_text.strip():
            documents.append(Document(
                page_content=full_text,
                metadata={"source": filename}
            ))
            logger.info("PDF cargado; caracteres=%d", len(full_text))
        else:
            logger.warning("PDF sin texto utilizable")

    return documents


def chunk_pdfs() -> list[Document]:
    documents = load_pdfs_with_pdfplumber(DOCUMENTS_PATH)
    logger.info("PDFs cargados=%d", len(documents))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,   # ← más grande para no cortar preguntas frecuentes
        chunk_overlap=300, # ← más overlap para no perder contexto entre chunks
        separators=["\n\n", "\n", ".", " ", ""], # ← respeta párrafos primero
        length_function=len,
        add_start_index=True,
    )

    chunks = splitter.split_documents(documents)
    logger.info("Chunks generados=%d", len(chunks))

    return chunks
