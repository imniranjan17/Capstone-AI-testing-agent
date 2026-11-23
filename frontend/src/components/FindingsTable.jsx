import { useState } from "react";
import DataTable from "./DataTable.jsx";

const COLS = ["idx", "category", "severity", "rule_id", "message", "selector", "decision", "decision_reason", "review_status"];

function Filter({ label, options, selected, onChange }) {
  return (
    <fieldset className="filter">
      <legend>{label}</legend>
      {options.map((o) => (
        <label key={o}>
          <input
            type="checkbox"
            checked={selected.includes(o)}
            onChange={(e) => onChange(e.target.checked ? [...selected, o] : selected.filter((x) => x !== o))}
          />
          {o}
        </label>
      ))}
    </fieldset>
  );
}

export default function FindingsTable({ findings }) {
  const cats = [...new Set(findings.map((f) => f.category))].sort();
  const decs = [...new Set(findings.map((f) => f.decision))].sort();
  const [selCats, setSelCats] = useState(cats);
  const [selDecs, setSelDecs] = useState(decs);

  if (!findings.length) return <div className="alert success">No findings.</div>;
  const rows = findings.filter((f) => selCats.includes(f.category) && selDecs.includes(f.decision));
  return (
    <>
      <div className="filters">
        <Filter label="Category" options={cats} selected={selCats} onChange={setSelCats} />
        <Filter label="Decision" options={decs} selected={selDecs} onChange={setSelDecs} />
      </div>
      <DataTable
        rows={rows}
        columns={COLS.map((key) => ({
          key,
          render: key === "severity" ? (r) => <span className={`sev ${r.severity}`}>{r.severity}</span> : undefined,
        }))}
      />
    </>
  );
}
