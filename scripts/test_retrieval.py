"""Manual retrieval sanity check against an already-built index.

Run from the repo root (after scripts/build_index.py):

    python scripts/test_retrieval.py [repo_name] [query ...]

With no query args, runs a handful of representative sample questions
against the psf/requests index so retrieval quality can be eyeballed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from codebase_rag.index import query_repo

DEFAULT_REPO_NAME = "requests"
SAMPLE_QUERIES = [
    "How does the library handle HTTP redirects?",
    "How are cookies parsed from a response?",
    "What class represents an HTTP session?",
    "How is a request timeout implemented?",
    "How is JSON encoded in a request body?",
]


def main() -> None:
    repo_name = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REPO_NAME
    queries = sys.argv[2:] or SAMPLE_QUERIES

    for query in queries:
        print(f"\n=== Query: {query!r} ===")
        results = query_repo(repo_name, query, n_results=3)
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]
        documents = results["documents"][0]

        for rank, (meta, dist, doc) in enumerate(zip(metadatas, distances, documents), start=1):
            loc = f"{meta['file_path']}:{meta['start_line']}-{meta['end_line']}"
            label = meta["chunk_type"] + (f" {meta['name']}" if meta["name"] else "")
            first_line = doc.splitlines()[0][:100] if doc.splitlines() else ""
            print(f"  {rank}. [dist {dist:.3f}] {loc}  ({label})")
            print(f"     {first_line}")


if __name__ == "__main__":
    main()
