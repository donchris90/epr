import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import ClientsPage from "./ClientsPage";
import LeadsPage from "./LeadsPage";
import OpportunitiesPage from "./OpportunitiesPage";

const TABS = [
  { to: "/business-development/pipeline", label: "Pipeline" },
  { to: "/business-development/leads", label: "Leads" },
  { to: "/business-development/clients", label: "Clients" },
];

export default function BDCModule() {
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
        <Route index element={<Navigate to="/business-development/pipeline" replace />} />
        <Route path="pipeline" element={<OpportunitiesPage />} />
        <Route path="leads" element={<LeadsPage />} />
        <Route path="clients" element={<ClientsPage />} />
      </Routes>
    </div>
  );
}
