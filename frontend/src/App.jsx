import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import RunPage from "./pages/RunPage.jsx";
import ReviewPage from "./pages/ReviewPage.jsx";
import HistoryPage from "./pages/HistoryPage.jsx";
import AskPage from "./pages/AskPage.jsx";
import AuditPage from "./pages/AuditPage.jsx";

const NAV = [
  ["/run", "Run"],
  ["/review", "Review queue"],
  ["/history", "History"],
  ["/ask", "Ask (RAG)"],
  ["/audit", "Audit"],
];

export default function App() {
  return (
    <div className="container">
      <header className="topbar">
        <div>
          <div className="logo">🛡️ Web Testing Agent</div>
          <div className="tag">Change-triggered checks · suggest-only fixes</div>
        </div>
        <nav>
          {NAV.map(([to, label]) => (
            <NavLink key={to} to={to} className={({ isActive }) => (isActive ? "active" : "")}>
              {label}
            </NavLink>
          ))}
        </nav>
      </header>
      <hr className="nav-sep" />
      <Routes>
        <Route path="/" element={<Navigate to="/run" replace />} />
        <Route path="/run" element={<RunPage />} />
        <Route path="/review" element={<ReviewPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/ask" element={<AskPage />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="*" element={<Navigate to="/run" replace />} />
      </Routes>
    </div>
  );
}
