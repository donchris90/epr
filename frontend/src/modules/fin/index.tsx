import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import SetupPage from "./SetupPage";
import LedgerPage from "./LedgerPage";
import ReportsPage from "./ReportsPage";

const TABS = [
  { to: "/finance/setup", label: "Setup" },
  { to: "/finance/ledger", label: "Ledger" },
  { to: "/finance/reports", label: "Reports" },
];

export default function FINModule() {
  return (
    <div>
      <div style={{ display: "flex", gap: 4, marginBottom: 4 }}>
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            style={({ isActive }) => ({
              padding: "6px 12px",
              fontSize: 12,
              fontWeight: 600,
              textDecoration: "none",
              color: isActive ? "var(--sf-navy-900)" : "var(--sf-navy-400)",
              borderBottom: isActive ? "2px solid var(--sf-amber)" : "2px solid transparent",
            })}
          >
            {tab.label}
          </NavLink>
        ))}
      </div>
      <Routes>
        <Route index element={<Navigate to="/finance/setup" replace />} />
        <Route path="setup" element={<SetupPage />} />
        <Route path="ledger" element={<LedgerPage />} />
        <Route path="reports" element={<ReportsPage />} />
      </Routes>
    </div>
  );
}
