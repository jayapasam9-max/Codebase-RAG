"""Tests for ast-based Python chunking and the line-based fallback."""

from pathlib import Path

from codebase_rag.ingest.chunker import (
    LINE_CHUNK_OVERLAP,
    LINE_CHUNK_SIZE,
    MAX_CHUNK_LINES,
    chunk_file,
    chunk_lines,
    chunk_python_source,
)


def test_top_level_function_is_one_chunk():
    source = "def greet(name):\n    return f'hello {name}'\n"

    chunks = chunk_python_source(source, "greet.py")

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_type == "function"
    assert chunk.name == "greet"
    assert chunk.start_line == 1
    assert chunk.end_line == 2
    assert "def greet(name):" in chunk.content


def test_top_level_class_is_one_chunk():
    source = "class Greeter:\n    def hello(self):\n        return 'hi'\n"

    chunks = chunk_python_source(source, "greeter.py")

    assert len(chunks) == 1
    assert chunks[0].chunk_type == "class"
    assert chunks[0].name == "Greeter"


def test_decorator_is_included_in_chunk_span():
    source = (
        "@app.route('/health')\n"
        "def health():\n"
        "    return 'ok'\n"
    )

    chunks = chunk_python_source(source, "app.py")

    assert len(chunks) == 1
    assert chunks[0].start_line == 1  # the decorator line, not the `def` line
    assert "@app.route" in chunks[0].content


def test_module_level_code_is_captured_as_a_separate_chunk():
    source = (
        "import os\n"
        "\n"
        "def greet():\n"
        "    return 'hi'\n"
    )

    chunks = chunk_python_source(source, "mod.py")

    types = {c.chunk_type for c in chunks}
    assert "module" in types
    assert "function" in types
    module_chunk = next(c for c in chunks if c.chunk_type == "module")
    assert "import os" in module_chunk.content


def test_oversized_function_is_split_but_keeps_its_name():
    body_lines = "\n".join(f"    x{i} = {i}" for i in range(MAX_CHUNK_LINES + 20))
    source = f"def big_function():\n{body_lines}\n    return x0\n"

    chunks = chunk_python_source(source, "big.py")

    assert len(chunks) > 1
    assert all(c.chunk_type == "function" for c in chunks)
    assert all(c.name == "big_function" for c in chunks)


def test_syntax_error_falls_back_to_line_chunking():
    source = "def broken(:\n    this is not valid python\n"

    chunks = chunk_python_source(source, "broken.py")

    assert len(chunks) >= 1
    assert all(c.chunk_type == "lines" for c in chunks)


def test_non_python_file_uses_line_based_fallback(tmp_path: Path):
    content = "\n".join(f"line {i}" for i in range(1, 251))
    readme = tmp_path / "README.md"
    readme.write_text(content)

    chunks = chunk_file(readme, tmp_path)

    assert len(chunks) > 1
    assert all(c.chunk_type == "lines" for c in chunks)
    assert chunks[0].file_path == "README.md"
    assert chunks[0].start_line == 1


def test_line_chunks_overlap_by_configured_amount():
    lines = [f"line {i}" for i in range(1, 251)]
    text = "\n".join(lines)

    chunks = chunk_lines(text, "big.txt", size=LINE_CHUNK_SIZE, overlap=LINE_CHUNK_OVERLAP)

    assert len(chunks) >= 2
    # second chunk should start before the first chunk ends, by the overlap amount
    assert chunks[1].start_line == chunks[0].end_line - LINE_CHUNK_OVERLAP + 1


def test_chunk_to_metadata_excludes_content_and_defaults_name():
    chunks = chunk_python_source("def f():\n    pass\n", "f.py")
    meta = chunks[0].to_metadata()

    assert meta["file_path"] == "f.py"
    assert meta["chunk_type"] == "function"
    assert meta["name"] == "f"
    assert "content" not in meta

    # module-level chunks have no name — should serialize to "" not None
    module_source = "X = 1\n"
    module_chunks = chunk_python_source(module_source, "consts.py")
    assert module_chunks[0].to_metadata()["name"] == ""


def test_chunk_file_uses_posix_relative_path(tmp_path: Path):
    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir()
    (pkg_dir / "mod.py").write_text("def f():\n    pass\n")

    chunks = chunk_file(pkg_dir / "mod.py", tmp_path)

    assert chunks[0].file_path == "pkg/mod.py"
