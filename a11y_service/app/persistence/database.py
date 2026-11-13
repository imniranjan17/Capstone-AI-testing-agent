"""SQLite operational store for runs. Stores only the sanitized report, never raw input."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.config import get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, input_type TEXT NOT NULL,
    overall_verdict TEXT NOT NULL, report_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS findings (
    finding_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, rule_id TEXT NOT NULL,
    verdict TEXT NOT NULL, finding_json TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
"""


def _connect() -> sqlite3.Connection:
    path = Path(get_settings().sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    return conn


def save_run(report: dict) -> None:
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?)",
                (report["run_id"], report["created_at"], report["scope"]["input_type"],
                 report["overall_verdict"], json.dumps(report)),
            )
            for f in report["findings"]:
                conn.execute(
                    "INSERT OR REPLACE INTO findings VALUES (?,?,?,?,?)",
                    (f["finding_id"], report["run_id"], f["rule_id"], f["verdict"], json.dumps(f)),
                )
    finally:
        conn.close()


def get_run(run_id: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT report_json FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return json.loads(row[0]) if row else None
    finally:
        conn.close()
