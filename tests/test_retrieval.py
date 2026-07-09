"""Retrieval sanity checks: embed a handful of clearly-distinct chunks with the
real local embedding model (no API cost) and verify obviously-relevant queries
return the obviously-correct chunk first. Uses a temp ChromaDB directory so
tests never touch the project's real chroma_db/.
"""

from pathlib import Path

from codebase_rag.embed import embed_texts
from codebase_rag.index import query_repo
from codebase_rag.ingest.chunker import Chunk
from codebase_rag.store import get_client, reset_collection

SAMPLE_CHUNKS = [
    Chunk(
        file_path="auth.py",
        start_line=1,
        end_line=3,
        chunk_type="function",
        name="login_user",
        content=(
            "def login_user(username, password):\n"
            "    '''Authenticate a user against the database and start a session.'''\n"
            "    return check_credentials(username, password)"
        ),
    ),
    Chunk(
        file_path="math_utils.py",
        start_line=1,
        end_line=3,
        chunk_type="function",
        name="add",
        content=(
            "def add(a, b):\n"
            "    '''Return the sum of two numbers.'''\n"
            "    return a + b"
        ),
    ),
    Chunk(
        file_path="README.md",
        start_line=1,
        end_line=2,
        chunk_type="lines",
        name=None,
        content="# My Project\nThis project has authentication and math utilities.",
    ),
]


def _index_sample_chunks(db_dir: Path, repo_name: str = "sample-repo") -> None:
    client = get_client(db_dir)
    collection = reset_collection(client, repo_name)
    ids = [f"chunk-{i}" for i in range(len(SAMPLE_CHUNKS))]
    documents = [c.content for c in SAMPLE_CHUNKS]
    metadatas = [c.to_metadata() for c in SAMPLE_CHUNKS]
    embeddings = embed_texts(documents)
    collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)


def test_authentication_query_returns_auth_chunk_first(tmp_path: Path):
    _index_sample_chunks(tmp_path)

    results = query_repo(
        "sample-repo", "How do I authenticate a user and check their password?",
        n_results=3, db_dir=tmp_path,
    )

    assert results["metadatas"][0][0]["file_path"] == "auth.py"


def test_math_query_returns_math_chunk_first(tmp_path: Path):
    _index_sample_chunks(tmp_path)

    results = query_repo(
        "sample-repo", "How do I add two numbers together?", n_results=3, db_dir=tmp_path,
    )

    assert results["metadatas"][0][0]["file_path"] == "math_utils.py"


def test_query_respects_n_results_limit(tmp_path: Path):
    _index_sample_chunks(tmp_path)

    results = query_repo("sample-repo", "authentication", n_results=1, db_dir=tmp_path)

    assert len(results["metadatas"][0]) == 1


def test_separate_repos_do_not_leak_into_each_other(tmp_path: Path):
    _index_sample_chunks(tmp_path, repo_name="repo-a")

    other_client = get_client(tmp_path)
    other_collection = reset_collection(other_client, "repo-b")
    only_chunk = Chunk(
        file_path="other.py", start_line=1, end_line=1, chunk_type="function",
        name="unrelated", content="def unrelated():\n    return None",
    )
    other_collection.add(
        ids=["chunk-0"],
        documents=[only_chunk.content],
        metadatas=[only_chunk.to_metadata()],
        embeddings=embed_texts([only_chunk.content]),
    )

    results = query_repo("repo-b", "authentication", n_results=5, db_dir=tmp_path)

    file_paths = {m["file_path"] for m in results["metadatas"][0]}
    assert file_paths == {"other.py"}
