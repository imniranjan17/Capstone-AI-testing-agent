import { useState } from "react";
import { api } from "../api/client.js";
import { useAsync } from "../hooks/useAsync.js";
import Loader from "../components/Loader.jsx";
import ErrorBox from "../components/ErrorBox.jsx";
import DataTable from "../components/DataTable.jsx";
import Tabs from "../components/Tabs.jsx";
import { MetricRow } from "../components/Metric.jsx";
import { BarChart, LineChart } from "../components/Charts.jsx";

const asCols = (keys) => keys.map((key) => ({ key }));
const NODE_COLS = asCols(["node", "kind", "calls", "errors", "degraded", "error_rate", "contract_violations", "avg_ms", "p95_ms", "max_ms", "findings"]);
const SPAN_COLS = asCols(["node", "status", "duration_ms", "input", "output", "contract_ok", "violations", "error"]);

function Health({ ov }) {
  const r = ov.runs;
  const bad = ov.nodes.filter((n) => n.errors || n.degraded || n.contract_violations);
  return (
    <>
      <p className="muted">Last 500 runs. Spans are recorded for every graph node; unchanged DOMs skip the branches.</p>
      <MetricRow items={[
        ["Runs", r.runs], ["Skipped (DOM unchanged)", r.unchanged_skipped], ["Failed runs", r.errors],
        ["Avg latency", `${r.avg_ms.toFixed(0)} ms`], ["p95 latency", `${r.p95_ms.toFixed(0)} ms`],
        ["Avg findings / run", r.avg_findings],
      ]} />
      {bad.length ? (
        <div className="alert warn">
          Attention: {bad.map((n) => `${n.node} (errors ${n.errors}, degraded ${n.degraded}, contract violations ${n.contract_violations})`).join("; ")}
        </div>
      ) : (
        <div className="alert success">All nodes healthy: no errors, degradations or contract violations.</div>
      )}
      {ov.recent_traces.length > 0 && (
        <>
          <h3>Run latency (ms), oldest → newest</h3>
          <LineChart values={[...ov.recent_traces].reverse().map((t) => t.duration_ms)} />
        </>
      )}
    </>
  );
}

function Nodes({ ov }) {
  if (!ov.nodes.length) return <div className="alert info">No spans yet. Run a test first.</div>;
  return (
    <>
      <DataTable rows={ov.nodes} columns={NODE_COLS} />
      <h3>Avg duration by node (ms): parallel branches overlap, so run time ≈ slowest branch</h3>
      <BarChart data={ov.nodes.map((n) => ({ label: n.node, value: n.avg_ms }))} />
      <p className="muted">degraded = dependency unavailable (e.g. a11y service down). errors = branch crashed.</p>
    </>
  );
}

function Llm({ ov }) {
  const t = ov.llm_totals, p = ov.pricing;
  return (
    <>
      <MetricRow items={[
        ["LLM calls", t.calls], ["Input tokens", t.prompt_tokens.toLocaleString()],
        ["Output tokens", t.completion_tokens.toLocaleString()], ["Est. spend", `$${t.cost_usd.toFixed(4)}`],
        ["Est. $ / run", `$${t.cost_per_run_usd.toFixed(5)}`],
      ]} />
      <p className="muted">
        Model <code>{p.model}</code> · ${p.input_usd_per_mtok}/M input · ${p.output_usd_per_mtok}/M output. Prompts and completions are never stored.
      </p>
      {ov.llm.length ? (
        <>
          <DataTable rows={ov.llm} />
          <h3>Recent calls</h3>
          <DataTable rows={ov.recent_llm_calls} />
        </>
      ) : (
        <div className="alert info">
          No LLM calls recorded. Without GROQ_API_KEY the patch drafter and RAG answerer use deterministic fallbacks, so token spend is zero.
        </div>
      )}
    </>
  );
}

function Contracts({ ov, contracts }) {
  const join = (o) => Object.entries(o).map(([a, b]) => `${a}: ${b}`).join("; ");
  const rows = Object.entries(contracts).map(([node, v]) => ({
    node, kind: v.kind, purpose: v.purpose, input: join(v.input), output: join(v.output),
  }));
  return (
    <>
      <p className="muted">Declared contract per node/agent. Output contracts are checked at runtime on every span.</p>
      <DataTable rows={rows} />
      <h3>Recent contract violations</h3>
      {ov.contract_violations.length
        ? <DataTable rows={ov.contract_violations.map((v) => ({ ...v, violations: v.violations.join("; ") }))} />
        : <div className="alert success">None.</div>}
    </>
  );
}

function Traces({ ov }) {
  const [picked, setPicked] = useState(null);
  const trace = useAsync(() => (picked ? api.auditTrace(picked) : Promise.resolve(null)), [picked]);
  if (!ov.recent_traces.length) return <div className="alert info">No traces yet.</div>;
  const d = trace.data;
  return (
    <>
      <DataTable rows={ov.recent_traces} onRowClick={(r) => setPicked(r.run_id)} />
      {trace.loading && picked && <Loader message="Opening trace" />}
      <ErrorBox message={trace.error} />
      {d && (
        <>
          <p>
            <b>{d.key}</b> · DOM <code>{d.dom_status}</code> · {d.duration_ms.toFixed(0)} ms · {d.total_findings} findings
            {d.error ? ` · error: ${d.error}` : ""}
          </p>
          <DataTable rows={d.spans.map((s) => ({ ...s, violations: s.violations.join("; ") }))} columns={SPAN_COLS} />
          {d.llm_calls.length > 0 && <DataTable rows={d.llm_calls} />}
        </>
      )}
    </>
  );
}

export default function AuditPage() {
  const ov = useAsync(api.auditOverview);
  const contracts = useAsync(api.auditContracts);
  return (
    <>
      <div className="row between">
        <h1>📊 Pipeline audit &amp; observability</h1>
        <button onClick={() => { ov.reload(); contracts.reload(); }}>Refresh</button>
      </div>
      {(ov.loading || contracts.loading) && <Loader message="Loading audit data" />}
      <ErrorBox message={ov.error || contracts.error} />
      {ov.data && contracts.data && (
        <Tabs tabs={[
          { label: "Health", content: <Health ov={ov.data} /> },
          { label: "Nodes (spans)", content: <Nodes ov={ov.data} /> },
          { label: "LLM / token spend", content: <Llm ov={ov.data} /> },
          { label: "I/O contracts", content: <Contracts ov={ov.data} contracts={contracts.data} /> },
          { label: "Trace explorer", content: <Traces ov={ov.data} /> },
        ]} />
      )}
    </>
  );
}
