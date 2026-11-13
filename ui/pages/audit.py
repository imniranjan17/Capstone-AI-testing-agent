"""Observability dashboard, served by Streamlit multipage at /audit. Reads /audit/* endpoints of the agent API."""
import os

import httpx
import pandas as pd
import streamlit as st

API = os.getenv("AGENT_API_URL", "http://localhost:8100")
st.set_page_config(page_title="Audit · Web Testing Agent", page_icon="📊", layout="wide",
                   initial_sidebar_state="collapsed")
st.markdown("""<style>
  [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display:none}
  .block-container {padding-top: 1.2rem; max-width: 1300px}
  [data-testid="stMetric"] {background:#1e293b; border:1px solid #334155; border-radius:12px; padding:14px 18px}
  [data-testid="stMetricValue"] {color:#38bdf8}
</style>""", unsafe_allow_html=True)


def get(path: str):
    try:
        r = httpx.get(API + path, timeout=30)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        st.error(f"API not reachable / failed at {API}{path} ({e.__class__.__name__}). "
                 "Start it with: python -m uvicorn app.api:app --port 8100")
        return None


top = st.columns([6, 1])
top[0].title("📊 Pipeline audit & observability")
top[1].page_link("streamlit_app.py", label="← App")
if top[1].button("Refresh"):
    st.rerun()

ov, contracts = get("/audit/overview"), get("/audit/contracts")
if not ov or contracts is None:
    st.stop()

tab_health, tab_nodes, tab_llm, tab_contracts, tab_traces = st.tabs(
    ["Health", "Nodes (spans)", "LLM / token spend", "I/O contracts", "Trace explorer"])

r, t = ov["runs"], ov["llm_totals"]
with tab_health:
    st.caption("Last 500 runs. Spans are recorded for every graph node; unchanged DOMs skip the branches.")
    c = st.columns(6)
    c[0].metric("Runs", r["runs"])
    c[1].metric("Skipped (DOM unchanged)", r["unchanged_skipped"])
    c[2].metric("Failed runs", r["errors"])
    c[3].metric("Avg latency", f"{r['avg_ms']:.0f} ms")
    c[4].metric("p95 latency", f"{r['p95_ms']:.0f} ms")
    c[5].metric("Avg findings / run", r["avg_findings"])
    bad = [n for n in ov["nodes"] if n["errors"] or n["degraded"] or n["contract_violations"]]
    if bad:
        st.warning("Attention: " + "; ".join(
            f"**{n['node']}** (errors {n['errors']}, degraded {n['degraded']}, contract violations {n['contract_violations']})"
            for n in bad))
    else:
        st.success("All nodes healthy: no errors, degradations or contract violations.")
    if ov["recent_traces"]:
        df = pd.DataFrame(ov["recent_traces"])
        st.subheader("Run latency (ms), oldest → newest")
        st.line_chart(df.iloc[::-1].reset_index(drop=True)["duration_ms"])

with tab_nodes:
    if ov["nodes"]:
        df = pd.DataFrame(ov["nodes"])
        st.dataframe(df[["node", "kind", "calls", "errors", "degraded", "error_rate", "contract_violations",
                         "avg_ms", "p95_ms", "max_ms", "findings"]], hide_index=True, width="stretch")
        st.subheader("Avg duration by node (ms): parallel branches overlap, so run time ≈ slowest branch")
        st.bar_chart(df.set_index("node")["avg_ms"])
        st.caption("degraded = dependency unavailable (e.g. a11y service down). errors = branch crashed.")
    else:
        st.info("No spans yet. Run a test first.")

with tab_llm:
    c = st.columns(5)
    c[0].metric("LLM calls", t["calls"])
    c[1].metric("Input tokens", f"{t['prompt_tokens']:,}")
    c[2].metric("Output tokens", f"{t['completion_tokens']:,}")
    c[3].metric("Est. spend", f"${t['cost_usd']:.4f}")
    c[4].metric("Est. $ / run", f"${t['cost_per_run_usd']:.5f}")
    p = ov["pricing"]
    st.caption(f"Model `{p['model']}` · ${p['input_usd_per_mtok']}/M input · ${p['output_usd_per_mtok']}/M output "
               "(set LLM_INPUT_USD_PER_MTOK / LLM_OUTPUT_USD_PER_MTOK in .env). Prompts and completions are never stored.")
    if ov["llm"]:
        st.dataframe(pd.DataFrame(ov["llm"]), hide_index=True, width="stretch")
        st.bar_chart(pd.DataFrame(ov["llm"]).set_index("component")[["prompt_tokens", "completion_tokens"]])
        calls = pd.DataFrame(ov["recent_llm_calls"])
        st.subheader("Recent calls")
        st.dataframe(calls, hide_index=True, width="stretch")
    else:
        st.info("No LLM calls recorded. Without GROQ_API_KEY the patch drafter and RAG answerer use deterministic "
                "fallbacks, so token spend is zero.")

with tab_contracts:
    st.caption("Declared contract per node/agent. Output contracts are checked at runtime on every span.")
    rows = [{"node": k, "kind": v["kind"], "purpose": v["purpose"],
             "input": "; ".join(f"{a}: {b}" for a, b in v["input"].items()),
             "output": "; ".join(f"{a}: {b}" for a, b in v["output"].items())} for k, v in contracts.items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.subheader("Recent contract violations")
    if ov["contract_violations"]:
        st.dataframe(pd.DataFrame([{**v, "violations": "; ".join(v["violations"])} for v in ov["contract_violations"]]),
                     hide_index=True, width="stretch")
    else:
        st.success("None.")

with tab_traces:
    if ov["recent_traces"]:
        df = pd.DataFrame(ov["recent_traces"])
        st.dataframe(df, hide_index=True, width="stretch")
        pick = st.selectbox("Open trace", df["run_id"])
        d = get(f"/audit/traces/{pick}")
        if d:
            st.write(f"**{d['key']}** · DOM `{d['dom_status']}` · {d['duration_ms']:.0f} ms · {d['total_findings']} findings"
                     + (f" · error: {d['error']}" if d["error"] else ""))
            sp = pd.DataFrame(d["spans"])
            if not sp.empty:
                sp["input"], sp["output"] = sp["input"].astype(str), sp["output"].astype(str)
                sp["violations"] = sp["violations"].apply(lambda v: "; ".join(v))
                st.dataframe(sp[["node", "status", "duration_ms", "input", "output", "contract_ok", "violations", "error"]],
                             hide_index=True, width="stretch")
            if d["llm_calls"]:
                st.dataframe(pd.DataFrame(d["llm_calls"]), hide_index=True, width="stretch")
    else:
        st.info("No traces yet.")
