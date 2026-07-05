"""Split repo files into retrievable chunks.

Python files are split by top-level function/class definitions using `ast`,
so retrieval can point back to a specific function or class. Everything else
(and any oversized def/class body) falls back to fixed-size, overlapping
line-based chunks.
"""

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

MAX_CHUNK_LINES = 200
LINE_CHUNK_SIZE = 100
LINE_CHUNK_OVERLAP = 20


@dataclass
class Chunk:
    file_path: str  # posix-style, relative to repo root
    start_line: int  # 1-indexed, inclusive
    end_line: int  # 1-indexed, inclusive
    chunk_type: str  # "function" | "class" | "module" | "lines"
    name: Optional[str]
    content: str

    def to_metadata(self) -> dict:
        """Metadata suitable for storing alongside the embedding (excludes content)."""
        return {
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "chunk_type": self.chunk_type,
            "name": self.name or "",
        }


def chunk_file(path: Path, repo_root: Path) -> list[Chunk]:
    rel_path = path.relative_to(repo_root).as_posix()
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    if path.suffix == ".py":
        return chunk_python_source(source, rel_path)
    return chunk_lines(source, rel_path, chunk_type="lines", base_line=1)


def chunk_python_source(source: str, rel_path: str) -> list[Chunk]:
    lines = source.splitlines()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return chunk_lines(source, rel_path, chunk_type="lines", base_line=1)

    chunks: list[Chunk] = []
    covered = [False] * (len(lines) + 1)  # 1-indexed; index 0 unused

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = _node_start_line(node)
            end = node.end_lineno
            chunk_type = "class" if isinstance(node, ast.ClassDef) else "function"
            text = "\n".join(lines[start - 1 : end])
            chunks.extend(_chunk_def(text, rel_path, start, chunk_type, node.name))
            for i in range(start, end + 1):
                covered[i] = True

    for start, end in _uncovered_ranges(covered, len(lines)):
        text = "\n".join(lines[start - 1 : end])
        if text.strip():
            chunks.extend(chunk_lines(text, rel_path, chunk_type="module", base_line=start))

    chunks.sort(key=lambda c: c.start_line)
    return chunks


def _node_start_line(node: ast.AST) -> int:
    """Include leading decorators in the chunk span."""
    decorators = getattr(node, "decorator_list", None)
    if decorators:
        return min(d.lineno for d in decorators)
    return node.lineno


def _chunk_def(text: str, rel_path: str, start_line: int, chunk_type: str, name: str) -> list[Chunk]:
    line_count = len(text.splitlines())
    if line_count <= MAX_CHUNK_LINES:
        return [
            Chunk(
                file_path=rel_path,
                start_line=start_line,
                end_line=start_line + line_count - 1,
                chunk_type=chunk_type,
                name=name,
                content=text,
            )
        ]
    # Too large for one chunk — fall back to line-based splitting, keeping the name for traceability.
    return chunk_lines(text, rel_path, chunk_type=chunk_type, base_line=start_line, name=name)


def chunk_lines(
    text: str,
    rel_path: str,
    chunk_type: str = "lines",
    base_line: int = 1,
    name: Optional[str] = None,
    size: int = LINE_CHUNK_SIZE,
    overlap: int = LINE_CHUNK_OVERLAP,
) -> list[Chunk]:
    lines = text.splitlines()
    n = len(lines)
    if n == 0:
        return []

    chunks: list[Chunk] = []
    step = max(size - overlap, 1)
    i = 0
    while i < n:
        end = min(i + size, n)
        piece = "\n".join(lines[i:end])
        if piece.strip():
            chunks.append(
                Chunk(
                    file_path=rel_path,
                    start_line=base_line + i,
                    end_line=base_line + end - 1,
                    chunk_type=chunk_type,
                    name=name,
                    content=piece,
                )
            )
        if end == n:
            break
        i += step
    return chunks


def _uncovered_ranges(covered: list[bool], n: int) -> list[tuple[int, int]]:
    """Contiguous 1-indexed [start, end] ranges where covered[i] is False."""
    ranges = []
    start = None
    for i in range(1, n + 1):
        if not covered[i]:
            if start is None:
                start = i
        elif start is not None:
            ranges.append((start, i - 1))
            start = None
    if start is not None:
        ranges.append((start, n))
    return ranges
