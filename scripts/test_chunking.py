"""Manual test: clone a small real repo and inspect the resulting chunks.

Run from the repo root:

    python scripts/test_chunking.py [repo_url]

Defaults to https://github.com/psf/requests.git
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from codebase_rag.ingest.chunker import chunk_file
from codebase_rag.ingest.repo_loader import clone_repo, iter_repo_files

DEFAULT_REPO_URL = "https://github.com/psf/requests.git"
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "repos"


def main() -> None:
    repo_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REPO_URL

    print(f"Cloning {repo_url} ...")
    repo_path = clone_repo(repo_url, DATA_DIR)
    print(f"Cloned to {repo_path}")

    all_chunks = []
    files_processed = 0
    for file_path in iter_repo_files(repo_path):
        chunks = chunk_file(file_path, repo_path)
        if chunks:
            files_processed += 1
            all_chunks.extend(chunks)

    print(f"\nFiles processed: {files_processed}")
    print(f"Total chunks:    {len(all_chunks)}")

    by_type = Counter(c.chunk_type for c in all_chunks)
    print("\nChunks by type:")
    for chunk_type, count in by_type.most_common():
        print(f"  {chunk_type:10s} {count}")

    print("\nSample chunks:")
    samples = [c for c in all_chunks if c.chunk_type in ("function", "class")][:5]
    for chunk in samples:
        print(f"\n--- {chunk.file_path}:{chunk.start_line}-{chunk.end_line} "
              f"({chunk.chunk_type}: {chunk.name}) ---")
        preview = "\n".join(chunk.content.splitlines()[:6])
        print(preview)
        if len(chunk.content.splitlines()) > 6:
            print("...")


if __name__ == "__main__":
    main()
