"""RAG prompt construction + Claude Haiku call for cited answer generation.

Design note (see step 3 / README "Known limitations"): our local embedding
model sometimes ranks prose files (README/HISTORY/CHANGELOG) above the
actual source code that answers a question, because changelog entries often
repeat query keywords more literally than the code itself does. Rather than
try to fix this at the retrieval layer, the system prompt below tells Haiku
to prefer source-code chunks over non-code chunks when both are present in
the retrieved context, and to fall back to non-code chunks only when no
relevant code chunk was retrieved.
"""

import anthropic
from dotenv import load_dotenv

from .index import query_repo

load_dotenv()  # picks up ANTHROPIC_API_KEY from a local .env file, if present

MODEL = "claude-haiku-4-5-20251001"  # pinned explicitly — never fall back to Sonnet/Opus
MAX_TOKENS = 1024
N_RESULTS = 5

# Haiku 4.5 pricing (input / output per 1M tokens) — used only for cost logging below.
INPUT_PRICE_PER_MTOK = 1.00
OUTPUT_PRICE_PER_MTOK = 5.00

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".c", ".cpp",
    ".h", ".hpp", ".rb", ".php", ".cs", ".swift", ".kt", ".scala", ".sh",
}

SYSTEM_PROMPT = """You are a code Q&A assistant for a GitHub repository. Answer questions using \
ONLY the retrieved chunks provided as context — do not rely on outside knowledge of the repo.

Rules:
1. Base your answer strictly on the provided chunks. If they don't contain enough information to \
answer confidently, say so instead of guessing.
2. The retrieved context may mix actual source code with non-code files (README, HISTORY, \
CHANGELOG, docs). PRIORITIZE source code as the basis for your answer: prose files can describe \
behavior inaccurately or out of date, while the code is ground truth. Only lean on a non-code chunk \
when no relevant source-code chunk was retrieved.
3. Every claim must be backed by a citation in the exact form `file_path:start_line-end_line`, taken \
directly from the chunk headers you were given. Never invent a citation or line number.
4. Be concise: answer directly, then list the citations you relied on.
"""

# Running totals for this process — printed after every call so spend against
# the project's fixed API budget stays visible.
_cumulative_usage = {"input_tokens": 0, "output_tokens": 0}


def _format_context(results: dict) -> str:
    metadatas = results["metadatas"][0]
    documents = results["documents"][0]
    blocks = []
    for meta, doc in zip(metadatas, documents):
        loc = f"{meta['file_path']}:{meta['start_line']}-{meta['end_line']}"
        is_code = any(meta["file_path"].endswith(ext) for ext in CODE_EXTENSIONS)
        kind = meta["chunk_type"] if is_code else "non-code"
        label = kind + (f" {meta['name']}" if meta["name"] else "")
        blocks.append(f"### {loc} ({label})\n```\n{doc}\n```")
    return "\n\n".join(blocks)


def answer_question(repo_name: str, question: str, n_results: int = N_RESULTS) -> str:
    """Retrieve relevant chunks and ask Claude Haiku to answer with citations."""
    results = query_repo(repo_name, question, n_results=n_results)
    context = _format_context(results)

    client = anthropic.Anthropic()
    user_message = (
        f"Retrieved context from the `{repo_name}` repository:\n\n{context}\n\n"
        f"Question: {question}"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    _log_usage(response.usage)

    return "".join(block.text for block in response.content if block.type == "text")


def _log_usage(usage) -> None:
    _cumulative_usage["input_tokens"] += usage.input_tokens
    _cumulative_usage["output_tokens"] += usage.output_tokens

    call_cost = (
        usage.input_tokens * INPUT_PRICE_PER_MTOK / 1_000_000
        + usage.output_tokens * OUTPUT_PRICE_PER_MTOK / 1_000_000
    )
    cumulative_cost = (
        _cumulative_usage["input_tokens"] * INPUT_PRICE_PER_MTOK / 1_000_000
        + _cumulative_usage["output_tokens"] * OUTPUT_PRICE_PER_MTOK / 1_000_000
    )
    print(
        f"[usage] this call: {usage.input_tokens} in / {usage.output_tokens} out "
        f"(~${call_cost:.5f}) | session total: {_cumulative_usage['input_tokens']} in / "
        f"{_cumulative_usage['output_tokens']} out (~${cumulative_cost:.5f})"
    )
