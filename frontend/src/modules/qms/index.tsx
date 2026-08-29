import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import ITPsPage from "./ITPsPage";
import NCRsPage from "./NCRsPage";
import MaterialApprovalsAndLabResultsPage from "./MaterialApprovalsAndLabResultsPage";
import PunchAndSnagListsPage from "./PunchAndSnagListsPage";

const TABS = [
  { to: "/quality/itps", label: "ITPs & Hold Points" },
  { to: "/quality/ncrs", label: "NCRs" },
  { to: "/quality/material-lab", label: "Material Approvals & Lab Results" },
  { to: "/quality/punch-snag", label: "Punch & Snag Lists" },
];

export default function QMSModule() {
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
        <Route index element={<Navigate to="/quality/itps" replace />} />
        <Route path="itps" element={<ITPsPage />} />
        <Route path="ncrs" element={<NCRsPage />} />
        <Route path="material-lab" element={<MaterialApprovalsAndLabResultsPage />} />
        <Route path="punch-snag" element={<PunchAndSnagListsPage />} />
      </Routes>
    </div>
  );
}
