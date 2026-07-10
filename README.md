# Codebase-RAG

![Python](https://img.shields.io/badge/Python-3.10-3776AB?logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-0.139-009688?logo=fastapi&logoColor=white) ![Streamlit](https://img.shields.io/badge/Streamlit-1.59-FF4B4B?logo=streamlit&logoColor=white) ![Claude Haiku](https://img.shields.io/badge/Claude-Haiku%204.5-D97757?logo=anthropic&logoColor=white) ![ChromaDB](https://img.shields.io/badge/ChromaDB-1.5-6A3EA1) ![Sentence Transformers](https://img.shields.io/badge/Sentence--Transformers-5.6-FFD21E?logo=huggingface&logoColor=black) ![License](https://img.shields.io/badge/License-MIT-yellow.svg) ![CI](https://github.com/jayapasam9-max/Codebase-RAG/actions/workflows/ci.yml/badge.svg)

A RAG-based Q&A bot for GitHub repositories. Point it at a repo, ask questions
about the code, and get answers with file/line citations.

## Demo

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://codebase-rag678567.streamlit.app)

**[Live demo →](https://codebase-rag678567.streamlit.app)** — paste a repo URL, index it, and ask it questions yourself.

> The demo session has a hard cap ($0.50 / 5 queries) so a shared public link
> can't drain the project's API budget — see [Design decisions](#design-decisions--known-limitations).
> It also runs on an ephemeral container, so a fresh deploy means re-indexing.
> For unrestricted use, clone the repo and run it locally with your own
> `ANTHROPIC_API_KEY` (see [Setup](#setup)).

![Streamlit UI answering "What class represents an HTTP session?" against psf/requests, with a correct citation to src/requests/sessions.py and a running Claude Haiku spend counter](docs/images/demo-query.png)

Indexed against [psf/requests](https://github.com/psf/requests) and asked
*"What class represents an HTTP session?"* — the answer correctly cites
`src/requests/sessions.py`, the actual source of the `Session` class, rather
than any of the documentation pages that also mention sessions.

![Live deployment on Streamlit Community Cloud answering "How are cookies parsed from a response?" with a correct citation to extract_cookies_to_jar in cookies.py, and the session budget cap visible in the sidebar](docs/images/demo-live-budget.png)

The live deployment above, mid-session — sidebar shows the budget safeguard
tracking real spend and query count against the demo's caps.

## Architecture

```
GitHub repo URL
      │
      ▼
 clone_repo()                 codebase_rag/ingest/repo_loader.py
      │                       (shallow git clone; skips vendored/binary/oversized files)
      ▼
 chunk_file()                 codebase_rag/ingest/chunker.py
      │                       ast-based split by function/class for .py,
      │                       line-based fallback (with overlap) for everything else
      ▼
 embed_texts()                codebase_rag/embed.py
      │                       sentence-transformers, local — no API cost
      ▼
 ChromaDB collection          codebase_rag/store.py
      │                       one collection per repo, reset on re-index
      │
      │   query_repo()  ◄──────────────────  user's question
      ▼
 top-k chunks + file/line metadata
      │
      ▼
 answer_question()            codebase_rag/generate.py
      │                       RAG prompt (prioritizes code over docs — see
      │                       "Design decisions" below) + Claude Haiku, cited answer
      ▼
 FastAPI (/index, /query)          Streamlit UI
 codebase_rag/api.py               streamlit_app.py
```

The Streamlit app and FastAPI app are two independent interfaces over the same
`codebase_rag` package — Streamlit calls it directly in-process (simplest for a
single-user demo); FastAPI exposes it as a JSON API for other consumers. Both
end at the same `index_repo()` / `answer_question()` functions, so indexing and
retrieval logic isn't duplicated between them.

## Stack

- **Chunking**: `ast`-based splitting for Python files (by function/class), line-based fallback for other file types
- **Embeddings**: local, via `sentence-transformers` (no API cost)
- **Vector store**: ChromaDB
- **Answer generation**: Claude Haiku (Anthropic API)
- **Backend**: FastAPI (`/index`, `/query`)
- **Frontend**: Streamlit

## Project structure

```
codebase_rag/
├── ingest/
│   ├── repo_loader.py   clone/walk a target repo
│   └── chunker.py       ast-based + line-based chunking
├── embed.py             local sentence-transformers embeddings
├── store.py             ChromaDB persistence (one collection per repo)
├── index.py             chunk → embed → store → retrieve
├── generate.py          RAG prompt + Claude Haiku call, with citations
└── api.py               FastAPI /index and /query endpoints
streamlit_app.py          Streamlit frontend (calls codebase_rag directly)
scripts/                  one-off CLI scripts used during development
tests/                    pytest suite (chunking, retrieval, mocked LLM calls)
.github/workflows/        CI
```

## Setup

```bash
git clone https://github.com/jayapasam9-max/Codebase-RAG.git
cd Codebase-RAG
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Indexing works without any credentials (embeddings are local). Answer
generation needs an Anthropic API key — put it in a `.env` file at the repo
root (already gitignored):

```
ANTHROPIC_API_KEY=sk-ant-...
```

### Run the Streamlit app (recommended)

```bash
streamlit run streamlit_app.py
```

Paste a GitHub repo URL, click **Index repository**, then ask questions.

### Or use the FastAPI backend directly

```bash
uvicorn codebase_rag.api:app --reload
```

```bash
curl -X POST localhost:8000/index -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/psf/requests.git"}'

curl -X POST localhost:8000/query -H "Content-Type: application/json" \
  -d '{"repo_name": "requests", "question": "What class represents an HTTP session?"}'
```

### Run the tests

```bash
pytest
```

The whole suite runs offline — the Anthropic client is patched out at the
class level, so it never spends API credit and never needs a real key.

## Roadmap

- [x] Repo init + .gitignore + requirements.txt + README stub
- [x] Script to clone/walk a target repo and chunk files (ast-based for .py, line-based fallback for others)
- [x] Local embedding generation with sentence-transformers + store in ChromaDB with file/line metadata
- [x] RAG prompt construction + Claude Haiku API call for answer generation, with file/line citations
- [x] Wrap into FastAPI endpoints: /index and /query
- [x] Streamlit frontend: paste repo URL, index, ask questions, see cited answers
- [x] Basic tests (chunking logic + retrieval sanity checks, mocked LLM call) + GitHub Actions CI workflow
- [x] Polish README with architecture explanation and setup instructions

## Design decisions & known limitations

**Retrieval sometimes ranks docs above the code that actually implements a feature.**
Manual retrieval checks (step 3, against `psf/requests`) showed that changelog/doc
files (`HISTORY.md`, `docs/*.rst`) can outrank the actual source code for a query,
because prose often repeats the query's keywords more literally than code does —
e.g. a query about "HTTP redirects" ranked `HISTORY.md` entries above the
`SessionRedirectMixin` class that implements the behavior.

Rather than fix this at the retrieval layer (e.g. reranking, hybrid search), the
**answer-generation prompt (step 4) is told explicitly to prioritize source code
over non-code chunks** (README/HISTORY/CHANGELOG/docs) when both are retrieved,
and to say so — rather than guess — when no relevant source code was retrieved at
all. This was verified with two test queries against Claude Haiku:

- A query where no code chunk was retrieved in the top 5: the model correctly
  said the implementing class wasn't present in its context, instead of
  fabricating an answer from the docs.
- A query where a doc chunk outranked a code chunk: the model cited only the
  actual source function (`extract_cookies_to_jar` in `cookies.py`) and ignored
  the higher-ranked doc chunk.

**Public demo capped at $0.50 / 5 queries per session to protect API budget** —
clone and run locally with your own key for unrestricted use. The cap lives in
`streamlit_app.py` (`SESSION_BUDGET_LIMIT`, `MAX_QUERIES_PER_SESSION`), tracked
per browser session via `st.session_state` so it resets only on a new session,
not on every rerun.

## License

MIT — see [LICENSE](LICENSE).
