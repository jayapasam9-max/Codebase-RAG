# Codebase-RAG

A RAG-based Q&A bot for GitHub repositories. Point it at a repo, ask questions
about the code, and get answers with file/line citations.

## Stack

- **Chunking**: `ast`-based splitting for Python files (by function/class), line-based fallback for other file types
- **Embeddings**: local, via `sentence-transformers` (no API cost)
- **Vector store**: ChromaDB
- **Answer generation**: Claude Haiku (Anthropic API)
- **Backend**: FastAPI (`/index`, `/query`)
- **Frontend**: Streamlit

## Status

Early scaffolding — build log follows in commit history.

## Roadmap

- [x] Repo init + .gitignore + requirements.txt + README stub
- [x] Script to clone/walk a target repo and chunk files (ast-based for .py, line-based fallback for others)
- [x] Local embedding generation with sentence-transformers + store in ChromaDB with file/line metadata
- [ ] RAG prompt construction + Claude Haiku API call for answer generation, with file/line citations
- [ ] Wrap into FastAPI endpoints: /index and /query
- [ ] Streamlit frontend: paste repo URL, index, ask questions, see cited answers
- [ ] Basic tests (chunking logic + retrieval sanity checks, mocked LLM call) + GitHub Actions CI workflow
- [ ] Polish README with architecture explanation and setup instructions

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You'll need an `ANTHROPIC_API_KEY` set in your environment (or a `.env` file)
to use answer generation.

More setup and architecture details to come as the project is built out.
