import { useState } from "react";
import { api } from "../api/client.js";
import { useAsync } from "../hooks/useAsync.js";
import { useSessionState } from "../hooks/useSessionState.js";
import Loader from "../components/Loader.jsx";
import ErrorBox from "../components/ErrorBox.jsx";
import DataTable from "../components/DataTable.jsx";

const SOURCE_COLS = ["n", "page", "rule_id", "severity", "sparse_rank", "dense_rank", "rrf_score"];
const asCols = (keys) => keys.map((key) => ({ key }));

export default function AskPage() {
  const domains = useAsync(api.domains);
  const [domain, setDomain] = useState("");
  const [chat, setChat] = useSessionState("chat", []);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function send(e) {
    e.preventDefault();
    const q = question.trim();
    if (!q) return;
    setBusy(true);
    setError(null);
    try {
      const a = await api.ask(q, domain || null);
      setChat([...chat, { q, a }]);
      setQuestion("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Ask about your findings</h1>
      {domains.loading && <Loader message="Loading domains" />}
      <ErrorBox message={domains.error} />
      {domains.data?.length === 0 && <div className="alert info">No findings yet. Run tests on some pages first.</div>}
      {domains.data?.length > 0 && (
        <>
          <DataTable rows={domains.data} columns={asCols(["domain", "page_count", "total_findings"])} />
          <label className="field">Domain
            <select value={domain} onChange={(e) => setDomain(e.target.value)}>
              <option value="">(all)</option>
              {domains.data.map((d) => <option key={d.domain}>{d.domain}</option>)}
            </select>
          </label>
          {chat.map((m, i) => (
            <div key={i}>
              <div className="bubble user">{m.q}</div>
              <div className="bubble assistant">
                <div className="answer">{m.a.answer}</div>
                <p className="muted">mode: {m.a.mode} | retrieval: {m.a.retrieval}</p>
                <details>
                  <summary>Sources ({m.a.sources.length}): BM25 rank / dense rank / RRF</summary>
                  <DataTable rows={m.a.sources} columns={asCols(SOURCE_COLS)} />
                </details>
              </div>
            </div>
          ))}
          {busy && <Loader message="Searching findings and writing an answer" />}
          <ErrorBox message={error} />
          <form onSubmit={send} className="chat-input">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. Which pages have broken links? What critical security issues exist?"
            />
            <button className="primary" disabled={busy || !question.trim()}>Ask</button>
          </form>
        </>
      )}
    </>
  );
}
