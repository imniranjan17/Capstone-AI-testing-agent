"""Standalone HTML report. All dynamic content is escaped (inputs may contain markup)."""
from __future__ import annotations

from html import escape as e

_COLORS = {"FAIL": "#b00020", "PASS": "#1b6e2d", "MANUAL_REVIEW": "#8a5a00", "INSUFFICIENT_EVIDENCE": "#555"}


def to_html(report: dict) -> str:
    rows = []
    for f in report["findings"]:
        wcag = "<br>".join(
            f'<a href="{e(w["source_url"], quote=True)}" rel="noopener">SC {e(w["criterion"])} {e(w["title"])} '
            f'(Level {e(w["level"])})</a>' for w in f["wcag"]) or "&mdash;"
        rows.append(
            f'<tr><td style="color:{_COLORS.get(f["verdict"], "#000")};font-weight:bold">{e(f["verdict"])}</td>'
            f'<td>{e(f["rule_id"])}</td><td>{e(f["observation"])}<br><code>{e(f["element"])}</code></td>'
            f'<td>{wcag}</td><td>{e(f["reason"])}<br><em>{e(f["recommendation"])}</em></td></tr>'
        )
    s = report["summary"]
    warnings = "".join(f"<li>{e(w)}</li>" for w in report.get("warnings", []))
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Accessibility review</title>'
        "<style>body{font-family:sans-serif;margin:2rem}table{border-collapse:collapse;width:100%}"
        "td,th{border:1px solid #ccc;padding:.4rem;vertical-align:top}</style></head><body>"
        f'<h1>Accessibility review: {e(report["overall_verdict"])}</h1>'
        f'<p role="note"><strong>Scope:</strong> {e(report["scope"]["limitation"])}</p>'
        f'<p>Failed {s["failed"]}, passed {s["passed"]}, manual review {s["manual_review"]}, '
        f'insufficient evidence {s["insufficient_evidence"]}. Target: {e(report["target_standard"])}. '
        f'Run {e(report["run_id"])}.</p>'
        + (f"<h2>Warnings</h2><ul>{warnings}</ul>" if warnings else "")
        + "<table><caption>Findings</caption><thead><tr><th scope=\"col\">Verdict</th><th scope=\"col\">Rule</th>"
        "<th scope=\"col\">Observation</th><th scope=\"col\">WCAG</th><th scope=\"col\">Reason / fix</th></tr></thead>"
        f'<tbody>{"".join(rows)}</tbody></table></body></html>'
    )
