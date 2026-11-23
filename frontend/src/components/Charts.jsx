// Tiny dependency-free charts for the audit dashboard.
export function BarChart({ data, unit = "" }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="bars">
      {data.map((d) => (
        <div className="bar-row" key={d.label}>
          <span className="bar-label">{d.label}</span>
          <div className="bar-track"><div className="bar-fill" style={{ width: `${(d.value / max) * 100}%` }} /></div>
          <span className="bar-value">{d.value}{unit}</span>
        </div>
      ))}
    </div>
  );
}

export function LineChart({ values }) {
  if (values.length < 2) return <p className="muted">Not enough runs to chart.</p>;
  const w = 600, h = 140, max = Math.max(...values, 1);
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * w},${h - (v / max) * (h - 10) - 5}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="line-chart" preserveAspectRatio="none">
      <polyline points={pts} fill="none" stroke="#38bdf8" strokeWidth="2" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
