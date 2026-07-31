"""
Wraps a Chroma vector store, one persisted collection per uploaded
document, so each document's knowledge base stays isolated and can be
reopened cheaply on later requests without re-embedding.
"""

from django.conf import settings
from langchain_chroma import Chroma
from langchain_core.documents import Document as LCDocument

from .llm import get_embeddings


def build_vectorstore(collection_name: str, docs: list[LCDocument]) -> Chroma:
    return Chroma.from_documents(
        documents=docs,
        embedding=get_embeddings(),
        collection_name=collection_name,
        persist_directory=str(settings.VECTOR_STORE_DIR),
    )


def load_vectorstore(collection_name: str) -> Chroma:
    return Chroma(
        collection_name=collection_name,
        embedding_function=get_embeddings(),
        persist_directory=str(settings.VECTOR_STORE_DIR),
    )


def get_retriever(collection_name: str, k: int = 4):
    return load_vectorstore(collection_name).as_retriever(search_kwargs={"k": k})
