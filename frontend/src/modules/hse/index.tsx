import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import PermitsPage from "./PermitsPage";
import IncidentsPage from "./IncidentsPage";

const TABS = [
  { to: "/hse/permits", label: "Permits to Work" },
  { to: "/hse/incidents", label: "Incidents" },
];

export default function HSEModule() {
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
        <Route index element={<Navigate to="/hse/permits" replace />} />
        <Route path="permits" element={<PermitsPage />} />
        <Route path="incidents" element={<IncidentsPage />} />
      </Routes>
    </div>
  );
}
