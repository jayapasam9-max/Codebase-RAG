"""Clone (or reuse) a repo, chunk it, embed the chunks, and store them in ChromaDB.

Run from the repo root:

    python scripts/build_index.py [repo_url]

Defaults to https://github.com/psf/requests.git
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from codebase_rag.index import index_repo
from codebase_rag.ingest.repo_loader import clone_repo

DEFAULT_REPO_URL = "https://github.com/psf/requests.git"
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "repos"


def main() -> None:
    repo_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REPO_URL
    repo_name = repo_url.rstrip("/").rsplit("/", 1)[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[: -len(".git")]

    print(f"Cloning/updating {repo_url} ...")
    repo_path = clone_repo(repo_url, DATA_DIR)

    print(f"Chunking + embedding {repo_name} (this loads the embedding model on first run) ...")
    count = index_repo(repo_path, repo_name)
    print(f"Indexed {count} chunks into ChromaDB collection '{repo_name}'.")


if __name__ == "__main__":
    main()
