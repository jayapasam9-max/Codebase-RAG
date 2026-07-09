"""Streamlit frontend for Codebase-RAG: paste a repo URL, index it, ask questions.

Run from the repo root, with ANTHROPIC_API_KEY set in your environment or in a
.env file:

    streamlit run streamlit_app.py

This calls the codebase_rag pipeline (chunk/embed/store/generate) directly in
the Streamlit process rather than going through the FastAPI layer from step 5
— simpler for a single-user local demo, with no separate server to run. The
FastAPI app remains available as a standalone API for other consumers.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from codebase_rag.generate import answer_question
from codebase_rag.index import index_repo
from codebase_rag.ingest.repo_loader import clone_repo

DATA_DIR = Path(__file__).resolve().parent / "data" / "repos"

# Hard safeguards for a public demo deployment (e.g. Streamlit Community Cloud)
# so a widely-shared link can't drain the project's fixed Anthropic API budget.
SESSION_BUDGET_LIMIT = 0.50  # USD, per browser session
MAX_QUERIES_PER_SESSION = 5  # backup cap in case many cheap queries slip under the $ cap

BUDGET_EXHAUSTED_MESSAGE = (
    "Demo budget reached for this session. Clone the repo and run it locally "
    "with your own Anthropic API key to keep exploring."
)

st.set_page_config(page_title="Codebase-RAG", page_icon="🔍", layout="wide")


def repo_name_from_url(repo_url: str) -> str:
    name = repo_url.rstrip("/").rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[: -len(".git")]
    return name


if "indexed_repo" not in st.session_state:
    st.session_state.indexed_repo = None
if "history" not in st.session_state:
    st.session_state.history = []
if "session_cost" not in st.session_state:
    st.session_state.session_cost = 0.0
if "query_count" not in st.session_state:
    st.session_state.query_count = 0

st.title("🔍 Codebase-RAG")
st.caption(
    "Ask questions about a GitHub repo's code and get answers with file/line "
    "citations, powered by local embeddings + Claude Haiku."
)

with st.sidebar:
    st.header("1. Index a repository")
    repo_url = st.text_input("GitHub repo URL", placeholder="https://github.com/psf/requests.git")
    index_clicked = st.button("Index repository", type="primary", disabled=not repo_url)

    if index_clicked:
        repo_name = repo_name_from_url(repo_url)
        with st.spinner(
            f"Cloning and indexing '{repo_name}'... first run also downloads the "
            "embedding model, so this can take a minute."
        ):
            try:
                repo_path = clone_repo(repo_url, DATA_DIR)
                count = index_repo(repo_path, repo_name)
            except Exception as exc:
                st.error(f"Failed to index repo: {exc}")
            else:
                if count == 0:
                    st.error("No indexable files found in this repo.")
                else:
                    st.session_state.indexed_repo = repo_name
                    st.session_state.history = []
                    st.success(f"Indexed {count} chunks from '{repo_name}'.")

    if st.session_state.indexed_repo:
        st.info(f"Currently indexed: **{st.session_state.indexed_repo}**")

st.header("2. Ask a question")

if not st.session_state.indexed_repo:
    st.warning("Index a repository in the sidebar first.")
else:
    budget_exhausted = (
        st.session_state.session_cost >= SESSION_BUDGET_LIMIT
        or st.session_state.query_count >= MAX_QUERIES_PER_SESSION
    )

    if budget_exhausted:
        st.error(BUDGET_EXHAUSTED_MESSAGE)
    else:
        question = st.text_input(
            "Your question", placeholder="How does this library handle HTTP redirects?"
        )
        ask_clicked = st.button("Ask", disabled=not question)

        if ask_clicked:
            with st.spinner("Retrieving relevant code and asking Claude Haiku..."):
                try:
                    result = answer_question(st.session_state.indexed_repo, question)
                except Exception as exc:
                    st.error(f"Failed to answer: {exc}")
                else:
                    st.session_state.session_cost = result.session_cost_usd
                    st.session_state.query_count += 1
                    st.session_state.history.insert(
                        0, {"question": question, "answer": result.text, "usage": result.usage}
                    )

    for entry in st.session_state.history:
        with st.container(border=True):
            st.markdown(f"**Q: {entry['question']}**")
            st.markdown(entry["answer"])
            usage = entry["usage"]
            st.caption(
                f"{usage.input_tokens} in / {usage.output_tokens} out tokens "
                f"(~${usage.cost_usd:.5f} this call)"
            )

# Rendered after the ask-handling above (not in the earlier sidebar block) so it
# reflects a call that just completed in this same rerun, rather than lagging one
# interaction behind — Streamlit sidebar elements render in call order, independent
# of where in the main-body script flow they're issued.
with st.sidebar:
    st.divider()
    st.metric(
        "Session spend (Claude Haiku)",
        f"${st.session_state.session_cost:.4f} / ${SESSION_BUDGET_LIMIT:.2f} limit",
    )
    st.caption(f"Queries used: {st.session_state.query_count} / {MAX_QUERIES_PER_SESSION}")
