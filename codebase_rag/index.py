"""Chunk a repo, embed the chunks, and store them in ChromaDB (and query them back)."""

from pathlib import Path
from typing import Optional

from .embed import embed_texts
from .ingest.chunker import Chunk, chunk_file
from .ingest.repo_loader import iter_repo_files
from .store import get_client, get_collection, reset_collection

BATCH_SIZE = 64


def build_chunks(repo_path: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for file_path in iter_repo_files(repo_path):
        chunks.extend(chunk_file(file_path, repo_path))
    return chunks


def index_repo(repo_path: Path, repo_name: str, db_dir: Optional[Path] = None) -> int:
    """Chunk, embed, and store every file in repo_path under a fresh collection.

    `db_dir` overrides the default ChromaDB location — used by tests to avoid
    writing into the project's real chroma_db/ directory.

    Returns the number of chunks indexed.
    """
    chunks = build_chunks(repo_path)
    if not chunks:
        return 0

    client = get_client(db_dir) if db_dir else get_client()
    collection = reset_collection(client, repo_name)

    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]
        ids = [f"chunk-{start + i}" for i in range(len(batch))]
        documents = [c.content for c in batch]
        metadatas = [c.to_metadata() for c in batch]
        embeddings = embed_texts(documents)
        collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)

    return len(chunks)


def query_repo(
    repo_name: str, query_text: str, n_results: int = 5, db_dir: Optional[Path] = None
) -> dict:
    """Return the top-n chunks (with metadata) most similar to query_text.

    `db_dir` overrides the default ChromaDB location — used by tests to avoid
    writing into the project's real chroma_db/ directory.
    """
    client = get_client(db_dir) if db_dir else get_client()
    collection = get_collection(client, repo_name)
    query_embedding = embed_texts([query_text])[0]
    return collection.query(query_embeddings=[query_embedding], n_results=n_results)
