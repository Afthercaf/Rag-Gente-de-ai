from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


DOCUMENTS_PATH = "documents"


def chunk_pdfs() -> list[Document]:

    loader = PyPDFDirectoryLoader(
        DOCUMENTS_PATH
    )

    documents = loader.load()

    print(f"PDFs cargados: {len(documents)}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        length_function=len,
        add_start_index=True,
    )

    chunks = splitter.split_documents(
        documents
    )

    print(f"Chunks generados: {len(chunks)}")

    return chunks