
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore


def create_vector_store(chunks, embeddings, source_name):

    docs = []

    for i, chunk in enumerate(chunks):
        docs.append(
            Document(
                page_content=chunk,
                metadata={
                    "source": source_name,
                    "chunk_id": i + 1
                }
            )
        )

    vector_store = InMemoryVectorStore(embeddings)
    vector_store.add_documents(docs)

    return vector_store
