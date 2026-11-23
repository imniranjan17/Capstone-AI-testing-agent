import { useState } from "react";
import { api } from "../api/client.js";
import { useSessionState } from "../hooks/useSessionState.js";
import Loader from "../components/Loader.jsx";
import ErrorBox from "../components/ErrorBox.jsx";
import ReportView from "../components/ReportView.jsx";

export default function RunPage() {
  const [mode, setMode] = useState("html");
  const [force, setForce] = useState(false);
  const [key, setKey] = useState("demo-page");
  const [html, setHtml] = useState("");
  const [url, setUrl] = useState("https://");
  const [report, setReport] = useSessionState("report", null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const ready = mode === "html" ? html.trim() !== "" : /^https?:\/\/.{2,}/i.test(url);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      const body = mode === "html" ? { key, html, force } : { url, force };
      setReport(await api.createRun(body));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Run a test</h1>
      <div className="row">
        <label><input type="radio" checked={mode === "html"} onChange={() => setMode("html")} /> Paste DOM / HTML</label>
        <label><input type="radio" checked={mode === "url"} onChange={() => setMode("url")} /> URL</label>
      </div>
      <label className="row">
        <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} />
        Force run (even if DOM unchanged)
      </label>
      {mode === "html" ? (
        <>
          <label className="field">Name (snapshot key)
            <input value={key} onChange={(e) => setKey(e.target.value)} />
          </label>
          <label className="field">HTML
            <textarea rows={12} value={html} onChange={(e) => setHtml(e.target.value)} />
          </label>
        </>
      ) : (
        <label className="field">URL (only test sites you are authorized to test)
          <input value={url} onChange={(e) => setUrl(e.target.value)} />
        </label>
      )}
      <button className="primary" disabled={!ready || busy} onClick={run}>Run</button>
      {busy && <Loader message="Running accessibility, validation, links, security and MCP checks in parallel" />}
      <ErrorBox message={error} />
      {report && !busy && <ReportView report={report} />}
    </>
  );
}
