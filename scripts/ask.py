"""Ask a question against an already-built index and get a cited answer from Claude Haiku.

Run from the repo root (after scripts/build_index.py), with ANTHROPIC_API_KEY set
in your environment or in a .env file at the repo root:

    python scripts/ask.py [repo_name] "<question>"

With no question arg, defaults to a question about HTTP redirect handling — chosen
deliberately because step 3's manual retrieval check found this exact topic surfaces
HISTORY.md/docs chunks above the actual SessionRedirectMixin code, making it a good
test of the "prioritize source code over docs" instruction in the system prompt.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from codebase_rag.generate import answer_question

DEFAULT_REPO_NAME = "requests"
DEFAULT_QUESTION = "How does the library handle HTTP redirects, and what class implements it?"


def main() -> None:
    repo_name = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REPO_NAME
    question = " ".join(sys.argv[2:]) or DEFAULT_QUESTION

    print(f"Repo: {repo_name}")
    print(f"Question: {question}\n")

    answer = answer_question(repo_name, question)
    print("\n--- Answer ---")
    print(answer)


if __name__ == "__main__":
    main()
