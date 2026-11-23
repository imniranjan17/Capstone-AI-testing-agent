import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev the UI (5173) proxies API calls to FastAPI so no CORS setup is needed.
// In production FastAPI serves the built files itself (same origin).
const target = process.env.AGENT_API_URL || "http://localhost:8100";
const API_PREFIXES = ["/runs", "/reviews", "/audit", "/domains", "/stats", "/ask"];

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(API_PREFIXES.map((p) => [p, { target, changeOrigin: true }])),
  },
});
