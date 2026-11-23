import { useState } from "react";
import { api } from "../api/client.js";
import { useAsync } from "../hooks/useAsync.js";
import Loader from "../components/Loader.jsx";
import ErrorBox from "../components/ErrorBox.jsx";
import DataTable from "../components/DataTable.jsx";
import ReportView from "../components/ReportView.jsx";

export default function HistoryPage() {
  const runs = useAsync(api.listRuns);
  const [picked, setPicked] = useState(null);
  const run = useAsync(() => (picked ? api.getRun(picked) : Promise.resolve(null)), [picked]);

  return (
    <>
      <h1>History</h1>
      {runs.loading && <Loader message="Loading run history" />}
      <ErrorBox message={runs.error} />
      {runs.data && (
        <DataTable rows={runs.data} onRowClick={(r) => setPicked(r.run_id)} empty="No runs yet." />
      )}
      {picked && <p className="muted">Opened run {picked.slice(0, 8)} (click another row to switch)</p>}
      {run.loading && picked && <Loader message="Opening run" />}
      <ErrorBox message={run.error} />
      {run.data && <ReportView report={run.data} />}
    </>
  );
}
