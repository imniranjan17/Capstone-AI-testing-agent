import { useState } from "react";
import { api } from "../api/client.js";
import { useAsync } from "../hooks/useAsync.js";
import Loader from "../components/Loader.jsx";
import ErrorBox from "../components/ErrorBox.jsx";

function ReviewItem({ f, onDone }) {
  const [fix, setFix] = useState(f.suggested_fix || "");
  const [note, setNote] = useState("");
  const [error, setError] = useState(null);

  async function submit(status) {
    try {
      await api.review(f.run_id, { idx: f.idx, status, note, final_fix: fix });
      onDone();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <details className="card">
      <summary>[{f.severity}] {f.rule_id} — {f.message.slice(0, 80)}</summary>
      <p><b>Why human:</b> {f.decision_reason}</p>
      {f.selector && <p><b>Element:</b> <code>{f.selector}</code></p>}
      {f.evidence && <pre>{f.evidence}</pre>}
      <label className="field">Suggested fix (editable)
        <textarea rows={5} value={fix} onChange={(e) => setFix(e.target.value)} />
      </label>
      <label className="field">Note
        <input value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      <div className="row">
        <button onClick={() => submit("approved")}>Approved</button>
        <button onClick={() => submit("rejected")}>Rejected</button>
      </div>
      <ErrorBox message={error} />
    </details>
  );
}

export default function ReviewPage() {
  const { data, error, loading, reload } = useAsync(api.pendingReviews);
  return (
    <>
      <h1>Human review queue</h1>
      {loading && <Loader message="Loading review queue" />}
      <ErrorBox message={error} />
      {data && <p className="muted">{data.length} pending</p>}
      {data?.map((f) => <ReviewItem key={`${f.run_id}-${f.idx}`} f={f} onDone={reload} />)}
    </>
  );
}
