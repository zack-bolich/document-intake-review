"""Ingest Gmail PDF attachments and optionally send a summary email."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.gmail import (  # noqa: E402
    build_gmail_service,
    process_pdf_attachments,
    send_processing_summary,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--send-summary", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if args.send_summary and not settings.gmail_summary_recipient:
        raise SystemExit("Set GMAIL_SUMMARY_RECIPIENT before using --send-summary")
    Base.metadata.create_all(engine)
    service = build_gmail_service(settings.gmail_token_file)
    with SessionLocal() as db:
        summary = process_pdf_attachments(db, service, settings.gmail_query)
    if args.send_summary:
        summary["summary_message_id"] = send_processing_summary(
            service, settings.gmail_summary_recipient, summary
        )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
