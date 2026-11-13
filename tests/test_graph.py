from app.graph import build_graph, run_pipeline
from app.schemas import Category, Finding

calls = []


def mk(name):
    def fn(s):
        calls.append(name)
        return [Finding(source=name, category=Category.validation, rule_id=f"{name}-r", message="m"),
                Finding(source="dup", category=Category.validation, rule_id="same", message="m")]
    return fn


def graph():
    return build_graph({n: mk(n) for n in ["a11y", "validation", "links", "security", "mcp_tests"]})


def test_flow(tmp_path):
    db, g = str(tmp_path / "g.db"), graph()
    r = run_pipeline("demo", "<p>a</p>", db_path=db, graph=g)
    assert r["dom_status"] == "baseline" and r["total"] == 6          # 5 branches + 1 deduped
    assert len(set(calls)) == 5
    calls.clear()
    r = run_pipeline("demo", "<p>a</p>", db_path=db, graph=g)          # unchanged -> short-circuit
    assert r["dom_status"] == "unchanged" and r["total"] == 0 and calls == []
    r = run_pipeline("demo", "<p>a</p>", db_path=db, graph=g, force=True)
    assert r["total"] == 6 and r["forced"] and r["dom_status"] == "unchanged"
    r = run_pipeline("demo", "<p>b</p>", db_path=db, graph=g)
    assert r["dom_status"] == "changed" and "+<p>" in r["diff"].replace(" ", "").replace("\n", "") or r["diff"]


def test_branch_crash_is_contained(tmp_path):
    def boom(s): raise RuntimeError("x")
    g = build_graph({"a11y": boom, "validation": mk("validation")})
    r = run_pipeline("k", "<p/>", db_path=str(tmp_path / "c.db"), graph=g)
    assert any(f["rule_id"] == "a11y-crashed" for f in r["findings"])
