"""FastAPI app exposing the RAG pipeline as /index and /query endpoints."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .generate import answer_question
from .index import index_repo
from .ingest.repo_loader import clone_repo
from .store import collection_name_for_repo, get_client

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "repos"

app = FastAPI(
    title="Codebase-RAG",
    description="RAG-based Q&A over a GitHub repository, with Claude Haiku answer generation.",
)


class IndexRequest(BaseModel):
    repo_url: str


class IndexResponse(BaseModel):
    repo_name: str
    chunks_indexed: int


class QueryRequest(BaseModel):
    repo_name: str
    question: str
    n_results: int = 5


class QueryResponse(BaseModel):
    answer: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    session_cost_usd: float


def _repo_name_from_url(repo_url: str) -> str:
    name = repo_url.rstrip("/").rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[: -len(".git")]
    return name


def _ensure_indexed(repo_name: str) -> None:
    """Raise 404 if /query is called before /index has ever run for this repo."""
    client = get_client()
    name = collection_name_for_repo(repo_name)
    try:
        collection = client.get_collection(name)
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Repo '{repo_name}' has not been indexed yet. Call /index first.",
        ) from exc
    if collection.count() == 0:
        raise HTTPException(status_code=404, detail=f"Repo '{repo_name}' has no indexed chunks.")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/index", response_model=IndexResponse)
def index_endpoint(payload: IndexRequest) -> IndexResponse:
    repo_name = _repo_name_from_url(payload.repo_url)

    try:
        repo_path = clone_repo(payload.repo_url, DATA_DIR)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to clone repo: {exc}") from exc

    count = index_repo(repo_path, repo_name)
    if count == 0:
        raise HTTPException(status_code=422, detail="No indexable files found in repo")

    return IndexResponse(repo_name=repo_name, chunks_indexed=count)


@app.post("/query", response_model=QueryResponse)
def query_endpoint(payload: QueryRequest) -> QueryResponse:
    _ensure_indexed(payload.repo_name)

    try:
        result = answer_question(payload.repo_name, payload.question, n_results=payload.n_results)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return QueryResponse(
        answer=result.text,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        cost_usd=result.usage.cost_usd,
        session_cost_usd=result.session_cost_usd,
    )
