// Single place that talks to the FastAPI service. Pages never call fetch directly.
const BASE = import.meta.env.VITE_API_URL ?? "";

export class ApiError extends Error {}

async function request(method, path, body) {
  let res;
  try {
    res = await fetch(BASE + path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(
      "API not reachable. Start it with: python -m uvicorn app.api:app --port 8100"
    );
  }
  if (!res.ok) throw new ApiError(`${res.status}: ${await res.text()}`);
  return res.json();
}

const get = (p) => request("GET", p);
const post = (p, b) => request("POST", p, b);

export const api = {
  createRun: (body) => post("/runs", body),
  listRuns: () => get("/runs"),
  getRun: (id) => get(`/runs/${id}`),
  pendingReviews: () => get("/reviews/pending"),
  review: (runId, body) => post(`/runs/${runId}/review`, body),
  domains: () => get("/domains"),
  ask: (question, domain) => post("/ask", { question, domain }),
  auditOverview: () => get("/audit/overview"),
  auditContracts: () => get("/audit/contracts"),
  auditTrace: (id) => get(`/audit/traces/${id}`),
};
