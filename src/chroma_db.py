import os
import time
import shutil

from langchain_community.vectorstores import Chroma

CHROMA_PATH = "chroma"


def save_to_chroma_db(
    chunks,
    embedding_model
):

    # Esperar liberación del lock
    time.sleep(2)

    # Intentar borrar DB anterior
    if os.path.exists(CHROMA_PATH):

        try:

            shutil.rmtree(
                CHROMA_PATH,
                ignore_errors=True
            )

            print("Chroma anterior eliminado.")

        except Exception as e:

            print("No se pudo borrar Chroma:")
            print(e)

    # Crear nueva DB
    db = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_model,
        persist_directory=CHROMA_PATH
    )

    db.persist()

    print("Base vectorial creada.")

    return db