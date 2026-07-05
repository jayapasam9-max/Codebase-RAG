"""Clone a GitHub repo locally and walk its files for chunking."""

import subprocess
from pathlib import Path
from typing import Iterator

IGNORED_DIR_NAMES = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "dist", "build", ".pytest_cache", ".mypy_cache", ".tox",
}
IGNORED_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2",
    ".ttf", ".eot", ".zip", ".tar", ".gz", ".whl", ".pyc", ".so",
    ".dll", ".exe", ".bin", ".pdf", ".lock",
}
MAX_FILE_SIZE_BYTES = 500_000


def clone_repo(url: str, dest_dir: Path) -> Path:
    """Shallow-clone `url` into dest_dir/<repo_name>, reusing an existing clone if present.

    Returns the path to the cloned repo.
    """
    repo_name = url.rstrip("/").rsplit("/", 1)[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[: -len(".git")]
    target = dest_dir / repo_name

    if target.exists():
        subprocess.run(
            ["git", "-C", str(target), "fetch", "--depth", "1", "origin"], check=True
        )
        subprocess.run(
            ["git", "-C", str(target), "reset", "--hard", "FETCH_HEAD"], check=True
        )
    else:
        dest_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", url, str(target)], check=True)

    return target


def iter_repo_files(repo_path: Path) -> Iterator[Path]:
    """Yield source files under repo_path, skipping vendored/binary/oversized files."""
    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIR_NAMES for part in path.parts):
            continue
        if path.suffix.lower() in IGNORED_SUFFIXES:
            continue
        try:
            if path.stat().st_size > MAX_FILE_SIZE_BYTES:
                continue
        except OSError:
            continue
        yield path
