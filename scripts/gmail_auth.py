"""Perform one-time local Gmail OAuth authorization."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402
from app.gmail import authorize  # noqa: E402


def main() -> None:
    settings = get_settings()
    authorize(settings.gmail_client_file, settings.gmail_token_file)
    print(f"Gmail authorization saved to {settings.gmail_token_file}")


if __name__ == "__main__":
    main()
