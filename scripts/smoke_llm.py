from pathlib import Path
import sys

# Allow direct script execution without setting PYTHONPATH manually.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from researchpilot.llm.openai_client import chat_completion


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print('Usage: python scripts/smoke_llm.py "hello"', file=sys.stderr)
        return 1

    user_text = " ".join(argv[1:]).strip()
    if not user_text:
        print("Error: message is empty", file=sys.stderr)
        return 1

    try:
        result = chat_completion(
            messages=[{"role": "user", "content": user_text}],
        )
        print(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
