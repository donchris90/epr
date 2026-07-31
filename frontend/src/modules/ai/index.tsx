import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import ToolsPage from "./ToolsPage";
import ExtractionPage from "./ExtractionPage";

const TABS = [
  { to: "tools", label: "Tools & Audit Log" },
  { to: "extraction", label: "Document Extraction" },
];

export default function AIModule() {
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
        <Route index element={<Navigate to="tools" replace />} />
        <Route path="tools" element={<ToolsPage />} />
        <Route path="extraction" element={<ExtractionPage />} />
      </Routes>
    </div>
  );
}
