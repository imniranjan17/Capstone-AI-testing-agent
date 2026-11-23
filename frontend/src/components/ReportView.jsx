import { MetricRow } from "./Metric.jsx";
import Tabs from "./Tabs.jsx";
import FindingsTable from "./FindingsTable.jsx";

function Patches({ findings }) {
  const auto = findings.filter((f) => f.decision === "auto_suggest");
  if (!auto.length) return <p className="muted">No auto-suggested patches.</p>;
  return auto.map((f, i) => (
    <details key={i} className="card">
      <summary>{f.rule_id} — {f.selector || ""}</summary>
      <p>{f.message}</p>
      <pre>{f.suggested_fix || ""}</pre>
    </details>
  ));
}

// Renders one run report (same shape returned by POST /runs and GET /runs/{id}).
export default function ReportView({ report }) {
  const { run_id, dom_status, forced, total, by_decision = {}, by_severity = {}, findings = [], diff } = report;
  return (
    <section>
      <h2>Run {run_id.slice(0, 8)} — DOM {dom_status}</h2>
      {dom_status === "unchanged" && !forced ? (
        <div className="alert info">
          DOM unchanged since last snapshot, so no checks ran. Tick "Force run" to re-check anyway.
        </div>
      ) : (
        <>
          {forced && dom_status === "unchanged" && (
            <p className="muted">DOM unchanged since last snapshot; checks were re-run because Force run was ticked.</p>
          )}
          <MetricRow
            items={[
              ["Findings", total],
              ["Auto-suggested", by_decision.auto_suggest ?? 0],
              ["Needs human", by_decision.needs_human ?? 0],
              ["High/Critical", (by_severity.high ?? 0) + (by_severity.critical ?? 0)],
            ]}
          />
          <Tabs
            tabs={[
              { label: "Findings", content: <FindingsTable findings={findings} /> },
              { label: "Suggested patches", content: <Patches findings={findings} /> },
              { label: "DOM diff", content: <pre>{diff || "(baseline or no diff)"}</pre> },
            ]}
          />
        </>
      )}
    </section>
  );
}
