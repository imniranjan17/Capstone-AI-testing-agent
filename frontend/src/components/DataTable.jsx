// rows: array of objects. columns: optional [{ key, label?, render? }]; defaults to all keys of row 0.
export default function DataTable({ rows, columns, onRowClick, empty = "No data." }) {
  if (!rows?.length) return <p className="muted">{empty}</p>;
  const cols = columns ?? Object.keys(rows[0]).map((key) => ({ key }));
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{cols.map((c) => <th key={c.key}>{c.label ?? c.key}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={onRowClick ? "clickable" : ""} onClick={() => onRowClick?.(r)}>
              {cols.map((c) => (
                <td key={c.key}>{c.render ? c.render(r) : format(r[c.key])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function format(v) {
  if (v === null || v === undefined) return "";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
