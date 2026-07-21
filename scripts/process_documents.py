"""Document intake pipeline runner.

Run:
  python scripts/process_documents.py --run-once
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from parser import parse_file_bytes, parse_text
from categorizer import categorize


@dataclass
class Config:
    input_dir: Path
    output_dir: Path
    state_dir: Path
    clean_file: str = "clean_records.csv"
    dead_file: str = "dead_letter.csv"
    processed_file: str = "processed.json"


def _load_env(path: Path | None = None) -> Config:
    values = os.environ.copy()
    if path and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line or "=" not in line or line.startswith("#"):
                continue
            key, value = line.split("=", 1)
            values.setdefault(key.strip(), value.strip())
    return Config(
        input_dir=Path(values.get("INPUT_DIR", "sample-data/inbox")),
        output_dir=Path(values.get("OUTPUT_DIR", "results")),
        state_dir=Path(values.get("STATE_DIR", "state")),
        clean_file=values.get("CLEAN_FILE", "clean_records.csv"),
        dead_file=values.get("DEAD_LETTER_FILE", "dead_letter.csv"),
        processed_file=values.get("PROCESSED_FILE", "processed.json"),
    )


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _read_manifest(state_path: Path) -> set[str]:
    if not state_path.exists():
        return set()
    try:
        return set(json.loads(state_path.read_text(encoding="utf-8")))
    except Exception:
        return set()


def _write_manifest(state_path: Path, processed: set[str]) -> None:
    state_path.write_text(
        json.dumps(sorted(processed), indent=2),
        encoding="utf-8",
    )


def _iter_docs(input_dir: Path) -> Iterable[Path]:
    if not input_dir.exists():
        return []
    return [p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in {".txt", ".json", ".csv", ".pdf"}]


def _load_csv(path: Path, header: list[str]) -> list[list[str]]:
    if not path.exists():
        return []
    out: list[list[str]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out.append([row.get(col, "") for col in header])
    return out


def _append_row(file_path: Path, header: list[str], row: dict[str, str]) -> None:
    exists = file_path.exists()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def _process_single(path: Path, output_dir: Path, processed: set[str], row_seen: set[str]) -> tuple[bool, list[str]]:
    digest = _hash_file(path)
    if digest in processed or digest in row_seen:
        return False, []

    raw = path.read_bytes()
    text = parse_file_bytes(path.name, raw)
    if not text.strip():
        return False, [f"cannot_parse_text:{path.name}"]

    fields, issues = parse_text(text)
    doc_type, tags = categorize(text, metadata={"doc_type": ""})
    now = datetime.utcnow().isoformat() + "Z"

    row = {
        "filename": path.name,
        "document_type": doc_type,
        "document_number": fields["document_number"],
        "vendor": fields["vendor"],
        "amount": fields["amount"],
        "currency": fields["currency"] or "USD",
        "date": fields["date"],
        "tags": ";".join(tags),
        "processed_at": now,
    }

    clean_header = ["filename", "document_type", "document_number", "vendor", "amount", "currency", "date", "tags", "processed_at"]
    dead_header = ["filename", "error", "raw_text_excerpt", "processed_at"]
    clean_path = output_dir / "clean_records.csv"
    dead_path = output_dir / "dead_letter.csv"

    if issues:
        dead_row = {
            "filename": path.name,
            "error": "|".join(issues),
            "raw_text_excerpt": text[:500],
            "processed_at": now,
        }
        _append_row(dead_path, dead_header, dead_row)
    else:
        _append_row(clean_path, clean_header, row)

    row_seen.add(digest)
    return True, []


def run_once(config: Config) -> None:
    output_dir = config.output_dir
    state_file = config.state_dir / config.processed_file
    output_dir.mkdir(parents=True, exist_ok=True)
    config.state_dir.mkdir(parents=True, exist_ok=True)

    processed = _read_manifest(state_file)
    row_seen: set[str] = set()

    files = list(_iter_docs(config.input_dir))
    if not files:
        print("No files found in inbox")
        return

    for path in files:
        _process_single(path, output_dir, processed, row_seen)

    processed.update(row_seen)
    _write_manifest(state_file, processed)

    print(f"Processed files: {len(row_seen)}; total unique processed: {len(processed)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-once", action="store_true", help="Run single scan (no continuous watcher)")
    args = parser.parse_args()

    env_path = Path(".env")
    config = _load_env(env_path if env_path.exists() else None)
    if args.run_once:
        run_once(config)
        return 0
    print("Only --run-once is implemented in this version.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
