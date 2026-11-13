"""End-to-end demo: baseline -> unchanged -> changed DOM -> findings -> decisions -> human review.

Usage: python scripts/demo.py [--db data/demo.db]
(Start a11y_service on :8000 first if you want real accessibility findings.)
"""
import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
logging.disable(logging.INFO)

from app import store  # noqa: E402
from app.graph import run_pipeline  # noqa: E402

DEMO = Path(__file__).resolve().parent.parent / "demo"


def show(title: str, rep: dict) -> None:
    print(f"\n=== {title}: DOM {rep['dom_status']} | findings {rep['total']} | {rep.get('by_decision', {})}")
    for f in rep["findings"]:
        print(f"  [{f['severity']:<8}] {f['decision']:<12} {f['rule_id']:<26} {f['message'][:60]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/demo.db")
    db = ap.parse_args().db
    if os.path.exists(db):
        os.remove(db)   # fresh demo
    v1 = (DEMO / "page_v1.html").read_text(encoding="utf-8")
    v2 = (DEMO / "page_v2.html").read_text(encoding="utf-8")

    show("1. baseline (clean page)", run_pipeline("demo-shop", v1, db_path=db))
    show("2. same DOM again", run_pipeline("demo-shop", v1, db_path=db))
    rep = run_pipeline("demo-shop", v2, db_path=db)
    show("3. DOM changed (defects introduced)", rep)
    print("\n--- DOM diff (first 12 lines) ---")
    print("\n".join(rep["diff"].splitlines()[:12]))

    pend = store.pending_reviews(rep["run_id"], db)
    print(f"\n=== 4. human review queue: {len(pend)} pending")
    if pend:
        p = pend[0]
        r = store.review(rep["run_id"], p["idx"], "approved", "demo approval", db_path=db)
        print(f"  approved: {r['rule_id']} ({p['decision_reason']})")
        print(f"  remaining pending: {len(store.pending_reviews(rep['run_id'], db))}")
    print("\nSuggested patches (auto):")
    for f in rep["findings"]:
        if f["decision"] == "auto_suggest":
            print(f"  - {f['rule_id']}: {f['suggested_fix'].splitlines()[0]}")


if __name__ == "__main__":
    main()
