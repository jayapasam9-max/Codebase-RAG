"""ChromaDB persistence for chunk embeddings + file/line metadata."""

from pathlib import Path

import chromadb
from chromadb.api import ClientAPI

DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent / "chroma_db"


def get_client(db_dir: Path = DEFAULT_DB_DIR) -> ClientAPI:
    db_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(db_dir))


def collection_name_for_repo(repo_name: str) -> str:
    """Chroma collection names must be alnum/./-/_ and 3-63 chars."""
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in repo_name)
    safe = safe.strip("-_") or "repo"
    return safe[:63]


def reset_collection(client: ClientAPI, repo_name: str):
    """Drop any existing collection for this repo and create a fresh one.

    Re-indexing should replace the previous index rather than append to it,
    since re-running the chunker can change chunk boundaries/ids.
    """
    name = collection_name_for_repo(repo_name)
    try:
        client.delete_collection(name)
    except Exception:
        pass
    return client.create_collection(name)


def get_collection(client: ClientAPI, repo_name: str):
    return client.get_or_create_collection(collection_name_for_repo(repo_name))
