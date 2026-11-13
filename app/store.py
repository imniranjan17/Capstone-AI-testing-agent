"""Step 8: run history + human-in-the-loop review queue (SQLite)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.config import settings

VALID_REVIEW = {"approved", "rejected"}


def _conn(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or settings.db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, key TEXT, dom_status TEXT,
            total INTEGER, summary TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS findings (run_id TEXT, idx INTEGER, data TEXT, review_status TEXT,
            note TEXT DEFAULT '', final_fix TEXT, reviewed_at TEXT, PRIMARY KEY (run_id, idx));
    """)
    return c


def save_run(report: dict, db_path: str | None = None) -> None:
    findings = report.get("findings", [])
    summary = {k: v for k, v in report.items() if k != "findings"}
    with _conn(db_path) as c:
        c.execute("INSERT OR REPLACE INTO runs(run_id, key, dom_status, total, summary) VALUES (?,?,?,?,?)",
                  (report["run_id"], report["key"], report["dom_status"], report.get("total", len(findings)),
                   json.dumps(summary)))
        c.execute("DELETE FROM findings WHERE run_id=?", (report["run_id"],))
        c.executemany("INSERT INTO findings(run_id, idx, data, review_status) VALUES (?,?,?,?)",
                      [(report["run_id"], i, json.dumps(f), f.get("review_status", "n/a")) for i, f in enumerate(findings)])


def _finding(row: sqlite3.Row) -> dict:
    f = json.loads(row["data"])
    f.update(idx=row["idx"], run_id=row["run_id"], review_status=row["review_status"],
             note=row["note"], final_fix=row["final_fix"])
    return f


def get_run(run_id: str, db_path: str | None = None) -> dict | None:
    with _conn(db_path) as c:
        r = c.execute("SELECT summary FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if r is None:
            return None
        rep = json.loads(r["summary"])
        rep["findings"] = [_finding(x) for x in c.execute(
            "SELECT * FROM findings WHERE run_id=? ORDER BY idx", (run_id,))]
        return rep


def list_runs(key: str | None = None, limit: int = 50, db_path: str | None = None) -> list[dict]:
    q, args = "SELECT run_id, key, dom_status, total, created FROM runs", ()
    if key:
        q, args = q + " WHERE key=?", (key,)
    with _conn(db_path) as c:
        return [dict(r) for r in c.execute(q + " ORDER BY created DESC, rowid DESC LIMIT ?", (*args, limit))]


def pending_reviews(run_id: str | None = None, db_path: str | None = None) -> list[dict]:
    q, args = "SELECT * FROM findings WHERE review_status='pending'", ()
    if run_id:
        q, args = q + " AND run_id=?", (run_id,)
    with _conn(db_path) as c:
        return [_finding(r) for r in c.execute(q + " ORDER BY run_id, idx", args)]


def review(run_id: str, idx: int, status: str, note: str = "", final_fix: str | None = None,
           db_path: str | None = None) -> dict:
    """Human approve/reject. final_fix lets the reviewer edit the suggested patch."""
    if status not in VALID_REVIEW:
        raise ValueError(f"status must be one of {sorted(VALID_REVIEW)}")
    with _conn(db_path) as c:
        row = c.execute("SELECT * FROM findings WHERE run_id=? AND idx=?", (run_id, idx)).fetchone()
        if row is None:
            raise KeyError(f"finding {run_id}#{idx} not found")
        if row["review_status"] != "pending":
            raise ValueError(f"finding is '{row['review_status']}', only pending findings can be reviewed")
        c.execute("UPDATE findings SET review_status=?, note=?, final_fix=?, reviewed_at=CURRENT_TIMESTAMP "
                  "WHERE run_id=? AND idx=?", (status, note, final_fix, run_id, idx))
        return _finding(c.execute("SELECT * FROM findings WHERE run_id=? AND idx=?", (run_id, idx)).fetchone())
