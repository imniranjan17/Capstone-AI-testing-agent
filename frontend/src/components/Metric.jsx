export default function Metric({ label, value }) {
  return (
    <div className="metric">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
    </div>
  );
}

export function MetricRow({ items }) {
  return (
    <div className="metric-row">
      {items.map(([label, value]) => <Metric key={label} label={label} value={value} />)}
    </div>
  );
}
