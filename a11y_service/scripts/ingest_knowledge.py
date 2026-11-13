"""Deterministic ingestion of local knowledge files.

Usage: python scripts/ingest_knowledge.py [directory] [--no-dense]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.routes_knowledge import rebuild_indexes  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.knowledge import loader  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs="?", default=get_settings().knowledge_dir)
    parser.add_argument("--no-dense", action="store_true", help="skip embedding/Qdrant indexing")
    args = parser.parse_args()
    chunks, errors = loader.ingest_paths(loader.discover(Path(args.directory)))
    print(f"Ingested {len(chunks)} chunks from {args.directory}")
    for err in errors:
        print(f"REJECTED {err}")
    print(rebuild_indexes(rebuild_dense=not args.no_dense))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
