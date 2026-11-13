"""Rebuild the dense (Qdrant) index from the stored chunks. Usage: python scripts/build_indexes.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.routes_knowledge import rebuild_indexes  # noqa: E402

if __name__ == "__main__":
    print(rebuild_indexes(rebuild_dense=True))
