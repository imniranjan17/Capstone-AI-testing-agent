"""Step 9b: Streamlit UI. Run: python -m streamlit run ui/streamlit_app.py"""
import os
from contextlib import contextmanager

import httpx
import pandas as pd
import streamlit as st

API = os.getenv("AGENT_API_URL", "http://localhost:8100")
st.set_page_config(page_title="Web Testing Agent", page_icon="🛡️", layout="wide",
                   initial_sidebar_state="collapsed")

CSS = """
<style>
  [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display:none}
  .block-container {padding-top: 1.2rem; max-width: 1200px}
  header[data-testid="stHeader"] {background: transparent}
  .brand {display:flex; align-items:center; gap:12px; margin-bottom:4px}
  .brand .logo {font-size:26px; font-weight:700; color:#38bdf8; letter-spacing:.3px}
  .brand .tag {color:#94a3b8; font-size:14px}
  [data-testid="stMetric"] {background:#1e293b; border:1px solid #334155; border-radius:12px; padding:14px 18px}
  [data-testid="stMetricValue"] {color:#38bdf8}
  [data-testid="stExpander"] {background:#1e293b; border:1px solid #334155; border-radius:12px}
  [data-testid="stDataFrame"] {border-radius:12px; overflow:hidden}
  .stButton > button {border-radius:8px; font-weight:600}
  h1 {font-weight:700 !important}
  [data-testid="stChatMessage"] {background:#1e293b; border:1px solid #334155; border-radius:12px;
      padding:18px 22px; margin-bottom:16px; letter-spacing:.2px; line-height:1.75}
  [data-testid="stChatMessage"] p {margin-bottom:.7rem}
  [data-testid="stChatMessage"] ul {margin:.2rem 0 1.1rem; padding-left:1.2rem}
  [data-testid="stChatMessage"] li {margin-bottom:.3rem}
  [data-testid="stChatMessage"] code {color:#38bdf8}
  .loader {display:flex; align-items:center; gap:14px; padding:14px 18px; margin:8px 0;
      background:#1e293b; border:1px solid #334155; border-radius:12px; color:#94a3b8; font-size:15px}
  .loader .ring {width:22px; height:22px; border-radius:50%; border:3px solid #334155;
      border-top-color:#38bdf8; animation:spin .8s linear infinite; flex:none}
  .loader .dots span {display:inline-block; width:6px; height:6px; margin-left:3px; border-radius:50%;
      background:#38bdf8; animation:bounce 1.2s ease-in-out infinite}
  .loader .dots span:nth-child(2) {animation-delay:.15s}
  .loader .dots span:nth-child(3) {animation-delay:.3s}
  @keyframes spin {to {transform:rotate(360deg)}}
  @keyframes bounce {0%,80%,100% {opacity:.25; transform:translateY(0)} 40% {opacity:1; transform:translateY(-4px)}}
  hr.nav-sep {border:0; border-top:1px solid #1e293b; margin:6px 0 18px}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@contextmanager
def loader(msg: str = "Loading"):
    """Animated spinner card; removed automatically when the block finishes (even on error)."""
    slot = st.empty()
    slot.markdown(f'<div class="loader"><div class="ring"></div><span>{msg}</span>'
                  '<span class="dots"><span></span><span></span><span></span></span></div>',
                  unsafe_allow_html=True)
    try:
        yield
    finally:
        slot.empty()


def call(method: str, path: str, msg: str = "Loading", **kw):
    try:
        with loader(msg):
            r = httpx.request(method, API + path, timeout=180, **kw)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        st.error(f"{e.response.status_code}: {e.response.text}")
    except httpx.HTTPError as e:
        st.error(f"API not reachable at {API} ({e.__class__.__name__}). Start it with: "
                 "python -m uvicorn app.api:app --port 8100")
    return None


def findings_table(findings: list[dict]):
    if not findings:
        st.success("No findings.")
        return
    df = pd.DataFrame(findings)
    cols = [c for c in ["idx", "category", "severity", "rule_id", "message", "selector", "decision",
                        "decision_reason", "review_status"] if c in df]
    c1, c2 = st.columns(2)
    cats = c1.multiselect("Category", sorted(df.category.unique()), default=sorted(df.category.unique()))
    decs = c2.multiselect("Decision", sorted(df.decision.unique()), default=sorted(df.decision.unique()))
    st.dataframe(df[df.category.isin(cats) & df.decision.isin(decs)][cols], width="stretch", hide_index=True)


def show_report(rep: dict):
    st.subheader(f"Run {rep['run_id'][:8]} — DOM {rep['dom_status']}")
    if rep["dom_status"] == "unchanged" and not rep.get("forced"):
        st.info("DOM unchanged since last snapshot, so no checks ran. Tick 'Force run' to re-check anyway.")
        return
    if rep.get("forced") and rep["dom_status"] == "unchanged":
        st.caption("DOM unchanged since last snapshot; checks were re-run because Force run was ticked.")
    m = st.columns(4)
    m[0].metric("Findings", rep["total"])
    m[1].metric("Auto-suggested", rep.get("by_decision", {}).get("auto_suggest", 0))
    m[2].metric("Needs human", rep.get("by_decision", {}).get("needs_human", 0))
    m[3].metric("High/Critical", sum(rep.get("by_severity", {}).get(k, 0) for k in ("high", "critical")))
    tab1, tab2, tab3 = st.tabs(["Findings", "Suggested patches", "DOM diff"])
    with tab1:
        findings_table(rep["findings"])
    with tab2:
        auto = [f for f in rep["findings"] if f["decision"] == "auto_suggest"]
        for f in auto or []:
            with st.expander(f"{f['rule_id']} — {f.get('selector') or ''}"):
                st.write(f["message"])
                st.code(f.get("suggested_fix") or "", language="html")
        if not auto:
            st.caption("No auto-suggested patches.")
    with tab3:
        st.code(rep.get("diff") or "(baseline or no diff)", language="diff")


PAGES = {"Run": ":material/play_arrow:", "Review queue": ":material/rule:",
         "History": ":material/history:", "Ask (RAG)": ":material/chat:"}

brand, nav = st.columns([2, 3], vertical_alignment="center")
brand.markdown('<div class="brand"><span class="logo">🛡️ Web Testing Agent</span></div>'
               '<div class="brand"><span class="tag">Change-triggered checks · suggest-only fixes</span></div>',
               unsafe_allow_html=True)
with nav:
    st.page_link("pages/audit.py", label="Audit", icon=":material/monitoring:")
    choice = st.segmented_control("Navigation", list(PAGES), default="Run", key="nav",
                                  format_func=lambda p: f"{PAGES[p]} {p}", label_visibility="collapsed")
page = choice or "Run"
st.markdown('<hr class="nav-sep">', unsafe_allow_html=True)

if page == "Run":
    st.title("Run a test")
    mode = st.radio("Input", ["Paste DOM / HTML", "URL"], horizontal=True)
    force = st.checkbox("Force run (even if DOM unchanged)")
    if mode == "Paste DOM / HTML":
        key = st.text_input("Name (snapshot key)", "demo-page")
        html = st.text_area("HTML", height=300)
        body = {"key": key, "html": html, "force": force}
        ready = bool(html.strip())
    else:
        url = st.text_input("URL (only test sites you are authorized to test)", "https://")
        body = {"url": url, "force": force}
        ready = url.startswith(("http://", "https://")) and len(url) > 9
    if st.button("Run", type="primary", disabled=not ready):
        rep = call("POST", "/runs", "Running accessibility, validation, links, security and MCP checks in parallel", json=body)
        if rep:
            st.session_state["report"] = rep
    if "report" in st.session_state:
        show_report(st.session_state["report"])

elif page == "Review queue":
    st.title("Human review queue")
    items = call("GET", "/reviews/pending", "Loading review queue") or []
    st.caption(f"{len(items)} pending")
    for f in items:
        with st.expander(f"[{f['severity']}] {f['rule_id']} — {f['message'][:80]}"):
            st.write(f"**Why human:** {f.get('decision_reason')}")
            if f.get("selector"):
                st.write(f"**Element:** `{f['selector']}`")
            if f.get("evidence"):
                st.code(f["evidence"], language="html")
            fix = st.text_area("Suggested fix (editable)", f.get("suggested_fix") or "", key=f"fix{f['run_id']}{f['idx']}")
            note = st.text_input("Note", key=f"note{f['run_id']}{f['idx']}")
            a, b, _ = st.columns([1, 1, 6])
            for col, status in ((a, "approved"), (b, "rejected")):
                if col.button(status.capitalize(), key=f"{status}{f['run_id']}{f['idx']}"):
                    if call("POST", f"/runs/{f['run_id']}/review", "Saving review",
                            json={"idx": f["idx"], "status": status, "note": note, "final_fix": fix}):
                        st.rerun()

elif page == "Ask (RAG)":
    st.title("Ask about your findings")
    doms = call("GET", "/domains", "Loading domains") or []
    if not doms:
        st.info("No findings yet. Run tests on some pages first.")
    else:
        st.dataframe(pd.DataFrame([{k: d[k] for k in ("domain", "page_count", "total_findings")} for d in doms]),
                     hide_index=True, width="stretch")
        dom = st.selectbox("Domain", ["(all)"] + [d["domain"] for d in doms])
        for q in st.session_state.get("chat", []):
            with st.chat_message("user"):
                st.write(q["q"])
            with st.chat_message("assistant"):
                st.write(q["a"]["answer"])
                st.caption(f"mode: {q['a']['mode']} | retrieval: {q['a']['retrieval']}")
                with st.expander(f"Sources ({len(q['a']['sources'])}): BM25 rank / dense rank / RRF"):
                    cols = ("n", "page", "rule_id", "severity", "sparse_rank", "dense_rank", "rrf_score")
                    st.dataframe(pd.DataFrame([{k: s[k] for k in cols} for s in q["a"]["sources"]]),
                                 hide_index=True, width="stretch")
        question = st.chat_input("e.g. Which pages have broken links? What critical security issues exist?")
        if question:
            with st.chat_message("user"):
                st.write(question)
            with st.chat_message("assistant"):
                a = call("POST", "/ask", "Searching findings and writing an answer",
                         json={"question": question, "domain": None if dom == "(all)" else dom})
            if a:
                st.session_state.setdefault("chat", []).append({"q": question, "a": a})
                st.rerun()

else:
    st.title("History")
    runs = call("GET", "/runs", "Loading run history") or []
    if runs:
        st.dataframe(pd.DataFrame(runs), width="stretch", hide_index=True)
        pick = st.selectbox("Open run", [r["run_id"] for r in runs])
        rep = call("GET", f"/runs/{pick}", "Opening run")
        if rep:
            show_report(rep)
    else:
        st.caption("No runs yet.")
