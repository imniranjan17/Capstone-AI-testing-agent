from app.snapshot import detect_change

A = "<html><body><h1>Hi</h1><script>var t=1</script></body></html>"
A2 = "<html><body><h1>Hi</h1><script>var t=2</script><!-- c --></body></html>"  # only volatile changes
B = "<html><body><h1>Hi</h1><img src='x.png'></body></html>"


def test_flow(tmp_path):
    db = str(tmp_path / "t.db")
    assert detect_change("demo", A, db).status == "baseline"
    assert detect_change("demo", A2, db).status == "unchanged"
    r = detect_change("demo", B, db)
    assert r.status == "changed" and "+" in r.diff and "img" in r.diff
    assert detect_change("demo", B, db).status == "unchanged"
